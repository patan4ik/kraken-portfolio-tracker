![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Coverage](https://codecov.io/gh/patan4ik/kraken-portfolio-tracker/branch/main/graph/badge.svg)

# Kraken Portfolio Tracker

A Python tool for tracking and analyzing your Kraken portfolio and ledger history.  
Generates CSV snapshots, computes trends, and builds daily reports of EUR spend per asset.

## Overview

Kraken Portfolio Tracker helps you monitor your cryptocurrency holdings and transaction history on Kraken.  
It supports real-time balance tracking, historical portfolio snapshots, and incremental ledger reporting.

## Features

### 📊 Portfolio Tracking
- Fetch balances and prices from Kraken API
- Aggregate staked and available balances
- Save daily CSV snapshots (`portfolio_snapshots.csv`)
- Compute portfolio trends from historical data

### 📁 Ledger Reporting
- Incrementally download and cache Kraken ledger (`raw-ledger.json`)
- Build daily EUR spend reports per asset (`ledger_eur_report.csv`)
- Efficient refid-based updates to avoid redundant API calls

### 🧪 Developer Tools
- Fully unit-tested with `pytest`
- Code formatting with Black and linting with Ruff
- Pre-commit hooks for clean commits

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
