# portfolio_summary.py
"""
FIFO cost-basis engine + EMA/regression price forecast, ported from the
Google Sheets Apps Script pipeline (runFIFO + forecastPrices).

IMPORTANT - Kraken wallet-suffix handling:
Kraken splits one asset across wallet types using suffixes:
  .F = Flexible/Spot wallet, .B = Bonded/Staking wallet,
  .S = Staked, .M = Locked/Misc, .P = Pool
type='transfer' (e.g. subtype='spottostaking') moves the SAME asset between
these wallets with equal and opposite amounts under the SAME refid.
This is NOT a buy or sell - net cost-basis effect is zero. These entries are
filtered out entirely, and asset suffixes are stripped so SUI.B / SUI.F both
roll up into ticker 'SUI' for FIFO and balance purposes.

Design decisions (per project review):
- No DataNormalization/FIFOState/AssetPriceState persistent tables.
  Full ledger history is always available in SQLite -> recompute on every run.
- `summary` table is a derived, disposable output (INSERT OR REPLACE),
  never incrementally patched. Idempotent, always correct.
- FIFO and forecast NEVER apply a --days cutoff. Full history required
  for correct running average cost and regression trend.
"""

import logging
import re
import sqlite3
from collections import defaultdict
from datetime import datetime, timezone
from typing import Dict, Any, List, DefaultDict, Optional

import pandas as pd
import storage

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

EUR_ASSETS = {"ZEUR", "EUR"}

# Ledger entry types that represent internal wallet moves, NOT buys/sells.
# These must be excluded from FIFO entirely (transfer between spot/staking/etc.
# nets to zero real acquisition or disposal).
NON_TRADE_TYPES = {"transfer"}

# Kraken legacy asset code normalization (X/Z prefixed codes -> common ticker)
ASSET_ALIASES = {
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

# Kraken wallet-location suffix pattern, e.g.:
#   SUI.F / SUI.B                -> flexible / bonded staking wallet
#   GRT28.S / DOT28.S / ATOM21.S -> locked staking wallet with N-day lock term
# The optional digits before the suffix (locked-term length) must be stripped
# too, otherwise "GRT28" is wrongly treated as a distinct asset from "GRT".
WALLET_SUFFIX_RE = re.compile(r"\d*\.(F|B|S|M|P)$")


def normalize_asset(raw: Optional[str]) -> str:
    """
    Mirror of Apps Script normalizeAsset(): trim + uppercase + map legacy codes
    + strip Kraken wallet-location suffix (optionally preceded by a lock-term
    number, e.g. .F/.B/.S/.M/.P or 28.S/21.S) so the same coin held in
    different wallets (spot vs flexible/locked staking) rolls up to one ticker.
    """
    if not raw:
        return ""
    a = str(raw).strip().upper()
    a = WALLET_SUFFIX_RE.sub("", a)
    return ASSET_ALIASES.get(a, a)


# ---------------------------------------------------------------------------
# TRANSACTION-LEVEL EXTRACTION (unlike the day-aggregated report builders,
# FIFO needs every individual transaction, fully unfiltered by date range)
# ---------------------------------------------------------------------------


def _group_by_refid(entries: Dict[str, Any]) -> DefaultDict[str, List[Dict[str, Any]]]:
    groups: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for txid, e in entries.items():
        if str(e.get("type", "")).lower() in NON_TRADE_TYPES:
            continue  # exclude wallet transfers (spot<->staking) entirely
        ref = e.get("refid") or txid
        groups[ref].append(e)
    return groups


def _entry_date(e: Dict[str, Any]):
    if e.get("date"):
        try:
            return datetime.fromisoformat(e["date"])
        except Exception:
            pass
    ts = float(e.get("time", 0))
    return datetime.fromtimestamp(ts, tz=timezone.utc) if ts else None


def extract_buys(entries: Dict[str, Any]) -> List[Dict[str, Any]]:
    """
    Pair EUR-out legs with asset-in legs per refid -> individual buy transactions.
    Also captures fee-free asset inflows (staking rewards, airdrops - NOT
    spot<->staking transfers, which are already excluded) with paid=0, which
    correctly dilutes average cost like a free lot.
    """
    buys = []
    for ref, items in _group_by_refid(entries).items():
        eur_legs = [
            i
            for i in items
            if i.get("asset") in EUR_ASSETS and float(i.get("amount", 0)) < 0
        ]
        asset_legs = [
            i
            for i in items
            if i.get("asset") not in EUR_ASSETS and float(i.get("amount", 0)) > 0
        ]

        if not asset_legs:
            continue

        paid = sum(abs(float(leg_item.get("amount", 0))) for leg_item in eur_legs)
        fee = sum(float(leg_item.get("fee", 0)) for leg_item in items)
        total_asset_amount = sum(
            float(leg_item.get("amount", 0)) for leg_item in asset_legs
        )

        for leg in asset_legs:
            asset = normalize_asset(leg.get("asset"))
            amount = float(leg.get("amount", 0))
            if amount <= 0 or not asset:
                continue
            date = _entry_date(leg)
            if not date:
                logger.warning(
                    "Skipped buy leg with invalid date | refid=%s asset=%s", ref, asset
                )
                continue

            share = amount / total_asset_amount if total_asset_amount else 1.0
            leg_paid = paid * share
            leg_fee = fee * share
            price = (leg_paid / amount) if (amount and leg_paid > 0) else 0.0

            buys.append(
                {
                    "asset": asset,
                    "date": date,
                    "amount": amount,
                    "paid": leg_paid,
                    "fee": leg_fee,
                    "price": price,
                }
            )

    buys.sort(key=lambda r: r["date"])
    logger.info("Extracted %d buy transactions", len(buys))
    return buys


def extract_sells(entries: Dict[str, Any]) -> List[Dict[str, Any]]:
    """Pair asset-out legs with EUR-in legs per refid -> individual sell transactions."""
    sells = []
    for ref, items in _group_by_refid(entries).items():
        asset_legs = [
            i
            for i in items
            if i.get("asset") not in EUR_ASSETS and float(i.get("amount", 0)) < 0
        ]
        eur_legs = [
            i
            for i in items
            if i.get("asset") in EUR_ASSETS and float(i.get("amount", 0)) > 0
        ]

        if not asset_legs or not eur_legs:
            continue

        proceeds = sum(float(leg_item.get("amount", 0)) for leg_item in eur_legs)
        fee = sum(float(leg_item.get("fee", 0)) for leg_item in items)

        for leg in asset_legs:
            asset = normalize_asset(leg.get("asset"))
            amount = abs(float(leg.get("amount", 0)))
            if amount <= 0 or not asset:
                continue
            date = _entry_date(leg)
            if not date:
                logger.warning(
                    "Skipped sell with invalid date | refid=%s asset=%s", ref, asset
                )
                continue

            sells.append(
                {
                    "asset": asset,
                    "date": date,
                    "amount": amount,
                    "proceeds": proceeds,
                    "fee": fee,
                }
            )

    sells.sort(key=lambda r: r["date"])
    logger.info("Extracted %d sell transactions", len(sells))
    return sells


# ---------------------------------------------------------------------------
# FIFO CORE (direct port of applyBuyToState / applySellToState)
# ---------------------------------------------------------------------------


def _new_asset_state():
    return {
        "remaining_amount": 0.0,
        "remaining_cost": 0.0,
        "avg_price": 0.0,
        "latest_price": 0.0,
        "update_date": None,
        "total_paid": 0.0,
        "total_fee": 0.0,
    }


def _apply_buy(state: Dict[str, Any], buy: Dict[str, Any]):
    s = state.setdefault(buy["asset"], _new_asset_state())
    s["remaining_amount"] += buy["amount"]
    s["remaining_cost"] += buy["paid"] + buy["fee"]
    s["avg_price"] = (
        s["remaining_cost"] / s["remaining_amount"]
        if s["remaining_amount"] > 0
        else 0.0
    )
    s["total_paid"] += buy["paid"]
    s["total_fee"] += buy["fee"]

    if buy["price"] > 0 and (
        s["update_date"] is None or buy["date"] >= s["update_date"]
    ):
        s["latest_price"] = buy["price"]
        s["update_date"] = buy["date"]


def _apply_sell(state: Dict[str, Any], sell: Dict[str, Any]):
    s = state.get(sell["asset"])
    if not s:
        logger.warning("Sell skipped, asset not in FIFO state | %s", sell)
        return

    remaining = sell["amount"]
    while remaining > 0 and s["remaining_amount"] > 0:
        used = min(s["remaining_amount"], remaining)
        lot_price = s["avg_price"]
        s["remaining_amount"] -= used
        s["remaining_cost"] -= used * lot_price
        remaining -= used

    if s["remaining_amount"] > 0:
        s["avg_price"] = s["remaining_cost"] / s["remaining_amount"]
    else:
        s["remaining_amount"] = 0.0
        s["remaining_cost"] = 0.0
        s["avg_price"] = 0.0

    if remaining > 1e-8:
        logger.warning(
            "Sell overshoot for %s: sold %.8f more than FIFO remaining balance "
            "(missing buy history or bad data) | sell=%s",
            sell["asset"],
            remaining,
            sell,
        )


def _apply_buy_to_price_state(price_state: Dict[str, Any], buy: Dict[str, Any]):
    """EMA7 + regression accumulators, direct port of applyBuyToPriceState."""
    if buy["price"] <= 0:
        return
    ps = price_state.setdefault(
        buy["asset"],
        {
            "ema7": 0.0,
            "n": 0,
            "sumX": 0.0,
            "sumY": 0.0,
            "sumXX": 0.0,
            "sumXY": 0.0,
            "last_date": None,
        },
    )
    x = ps["n"]
    ps["ema7"] = (
        buy["price"] if ps["n"] == 0 else buy["price"] * (2 / 8) + ps["ema7"] * (6 / 8)
    )
    ps["sumX"] += x
    ps["sumY"] += buy["price"]
    ps["sumXX"] += x * x
    ps["sumXY"] += x * buy["price"]
    ps["n"] += 1
    if ps["last_date"] is None or buy["date"] > ps["last_date"]:
        ps["last_date"] = buy["date"]


def run_fifo(entries: Dict[str, Any]) -> pd.DataFrame:
    """
    Full-history FIFO recompute — NEVER pass a days-filtered entries dict here.
    Returns a DataFrame equivalent to the Google Sheets Summary tab (cols A-H).
    """
    if not entries:
        logger.warning("run_fifo called with empty entries")
        return pd.DataFrame()

    buys = extract_buys(entries)
    sells = extract_sells(entries)

    fifo_state: Dict[str, Any] = {}
    price_state: Dict[str, Any] = {}

    for b in buys:
        _apply_buy(fifo_state, b)
        _apply_buy_to_price_state(price_state, b)

    for s in sells:
        _apply_sell(fifo_state, s)

    rows = []
    for asset in sorted(fifo_state.keys()):
        st = fifo_state[asset]
        rows.append(
            {
                "asset": asset,
                "latest_price": st["latest_price"],
                "update_date": st["update_date"],
                "remaining_amount": st["remaining_amount"],
                "total_paid": st["total_paid"],
                "total_fee": st["total_fee"],
                "remaining_cost": st["remaining_cost"],
                "avg_price": st["avg_price"],
            }
        )

    df = pd.DataFrame(rows)
    df.attrs["price_state"] = price_state  # carried internally to forecast_prices()
    logger.info("run_fifo finished | assets=%d", len(df))
    return df


# ---------------------------------------------------------------------------
# FORECAST (direct port of forecastPrices)
# ---------------------------------------------------------------------------


def forecast_prices(summary_df: pd.DataFrame) -> pd.DataFrame:
    """EMA7 + linear regression 7d/30d forecast, appended as new columns."""
    if summary_df.empty:
        return summary_df

    price_state = summary_df.attrs.get("price_state", {})
    ema7_col, f7_col, f30_col = [], [], []

    for _, row in summary_df.iterrows():
        asset = row["asset"]
        avg_price = row["avg_price"] or 0.0
        ps = price_state.get(asset)

        if not ps or ps["n"] < 3:
            ema7_col.append(avg_price if avg_price > 0 else None)
            f7_col.append(None)
            f30_col.append(None)
            logger.warning(
                "Forecast fallback (n<3) for %s -> avgPrice=%s", asset, avg_price
            )
            continue

        n = ps["n"]
        den = n * ps["sumXX"] - ps["sumX"] ** 2
        slope = (n * ps["sumXY"] - ps["sumX"] * ps["sumY"]) / den if den else 0.0
        intercept = (ps["sumY"] - slope * ps["sumX"]) / n

        ema7_col.append(ps["ema7"])
        f7_col.append(intercept + slope * (n + 7))
        f30_col.append(intercept + slope * (n + 30))

    summary_df = summary_df.copy()
    summary_df["ema7"] = ema7_col
    summary_df["forecast_7d"] = f7_col
    summary_df["forecast_30d"] = f30_col
    logger.info("forecast_prices finished | rows=%d", len(summary_df))
    return summary_df


# ---------------------------------------------------------------------------
# PERSISTENCE — summary table, always INSERT OR REPLACE (disposable/derived)
# ---------------------------------------------------------------------------


def init_summary_table(conn: sqlite3.Connection):
    conn.execute(
        """
        CREATE TABLE IF NOT EXISTS summary (
            asset TEXT PRIMARY KEY,
            latest_price REAL,
            update_date TEXT,
            remaining_amount REAL,
            total_paid REAL,
            total_fee REAL,
            remaining_cost REAL,
            avg_price REAL,
            ema7 REAL,
            forecast_7d REAL,
            forecast_30d REAL,
            computed_at TEXT
        )
    """
    )
    conn.commit()


def save_summary(df: pd.DataFrame, db_path: str = None):
    """Overwrites the summary table content — fully derived/disposable output."""
    db_path = db_path or storage.LEDGER_DB_FILE
    conn = sqlite3.connect(db_path)
    try:
        init_summary_table(conn)
        conn.execute("DELETE FROM summary")

        now = datetime.now(timezone.utc).isoformat()
        out = df.copy()
        for col in ["ema7", "forecast_7d", "forecast_30d"]:
            if col not in out.columns:
                out[col] = None

        rows = [
            (
                r["asset"],
                r["latest_price"],
                (
                    r["update_date"].isoformat()
                    if pd.notna(r["update_date"]) and r["update_date"]
                    else None
                ),
                r["remaining_amount"],
                r["total_paid"],
                r["total_fee"],
                r["remaining_cost"],
                r["avg_price"],
                r["ema7"],
                r["forecast_7d"],
                r["forecast_30d"],
                now,
            )
            for _, r in out.iterrows()
        ]
        conn.executemany(
            """INSERT OR REPLACE INTO summary
               (asset, latest_price, update_date, remaining_amount, total_paid,
                total_fee, remaining_cost, avg_price, ema7, forecast_7d, forecast_30d, computed_at)
               VALUES (?,?,?,?,?,?,?,?,?,?,?,?)""",
            rows,
        )
        conn.commit()
        logger.info("Saved summary table | assets=%d", len(rows))
    finally:
        conn.close()


def update_summary() -> pd.DataFrame:
    """Convenience entrypoint mirroring update_asset_report()/update_sell_report()."""
    entries = storage.load_entries_from_db()
    if not entries:
        logger.warning("No data for portfolio summary")
        return pd.DataFrame()

    df = run_fifo(entries)  # full history, NEVER days-filtered
    df = forecast_prices(df)
    if not df.empty:
        save_summary(df)
    return df


if __name__ == "__main__":
    result_df = update_summary()
    print(result_df)
