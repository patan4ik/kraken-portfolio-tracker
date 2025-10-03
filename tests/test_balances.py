# tests/test_balances.py
import os
import tempfile
import shutil
from decimal import Decimal
from unittest.mock import MagicMock
import pandas as pd
import pytest
from src import balances
from src.balances import (
    compute_trends,
    normalize_asset_code,
    _unwrap_api_response,
    fetch_balances,
    fetch_asset_pairs,
    fetch_prices_batch,
    _atomic_to_csv,
    _write_json_atomic,
    _acquire_lock,
    _release_lock,
    main,
)


@pytest.fixture
def tmp_balances_dir(monkeypatch):
    tmp_dir = tempfile.mkdtemp()
    monkeypatch.setattr(balances, "BALANCES_DIR", tmp_dir)
    monkeypatch.setattr(
        balances, "SNAPSHOTS_FILE", os.path.join(tmp_dir, "portfolio_snapshots.csv")
    )
    yield tmp_dir
    shutil.rmtree(tmp_dir)


# ---------------- UTILS ---------------- #
def test_normalize_asset_code_basic():
    assert normalize_asset_code("BTC.S") == "BTC"
    assert normalize_asset_code("ETH.F") == "ETH"
    assert normalize_asset_code("USDT.B") == "USDT"
    assert normalize_asset_code("XRP123") == "XRP"
    assert normalize_asset_code("LONGASSETB") == "LONGASSET"
    assert normalize_asset_code("LTC") == "LTC"


def test_unwrap_api_response_various_shapes():
    data = _unwrap_api_response(({"result": {"a": 1}},))
    assert data == {"a": 1}

    data = _unwrap_api_response([{"result": {"b": 2}}])
    assert data == {"b": 2}

    data = _unwrap_api_response({"result": {"c": 3}})
    assert data == {"c": 3}

    data = _unwrap_api_response({"x": 1})
    assert data == {"x": 1}


def test_fetch_balances_filter_and_conversion():
    api_mock = MagicMock()
    api_mock.get_balance.return_value = {"BTC": "1.0", "ETH": "0.0"}
    result = fetch_balances(api_mock)
    assert result == {"BTC": 1.0}


def test_fetch_asset_pairs_success():
    api_mock = MagicMock()
    api_mock.get_asset_pairs.return_value = {
        "XXBTZEUR": {"base": "XXBT", "quote": "ZEUR"}
    }
    result = fetch_asset_pairs(api_mock)
    assert result["XXBTZEUR"]["base"] == "XXBT"


def test_fetch_prices_batch_converts_decimal():
    api_mock = MagicMock()
    api_mock.get_ticker.return_value = {
        "XXBTZEUR": {"c": ["12345.67"]},
        "XETHZEUR": {"c": ["2000.5"]},
    }
    result = fetch_prices_batch(api_mock, ["XXBTZEUR", "XETHZEUR"])
    assert result["XXBTZEUR"] == Decimal("12345.67")
    assert result["XETHZEUR"] == Decimal("2000.5")


# ---------------- TRENDS ---------------- #
def test_compute_trends_creates_columns(tmp_balances_dir):
    old_file = os.path.join(tmp_balances_dir, "balance_2000-01-01.csv")
    df_prev = pd.DataFrame({"Asset": ["BTC", "ETH"], "Value (EUR)": [1000, 2000]})
    df_prev.to_csv(old_file, index=False, encoding="utf-8")

    df_current = pd.DataFrame({"Asset": ["BTC", "ETH"], "Value (EUR)": [1100, 2100]})
    df_out = compute_trends(df_current)

    trend_cols = [c for c in df_out.columns if c.startswith("Trend_")]
    assert trend_cols
    assert df_out.loc[df_out["Asset"] == "BTC", trend_cols[0]].iloc[0] == 100
    assert df_out.loc[df_out["Asset"] == "ETH", trend_cols[0]].iloc[0] == 100
    assert "Portfolio Trend Avg" in df_out.columns
    assert df_out["Portfolio Trend Avg"].iloc[0] == 100


def test_compute_trends_with_no_previous_file(tmp_balances_dir):
    df = pd.DataFrame({"Asset": ["BTC"], "Value (EUR)": [1000]})
    result = compute_trends(df)
    assert (
        "Portfolio Trend Avg" not in result.columns
        or result["Portfolio Trend Avg"].iloc[0] == 0
    )


# ---------------- ATOMIC IO ---------------- #
def test_atomic_csv_write(tmp_balances_dir):
    path = os.path.join(tmp_balances_dir, "test.csv")
    df = pd.DataFrame({"a": [1, 2]})
    _atomic_to_csv(df, path, index=False)
    df2 = pd.read_csv(path)
    assert (df2["a"] == [1, 2]).all()


def test_atomic_json_write(tmp_balances_dir):
    path = os.path.join(tmp_balances_dir, "test.json")
    data = {"x": 1}
    _write_json_atomic(data, path)
    import json

    with open(path) as f:
        d = json.load(f)
    assert d == data


# ---------------- LOCK ---------------- #
def test_acquire_release_lock(tmp_balances_dir):
    locked = _acquire_lock()
    assert locked is True
    # повторное захватывание должно вернуть False
    locked2 = _acquire_lock()
    assert locked2 is False
    _release_lock()
    # после релиза можно снова захватить
    locked3 = _acquire_lock()
    assert locked3 is True
    _release_lock()


# ---------------- MAIN CLI ---------------- #
def test_main_no_keys(monkeypatch):
    # keys_exist вернет False
    monkeypatch.setattr(balances, "keys_exist", lambda: False)
    res = main(["--no-update"])
    assert res == 2


def test_main_with_keys(monkeypatch):
    api_mock = MagicMock()
    api_mock.get_balance.return_value = {"BTC": "1.0"}
    api_mock.get_asset_pairs.return_value = {
        "XXBTZEUR": {"base": "XXBT", "quote": "ZEUR"}
    }
    api_mock.get_ticker.return_value = {"XXBTZEUR": {"c": ["1000.0"]}}

    monkeypatch.setattr(balances, "keys_exist", lambda: True)
    monkeypatch.setattr(
        balances, "load_keys", lambda: {"api_key": "k", "api_secret": "s"}
    )
    monkeypatch.setattr(balances, "KrakenAPI", lambda k, s: api_mock)
    monkeypatch.setattr(balances, "_atomic_to_csv", lambda df, path, **kwargs: None)

    res = main(["--no-update"])
    assert res == 0
