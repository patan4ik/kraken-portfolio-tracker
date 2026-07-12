"""Unit tests for src/balance_reconciliation.py — FIFO vs live balance cross-check."""

import os

import pandas as pd
import pytest

# storage_stub = types.ModuleType("storage")
# sys.modules.setdefault("storage", storage_stub)

import balance_reconciliation as br  # noqa: E402


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("XXBT", "BTC"),
        ("ETH.F", "ETH"),
        ("ETH.S", "ETH"),
        ("SUI28", "SUI"),
        ("DOT", "DOT"),
        ("ZEUR", "EUR"),
    ],
)
def test_normalize_kraken_asset(raw, expected):
    assert br._normalize_kraken_asset(raw) == expected


def test_load_latest_balance_snapshot_no_files(tmp_path, monkeypatch):
    monkeypatch.setattr(br.storage, "BALANCES_DIR", str(tmp_path))
    assert br.load_latest_balance_snapshot() is None


def test_load_latest_balance_snapshot_missing_columns(tmp_path, monkeypatch):
    monkeypatch.setattr(br.storage, "BALANCES_DIR", str(tmp_path))
    f = tmp_path / "balance_2026-01-01.csv"
    pd.DataFrame([{"Foo": 1}]).to_csv(f, index=False)
    assert br.load_latest_balance_snapshot() is None


def test_load_latest_balance_snapshot_aggregates(tmp_path, monkeypatch):
    monkeypatch.setattr(br.storage, "BALANCES_DIR", str(tmp_path))
    f = tmp_path / "balance_2026-01-01.csv"
    pd.DataFrame(
        [
            {"Asset": "ETH.F", "Amount": 1.0, "Current Price (EUR)": 3000},
            {"Asset": "ETH.S", "Amount": 0.5, "Current Price (EUR)": 3000},
        ]
    ).to_csv(f, index=False)
    out = br.load_latest_balance_snapshot()
    assert out is not None
    row = out[out["asset"] == "ETH"].iloc[0]
    assert row["live_amount"] == pytest.approx(1.5)


def test_reconcile_missing_data_returns_empty(monkeypatch):
    monkeypatch.setattr(br, "load_latest_balance_snapshot", lambda: None)
    out = br.reconcile(
        pd.DataFrame([{"asset": "BTC", "remaining_amount": 1, "latest_price": 100}])
    )
    assert out.empty

    out2 = br.reconcile(pd.DataFrame())
    assert out2.empty


def test_reconcile_flags_mismatch(monkeypatch):
    live = pd.DataFrame([{"asset": "BTC", "live_amount": 2.0, "live_price": 50000.0}])
    monkeypatch.setattr(br, "load_latest_balance_snapshot", lambda: live)
    fifo = pd.DataFrame(
        [{"asset": "BTC", "remaining_amount": 1.0, "latest_price": 50000.0}]
    )
    merged = br.reconcile(fifo)
    row = merged[merged["asset"] == "BTC"].iloc[0]
    assert bool(row["mismatch"]) is True


def test_reconcile_within_tolerance_no_mismatch(monkeypatch):
    live = pd.DataFrame(
        [{"asset": "BTC", "live_amount": 1.0000005, "live_price": 50000.0}]
    )
    monkeypatch.setattr(br, "load_latest_balance_snapshot", lambda: live)
    fifo = pd.DataFrame(
        [{"asset": "BTC", "remaining_amount": 1.0, "latest_price": 50000.0}]
    )
    merged = br.reconcile(fifo)
    row = merged[merged["asset"] == "BTC"].iloc[0]
    assert not row["mismatch"]


def test_save_reconciliation_report_writes_file(tmp_path, monkeypatch):
    monkeypatch.setattr(br.storage, "BALANCES_DIR", str(tmp_path))
    br.RECONCILIATION_FILE = os.path.join(str(tmp_path), "reconciliation_report.csv")
    df = pd.DataFrame([{"asset": "BTC", "amount_diff": 0.0}])
    br.save_reconciliation_report(df)
    assert os.path.exists(br.RECONCILIATION_FILE)


def test_save_reconciliation_report_skips_empty(tmp_path, monkeypatch):
    monkeypatch.setattr(br.storage, "BALANCES_DIR", str(tmp_path))
    br.RECONCILIATION_FILE = os.path.join(str(tmp_path), "reconciliation_report.csv")
    br.save_reconciliation_report(pd.DataFrame())
    assert not os.path.exists(br.RECONCILIATION_FILE)


def test_run_reconciliation_never_raises(monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("boom")

    monkeypatch.setattr(br, "reconcile", boom)
    out = br.run_reconciliation(pd.DataFrame([{"asset": "BTC"}]), write_csv=True)
    assert out.empty
