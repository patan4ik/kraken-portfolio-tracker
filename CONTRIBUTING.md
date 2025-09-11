# Contributing to Kraken Portfolio Tracker

Thanks for your interest in contributing! This project welcomes improvements, bug fixes, and new features. Here's how to get started.

---

## Development Setup

1. Clone the repository and create a virtual environment:

```bash
git clone https://github.com/patan4ik/kraken-portfolio-tracker.git
cd kraken-portfolio-tracker
python -m venv venv # Create and activate virtual environment
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Run tests to verify your environment:
```
pytest -v
```

3. Use Code Style & Tooling
This project uses:
- Black for code formatting
- Ruff for linting and static analysis
- Pre-commit hooks to enforce style before commits

Before committing, run:
```bash
black .
ruff check . --fix
```

To enable pre-commit hooks:
```
pre-commit install
```

## How to Contribute
- Fork the repository
- Create a branch for your feature or fix:
```
git checkout -b feature/my-new-feature
```
- Make your changes
- Write or update tests if needed
- Run tests to ensure everything passes
- Commit with a clear message:
```
git commit -m "feat: add support for XYZ"
```
- Push and open a Pull Request

## Testing Guidelines
- All new features should include unit tests in the tests/ directory
- Use pytest for testing and monkeypatch for mocking where needed
- Run pytest -v before submitting a PR

##  Project Structure
- balances.py: Portfolio snapshot logic
- ledger_loader.py: Incremental ledger downloader
- ledger_eur_report.py: EUR spend report generator
- tests/: Unit tests for all modules
See README.md for full usage instructions.

## Changelog & Versioning
If your contribution adds a feature or fixes a bug, please update CHANGELOG.md under the appropriate version heading.

##  License
By contributing, you agree that your code will be licensed under the MIT License.

Thanks again for helping improve Kraken Portfolio Tracker!
