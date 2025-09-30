# src/balances.py
"""
Balances module — обновлённая версия, совместимая с keys.py и config.py.
Сохраняет прежнее поведение CSV и snapshot-логики, но делает операции
по возможности более безопасными (атомарная запись, простая блокировка).
"""

from __future__ import annotations

import argparse
import logging
import os
import re
import glob
import tempfile
from datetime import datetime
from decimal import Decimal
from typing import Dict, List, Any

import pandas as pd
from tabulate import tabulate

from api import KrakenAPI
from keys import load_keys, keys_exist, KeysError
import storage
from ledger_loader import update_raw_ledger
import ledger_eur_report
import ledger_asset_report
import ledger_sell_report
from config import BALANCES_HISTORY_DIR as CFG_BALANCES_DIR


# backward compatible default for tests that expect string path "balances_history"
# CFG_BALANCES_DIR may be Path object; normalize to str
BALANCES_DIR = str(CFG_BALANCES_DIR)
SNAPSHOTS_FILE = os.path.join(BALANCES_DIR, "portfolio_snapshots.csv")

# Lockfile name inside balances dir to avoid concurrent runs
_LOCKFILE_NAME = ".balances_lock"

# ---------------- ЛОГИРОВАНИЕ ---------------- #
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[logging.StreamHandler()],
)
logger = logging.getLogger(__name__)


# ---------------- CSV REPORTS ---------------- #
def generate_all_reports(days: int = 7, update: bool = True) -> None:
    """Central entrypoint: update raw ledger + regenerate all reports."""
    if update:
        update_raw_ledger(days=days)

    entries = storage.load_entries()

    # EUR report
    df_eur = ledger_eur_report.build_eur_report(entries, days=days)
    if not df_eur.empty:
        ledger_eur_report.save_eur_report(df_eur)

    # Asset report
    df_asset = ledger_asset_report.build_asset_report(entries, days=days)
    if not df_asset.empty:
        out_asset = os.path.join(BALANCES_DIR, "ledger_asset_report.csv")
        _atomic_to_csv(df_asset, out_asset, sep=";", index=False)

    # Sell report
    df_sell = ledger_sell_report.build_sell_report(entries, days=days)
    if not df_sell.empty:
        out_sell = os.path.join(BALANCES_DIR, "ledger_sell_report.csv")
        _atomic_to_csv(df_sell, out_sell, sep=";", index=False)


# ---------------- УТИЛИТЫ ---------------- #
def normalize_asset_code(asset: str) -> str:
    """Нормализует код актива (убирает .S/.F/.B и цифровые суффиксы и common single-letter suffix)."""
    # remove dotted suffixes first
    base = re.split(r"\.", asset, maxsplit=1)[0]
    # remove trailing digits
    base = re.sub(r"\d+$", "", base)
    # if there's a common single-letter suffix (B/F/S) appended without dot, strip it for long codes
    if len(base) > 3 and base[-1] in {"B", "F", "S"}:
        base = base[:-1]
    return base


def compute_trends(df: pd.DataFrame) -> pd.DataFrame:
    """Добавляет тренды на основе предыдущих CSV (balance_YYYY-MM-DD.csv)."""
    os.makedirs(BALANCES_DIR, exist_ok=True)
    csv_files = sorted(glob.glob(os.path.join(BALANCES_DIR, "balance_*.csv")))
    for fpath in csv_files:
        try:
            date_str = os.path.basename(fpath).split("_")[1].split(".")[0]
        except Exception:
            continue
        try:
            prev_df = pd.read_csv(fpath)
        except Exception:
            logger.debug("Cannot read previous balances file %s", fpath)
            continue
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


# helper to make API responses uniform: accept tuple wrappers and {'result': ...} shapes
def _unwrap_api_response(resp: Any) -> Any:
    """Unwrap API response which may be a tuple or have a 'result' key."""
    # Unwrap tuple/list if API wrapper returned (resp, ) or (resp, error)
    if isinstance(resp, (tuple, list)) and resp:
        # prefer the first dict-like element
        for item in resp:
            if isinstance(item, dict):
                resp = item
                break
        else:
            # fallback: take first element
            resp = resp[0]
    # If response has Kraken-style envelope, return inner 'result'
    if isinstance(resp, dict) and "result" in resp:
        return resp["result"]
    return resp


def fetch_balances(api: KrakenAPI) -> Dict[str, float]:
    balances_raw = _unwrap_api_response(api.get_balance())
    if not balances_raw:
        return {}
    # if wrapped like {'XXBT': '1.0'} or similar
    if isinstance(balances_raw, dict):
        return {a: float(v) for a, v in balances_raw.items() if float(v) > 0}
    # unexpected shape -> return empty
    return {}


def fetch_asset_pairs(api: KrakenAPI) -> dict:
    resp = _unwrap_api_response(api.get_asset_pairs())
    if not resp:
        raise RuntimeError("AssetPairs error: пустой ответ")
    return resp


def fetch_prices_batch(api: KrakenAPI, pairs: List[str]) -> Dict[str, Decimal]:
    """Получаем цены одним батч-запросом Ticker."""
    if not pairs:
        return {}
    resp = _unwrap_api_response(api.get_ticker(",".join(pairs)))
    if not resp:
        return {}
    prices: Dict[str, Decimal] = {}
    for pair, data in resp.items():
        try:
            # Kraken ticker shape: data['c'][0] (close price string)
            if isinstance(data, dict) and "c" in data and data["c"]:
                prices[pair] = Decimal(data["c"][0])
            else:
                # if direct numeric or unexpected, try to coerce
                prices[pair] = Decimal(data)
        except Exception:
            logger.warning("Ошибка получения цены для %s", pair)
    return prices


def _atomic_to_csv(df: pd.DataFrame, out_path: str, **to_csv_kwargs) -> None:
    """Сохраняет DataFrame в CSV атомарно (через temp file + os.replace)."""
    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    dir_for_temp = os.path.dirname(out_path) or "."
    fd, tmppath = tempfile.mkstemp(prefix=".tmp_", dir=dir_for_temp, text=True)
    os.close(fd)
    try:
        # use pandas to_csv writing to tmppath
        df.to_csv(tmppath, **to_csv_kwargs)
        # replace target
        os.replace(tmppath, out_path)
    except Exception:
        # cleanup tmp file if something went wrong
        try:
            if os.path.exists(tmppath):
                os.remove(tmppath)
        except Exception:
            pass
        raise


def _write_json_atomic(data, out_path: str) -> None:
    """Если понадобится — сохранять JSON атомарно (placeholder)."""
    import json

    os.makedirs(os.path.dirname(out_path), exist_ok=True)
    dir_for_temp = os.path.dirname(out_path) or "."
    fd, tmppath = tempfile.mkstemp(prefix=".tmp_", dir=dir_for_temp, text=True)
    os.close(fd)
    try:
        with open(tmppath, "w", encoding="utf-8") as f:
            json.dump(data, f, ensure_ascii=False, indent=2)
        os.replace(tmppath, out_path)
    except Exception:
        if os.path.exists(tmppath):
            os.remove(tmppath)
        raise


def _acquire_lock(timeout: int = 1) -> bool:
    """Простейшая блокировка через создание .lock файла.
    Возвращает True если блокировка получена, False если нет.
    Не ждём долго — минимальная защита от параллельных запусков.
    """
    try:
        os.makedirs(BALANCES_DIR, exist_ok=True)
        lockfile = os.path.join(BALANCES_DIR, _LOCKFILE_NAME)
        # O_EXCL + O_CREAT to ensure atomic creation
        flags = os.O_CREAT | os.O_EXCL | os.O_WRONLY
        # Windows may not support mode param meaningfully; ignore permission setting errors
        fd = os.open(lockfile, flags)
        os.close(fd)
        return True
    except FileExistsError:
        logger.debug("Lock file exists (%s). Another process may be running.", lockfile)
        return False
    except Exception:
        logger.debug("Cannot create lock file; proceeding without lock.")
        return True


def _release_lock() -> None:
    try:
        lockfile = os.path.join(BALANCES_DIR, _LOCKFILE_NAME)
        if os.path.exists(lockfile):
            os.remove(lockfile)
    except Exception:
        logger.debug("Failed to remove lock file", exc_info=True)


# ---------------- ОСНОВНАЯ ЛОГИКА ---------------- #
def main(argv=None) -> int:
    """Main CLI entrypoint for balances. Returns int exit code."""
    import sys

    argv = argv or sys.argv[1:]
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
    parser.add_argument(
        "--no-update",
        dest="update",
        default=True,
        action="store_false",
        help="Не обновлять ledger",
    )
    # use parse_known_args so CI/pytest flags won't break invocation
    args, _unknown = parser.parse_known_args(argv)

    # Early exit if no keys (behaviour consistent with start.py)
    try:
        if not keys_exist():
            print(
                "ERROR: API-ключи Kraken не найдены. Создайте файл ключей или используйте --setup-keys."
            )
            return 2
        keys = load_keys()
    except FileNotFoundError:
        print("ERROR: API-ключи Kraken не найдены. Используйте --setup-keys.")
        return 2
    except KeysError as e:
        print(f"ERROR: Проблема с файлом ключей: {e}")
        return 3
    except Exception as e:
        logger.exception("Unexpected error while loading keys: %s", e)
        return 4

    # Accept both tuple/list and dict return types from load_keys()
    api_key = None
    api_secret = None
    if isinstance(keys, dict):
        api_key = keys.get("api_key") or keys.get("key")
        api_secret = keys.get("api_secret") or keys.get("secret")
    elif isinstance(keys, (tuple, list)) and len(keys) >= 2:
        api_key, api_secret = keys[0], keys[1]
    else:
        logger.error("Unexpected keys format from load_keys(): %r", keys)
        return 4

    # Instantiate API
    api = KrakenAPI(api_key, api_secret)

    # Update ledger if requested
    if args.update:
        try:
            update_raw_ledger(days=7)
        except Exception:
            logger.exception("Failed to update raw ledger")

    balances_raw = fetch_balances(api)
    if not balances_raw:
        logger.info("Нет ненулевых балансов.")
        return 0

    # try acquire lock (best-effort)
    locked = _acquire_lock()
    try:
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
        pairs_needed: List[str] = []
        asset_to_pair: Dict[str, str] = {}
        for asset in aggregated.keys():
            if asset == args.quote:
                continue
            candidates = [asset, f"X{asset}", f"Z{asset}"]
            found = False
            for cand in candidates:
                for pair_name, info in asset_pairs.items():
                    if info.get("base") == cand and info.get("quote") == args.quote:
                        asset_to_pair[asset] = pair_name
                        pairs_needed.append(pair_name)
                        found = True
                        break
                if found:
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

        if df.empty:
            logger.info("No assets above threshold after aggregation.")
            return 0

        # avoid division by zero
        if total_value == 0:
            df["Portfolio %"] = 0.0
        else:
            df["Portfolio %"] = (df["Value (EUR)"] / total_value * 100).round(6)

        df.sort_values(by="Value (EUR)", ascending=False, inplace=True)

        # Тренды
        df = compute_trends(df)

        # ---- Расчёт total_trend_value ---- #
        total_trend_value = 0.0
        if "Portfolio Trend Avg" in df.columns:
            total_trend_value = df.loc[
                df["Asset"] != "ZEUR", "Portfolio Trend Avg"
            ].sum()

        # ---- ВЫВОД НА ЭКРАН ---- #
        short_df = df[["Asset", "Amount", "Current Price (EUR)", "Value (EUR)"]]
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
        _atomic_to_csv(df, out_file, index=False, encoding="utf-8")
        logger.info(f"CSV сохранён: {out_file}")

        # ---- СОХРАНЕНИЕ SNAPSHOT CSV ---- #
        snapshot_row = {
            "Timestamp": datetime.now().strftime("%d.%m.%Y"),
            "Portfolio Value (EUR)": round(total_value, 2),
            "Portfolio Trend Avg (EUR)": round(total_trend_value, 2),
            "Total Potential Value": round(total_value + total_trend_value, 2),
        }

        os.makedirs(BALANCES_DIR, exist_ok=True)

        if not os.path.exists(SNAPSHOTS_FILE):
            # write single-row dataframe atomically
            _atomic_to_csv(
                pd.DataFrame([snapshot_row]),
                SNAPSHOTS_FILE,
                sep=";",
                index=False,
                encoding="utf-8",
            )
        else:
            try:
                snapshots = pd.read_csv(SNAPSHOTS_FILE, sep=";", encoding="utf-8")
            except Exception:
                snapshots = pd.DataFrame()
            if (
                not snapshots.empty
                and snapshots.iloc[-1]["Timestamp"] == snapshot_row["Timestamp"]
            ):
                for k, v in snapshot_row.items():
                    snapshots.loc[snapshots.index[-1], k] = v
            else:
                snapshots = pd.concat(
                    [snapshots, pd.DataFrame([snapshot_row])], ignore_index=True
                )

            # save atomically
            _atomic_to_csv(
                snapshots, SNAPSHOTS_FILE, sep=";", index=False, encoding="utf-8"
            )

        logger.info(f"Снапшот портфеля обновлён в {SNAPSHOTS_FILE}")

    finally:
        if locked:
            _release_lock()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
