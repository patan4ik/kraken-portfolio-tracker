# test_ledger_eur_report.py
import pandas as pd
import time
from ledger_eur_report import build_eur_report
from ledger_loader import save_progress, load_raw_ledger

now = int(time.time())


def test_build_eur_report(tmp_path, monkeypatch):
    monkeypatch.setattr(
        "ledger_loader.RAW_LEDGER_FILE", str(tmp_path / "raw-ledger.json")
    )
    monkeypatch.setattr(
        "ledger_eur_report.LEDGER_EUR_FILE", str(tmp_path / "ledger_eur_report.csv")
    )

    raw_data = {
        "tx1": {
            "refid": "r1",
            "time": now,
            "type": "receive",  # crypto received
            "asset": "ETH",
            "amount": "0.1",
            "fee": "0",
        },
        "tx2": {
            "refid": "r1",
            "time": now,
            "type": "spend",  # fiat spent
            "asset": "ZEUR",
            "amount": "-1.98",
            "fee": "0.02",
        },
    }

    save_progress(raw_data)

    entries = load_raw_ledger()
    assert entries, "No entries loaded from raw ledger"

    df = build_eur_report(entries, days=9999)  # if needed
    assert not df.empty
    assert isinstance(df, pd.DataFrame)
    assert "ETH" in df.columns
    assert "Total Spent EUR" in df.columns
    assert df.iloc[0]["Total Spent EUR"] == 1.98
    assert df.iloc[0]["Total Fee"] == 0.02
