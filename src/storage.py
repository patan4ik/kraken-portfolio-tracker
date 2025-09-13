# storage.py
import os
import json
import sqlite3
from typing import Dict, Any

BALANCES_DIR = "balances_history"
RAW_LEDGER_FILE = os.path.join(BALANCES_DIR, "raw-ledger.json")
LEDGER_DB_FILE = os.path.join(BALANCES_DIR, "ledger.db")
DB_FILE = LEDGER_DB_FILE


def init_db():
    """Создать таблицу ledger, если её нет."""
    os.makedirs(BALANCES_DIR, exist_ok=True)
    conn = sqlite3.connect(LEDGER_DB_FILE)
    cur = conn.cursor()
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger (
            txid TEXT PRIMARY KEY,
            refid TEXT,
            time REAL,
            type TEXT,
            asset TEXT,
            amount REAL,
            fee REAL,
            data TEXT
        )
        """
    )
    conn.commit()
    conn.close()


def load_entries() -> Dict[str, Any]:
    """Load ledger from JSON file (backup source)."""
    if not os.path.exists(RAW_LEDGER_FILE):
        return {}
    if os.path.getsize(RAW_LEDGER_FILE) == 0:  # ✅ если файл пустой
        return {}
    with open(RAW_LEDGER_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}


def save_entries(entries: Dict[str, Any]):
    """Сохранить ledger в JSON и в SQLite."""
    os.makedirs(BALANCES_DIR, exist_ok=True)

    # ---- JSON ----
    with open(RAW_LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    # ---- SQLite ----
    init_db()
    conn = sqlite3.connect(LEDGER_DB_FILE)
    cur = conn.cursor()

    for txid, entry in entries.items():
        cur.execute(
            """
            INSERT OR REPLACE INTO ledger
            (txid, refid, time, type, asset, amount, fee, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                txid,
                entry.get("refid"),
                float(entry.get("time", 0)),
                entry.get("type"),
                entry.get("asset"),
                float(entry.get("amount", 0)),
                float(entry.get("fee", 0)),
                json.dumps(entry, ensure_ascii=False),
            ),
        )

    conn.commit()
    conn.close()


def load_entries_from_db() -> Dict[str, Any]:
    """Load ledger entries directly from SQLite DB instead of JSON."""
    if not os.path.exists(LEDGER_DB_FILE):
        return {}

    conn = sqlite3.connect(LEDGER_DB_FILE)
    cur = conn.cursor()
    cur.execute("SELECT txid, data FROM ledger")
    rows = cur.fetchall()
    conn.close()

    entries: Dict[str, Any] = {}
    for txid, data_json in rows:
        try:
            entries[txid] = json.loads(data_json)
        except Exception:
            entries[txid] = {"raw": data_json}
    return entries
