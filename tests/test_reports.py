# tests/test_reports.py
import pandas as pd
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import storage
import ledger_eur_report
import ledger_asset_report
import ledger_sell_report


def make_fake_entries():
    """Fake ledger entries for tests (one buy, one sell)."""
    return {
        "tx1": {
            "time": 1757000000,
            "type": "trade",
            "asset": "ZEUR",
            "amount": "-100.0",
            "fee": "0.5",
            "refid": "R1",
        },
        "tx2": {
            "time": 1757000000,
            "type": "trade",
            "asset": "SOL",
            "amount": "2.0",
            "fee": "0.0",
            "refid": "R1",
        },
        "tx3": {
            "time": 1757100000,
            "type": "trade",
            "asset": "SOL",
            "amount": "-1.0",
            "fee": "0.2",
            "refid": "R2",
        },
        "tx4": {
            "time": 1757100000,
            "type": "trade",
            "asset": "ZEUR",
            "amount": "50.0",
            "fee": "0.0",
            "refid": "R2",
        },
    }


def test_all_reports(monkeypatch):
    fake_entries = make_fake_entries()
    monkeypatch.setattr(storage, "load_entries_from_db", lambda: fake_entries)

    # EUR report
    df_eur = ledger_eur_report.update_eur_report(days=10, write_csv=False)
    assert isinstance(df_eur, pd.DataFrame)
    assert "SOL" in df_eur.columns
    assert (df_eur["Total Spent EUR"] > 0).any()

    # Asset report
    df_asset = ledger_asset_report.update_asset_report(days=10, write_csv=False)
    assert isinstance(df_asset, pd.DataFrame)
    assert "SOL" in df_asset.columns
    assert (df_asset["SOL"] > 0).any()

    # Sell report
    df_sell = ledger_sell_report.update_sell_report(days=10, write_csv=False)
    assert isinstance(df_sell, pd.DataFrame)
    assert "Total EUR" in df_sell.columns
    assert (df_sell["Total EUR"] > 0).any()
