# ledger_loader.py
import time
import random
import logging
import argparse
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from api import KrakenAPI
from config import (
    load_keyfile,
    DEFAULT_PAGE_SIZE,
    DEFAULT_DAYS,
    DEFAULT_DELAY_MIN,
    DEFAULT_DELAY_MAX,
)
from storage import save_entries, load_entries

BALANCES_DIR = "balances_history"

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def fetch_ledger(
    api: KrakenAPI,
    days: int = DEFAULT_DAYS,
    page_size: int = DEFAULT_PAGE_SIZE,
    delay_min: float = DEFAULT_DELAY_MIN,
    delay_max: float = DEFAULT_DELAY_MAX,
) -> Dict[str, Any]:
    """Скачать все записи леджера за последние N дней."""
    entries: Dict[str, Any] = {}
    now_ts = int(datetime.now(timezone.utc).timestamp())
    since_limit = now_ts - days * 86400

    ofs = 0
    while True:
        resp = api.get_ledgers(ofs=ofs)
        if not resp:
            break

        ledgers = resp.get("ledger", resp)
        if not ledgers:
            break

        entries.update(ledgers)
        min_time = min(float(e["time"]) for e in ledgers.values())
        logger.info(f"Fetched {len(ledgers)} entries (ofs={ofs}), total {len(entries)}")

        if min_time < since_limit:
            logger.info("Reached since_limit, stopping fetch.")
            break

        if len(ledgers) < page_size:
            break

        ofs += page_size
        time.sleep(random.uniform(delay_min, delay_max))

    logger.info(f"Finished. Total entries stored: {len(entries)}")
    return entries


def update_raw_ledger(
    api: Optional[KrakenAPI] = None,
    days: int = DEFAULT_DAYS,
    page_size: int = DEFAULT_PAGE_SIZE,
    delay_min: float = DEFAULT_DELAY_MIN,
    delay_max: float = DEFAULT_DELAY_MAX,
):
    """Обновить данные леджера и сохранить в JSON + SQLite."""
    if api is None:
        api_key, api_secret = load_keyfile()
        api = KrakenAPI(api_key, api_secret)

    entries = fetch_ledger(api, days, page_size, delay_min, delay_max)
    save_entries(entries)


def load_raw_ledger() -> Dict[str, Any]:
    """Загрузить записи леджера (JSON как основной источник)."""
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

    api_key, api_secret = load_keyfile()
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
