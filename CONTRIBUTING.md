# Contributing

1. Create and activate virtual environment:
```bash
python -m venv venv
source venv/bin/activate  # Windows: venv\Scripts\activate
pip install -r requirements.txt
```

2. Run tests locally:
```bash
pytest -v
```

3. Use Black and Ruff before committing:
```bash
black .
ruff check . --fix
```
