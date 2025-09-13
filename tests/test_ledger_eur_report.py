# tests/test_ledger_eur_report.py
import pandas as pd
import sys
import time
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import storage
from ledger_eur_report import build_eur_report


now = int(time.time())


def test_build_eur_report(tmp_path, monkeypatch):
    """
    Unit test for build_eur_report:
    - Saves dummy ledger entries via storage
    - Loads them back
    - Ensures the EUR report CSV is generated correctly
    """
    monkeypatch.setattr("storage.BALANCES_DIR", str(tmp_path))
    monkeypatch.setattr("storage.RAW_LEDGER_FILE", str(tmp_path / "raw-ledger.json"))
    monkeypatch.setattr("storage.LEDGER_DB_FILE", str(tmp_path / "ledger.db"))
    monkeypatch.setattr(
        "ledger_eur_report.LEDGER_EUR_FILE", str(tmp_path / "ledger_eur_report.csv")
    )

    raw_data = {
        "tx1": {
            "refid": "r1",
            "time": now,
            "type": "receive",
            "asset": "ETH",
            "amount": "0.1",
            "fee": "0",
        },
        "tx2": {
            "refid": "r1",
            "time": now,
            "type": "spend",
            "asset": "ZEUR",
            "amount": "-1.98",
            "fee": "0.02",
        },
    }

    # Save to JSON + DB
    storage.save_entries(raw_data)

    # Load entries
    entries = storage.load_entries()

    # Build report
    df = build_eur_report(entries)
    assert not df.empty
    assert isinstance(df, pd.DataFrame)
    assert "ETH" in df.columns
    assert "Total Spent EUR" in df.columns
    assert "Total Fee" in df.columns
    assert df.iloc[0]["Total Spent EUR"] == 1.98
    assert df.iloc[0]["Total Fee"] == 0.02
