# storage.py (patch)
import os
import json
import sqlite3
from typing import Dict, Any
from datetime import datetime, timezone

BALANCES_DIR = "balances_history"
RAW_LEDGER_FILE = os.path.join(BALANCES_DIR, "raw-ledger.json")
LEDGER_DB_FILE = os.path.join(BALANCES_DIR, "ledger.db")
DB_FILE = LEDGER_DB_FILE


def init_db():
    """Create ledger table if it doesn't exist and ensure date_iso column exists."""
    os.makedirs(BALANCES_DIR, exist_ok=True)
    conn = sqlite3.connect(LEDGER_DB_FILE)
    cur = conn.cursor()

    # Create the table with date_iso column (if table doesn't exist yet)
    cur.execute(
        """
        CREATE TABLE IF NOT EXISTS ledger (
            txid TEXT PRIMARY KEY,
            refid TEXT,
            time REAL,
            date_iso TEXT,
            type TEXT,
            asset TEXT,
            amount REAL,
            fee REAL,
            data TEXT
        )
        """
    )
    conn.commit()

    # Defensive: if older DB existed without date_iso column, add it.
    cur.execute("PRAGMA table_info(ledger)")
    cols = [r[1] for r in cur.fetchall()]
    if "date_iso" not in cols:
        cur.execute("ALTER TABLE ledger ADD COLUMN date_iso TEXT")
        conn.commit()

    conn.close()


def save_entries(entries: Dict[str, Any]):
    """Save ledger to JSON file and insert into SQLite with a computed ISO date."""
    os.makedirs(BALANCES_DIR, exist_ok=True)

    # write JSON backup
    with open(RAW_LEDGER_FILE, "w", encoding="utf-8") as f:
        json.dump(entries, f, indent=2, ensure_ascii=False)

    # write to SQLite
    init_db()
    conn = sqlite3.connect(LEDGER_DB_FILE)
    cur = conn.cursor()

    for txid, entry in entries.items():
        # compute canonical ISO date from the timestamp (UTC)
        try:
            ts = float(entry.get("time", 0))
            date_iso = datetime.fromtimestamp(ts, tz=timezone.utc).date().isoformat()
        except Exception:
            date_iso = None

        cur.execute(
            """
            INSERT OR REPLACE INTO ledger
            (txid, refid, time, date_iso, type, asset, amount, fee, data)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                txid,
                entry.get("refid"),
                float(entry.get("time", 0)),
                date_iso,
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
    """Load ledger entries from SQLite and return dict(txid -> entry dict).
    If `date_iso` column exists, add it as entry['date'].
    """
    if not os.path.exists(LEDGER_DB_FILE):
        return {}

    conn = sqlite3.connect(LEDGER_DB_FILE)
    cur = conn.cursor()

    # Query date_iso if present (defensive select)
    # We attempt to select date_iso, but if not present SELECT will fail; handle that.
    try:
        cur.execute("SELECT txid, data, date_iso FROM ledger")
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        # fallback to older schema with only data
        cur.execute("SELECT txid, data FROM ledger")
        rows = cur.fetchall()
        rows = [(r[0], r[1], None) for r in rows]

    conn.close()

    entries: Dict[str, Any] = {}
    for txid, data_json, date_iso in rows:
        try:
            obj = json.loads(data_json)
        except Exception:
            obj = {"raw": data_json}
        # attach canonical date (if available)
        if date_iso:
            obj["date"] = date_iso
        entries[txid] = obj
    return entries


def load_entries() -> Dict[str, Any]:
    """Load ledger from JSON file (backup source)."""
    if not os.path.exists(RAW_LEDGER_FILE):
        return {}
    if os.path.getsize(RAW_LEDGER_FILE) == 0:
        return {}
    with open(RAW_LEDGER_FILE, "r", encoding="utf-8") as f:
        try:
            return json.load(f)
        except json.JSONDecodeError:
            return {}
