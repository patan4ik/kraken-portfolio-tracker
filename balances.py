import argparse
import logging
import os
import re
import glob
import pandas as pd
from datetime import datetime
from decimal import Decimal
from tabulate import tabulate

from api import KrakenAPI
from config import load_keyfile

BALANCES_DIR = "balances_history"
SNAPSHOTS_FILE = os.path.join(BALANCES_DIR, "portfolio_snapshots.csv")

# ---------------- ЛОГИРОВАНИЕ ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# ---------------- УТИЛИТЫ ---------------- #
def normalize_asset_code(asset: str) -> str:
    base = re.split(r"\.", asset, maxsplit=1)[0]
    base = re.sub(r"\d+$", "", base)
    return base


def compute_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет тренды на основе предыдущих CSV."""
    os.makedirs(BALANCES_DIR, exist_ok=True)
    csv_files = sorted(glob.glob(os.path.join(BALANCES_DIR, "balance_*.csv")))
    for fpath in csv_files:
        date_str = os.path.basename(fpath).split("_")[1].split(".")[0]
        prev_df = pd.read_csv(fpath)
        if "Asset" not in prev_df.columns or "Value (EUR)" not in prev_df.columns:
            continue
        trend_col = f"Trend_{date_str}"
        df[trend_col] = 0.0
        for asset in df["Asset"]:
            match = prev_df.loc[prev_df["Asset"] == asset, "Value (EUR)"]
            if not match.empty:
                df.loc[df["Asset"] == asset, trend_col] = round(
                    df.loc[df["Asset"] == asset, "Value (EUR)"].values[0]
                    - match.values[0],
                    2,
                )

    trend_cols = [c for c in df.columns if c.startswith("Trend_")]
    if trend_cols:
        df["Portfolio Trend Avg"] = df[trend_cols].mean(axis=1).round(2)
    return df


def fetch_balances(api: KrakenAPI) -> dict[str, float]:
    balances_raw = api.get_balance()
    return {a: float(v) for a, v in balances_raw.items() if float(v) > 0}


def fetch_asset_pairs(api: KrakenAPI) -> dict:
    resp = api.get_asset_pairs()
    if not resp:
        raise RuntimeError("AssetPairs error: пустой ответ")
    return resp


def fetch_prices_batch(api: KrakenAPI, pairs: list[str]) -> dict[str, Decimal]:
    """Получаем цены одним батч-запросом Ticker."""
    resp = api.get_ticker(",".join(pairs))
    if not resp:
        return {}
    prices = {}
    for pair, data in resp.items():
        try:
            prices[pair] = Decimal(data["c"][0])
        except Exception:
            logger.warning("Ошибка получения цены для %s", pair)
    return prices


# ---------------- ОСНОВНАЯ ЛОГИКА ---------------- #
def main():
    parser = argparse.ArgumentParser(description="Kraken Portfolio Balances")
    parser.add_argument(
        "--quote", default="ZEUR", help="Валюта для оценки (по умолчанию ZEUR)"
    )
    parser.add_argument(
        "--min-balance",
        type=float,
        default=0.001,
        help="Минимальный баланс для отображения",
    )
    args = parser.parse_args()

    # API
    try:
        api_key, api_secret = load_keyfile()
    except RuntimeError as e:
        logger.error(e)
        return
    api = KrakenAPI(api_key, api_secret)

    balances_raw = fetch_balances(api)
    if not balances_raw:
        logger.info("Нет ненулевых балансов.")
        return

    # Агрегация (available/staked)
    aggregated = {}
    for asset, amt in balances_raw.items():
        base = normalize_asset_code(asset)
        available, staked = 0.0, 0.0
        if re.search(r"\.S$|\.F$|\.B$", asset):
            staked = amt
        else:
            available = amt
        if base not in aggregated:
            aggregated[base] = {"available": 0.0, "staked": 0.0}
        aggregated[base]["available"] += available
        aggregated[base]["staked"] += staked

    # AssetPairs
    asset_pairs = fetch_asset_pairs(api)

    # Формируем список пар для батч-запроса
    pairs_needed = []
    asset_to_pair = {}
    for asset in aggregated.keys():
        if asset == args.quote:
            continue
        candidates = [asset, f"X{asset}", f"Z{asset}"]
        for cand in candidates:
            for pair_name, info in asset_pairs.items():
                if info.get("base") == cand and info.get("quote") == args.quote:
                    asset_to_pair[asset] = pair_name
                    pairs_needed.append(pair_name)
                    break

    # Получаем цены батчем
    prices = fetch_prices_batch(api, pairs_needed)

    # Считаем портфель
    rows = []
    total_value = 0.0
    for asset, info in aggregated.items():
        amount_total = info["available"] + info["staked"]
        if amount_total < args.min_balance:
            continue
        price_eur = (
            1.0
            if asset == args.quote
            else float(prices.get(asset_to_pair.get(asset), 0))
        )
        val_avail = info["available"] * price_eur
        val_staked = info["staked"] * price_eur
        value_total = val_avail + val_staked
        total_value += value_total

        rows.append(
            [
                asset,
                round(amount_total, 8),
                round(price_eur, 8),
                round(value_total, 8),
                round(info["available"], 8),
                round(val_avail, 8),
                round(info["staked"], 8),
                round(val_staked, 8),
                0.0,  # Total Fees (EUR) placeholder
                0.0,  # Avg Buy Price (EUR) placeholder
            ]
        )

    df = pd.DataFrame(
        rows,
        columns=[
            "Asset",
            "Amount",
            "Current Price (EUR)",
            "Value (EUR)",
            "Available",
            "Available EUR",
            "Staked",
            "Staked EUR",
            "Total Fees (EUR)",
            "Avg Buy Price (EUR)",
        ],
    )
    df["Portfolio %"] = (df["Value (EUR)"] / total_value * 100).round(6)
    df.sort_values(by="Value (EUR)", ascending=False, inplace=True)

    # Тренды
    df = compute_trends(df)

    # ---- Расчёт total_trend_value (исправленный) ---- #
    total_trend_value = 0.0
    if "Portfolio Trend Avg" in df.columns:
        #        total_trend_value = df["Portfolio Trend Avg"].sum()
        total_trend_value = df.loc[df["Asset"] != "ZEUR", "Portfolio Trend Avg"].sum()

    #    trend_cols = [c for c in df.columns if c.startswith("Trend_")]
    #    if trend_cols:
    #        total_trend_value = df_trends.sum(axis=1).sum()

    # ---- ВЫВОД НА ЭКРАН ---- #
    short_df = df[["Asset", "Amount", "Current Price (EUR)", "Value (EUR)"]]
    # extra row to enable for unit test_main_creates_balance_and_snapshot, test_snapshots_update_last_row, test_snapshots_append_new_day functionality check.
    # Expected result - KeyError: "['AssetX'] not in index
    # short_df = df[["AssetX", "Amount", "Current Price (EUR)", "Value (EUR)"]]
    logger.info(
        "\n" + tabulate(short_df, headers="keys", tablefmt="psql", showindex=False)
    )
    logger.info(
        f"\nИТОГО: €{total_value:,.2f} | Trend: €{total_trend_value:,.2f} | Прогноз: €{(total_value + total_trend_value):,.2f}"
    )

    # ---- СОХРАНЕНИЕ ОСНОВНОГО CSV ---- #
    os.makedirs(BALANCES_DIR, exist_ok=True)
    ts = datetime.now().strftime("%Y-%m-%d")
    out_file = os.path.join(BALANCES_DIR, f"balance_{ts}.csv")
    df.to_csv(out_file, index=False, encoding="utf-8")
    logger.info(f"CSV сохранён: {out_file}")

    # ---- СОХРАНЕНИЕ SNAPSHOT CSV (исправленный режим) ---- #
    snapshot_row = {
        "Timestamp": datetime.now().strftime("%d.%m.%Y"),
        "Portfolio Value (EUR)": round(total_value, 2),
        "Portfolio Trend Avg (EUR)": round(total_trend_value, 2),
        "Total Potential Value": round(total_value + total_trend_value, 2),
    }

    os.makedirs(BALANCES_DIR, exist_ok=True)

    if not os.path.exists(SNAPSHOTS_FILE):
        pd.DataFrame([snapshot_row]).to_csv(
            SNAPSHOTS_FILE, sep=";", index=False, encoding="utf-8"
        )
    else:
        snapshots = pd.read_csv(SNAPSHOTS_FILE, sep=";", encoding="utf-8")
        if (
            not snapshots.empty
            and snapshots.iloc[-1]["Timestamp"] == snapshot_row["Timestamp"]
        ):
            snapshots.iloc[-1] = snapshot_row
        else:
            snapshots = pd.concat(
                [snapshots, pd.DataFrame([snapshot_row])], ignore_index=True
            )
        # comment next snapshots.to_csv row for unit test_snapshots_update_last_row, test_snapshots_append_new_day functionality check.
        # Expected result - tests\test_main_and_snapshots.py:93: AssertionError (logic error CSV file not updated)
        snapshots.to_csv(SNAPSHOTS_FILE, sep=";", index=False, encoding="utf-8")

    logger.info(f"Снапшот портфеля обновлён в {SNAPSHOTS_FILE}")

    # Pause for reading output on the screen
    # print("Script has finished running. Press Enter to exit.")
    # input()


if __name__ == "__main__":
    main()
