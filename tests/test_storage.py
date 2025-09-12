# test_storage.py
import os
import time
import json
import sqlite3
import storage

now = int(time.time())


def test_save_entries_creates_json_and_db(tmp_path, monkeypatch):
    """
    Ensure save_entries writes both JSON and SQLite DB.
    """
    monkeypatch.setattr("storage.BALANCES_DIR", str(tmp_path))
    monkeypatch.setattr("storage.RAW_LEDGER_FILE", str(tmp_path / "raw-ledger.json"))
    monkeypatch.setattr("storage.LEDGER_DB_FILE", str(tmp_path / "ledger.db"))

    # Clean old files if exist
    if os.path.exists(storage.RAW_LEDGER_FILE):
        os.remove(storage.RAW_LEDGER_FILE)
    if os.path.exists(storage.LEDGER_DB_FILE):
        os.remove(storage.LEDGER_DB_FILE)

    entries = {
        "tx1": {
            "refid": "r1",
            "time": now,
            "type": "trade",
            "asset": "ETH",
            "amount": 0.1,
            "fee": 0.01,
        }
    }

    storage.save_entries(entries)

    # JSON check
    assert os.path.exists(storage.RAW_LEDGER_FILE)
    with open(storage.RAW_LEDGER_FILE, "r", encoding="utf-8") as f:
        data = json.load(f)
    assert "tx1" in data

    # SQLite check
    assert os.path.exists(storage.LEDGER_DB_FILE)
    conn = sqlite3.connect(storage.LEDGER_DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT txid, asset, amount FROM ledger WHERE txid=?", ("tx1",))
    row = cur.fetchone()
    conn.close()
    assert row is not None
    assert row[0] == "tx1"
    assert row[1] == "ETH"
    assert row[2] == 0.1
