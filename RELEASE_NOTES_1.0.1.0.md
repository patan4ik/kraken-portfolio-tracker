## v1.0.1.0 — CI Hardening, Bandit/mypy Validation, Bug Fixes

### Added
- `.github/workflows/lint.yml` — mypy and Bandit checks now hard-fail CI (`continue-on-error: false`); pyupgrade remains informational.
- `.github/dependabot.yml` — automated weekly dependency update PRs for pip and github-actions ecosystems.
- `.pre-commit-config.yaml` — local pre-commit hooks: Black, Ruff (`--fix`), Bandit, pyupgrade (`--py313-plus`), mypy.
- `requirements-dev.txt` — dev-only tooling dependencies separated from runtime `requirements.txt`.
- `pyproject.toml` — centralized mypy/bandit/pytest configuration.

### Fixed
- `balances.py`: fixed `tabulate()` `ValueError` when rendering the on-screen summary table (`headers="keys"` required for list-of-dicts input).
- `balances.py`: fixed `load_keys()` result handling to accept both tuple/list and dict return shapes with runtime validation.
- `balances.py`: fixed `UnboundLocalError` in the portfolio snapshot CSV save logic.
- Applied `pyupgrade --py313-plus` modernization across `balances.py`, `ledger_eur_report.py`.

### Changed
- Untracked `.coverage` and `coverage.xml` (now properly gitignored as build artifacts).
- Full test suite green: 187 tests, coverage 83.76% (gate: 80%).
- Bandit and mypy pass clean across `src/`, `start.py`, `update.py`.

**Full Changelog**: https://github.com/patan4ik/kraken-portfolio-tracker/compare/v1.0.0.2...v1.0.1.0
