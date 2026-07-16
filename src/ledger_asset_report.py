# ledger_asset_report.py
import argparse
import logging
import os
import time
from datetime import date, datetime, timezone
from collections import defaultdict
from typing import Any, DefaultDict

import pandas as pd
import storage

LEDGER_ASSET_FILE = os.path.join(storage.BALANCES_DIR, "ledger_asset_report.csv")
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )


def build_asset_report(entries: dict[str, Any], days: int = 7) -> pd.DataFrame:
    """Aggregate received assets by day (all buys)."""
    if not entries:
        return pd.DataFrame()

    cutoff = time.time() - days * 86400
    filtered = {}
    for txid, e in entries.items():
        try:
            ts = float(e.get("time", 0))
        except (TypeError, ValueError):
            logger.debug(
                "Skipping ledger entry %s: unparsable time value %r",
                txid,
                e.get("time"),
            )
            continue
        if ts >= cutoff:
            filtered[txid] = e

    if not filtered:
        return pd.DataFrame()

    groups: DefaultDict[str, list[dict[str, Any]]] = defaultdict(list)
    for txid, e in filtered.items():
        ref = str(e.get("refid") or txid)
        groups[ref].append(e)

    daily: dict[date, dict[str, Any]] = {}

    for ref, items in groups.items():
        receives = [
            i
            for i in items
            if float(i.get("amount", 0)) > 0 and i.get("asset") not in {"ZEUR", "EUR"}
        ]
        if not receives:
            continue

        first = receives[0]
        if first.get("date"):
            date_obj = datetime.fromisoformat(first["date"]).date()
        else:
            ts = float(first.get("time", 0))
            date_obj = datetime.fromtimestamp(ts, tz=timezone.utc).date()

        if date_obj not in daily:
            daily[date_obj] = {"Date": date_obj}

        for r in receives:
            asset = str(r.get("asset"))
            amt = float(r.get("amount", 0))
            daily[date_obj][asset] = daily[date_obj].get(asset, 0.0) + amt

    rows = list(daily.values())
    df = pd.DataFrame(rows)
    df = df.fillna(0.0)

    if "Date" in df.columns:
        df["Date"] = pd.to_datetime(df["Date"])
        df.sort_values("Date", inplace=True)
        df.reset_index(drop=True, inplace=True)

    asset_cols = [c for c in df.columns if c != "Date"]
    for a in asset_cols:
        df[a] = df[a].round(8)

    return df


def save_asset_report(df: pd.DataFrame):
    os.makedirs(storage.BALANCES_DIR, exist_ok=True)
    out = df.copy()
    if "Date" in out.columns:
        out["Date"] = pd.to_datetime(out["Date"]).dt.strftime("%d.%m.%Y")
    out.to_csv(LEDGER_ASSET_FILE, sep=";", index=False, encoding="utf-8")
    logger.info(f"ASSET report saved to {LEDGER_ASSET_FILE}")


def update_asset_report(days: int = 7, write_csv: bool = False):
    entries = storage.load_entries_from_db()
    if not entries:
        logger.warning("No data for ASSET report")
        return pd.DataFrame()

    df = build_asset_report(entries, days=days)
    if df.empty:
        logger.warning("ASSET report is empty")
        return df

    if write_csv:
        save_asset_report(df)
    logger.info("ASSET report updated")
    return df


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--days", type=int, default=7, help="Number of days to include")
    parser.add_argument("--csv", action="store_true", help="Export to CSV")
    args = parser.parse_args()

    entries = storage.load_entries_from_db()
    df = build_asset_report(entries, days=args.days)

    if df.empty:
        logger.warning("No data for asset report")
        return

    if args.csv:
        save_asset_report(df)
    else:
        print(df)


if __name__ == "__main__":
    main()
