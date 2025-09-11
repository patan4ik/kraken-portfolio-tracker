# ledger_loader.py (упрощённый режим)
import os
import json
import time
import random
import logging
from datetime import datetime, timezone
from typing import Dict, Any, Optional

from api import KrakenAPI
from config import load_keyfile

BALANCES_DIR = "balances_history"
RAW_LEDGER_FILE = os.path.join(BALANCES_DIR, "raw-ledger.json")
PROGRESS_FILE = os.path.join(BALANCES_DIR, "ledger-progress.json")

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
logger = logging.getLogger(__name__)


def load_progress() -> Dict[str, Any]:
    if os.path.exists(PROGRESS_FILE):
        with open(PROGRESS_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    return {"entries": {}}


def save_progress(entries: Dict[str, Any]):
    os.makedirs(BALANCES_DIR, exist_ok=True)

    # сохраняем как progress (метаданные + ledger)
    progress = {"entries": entries}
    with open(PROGRESS_FILE, "w", encoding="utf-8") as f:
        json.dump(progress, f, indent=2, ensure_ascii=False)

    # также сохраняем в raw-ledger.json для совместимости
    cleaned = {}
    for txid, entry in entries.items():
        e = dict(entry)
        try:
            e["time"] = float(e.get("time", 0))
        except Exception:
            pass
        cleaned[txid] = e

    with open(RAW_LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(cleaned, f, indent=2, ensure_ascii=False)


def fetch_ledger(api: KrakenAPI, days: int = 7) -> Dict[str, Any]:
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

        # Добавляем новые записи
        entries.update(ledgers)

        # Минимальное время в этой пачке
        min_time = min(float(e["time"]) for e in ledgers.values())
        logger.info(f"Fetched {len(ledgers)} entries (ofs={ofs}), total {len(entries)}")

        # Если дошли до лимита по времени → стоп
        if min_time < since_limit:
            logger.info("Reached since_limit, stopping fetch.")
            break

        if len(ledgers) < 50:
            break

        ofs += 50
        time.sleep(random.uniform(1.0, 2.5))

    logger.info(f"Finished. Total entries stored: {len(entries)}")
    return entries


def update_raw_ledger(api: Optional[KrakenAPI] = None, days: int = 7):
    """Обновить raw-ledger.json (совместимость)."""
    if api is None:
        api_key, api_secret = load_keyfile()
        api = KrakenAPI(api_key, api_secret)

    entries = fetch_ledger(api, days=days)
    save_progress(entries)


def load_raw_ledger() -> Dict[str, Any]:
    """Загрузить текущий raw-ledger.json (dict txid -> entry)."""
    progress = load_progress()
    return progress.get("entries", {})


def main():
    api_key, api_secret = load_keyfile()
    api = KrakenAPI(api_key, api_secret)
    update_raw_ledger(api, days=7)


if __name__ == "__main__":
    main()
