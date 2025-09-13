# tests/test_balances.py
import shutil
import pandas as pd
import pytest
from unittest.mock import patch
import sys
import os
import argparse

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import balances


@pytest.fixture
def cleanup_balances_dir():
    if os.path.exists(balances.BALANCES_DIR):
        shutil.rmtree(balances.BALANCES_DIR)
    os.makedirs(balances.BALANCES_DIR)
    yield
    shutil.rmtree(balances.BALANCES_DIR)


def test_normalize_asset_code():
    assert balances.normalize_asset_code("XXBT.S") == "XXBT"
    assert balances.normalize_asset_code("ETH2.F") == "ETH"
    assert balances.normalize_asset_code("DOT123") == "DOT"


def test_compute_trends_adds_columns(cleanup_balances_dir):
    df_current = pd.DataFrame({"Asset": ["BTC"], "Value (EUR)": [1000.0]})
    # Create a previous CSV
    prev_df = pd.DataFrame({"Asset": ["BTC"], "Value (EUR)": [900.0]})
    prev_df.to_csv(
        os.path.join(balances.BALANCES_DIR, "balance_2023-01-01.csv"), index=False
    )

    result = balances.compute_trends(df_current.copy())
    assert "Trend_2023-01-01" in result.columns
    assert result["Trend_2023-01-01"].iloc[0] == 100.0
    assert "Portfolio Trend Avg" in result.columns


@patch("src.balances.KrakenAPI")
def test_fetch_balances_filters_zero(mock_api):
    mock_api.get_balance.return_value = {"BTC": "0.0", "ETH": "1.5"}
    result = balances.fetch_balances(mock_api)
    assert result == {"ETH": 1.5}


@patch("src.balances.KrakenAPI")
def test_fetch_asset_pairs_raises_on_empty(mock_api):
    mock_api.get_asset_pairs.return_value = {}
    with pytest.raises(RuntimeError):
        balances.fetch_asset_pairs(mock_api)


@patch("src.balances.KrakenAPI")
def test_fetch_prices_batch_parses_prices(mock_api):
    mock_api.get_ticker.return_value = {
        "XETHZEUR": {"c": ["2000.0"]},
        "XXBTZEUR": {"c": ["30000.0"]},
    }
    result = balances.fetch_prices_batch(mock_api, ["XETHZEUR", "XXBTZEUR"])
    assert result["XETHZEUR"] == balances.Decimal("2000.0")


# @patch("src.balances.update_raw_ledger")
@patch("balances.update_raw_ledger")
@patch("src.balances.storage.load_entries")
@patch("src.balances.ledger_eur_report.build_eur_report")
@patch("src.balances.ledger_eur_report.save_eur_report")
@patch("src.balances.ledger_asset_report.build_asset_report")
@patch("src.balances.ledger_sell_report.build_sell_report")
def test_generate_all_reports_runs_all(
    mock_sell, mock_asset, mock_save, mock_eur, mock_load, mock_update
):
    # ✅ Ensure balances_history directory exists
    os.makedirs(balances.BALANCES_DIR, exist_ok=True)

    mock_load.return_value = ["entry"]
    mock_eur.return_value = pd.DataFrame({"a": [1]})
    mock_asset.return_value = pd.DataFrame({"Asset": ["BTC"], "Value (EUR)": [1000]})
    mock_sell.return_value = pd.DataFrame({"Asset": ["BTC"], "Value (EUR)": [1000]})

    balances.generate_all_reports(days=1, update=True)
    mock_update.assert_called_once()
    mock_save.assert_called_once()


@patch("src.balances.load_keyfile", return_value=("key", "secret"))
@patch("src.balances.KrakenAPI")
@patch("src.balances.fetch_balances", return_value={"BTC": 1.0})
@patch(
    "src.balances.fetch_asset_pairs",
    return_value={"XXBTZEUR": {"base": "XXBT", "quote": "ZEUR"}},
)
@patch(
    "src.balances.fetch_prices_batch",
    return_value={"XXBTZEUR": balances.Decimal("30000.0")},
)
@patch(
    "argparse.ArgumentParser.parse_args",
    return_value=argparse.Namespace(quote="ZEUR", min_balance=0.001),
)
def test_main_creates_balance_and_snapshot(
    mock_args,
    mock_prices,
    mock_pairs,
    mock_balances,
    mock_api,
    mock_keyfile,
    cleanup_balances_dir,
):
    balances.main()
    # Check balance CSV created
    files = os.listdir(balances.BALANCES_DIR)
    assert any(f.startswith("balance_") for f in files)
    assert os.path.exists(balances.SNAPSHOTS_FILE)
    df_snap = pd.read_csv(balances.SNAPSHOTS_FILE, sep=";")
    assert not df_snap.empty
