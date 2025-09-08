![Python](https://img.shields.io/badge/python-3.10+-blue)
![License](https://img.shields.io/badge/license-MIT-green)

# Kraken Portfolio Tracker

A Python tool for tracking and analyzing your Kraken portfolio balances.  
Generates CSV history, portfolio snapshots, and computes trends over time.

## Overview

Kraken Portfolio Tracker is a lightweight Python tool that helps you monitor your cryptocurrency holdings on Kraken. It fetches real-time balances, tracks historical trends, and stores daily snapshots in CSV format for easy analysis.

## Features
- Fetch balances and prices from Kraken API
- Aggregate staked and available balances
- Save daily CSV with portfolio breakdown (can be scheduled via OS)
- Compute portfolio trend based on historical CSVs
- Append portfolio snapshots to `portfolio_snapshots.csv`
- Fully unit-tested with `pytest`
- Supports automatic code formatting (Black) and linting (Ruff)

## Installation

Clone the repository and install dependencies:

```bash
git clone https://github.com/your-username/kraken-portfolio-tracker.git
cd kraken-portfolio-tracker
python -m venv .venv
.venv\Scripts\activate    # Windows
pip install -r requirements.txt
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
- Fetch your current Kraken balances
- Save a snapshot to 
- Update your historical CSV log

or schedule it via Task Scheduler (Windows) or cron (Linux) to log portfolio history daily.

## Running Tests

Run the unit tests:
```
pytest -v
```

## Code Style

This project uses Black and Ruff for consistent code style:
```bash
black .
ruff check .
```

Pre-commit hooks are configured — enable them with:
```
pre-commit install
```

## Requirements

- Python 3.10+
- Internet connection
- Kraken API credentials

See [REQUIREMENTS.md](REQUIREMENTS.md) for full dependency list.

## Building the Executable

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