# ledger_eur_report.py
import os
import logging
import time
import argparse
from datetime import datetime, UTC
from typing import Dict, Any, List, DefaultDict
from collections import defaultdict

import pandas as pd
import storage

LEDGER_EUR_FILE = os.path.join(storage.BALANCES_DIR, "ledger_eur_report.csv")
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

EUR_ASSETS = {"ZEUR", "EUR"}


def build_eur_report(entries: Dict[str, Any], days: int = 7) -> pd.DataFrame:
    """Build report of EUR spent per asset grouped by date."""
    if not entries:
        return pd.DataFrame()

    cutoff = time.time() - days * 86400
    filtered = {}
    for txid, e in entries.items():
        try:
            ts = float(e.get("time", 0))
        except Exception:
            continue
        typ = (e.get("type") or "").lower()
        if ts >= cutoff and typ in {"receive", "spend", "trade"}:
            out = dict(e)
            out["_txid"] = txid
            out["_time"] = ts
            out["_type"] = typ
            out["_asset"] = out.get("asset")
            filtered[txid] = out

    if not filtered:
        return pd.DataFrame()

    groups: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for txid, e in filtered.items():
        ref = e.get("refid") or txid
        groups[ref].append(e)

    daily: Dict[str, Dict[str, Any]] = {}

    for ref, items in groups.items():
        spends = [
            it
            for it in items
            if it["_asset"] in EUR_ASSETS and float(it.get("amount", 0)) < 0
        ]
        receives = [
            it
            for it in items
            if it["_asset"] not in EUR_ASSETS and float(it.get("amount", 0)) > 0
        ]

        if not spends or not receives:
            continue

        ts = float(spends[0]["_time"])
        date = datetime.fromtimestamp(ts, UTC).strftime("%d.%m.%Y")
        # date = datetime.utcfromtimestamp(ts).strftime("%d.%m.%Y")

        total_spent = sum(-float(s.get("amount", 0)) for s in spends)
        total_fee = sum(float(s.get("fee", 0)) for s in spends)

        recv_amounts = [abs(float(r.get("amount", 0))) for r in receives]
        total_recv_amount = sum(recv_amounts) if recv_amounts else 0.0

        alloc: Dict[str, float] = {}
        if total_recv_amount > 0 and len(receives) > 1:
            for r, amt in zip(receives, recv_amounts):
                asset = r.get("asset")
                alloc[asset] = alloc.get(asset, 0.0) + total_spent * (
                    amt / total_recv_amount
                )
        else:
            first_asset = receives[0].get("asset")
            alloc[first_asset] = alloc.get(first_asset, 0.0) + total_spent

        if date not in daily:
            daily[date] = {"Date": date, "Total Fee": 0.0, "Total Spent EUR": 0.0}
        daily_row = daily[date]
        daily_row["Total Fee"] += total_fee
        daily_row["Total Spent EUR"] += total_spent
        for asset, eur_val in alloc.items():
            daily_row[asset] = daily_row.get(asset, 0.0) + eur_val

    if not daily:
        return pd.DataFrame()

    rows = list(daily.values())
    df = pd.DataFrame(rows)

    assets = sorted(
        [c for c in df.columns if c not in {"Date", "Total Fee", "Total Spent EUR"}]
    )
    ordered_cols = ["Date", "Total Fee", "Total Spent EUR"] + assets
    df = df.reindex(columns=ordered_cols).fillna(0.0)

    df["__sort_dt"] = pd.to_datetime(df["Date"], format="%d.%m.%Y", errors="coerce")
    df.sort_values("__sort_dt", inplace=True)
    df.drop(columns="__sort_dt", inplace=True)

    df["Total Fee"] = df["Total Fee"].round(2)
    df["Total Spent EUR"] = df["Total Spent EUR"].round(2)
    for a in assets:
        df[a] = df[a].round(2)

    return df


def save_eur_report(df: pd.DataFrame):
    os.makedirs(storage.BALANCES_DIR, exist_ok=True)
    df.to_csv(LEDGER_EUR_FILE, sep=";", index=False, encoding="utf-8")
    logger.info(f"EUR report saved to {LEDGER_EUR_FILE}")


def update_eur_report(days: int = 7, write_csv: bool = False):
    entries = storage.load_entries_from_db()
    if not entries:
        logger.warning("No data for EUR report")
        return

    df = build_eur_report(entries, days=days)
    if df.empty:
        logger.warning("EUR report is empty")
        return

    if write_csv:
        save_eur_report(df)
    logger.info("EUR report updated")
    return df


def main():
    parser = argparse.ArgumentParser(description="Build EUR ledger report from DB")
    parser.add_argument("--days", type=int, default=7, help="Number of days to include")
    parser.add_argument("--csv", action="store_true", help="Export to CSV")
    args = parser.parse_args()

    # entries = storage.load_entries() # backup method from JSON file
    entries = storage.load_entries_from_db()
    df = build_eur_report(entries, days=args.days)

    if df.empty:
        logger.warning("No data for asset report")
        return

    if args.csv:
        out = os.path.join(storage.BALANCES_DIR, "ledger_eur_report.csv")
        os.makedirs(storage.BALANCES_DIR, exist_ok=True)
        df.to_csv(out, sep=";", index=False, encoding="utf-8")
        logger.info(f"EUR report saved to {out}")
    else:
        print(df)


if __name__ == "__main__":
    main()
