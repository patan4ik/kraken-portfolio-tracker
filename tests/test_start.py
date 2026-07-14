"""Unit tests for start.py — central CLI launcher orchestrating balances, ledger, reports."""

import os
import sys
import types

import pandas as pd
import pytest
import pathlib

_TESTS_DIR = pathlib.Path(__file__).resolve().parent
_PROJECT_ROOT = _TESTS_DIR.parent  # adjust if start.py lives elsewhere
_START_PY = _PROJECT_ROOT / "start.py"


@pytest.fixture()
def start_mod(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    src_dir = tmp_path / "src"
    os.makedirs(src_dir, exist_ok=True)
    monkeypatch.syspath_prepend(str(src_dir))

    storage_stub = types.ModuleType("storage")
    storage_stub.DB_FILE = str(tmp_path / "ledger.db")
    storage_stub.RAW_LEDGER_FILE = str(tmp_path / "raw-ledger.json")
    storage_stub.load_entries = lambda: {}
    storage_stub.save_entries = lambda e: None
    storage_stub.init_db = lambda: None
    storage_stub.load_entries_from_db = lambda: {}
    monkeypatch.setitem(sys.modules, "storage", storage_stub)

    ll_stub = types.ModuleType("ledger_loader")
    ll_stub.update_raw_ledger = lambda days=7: None
    monkeypatch.setitem(sys.modules, "ledger_loader", ll_stub)

    eur_stub = types.ModuleType("ledger_eur_report")
    eur_stub.build_eur_report = lambda entries, days=7: pd.DataFrame()
    eur_stub.save_eur_report = lambda df: None
    monkeypatch.setitem(sys.modules, "ledger_eur_report", eur_stub)

    asset_stub = types.ModuleType("ledger_asset_report")
    asset_stub.build_asset_report = lambda entries, days=7: pd.DataFrame()
    asset_stub.save_asset_report = lambda df: None
    monkeypatch.setitem(sys.modules, "ledger_asset_report", asset_stub)

    sell_stub = types.ModuleType("ledger_sell_report")
    sell_stub.build_sell_report = lambda entries, days=7: pd.DataFrame()
    sell_stub.save_sell_report = lambda df: None
    monkeypatch.setitem(sys.modules, "ledger_sell_report", sell_stub)

    balances_stub = types.ModuleType("balances")
    balances_stub.main = lambda argv=None: 0
    monkeypatch.setitem(sys.modules, "balances", balances_stub)

    keys_stub = types.ModuleType("keys")

    class KeysError(Exception):
        pass

    keys_stub.KeysError = KeysError
    keys_stub.save_keys = lambda k, s: None
    keys_stub.load_keys = lambda: ("k", "s")
    monkeypatch.setitem(sys.modules, "keys", keys_stub)

    config_stub = types.ModuleType("config")
    config_stub.DEFAULT_DAYS = 7
    monkeypatch.setitem(sys.modules, "config", config_stub)

    validators_stub = types.ModuleType("validators")
    validators_stub.db_row_count = lambda path: 0
    monkeypatch.setitem(sys.modules, "validators", validators_stub)

    if "start" in sys.modules:
        del sys.modules["start"]

    # start.py may not exist at cwd; instead import from provided file path
    yield {
        "storage": storage_stub,
        "ll": ll_stub,
        "balances": balances_stub,
        "keys": keys_stub,
        "config": config_stub,
        "validators": validators_stub,
    }
    if "start" in sys.modules:
        del sys.modules["start"]


def _load_start_module():
    """Load start.py as a module named 'start' from its real repo location."""
    import importlib.util

    if not _START_PY.exists():
        pytest.skip(f"start.py not found at {_START_PY}")
    spec = importlib.util.spec_from_file_location("start", str(_START_PY))
    mod = importlib.util.module_from_spec(spec)
    sys.modules["start"] = mod
    spec.loader.exec_module(mod)
    return mod


def test_main_setup_keys_missing_input(start_mod, monkeypatch, capsys):
    start = _load_start_module()
    monkeypatch.setattr("builtins.input", lambda prompt="": "")
    start.main(["--setup-keys"])
    captured = capsys.readouterr()
    assert "required" in captured.out.lower()


def test_main_setup_keys_success(start_mod, monkeypatch, capsys):
    start = _load_start_module()
    responses = iter(["mykey", "mysecret"])
    monkeypatch.setattr("builtins.input", lambda prompt="": next(responses))
    saved = {}
    monkeypatch.setattr(start, "save_keys", lambda k, s: saved.update(key=k, secret=s))
    start.main(["--setup-keys"])
    assert saved == {"key": "mykey", "secret": "mysecret"}


def test_main_key_error_exits(start_mod, monkeypatch):
    start = _load_start_module()

    def raise_keyerror():
        raise start.KeysError("no keys")

    monkeypatch.setattr(start, "load_keys", raise_keyerror)
    with pytest.raises(SystemExit) as exc:
        start.main([])
    assert exc.value.code == 1


def test_main_happy_path_returns_balances_result(start_mod, monkeypatch):
    start = _load_start_module()
    monkeypatch.setattr(start, "load_keys", lambda: ("k", "s"))
    monkeypatch.setattr(start.balances, "main", lambda argv: 42)
    monkeypatch.setattr(start.storage, "load_entries_from_db", lambda: {})
    result = start.main([])
    assert result == 42


def test_main_force_update_when_days_specified(start_mod, monkeypatch):
    start = _load_start_module()
    monkeypatch.setattr(start, "load_keys", lambda: ("k", "s"))
    monkeypatch.setattr(start.balances, "main", lambda argv: 0)
    calls = {"n": 0}
    monkeypatch.setattr(
        start.ledger_loader,
        "update_raw_ledger",
        lambda days=7: calls.update(n=calls["n"] + 1),
    )
    monkeypatch.setattr(start.storage, "load_entries_from_db", lambda: {})
    start.main(["--days", "30"])
    assert calls["n"] >= 1


def test_main_generates_reports_when_data_present(start_mod, monkeypatch):
    start = _load_start_module()
    monkeypatch.setattr(start, "load_keys", lambda: ("k", "s"))
    monkeypatch.setattr(start.balances, "main", lambda argv: 0)
    entries = {"t1": {"asset": "BTC", "amount": 1.0, "time": 1700000000.0}}
    monkeypatch.setattr(start.storage, "load_entries_from_db", lambda: entries)

    saved = {}
    non_empty_df = pd.DataFrame([{"Date": "2026-01-01", "BTC": 1.0}])
    monkeypatch.setattr(
        start.ledger_eur_report, "build_eur_report", lambda e, days=7: non_empty_df
    )
    monkeypatch.setattr(
        start.ledger_eur_report, "save_eur_report", lambda df: saved.update(eur=True)
    )
    monkeypatch.setattr(
        start.ledger_asset_report, "build_asset_report", lambda e, days=7: non_empty_df
    )
    monkeypatch.setattr(
        start.ledger_asset_report,
        "save_asset_report",
        lambda df: saved.update(asset=True),
    )
    monkeypatch.setattr(
        start.ledger_sell_report, "build_sell_report", lambda e, days=7: non_empty_df
    )
    monkeypatch.setattr(
        start.ledger_sell_report, "save_sell_report", lambda df: saved.update(sell=True)
    )

    start.main([])
    assert saved.get("eur") and saved.get("asset") and saved.get("sell")
