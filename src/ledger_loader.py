# src/ledger_loader.py
import time
import random
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional, Set

from api import KrakenAPI
from config import (
    DEFAULT_PAGE_SIZE,
    DEFAULT_DAYS,
    DEFAULT_DELAY_MIN,
    DEFAULT_DELAY_MAX,
)
from keys import load_keys
from storage import save_entries, load_entries

BALANCES_DIR = "balances_history"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)

# --- Retry tuning ---------------------------------------------------------
MAX_RETRIES_PER_PAGE = 6  # give up on a single page only after this many attempts
RETRY_BACKOFF_BASE = 2.0  # seconds, doubles each retry (exponential backoff)
RETRY_BACKOFF_MAX = 60.0  # cap backoff so it never sleeps forever
RETRY_JITTER_MIN = 0.5  # random jitter added to backoff, avoids thundering herd
RETRY_JITTER_MAX = 3.0


def _fetch_page_with_retry(
    api: KrakenAPI,
    ofs: int,
    since_limit: int,
    page_size: int,
    max_retries: int = MAX_RETRIES_PER_PAGE,
) -> Optional[Dict[str, Any]]:
    """
    Fetch a single ledger page, retrying on ANY exception (timeout, rate-limit,
    connection error, transient Kraken 5xx, etc.) with exponential backoff +
    random jitter. Returns the raw response dict, or None if all retries
    exhausted (caller decides whether to stop or skip).
    """
    attempt = 0
    while attempt < max_retries:
        try:
            return api.get_ledgers(ofs=ofs, since=since_limit, page_size=page_size)
        except TypeError:
            # api signature does not accept these kwargs -> fall back once, no retry needed
            try:
                return api.get_ledgers(ofs=ofs)
            except Exception as e:
                logger.warning(
                    "Fallback get_ledgers(ofs=%d) failed (attempt %d/%d): %s",
                    ofs,
                    attempt + 1,
                    max_retries,
                    e,
                )
        except Exception as e:
            logger.warning(
                "get_ledgers(ofs=%d) failed (attempt %d/%d): %s",
                ofs,
                attempt + 1,
                max_retries,
                e,
            )

        attempt += 1
        if attempt >= max_retries:
            break

        backoff = min(RETRY_BACKOFF_BASE * (2 ** (attempt - 1)), RETRY_BACKOFF_MAX)
        jitter = random.uniform(RETRY_JITTER_MIN, RETRY_JITTER_MAX)
        sleep_for = backoff + jitter
        logger.info(
            "Retrying ofs=%d in %.1fs (attempt %d/%d)...",
            ofs,
            sleep_for,
            attempt + 1,
            max_retries,
        )
        time.sleep(sleep_for)

    logger.error(
        "Giving up on ofs=%d after %d attempts — Kraken API unreachable/rate-limited.",
        ofs,
        max_retries,
    )
    return None


def fetch_ledger(
    api: KrakenAPI,
    days: int = DEFAULT_DAYS,
    page_size: int = DEFAULT_PAGE_SIZE,
    delay_min: float = DEFAULT_DELAY_MIN,
    delay_max: float = DEFAULT_DELAY_MAX,
    *,
    since_ts: Optional[int] = None,
    stop_on_txids: Optional[Set[str]] = None,
    max_consecutive_page_failures: int = 3,
) -> Dict[str, Any]:
    """
    Fetch ledger entries from Kraken.

    - If since_ts is provided: use that timestamp (UTC seconds) as `since`.
      Otherwise use `days` to compute `since = now - days * 86400`.

    - If stop_on_txids is provided (set of txid strings), stop fetching
      as soon as any fetched txid matches one from that set (avoids duplicates).
      Already-known txids are NOT included in the returned dict.

    - Transient errors (timeouts, rate limits, connection drops) no longer
      abort the whole fetch. Each page is retried with exponential backoff
      + random jitter (see _fetch_page_with_retry). The fetch only stops
      early if a single page fails MAX_RETRIES_PER_PAGE times in a row, or
      if `max_consecutive_page_failures` pages in a row are fully exhausted
      (protects against an indefinite loop if Kraken is down for a long time).

    Returns dict(txid -> entry).
    """
    entries: Dict[str, Any] = {}
    now_ts = int(datetime.now(timezone.utc).timestamp())
    since_limit = since_ts if since_ts is not None else now_ts - days * 86400

    ofs = 0
    stop_on_txids_local = set(stop_on_txids) if stop_on_txids else set()
    known_hit_count = 0
    found_known = False
    consecutive_page_failures = 0

    while True:
        resp = _fetch_page_with_retry(api, ofs, since_limit, page_size)

        if resp is None:
            consecutive_page_failures += 1
            logger.warning(
                "Page ofs=%d permanently failed (%d/%d consecutive failures).",
                ofs,
                consecutive_page_failures,
                max_consecutive_page_failures,
            )
            if consecutive_page_failures >= max_consecutive_page_failures:
                logger.error(
                    "Too many consecutive page failures (%d) — stopping fetch. "
                    "Entries collected so far (%d) are still returned/saved.",
                    consecutive_page_failures,
                    len(entries),
                )
                break
            # skip this offset attempt cycle but keep going (do not advance ofs blindly —
            # retry same ofs after a cooldown, since Kraken likely still owes us this page)
            time.sleep(random.uniform(delay_min, delay_max) + 5.0)
            continue

        # reset failure streak on any successful page
        consecutive_page_failures = 0

        if not resp:
            logger.info("Empty response at ofs=%d — treating as end of data.", ofs)
            break

        ledgers = resp.get("ledger", resp) if isinstance(resp, dict) else resp
        if not ledgers:
            logger.info("No ledger entries in response at ofs=%d — end of data.", ofs)
            break

        items = list(ledgers.items())
        try:
            items_sorted = sorted(
                items, key=lambda kv: float(kv[1].get("time", 0)), reverse=True
            )
        except Exception:
            items_sorted = items

        page_new = 0
        for txid, entry in items_sorted:
            if txid in stop_on_txids_local:
                known_hit_count += 1
                found_known = True
                continue

            if txid not in entries:
                entries[txid] = entry
                page_new += 1

        logger.info(
            "Fetched %d entries (ofs=%d), total %d",
            len(items_sorted),
            ofs,
            len(entries),
        )

        if found_known and known_hit_count > 0:
            logger.info(
                "Encountered %d already-known txids — stopping fetch early.",
                known_hit_count,
            )
            break

        try:
            min_time = min(float(e["time"]) for _, e in items_sorted)
        except Exception:
            min_time = None

        if min_time is not None and min_time < since_limit:
            logger.info(
                "Reached since_limit (%.0f < %.0f), stopping fetch.",
                min_time,
                since_limit,
            )
            break

        if len(items_sorted) < page_size:
            logger.info("Last page reached (page smaller than page_size).")
            break

        ofs += page_size
        time.sleep(random.uniform(delay_min, delay_max))

    logger.info(
        "Finished. Total entries stored: %d (early-stop: %s, matched: %d)",
        len(entries),
        "YES" if known_hit_count > 0 else "NO",
        known_hit_count,
    )
    return entries


def update_raw_ledger(
    api: Optional[KrakenAPI] = None,
    days: int = DEFAULT_DAYS,
    page_size: int = DEFAULT_PAGE_SIZE,
    delay_min: float = DEFAULT_DELAY_MIN,
    delay_max: float = DEFAULT_DELAY_MAX,
):
    """Download ledger using fetch_ledger and save via storage.save_entries()."""
    if api is None:
        api_key, api_secret = load_keys()
        api = KrakenAPI(api_key, api_secret)

    entries = fetch_ledger(api, days, page_size, delay_min, delay_max)
    save_entries(entries)


def load_raw_ledger() -> Dict[str, Any]:
    """Load stored raw ledger (JSON)."""
    return load_entries()


def main():
    parser = argparse.ArgumentParser(description="Kraken ledger loader")
    parser.add_argument(
        "--days",
        type=int,
        default=DEFAULT_DAYS,
        help="How many days of history to fetch",
    )
    parser.add_argument(
        "--page-size",
        type=int,
        default=DEFAULT_PAGE_SIZE,
        help="Page size for API calls",
    )
    parser.add_argument(
        "--delay-min",
        type=float,
        default=DEFAULT_DELAY_MIN,
        help="Min delay between API calls",
    )
    parser.add_argument(
        "--delay-max",
        type=float,
        default=DEFAULT_DELAY_MAX,
        help="Max delay between API calls",
    )
    args = parser.parse_args()

    api_key, api_secret = load_keys()
    api = KrakenAPI(api_key, api_secret)

    update_raw_ledger(
        api,
        days=args.days,
        page_size=args.page_size,
        delay_min=args.delay_min,
        delay_max=args.delay_max,
    )


if __name__ == "__main__":
    main()
