# tests/test_balances.py
import os
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)

import tempfile
import shutil
import pandas as pd
import pytest
from decimal import Decimal
from unittest.mock import MagicMock, patch

# Import functions and constants from balances.py
from balances import (
    normalize_asset_code,
    fetch_balances,
    fetch_asset_pairs,
    fetch_prices_batch,
    _atomic_to_csv,
    compute_trends,
)


# ----------------------------
# Test _unwrap_api_response
# ----------------------------
@pytest.mark.parametrize(
    "resp,expected",
    [
        ({"result": {"XXBT": "1.0"}}, {"XXBT": "1.0"}),
        (({"XXBT": "1.0"},), {"XXBT": "1.0"}),
        # Function does not skip errors, it just returns the first element
        (({"error": "fail"}, {"XXBT": "1.0"}), {"error": "fail"}),
        ([{"XXBT": "1.0"}, {"ZZZ": "2"}], {"XXBT": "1.0"}),
        ({"XXBT": "1.0"}, {"XXBT": "1.0"}),
        (None, None),
    ],
)
def test_unwrap_api_response(resp, expected):
    from src.balances import _unwrap_api_response as unwrap

    result = unwrap(resp)
    assert result == expected


# ----------------------------
# Test normalize_asset_code
# ----------------------------
@pytest.mark.parametrize(
    "asset,expected",
    [
        ("BTC.S", "BTC"),
        ("ETH.F", "ETH"),
        ("XRP.B", "XRP"),
        ("DOGE1", "DOGE"),
        ("LTCB", "LTC"),
        ("ADA", "ADA"),
        ("SOLF2", "SOL"),
        ("BNB", "BNB"),
    ],
)
def test_normalize_asset_code(asset, expected):
    assert normalize_asset_code(asset) == expected


# ----------------------------
# Test fetch_balances
# ----------------------------
def test_fetch_balances_dict():
    mock_api = MagicMock()
    mock_api.get_balance.return_value = {"XXBT": "1.5", "ZEUR": "0"}
    result = fetch_balances(mock_api)
    assert result == {"XXBT": 1.5}


# ----------------------------
# Test fetch_asset_pairs
# ----------------------------
def test_fetch_asset_pairs_success():
    mock_api = MagicMock()
    mock_api.get_asset_pairs.return_value = {
        "XXBTZEUR": {"base": "XXBT", "quote": "ZEUR"}
    }
    result = fetch_asset_pairs(mock_api)
    assert result == {"XXBTZEUR": {"base": "XXBT", "quote": "ZEUR"}}


def test_fetch_asset_pairs_empty_raises():
    mock_api = MagicMock()
    mock_api.get_asset_pairs.return_value = {}
    with pytest.raises(RuntimeError):
        fetch_asset_pairs(mock_api)


# ----------------------------
# Test fetch_prices_batch
# ----------------------------
def test_fetch_prices_batch():
    mock_api = MagicMock()
    mock_api.get_ticker.return_value = {
        "XXBTZEUR": {"c": ["30000.0", "1", "1.0"]},
        "ETHZEUR": {"c": ["2000.0", "1", "1.0"]},
    }
    pairs = ["XXBTZEUR", "ETHZEUR"]
    result = fetch_prices_batch(mock_api, pairs)
    assert result["XXBTZEUR"] == Decimal("30000.0")
    assert result["ETHZEUR"] == Decimal("2000.0")


# ----------------------------
# Test _atomic_to_csv
# ----------------------------
def test_atomic_to_csv_creates_file():
    df = pd.DataFrame({"A": [1, 2], "B": [3, 4]})
    tmp_dir = tempfile.mkdtemp()
    try:
        out_file = os.path.join(tmp_dir, "test.csv")
        _atomic_to_csv(df, out_file, index=False)
        df2 = pd.read_csv(out_file)
        assert list(df2.columns) == ["A", "B"]
        assert df2.shape == (2, 2)
    finally:
        shutil.rmtree(tmp_dir)


# ----------------------------
# Test compute_trends
# ----------------------------
def test_compute_trends_creates_trend_column():
    tmp_dir = tempfile.mkdtemp()
    try:
        # patch BALANCES_DIR to tmp_dir
        with patch("src.balances.BALANCES_DIR", tmp_dir):
            # Create previous CSV
            prev_df = pd.DataFrame(
                {"Asset": ["BTC", "ETH"], "Value (EUR)": [1000, 2000]}
            )
            prev_file = os.path.join(tmp_dir, "balance_2025-01-01.csv")
            prev_df.to_csv(prev_file, index=False)

            # Current df
            df = pd.DataFrame({"Asset": ["BTC", "ETH"], "Value (EUR)": [1100, 2100]})
            df_out = compute_trends(df)

            # Detect trend column automatically (since it's based on datetime.now)
            trend_cols = [c for c in df_out.columns if c.startswith("Trend_")]
            assert trend_cols, "No trend column created"
            trend_col = trend_cols[0]

            # Check values exist
            assert not df_out[trend_col].isna().all()
            # Portfolio Trend Avg column should exist
            assert "Portfolio Trend Avg" in df_out.columns
    finally:
        shutil.rmtree(tmp_dir)
