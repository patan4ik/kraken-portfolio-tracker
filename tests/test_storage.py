# tests/test_storage.py
import os
import time
import json
import sqlite3
import sys

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import storage

now = int(time.time())


def setup_tmp(monkeypatch, tmp_path):
    monkeypatch.setattr("storage.BALANCES_DIR", str(tmp_path))
    monkeypatch.setattr("storage.RAW_LEDGER_FILE", str(tmp_path / "raw-ledger.json"))
    monkeypatch.setattr("storage.LEDGER_DB_FILE", str(tmp_path / "ledger.db"))


def test_save_entries_creates_json_and_db(tmp_path, monkeypatch):
    """
    Ensure save_entries writes both JSON and SQLite DB.
    """
    setup_tmp(monkeypatch, tmp_path)

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
    assert row == ("tx1", "ETH", 0.1)


def test_load_entries_cases(tmp_path, monkeypatch):
    """
    load_entries should handle missing, empty and corrupted JSON.
    """
    setup_tmp(monkeypatch, tmp_path)

    # Case 1: file not exists
    assert storage.load_entries() == {}

    # Case 2: empty file
    with open(storage.RAW_LEDGER_FILE, "w", encoding="utf-8") as f:
        f.write("")
    assert storage.load_entries() == {}

    # Case 3: corrupted JSON
    with open(storage.RAW_LEDGER_FILE, "w", encoding="utf-8") as f:
        f.write("{not-valid-json")
    assert storage.load_entries() == {}

    # Case 4: valid JSON
    entries = {"tx42": {"asset": "BTC", "amount": "0.5"}}
    with open(storage.RAW_LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f)
    result = storage.load_entries()
    assert "tx42" in result
    assert result["tx42"]["asset"] == "BTC"


def test_load_entries_from_db(tmp_path, monkeypatch):
    """
    load_entries_from_db should handle missing and existing DB.
    """
    setup_tmp(monkeypatch, tmp_path)

    # Case 1: no DB
    assert storage.load_entries_from_db() == {}

    # Case 2: valid DB with one entry
    entries = {
        "txdb1": {
            "refid": "r2",
            "time": now,
            "type": "trade",
            "asset": "ADA",
            "amount": 123,
            "fee": 0.0,
        }
    }
    storage.save_entries(entries)

    result = storage.load_entries_from_db()
    assert "txdb1" in result
    assert result["txdb1"]["asset"] == "ADA"


def test_save_entries_overwrites(tmp_path, monkeypatch):
    """
    save_entries should replace existing rows in DB.
    """
    setup_tmp(monkeypatch, tmp_path)

    first = {
        "tx_replace": {
            "refid": "r3",
            "time": now,
            "type": "trade",
            "asset": "LINK",
            "amount": 1,
            "fee": 0.01,
        }
    }
    storage.save_entries(first)

    second = {
        "tx_replace": {
            "refid": "r3",
            "time": now,
            "type": "trade",
            "asset": "LINK",
            "amount": 2,  # changed
            "fee": 0.02,
        }
    }
    storage.save_entries(second)

    result = storage.load_entries_from_db()
    assert result["tx_replace"]["amount"] == 2
