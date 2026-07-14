"""Unit tests for update.py — date parsing + DB range helpers (pure-logic slices,
not the full API-dependent pipeline, which needs live Kraken creds by design)."""

import sqlite3
from datetime import date, timedelta

import pytest
import update  # noqa: E402  (resolved via tests/conftest.py adding ROOT to sys.path)
import validators  # noqa: E402  (real module in src/, added to sys.path by conftest.py)
import pandas as pd


def test_run_portfolio_summary_success(monkeypatch):
    monkeypatch.setattr(update.balances, "main", lambda argv=None: 0)
    monkeypatch.setattr(
        update.portfolio_summary_report,
        "update_summary_report",
        lambda write_csv=True: pd.DataFrame({"asset": ["BTC"]}),
    )
    monkeypatch.setattr(update.portfolio_summary, "update_summary", lambda: {"BTC": {}})
    monkeypatch.setattr(
        update.balance_reconciliation,
        "run_reconciliation",
        lambda raw, write_csv=True: None,
    )
    update._run_portfolio_summary()  # should not raise


def test_run_portfolio_summary_empty_result_logs_warning(monkeypatch, caplog):
    monkeypatch.setattr(update.balances, "main", lambda argv=None: 0)
    monkeypatch.setattr(
        update.portfolio_summary_report,
        "update_summary_report",
        lambda write_csv=True: pd.DataFrame(),
    )
    update._run_portfolio_summary()
    assert "no rows" in caplog.text.lower()


def test_run_portfolio_summary_balances_exception_nonfatal(monkeypatch):
    def boom(argv=None):
        raise RuntimeError("boom")

    monkeypatch.setattr(update.balances, "main", boom)
    monkeypatch.setattr(
        update.portfolio_summary_report,
        "update_summary_report",
        lambda write_csv=True: pd.DataFrame({"asset": ["BTC"]}),
    )
    monkeypatch.setattr(update.portfolio_summary, "update_summary", lambda: {})
    monkeypatch.setattr(
        update.balance_reconciliation,
        "run_reconciliation",
        lambda raw, write_csv=True: None,
    )
    update._run_portfolio_summary()  # non-fatal, must not propagate


def _make_ledger_db(path, rows):
    conn = sqlite3.connect(str(path))
    conn.execute("CREATE TABLE ledger (date_iso TEXT)")
    for iso in rows:
        conn.execute("INSERT INTO ledger VALUES (?)", (iso,))
    conn.commit()
    conn.close()


def test_main_already_up_to_date_runs_summary(tmp_path, monkeypatch):
    db = tmp_path / "ledger.db"
    _make_ledger_db(db, ["2026-01-01T00:00:00+00:00", "2026-07-14T00:00:00+00:00"])
    monkeypatch.setattr(update.storage, "LEDGER_DB_FILE", str(db))
    monkeypatch.setattr(update, "validate_for_update", lambda path: None)
    called = {}
    monkeypatch.setattr(
        update, "_run_portfolio_summary", lambda: called.setdefault("ran", True)
    )
    rc = update.main(["--fromdate", "2026-01-01", "--todate", "2026-07-14"])
    assert rc == 0 and called.get("ran") is True


def test_main_no_summary_flag_skips_summary(tmp_path, monkeypatch):
    db = tmp_path / "ledger.db"
    _make_ledger_db(db, ["2026-01-01T00:00:00+00:00", "2026-07-14T00:00:00+00:00"])
    monkeypatch.setattr(update.storage, "LEDGER_DB_FILE", str(db))
    monkeypatch.setattr(update, "validate_for_update", lambda path: None)
    called = {}
    monkeypatch.setattr(
        update, "_run_portfolio_summary", lambda: called.setdefault("ran", True)
    )
    rc = update.main(
        ["--fromdate", "2026-01-01", "--todate", "2026-07-14", "--no-summary"]
    )
    assert rc == 0 and "ran" not in called


def test_main_fetches_filters_and_persists(tmp_path, monkeypatch):
    db = tmp_path / "ledger.db"
    _make_ledger_db(db, ["2026-06-01T00:00:00+00:00", "2026-06-10T00:00:00+00:00"])
    monkeypatch.setattr(update.storage, "LEDGER_DB_FILE", str(db))
    monkeypatch.setattr(update, "validate_for_update", lambda path: None)
    monkeypatch.setattr(update, "load_keys", lambda: ("k", "s"))
    monkeypatch.setattr(update.storage, "load_entries_from_db", lambda: {})
    fake_entry = {"tx1": {"time": 1781000000.0}}  # inside requested window
    monkeypatch.setattr(
        update.ledger_loader, "fetch_ledger", lambda *a, **k: fake_entry
    )
    monkeypatch.setattr(
        update.storage, "save_update_entries", lambda entries: len(entries)
    )
    monkeypatch.setattr(update, "_run_portfolio_summary", lambda: None)
    rc = update.main(["--fromdate", "2026-06-11", "--todate", "2026-06-20"])
    assert rc == 0


def test_main_dry_run_never_fetches(tmp_path, monkeypatch):
    db = tmp_path / "ledger.db"
    _make_ledger_db(db, ["2026-06-01T00:00:00+00:00", "2026-06-10T00:00:00+00:00"])
    monkeypatch.setattr(update.storage, "LEDGER_DB_FILE", str(db))
    monkeypatch.setattr(update, "validate_for_update", lambda path: None)
    monkeypatch.setattr(update, "load_keys", lambda: ("k", "s"))
    monkeypatch.setattr(update.storage, "load_entries_from_db", lambda: {})
    fetch_called = {"n": 0}
    monkeypatch.setattr(
        update.ledger_loader,
        "fetch_ledger",
        lambda *a, **k: fetch_called.update(n=1) or {},
    )
    rc = update.main(
        ["--fromdate", "2026-05-01", "--todate", "2026-06-20", "--dry-run"]
    )
    assert rc == 0 and fetch_called["n"] == 0


def test_main_keys_error_after_validation_returns_1(tmp_path, monkeypatch):
    db = tmp_path / "ledger.db"
    _make_ledger_db(db, ["2026-06-01T00:00:00+00:00", "2026-06-10T00:00:00+00:00"])
    monkeypatch.setattr(update.storage, "LEDGER_DB_FILE", str(db))
    monkeypatch.setattr(update, "validate_for_update", lambda path: None)

    def raise_keys():
        raise update.KeysError("no keys")

    monkeypatch.setattr(update, "load_keys", raise_keys)
    rc = update.main(["--fromdate", "2026-05-01", "--todate", "2026-06-20"])
    assert rc == 1


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
