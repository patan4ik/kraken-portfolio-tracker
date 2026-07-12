"""Unit tests for src/portfolio_summary_report.py — enrichment calculations."""

import sys
import types

import pandas as pd
import pytest

# storage_stub = types.ModuleType("storage")
# storage_stub.BALANCES_DIR = "unused_dir"
# sys.modules.setdefault("storage", storage_stub)

ps_stub = types.ModuleType("portfolio_summary")
ps_stub.update_summary = lambda: pd.DataFrame()
ps_stub.load_summary = lambda: pd.DataFrame()
sys.modules.setdefault("portfolio_summary", ps_stub)

import portfolio_summary_report as psr  # noqa: E402


def test_is_na_and_num():
    assert psr._is_na(None) is True
    assert psr._is_na("N/A") is True
    assert psr._is_na("") is True
    assert psr._is_na(5) is False
    assert psr._num("abc") is None
    assert psr._num("5.5") == 5.5
    assert psr._num(None) is None


def test_calc_sell_targets():
    r25, r35, r50, r75 = psr.calc_sell_targets(100.0)
    assert (r25, r35, r50, r75) == (125.0, 135.0, 150.0, 175.0)
    assert psr.calc_sell_targets(None) == (None, None, None, None)


def test_calc_trend_up_down_flat():
    assert psr.calc_trend(110, 100).startswith("↑")
    assert psr.calc_trend(90, 100).startswith("↓")
    assert psr.calc_trend(100, 100) == "0,00%"
    assert psr.calc_trend(100, None) == ""
    assert psr.calc_trend(100, 0) == ""


def test_calc_upside_pct():
    assert psr.calc_upside_pct(100, 120) == pytest.approx(0.2)
    assert psr.calc_upside_pct(0, 120) is None
    assert psr.calc_upside_pct(100, None) is None


def test_calc_volatility_score():
    assert psr.calc_volatility_score(100, 90, 95) == pytest.approx(0.05)
    assert psr.calc_volatility_score(0, 90, 95) is None


def test_calc_recovery_strength():
    assert psr.calc_recovery_strength(90, 100, 95) == pytest.approx(0.5)
    assert psr.calc_recovery_strength(100, 100, 95) is None  # h == b


def test_calc_confidence_levels():
    assert psr.calc_confidence(0.1, 1, 2, 3) == "HIGH"
    assert psr.calc_confidence(0.2, 1, 2, 3) == "MEDIUM"
    assert psr.calc_confidence(0.5, 1, 2, 3) == "LOW"
    assert psr.calc_confidence(None, 1, 2, 3) == "LOW"


def test_calc_regime_variants():
    assert psr.calc_regime(90, 100, 110) == "BULLISH RECOVERY"
    assert psr.calc_regime(110, 100, 120) == "BULLISH"
    assert psr.calc_regime(90, 100, 95) == "WEAK/SIDEWAYS"
    assert psr.calc_regime(110, 100, 90) == "BEARISH"
    assert psr.calc_regime(None, 100, 90) == "N/A"


def test_calc_signal_variants():
    assert psr.calc_signal(90, 100, 110, 95, 120, 0.2) == "ACCUMULATE"
    assert psr.calc_signal(90, 100, 90, 95, 120, 0.5) == "BUY LIGHT"
    assert psr.calc_signal(110, 100, 90, 90, 90, 0.1) == "REDUCE"
    assert psr.calc_signal(100, 100, 100, 100, 100, 0.7) == "HIGH RISK"
    assert psr.calc_signal(None, 100, 100, 100, 100, 0.1) == "N/A"


def test_calc_asset_color_score_none_when_missing():
    assert (
        psr.calc_asset_color_score(None, "↑ 1,00%", 0.1, 0.1, 1.5, "HIGH", "BULLISH")
        is None
    )


def test_calc_asset_color_score_positive_case():
    score = psr.calc_asset_color_score(
        "STRONG BUY", "↑ 15,00%", 0.25, 0.2, 1.5, "HIGH", "BULLISH"
    )
    assert score == 7


def test_calc_asset_color_score_negative_case():
    score = psr.calc_asset_color_score(
        "HOLD", "↓ -20,00%", 0.05, 0.7, 0.5, "LOW", "BEARISH"
    )
    assert score == -2


def test_enrich_summary_adds_columns():
    df = pd.DataFrame(
        [
            {
                "asset": "BTC",
                "latest_price": 110.0,
                "avg_price": 100.0,
                "ema7": 105.0,
                "forecast_7d": 108.0,
                "forecast_30d": 130.0,
            }
        ]
    )
    out = psr.enrich_summary(df)
    for col in [
        "sell_25",
        "sell_35",
        "sell_50",
        "sell_75",
        "trend",
        "upside_pct",
        "volatility_score",
        "recovery_strength",
        "confidence",
        "regime",
        "signal",
        "asset_color_score",
    ]:
        assert col in out.columns


def test_build_summary_report_empty_when_no_data(monkeypatch):
    monkeypatch.setattr(psr.portfolio_summary, "update_summary", lambda: pd.DataFrame())
    out = psr.build_summary_report(recompute=True)
    assert out.empty


def test_update_summary_report_no_csv_write(tmp_path, monkeypatch):
    df = pd.DataFrame(
        [
            {
                "asset": "BTC",
                "latest_price": 110.0,
                "update_date": "2026-01-01",
                "remaining_amount": 1.0,
                "total_paid": 100.0,
                "total_fee": 1.0,
                "remaining_cost": 101.0,
                "avg_price": 100.0,
                "ema7": 105.0,
                "forecast_7d": 108.0,
                "forecast_30d": 130.0,
            }
        ]
    )
    monkeypatch.setattr(psr.portfolio_summary, "update_summary", lambda: df)
    out = psr.update_summary_report(write_csv=False, recompute=True)
    assert not out.empty
    assert "Asset" in out.columns
