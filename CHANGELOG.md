# Changelog

## [0.9.3] - 2025-09-13
### Added
- Introduced **`start.py`** as a central launcher for portfolio tracking and report generation
- Added two new reports:
  - **Asset report** – summarizes all acquired assets
  - **Sell report** – summarizes sell operations, proceeds in EUR, and Kraken fees
- All reports are now generated **from SQLite (`ledger.db`)**, not from raw JSON
- CLI support for reports (`--days`, `--csv`)

### Changed
- Project files moved into `/src` for cleaner structure
- Reports are stored in `data/` folder along with `ledger.db` and snapshots
- Improved offline workflow: if `ledger.db` or `raw-ledger.json` exist → use them, no API calls

### Fixed
- Handling of empty `raw-ledger.json` (skips DB creation gracefully)
- Tests updated for new project structure and report logic

---

## [0.9.2] - 2025-09-10
### Added
- SQLite database support for storing ledger history
- Migration from `raw-ledger.json` into `ledger.db`
- `save_entries()` function now writes to both JSON and SQLite
- CLI continues to support flags: `--days`, `--page-size`, `--delay-min`, `--delay-max`

---

## [0.9.1] - Update 2025-09-11

### Added
- `ledger_loader.py`: Incremental Kraken ledger downloader with caching to `raw-ledger.json`
- `ledger_eur_report.py`: Generates EUR spend report per asset per day
- Unit tests: `test_ledger_loader.py`, `test_ledger_eur_report.py`

### Changed
- Project structure updated to support modular ledger reporting
- CSV output now appends new purchases without overwriting existing data

### Notes
- Future support planned for `ledger_asset_report.py`, `ledger_sell_report.py` and others
- Improved resilience and efficiency for large ledger histories

---

## [0.9.0] - 2025-09-05
- Initial public release
