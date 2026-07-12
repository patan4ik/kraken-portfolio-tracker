"""Unit tests for storage.py — atomic JSON/SQLite persistence layer."""

import json
import os
import sqlite3
import sys

import pytest


@pytest.fixture()
def storage_mod(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    if "storage" in sys.modules:
        del sys.modules["storage"]
    import storage as storage_mod  # noqa: E402

    yield storage_mod
    if "storage" in sys.modules:
        del sys.modules["storage"]


def _entry(
    asset="BTC", amount=1.0, fee=0.0, refid="r1", type_="trade", time_=1700000000.0
):
    return {
        "asset": asset,
        "amount": amount,
        "fee": fee,
        "refid": refid,
        "type": type_,
        "time": time_,
    }


def test_init_db_creates_table(storage_mod):
    storage_mod.init_db()
    conn = sqlite3.connect(storage_mod.LEDGER_DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='ledger'")
    assert cur.fetchone() is not None
    conn.close()


def test_save_entries_writes_json_and_db(storage_mod):
    entries = {"t1": _entry()}
    storage_mod.save_entries(entries)
    assert os.path.exists(storage_mod.RAW_LEDGER_FILE)
    with open(storage_mod.RAW_LEDGER_FILE) as f:
        data = json.load(f)
    assert "t1" in data
    loaded = storage_mod.load_entries_from_db()
    assert "t1" in loaded


def test_save_entries_empty_skips(storage_mod):
    storage_mod.save_entries({})
    assert not os.path.exists(storage_mod.RAW_LEDGER_FILE)


def test_save_entries_creates_backup_on_second_write(storage_mod):
    storage_mod.save_entries({"t1": _entry()})
    storage_mod.save_entries({"t2": _entry(refid="r2")})
    backups = [f for f in os.listdir(storage_mod.BALANCES_DIR) if ".bak." in f]
    assert len(backups) >= 1


def test_save_update_entries_counts_new(storage_mod):
    storage_mod.init_db()
    n1 = storage_mod.save_update_entries({"t1": _entry()})
    assert n1 == 1
    n2 = storage_mod.save_update_entries(
        {"t1": _entry(amount=2.0), "t2": _entry(refid="r2")}
    )
    assert n2 == 1  # t1 already existed, only t2 is new


def test_save_update_entries_empty_returns_zero(storage_mod):
    assert storage_mod.save_update_entries({}) == 0


def test_load_entries_from_db_missing_file_returns_empty(storage_mod):
    assert storage_mod.load_entries_from_db() == {}


def test_load_entries_from_db_adds_date_field(storage_mod):
    storage_mod.save_entries({"t1": _entry(time_=1700000000.0)})
    loaded = storage_mod.load_entries_from_db()
    assert "date" in loaded["t1"]


def test_load_entries_missing_file_returns_empty(storage_mod):
    assert storage_mod.load_entries() == {}


def test_load_entries_empty_file_returns_empty(storage_mod):
    storage_mod._ensure_dir()
    open(storage_mod.RAW_LEDGER_FILE, "w").close()
    assert storage_mod.load_entries() == {}


def test_load_entries_invalid_json_returns_empty(storage_mod):
    storage_mod._ensure_dir()
    with open(storage_mod.RAW_LEDGER_FILE, "w") as f:
        f.write("{not valid json")
    assert storage_mod.load_entries() == {}


def test_load_entries_valid_json_roundtrip(storage_mod):
    storage_mod.save_entries({"t1": _entry()})
    loaded = storage_mod.load_entries()
    assert "t1" in loaded


def test_init_db_adds_missing_date_iso_column(storage_mod):
    storage_mod._ensure_dir()
    conn = sqlite3.connect(storage_mod.LEDGER_DB_FILE)
    conn.execute(
        "CREATE TABLE ledger (txid TEXT PRIMARY KEY, refid TEXT, time REAL, type TEXT, asset TEXT, amount REAL, fee REAL, data TEXT)"
    )
    conn.commit()
    conn.close()
    storage_mod.init_db()
    conn = sqlite3.connect(storage_mod.LEDGER_DB_FILE)
    cur = conn.cursor()
    cur.execute("PRAGMA table_info(ledger)")
    cols = [r[1] for r in cur.fetchall()]
    conn.close()
    assert "date_iso" in cols
