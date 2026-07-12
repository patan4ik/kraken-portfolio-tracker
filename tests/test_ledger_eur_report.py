"""Unit tests for ledger_eur_report.py — daily EUR spend breakdown per asset."""

import sys
import types

import pytest


@pytest.fixture()
def eur_mod(tmp_path, monkeypatch):
    storage_stub = types.ModuleType("storage")
    storage_stub.BALANCES_DIR = str(tmp_path)
    monkeypatch.setitem(sys.modules, "storage", storage_stub)
    if "ledger_eur_report" in sys.modules:
        del sys.modules["ledger_eur_report"]
    import ledger_eur_report as eur_mod  # noqa: E402

    yield eur_mod
    if "ledger_eur_report" in sys.modules:
        del sys.modules["ledger_eur_report"]


def _spend(refid, asset, amount, fee=0.0, time_=None):
    import time as _t

    return {
        "asset": asset,
        "amount": amount,
        "fee": fee,
        "refid": refid,
        "type": "trade",
        "time": time_ if time_ is not None else _t.time(),
    }


def test_build_eur_report_empty_entries(eur_mod):
    assert eur_mod.build_eur_report({}).empty


def test_build_eur_report_basic_spend(eur_mod):
    import time as _t

    now = _t.time()
    entries = {
        "s1": _spend("r1", "ZEUR", -100.0, fee=1.0, time_=now),
        "b1": _spend("r1", "BTC", 0.01, time_=now),
    }
    df = eur_mod.build_eur_report(entries, days=7)
    assert not df.empty
    assert "BTC" in df.columns
    assert df.iloc[0]["Total Spent EUR"] == 100.0


def test_build_eur_report_multi_asset_allocation(eur_mod):
    import time as _t

    now = _t.time()
    entries = {
        "s1": _spend("r1", "ZEUR", -100.0, time_=now),
        "b1": _spend("r1", "BTC", 0.5, time_=now),
        "b2": _spend("r1", "ETH", 0.5, time_=now),
    }
    df = eur_mod.build_eur_report(entries, days=7)
    assert df.iloc[0]["BTC"] == pytest.approx(50.0)
    assert df.iloc[0]["ETH"] == pytest.approx(50.0)


def test_build_eur_report_excludes_old_entries(eur_mod):
    old_time = 1.0  # epoch, way outside cutoff
    entries = {
        "s1": _spend("r1", "ZEUR", -100.0, time_=old_time),
        "b1": _spend("r1", "BTC", 0.01, time_=old_time),
    }
    df = eur_mod.build_eur_report(entries, days=7)
    assert df.empty


def test_build_eur_report_no_receive_leg_skipped(eur_mod):
    import time as _t

    now = _t.time()
    entries = {"s1": _spend("r1", "ZEUR", -100.0, time_=now)}
    df = eur_mod.build_eur_report(entries, days=7)
    assert df.empty


def test_save_eur_report_writes_csv(eur_mod, tmp_path):
    import pandas as pd

    df = pd.DataFrame(
        [
            {
                "Date": "2026-01-01",
                "Total Fee": 1.0,
                "Total Spent EUR": 100.0,
                "BTC": 100.0,
            }
        ]
    )
    eur_mod.save_eur_report(df)
    assert __import__("os").path.exists(eur_mod.LEDGER_EUR_FILE)


def test_update_eur_report_no_entries(eur_mod, monkeypatch):
    storage_mock = eur_mod.storage
    monkeypatch.setattr(storage_mock, "load_entries_from_db", lambda: {}, raising=False)
    df = eur_mod.update_eur_report(days=7, write_csv=False)
    assert df.empty


def test_update_eur_report_with_data(eur_mod, monkeypatch):
    import time as _t

    now = _t.time()
    entries = {
        "s1": _spend("r1", "ZEUR", -100.0, time_=now),
        "b1": _spend("r1", "BTC", 0.01, time_=now),
    }
    eur_mod.storage.load_entries_from_db = lambda: entries
    df = eur_mod.update_eur_report(days=7, write_csv=True)
    assert not df.empty
    assert __import__("os").path.exists(eur_mod.LEDGER_EUR_FILE)
