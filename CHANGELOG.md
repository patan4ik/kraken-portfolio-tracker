# Changelog

## [1.0.1.0] - 2026-07-16
### Added
- New GitHub Actions workflow `.github/workflows/lint.yml` — runs mypy, Bandit, and pyupgrade compliance checks on every push/PR to `main` (non-blocking via `continue-on-error`, informational for now).
- `.pre-commit-config.yaml` — local pre-commit hooks for Black, Ruff (`--fix`), Bandit (`-c pyproject.toml`), pyupgrade (`--py313-plus`), and mypy (`--config-file=pyproject.toml`), scoped to `src/`, `start.py`, `update.py`.
- `requirements-dev.txt` — separated dev-only tooling dependencies (bandit, mypy, pre-commit, ruff, black, pyupgrade, pandas-stubs, types-requests, types-tabulate) from runtime `requirements.txt`.

### Fixed
- `balances.py`: extensive code review fixes — corrected `load_keys()` result handling to accept both tuple/list and dict shapes with runtime validation instead of assuming a fixed type.
- `balances.py`: fixed `tabulate()` invocation for the on-screen summary table — passing `headers=list(df.columns)` against a `list[dict]` payload raised `ValueError`; now uses `headers="keys"` as required by tabulate for list-of-dicts input.
- `balances.py`: fixed `UnboundLocalError` in the portfolio snapshot CSV save logic — the `snapshots` DataFrame is now always assigned before use in both the "file exists" and "file does not exist" branches, and written exactly once via `_atomic_to_csv`.

### Changed
- Ran full Bandit and mypy validation across `src/`, `start.py`, `update.py` — both pass clean (`bandit... Passed`, `mypy... Passed`).
- Test suite (187 tests) fully green with `pytest --cov=src --cov-fail-under=80`; total coverage raised to 83.76% (previously below the 80% gate).
- Updated `requirements.txt` with pinned versions for `bandit==1.9.4`, `mypy==2.3.0`, `ruff==0.12.12`, `black==25.1.0`, and related type-stub packages.
- `lint.yml`: `mypy` and `Bandit` steps changed from `continue-on-error: true` to `continue-on-error: false` — CI now hard-fails on type-check or security-scan violations. `pyupgrade` remains informational (`continue-on-error: true`).

## [1.0.0.1] - 2026-07-14
### Changed
- Extended the GitHub Actions Python test matrix to include 3.13.0 alongside 3.11 and 3.12.
- Expanded coverage measurement to include root-level `update.py` and `start.py`, previously only `src/` was measured.
- Synchronized `.pre-commit-config.yaml` Black (25.1.0) and Ruff (0.12.12) pins with `requirements.txt`, so local pre-commit hooks match CI exactly.
- Added `.python-version` (3.13.0) to keep local development environments aligned with the CI matrix's newest version.

### Notes
- `--cov-fail-under` remains at 70 for this release; raising it to 80 is planned as a follow-up once coverage on `update.py`/`start.py` is confirmed via CI.
- Codecov project-level target (85%, threshold 5%) in `codecov.yml` is unchanged and intentionally stricter than the CI hard gate.

## [1.0.0.0] - 2026-07-12
### Added
- **`update.py`**: new incremental ledger updater — detects missing date ranges against the existing `ledger.db` (before earliest and after latest stored date), fetches only the gaps via `ledger_loader.fetch_ledger()`, and skips already-known txids. Supports `--fromdate`, `--todate` (relative `Nd`/`Nm` or absolute `YYYY-MM-DD`/`DD.MM.YYYY`), `--dry-run`, `--page-size`, `--delay-min`, `--delay-max`, and `--no-summary`.
- **`portfolio_summary.py`**: new FIFO cost-basis engine ported from the Google Sheets Apps Script pipeline. Computes running average cost per asset (`run_fifo`), strips Kraken wallet-suffixes (`.F`/`.B`/`.S`/`.M`/`.P`) so balances roll up per ticker, excludes `transfer` entries (spot↔staking moves) from FIFO, and adds an EMA7 + linear-regression price forecast (`forecast_prices`) with 7-day and 30-day projections. Persists results to a disposable `summary` SQLite table (`save_summary`, `update_summary`).
- **`portfolio_summary_report.py`**: new CSV/CLI report layer built on top of `portfolio_summary.py`. Adds Google-Sheets-style derived analytics per asset: Sell +25/35/50/75% targets, Trend, Upside %, Volatility Score, Recovery Strength, Confidence (HIGH/MEDIUM/LOW), Regime (BULLISH/BULLISH RECOVERY/WEAK-SIDEWAYS/BEARISH), Signal (ACCUMULATE/BUY LIGHT/REDUCE/HIGH RISK/HOLD), and a composite Asset Color Score. Supports `--csv` and `--no-recompute` (read last persisted summary instead of recomputing FIFO).
- **`balance_reconciliation.py`**: new cross-check module that compares FIFO-computed remaining amount/price against the latest live Kraken balance snapshot CSV, flags mismatches beyond tolerance, and writes `reconciliation_report.csv`. Runs automatically as a non-fatal validation step after every `update.py` run.
- **`validators.py`**: new pre-flight validation module — `check_db_exists`, `check_db_schema`, `check_api_key(s)`, combined `validate_for_update()` (used by `update.py` before any API call), plus post-update row-count checks (`db_row_count`, `validate_after_update`).
- Full pytest suite (171 tests) covering `update.py`, `portfolio_summary.py`, `portfolio_summary_report.py`, `balance_reconciliation.py`, and `validators.py`, with coverage reporting via `pytest --cov`.

### Fixed
- `validators.check_db_schema()` now catches the full `sqlite3.DatabaseError` hierarchy instead of only `OperationalError`, so corrupted/non-SQLite files are correctly reported as `SchemaInvalidError` instead of leaking a raw `sqlite3.DatabaseError`.
- `portfolio_summary.py`: renamed ambiguous loop variable `l` to `leg_item` in FIFO leg-aggregation sums (ruff E741).
- Resolved test-suite import/collection failures caused by module-level `sys.modules` stubbing leaking across test files; all fixtures now scope monkeypatched attributes to individual test functions.


## [0.9.4.2] - 2025-10-03
### Fixed
- Prevent from accidentally commit of `ledger.db` or `.master` file by adding `*.db`, `*.master` to `.gitignore`.
- Fixed `days` argument propagation across `start.py`, `ledger_asset_report.py`, `ledger_eur_report.py`, `ledger_loader.py`, and `ledger_sell_report.py`.
- Improved `keys.py` to support dual storage (system keyring + `.master` backup).
- Added snapshot test to verify `kraken.key` encryption (ensures no plain-text keys are stored).
- All unit tests are now green.


## [0.9.4.1] - 2025-09-30
### Changed
- `start.main()` now returns the result of `balances.main()`, enabling consistent testing and programmatic usage.

### Fixed
- Improved error handling and cleaned unit tests failures.


## [0.9.4] - 2025-09-15

### Added
- `keys.py`: new secure method to store Kraken API credentials (via system keyring).
- CLI helper: `python start.py --setup-keys` for easy key setup.

### Changed
- Reports now use **dates from DB** (ISO format) instead of recalculating from timestamps.
- Reports consistently return `pd.DataFrame` (empty instead of `None`).
- Fallback logic for API keys:
  1. Secure storage
  2. File (`kraken.key`)
  3. Environment variables
  4. Clear error message

### Fixed
- Date sorting and formatting issues in EUR/Asset/Sell reports.
- Lint error: replaced ambiguous variable `l` with `line` in `keys.py`.
- All related unit tests


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

## [0.9.0] - 2025-09-01
- Initial public release
