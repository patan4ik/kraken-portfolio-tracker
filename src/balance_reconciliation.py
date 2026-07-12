# balance_reconciliation.py
"""
Cross-check layer: compares portfolio_summary.py FIFO output (remaining_amount,
latest_price) against the latest balances.py snapshot (balance_YYYY-MM-DD.csv),
which reads live Kraken Balance + Ticker API data.

IMPORTANT — this module does NOT override FIFO numbers. avg_price, total_paid,
total_fee, remaining_cost are cost-basis figures that ONLY the FIFO ledger
replay can compute; balances.py cannot produce them (Kraken Balance API has
no concept of cost basis). This module is a validation/alerting layer only:
if FIFO's remaining_amount or latest_price disagree with the live exchange
balance beyond a small tolerance, that indicates a bug in the FIFO replay
(e.g. a missed sell, a bad ledger entry, an unhandled transfer type) and
must be investigated — not silently patched over.
"""

import glob
import logging
import os
import re
from typing import Optional

import pandas as pd

import storage

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

RECONCILIATION_FILE = os.path.join(storage.BALANCES_DIR, "reconciliation_report.csv")

# same alias table as balances.normalize_asset_code(), duplicated intentionally
# (no import cycle risk) — keep in sync if Kraken adds new legacy codes
KRAKEN_LEGACY_ALIASES = {
    "XXBT": "BTC",
    "XBT": "BTC",
    "XETH": "ETH",
    "XXDG": "DOGE",
    "XDG": "DOGE",
    "XLTC": "LTC",
    "XXLM": "XLM",
    "XXRP": "XRP",
    "XXMR": "XMR",
    "XZEC": "ZEC",
    "XREP": "REP",
    "XETC": "ETC",
    "ZEUR": "EUR",
    "ZUSD": "USD",
    "ZGBP": "GBP",
}

# tolerance for amount mismatch — small dust/rounding differences are expected
# (Kraken fee residue, float rounding); anything above this is a real bug
AMOUNT_ABS_TOLERANCE = 0.00000100  # absolute, for very small balances
AMOUNT_REL_TOLERANCE = 0.001  # 0.1% relative, for larger balances


def _normalize_kraken_asset(raw: str) -> str:
    base = re.split(r"\.", str(raw), maxsplit=1)[0]
    base = re.sub(r"\d+$", "", base)
    if len(base) > 3 and base[-1] in {"B", "F", "S"}:
        base = base[:-1]
    return KRAKEN_LEGACY_ALIASES.get(base, base)


def load_latest_balance_snapshot() -> Optional[pd.DataFrame]:
    """
    Load the most recent balances_history/balance_YYYY-MM-DD.csv written by
    balances.py, aggregate wallet-suffixed rows (XETH/ETH.F/ETH.S -> ETH),
    and return columns: Asset, Amount, Current Price (EUR).
    """
    pattern = os.path.join(storage.BALANCES_DIR, "balance_*.csv")
    files = sorted(glob.glob(pattern))
    if not files:
        logger.warning("No balance_*.csv snapshot found for reconciliation")
        return None

    latest_file = files[-1]
    try:
        df = pd.read_csv(latest_file)
    except Exception as e:
        logger.error("Failed to read %s: %s", latest_file, e)
        return None

    if "Asset" not in df.columns or "Amount" not in df.columns:
        logger.error("Balance snapshot %s missing required columns", latest_file)
        return None

    df["asset_norm"] = df["Asset"].apply(_normalize_kraken_asset)
    agg = (
        df.groupby("asset_norm", as_index=False)
        .agg(
            {
                "Amount": "sum",
                "Current Price (EUR)": "max",
            }
        )
        .rename(
            columns={
                "asset_norm": "asset",
                "Amount": "live_amount",
                "Current Price (EUR)": "live_price",
            }
        )
    )

    logger.info("Loaded live balance snapshot: %s (%d assets)", latest_file, len(agg))
    return agg


def reconcile(fifo_df: pd.DataFrame) -> pd.DataFrame:
    """
    Compare fifo_df (output of portfolio_summary.run_fifo(), columns include
    'asset', 'remaining_amount', 'latest_price') against the live balances.py
    snapshot. Returns a diff DataFrame; does NOT modify fifo_df.
    """
    live = load_latest_balance_snapshot()
    if live is None or fifo_df is None or fifo_df.empty:
        logger.warning("Reconciliation skipped: missing FIFO or live balance data")
        return pd.DataFrame()

    merged = fifo_df[["asset", "remaining_amount", "latest_price"]].merge(
        live, on="asset", how="outer"
    )
    merged["remaining_amount"] = merged["remaining_amount"].fillna(0.0)
    merged["live_amount"] = merged["live_amount"].fillna(0.0)

    merged["amount_diff"] = merged["remaining_amount"] - merged["live_amount"]

    def _is_mismatch(row):
        diff = abs(row["amount_diff"])
        ref = max(abs(row["live_amount"]), abs(row["remaining_amount"]))
        rel = diff / ref if ref > 0 else 0.0
        return diff > AMOUNT_ABS_TOLERANCE and rel > AMOUNT_REL_TOLERANCE

    merged["mismatch"] = merged.apply(_is_mismatch, axis=1)
    merged.sort_values("amount_diff", key=abs, ascending=False, inplace=True)
    merged.reset_index(drop=True, inplace=True)

    n_mismatch = int(merged["mismatch"].sum())
    if n_mismatch:
        logger.warning(
            "RECONCILIATION FAILED for %d asset(s) — FIFO vs live Kraken balance "
            "disagree beyond tolerance. Review reconciliation_report.csv. "
            "This likely means run_fifo() has a bug (missed sell, bad ledger "
            "entry, unhandled transfer type) — do NOT silently trust FIFO output "
            "until resolved.",
            n_mismatch,
        )
        for _, r in merged[merged["mismatch"]].iterrows():
            logger.warning(
                "  %-8s FIFO=%.8f  live=%.8f  diff=%.8f",
                r["asset"],
                r["remaining_amount"],
                r["live_amount"],
                r["amount_diff"],
            )
    else:
        logger.info(
            "Reconciliation OK — FIFO matches live Kraken balance for all assets"
        )

    return merged


def save_reconciliation_report(merged: pd.DataFrame):
    if merged is None or merged.empty:
        return
    os.makedirs(storage.BALANCES_DIR, exist_ok=True)
    merged.to_csv(RECONCILIATION_FILE, sep=";", index=False, encoding="utf-8")
    logger.info("Reconciliation report saved to %s", RECONCILIATION_FILE)


def run_reconciliation(fifo_df: pd.DataFrame, write_csv: bool = True) -> pd.DataFrame:
    """Convenience entrypoint: reconcile + optionally save CSV. Never raises —
    a reconciliation failure must never break the main update.py pipeline."""
    try:
        merged = reconcile(fifo_df)
        if write_csv and not merged.empty:
            save_reconciliation_report(merged)
        return merged
    except Exception as e:
        logger.exception("Reconciliation step failed (non-fatal): %s", e)
        return pd.DataFrame()
