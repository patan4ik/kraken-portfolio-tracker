# portfolio_summary_report.py
"""
CSV export + CLI for the portfolio summary (FIFO + forecast), mirroring the
existing convention of ledger_asset_report.py / ledger_sell_report.py:
build_*() -> save_*() -> update_*() -> main() with --csv flag.

This module does NOT recompute FIFO itself - it either:
  (a) triggers a fresh recompute via portfolio_summary.update_summary(), or
  (b) reads back the already-persisted `summary` table via
      portfolio_summary.load_summary() for a quick review without recomputation.

Adds Google Sheets Summary-like derived columns:
Sell +25/35/50/75%, Trend, Signal, Upside %, Volatility Score,
Recovery Strength, Confidence, Regime, Asset Color Score.
"""

import argparse
import logging
import os
import re

import pandas as pd
import storage
import portfolio_summary

PORTFOLIO_SUMMARY_FILE = os.path.join(
    storage.BALANCES_DIR, "portfolio_summary_report.csv"
)

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

DISPLAY_COLUMNS = {
    "asset": "Asset",
    "latest_price": "Latest Price",
    "update_date": "Update Date",
    "remaining_amount": "Total Amount",
    "total_paid": "Total Paid EUR",
    "total_fee": "Total Fee EUR",
    "remaining_cost": "Remaining Cost (FIFO)",
    "avg_price": "Average Buy Price EUR",
    "sell_25": "Sell +25%",
    "sell_35": "Sell +35%",
    "sell_50": "Sell +50%",
    "sell_75": "Sell +75%",
    "trend": "Trend",
    "ema7": "EMA7",
    "forecast_7d": "Forecast 7d",
    "forecast_30d": "Forecast 30d",
    "signal": "Signal",
    "upside_pct": "Upside %",
    "volatility_score": "Volatility Score",
    "recovery_strength": "Recovery Strength",
    "confidence": "Confidence",
    "regime": "Regime",
    "asset_color_score": "Asset Color Score",
}


def _is_na(v) -> bool:
    if v is None:
        return True
    try:
        if pd.isna(v):
            return True
    except Exception:
        pass
    if isinstance(v, str) and v.strip().upper() in {"", "N/A"}:
        return True
    return False


def _num(v):
    if _is_na(v):
        return None
    try:
        return float(v)
    except Exception:
        return None


def _pct_text(value: float) -> str:
    return f"{value * 100:.2f}".replace(".", ",") + "%"


def _trend_number_from_text(trend: str) -> float:
    if _is_na(trend):
        return 0.0
    m = re.search(r"([+-]?[0-9]+,[0-9]+)%", str(trend))
    if not m:
        return 0.0
    return float(m.group(1).replace(",", ".")) / 100.0


def calc_sell_targets(avg_price):
    h = _num(avg_price)
    if h is None:
        return None, None, None, None
    return h * 1.25, h * 1.35, h * 1.50, h * 1.75


def calc_trend(latest_price, avg_price):
    b = _num(latest_price)
    h = _num(avg_price)
    if h in (None, 0) or b is None:
        return ""
    diff = (b - h) / h
    if b > h:
        return f"↑ {_pct_text(diff)}"
    if b < h:
        return f"↓ {_pct_text(diff)}"
    return "0,00%"


def calc_upside_pct(latest_price, forecast_30d):
    b = _num(latest_price)
    p = _num(forecast_30d)
    if b in (None, 0) or p is None:
        return None
    return (p - b) / b


def calc_volatility_score(latest_price, ema7, forecast_7d):
    b = _num(latest_price)
    n = _num(ema7)
    o = _num(forecast_7d)
    if b in (None, 0) or n is None or o is None:
        return None
    return abs(o - n) / b


def calc_recovery_strength(latest_price, avg_price, ema7):
    b = _num(latest_price)
    h = _num(avg_price)
    n = _num(ema7)
    if b is None or h is None or n is None or h == b:
        return None
    return (n - b) / abs(h - b)


def calc_confidence(volatility_score, ema7, forecast_7d, forecast_30d):
    s = _num(volatility_score)
    n = _num(ema7)
    o = _num(forecast_7d)
    p = _num(forecast_30d)
    if s is None or n is None or o is None or p is None:
        return "LOW"
    if s < 0.15:
        return "HIGH"
    if s < 0.35:
        return "MEDIUM"
    return "LOW"


def calc_regime(latest_price, ema7, forecast_7d):
    b = _num(latest_price)
    n = _num(ema7)
    o = _num(forecast_7d)
    if b is None or n is None or o is None:
        return "N/A"
    if b < n and o > n:
        return "BULLISH RECOVERY"
    if b > n and o > b:
        return "BULLISH"
    if b < n and o < n:
        return "WEAK/SIDEWAYS"
    return "BEARISH"


def calc_signal(
    latest_price, avg_price, ema7, forecast_7d, forecast_30d, volatility_score
):
    b = _num(latest_price)
    h = _num(avg_price)
    n = _num(ema7)
    o = _num(forecast_7d)
    p = _num(forecast_30d)
    s = _num(volatility_score)
    if b is None or h is None or n is None or o is None or p is None or s is None:
        return "N/A"
    if b < h and n > b and p > b and s < 0.35:
        return "ACCUMULATE"
    if b < h and p > b and s < 0.6:
        return "BUY LIGHT"
    if b > h and n < b and p < b:
        return "REDUCE"
    if s >= 0.6:
        return "HIGH RISK"
    return "HOLD"


def calc_asset_color_score(
    signal, trend, upside_pct, volatility_score, recovery_strength, confidence, regime
):
    if any(
        _is_na(x)
        for x in [
            signal,
            trend,
            upside_pct,
            volatility_score,
            recovery_strength,
            confidence,
            regime,
        ]
    ):
        return None

    score = 0
    if signal in {"STRONG BUY", "BUY"}:
        score += 2
    elif signal == "HOLD":
        score += 1

    trend_pct = _trend_number_from_text(trend)
    if trend_pct > 0.1:
        score += 1
    elif trend_pct < -0.1:
        score -= 1

    if upside_pct > 0.2:
        score += 1
    if volatility_score < 0.35:
        score += 1
    if recovery_strength > 1:
        score += 1
    if confidence == "HIGH":
        score += 1
    if volatility_score > 0.6:
        score -= 1
    if regime in {"BEARISH", "WEAK/SIDEWAYS"}:
        score -= 1
    return score


def enrich_summary(df: pd.DataFrame) -> pd.DataFrame:
    out = df.copy()

    out[["sell_25", "sell_35", "sell_50", "sell_75"]] = out.apply(
        lambda r: pd.Series(calc_sell_targets(r.get("avg_price"))), axis=1
    )

    out["trend"] = out.apply(
        lambda r: calc_trend(r.get("latest_price"), r.get("avg_price")), axis=1
    )

    out["upside_pct"] = out.apply(
        lambda r: calc_upside_pct(r.get("latest_price"), r.get("forecast_30d")), axis=1
    )

    out["volatility_score"] = out.apply(
        lambda r: calc_volatility_score(
            r.get("latest_price"), r.get("ema7"), r.get("forecast_7d")
        ),
        axis=1,
    )

    out["recovery_strength"] = out.apply(
        lambda r: calc_recovery_strength(
            r.get("latest_price"), r.get("avg_price"), r.get("ema7")
        ),
        axis=1,
    )

    out["confidence"] = out.apply(
        lambda r: calc_confidence(
            r.get("volatility_score"),
            r.get("ema7"),
            r.get("forecast_7d"),
            r.get("forecast_30d"),
        ),
        axis=1,
    )

    out["regime"] = out.apply(
        lambda r: calc_regime(
            r.get("latest_price"), r.get("ema7"), r.get("forecast_7d")
        ),
        axis=1,
    )

    out["signal"] = out.apply(
        lambda r: calc_signal(
            r.get("latest_price"),
            r.get("avg_price"),
            r.get("ema7"),
            r.get("forecast_7d"),
            r.get("forecast_30d"),
            r.get("volatility_score"),
        ),
        axis=1,
    )

    out["asset_color_score"] = out.apply(
        lambda r: calc_asset_color_score(
            r.get("signal"),
            r.get("trend"),
            r.get("upside_pct"),
            r.get("volatility_score"),
            r.get("recovery_strength"),
            r.get("confidence"),
            r.get("regime"),
        ),
        axis=1,
    )

    return out


def build_summary_report(recompute: bool = True) -> pd.DataFrame:
    """
    Returns the portfolio summary DataFrame ready for CSV export / review.

    recompute=True  -> full FIFO + forecast recompute from the ledger (default,
                        always correct, matches "recompute-on-read" design).
    recompute=False -> read back the last persisted `summary` table without
                        recomputation (fast, useful for a quick look).
    """
    if recompute:
        df = portfolio_summary.update_summary()
    else:
        df = portfolio_summary.load_summary()

    if df is None or df.empty:
        logger.warning("Portfolio summary is empty")
        return pd.DataFrame()

    df = enrich_summary(df)

    ordered = [c for c in DISPLAY_COLUMNS if c in df.columns]
    out = df[ordered].copy()
    out.rename(columns=DISPLAY_COLUMNS, inplace=True)

    money_cols = [
        "Latest Price",
        "Total Paid EUR",
        "Total Fee EUR",
        "Remaining Cost (FIFO)",
        "Average Buy Price EUR",
        "Sell +25%",
        "Sell +35%",
        "Sell +50%",
        "Sell +75%",
        "EMA7",
        "Forecast 7d",
        "Forecast 30d",
    ]
    for c in money_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").round(4)

    metric_cols = ["Upside %", "Volatility Score", "Recovery Strength"]
    for c in metric_cols:
        if c in out.columns:
            out[c] = pd.to_numeric(out[c], errors="coerce").round(4)

    if "Total Amount" in out.columns:
        out["Total Amount"] = pd.to_numeric(out["Total Amount"], errors="coerce").round(
            8
        )

    if "Asset Color Score" in out.columns:
        out["Asset Color Score"] = pd.to_numeric(
            out["Asset Color Score"], errors="coerce"
        )

    if "Update Date" in out.columns:
        out["Update Date"] = pd.to_datetime(
            out["Update Date"], errors="coerce", utc=True
        )

    out.sort_values("Asset", inplace=True)
    out.reset_index(drop=True, inplace=True)
    return out


def save_summary_report(df: pd.DataFrame):
    """CSV export, same style/format as save_asset_report() / save_sell_report()."""
    os.makedirs(storage.BALANCES_DIR, exist_ok=True)
    out = df.copy()
    if "Update Date" in out.columns:
        out["Update Date"] = pd.to_datetime(
            out["Update Date"], errors="coerce"
        ).dt.strftime("%d.%m.%Y")
    out.to_csv(PORTFOLIO_SUMMARY_FILE, sep=";", index=False, encoding="utf-8")
    logger.info(f"PORTFOLIO SUMMARY report saved to {PORTFOLIO_SUMMARY_FILE}")


def update_summary_report(
    write_csv: bool = False, recompute: bool = True
) -> pd.DataFrame:
    """Entry point mirroring update_asset_report()/update_sell_report()."""
    df = build_summary_report(recompute=recompute)
    if df.empty:
        logger.warning("Portfolio summary report is empty")
        return df

    if write_csv:
        save_summary_report(df)
    logger.info("Portfolio summary report updated")
    return df


def main():
    parser = argparse.ArgumentParser(
        description="Portfolio FIFO summary + forecast report"
    )
    parser.add_argument("--csv", action="store_true", help="Export to CSV")
    parser.add_argument(
        "--no-recompute",
        action="store_true",
        help="Read the last persisted summary table instead of recomputing FIFO from the ledger",
    )
    args = parser.parse_args()

    df = build_summary_report(recompute=not args.no_recompute)

    if df.empty:
        logger.warning("No data for portfolio summary report")
        return

    if args.csv:
        save_summary_report(df)
    else:
        print(df.to_string(index=False))


if __name__ == "__main__":
    main()
