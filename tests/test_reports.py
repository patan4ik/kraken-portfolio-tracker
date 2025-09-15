# tests/test_reports.py
import time
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
    """
    Create ledger entries with timestamps relative to "now" so tests are
    deterministic and don't depend on fixed epoch values.
    We'll create:
      - R1: buy 2 SOL for 100 ZEUR
      - R2: buy 1 SOL for 50 ZEUR
      - R3: sell 1 SOL for 60 ZEUR (fee 0.1)
    """
    now = int(time.time())
    # choose times within last few days (within default 10-day window)
    t1 = now - 2 * 86400  # 2 days ago
    t2 = now - 1 * 86400  # 1 day ago
    t3 = now - 1 * 86400  # 1 day ago

    return {
        # Buy 2 SOL for 100 ZEUR (ref R1)
        "tx1": {
            "time": t1,
            "type": "trade",
            "asset": "ZEUR",
            "amount": "-100.0",
            "fee": "0.5",
            "refid": "R1",
        },
        "tx2": {
            "time": t1,
            "type": "trade",
            "asset": "SOL",
            "amount": "2.0",
            "fee": "0.0",
            "refid": "R1",
        },
        # Buy 1 SOL for 50 ZEUR (ref R2)
        "tx3": {
            "time": t2,
            "type": "trade",
            "asset": "ZEUR",
            "amount": "-50.0",
            "fee": "0.2",
            "refid": "R2",
        },
        "tx4": {
            "time": t2,
            "type": "trade",
            "asset": "SOL",
            "amount": "1.0",
            "fee": "0.0",
            "refid": "R2",
        },
        # Sell 1 SOL for 60 ZEUR (ref R3)
        "tx5": {
            "time": t3,
            "type": "trade",
            "asset": "SOL",
            "amount": "-1.0",
            "fee": "0.1",
            "refid": "R3",
        },
        "tx6": {
            "time": t3,
            "type": "trade",
            "asset": "ZEUR",
            "amount": "60.0",
            "fee": "0.0",
            "refid": "R3",
        },
    }


def test_all_reports(monkeypatch):
    fake_entries = make_fake_entries()
    # patch DB loader so reports use our fake entries
    monkeypatch.setattr(storage, "load_entries_from_db", lambda: fake_entries)

    # EUR report
    df_eur = ledger_eur_report.update_eur_report(days=10, write_csv=False)
    assert isinstance(df_eur, pd.DataFrame)
    # If the report builder filtered everything out it will be empty,
    # but for our data we expect rows.
    assert not df_eur.empty
    assert "SOL" in df_eur.columns
    assert (df_eur["Total Spent EUR"] > 0).any()

    # Asset report
    df_asset = ledger_asset_report.update_asset_report(days=10, write_csv=False)
    assert isinstance(df_asset, pd.DataFrame)
    assert not df_asset.empty
    assert "SOL" in df_asset.columns
    assert (df_asset["SOL"] > 0).any()

    # Sell report
    df_sell = ledger_sell_report.update_sell_report(days=10, write_csv=False)
    assert isinstance(df_sell, pd.DataFrame)
    assert not df_sell.empty
    assert "Total EUR" in df_sell.columns
    assert (df_sell["Total EUR"] > 0).any()
