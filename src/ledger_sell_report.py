# ledger_sell_report.py
import argparse
import logging
import os
import time
from datetime import datetime, timezone
from collections import defaultdict
from typing import Dict, Any, List, DefaultDict

import pandas as pd
import storage

LEDGER_SELL_FILE = os.path.join(storage.BALANCES_DIR, "ledger_sell_report.csv")
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

EUR_ASSETS = {"ZEUR", "EUR"}


def build_sell_report(entries: Dict[str, Any], days: int = 7) -> pd.DataFrame:
    """Aggregate sells (crypto → EUR)."""
    if not entries:
        return pd.DataFrame()

    cutoff = time.time() - days * 86400
    filtered = {
        txid: e for txid, e in entries.items() if float(e.get("time", 0)) >= cutoff
    }
    if not filtered:
        return pd.DataFrame()

    groups: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for txid, e in filtered.items():
        ref = e.get("refid") or txid
        groups[ref].append(e)

    daily: Dict[datetime.date, Dict[str, Any]] = {}

    for ref, items in groups.items():
        sells = [
            it
            for it in items
            if it.get("asset") not in EUR_ASSETS and float(it.get("amount", 0)) < 0
        ]
        eur = [
            it
            for it in items
            if it.get("asset") in EUR_ASSETS and float(it.get("amount", 0)) > 0
        ]

        if not sells or not eur:
            continue

        first = sells[0]
        if first.get("date"):
            date_obj = datetime.fromisoformat(first["date"]).date()
        else:
            ts = float(first.get("time", 0))
            date_obj = datetime.fromtimestamp(ts, tz=timezone.utc).date()

        if date_obj not in daily:
            daily[date_obj] = {"Date": date_obj, "Total EUR": 0.0, "Total Fee": 0.0}
        daily_row = daily[date_obj]

        total_fee = sum(float(s.get("fee", 0)) for s in sells)
        total_eur = sum(float(r.get("amount", 0)) for r in eur)

        daily_row["Total Fee"] += total_fee
        daily_row["Total EUR"] += total_eur
        for s in sells:
            asset = s.get("asset")
            amt = abs(float(s.get("amount", 0)))
            daily_row[asset] = daily_row.get(asset, 0.0) + amt

    if not daily:
        return pd.DataFrame()

    rows = list(daily.values())
    df = pd.DataFrame(rows)

    assets = sorted(
        [c for c in df.columns if c not in {"Date", "Total EUR", "Total Fee"}]
    )
    ordered_cols = ["Date", "Total EUR", "Total Fee"] + assets
    df = df.reindex(columns=ordered_cols).fillna(0.0)

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df.sort_values("Date", inplace=True)
        df.reset_index(drop=True, inplace=True)

    df["Total EUR"] = df["Total EUR"].round(2)
    df["Total Fee"] = df["Total Fee"].round(2)
    for a in assets:
        df[a] = df[a].round(8)

    return df


def save_sell_report(df: pd.DataFrame):
    os.makedirs(storage.BALANCES_DIR, exist_ok=True)
    out = df.copy()
    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%d.%m.%Y")
    out.to_csv(LEDGER_SELL_FILE, sep=";", index=False, encoding="utf-8")
    logger.info(f"SELL report saved to {LEDGER_SELL_FILE}")


def update_sell_report(days: int = 7, write_csv: bool = False):
    entries = storage.load_entries_from_db()
    if not entries:
        logger.warning("No data for SELL report")
        return pd.DataFrame()

    df = build_sell_report(entries, days=days)
    if df.empty:
        logger.warning("SELL report is empty")
        return df

    if write_csv:
        save_sell_report(df)
    logger.info("SELL report updated")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="Number of days to include")
    parser.add_argument("--csv", action="store_true", help="Export to CSV")
    args = parser.parse_args()

    entries = storage.load_entries_from_db()
    df = build_sell_report(entries, days=args.days)

    if df.empty:
        logger.warning("No data for sell report")
        return

    if args.csv:
        save_sell_report(df)
    else:
        print(df)


if __name__ == "__main__":
    main()
