# ledger_eur_report.py
import os
import logging
import time
from datetime import datetime
from typing import Dict, Any, List, DefaultDict
from collections import defaultdict

import pandas as pd

from ledger_loader import load_raw_ledger, update_raw_ledger, BALANCES_DIR

LEDGER_EUR_FILE = os.path.join(BALANCES_DIR, "ledger_eur_report.csv")
logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )


EUR_ASSETS = {"ZEUR", "EUR"}


def build_eur_report(entries: Dict[str, Any], days: int = 7) -> pd.DataFrame:
    """
    Build a DataFrame:
    Date; Total Fee; Total Spent EUR; <asset columns (EUR spent per asset)>
    entries: dict(txid -> entry)
    """
    if not entries:
        return pd.DataFrame()

    cutoff = time.time() - days * 86400
    # keep only relevant records (type receive/spend) within cutoff
    filtered = {}
    for txid, e in entries.items():
        try:
            ts = float(e.get("time", 0))
        except Exception:
            continue
        typ = (e.get("type") or "").lower()
        if ts >= cutoff and typ in {"receive", "spend"}:
            out = dict(e)
            out["_txid"] = txid
            out["_time"] = ts
            out["_type"] = typ
            out["_asset"] = out.get("asset")
            filtered[txid] = out

    if not filtered:
        return pd.DataFrame()

    # group by refid (fallback to txid)
    groups: DefaultDict[str, List[Dict[str, Any]]] = defaultdict(list)
    for txid, e in filtered.items():
        ref = e.get("refid") or txid
        groups[ref].append(e)

    # accumulate per date
    daily: Dict[str, Dict[str, Any]] = {}

    for ref, items in groups.items():
        # find spends in EUR and receives (non-eur)
        spends = [
            it
            for it in items
            if it["_type"] == "spend" and (it.get("asset") in EUR_ASSETS)
        ]
        receives = [
            it
            for it in items
            if it["_type"] == "receive" and (it.get("asset") not in EUR_ASSETS)
        ]

        if not spends:
            # no EUR spent -> skip (not a fiat buy)
            continue
        if not receives:
            # no receive -> nothing to assign to asset columns (skip)
            continue

        # choose timestamp and date from first spend
        ts = float(spends[0]["_time"])
        # date = datetime.fromtimestamp(ts, datetime.UTC).strftime("%d.%m.%Y")
        date = datetime.utcfromtimestamp(ts).strftime(
            "%d.%m.%Y"
        )  # Python is warning that this method is deprecated

        total_spent = sum(
            [-float(s.get("amount", 0)) for s in spends]
        )  # amounts likely negative -> invert
        total_fee = sum([float(s.get("fee", 0)) for s in spends])

        # allocate spent EUR to receive assets:
        # if single receive asset => full assign; else proportional to absolute receive amounts
        recv_amounts = []
        for r in receives:
            try:
                recv_amounts.append(abs(float(r.get("amount", 0))))
            except Exception:
                recv_amounts.append(0.0)
        total_recv_amount = sum(recv_amounts) if recv_amounts else 0.0

        alloc: Dict[str, float] = {}
        if total_recv_amount > 0 and len(receives) > 1:
            # proportional split
            for r, amt in zip(receives, recv_amounts):
                asset = r.get("asset")
                alloc[asset] = alloc.get(asset, 0.0) + (
                    total_spent * (amt / total_recv_amount)
                    if total_recv_amount
                    else 0.0
                )
        else:
            # single receive or zero-sum -> attribute full amount to first receive asset
            first_asset = receives[0].get("asset")
            alloc[first_asset] = alloc.get(first_asset, 0.0) + total_spent

        # add to daily accumulator
        if date not in daily:
            daily[date] = {"Date": date, "Total Fee": 0.0, "Total Spent EUR": 0.0}
        daily_row = daily[date]
        daily_row["Total Fee"] = daily_row.get("Total Fee", 0.0) + total_fee
        daily_row["Total Spent EUR"] = (
            daily_row.get("Total Spent EUR", 0.0) + total_spent
        )
        for asset, eur_val in alloc.items():
            daily_row[asset] = daily_row.get(asset, 0.0) + eur_val

    if not daily:
        return pd.DataFrame()

    # build dataframe rows and unify columns
    rows = list(daily.values())
    df = pd.DataFrame(rows)
    # ensure asset columns exist and fill NaNs with 0
    # determine full set of assets
    assets = sorted(
        [c for c in df.columns if c not in {"Date", "Total Fee", "Total Spent EUR"}]
    )
    ordered_cols = ["Date", "Total Fee", "Total Spent EUR"] + assets
    df = df.reindex(columns=ordered_cols).fillna(0.0)

    # sort by date ascending
    df["__sort_dt"] = pd.to_datetime(df["Date"], format="%d.%m.%Y", errors="coerce")
    df.sort_values("__sort_dt", inplace=True)
    df.drop(columns="__sort_dt", inplace=True)

    # round numeric columns to 2 decimals for money, 8 for asset units not used here (we store EUR)
    df["Total Fee"] = df["Total Fee"].round(2)
    df["Total Spent EUR"] = df["Total Spent EUR"].round(2)
    # round assets as money (EUR per asset)
    for a in assets:
        df[a] = df[a].round(2)

    return df


def save_eur_report(df: pd.DataFrame):
    os.makedirs(BALANCES_DIR, exist_ok=True)
    df.to_csv(LEDGER_EUR_FILE, sep=";", index=False, encoding="utf-8")
    logger.info(f"EUR report saved to {LEDGER_EUR_FILE}")


def update_eur_report(days: int = 7):
    """
    Update raw ledger and then build EUR report for last `days` days.
    """
    logger.info("Обновляю raw ledger...")
    # update raw ledger (loader will create api if needed)
    try:
        update_raw_ledger(days=days)
    except Exception as exc:
        logger.exception("Ошибка при обновлении raw ledger: %s", exc)
        # continue — maybe there is still existing raw-ledger to build from

    raw = load_raw_ledger()
    if not raw:
        logger.warning("Нет записей для отчёта EUR.")
        return

    df = build_eur_report(raw, days=days)
    if df.empty:
        logger.warning("Данные пусты, отчёт не будет обновлён.")
        return

    save_eur_report(df)
    logger.info("EUR report updated.")
    logger.info("\n%s", df.tail())
