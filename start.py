# start.py
import logging
import os
import sys
import argparse
import sqlite3

# add src to PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import storage
import ledger_loader
import ledger_eur_report
import ledger_asset_report
import ledger_sell_report
import balances
from keys import save_keys, load_keys, KeysError

logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


def main(argv=None):
    logger.info("🚀 Kraken Portfolio Tracker initialization started")
    parser = argparse.ArgumentParser(description="Kraken Portfolio Tracker")
    parser.add_argument(
        "--setup-keys", action="store_true", help="Interactively setup API keys"
    )
    # ignore pytest/CI extra arguments
    args = parser.parse_known_args(argv)[0]

    if args.setup_keys:
        try:
            api_key = input("Enter your Kraken API Key: ").strip()
            api_secret = input("Enter your Kraken API Secret: ").strip()
            if not api_key or not api_secret:
                print("❌ Both API key and secret are required.")
                return
            save_keys(api_key, api_secret)
            print("✅ API keys saved successfully.")
        except Exception as e:
            print(f"❌ Failed to save keys: {e}")
            sys.exit(1)
        return

    # load keys (returns tuple (api_key, api_secret) or raises KeysError)
    try:
        api_key, api_secret = load_keys()
        logger.info("✅ API keys loaded successfully")
    except KeysError:
        logger.error(
            "ERROR: API-ключи Kraken не найдены. Создайте файл ключей или используйте --setup-keys."
        )
        sys.exit(1)
    except Exception as e:
        logger.error(f"Unexpected error loading keys: {e}")
        sys.exit(1)

    # --- 3. Portfolio ---
    try:
        # Return the result of balances.main so callers/tests get it
        result = balances.main()
    except Exception as e:
        logger.error("Ошибка при загрузке портфеля: %s", e)
        return

    # --- 4. DB / raw ledger ---
    try:
        if os.path.exists(storage.DB_FILE):
            logger.info("✅ ledger.db already exists")
        elif os.path.exists(storage.RAW_LEDGER_FILE):
            logger.info("💡 Found raw-ledger.json, creating SQLite DB from it...")
            raw_entries = storage.load_entries()
            if raw_entries:
                storage.save_entries(raw_entries)
                logger.info("✅ SQLite DB created from raw-ledger.json")
            else:
                logger.warning(
                    "⚠️ raw-ledger.json is empty or invalid, downloading from Kraken..."
                )
                ledger_loader.update_raw_ledger(days=30)
                storage.init_db()
        else:
            logger.info(
                "💡 No valid raw-ledger.json or ledger.db found. Downloading raw ledger from Kraken..."
            )
            ledger_loader.update_raw_ledger(days=30)
            storage.init_db()
    except Exception as e:
        logger.exception("Error while preparing DB/raw ledger: %s", e)

    # --- 5. Reports ---
    logger.info("Generating reports...")
    entries = storage.load_entries_from_db()
    eur_df = ledger_eur_report.build_eur_report(entries, days=10)
    asset_df = ledger_asset_report.build_asset_report(entries, days=10)
    sell_df = ledger_sell_report.build_sell_report(entries, days=10)

    if eur_df is not None and not eur_df.empty:
        ledger_eur_report.save_eur_report(eur_df)
    if asset_df is not None and not asset_df.empty:
        ledger_asset_report.save_asset_report(asset_df)
    if sell_df is not None and not sell_df.empty:
        ledger_sell_report.save_sell_report(sell_df)

    logger.info("Reports generated:")
    if eur_df is not None:
        logger.info(f" - EUR report: {len(eur_df)} rows")
    if asset_df is not None:
        logger.info(f" - Asset report: {len(asset_df)} rows")
    if sell_df is not None:
        logger.info(f" - Sell report: {len(sell_df)} rows")

    logger.info("✅ Initialization completed successfully.")

    # propagate balances.main() return value to caller/tests
    return result


def _db_row_count(db_path: str) -> int:
    try:
        if not os.path.exists(db_path):
            return 0
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ledger'"
        )
        if not cur.fetchone():
            conn.close()
            return 0
        cur.execute("SELECT count(*) FROM ledger")
        cnt = cur.fetchone()[0]
        conn.close()
        return int(cnt)
    except Exception as e:
        logger.warning("Could not count rows in DB %s: %s", db_path, e)
        return 0


if __name__ == "__main__":
    main()
