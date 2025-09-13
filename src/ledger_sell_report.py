# ledger_sell_report.py
import argparse
import logging
import os
import time
from datetime import datetime, UTC
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

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )


EUR_ASSETS = {"ZEUR", "EUR"}


def build_sell_report(entries: Dict[str, Any], days: int = 7) -> pd.DataFrame:
    """Aggregate sell operations: coins sold, EUR received, fee paid."""
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

    daily: Dict[str, Dict[str, Any]] = {}

    for ref, items in groups.items():
        sells = [
            i
            for i in items
            if float(i.get("amount", 0)) < 0 and i.get("asset") not in EUR_ASSETS
        ]
        euros = [
            i
            for i in items
            if i.get("asset") in EUR_ASSETS and float(i.get("amount", 0)) > 0
        ]
        if not sells or not euros:
            continue

        ts = float(sells[0].get("time", 0))
        # date = datetime.utcfromtimestamp(ts).strftime("%d.%m.%Y")
        date = datetime.fromtimestamp(ts, UTC).strftime("%d.%m.%Y")

        if date not in daily:
            daily[date] = {"Date": date, "Total Fee": 0.0, "Total EUR": 0.0}

        row = daily[date]

        for s in sells:
            asset = s.get("asset")
            amt = abs(float(s.get("amount", 0)))
            fee = float(s.get("fee", 0))
            row[asset] = row.get(asset, 0.0) + amt
            row["Total Fee"] = row.get("Total Fee", 0.0) + fee

        for e in euros:
            eur_amt = float(e.get("amount", 0))
            row["Total EUR"] = row.get("Total EUR", 0.0) + eur_amt

    rows = list(daily.values())
    df = pd.DataFrame(rows)
    df = df.fillna(0.0)

    if "Date" in df.columns:
        df["__sort_dt"] = pd.to_datetime(df["Date"], format="%d.%m.%Y", errors="coerce")
        df.sort_values("__sort_dt", inplace=True)
        df.drop(columns="__sort_dt", inplace=True)

    return df


def save_sell_report(df: pd.DataFrame):
    os.makedirs(storage.BALANCES_DIR, exist_ok=True)
    df.to_csv(LEDGER_SELL_FILE, sep=";", index=False, encoding="utf-8")
    logger.info(f"SELL report saved to {LEDGER_SELL_FILE}")


def update_sell_report(days: int = 7, write_csv: bool = False):
    entries = storage.load_entries_from_db()
    if not entries:
        logger.warning("No data for SELL report")
        return

    df = build_sell_report(entries, days=days)
    if df.empty:
        logger.warning("SELL report is empty")
        return

    if write_csv:
        save_sell_report(df)
    logger.info("SELL report updated")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="Number of days to include")
    parser.add_argument("--csv", action="store_true", help="Export to CSV")
    args = parser.parse_args()

    # entries = storage.load_entries() # backup menthod from JSON jile
    entries = storage.load_entries_from_db()
    df = build_sell_report(entries, days=args.days)

    if df.empty:
        logger.warning("No data for sell report")
        return

    if args.csv:
        out = os.path.join(storage.BALANCES_DIR, "ledger_sell_report.csv")
        os.makedirs(storage.BALANCES_DIR, exist_ok=True)
        df.to_csv(out, sep=";", index=False, encoding="utf-8")
        logger.info(f"Sell report saved to {out}")
    else:
        print(df)


if __name__ == "__main__":
    main()
