# start.py
import logging
import os
import sys
import argparse

# добавляем src в PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import storage
import ledger_loader
import ledger_eur_report
import ledger_asset_report
import ledger_sell_report
import balances
import keys  # <--- NEW


logger = logging.getLogger(__name__)
logging.basicConfig(
    level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
)


def setup_keys():
    """Interactive setup for Kraken API keys."""
    logger.info("🔑 Starting Kraken API key setup...")
    keys.save_keyfile()
    logger.info("✅ Kraken API keys saved. You can now run the app normally.")


def main():
    parser = argparse.ArgumentParser(description="Kraken Portfolio Tracker")
    parser.add_argument(
        "--setup-keys",
        action="store_true",
        help="Interactive setup to save Kraken API keys locally",
    )

    # Allow pytest/other tools to pass extra args without breaking
    args, _ = parser.parse_known_args()

    if args.setup_keys:
        setup_keys()
        return

    logger.info("🚀 Kraken Portfolio Tracker initialization started")

    # 1. Отображаем текущий портфель (если ключи Kraken работают — пользователь это сразу увидит)
    try:
        balances.main()
    except Exception as e:
        logger.exception("Ошибка при загрузке портфеля: %s", e)

    # 2. Проверяем базу
    if os.path.exists(storage.DB_FILE):
        logger.info("✅ ledger.db already exists")
    elif os.path.exists(storage.RAW_LEDGER_FILE):
        logger.info("💡Found raw-ledger.json, creating SQLite DB from it...")
        raw_entries = storage.load_entries()
        if raw_entries:
            storage.save_entries(raw_entries)
            logger.info("✅ SQLite DB created from raw-ledger.json")
        else:
            logger.warning("⚠️ raw-ledger.json is empty, skipping DB creation ")
            logger.info(
                "💡 No valid raw-ledger.json or ledger.db found. Downloading raw ledger from Kraken..."
            )
            ledger_loader.update_raw_ledger(days=30)
            logger.info("Ledger downloaded. Creating SQLite DB...")
            storage.init_db()
    else:
        logger.info(
            "💡 No valid raw-ledger.json or ledger.db found. Downloading raw ledger from Kraken..."
        )
        ledger_loader.update_raw_ledger(days=30)
        logger.info("Ledger downloaded. Creating SQLite DB...")
        storage.init_db()

    # 3. Создаём все отчёты
    logger.info("Generating reports...")
    entries = storage.load_entries_from_db()
    eur_df = ledger_eur_report.build_eur_report(entries, days=10)
    asset_df = ledger_asset_report.build_asset_report(entries, days=10)
    sell_df = ledger_sell_report.build_sell_report(entries, days=10)

    # сохраняем CSV
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


if __name__ == "__main__":
    main()
