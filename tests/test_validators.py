"""Unit tests for src/validators.py — DB/schema/API-key validation helpers."""

import sqlite3
import sys
import types
import pytest

# --- stub the `keys` module BEFORE importing validators, since validators
# does `from keys import load_keys, KeysError` and keys.py may not exist
# in the test environment (it lives outside src/ in the real project).
keys_stub = types.ModuleType("keys")


class KeysError(Exception):
    pass


def load_keys():
    raise KeysError("stub not configured")


keys_stub.KeysError = KeysError
keys_stub.load_keys = load_keys
sys.modules.setdefault("keys", keys_stub)

import validators  # noqa: E402


# ---------------------------------------------------------------------------
# check_db_exists
# ---------------------------------------------------------------------------
def test_check_db_exists_true(tmp_path):
    db = tmp_path / "ledger.db"
    db.write_text("x")
    ok, msg = validators.check_db_exists(str(db))
    assert ok is True
    assert "found" in msg.lower()


def test_check_db_exists_missing_raises(tmp_path):
    missing = tmp_path / "nope.db"
    with pytest.raises(validators.DatabaseMissingError):
        validators.check_db_exists(str(missing))


# ---------------------------------------------------------------------------
# check_db_schema
# ---------------------------------------------------------------------------
def _make_db_with_table(path, table="ledger"):
    conn = sqlite3.connect(path)
    conn.execute(f"CREATE TABLE {table} (txid TEXT PRIMARY KEY)")
    conn.commit()
    conn.close()


def test_check_db_schema_ok(tmp_path):
    db = tmp_path / "ledger.db"
    _make_db_with_table(str(db))
    ok, msg = validators.check_db_schema(str(db))
    assert ok is True
    assert "ledger" in msg.lower()


def test_check_db_schema_missing_table_raises(tmp_path):
    db = tmp_path / "ledger.db"
    _make_db_with_table(str(db), table="other")
    with pytest.raises(validators.SchemaInvalidError):
        validators.check_db_schema(str(db))


def test_check_db_schema_bad_file_raises(tmp_path):
    bad = tmp_path / "not_a_db.db"
    bad.write_bytes(b"not a real sqlite file at all, garbage bytes 0000")
    with pytest.raises(validators.SchemaInvalidError):
        validators.check_db_schema(str(bad))


# ---------------------------------------------------------------------------
# check_api_key
# ---------------------------------------------------------------------------
def test_check_api_key_missing_file_raises(tmp_path):
    missing = tmp_path / "nope.key"
    with pytest.raises(validators.APIKeyError):
        validators.check_api_key(str(missing))


def test_check_api_key_plaintext_two_lines_ok(tmp_path):
    keyfile = tmp_path / "kraken.key"
    keyfile.write_text("APIKEYVALUE\nAPISECRETVALUE\n")
    ok, msg = validators.check_api_key(str(keyfile))
    assert ok is True
    assert "plaintext" in msg.lower()


def test_check_api_key_fallback_to_load_keys_tuple(tmp_path, monkeypatch):
    keyfile = tmp_path / "kraken.key"
    keyfile.write_text("onlyoneline")
    monkeypatch.setattr(validators, "load_keys", lambda: ("k", "s"))
    ok, msg = validators.check_api_key(str(keyfile))
    assert ok is True


def test_check_api_key_fallback_to_load_keys_dict(tmp_path, monkeypatch):
    keyfile = tmp_path / "kraken.key"
    keyfile.write_text("onlyoneline")
    monkeypatch.setattr(
        validators, "load_keys", lambda: {"api_key": "k", "api_secret": "s"}
    )
    ok, msg = validators.check_api_key(str(keyfile))
    assert ok is True


def test_check_api_key_fallback_invalid_format_raises(tmp_path, monkeypatch):
    keyfile = tmp_path / "kraken.key"
    keyfile.write_text("onlyoneline")
    monkeypatch.setattr(validators, "load_keys", lambda: {"nope": "bad"})
    with pytest.raises(validators.APIKeyError):
        validators.check_api_key(str(keyfile))


def test_check_api_key_fallback_keyerror_raises(tmp_path, monkeypatch):
    keyfile = tmp_path / "kraken.key"
    keyfile.write_text("onlyoneline")

    def raise_keyserror():
        raise validators.KeysError("bad master key")

    monkeypatch.setattr(validators, "load_keys", raise_keyserror)
    with pytest.raises(validators.APIKeyError):
        validators.check_api_key(str(keyfile))


# ---------------------------------------------------------------------------
# check_api_keys
# ---------------------------------------------------------------------------
def test_check_api_keys_tuple(monkeypatch):
    monkeypatch.setattr(validators, "load_keys", lambda: ("k", "s"))
    k, s = validators.check_api_keys()
    assert (k, s) == ("k", "s")


def test_check_api_keys_dict(monkeypatch):
    monkeypatch.setattr(validators, "load_keys", lambda: {"key": "k", "secret": "s"})
    k, s = validators.check_api_keys()
    assert (k, s) == ("k", "s")


def test_check_api_keys_invalid_format_raises(monkeypatch):
    monkeypatch.setattr(validators, "load_keys", lambda: {"bad": "x"})
    with pytest.raises(validators.APIKeyError):
        validators.check_api_keys()


def test_check_api_keys_keyserror_raises(monkeypatch):
    def raise_keyserror():
        raise validators.KeysError("nope")

    monkeypatch.setattr(validators, "load_keys", raise_keyserror)
    with pytest.raises(validators.APIKeyError):
        validators.check_api_keys()


# ---------------------------------------------------------------------------
# validate_for_update
# ---------------------------------------------------------------------------
def test_validate_for_update_full_success(tmp_path, monkeypatch):
    db = tmp_path / "ledger.db"
    _make_db_with_table(str(db))
    monkeypatch.setattr(validators, "load_keys", lambda: ("k", "s"))
    validators.validate_for_update(str(db))  # should not raise


def test_validate_for_update_missing_db_raises(tmp_path):
    with pytest.raises(validators.DatabaseMissingError):
        validators.validate_for_update(str(tmp_path / "nope.db"))


# ---------------------------------------------------------------------------
# db_row_count / validate_after_update
# ---------------------------------------------------------------------------
def test_db_row_count_missing_file_returns_zero(tmp_path):
    assert validators.db_row_count(str(tmp_path / "nope.db")) == 0


def test_db_row_count_no_ledger_table_returns_zero(tmp_path):
    db = tmp_path / "ledger.db"
    _make_db_with_table(str(db), table="other")
    assert validators.db_row_count(str(db)) == 0


def test_db_row_count_counts_rows(tmp_path):
    db = tmp_path / "ledger.db"
    _make_db_with_table(str(db))
    conn = sqlite3.connect(str(db))
    conn.execute("INSERT INTO ledger (txid) VALUES ('a')")
    conn.execute("INSERT INTO ledger (txid) VALUES ('b')")
    conn.commit()
    conn.close()
    assert validators.db_row_count(str(db)) == 2


def test_validate_after_update_pass(tmp_path):
    db = tmp_path / "ledger.db"
    _make_db_with_table(str(db))
    conn = sqlite3.connect(str(db))
    conn.execute("INSERT INTO ledger (txid) VALUES ('a')")
    conn.commit()
    conn.close()
    assert validators.validate_after_update(str(db), expected_min_rows=1) is True


def test_validate_after_update_fail(tmp_path):
    db = tmp_path / "ledger.db"
    _make_db_with_table(str(db))
    assert validators.validate_after_update(str(db), expected_min_rows=5) is False
