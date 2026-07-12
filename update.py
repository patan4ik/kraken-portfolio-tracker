#!/usr/bin/env python3
# update.py — incremental ledger updater (safe incremental update)

from __future__ import annotations
import argparse
import logging
import os
import sys
from datetime import datetime, date, timedelta, timezone
from typing import Optional, Tuple, Dict, Any, Set

# ensure src on path when running from repo root
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import storage
import ledger_loader
import portfolio_summary_report
import portfolio_summary
import balances
import balance_reconciliation
from api import KrakenAPI
from keys import load_keys, KeysError
from config import DEFAULT_DAYS, DEFAULT_PAGE_SIZE, DEFAULT_DELAY_MIN, DEFAULT_DELAY_MAX
from validators import (
    validate_for_update,
    DatabaseMissingError,
    SchemaInvalidError,
    APIKeyError,
)

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )


def _run_portfolio_summary():
    """
    Refresh live Kraken balance snapshot (balances.py), recompute FIFO +
    price forecast from the full ledger, refresh the `summary` DB table +
    CSV export, then cross-check FIFO amount/price against the live
    balance snapshot (reconciliation — validation only, never overrides
    FIFO output). Called on every successful update.py exit path (data
    changed OR "already up to date"), but never on --dry-run or error exits.
    Failure here never fails the whole update.py run — the ledger update
    itself already succeeded and was persisted before this step runs.
    """
    # Step 1: refresh live balance snapshot. --no-update because update.py
    # already fetched/persisted new ledger entries earlier in this run.
    try:
        balances.main(["--no-update"])
    except Exception as e:
        logger.exception("balances.py refresh failed (non-fatal): %s", e)

    # Step 2: recompute FIFO summary + forecast, write CSV
    try:
        summary_df = portfolio_summary_report.update_summary_report(write_csv=True)
        if summary_df is not None and not summary_df.empty:
            logger.info(f" - Portfolio summary: {len(summary_df)} assets")
        else:
            logger.warning("Portfolio summary returned no rows")
            return
    except Exception as e:
        logger.exception("Portfolio summary step failed: %s", e)
        return

    # Step 3: reconcile FIFO output against live balance snapshot
    try:
        fifo_raw = portfolio_summary.update_summary()
        balance_reconciliation.run_reconciliation(fifo_raw, write_csv=True)
    except Exception as e:
        logger.exception("Reconciliation step failed (non-fatal): %s", e)


def parse_relative_or_date(s: str) -> date:
    s = s.strip()
    if not s:
        raise ValueError("Empty date")
    now = datetime.now(timezone.utc).date()
    if s.lower().endswith("d") and s[:-1].isdigit():
        return now - timedelta(days=int(s[:-1]))
    if s.lower().endswith("m") and s[:-1].isdigit():
        return now - timedelta(days=30 * int(s[:-1]))
    for fmt in ("%Y-%m-%d", "%d.%m.%Y"):
        try:
            return datetime.strptime(s, fmt).date()
        except Exception:
            continue
    raise ValueError(f"Unsupported date format: {s}")


def get_db_date_range(db_path: str) -> Tuple[Optional[date], Optional[date]]:
    """Return (min_date, max_date) present in DB (based on date_iso column)."""
    if not os.path.exists(db_path):
        return None, None
    try:
        conn = __import__("sqlite3").connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ledger'"
        )
        if not cur.fetchone():
            conn.close()
            return None, None
        try:
            cur.execute("SELECT MIN(date_iso), MAX(date_iso) FROM ledger")
            row = cur.fetchone()
            conn.close()
            if not row:
                return None, None
            min_iso, max_iso = row
            if not min_iso or not max_iso:
                return None, None
            return (
                datetime.fromisoformat(min_iso).date(),
                datetime.fromisoformat(max_iso).date(),
            )
        except Exception:
            conn.close()
            return None, None
    except Exception as e:
        logger.warning("Could not inspect DB: %s", e)
        return None, None


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Incremental ledger updater (requires initialized DB)"
    )
    parser.add_argument(
        "--fromdate",
        help="Start date or relative (e.g. 30d). Default: last %(default)s days",
        default=f"{DEFAULT_DAYS}d",
    )
    parser.add_argument(
        "--todate", help="End date or relative (default: today)", default=None
    )
    parser.add_argument(
        "--dry-run", action="store_true", help="Do not download; just print plan"
    )
    parser.add_argument(
        "--page-size", type=int, default=None, help="Page size for API calls"
    )
    parser.add_argument(
        "--delay-min", type=float, default=None, help="Min delay between API calls"
    )
    parser.add_argument(
        "--delay-max", type=float, default=None, help="Max delay between API calls"
    )
    parser.add_argument(
        "--no-summary",
        action="store_true",
        help="Skip portfolio FIFO summary/forecast recompute after updating the ledger",
    )

    args = parser.parse_args(argv)

    # Parse input dates
    try:
        target_from = parse_relative_or_date(args.fromdate)
    except Exception as e:
        logger.error("Invalid --fromdate: %s", e)
        return 2

    if args.todate:
        try:
            target_to = parse_relative_or_date(args.todate)
        except Exception as e:
            logger.error("Invalid --todate: %s", e)
            return 2
    else:
        target_to = datetime.now(timezone.utc).date()

    if target_from > target_to:
        logger.error("--fromdate must be <= --todate")
        return 2

    # Validate environment (DB must exist and have ledger table, keys present)
    try:
        validate_for_update(storage.LEDGER_DB_FILE)
    except DatabaseMissingError as e:
        logger.error("Database missing: %s", e)
        logger.info(
            "Run: python start.py --days=%s to initialize database first", DEFAULT_DAYS
        )
        return 1
    except SchemaInvalidError as e:
        logger.error("Database schema issue: %s", e)
        logger.info(
            "Run: python start.py to initialize DB (it will create required tables)."
        )
        return 1
    except APIKeyError as e:
        logger.error("API key problem: %s", e)
        logger.info("Run: python start.py --setup-keys")
        return 1

    # DB date range for logging
    db_min, db_max = get_db_date_range(storage.LEDGER_DB_FILE)
    logger.info("DB date range: %s -> %s", db_min, db_max)

    missing_ranges = []
    now_date = datetime.now(timezone.utc).date()

    # Identify missing date ranges (prior to db_min and after db_max)
    if db_min is None or db_min > target_from:
        start = target_from
        end = (db_min - timedelta(days=1)) if db_min else target_to
        if start <= end:
            missing_ranges.append((start, min(end, target_to)))

    if db_max is None or db_max < target_to:
        start = (db_max + timedelta(days=1)) if db_max else target_from
        end = target_to
        if start <= end:
            missing_ranges.append((max(start, target_from), end))

    if not missing_ranges:
        logger.info("Database already covers requested range -> nothing to do.")
        if not args.no_summary:
            _run_portfolio_summary()
        return 0

    # Prepare API
    try:
        api_key, api_secret = load_keys()
        api = KrakenAPI(api_key, api_secret)
    except KeysError:
        logger.error(
            "Keys not found (unexpected after validate_for_update). Run start.py --setup-keys"
        )
        return 1

    page_size = args.page_size if args.page_size is not None else DEFAULT_PAGE_SIZE
    delay_min = args.delay_min if args.delay_min is not None else DEFAULT_DELAY_MIN
    delay_max = args.delay_max if args.delay_max is not None else DEFAULT_DELAY_MAX

    # Load currently known entries from DB (used to filter duplicates)
    existing_entries: Dict[str, Any] = storage.load_entries_from_db() or {}
    known_txids: Set[str] = set(existing_entries.keys())
    logger.info("Existing entries loaded from DB: %d", len(existing_entries))

    total_fetched = 0

    for start_fetch, end_fetch in missing_ranges:
        if start_fetch > now_date:
            logger.info("Requested start %s is in the future -> skip", start_fetch)
            continue

        since_dt = datetime(
            start_fetch.year, start_fetch.month, start_fetch.day, tzinfo=timezone.utc
        )
        since_ts = int(since_dt.timestamp())

        logger.info(
            "Fetching window %s -> %s (since_ts=%d); no early-stop",
            start_fetch,
            end_fetch,
            since_ts,
        )

        if args.dry_run:
            logger.info(
                "Dry run: not performing fetch for window %s -> %s",
                start_fetch,
                end_fetch,
            )
            continue

        # Fetch without early stopping
        fetched = ledger_loader.fetch_ledger(
            api,
            page_size=page_size,
            delay_min=delay_min,
            delay_max=delay_max,
            since_ts=since_ts,
            stop_on_txids=known_txids,
        )

        if not fetched:
            logger.info(
                "No entries fetched for window %s -> %s", start_fetch, end_fetch
            )
            continue

        logger.info("Fetched %d entries (raw)", len(fetched))

        # Filter to the requested date window
        filtered: Dict[str, Any] = {}
        for txid, entry in fetched.items():
            try:
                ts = float(entry.get("time", 0))
            except Exception:
                ts = 0.0
            try:
                entry_date = datetime.fromtimestamp(ts, tz=timezone.utc).date()
            except Exception:
                continue
            if start_fetch <= entry_date <= end_fetch:
                filtered[txid] = entry

        if not filtered:
            logger.info(
                "After filtering, no entries fall into %s -> %s", start_fetch, end_fetch
            )
            continue

        logger.info(
            "Filtered to %d entries within %s..%s",
            len(filtered),
            start_fetch,
            end_fetch,
        )

        # Persist update chunk (save only truly new entries)
        try:
            new_only = {
                txid: entry
                for txid, entry in filtered.items()
                if txid not in known_txids
            }

            if not new_only:
                logger.info(
                    "All %d filtered entries already exist in DB — nothing new to insert.",
                    len(filtered),
                )
                continue

            inserted_new = storage.save_update_entries(new_only)
            total_fetched += len(new_only)

            logger.info(
                "Inserted %d new entries (of %d filtered, %d duplicates skipped)",
                inserted_new,
                len(filtered),
                len(filtered) - len(new_only),
            )

            known_txids.update(new_only.keys())

        except Exception as e:
            logger.exception("Failed to persist fetched entries: %s", e)
            return 1

    final_count = len(storage.load_entries_from_db() or {})
    logger.info(
        "Ledger DB updated successfully — total rows: %d (fetched %d new)",
        final_count,
        total_fetched,
    )

    if not args.dry_run and not args.no_summary:
        _run_portfolio_summary()

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
