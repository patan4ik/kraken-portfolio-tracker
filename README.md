![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Coverage](https://codecov.io/gh/patan4ik/kraken-portfolio-tracker/branch/main/graph/badge.svg)

# Kraken Portfolio Tracker

A Python tool for **offline tracking and analyzing your crypto portfolio and ledger history** on the Kraken crypto exchange.  
The main purpose of the tool is to get a full overview of all activities on Kraken **without keeping an active API session**.  
All data is cached locally (JSON + SQLite), and reports are generated from the local database for flexible offline analysis.

It generates daily snapshots, stores transaction data in SQLite, and produces multiple reports:  
- EUR spend report  
- Asset acquisition report  
- Sell operations report  

---

## Overview

Kraken Portfolio Tracker helps you monitor your crypto holdings and transaction history with precision and automation.  
It supports real-time balance fetching, historical portfolio logging, and modular ledger analysis — including daily spend breakdowns and persistent storage in both CSV and SQLite formats.

Whether you're a casual investor or a data-driven trader, this tool gives you insights and structure to manage your Kraken activity effectively.

---

## Features

### Portfolio Tracking
- Fetch balances and prices from Kraken API
- Aggregate staked and available balances
- Save daily CSV snapshots (`portfolio_snapshots.csv`)
- Track historical trends and portfolio evolution over time

### Ledger Reporting
- Incrementally download and cache Kraken ledger entries (`raw-ledger.json`)
- Store full ledger history in SQLite (`balances_history/ledger.db`)
- **Generate reports from SQLite** (faster, flexible, no API calls):
  - **EUR report** (`ledger_eur_report.csv`) – daily EUR spent per asset
  - **Asset report** (`ledger_asset_report.csv`) – all asset acquisitions
  - **Sell report** (`ledger_sell_report.csv`) – sell operations with proceeds and fees
- CLI options for each report:  
  `python ledger_asset_report.py --days=10 --csv`

### CLI & Automation
- Central launcher: `python start.py`
- Command-line flags for custom behavior (`--days`, `--page-size`, etc.)
- Compatible with cron (Linux) or Task Scheduler (Windows)

### Developer Tools
- Modular codebase inside `/src`
- Unit tests (`pytest`) and mocks for offline validation
- Clean code enforcement via Black and Ruff
- Pre-commit hooks for automatic formatting and linting

---

## Installation

```bash
git clone https://github.com/your-username/kraken-portfolio-tracker.git
cd kraken-portfolio-tracker
python -m venv .venv
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
```

## API Key Setup

The project uses Kraken API keys that you need copy-paste from kraken.com.



```
python start.py --setup-keys
```

This securely saves your Kraken API key/secret in the system keyring.
Alternatively, you can still:
**Important:** ⚠️ Create a file named kraken.key in the project root folder.
Create a kraken.key file with two lines (API_KEY and SECRET), or
```
cp kraken.key.example kraken.key
```
Then replace the placeholder values with your actual API credentials:
```
API_KEY=your_key_here
API_SECRET=your_secret_here
```
Set environment variables:
Then replace the placeholder values with your actual API credentials:
```bash
export KRAKEN_API_KEY=yourkey
export KRAKEN_API_SECRET=yoursecret
```

**Important:** ⚠️ Never commit your real API keys to GitHub. This file is excluded via .gitignore.

## Git Hygiene

This project includes a `.gitignore` file to exclude:
- API keys (`kraken.key`)
- Build artifacts (`__pycache__`, `.pytest_cache`, `build/`)
- PyInstaller spec files (`*.spec`)

## Getting Started

Once installed and configured api key, run the tracker:

```
python start.py
```
This will:
- Fetch current balances and prices
- Save a balance snapshot
- Update your historical CSV log
- Initialize or reuse ledger.db

Generate all reports from SQLite:
- EUR spend report
- Asset acquisition report
- Sell operations report

## Usage

Fetch and update DB:
```
python start.py --update-ledger
```

Generate reports:
```bash
python src/ledger_eur_report.py --days 30 --csv
python src/ledger_asset_report.py --days 30 --csv
python src/ledger_sell_report.py --days 30 --csv
```

## Storage
Starting from v0.9.2:
Ledger data is stored in SQLite database (ledger.db) instead of only JSON
The ledger table keeps all fields including a full JSON payload

Starting from v0.9.3:
All reports (EUR, Asset, Sell) are generated from SQLite instead of raw JSON
The table in the SQLite database contains all transaction fields, including a full copy of each entry in the  column.

## Working with the Database
To interact with the SQLite database, use the following commands:
```bash
sqlite3 balances_history/ledger.db
sqlite> .tables
sqlite> SELECT COUNT(*) FROM ledger;
```

## Running Tests
Run the unit tests:
```bash
pytest -v
pytest --cov=. --cov-report=xm # tests with coverage
```

## Code Style

This project uses Black and Ruff for consistent code style:
```bash
black . # automatically format your files before they are committed
ruff check . # catch code smells and unused imports before they hit production
```

Pre-commit hooks are configured — enable them with:
```bash
# Since you’ve already configured pre-commit hooks in .pre-commit-config.yaml, you can enable them locally.
# Now every time you run git commit, Black and Ruff will automatically check your files before they are committed — so your CI will stay green without extra work.
pre-commit install
```

## Requirements

- Python 3.11+
- Internet connection
- Kraken API credentials

See [requirements.txt](requirements.txt) for full dependency list.

## Building Executable (Windows)

To build a Windows `.exe` file from the source code:

```bash
pip install pyinstaller
pyinstaller --onefile balances.py
```
The output will be in the dist/ folder.

## Contributing

✍️ Pull requests are welcome! See CONTRIBUTING.md for details.

## License

✍️ This project is licensed under the MIT License.
