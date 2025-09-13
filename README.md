![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Coverage](https://codecov.io/gh/patan4ik/kraken-portfolio-tracker/branch/main/graph/badge.svg)

# Kraken Portfolio Tracker

A Python tool for tracking and analyzing your Kraken portfolio and ledger history.
It generates daily snapshots, stores transaction data in JSON and SQLite, and produces different spend reports.

## Overview

Kraken Portfolio Tracker is designed to help you monitor your crypto holdings and transaction history on Kraken with precision and automation.
It supports real-time balance fetching, historical portfolio logging, and modular ledger analysis — including daily spend breakdowns and persistent storage in both CSV and SQLite formats.
Whether you're a casual investor or a data-driven trader, this tool gives you the insights and structure to manage your Kraken activity effectively.

## Features

### Portfolio Tracking
- Fetch balances and prices from Kraken API
- Aggregate staked and available balances
- Save daily CSV snapshots (`portfolio_snapshots.csv`)
- Track historical trends and portfolio evolution over time

### Ledger Reporting
- Incrementally download and cache Kraken ledger entries (`raw-ledger.json`)
- Generate daily spend reports per asset (`ledger_eur_report.csv`)
- Append new purchases to CSV without overwriting existing data
- Store full ledger history in SQLite (balances_history/ledger.db)
- Efficient updates using refid to avoid redundant API call

### CLI & Automation
- Command-line flags for custom behavior: --days, --page-size, --delay-min, --delay-max
- Compatible with cron (Linux) or Task Scheduler (Windows) for daily automation

### Developer Tools
- Modular codebase with unit tests (`pytest`) and mocks
- Clean code enforcement via Black and Ruff
- Pre-commit hooks for automatic formatting and linting

## Installation

```bash
git clone https://github.com/your-username/kraken-portfolio-tracker.git
cd kraken-portfolio-tracker
python -m venv .venv
Set-ExecutionPolicy -Scope Process -ExecutionPolicy Bypass # bypass Windows policies for VM current session
.venv\Scripts\activate  # Windows
pip install -r requirements.txt
deactivate    # deactivate VM in Windows
```

## API Key Setup

This project uses Kraken API keys stored in `kraken.key`.  
**Important:** Replace the placeholder values with your own credentials before running the app.

To use the Kraken API, create a file named `kraken.key` in the project root.  
You can start by copying the example file:

```bash
cp kraken.key.example kraken.key
```

Then replace the placeholder values with your actual API credentials:
```
API_KEY=your_key_here
API_SECRET=your_secret_here
```
Important: Never commit your real API keys to GitHub. This file is excluded via .gitignore.

## Git Hygiene

This project includes a `.gitignore` file to exclude:
- API keys (`kraken.key`)
- Build artifacts (`__pycache__`, `.pytest_cache`, `build/`)
- PyInstaller spec files (`*.spec`)

## Getting Started

Once installed and configured, run the tracker:

```
python balances.py
```
This will:
- Fetch current balances
- Save a snapshot
- Update your historical CSV log
- Load or update raw-ledger.json
- Generate ledger_eur_report.csv with daily EUR spend per asset

or schedule it via Task Scheduler (Windows) or cron (Linux) to log portfolio history daily.

## Storage
Starting from version 0.9.2, ledger data is stored in two formats:
- JSON file:
- SQLite database:
The  table in the SQLite database contains all transaction fields, including a full copy of each entry in the  column.

## Working with the Database
To interact with the SQLite database, use the following commands:
```bash
sqlite3 balances_history/ledger.db
sqlite> .tables
sqlite> SELECT COUNT(*) FROM ledger;
```

## Running Tests
Run the unit tests:
```
pytest -v
```

## Code Style

This project uses Black and Ruff for consistent code style:
```bash
black . # automatically format your files before they are committed
ruff check . # catch code smells and unused imports before they hit production
```

Pre-commit hooks are configured — enable them with:
```bash
pre-commit install # Since you’ve already configured pre-commit hooks in .pre-commit-config.yaml, you can enable them locally. Now every time you run git commit, Black and Ruff will automatically check your files before they are committed — so your CI will stay green without extra work.
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

Pull requests are welcome! See CONTRIBUTING.md for details.

## License

This project is licensed under the MIT License.
