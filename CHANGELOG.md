# Changelog

## [0.9.0] - Initial Release
- Added main `balances.py` script
- Added `api.py` wrapper for Kraken REST API
- Added CSV history & snapshot saving
- Added basic test suite with mocks

## [0.9.1] - Update 2025-09-11

### Added
- `ledger_loader.py`: Incremental Kraken ledger downloader with caching to `raw-ledger.json`
- `ledger_eur_report.py`: Generates EUR spend report per asset per day
- Unit tests: `test_ledger_loader.py`, `test_ledger_eur_report.py`

### Changed
- Project structure updated to support modular ledger reporting
- CSV output now appends new purchases without overwriting existing data

### Notes
- Future support planned for `ledger_units_report.py`
- Improved resilience and efficiency for large ledger histories

## [0.9.2] - Update 2025-09-12

### Added
- Ledger data storage support in SQLite (`balances_history/ledger.db`)
- `save_entries()` function now writes to both JSON and SQLite
- CLI continues to support flags: `--days`, `--page-size`, `--delay-min`, `--delay-max`
