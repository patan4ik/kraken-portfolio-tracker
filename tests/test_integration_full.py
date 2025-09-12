# test_integration_full.py
import os
import pandas as pd
import storage
import time
import ledger_eur_report

now = int(time.time())


def test_full_cycle(tmp_path, monkeypatch):
    """
    Full integration test:
    1. Save dummy ledger entries (ZEUR spend + ETH receive).
    2. Load them back.
    3. Run update_eur_report (which writes CSV).
    4. Ensure CSV exists and has required columns.
    """
    monkeypatch.setattr("storage.BALANCES_DIR", str(tmp_path))
    monkeypatch.setattr("storage.RAW_LEDGER_FILE", str(tmp_path / "raw-ledger.json"))
    monkeypatch.setattr("storage.LEDGER_DB_FILE", str(tmp_path / "ledger.db"))
    monkeypatch.setattr(
        "ledger_eur_report.LEDGER_EUR_FILE", str(tmp_path / "ledger_eur_report.csv")
    )

    entries = {
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

    # Save ledger entries to both JSON + SQLite
    storage.save_entries(entries)
    loaded = storage.load_entries()

    # Run report generator (writes CSV)
    df = ledger_eur_report.build_eur_report(loaded)
    df.to_csv(ledger_eur_report.LEDGER_EUR_FILE, sep=";", index=False, encoding="utf-8")

    # Check DataFrame
    assert isinstance(df, pd.DataFrame)
    assert "Total Spent EUR" in df.columns
    assert "Total Fee" in df.columns

    # Check CSV written
    assert os.path.exists(ledger_eur_report.LEDGER_EUR_FILE)
    csv_df = pd.read_csv(ledger_eur_report.LEDGER_EUR_FILE, sep=";")
    assert "Total Spent EUR" in csv_df.columns
    assert abs(csv_df.iloc[0]["Total Spent EUR"] - 1.98) < 1e-6
