# PROJECT CONTEXT

Корень проекта: `C:\Users\patan\Scripts\Kraken`

Файлов включено: 3


## PROJECT TREE

```
Kraken/
├── tools/
│   ├── project_context.py
│   └── project_context_docs.md
└── README.md
```


## FILE CONTENTS


### `README.md`

```markdown
![Python](https://img.shields.io/badge/python-3.11+-blue)
![License](https://img.shields.io/badge/license-MIT-green)
![Coverage](https://codecov.io/gh/patan4ik/kraken-portfolio-tracker/branch/main/graph/badge.svg)
![Version](https://img.shields.io/badge/version-1.0.4.0-brightgreen)

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

### Portfolio Summary & Reconciliation (v1.0.0.0)
- **FIFO cost-basis engine** (`portfolio_summary.py`) — recomputes running average buy price per asset from the full ledger history on every run (no incremental state), correctly handling Kraken wallet-suffix splits (`.F`/`.B`/`.S`) and excluding internal transfers
- **Price forecasting** — EMA7 + linear regression trend, producing 7-day and 30-day price forecasts per asset
- **Enriched summary report** (`portfolio_summary_report.py`) — Sell targets (+25/35/50/75%), Trend, Upside %, Volatility Score, Recovery Strength, Confidence, Regime, and Signal (BUY/HOLD/REDUCE/HIGH RISK), exported to `portfolio_summary_report.csv`
- **Balance reconciliation** (`balance_reconciliation.py`) — cross-checks FIFO output against your live Kraken balance snapshot and flags any mismatch beyond tolerance in `reconciliation_report.csv`
- **Incremental updater** (`update.py`) — detects and fetches only missing ledger date ranges, validates DB/schema/API keys upfront (`validators.py`), then automatically refreshes balances, FIFO summary, and reconciliation in one run:
  ```bash
  python update.py --fromdate 30d --csv
  python update.py --fromdate 2026-01-01 --todate 2026-06-30 --dry-run
  ```

### CLI & Automation
- Central launcher: `python start.py` for project initiation
- Central launcher: `python update.py` for data updates
- Command-line flags for custom behavior (`--days`, `--fromdate`, etc.)
- Compatible with cron (Linux) or Task Scheduler (Windows)

## Code Quality & CI

This project enforces code quality via:
- **Black** — code formatting
- **Ruff** — linting (`ruff check src/ --fix`)
- **mypy** — static type checking (`--config-file=pyproject.toml`)
- **Bandit** — security static analysis (`-c pyproject.toml`)
- **pyupgrade** — Python 3.13+ syntax modernization

Run all checks locally before committing:

```bash
pip install -r requirements-dev.txt
pre-commit install
pre-commit run --all-files
pytest --cov=src --cov-fail-under=80
```

GitHub Actions (`.github/workflows/lint.yml`) runs mypy, Bandit, and pyupgrade checks on every push/PR to `main`.

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

(RECOMENDED) This securely saves your Kraken API key/secret in the system keyring.

Alternatively, you can still: **Important:** ⚠️ Create a file named kraken.key in the project root folder.
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
Run the unit tests locally (Python 3.13.0 recommended, matching CI):
```bash
pytest -v tests/
PYTHONPATH=src pytest --cov=src --cov=update --cov=start --cov-report=term-missing    # coverage in terminal
PYTHONPATH=src pytest --cov=src --cov=update --cov=start --cov-report=xml            # coverage for CI (e.g. Codecov)
```

The suite (171 tests) covers all `/src` modules plus `update.py`, `start.py`, `validators.py`, `portfolio_summary.py`, `portfolio_summary_report.py`, and `balance_reconciliation.py`. `tests/conftest.py` adds both the project root and `src/` to `sys.path` so root-level scripts and `src/` modules can be imported directly in tests without stubbing.

The suite (171 tests) covers all `/src` modules plus `update.py`, `start.py`, `validators.py`, `portfolio_summary.py`, `portfolio_summary_report.py`, and `balance_reconciliation.py`. `tests/conftest.py` adds both the project root and `src/` to `sys.path` so root-level scripts and `src/` modules can be imported directly in tests without stubbing.

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

## Continuous Integration
GitHub Actions runs on Python 3.11, 3.12, and 3.13.0 for every push and pull request to `main`.
Each run enforces: Black formatting check, Ruff linting, and pytest with coverage across `src/`, `update.py`, and `start.py` (minimum 70%, uploaded to Codecov).

## Requirements

- Python 3.11+
- Internet connection
- Kraken API credentials

See [requirements.txt](requirements.txt) for full dependency list.

## Building Executable (Windows)

Pre-built Windows executables (`start.exe`, `update.exe`) are published with each
[GitHub Release](https://github.com/patan4ik/kraken-portfolio-tracker/releases).
No Python installation is required to use them.

### CLI Usage — start.exe

usage: start.exe [-h] [--setup-keys] [--days DAYS]

Kraken Portfolio Tracker

options:
-h, --help show this help message and exit
--setup-keys Interactively setup API keys
--days DAYS How many days to include when updating ledger and building reports (default: 7)

### CLI Usage — update.exe

usage: update.exe [-h] [--fromdate FROMDATE] [--todate TODATE] [--dry-run] [--page-size PAGE_SIZE]
[--delay-min DELAY_MIN] [--delay-max DELAY_MAX] [--no-summary]

Incremental ledger updater (requires initialized DB)

options:
-h, --help show this help message and exit
--fromdate FROMDATE Start date or relative (e.g. 30d). Default: last 7d days
--todate TODATE End date or relative (default: today)
--dry-run Do not download; just print plan
--page-size PAGE_SIZE
Page size for API calls
--delay-min DELAY_MIN
Min delay between API calls
--delay-max DELAY_MAX
Max delay between API calls
--no-summary Skip portfolio FIFO summary/forecast recompute after updating the ledger

### Building from source

Executables are built with PyInstaller (`--onedir` mode, UPX-compressed):

```bash
pip install pyinstaller

pyinstaller --onedir --paths src --upx-dir "<path-to-upx>" --exclude-module setuptools --exclude-module pytest --exclude-module pygments --exclude-module wheel --hidden-import storage --hidden-import ledger_loader --hidden-import ledger_eur_report --hidden-import ledger_asset_report --hidden-import ledger_sell_report --hidden-import balances --hidden-import keys --hidden-import config --hidden-import validators --hidden-import api start.py

pyinstaller --onedir --paths src --upx-dir "<path-to-upx>" --exclude-module setuptools --exclude-module pytest --exclude-module pygments --exclude-module wheel --hidden-import storage --hidden-import ledger_loader --hidden-import portfolio_summary --hidden-import portfolio_summary_report --hidden-import balance_reconciliation --hidden-import balances --hidden-import api --hidden-import keys --hidden-import config --hidden-import validators update.py
```

The output for each entrypoint is written to `dist/start/` and `dist/update/` respectively.
For release packaging, both `--onedir` outputs are merged into a single distributable folder
and zipped (see release assets on the [Releases page](https://github.com/patan4ik/kraken-portfolio-tracker/releases)).

## Developer Tooling: LLM Context Generator

This repository includes, located in `tools/project_context.py` — a standalone script unrelated to portfolio tracking or reporting. It exists purely to help contributors and the maintainer quickly share the full (or partial) project structure and source code with an LLM assistant when debugging, reviewing, or planning changes — without manually copy-pasting dozens of files into a chat.

Inspired by benchmarking research on LLM context strategies, which showed that "read all files" context dumps correlate with degraded LLM output quality and excessive token usage. This release adds intermediate context-scoping options between --tree-only and a full dump.

--grep PATTERN — include only files whose content matches a regex pattern.
Useful for pulling in just the code relevant to a specific class, function, or feature name.

--signatures-only — output function/class signatures via Python's ast module, without full implementation bodies. Gives the LLM an interface map at a fraction of the token cost of a full dump.

Automatic runtime warning when full-dump mode includes more than 40 files without any scoping flag (--changed-only, --signatures-only, --grep).

Usage examples:

```bash
# Only the directory structure, no file contents
python tools/project_context.py --tree-only

# Only files changed since the last commit — fast context refresh mid-conversation
python tools/project_context.py --changed-only --output diff_context.md

# Only files relevant to "PortfolioSummary"
python tools/project_context.py --grep "PortfolioSummary" --output portfolio_context.md

# Fast interface map without full code
python tools/project_context.py --signatures-only --output signatures.md

# Full project dump for LLM context
python tools/project_context.py --output context.md
```

`tools/test_context.md` is a sample output of this tool and can be regenerated or deleted freely — it is not consumed by any part of the application, tests, or CI pipeline.

## Real-world token savings (v1.0.3.0 benchmark)

Measured on a live production codebase (Kraken portfolio tracker, ~subset of files matching the tool's default Python profile) using `tiktoken` (`cl100k_base` encoding):

| Mode | Output size | Input tokens | Savings vs. full dump |
|---|---|---|---|
| Full dump (no flags) | 313,339 chars | 73,694 tokens | — |
| `--signatures-only` | 20,200 chars | 4,717 tokens | **93.6% fewer tokens (15.6x smaller)** |
| `--grep "ClassName"` | 40,507 chars | 8,984 tokens | **87.8% fewer tokens (8.2x smaller)** |

Takeaway: for architectural awareness (interfaces, class/function structure), `--signatures-only` gives an LLM nearly the same map at ~6% of the token cost.
For focused debugging on a specific class or feature, `--grep` narrows scope to relevant files while keeping full implementation detail.

## Contributing

✍️ Pull requests are welcome! See CONTRIBUTING.md for details.

## License

✍️ This project is licensed under the MIT License.

```


### `tools/project_context.py`

```python
#!/usr/bin/env python3
"""
project_context.py

CLI-утилита для объединения кода Python-проекта в один текстовый файл,
удобный для передачи в контекст LLM (ChatGPT, Claude, Gemini и т.д.).

Version: 1.0.4.0

Возможности:
- Рекурсивный обход проекта с учётом .gitignore
- Фильтр по расширениям/именам файлов (профиль "python" по умолчанию)
- Исключение служебных директорий (venv, __pycache__, .git и т.д.)
- Режим --tree-only: только дерево проекта без содержимого
- Режим --changed-only: только файлы, изменённые относительно Git (working tree / staged)
- Режим --signatures-only: только сигнатуры функций/классов (AST), без тела, в одном файле
- Режим --grep PATTERN: только файлы, содержимое которых matches regex
- Режим --graph: OKF-flavored вывод — один markdown-файл на модуль с YAML
  frontmatter и явными cross-file ссылками на зависимости (import graph)
- Предупреждение при full-dump режиме на большом количестве файлов
- Ограничение размера вывода (--max-chars) с разбиением на части
- Вывод в файл, в stdout или в буфер обмена (--clipboard)
- Формат вывода: markdown (по умолчанию) или xml-like блоки

Пример использования:
python project_context.py --root . --output context.md
python project_context.py --tree-only
python project_context.py --changed-only --output diff_context.md
python project_context.py --signatures-only --output signatures.md
python project_context.py --grep "PortfolioSummary" --output portfolio_context.md
python project_context.py --graph --output project_graph
python project_context.py --max-chars 50000 --output context.md
"""

from __future__ import annotations

import argparse
import ast
import fnmatch
import os
import re
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
import tiktoken
import importlib.util
from dataclasses import replace

VERSION = "1.0.5.0"

# --------------------------------------------------------------------------- #
# Профили фильтров
# --------------------------------------------------------------------------- #

DEFAULT_INCLUDE_EXT = {
    ".py",
    ".pyi",
    ".md",
    ".rst",
    ".toml",
    ".yaml",
    ".yml",
    ".json",
    ".ini",
    ".cfg",
    ".sql",
    ".sh",
    ".txt",
    ".env.example",
}

DEFAULT_INCLUDE_NAMES = {
    "Dockerfile",
    "Makefile",
    "requirements.txt",
    "requirements-dev.txt",
    "pyproject.toml",
    "setup.py",
    "setup.cfg",
    "docker-compose.yml",
    "docker-compose.yaml",
    ".env.example",
}

DEFAULT_EXCLUDE_DIRS = {
    ".git",
    ".hg",
    ".svn",
    ".venv",
    "venv",
    "env",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".tox",
    ".nox",
    "dist",
    "build",
    ".idea",
    ".vscode",
    "node_modules",
    "htmlcov",
    ".coverage",
    "site-packages",
    ".eggs",
    "*.egg-info",
}

DEFAULT_EXCLUDE_CONTENT_EXT = {
    # файлы, которые остаются в дереве, но содержимое не выводится
    ".csv",
    ".json.lock",
    ".lock",
    ".png",
    ".jpg",
    ".jpeg",
    ".gif",
    ".pdf",
    ".zip",
    ".tar",
    ".gz",
    ".db",
    ".sqlite",
    ".sqlite3",
    ".parquet",
    ".ipynb",
}

DEFAULT_EXCLUDE_FILES = {
    "poetry.lock",
    "Pipfile.lock",
    "package-lock.json",
    "yarn.lock",
}

MAX_FILE_SIZE_BYTES = 300_000  # файлы больше этого лимита не выводятся целиком
FULL_DUMP_FILE_WARNING_THRESHOLD = 40  # порог для предупреждения о перегрузке контекста


@dataclass
class Config:
    root: Path
    output: str | None
    tree_only: bool
    changed_only: bool
    signatures_only: bool
    graph: bool
    grep_pattern: str | None
    max_chars: int | None
    output_format: str
    clipboard: bool
    include_ext: set[str] = field(default_factory=lambda: set(DEFAULT_INCLUDE_EXT))
    include_names: set[str] = field(default_factory=lambda: set(DEFAULT_INCLUDE_NAMES))
    exclude_dirs: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDE_DIRS))
    exclude_content_ext: set[str] = field(
        default_factory=lambda: set(DEFAULT_EXCLUDE_CONTENT_EXT)
    )
    exclude_files: set[str] = field(default_factory=lambda: set(DEFAULT_EXCLUDE_FILES))
    use_gitignore: bool = True


# --------------------------------------------------------------------------- #
# .gitignore
# --------------------------------------------------------------------------- #


def load_gitignore_patterns(root: Path) -> list[str]:
    gi = root / ".gitignore"
    if not gi.exists():
        return []
    patterns = []
    for line in gi.read_text(encoding="utf-8", errors="ignore").splitlines():
        line = line.strip()
        if not line or line.startswith("#"):
            continue
        patterns.append(line)
    return patterns


def is_gitignored(rel_path: str, patterns: list[str]) -> bool:
    for pat in patterns:
        pat_clean = pat.rstrip("/")
        if fnmatch.fnmatch(rel_path, pat_clean) or fnmatch.fnmatch(
            os.path.basename(rel_path), pat_clean
        ):
            return True
        if fnmatch.fnmatch(rel_path, f"{pat_clean}/*") or fnmatch.fnmatch(
            rel_path, f"*/{pat_clean}/*"
        ):
            return True
    return False


# --------------------------------------------------------------------------- #
# Git changed-only
# --------------------------------------------------------------------------- #


def get_changed_files(root: Path) -> set[str]:
    try:
        result = subprocess.run(
            ["git", "-C", str(root), "status", "--porcelain"],
            capture_output=True,
            text=True,
            check=True,
        )
    except (subprocess.CalledProcessError, FileNotFoundError):
        print(
            "Предупреждение: git не найден или это не git-репозиторий. "
            "--changed-only игнорируется.",
            file=sys.stderr,
        )
        return set()

    changed = set()
    for line in result.stdout.splitlines():
        line = line.strip()
        if not line:
            continue
        parts = line.split(maxsplit=1)
        if len(parts) == 2:
            path = parts[1].split(" -> ")[-1]
            changed.add(path)
    return changed


# --------------------------------------------------------------------------- #
# Relevance filter: --grep
# --------------------------------------------------------------------------- #


def matches_grep(path: Path, pattern: re.Pattern) -> bool:
    try:
        content = path.read_text(encoding="utf-8", errors="ignore")
    except OSError:
        return False
    return pattern.search(content) is not None


# --------------------------------------------------------------------------- #
# Обход проекта
# --------------------------------------------------------------------------- #


def should_skip_dir(dirname: str, cfg: Config) -> bool:
    for pattern in cfg.exclude_dirs:
        if fnmatch.fnmatch(dirname, pattern):
            return True
    return False


def should_include_file(path: Path, cfg: Config) -> bool:
    name = path.name
    if name in cfg.exclude_files:
        return False
    if name in cfg.include_names:
        return True
    return path.suffix in cfg.include_ext


def collect_files(cfg: Config) -> list[Path]:
    gitignore_patterns = load_gitignore_patterns(cfg.root) if cfg.use_gitignore else []
    changed_files = get_changed_files(cfg.root) if cfg.changed_only else None
    grep_re = re.compile(cfg.grep_pattern, re.IGNORECASE) if cfg.grep_pattern else None

    collected: list[Path] = []
    for dirpath, dirnames, filenames in os.walk(cfg.root):
        dirnames[:] = [d for d in dirnames if not should_skip_dir(d, cfg)]

        for filename in filenames:
            full_path = Path(dirpath) / filename
            rel_path = str(full_path.relative_to(cfg.root)).replace(os.sep, "/")

            if gitignore_patterns and is_gitignored(rel_path, gitignore_patterns):
                continue
            if not should_include_file(full_path, cfg):
                continue
            if changed_files is not None and rel_path not in changed_files:
                continue
            if grep_re is not None and not matches_grep(full_path, grep_re):
                continue

            collected.append(full_path)

    return sorted(collected)


# --------------------------------------------------------------------------- #
# AST: извлечение сигнатур функций/классов (--signatures-only, --graph)
# --------------------------------------------------------------------------- #


def extract_signatures(path: Path) -> str:
    if path.suffix not in (".py", ".pyi"):
        return ""
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except (SyntaxError, OSError, ValueError):
        return ""

    lines: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, (ast.FunctionDef, ast.AsyncFunctionDef)):
            args = ", ".join(a.arg for a in node.args.args)
            prefix = "async def" if isinstance(node, ast.AsyncFunctionDef) else "def"
            lines.append(f"{prefix} {node.name}({args})")
        elif isinstance(node, ast.ClassDef):
            bases = ", ".join(b.id for b in node.bases if isinstance(b, ast.Name))
            suffix = f"({bases})" if bases else ""
            lines.append(f"class {node.name}{suffix}")
    return "\n".join(lines)


# --------------------------------------------------------------------------- #
# AST: извлечение импортов и построение графа зависимостей (--graph)
# --------------------------------------------------------------------------- #


def extract_imports(path: Path) -> list[str]:
    """Возвращает список имён модулей, импортируемых в файле (top-level)."""
    if path.suffix not in (".py", ".pyi"):
        return []
    try:
        source = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(source)
    except (SyntaxError, OSError, ValueError):
        return []

    modules: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            for alias in node.names:
                modules.append(alias.name.split(".")[0])
        elif isinstance(node, ast.ImportFrom):
            if node.module:
                modules.append(node.module.split(".")[0])
    return modules


def build_dependency_graph(
    files: list[Path], root: Path
) -> tuple[dict[str, list[str]], dict[str, list[str]]]:
    """
    Строит граф внутренних зависимостей проекта на основе import-выражений.

    Возвращает (depends_on, used_by):
      depends_on[rel_path] -> список rel_path модулей, от которых зависит файл
      used_by[rel_path]    -> список rel_path модулей, которые зависят от файла
    """
    py_files = [f for f in files if f.suffix in (".py", ".pyi")]

    # Индекс: имя модуля (stem файла) -> список rel_path с таким stem
    stem_index: dict[str, list[str]] = {}
    for f in py_files:
        rel = f.relative_to(root).as_posix()
        stem_index.setdefault(f.stem, []).append(rel)

    depends_on: dict[str, list[str]] = {}
    used_by: dict[str, list[str]] = {}

    for f in py_files:
        rel = f.relative_to(root).as_posix()
        imported_names = extract_imports(f)
        deps: list[str] = []
        for name in imported_names:
            candidates = stem_index.get(name, [])
            for cand in candidates:
                if cand != rel:
                    deps.append(cand)
        deps = sorted(set(deps))
        depends_on[rel] = deps
        for dep in deps:
            used_by.setdefault(dep, [])
            if rel not in used_by[dep]:
                used_by[dep].append(rel)

    for f in py_files:
        rel = f.relative_to(root).as_posix()
        used_by.setdefault(rel, [])
        used_by[rel] = sorted(set(used_by[rel]))

    return depends_on, used_by


def module_id(rel_path: str) -> str:
    """Преобразует относительный путь в безопасное имя файла для --graph."""
    return rel_path.replace("/", "_").replace("\\", "_").replace(".", "_") + ".md"


# --------------------------------------------------------------------------- #
# Форматирование вывода
# --------------------------------------------------------------------------- #


def build_tree(files: list[Path], root: Path) -> str:
    tree: dict = {}
    for f in files:
        parts = f.relative_to(root).parts
        node = tree
        for part in parts[:-1]:
            node = node.setdefault(part, {})
        node.setdefault("__files__", []).append(parts[-1])

    lines = []

    def walk(node: dict, prefix: str = ""):
        dirs = sorted(k for k in node.keys() if k != "__files__")
        files_here = sorted(node.get("__files__", []))
        entries = [(d, True) for d in dirs] + [(f, False) for f in files_here]
        for i, (name, is_dir) in enumerate(entries):
            connector = "└── " if i == len(entries) - 1 else "├── "
            lines.append(f"{prefix}{connector}{name}{'/' if is_dir else ''}")
            if is_dir:
                extension = "    " if i == len(entries) - 1 else "│   "
                walk(node[name], prefix + extension)

    lines.append(root.name + "/")
    walk(tree)
    return "\n".join(lines)


def read_file_content(path: Path, cfg: Config) -> str | None:
    if path.suffix in cfg.exclude_content_ext:
        return None
    try:
        size = path.stat().st_size
    except OSError:
        return None
    if size > MAX_FILE_SIZE_BYTES:
        return (
            f"[файл пропущен: размер {size} байт превышает лимит {MAX_FILE_SIZE_BYTES}]"
        )

    try:
        raw = path.read_bytes()
    except OSError:
        return None

    # Определяем кодировку по BOM, иначе пробуем utf-8, затем cp1251/latin-1 как fallback
    if raw.startswith(b"\xff\xfe") or raw.startswith(b"\xfe\xff"):
        encoding = "utf-16"
    elif raw.startswith(b"\xef\xbb\xbf"):
        encoding = "utf-8-sig"
    else:
        encoding = "utf-8"

    try:
        return raw.decode(encoding)
    except UnicodeDecodeError:
        try:
            return raw.decode("cp1251")
        except UnicodeDecodeError:
            return raw.decode("utf-8", errors="replace")


def lang_for_highlight(path: Path) -> str:
    mapping = {
        ".py": "python",
        ".pyi": "python",
        ".md": "markdown",
        ".rst": "rst",
        ".toml": "toml",
        ".yaml": "yaml",
        ".yml": "yaml",
        ".json": "json",
        ".ini": "ini",
        ".cfg": "ini",
        ".sql": "sql",
        ".sh": "bash",
        ".txt": "text",
    }
    return mapping.get(path.suffix, "")


def render_markdown(files: list[Path], cfg: Config) -> str:
    parts = []
    parts.append("# PROJECT CONTEXT\n")
    parts.append(f"Корень проекта: `{cfg.root.resolve()}`\n")
    parts.append(f"Файлов включено: {len(files)}\n")

    parts.append("\n## PROJECT TREE\n")
    parts.append("```\n" + build_tree(files, cfg.root) + "\n```\n")

    if cfg.tree_only:
        return "\n".join(parts)

    if cfg.signatures_only:
        parts.append("\n## SIGNATURES\n")
        for f in files:
            rel = f.relative_to(cfg.root).as_posix()
            sig = extract_signatures(f)
            if sig:
                parts.append(f"\n### `{rel}`\n```python\n{sig}\n```\n")
        return "\n".join(parts)

    parts.append("\n## FILE CONTENTS\n")
    for f in files:
        rel = f.relative_to(cfg.root).as_posix()
        content = read_file_content(f, cfg)
        parts.append(f"\n### `{rel}`\n")
        if content is None:
            parts.append("_[содержимое не выводится: бинарный/исключённый файл]_\n")
        else:
            lang = lang_for_highlight(f)
            parts.append(f"```{lang}\n{content}\n```\n")

    return "\n".join(parts)


def render_xml(files: list[Path], cfg: Config) -> str:
    parts = []
    parts.append("<project_context>")
    parts.append(f"  <root>{cfg.root.resolve()}</root>")
    parts.append(f"  <file_count>{len(files)}</file_count>")
    parts.append(f"  <tree><![CDATA[\n{build_tree(files, cfg.root)}\n]]></tree>")

    if cfg.tree_only:
        parts.append("</project_context>")
        return "\n".join(parts)

    if cfg.signatures_only:
        parts.append("  <signatures>")
        for f in files:
            rel = f.relative_to(cfg.root).as_posix()
            sig = extract_signatures(f)
            if sig:
                parts.append(f'    <file path="{rel}"><![CDATA[\n{sig}\n]]></file>')
        parts.append("  </signatures>")
        parts.append("</project_context>")
        return "\n".join(parts)

    parts.append("  <files>")
    for f in files:
        rel = f.relative_to(cfg.root).as_posix()
        content = read_file_content(f, cfg)
        if content is None:
            parts.append(f'    <file path="{rel}" hidden="true"/>')
        else:
            parts.append(f'    <file path="{rel}"><![CDATA[\n{content}\n]]></file>')
    parts.append("  </files>")
    parts.append("</project_context>")
    return "\n".join(parts)


def render(files: list[Path], cfg: Config) -> str:
    if cfg.output_format == "xml":
        return render_xml(files, cfg)
    return render_markdown(files, cfg)


# --------------------------------------------------------------------------- #
# --graph: OKF-flavored многофайловый вывод
# --------------------------------------------------------------------------- #


def render_graph(files: list[Path], cfg: Config) -> dict[str, str]:
    """
    Генерирует OKF-flavored вывод: один markdown-файл на модуль с YAML
    frontmatter (path, depends_on, used_by) и сигнатурами. Плюс index.md
    со ссылками на все модули.

    Возвращает словарь {имя_файла: содержимое}, который затем пишется
    на диск функцией write_graph_output().
    """
    py_files = [f for f in files if f.suffix in (".py", ".pyi")]
    depends_on, used_by = build_dependency_graph(py_files, cfg.root)

    output: dict[str, str] = {}
    index_lines = [
        "# PROJECT GRAPH INDEX\n",
        f"Корень проекта: `{cfg.root.resolve()}`\n",
    ]
    index_lines.append(f"Модулей: {len(py_files)}\n")
    index_lines.append("\n## PROJECT TREE\n")
    index_lines.append("```\n" + build_tree(files, cfg.root) + "\n```\n")
    index_lines.append("\n## MODULES\n")

    for f in sorted(py_files, key=lambda p: p.relative_to(cfg.root).as_posix()):
        rel = f.relative_to(cfg.root).as_posix()
        fname = module_id(rel)
        deps = depends_on.get(rel, [])
        users = used_by.get(rel, [])
        sig = extract_signatures(f)

        fm_deps = ", ".join(deps) if deps else ""
        fm_users = ", ".join(users) if users else ""

        parts = []
        parts.append("---")
        parts.append("type: module")
        parts.append(f"path: {rel}")
        parts.append(f"depends_on: [{fm_deps}]")
        parts.append(f"used_by: [{fm_users}]")
        parts.append("---\n")
        parts.append(f"# `{rel}`\n")

        if sig:
            parts.append("## Signatures\n")
            parts.append(f"```python\n{sig}\n```\n")
        else:
            parts.append("_[нет функций/классов на верхнем уровне]_\n")

        if deps:
            parts.append("## Dependencies\n")
            for dep in deps:
                dep_fname = module_id(dep)
                parts.append(f"- [{dep}](./{dep_fname})")
            parts.append("")

        if users:
            parts.append("## Used by\n")
            for user in users:
                user_fname = module_id(user)
                parts.append(f"- [{user}](./{user_fname})")
            parts.append("")

        output[fname] = "\n".join(parts)
        index_lines.append(f"- [{rel}](./{fname})")

    output["index.md"] = "\n".join(index_lines)
    return output


def write_graph_output(graph_files: dict[str, str], cfg: Config) -> Path:
    out_dir = Path(cfg.output) if cfg.output else Path("project_graph")
    out_dir.mkdir(parents=True, exist_ok=True)
    for fname, content in graph_files.items():
        (out_dir / fname).write_text(content, encoding="utf-8")
    return out_dir


# --------------------------------------------------------------------------- #
# Разбиение на части по лимиту символов
# --------------------------------------------------------------------------- #


def split_by_max_chars(text: str, max_chars: int) -> list[str]:
    if len(text) <= max_chars:
        return [text]
    chunks = []
    start = 0
    while start < len(text):
        end = min(start + max_chars, len(text))
        chunks.append(text[start:end])
        start = end
    return chunks


def write_output(text: str, cfg: Config) -> list[Path]:
    written_paths: list[Path] = []

    if cfg.max_chars:
        chunks = split_by_max_chars(text, cfg.max_chars)
    else:
        chunks = [text]

    if cfg.output is None:
        for chunk in chunks:
            print(chunk)
        return written_paths

    base = Path(cfg.output)
    if len(chunks) == 1:
        base.write_text(text, encoding="utf-8")
        written_paths.append(base)
    else:
        stem, suffix = base.stem, base.suffix or ".md"
        for i, chunk in enumerate(chunks, start=1):
            part_path = base.with_name(f"{stem}_part{i}{suffix}")
            part_path.write_text(chunk, encoding="utf-8")
            written_paths.append(part_path)

    return written_paths


def copy_to_clipboard(text: str) -> bool:
    try:
        import pyperclip

        pyperclip.copy(text)
        return True
    except ImportError:
        print(
            "Модуль pyperclip не установлен. Установите: pip install pyperclip",
            file=sys.stderr,
        )
        return False


# --------------------------------------------------------------------------- #
# Benchmarks
# --------------------------------------------------------------------------- #


def run_benchmark(cfg: Config) -> list[dict]:
    """
    Executes full, signatures-only, and graph modes against the same
    project root, measures tiktoken cl100k_base token counts and raw
    character counts for each, and returns comparison rows.

    If cfg.grep_pattern is set, also benchmarks the --grep mode using
    that pattern.
    """

    enc = tiktoken.get_encoding("cl100k_base")
    rows = []

    def measure(label: str, text_or_texts) -> dict:
        if isinstance(text_or_texts, dict):
            chars = sum(len(t) for t in text_or_texts.values())
            tokens = sum(len(enc.encode(t)) for t in text_or_texts.values())
        else:
            chars = len(text_or_texts)
            tokens = len(enc.encode(text_or_texts))
        return {"mode": label, "characters": chars, "tokens": tokens}

    base_cfg = replace(
        cfg, tree_only=False, signatures_only=False, graph=False, grep_pattern=None
    )
    full_files = collect_files(base_cfg)
    full_text = render(full_files, base_cfg)
    rows.append(measure("full", full_text))

    sig_cfg = replace(base_cfg, signatures_only=True)
    sig_files = collect_files(sig_cfg)
    sig_text = render(sig_files, sig_cfg)
    rows.append(measure("signatures-only", sig_text))

    if cfg.grep_pattern:
        grep_cfg = replace(base_cfg, grep_pattern=cfg.grep_pattern)
        grep_files = collect_files(grep_cfg)
        grep_text = render(grep_files, grep_cfg)
        rows.append(measure(f"grep:{cfg.grep_pattern}", grep_text))

    graph_cfg = replace(base_cfg, graph=True)
    graph_files = collect_files(graph_cfg)
    graph_dict = render_graph(graph_files, graph_cfg)
    rows.append(measure("graph", graph_dict))

    baseline_tokens = rows[0]["tokens"]
    for row in rows:
        row["reduction_pct"] = round(100 * (1 - row["tokens"] / baseline_tokens), 1)
        row["multiplier"] = round(baseline_tokens / row["tokens"], 1)

    return rows


def print_benchmark_table(rows: list[dict]) -> None:
    print(
        f"{'Mode':<20} {'Chars':>10} {'Tokens':>10} {'Reduction':>10} {'Smaller':>10}"
    )
    print("-" * 62)
    for row in rows:
        print(
            f"{row['mode']:<20} {row['characters']:>10} {row['tokens']:>10} "
            f"{row['reduction_pct']:>9}% {row['multiplier']:>9}x"
        )


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def parse_args() -> Config:
    parser = argparse.ArgumentParser(
        description="Объединяет код Python-проекта в один файл для LLM-контекста."
    )
    parser.add_argument(
        "--version", action="version", version=f"project_context.py {VERSION}"
    )
    parser.add_argument(
        "--root", type=str, default=".", help="Корневая директория проекта"
    )
    parser.add_argument(
        "--output",
        type=str,
        default="project_context.md",
        help="Путь к выходному файлу (или директории для --graph). Пусто/'-' для stdout",
    )
    parser.add_argument(
        "--tree-only",
        action="store_true",
        help="Вывести только дерево проекта, без содержимого файлов",
    )
    parser.add_argument(
        "--changed-only",
        action="store_true",
        help="Включить только изменённые (git status) файлы",
    )
    parser.add_argument(
        "--signatures-only",
        action="store_true",
        help="Вывести только сигнатуры функций/классов (AST) в одном файле",
    )
    parser.add_argument(
        "--graph",
        action="store_true",
        help=(
            "OKF-flavored вывод: один markdown-файл на модуль с YAML "
            "frontmatter и cross-file ссылками на import-зависимости, "
            "плюс index.md. --output трактуется как директория."
        ),
    )
    parser.add_argument(
        "--grep",
        type=str,
        default=None,
        dest="grep_pattern",
        help="Включать только файлы, содержимое которых matches regex-паттерн",
    )
    parser.add_argument(
        "--max-chars",
        type=int,
        default=None,
        help="Максимум символов на файл вывода, для разбиения на части",
    )
    parser.add_argument(
        "--format",
        type=str,
        choices=["md", "xml"],
        default="md",
        help="Формат вывода: markdown или xml-like (игнорируется при --graph)",
    )
    parser.add_argument(
        "--clipboard",
        action="store_true",
        help="Скопировать результат в буфер обмена (требует pyperclip, игнорируется при --graph)",
    )
    parser.add_argument(
        "--no-gitignore", action="store_true", help="Не учитывать правила .gitignore"
    )
    parser.add_argument(
        "--include-ext",
        type=str,
        default=None,
        help="Доп. расширения через запятую, напр: .env,.j2",
    )
    parser.add_argument(
        "--exclude-dir",
        type=str,
        default=None,
        help="Доп. директории для исключения через запятую",
    )
    parser.add_argument(
        "--report",
        action="store_true",
        help=(
            "Run full, signatures-only, graph (and grep, if --grep is set) "
            "modes against the same root and print a token/character "
            "comparison table using tiktoken (cl100k_base)."
        ),
    )
    args = parser.parse_args()

    output = None if (args.output in ("-", "", None)) else args.output

    cfg = Config(
        root=Path(args.root).resolve(),
        output=output,
        tree_only=args.tree_only,
        changed_only=args.changed_only,
        signatures_only=args.signatures_only,
        graph=args.graph,
        grep_pattern=args.grep_pattern,
        max_chars=args.max_chars,
        output_format=args.format,
        clipboard=args.clipboard,
        use_gitignore=not args.no_gitignore,
    )
    if args.include_ext:
        cfg.include_ext |= {e.strip() for e in args.include_ext.split(",") if e.strip()}
    if args.exclude_dir:
        cfg.exclude_dirs |= {
            d.strip() for d in args.exclude_dir.split(",") if d.strip()
        }

    if cfg.graph and cfg.output == "project_context.md":
        # если пользователь не переопределил --output явно, используем
        # разумное имя директории по умолчанию для --graph
        cfg.output = "project_graph"

    return cfg


def warn_if_full_dump_overload(files: list[Path], cfg: Config) -> None:
    is_scoped = (
        cfg.tree_only
        or cfg.changed_only
        or cfg.signatures_only
        or cfg.graph
        or cfg.grep_pattern is not None
    )
    if not is_scoped and len(files) > FULL_DUMP_FILE_WARNING_THRESHOLD:
        print(
            f"[warning] Full-dump режим с {len(files)} файлами может перегрузить "
            "контекст LLM и снизить качество ответа. Рассмотрите --changed-only, "
            "--signatures-only, --graph или --grep для более точечного контекста.",
            file=sys.stderr,
        )


def main() -> None:
    cfg = parse_args()

    if not cfg.root.exists():
        print(f"Ошибка: директория {cfg.root} не найдена", file=sys.stderr)
        sys.exit(1)

    files = collect_files(cfg)

    if not files:
        print("Не найдено ни одного файла, подходящего под фильтры.", file=sys.stderr)
        sys.exit(0)

    warn_if_full_dump_overload(files, cfg)

    if cfg.graph:
        graph_files = render_graph(files, cfg)
        out_dir = write_graph_output(graph_files, cfg)
        total_chars = sum(len(c) for c in graph_files.values())
        print(
            f"Записано в {out_dir}: {len(graph_files)} файлов, "
            f"{total_chars} символов суммарно.",
            file=sys.stderr,
        )
        return

    text = render(files, cfg)

    written = write_output(text, cfg)
    if written:
        for p in written:
            print(
                f"Записано: {p} ({len(p.read_text(encoding='utf-8'))} символов)",
                file=sys.stderr,
            )

    if cfg.clipboard:
        if copy_to_clipboard(text):
            print("Результат скопирован в буфер обмена.", file=sys.stderr)

    if cfg.report:
        if importlib.util.find_spec("tiktoken") is None:
            print(
                "--report requires tiktoken. Install with: pip install tiktoken",
                file=sys.stderr,
            )
            sys.exit(1)
        rows = run_benchmark(cfg)
        print_benchmark_table(rows)
        return


if __name__ == "__main__":
    main()

```


### `tools/project_context_docs.md`

```markdown
# project_context.py — Usage Guide

CLI utility that turns a Python repository into a single, LLM-ready context document. Designed to be dropped into a `tools/` folder of any Python project and reused across projects without modification.

## Modes and measured token cost

As of v1.0.3.0, this table is backed by a real benchmark run against a production codebase (Kraken portfolio tracker), measured with `tiktoken` (`cl100k_base` encoding) — not estimates.

| Flag | Purpose | Tokens (measured) | Savings vs. full dump |
|---|---|---|---|
| (default, no flags) | Full tree + full file contents | 73,694 | baseline |
| `--signatures-only` | Function/class signatures via AST, no bodies | 4,717 | 93.6% fewer tokens (15.6x smaller) |
| `--grep PATTERN` | Only files whose content matches a regex, full detail kept | 8,984 | 87.8% fewer tokens (8.2x smaller) |
| `--tree-only` | Architecture only, no file contents | not benchmarked, expect <1% of full dump | very low |

Note the difference between `--signatures-only` and `--grep`: signatures-only strips implementation bodies from every file (interface map only), while `--grep` keeps full implementation detail but narrows the file set to only what matches the pattern. Choose based on whether you need breadth (signatures) or depth on a specific area (grep).

Running the default full-dump mode on more than 40 files without any scoping flag prints a warning to stderr, since unscoped dumps have been shown to correlate with degraded LLM output quality and unnecessary token spend.

## Installation

No external dependencies required for core functionality. Optional:

```bash
pip install pyperclip   # only needed for --clipboard
```

## Examples

Starting a new LLM chat with full context:
```bash
python tools/project_context.py --output context.md
```

Mid-refactor update — only files you just edited:
```bash
python tools/project_context.py --changed-only --clipboard
```

Architecture-only review (e.g. onboarding a new AI session):
```bash
python tools/project_context.py --tree-only
```

Reviewing only logic related to a specific class or feature, with full detail:
```bash
python tools/project_context.py --grep "PortfolioSummary" --output portfolio_context.md
```

Getting a fast interface map without full code — cheapest way to give an LLM architectural awareness of a large codebase (measured 15.6x token reduction):
```bash
python tools/project_context.py --signatures-only --output signatures.md
```

Splitting a large context into chunks under a model's context window:
```bash
python tools/project_context.py --max-chars 50000 --output context.md
```

Using XML-like output instead of Markdown:
```bash
python tools/project_context.py --format xml --output context.xml
```

## Recommended workflow

1. Start a new AI conversation with `--tree-only` so the model understands the architecture first.
2. If deep review is needed, follow up with `--signatures-only` to give the model an interface map at roughly 6% of the token cost of a full dump.
3. During iterative development, use `--changed-only --clipboard` to refresh the model with only what you've actually modified.
4. For focused debugging on one class or feature, use `--grep "ClassName"` — full implementation detail on relevant files only, at roughly 12% of the token cost of a full dump.
5. Reserve the unscoped full-dump mode for small projects or first-time full audits — expect the warning on repositories with 40+ files.

## Benchmarking your own project

Reproduce the comparison above on your own codebase:

```bash
python tools/project_context.py --output full.md
python tools/project_context.py --signatures-only --output sig.md
python tools/project_context.py --grep "YourClassName" --output grep.md
```

Each run prints the character count to stderr automatically. For a token
count closer to what an LLM actually charges, use `tiktoken`:

```bash
pip install tiktoken
python -c "import tiktoken; enc = tiktoken.get_encoding('cl100k_base'); [print(f, len(enc.encode(open(f, encoding='utf-8').read()))) for f in ['full.md','sig.md','grep.md']]"
```

Sample outputs generated for benchmarking (e.g. `full.md`, `sig.md`, `grep.md`, `test_context.md`) are disposable — they are not consumed by the tool, its tests, or CI, and should not be committed to version control. Add them to `.gitignore` if you regenerate them locally.

## Testing

```bash
pip install pytest
pytest tests/test_project_context.py -v
```

## Version history

See `CHANGELOG.md` for the full history of changes.

```
