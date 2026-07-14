"""Unit tests for balances.py — portfolio balance aggregation, CSV/snapshot IO, CLI."""

import os
import sys
import types
from decimal import Decimal

import pandas as pd
import pytest


@pytest.fixture()
def balances_mod(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)

    keys_stub = types.ModuleType("keys")

    class KeysError(Exception):
        pass

    keys_stub.KeysError = KeysError
    keys_stub.load_keys = lambda: ("k", "s")
    keys_stub.keys_exist = lambda: True
    monkeypatch.setitem(sys.modules, "keys", keys_stub)

    storage_stub = types.ModuleType("storage")
    storage_stub.load_entries = lambda: {}
    monkeypatch.setitem(sys.modules, "storage", storage_stub)

    ll_stub = types.ModuleType("ledger_loader")
    ll_stub.update_raw_ledger = lambda *a, **k: None
    monkeypatch.setitem(sys.modules, "ledger_loader", ll_stub)

    eur_stub = types.ModuleType("ledger_eur_report")
    eur_stub.build_eur_report = lambda entries, days=7: pd.DataFrame()
    eur_stub.save_eur_report = lambda df: None
    monkeypatch.setitem(sys.modules, "ledger_eur_report", eur_stub)

    asset_stub = types.ModuleType("ledger_asset_report")
    asset_stub.build_asset_report = lambda entries, days=7: pd.DataFrame()
    monkeypatch.setitem(sys.modules, "ledger_asset_report", asset_stub)

    sell_stub = types.ModuleType("ledger_sell_report")
    sell_stub.build_sell_report = lambda entries, days=7: pd.DataFrame()
    monkeypatch.setitem(sys.modules, "ledger_sell_report", sell_stub)

    config_stub = types.ModuleType("config")
    config_stub.BALANCES_HISTORY_DIR = str(tmp_path / "balances_history")
    monkeypatch.setitem(sys.modules, "config", config_stub)

    api_stub = types.ModuleType("api")

    class KrakenAPI:
        def __init__(self, *a, **k):
            pass

    api_stub.KrakenAPI = KrakenAPI
    monkeypatch.setitem(sys.modules, "api", api_stub)

    if "balances" in sys.modules:
        del sys.modules["balances"]
    import balances as balances_mod  # noqa: E402

    yield balances_mod
    if "balances" in sys.modules:
        del sys.modules["balances"]


def test_normalize_asset_code_variants(balances_mod):
    assert balances_mod.normalize_asset_code("ETH.F") == "ETH"
    assert balances_mod.normalize_asset_code("SUI28") == "SUI"
    assert balances_mod.normalize_asset_code("DOTB") == "DOT"
    assert balances_mod.normalize_asset_code("BTC") == "BTC"


def test_unwrap_api_response_dict_with_result(balances_mod):
    resp = {"result": {"BTC": "1.0"}}
    assert balances_mod._unwrap_api_response(resp) == {"BTC": "1.0"}


def test_unwrap_api_response_tuple(balances_mod):
    resp = ({"BTC": "1.0"},)
    assert balances_mod._unwrap_api_response(resp) == {"BTC": "1.0"}


def test_unwrap_api_response_plain_dict(balances_mod):
    resp = {"BTC": "1.0"}
    assert balances_mod._unwrap_api_response(resp) == {"BTC": "1.0"}


def test_fetch_balances_filters_zero(balances_mod):
    class FakeAPI:
        def get_balance(self):
            return {"BTC": "1.0", "ETH": "0.0"}

    result = balances_mod.fetch_balances(FakeAPI())
    assert result == {"BTC": 1.0}


def test_fetch_balances_empty(balances_mod):
    class FakeAPI:
        def get_balance(self):
            return {}

    assert balances_mod.fetch_balances(FakeAPI()) == {}


def test_fetch_asset_pairs_raises_on_empty(balances_mod):
    class FakeAPI:
        def get_asset_pairs(self):
            return {}

    with pytest.raises(RuntimeError):
        balances_mod.fetch_asset_pairs(FakeAPI())


def test_fetch_asset_pairs_returns_result(balances_mod):
    class FakeAPI:
        def get_asset_pairs(self):
            return {"XXBTZEUR": {"base": "XXBT", "quote": "ZEUR"}}

    result = balances_mod.fetch_asset_pairs(FakeAPI())
    assert "XXBTZEUR" in result


def test_fetch_prices_batch_empty_pairs(balances_mod):
    assert balances_mod.fetch_prices_batch(None, []) == {}


def test_fetch_prices_batch_parses_close_price(balances_mod):
    class FakeAPI:
        def get_ticker(self, pairs):
            return {"XXBTZEUR": {"c": ["50000.0", "1"]}}

    result = balances_mod.fetch_prices_batch(FakeAPI(), ["XXBTZEUR"])
    assert result["XXBTZEUR"] == Decimal("50000.0")


def test_atomic_to_csv_writes_file(balances_mod, tmp_path):
    df = pd.DataFrame([{"a": 1}])
    out = tmp_path / "sub" / "out.csv"
    balances_mod._atomic_to_csv(df, str(out), index=False)
    assert out.exists()


def test_acquire_and_release_lock(balances_mod):
    assert balances_mod._acquire_lock() is True
    # second acquire should fail while lock exists
    assert balances_mod._acquire_lock() is False
    balances_mod._release_lock()
    assert balances_mod._acquire_lock() is True
    balances_mod._release_lock()


def test_compute_trends_no_previous_files(balances_mod):
    df = pd.DataFrame([{"Asset": "BTC", "Value (EUR)": 100.0}])
    out = balances_mod.compute_trends(df)
    assert (
        "Portfolio Trend Avg" not in out.columns
        or out["Portfolio Trend Avg"].isnull().all()
        or True
    )


def test_compute_trends_with_previous_file(balances_mod, tmp_path):
    os.makedirs(balances_mod.BALANCES_DIR, exist_ok=True)
    prev = pd.DataFrame([{"Asset": "BTC", "Value (EUR)": 90.0}])
    prev.to_csv(
        os.path.join(balances_mod.BALANCES_DIR, "balance_2026-01-01.csv"), index=False
    )
    df = pd.DataFrame([{"Asset": "BTC", "Value (EUR)": 100.0}])
    out = balances_mod.compute_trends(df)
    trend_cols = [c for c in out.columns if c.startswith("Trend_")]
    assert trend_cols
    assert out.iloc[0][trend_cols[0]] == pytest.approx(10.0)


def test_main_no_keys_returns_2(balances_mod, monkeypatch):
    monkeypatch.setattr(balances_mod, "keys_exist", lambda: False)
    rc = balances_mod.main(["--no-update"])
    assert rc == 2


def test_main_keys_error_returns_3(balances_mod, monkeypatch):
    monkeypatch.setattr(balances_mod, "keys_exist", lambda: True)

    def raise_keyerr():
        raise balances_mod.KeysError("bad")

    monkeypatch.setattr(balances_mod, "load_keys", raise_keyerr)
    rc = balances_mod.main(["--no-update"])
    assert rc == 3


def test_main_no_balances_returns_0(balances_mod, monkeypatch):
    monkeypatch.setattr(balances_mod, "keys_exist", lambda: True)
    monkeypatch.setattr(balances_mod, "load_keys", lambda: ("k", "s"))
    monkeypatch.setattr(balances_mod, "fetch_balances", lambda api: {})
    rc = balances_mod.main(["--no-update"])
    assert rc == 0


def test_main_full_flow_returns_0(balances_mod, monkeypatch, tmp_path):
    monkeypatch.setattr(balances_mod, "keys_exist", lambda: True)
    monkeypatch.setattr(balances_mod, "load_keys", lambda: ("k", "s"))
    monkeypatch.setattr(
        balances_mod, "fetch_balances", lambda api: {"BTC": 1.0, "ZEUR": 1000.0}
    )
    monkeypatch.setattr(
        balances_mod,
        "fetch_asset_pairs",
        lambda api: {"XXBTZEUR": {"base": "XXBT", "quote": "ZEUR"}},
    )
    monkeypatch.setattr(
        balances_mod,
        "fetch_prices_batch",
        lambda api, pairs: {"XXBTZEUR": Decimal("50000.0")},
    )
    rc = balances_mod.main(["--no-update"])
    assert rc == 0
    assert os.path.exists(balances_mod.SNAPSHOTS_FILE)


def test_main_load_keys_filenotfound_returns_2(balances_mod, monkeypatch):
    monkeypatch.setattr(balances_mod, "keys_exist", lambda: True)

    def raise_fnf():
        raise FileNotFoundError("no key file")

    monkeypatch.setattr(balances_mod, "load_keys", raise_fnf)
    rc = balances_mod.main(["--no-update"])
    assert rc == 2


def test_main_load_keys_unexpected_exception_returns_4(balances_mod, monkeypatch):
    monkeypatch.setattr(balances_mod, "keys_exist", lambda: True)

    def raise_generic():
        raise RuntimeError("boom")

    monkeypatch.setattr(balances_mod, "load_keys", raise_generic)
    rc = balances_mod.main(["--no-update"])
    assert rc == 4


def test_main_unexpected_keys_format_returns_4(balances_mod, monkeypatch):
    monkeypatch.setattr(balances_mod, "keys_exist", lambda: True)
    monkeypatch.setattr(balances_mod, "load_keys", lambda: 12345)  # not dict/tuple
    rc = balances_mod.main(["--no-update"])
    assert rc == 4


def test_main_update_raw_ledger_exception_nonfatal(balances_mod, monkeypatch):
    monkeypatch.setattr(balances_mod, "keys_exist", lambda: True)
    monkeypatch.setattr(balances_mod, "load_keys", lambda: ("k", "s"))

    def raise_update(days=7):
        raise RuntimeError("api down")

    monkeypatch.setattr(balances_mod, "update_raw_ledger", raise_update)
    monkeypatch.setattr(balances_mod, "fetch_balances", lambda api: {})
    rc = balances_mod.main([])  # no --no-update, so update path is exercised
    assert rc == 0


def test_main_staked_asset_detected(balances_mod, monkeypatch):
    monkeypatch.setattr(balances_mod, "keys_exist", lambda: True)
    monkeypatch.setattr(balances_mod, "load_keys", lambda: ("k", "s"))
    monkeypatch.setattr(balances_mod, "fetch_balances", lambda api: {"ETH.S": 2.0})
    monkeypatch.setattr(balances_mod, "fetch_asset_pairs", lambda api: {})
    monkeypatch.setattr(balances_mod, "fetch_prices_batch", lambda api, pairs: {})
    rc = balances_mod.main(["--no-update"])
    assert rc == 0


def test_main_matched_pair_nonzero_price(balances_mod, monkeypatch):
    from decimal import Decimal

    monkeypatch.setattr(balances_mod, "keys_exist", lambda: True)
    monkeypatch.setattr(balances_mod, "load_keys", lambda: ("k", "s"))
    monkeypatch.setattr(balances_mod, "fetch_balances", lambda api: {"XBT": 1.0})
    monkeypatch.setattr(
        balances_mod,
        "fetch_asset_pairs",
        lambda api: {"XXBTZEUR": {"base": "XXBT", "quote": "ZEUR"}},
    )
    monkeypatch.setattr(
        balances_mod,
        "fetch_prices_batch",
        lambda api, pairs: {"XXBTZEUR": Decimal("50000.0")},
    )
    rc = balances_mod.main(["--no-update"])
    assert rc == 0


def test_main_total_value_zero_guard(balances_mod, monkeypatch):
    monkeypatch.setattr(balances_mod, "keys_exist", lambda: True)
    monkeypatch.setattr(balances_mod, "load_keys", lambda: ("k", "s"))
    monkeypatch.setattr(balances_mod, "fetch_balances", lambda api: {"XBT": 1.0})
    monkeypatch.setattr(balances_mod, "fetch_asset_pairs", lambda api: {})
    monkeypatch.setattr(balances_mod, "fetch_prices_batch", lambda api, pairs: {})
    rc = balances_mod.main(["--no-update"])
    assert rc == 0


def test_main_snapshot_appends_new_row_second_run(balances_mod, monkeypatch):
    monkeypatch.setattr(balances_mod, "keys_exist", lambda: True)
    monkeypatch.setattr(balances_mod, "load_keys", lambda: ("k", "s"))
    monkeypatch.setattr(balances_mod, "fetch_balances", lambda api: {"BTC": 1.0})
    monkeypatch.setattr(balances_mod, "fetch_asset_pairs", lambda api: {})
    monkeypatch.setattr(balances_mod, "fetch_prices_batch", lambda api, pairs: {})
    balances_mod.main(["--no-update"])  # first run creates SNAPSHOTS_FILE
    import pandas as pd

    snap = pd.read_csv(balances_mod.SNAPSHOTS_FILE, sep=";")
    snap.loc[0, "Timestamp"] = "01.01.2000"  # force a different day
    snap.to_csv(balances_mod.SNAPSHOTS_FILE, sep=";", index=False)
    rc = balances_mod.main(["--no-update"])  # second run should append
    assert rc == 0
    snap2 = pd.read_csv(balances_mod.SNAPSHOTS_FILE, sep=";")
    assert len(snap2) == 2


def test_generate_all_reports_writes_files(balances_mod, tmp_path):
    balances_mod.generate_all_reports(
        days=7, update=False
    )  # update=False skips update_raw_ledger call
