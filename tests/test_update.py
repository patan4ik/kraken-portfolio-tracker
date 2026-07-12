"""Unit tests for update.py — date parsing + DB range helpers (pure-logic slices,
not the full API-dependent pipeline, which needs live Kraken creds by design)."""

import sqlite3
from datetime import date, timedelta

import pytest
import update  # noqa: E402  (resolved via tests/conftest.py adding ROOT to sys.path)
import validators  # noqa: E402  (real module in src/, added to sys.path by conftest.py)


# ---------------------------------------------------------------------------
# parse_relative_or_date
# ---------------------------------------------------------------------------
def test_parse_relative_days():
    today = date.today()
    result = update.parse_relative_or_date("5d")
    assert result == today - timedelta(days=5)


def test_parse_relative_months():
    today = date.today()
    result = update.parse_relative_or_date("2m")
    assert result == today - timedelta(days=60)


def test_parse_absolute_iso_date():
    assert update.parse_relative_or_date("2026-01-15") == date(2026, 1, 15)


def test_parse_absolute_dotted_date():
    assert update.parse_relative_or_date("15.01.2026") == date(2026, 1, 15)


def test_parse_empty_raises():
    with pytest.raises(ValueError):
        update.parse_relative_or_date("")


def test_parse_unsupported_format_raises():
    with pytest.raises(ValueError):
        update.parse_relative_or_date("not-a-date")


# ---------------------------------------------------------------------------
# get_db_date_range
# ---------------------------------------------------------------------------
def test_get_db_date_range_missing_file(tmp_path):
    result = update.get_db_date_range(str(tmp_path / "nope.db"))
    assert result == (None, None)


def test_get_db_date_range_no_ledger_table(tmp_path):
    db = tmp_path / "ledger.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE other (x TEXT)")
    conn.commit()
    conn.close()
    assert update.get_db_date_range(str(db)) == (None, None)


def test_get_db_date_range_returns_min_max(tmp_path):
    db = tmp_path / "ledger.db"
    conn = sqlite3.connect(str(db))
    conn.execute("CREATE TABLE ledger (date_iso TEXT)")
    conn.execute("INSERT INTO ledger VALUES ('2026-01-01T00:00:00+00:00')")
    conn.execute("INSERT INTO ledger VALUES ('2026-01-10T00:00:00+00:00')")
    conn.commit()
    conn.close()
    lo, hi = update.get_db_date_range(str(db))
    assert lo == date(2026, 1, 1)
    assert hi == date(2026, 1, 10)


def test_main_invalid_fromdate_returns_2(capsys):
    rc = update.main(["--fromdate", "garbage"])
    assert rc == 2


def test_main_fromdate_after_todate_returns_2():
    rc = update.main(["--fromdate", "2026-02-01", "--todate", "2026-01-01"])
    assert rc == 2


def test_main_db_missing_returns_1(monkeypatch):
    def raise_missing(db_path):
        raise validators.DatabaseMissingError("missing")

    monkeypatch.setattr(update, "validate_for_update", raise_missing)
    rc = update.main(["--fromdate", "5d", "--dry-run"])
    assert rc == 1


def test_main_schema_invalid_returns_1(monkeypatch):
    def raise_schema(db_path):
        raise validators.SchemaInvalidError("bad schema")

    monkeypatch.setattr(update, "validate_for_update", raise_schema)
    rc = update.main(["--fromdate", "5d", "--dry-run"])
    assert rc == 1


def test_main_api_key_error_returns_1(monkeypatch):
    def raise_apikey(db_path):
        raise validators.APIKeyError("bad key")

    monkeypatch.setattr(update, "validate_for_update", raise_apikey)
    rc = update.main(["--fromdate", "5d", "--dry-run"])
    assert rc == 1
