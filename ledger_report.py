# ledger_report.py
import os
import json
import time
import random
import logging
import pandas as pd
from datetime import datetime, timedelta
from collections import defaultdict
from api import KrakenAPI
from config import load_keyfile

BALANCES_DIR = "balances_history"
LEDGER_REPORT_FILE = os.path.join(BALANCES_DIR, "ledger_report.csv")
LEDGER_STATE_FILE = os.path.join(BALANCES_DIR, "ledger_state.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    datefmt="%d-%m-%Y %H:%M:%S",
)


def load_last_state() -> int:
    """Загрузить последний since из файла состояния"""
    if os.path.exists(LEDGER_STATE_FILE):
        try:
            with open(LEDGER_STATE_FILE, "r", encoding="utf-8") as f:
                state = json.load(f)
                return state.get("last_since", 0)
        except Exception:
            return 0
    return 0


def save_last_state(since: int):
    """Сохранить since в файл состояния"""
    os.makedirs(BALANCES_DIR, exist_ok=True)
    with open(LEDGER_STATE_FILE, "w", encoding="utf-8") as f:
        json.dump({"last_since": since}, f)


def collect_ledger_data(
    api: KrakenAPI, days: int = 7, max_pages: int = 20, dump_raw: bool = False
) -> pd.DataFrame:
    """Собирает покупки из леджера за последние N дней (постранично, с лимитом)."""
    since_file = load_last_state()
    since_ts = max(since_file, int((datetime.now() - timedelta(days=days)).timestamp()))

    logging.info(
        f"Collecting ledger data since {since_ts} ({datetime.fromtimestamp(since_ts)})"
    )

    ofs = 0
    all_entries = {}
    for page in range(1, max_pages + 1):
        resp = api.get_ledgers(since=since_ts, ofs=ofs)
        entries = resp.get("ledger", {}) if isinstance(resp, dict) else resp

        if not entries:
            break

        all_entries.update(entries)
        logging.info(
            f"[INFO] Page {page}: loaded {len(entries)} entries (total {len(all_entries)})"
        )

        ofs += 50
        time.sleep(1.5 + random.uniform(0, 1.0))  # маленькая задержка

    if dump_raw:
        with open(
            os.path.join(BALANCES_DIR, "ledger_raw.json"), "w", encoding="utf-8"
        ) as f:
            json.dump(all_entries, f, indent=2, ensure_ascii=False)

    if not all_entries:
        return pd.DataFrame()

    # Группировка транзакций (только buy: spend + receive с одинаковым refid)
    grouped = defaultdict(
        lambda: {"fee": 0.0, "spent": 0.0, "assets": defaultdict(float)}
    )
    for txid, entry in all_entries.items():
        ts = datetime.fromtimestamp(float(entry["time"]))
        date = ts.strftime("%d.%m.%Y")
        ttype = entry.get("type")
        asset = entry.get("asset")

        if ttype == "spend" and asset == "ZEUR":
            grouped[date]["spent"] += abs(float(entry["amount"]))
            grouped[date]["fee"] += float(entry.get("fee", 0.0))
        elif ttype == "receive":
            grouped[date]["assets"][asset] += float(entry["amount"])

    rows = []
    for date, vals in grouped.items():
        row = {
            "Date": date,
            "Total Fee": round(vals["fee"], 2),
            "Total Spent EUR": round(vals["spent"], 2),
        }
        for asset, amt in vals["assets"].items():
            row[asset] = round(amt, 8)
        rows.append(row)

    df = pd.DataFrame(rows).sort_values("Date")

    # Сохраняем прогресс (берём последний ts)
    last_ts = max(int(float(entry["time"])) for entry in all_entries.values())
    save_last_state(last_ts)

    return df


def save_ledger_report(new_df: pd.DataFrame, portfolio_assets: list[str]):
    """Сохраняет/обновляет ledger_report.csv с учётом новых активов."""
    os.makedirs(BALANCES_DIR, exist_ok=True)

    if os.path.exists(LEDGER_REPORT_FILE):
        old_df = pd.read_csv(LEDGER_REPORT_FILE, sep=";", encoding="utf-8")
    else:
        old_df = pd.DataFrame(
            columns=["Date", "Total Fee", "Total Spent EUR"] + portfolio_assets
        )

    for asset in portfolio_assets:
        if asset not in old_df.columns:
            old_df[asset] = 0.0
        if asset not in new_df.columns:
            new_df[asset] = 0.0

    merged = pd.concat([old_df.set_index("Date"), new_df.set_index("Date")], axis=0)
    merged = merged.groupby("Date").last().reset_index()

    final_cols = ["Date", "Total Fee", "Total Spent EUR"] + portfolio_assets
    merged = merged.reindex(columns=final_cols, fill_value=0.0)

    merged.to_csv(LEDGER_REPORT_FILE, sep=";", index=False, encoding="utf-8")
    logging.info(f"Ledger report сохранён в {LEDGER_REPORT_FILE}")
    return merged


def update_ledger_report(days: int = 7):
    """Основная функция: собрать данные и сохранить CSV."""
    api_key, api_secret = load_keyfile()
    api = KrakenAPI(api_key, api_secret)

    from balances import fetch_balances

    balances = fetch_balances(api)
    portfolio_assets = sorted([a for a in balances.keys() if a != "ZEUR"])

    new_df = collect_ledger_data(api, days=days, dump_raw=True)
    if new_df.empty:
        logging.info("Нет новых данных в леджере.")
        return

    result = save_ledger_report(new_df, portfolio_assets)
    logging.info("Ledger report обновлён:")
    logging.info("\n%s", result.tail())

    # Pause for reading output on the screen
    print("Script has finished running. Press Enter to exit.")
    input()


if __name__ == "__main__":
    update_ledger_report()
