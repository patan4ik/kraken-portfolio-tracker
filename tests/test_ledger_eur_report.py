# tests/test_ledger_eur_report.py
import os
import tempfile
from unittest.mock import patch
from datetime import datetime, timezone
import pandas as pd
import pytest

import storage
from src import ledger_eur_report as eur


@pytest.fixture
def tmp_balances_dir(monkeypatch):
    tmp_dir = tempfile.mkdtemp()
    monkeypatch.setattr(storage, "BALANCES_DIR", tmp_dir)
    yield tmp_dir
    import shutil

    shutil.rmtree(tmp_dir)


def make_entry(asset="BTC", amount=1.0, fee=0.0, typ="receive", ts=None, refid=None):
    if ts is None:
        ts = datetime.now(timezone.utc).timestamp()
    return {
        "asset": asset,
        "amount": amount,
        "fee": fee,
        "type": typ,
        "time": ts,
        "refid": refid,
    }


def test_build_eur_report_empty():
    df = eur.build_eur_report({})
    assert df.empty


def test_build_eur_report_skips_old_and_wrong_types():
    old_ts = datetime.now(timezone.utc).timestamp() - 10_000_000
    entries = {
        "tx1": make_entry(typ="unknown", ts=old_ts),
        "tx2": make_entry(typ="receive", ts=old_ts),
    }
    df = eur.build_eur_report(entries, days=1)
    assert df.empty


def test_build_eur_report_basic_allocation():
    ts = datetime.now(timezone.utc).timestamp()
    entries = {
        "tx1": make_entry(asset="EUR", amount=-100, fee=1, typ="spend", ts=ts),
        "tx2": make_entry(asset="BTC", amount=0.01, typ="receive", ts=ts, refid="tx1"),
    }
    df = eur.build_eur_report(entries, days=1)
    assert not df.empty
    assert "BTC" in df.columns
    assert df["Total Spent EUR"].iloc[0] == 100
    assert df["Total Fee"].iloc[0] == 1
    assert df["BTC"].iloc[0] == 100  # full allocation to BTC


def test_build_eur_report_multiple_receives():
    ts = datetime.now(timezone.utc).timestamp()
    entries = {
        "tx1": make_entry(asset="EUR", amount=-100, fee=1, typ="spend", ts=ts),
        "tx2": make_entry(asset="BTC", amount=0.01, typ="receive", ts=ts, refid="tx1"),
        "tx3": make_entry(asset="ETH", amount=0.03, typ="receive", ts=ts, refid="tx1"),
    }
    df = eur.build_eur_report(entries, days=1)
    assert df["BTC"].iloc[0] > 0
    assert df["ETH"].iloc[0] > 0
    total_alloc = df["BTC"].iloc[0] + df["ETH"].iloc[0]
    assert total_alloc == 100


def test_save_eur_report_creates_csv(tmp_balances_dir):
    df = pd.DataFrame(
        {
            "Date": [datetime.now()],
            "Total Fee": [0.5],
            "Total Spent EUR": [10],
            "BTC": [10],
        }
    )
    out_file = os.path.join(tmp_balances_dir, "ledger_eur_report.csv")
    # Патчим LEDGER_EUR_FILE, чтобы запись пошла в tmp_balances_dir
    with patch("src.ledger_eur_report.LEDGER_EUR_FILE", out_file):
        eur.save_eur_report(df)
        assert os.path.exists(out_file)
        df2 = pd.read_csv(out_file, sep=";")
        assert "Date" in df2.columns
        assert df2["Date"].iloc[0].count(".") == 2  # dd.mm.yyyy


@patch("src.ledger_eur_report.storage.load_entries_from_db")
@patch("src.ledger_eur_report.save_eur_report")
def test_update_eur_report(mock_save, mock_load, tmp_balances_dir):
    # empty data
    mock_load.return_value = {}
    df = eur.update_eur_report(days=1, write_csv=True)
    assert df.empty

    # data present
    ts = datetime.now(timezone.utc).timestamp()
    entries = {
        "tx1": make_entry(asset="EUR", amount=-50, fee=0.5, typ="spend", ts=ts),
        "tx2": make_entry(asset="BTC", amount=0.01, typ="receive", ts=ts, refid="tx1"),
    }
    mock_load.return_value = entries
    df2 = eur.update_eur_report(days=1, write_csv=True)
    assert not df2.empty
    mock_save.assert_called_once()
    assert df2["BTC"].iloc[0] == 50
