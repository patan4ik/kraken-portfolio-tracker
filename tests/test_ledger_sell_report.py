"""Unit tests for ledger_sell_report.py — daily sell aggregation (crypto -> EUR)."""

import sys
import types

import pytest


@pytest.fixture()
def sell_mod(tmp_path, monkeypatch):
    storage_stub = types.ModuleType("storage")
    storage_stub.BALANCES_DIR = str(tmp_path)
    monkeypatch.setitem(sys.modules, "storage", storage_stub)
    if "ledger_sell_report" in sys.modules:
        del sys.modules["ledger_sell_report"]
    import ledger_sell_report as sell_mod  # noqa: E402

    yield sell_mod
    if "ledger_sell_report" in sys.modules:
        del sys.modules["ledger_sell_report"]


def _entry(refid, asset, amount, fee=0.0, time_=None):
    import time as _t

    return {
        "asset": asset,
        "amount": amount,
        "fee": fee,
        "refid": refid,
        "time": time_ if time_ is not None else _t.time(),
    }


def test_build_sell_report_empty(sell_mod):
    assert sell_mod.build_sell_report({}).empty


def test_build_sell_report_basic(sell_mod):
    import time as _t

    now = _t.time()
    entries = {
        "s1": _entry("r1", "BTC", -0.01, fee=0.5, time_=now),
        "e1": _entry("r1", "ZEUR", 200.0, time_=now),
    }
    df = sell_mod.build_sell_report(entries, days=7)
    assert not df.empty
    assert df.iloc[0]["Total EUR"] == pytest.approx(200.0)
    assert df.iloc[0]["BTC"] == pytest.approx(0.01)


def test_build_sell_report_requires_both_legs(sell_mod):
    import time as _t

    now = _t.time()
    entries = {"s1": _entry("r1", "BTC", -0.01, time_=now)}
    df = sell_mod.build_sell_report(entries, days=7)
    assert df.empty


def test_build_sell_report_outside_cutoff(sell_mod):
    entries = {
        "s1": _entry("r1", "BTC", -0.01, time_=1.0),
        "e1": _entry("r1", "ZEUR", 200.0, time_=1.0),
    }
    df = sell_mod.build_sell_report(entries, days=7)
    assert df.empty


def test_save_sell_report_writes_csv(sell_mod):
    import pandas as pd
    import os

    df = pd.DataFrame(
        [{"Date": "2026-01-01", "Total EUR": 200.0, "Total Fee": 0.5, "BTC": 0.01}]
    )
    sell_mod.save_sell_report(df)
    assert os.path.exists(sell_mod.LEDGER_SELL_FILE)


def test_update_sell_report_empty(sell_mod, monkeypatch):
    monkeypatch.setattr(
        sell_mod.storage, "load_entries_from_db", lambda: {}, raising=False
    )
    df = sell_mod.update_sell_report(days=7, write_csv=False)
    assert df.empty


def test_update_sell_report_with_data(sell_mod):
    import time as _t
    import os

    now = _t.time()
    entries = {
        "s1": _entry("r1", "BTC", -0.01, fee=0.5, time_=now),
        "e1": _entry("r1", "ZEUR", 200.0, time_=now),
    }
    sell_mod.storage.load_entries_from_db = lambda: entries
    df = sell_mod.update_sell_report(days=7, write_csv=True)
    assert not df.empty
    assert os.path.exists(sell_mod.LEDGER_SELL_FILE)
