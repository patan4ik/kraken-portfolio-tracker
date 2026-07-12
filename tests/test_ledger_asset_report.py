"""Unit tests for ledger_asset_report.py — daily asset acquisition aggregation."""

import sys
import types

import pytest


@pytest.fixture()
def asset_mod(tmp_path, monkeypatch):
    storage_stub = types.ModuleType("storage")
    storage_stub.BALANCES_DIR = str(tmp_path)
    monkeypatch.setitem(sys.modules, "storage", storage_stub)
    if "ledger_asset_report" in sys.modules:
        del sys.modules["ledger_asset_report"]
    import ledger_asset_report as asset_mod  # noqa: E402

    yield asset_mod
    if "ledger_asset_report" in sys.modules:
        del sys.modules["ledger_asset_report"]


def _entry(refid, asset, amount, time_=None):
    import time as _t

    return {
        "asset": asset,
        "amount": amount,
        "refid": refid,
        "time": time_ if time_ is not None else _t.time(),
    }


def test_build_asset_report_empty(asset_mod):
    assert asset_mod.build_asset_report({}).empty


def test_build_asset_report_basic(asset_mod):
    import time as _t

    now = _t.time()
    entries = {
        "b1": _entry("r1", "BTC", 0.01, time_=now),
        "s1": _entry("r1", "ZEUR", -100.0, time_=now),
    }
    df = asset_mod.build_asset_report(entries, days=7)
    assert not df.empty
    assert "BTC" in df.columns
    assert df.iloc[0]["BTC"] == pytest.approx(0.01)


def test_build_asset_report_excludes_eur_leg(asset_mod):
    import time as _t

    now = _t.time()
    entries = {"s1": _entry("r1", "ZEUR", 100.0, time_=now)}
    df = asset_mod.build_asset_report(entries, days=7)
    assert df.empty


def test_build_asset_report_outside_cutoff(asset_mod):
    entries = {"b1": _entry("r1", "BTC", 0.01, time_=1.0)}
    df = asset_mod.build_asset_report(entries, days=7)
    assert df.empty


def test_save_asset_report_writes_csv(asset_mod):
    import pandas as pd
    import os

    df = pd.DataFrame([{"Date": "2026-01-01", "BTC": 0.01}])
    asset_mod.save_asset_report(df)
    assert os.path.exists(asset_mod.LEDGER_ASSET_FILE)


def test_update_asset_report_empty(asset_mod, monkeypatch):
    monkeypatch.setattr(
        asset_mod.storage, "load_entries_from_db", lambda: {}, raising=False
    )
    df = asset_mod.update_asset_report(days=7, write_csv=False)
    assert df.empty


def test_update_asset_report_with_data(asset_mod):
    import time as _t
    import os

    now = _t.time()
    entries = {
        "b1": _entry("r1", "BTC", 0.01, time_=now),
        "s1": _entry("r1", "ZEUR", -100.0, time_=now),
    }
    asset_mod.storage.load_entries_from_db = lambda: entries
    df = asset_mod.update_asset_report(days=7, write_csv=True)
    assert not df.empty
    assert os.path.exists(asset_mod.LEDGER_ASSET_FILE)
