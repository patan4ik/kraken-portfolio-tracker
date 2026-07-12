"""Unit tests for src/portfolio_summary.py — FIFO engine + forecast."""

import sqlite3
import sys
import types
from datetime import datetime, timezone

import pandas as pd
import pytest

# stub `storage` module (portfolio_summary imports it for LEDGER_DB_FILE etc.)
storage_stub = types.ModuleType("storage")
storage_stub.LEDGER_DB_FILE = "unused.db"
storage_stub.BALANCES_DIR = "unused_dir"
storage_stub.load_entries_from_db = lambda: {}
sys.modules.setdefault("storage", storage_stub)

import portfolio_summary as ps  # noqa: E402


# ---------------------------------------------------------------------------
# normalize_asset
# ---------------------------------------------------------------------------
@pytest.mark.parametrize(
    "raw,expected",
    [
        ("XXBT", "BTC"),
        ("xbt", "BTC"),
        ("SUI.F", "SUI"),
        ("SUI.B", "SUI"),
        ("GRT28.S", "GRT"),
        ("ATOM21.S", "ATOM"),
        ("ZEUR", "EUR"),
        ("DOT", "DOT"),
        ("", ""),
        (None, ""),
    ],
)
def test_normalize_asset(raw, expected):
    assert ps.normalize_asset(raw) == expected


# ---------------------------------------------------------------------------
# extract_buys / extract_sells
# ---------------------------------------------------------------------------
def _entry(
    asset, amount, fee=0.0, refid="r1", type_="trade", date="2026-01-01T00:00:00+00:00"
):
    return {
        "asset": asset,
        "amount": amount,
        "fee": fee,
        "refid": refid,
        "type": type_,
        "date": date,
    }


def test_extract_buys_basic():
    entries = {
        "t1": _entry("ZEUR", -100.0, fee=0.0, refid="r1"),
        "t2": _entry("BTC", 0.01, fee=0.5, refid="r1"),
    }
    buys = ps.extract_buys(entries)
    assert len(buys) == 1
    b = buys[0]
    assert b["asset"] == "BTC"
    assert b["amount"] == pytest.approx(0.01)
    assert b["paid"] == pytest.approx(100.0)
    assert b["fee"] == pytest.approx(0.5)
    assert b["price"] > 0


def test_extract_buys_excludes_transfers():
    entries = {
        "t1": _entry("SUI", 5.0, refid="r1", type_="transfer"),
        "t2": _entry("SUI", -5.0, refid="r1", type_="transfer"),
    }
    buys = ps.extract_buys(entries)
    assert buys == []


def test_extract_buys_skips_invalid_date():
    entries = {
        "t1": _entry("ZEUR", -100.0, refid="r1", date=""),
        "t2": _entry("BTC", 0.01, refid="r1", date=""),
    }
    for e in entries.values():
        e.pop("date")
        e["time"] = 0
    buys = ps.extract_buys(entries)
    assert buys == []


def test_extract_sells_basic():
    entries = {
        "t1": _entry("BTC", -0.005, fee=0.1, refid="r2"),
        "t2": _entry("ZEUR", 200.0, fee=0.0, refid="r2"),
    }
    sells = ps.extract_sells(entries)
    assert len(sells) == 1
    s = sells[0]
    assert s["asset"] == "BTC"
    assert s["amount"] == pytest.approx(0.005)
    assert s["proceeds"] == pytest.approx(200.0)
    assert s["fee"] == pytest.approx(0.1)


def test_extract_sells_requires_both_legs():
    entries = {"t1": _entry("BTC", -0.005, refid="r3")}
    assert ps.extract_sells(entries) == []


# ---------------------------------------------------------------------------
# run_fifo (integration of buy/sell state machine)
# ---------------------------------------------------------------------------
def test_run_fifo_empty_entries():
    df = ps.run_fifo({})
    assert df.empty


def test_run_fifo_buy_then_partial_sell():
    entries = {
        "b1": _entry("ZEUR", -100.0, refid="r1", date="2026-01-01T00:00:00+00:00"),
        "b1a": _entry("BTC", 1.0, refid="r1", date="2026-01-01T00:00:00+00:00"),
        "b2": _entry("ZEUR", -300.0, refid="r2", date="2026-01-02T00:00:00+00:00"),
        "b2a": _entry("BTC", 1.0, refid="r2", date="2026-01-02T00:00:00+00:00"),
        "s1": _entry("BTC", -0.5, refid="r3", date="2026-01-03T00:00:00+00:00"),
        "s1a": _entry("ZEUR", 250.0, refid="r3", date="2026-01-03T00:00:00+00:00"),
    }
    df = ps.run_fifo(entries)
    assert list(df["asset"]) == ["BTC"]
    row = df.iloc[0]
    assert row["remaining_amount"] == pytest.approx(1.5)
    assert row["avg_price"] == pytest.approx(200.0)


def test_run_fifo_sell_without_prior_buy_is_skipped(caplog):
    entries = {
        "s1": _entry("BTC", -1.0, refid="r1"),
        "s1a": _entry("ZEUR", 100.0, refid="r1"),
    }
    df = ps.run_fifo(entries)
    assert df.empty


# ---------------------------------------------------------------------------
# forecast_prices
# ---------------------------------------------------------------------------
def test_forecast_prices_empty_df_returns_as_is():
    df = pd.DataFrame()
    out = ps.forecast_prices(df)
    assert out.empty


def test_forecast_prices_fallback_when_insufficient_points():
    df = pd.DataFrame([{"asset": "BTC", "avg_price": 100.0}])
    df.attrs["price_state"] = {}
    out = ps.forecast_prices(df)
    assert out.loc[0, "ema7"] == 100.0
    assert out.loc[0, "forecast_7d"] is None
    assert out.loc[0, "forecast_30d"] is None


def test_forecast_prices_with_enough_points():
    df = pd.DataFrame([{"asset": "BTC", "avg_price": 100.0}])
    df.attrs["price_state"] = {
        "BTC": {
            "ema7": 105.0,
            "n": 5,
            "sumX": 10,
            "sumY": 500,
            "sumXX": 30,
            "sumXY": 1050,
            "last_date": None,
        }
    }
    out = ps.forecast_prices(df)
    assert out.loc[0, "ema7"] == 105.0
    assert out.loc[0, "forecast_7d"] is not None
    assert out.loc[0, "forecast_30d"] is not None


# ---------------------------------------------------------------------------
# save_summary / init_summary_table (SQLite persistence)
# ---------------------------------------------------------------------------
def test_save_summary_persists_rows(tmp_path):
    db_path = str(tmp_path / "ledger.db")
    df = pd.DataFrame(
        [
            {
                "asset": "BTC",
                "latest_price": 100.0,
                "update_date": datetime(2026, 1, 1, tzinfo=timezone.utc),
                "remaining_amount": 1.0,
                "total_paid": 100.0,
                "total_fee": 1.0,
                "remaining_cost": 101.0,
                "avg_price": 101.0,
                "ema7": 100.0,
                "forecast_7d": 105.0,
                "forecast_30d": 110.0,
            }
        ]
    )
    ps.save_summary(df, db_path=db_path)
    conn = sqlite3.connect(db_path)
    cur = conn.cursor()
    cur.execute("SELECT asset, remaining_amount FROM summary")
    rows = cur.fetchall()
    conn.close()
    assert rows == [("BTC", 1.0)]


def test_update_summary_no_entries(monkeypatch):
    monkeypatch.setattr(ps.storage, "load_entries_from_db", lambda: {})
    df = ps.update_summary()
    assert df.empty
