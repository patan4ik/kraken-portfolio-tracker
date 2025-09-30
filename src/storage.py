# storage.py
import os
import json
import sqlite3
import tempfile
import shutil
import logging
from typing import Dict, Any
from datetime import datetime, timezone

logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )

BALANCES_DIR = "balances_history"
RAW_LEDGER_FILE = os.path.join(BALANCES_DIR, "raw-ledger.json")
LEDGER_DB_FILE = os.path.join(BALANCES_DIR, "ledger.db")
DB_FILE = LEDGER_DB_FILE


def _ensure_dir():
    os.makedirs(BALANCES_DIR, exist_ok=True)


def _backup_file(path: str):
    """Create a timestamped backup of path (if exists)."""
    try:
        if os.path.exists(path):
            ts = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
            backup = f"{path}.bak.{ts}"
            shutil.copy2(path, backup)
            logger.info("Backup created: %s", backup)
    except Exception as e:
        logger.warning("Failed to backup %s: %s", path, e)


def init_db():
    """Create ledger table if it doesn't exist and ensure date_iso column exists."""
    _ensure_dir()
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
        try:
            cur.execute("ALTER TABLE ledger ADD COLUMN date_iso TEXT")
            conn.commit()
            logger.info("Added missing column date_iso to ledger table")
        except Exception as e:
            logger.warning("Could not add date_iso column: %s", e)

    conn.close()


def _atomic_write_json(path: str, data: Dict[str, Any]):
    """Write JSON atomically into `path`."""
    _ensure_dir()
    dirn = os.path.dirname(path) or "."
    fd = None
    tmp_path = None
    try:
        fd, tmp_path = tempfile.mkstemp(
            prefix=os.path.basename(path) + ".tmp", dir=dirn
        )
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)
            f.flush()
            os.fsync(f.fileno())
        os.replace(tmp_path, path)  # atomic replace
    finally:
        if tmp_path and os.path.exists(tmp_path):
            try:
                os.remove(tmp_path)
            except Exception:
                pass


def save_entries(entries: Dict[str, Any]):
    """
    Save ledger entries to JSON backup and to SQLite.
    IMPORTANT: if entries is empty -> skip to avoid accidental wipe.
    """
    if not entries:
        logger.warning("save_entries called with empty entries — skipping write.")
        return

    _ensure_dir()

    # backup existing raw JSON (if any)
    try:
        _backup_file(RAW_LEDGER_FILE)
    except Exception:
        pass

    # atomic write JSON backup
    try:
        _atomic_write_json(RAW_LEDGER_FILE, entries)
        logger.info("raw-ledger.json written (%d entries)", len(entries))
    except Exception as e:
        logger.exception("Failed to write raw-ledger.json: %s", e)
        # don't stop — continue to DB write attempt

    # ---- SQLite ----
    try:
        init_db()
        conn = sqlite3.connect(LEDGER_DB_FILE)
        cur = conn.cursor()

        for txid, entry in entries.items():
            try:
                ts_val = float(entry.get("time", 0))
            except Exception:
                ts_val = 0.0
            try:
                date_iso = (
                    datetime.fromtimestamp(ts_val, tz=timezone.utc).date().isoformat()
                    if ts_val
                    else None
                )
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
                    ts_val,
                    date_iso,
                    entry.get("type"),
                    entry.get("asset"),
                    float(entry.get("amount", 0)),
                    float(entry.get("fee", 0)),
                    json.dumps(entry, ensure_ascii=False),
                ),
            )

        conn.commit()
        logger.info("Saved %d entries into ledger.db", len(entries))
    except Exception as e:
        logger.exception("Failed to save entries into DB: %s", e)
    finally:
        try:
            conn.close()
        except Exception:
            pass


def load_entries_from_db() -> Dict[str, Any]:
    """
    Load ledger entries from SQLite and return dict(txid -> entry dict).
    If `date_iso` column exists, add it as entry['date'].
    """
    if not os.path.exists(LEDGER_DB_FILE):
        return {}

    conn = sqlite3.connect(LEDGER_DB_FILE)
    cur = conn.cursor()

    try:
        cur.execute("SELECT txid, data, date_iso FROM ledger")
        rows = cur.fetchall()
    except sqlite3.OperationalError:
        # fallback to older schema with only data
        cur.execute("SELECT txid, data FROM ledger")
        rows_raw = cur.fetchall()
        rows = [(r[0], r[1], None) for r in rows_raw]

    conn.close()

    entries: Dict[str, Any] = {}
    for txid, data_json, date_iso in rows:
        try:
            obj = json.loads(data_json)
        except Exception:
            obj = {"raw": data_json}
        if date_iso:
            obj["date"] = date_iso
        entries[txid] = obj
    return entries


def load_entries() -> Dict[str, Any]:
    """Load ledger from JSON file (backup source)."""
    if not os.path.exists(RAW_LEDGER_FILE):
        return {}
    try:
        if os.path.getsize(RAW_LEDGER_FILE) == 0:
            return {}
    except Exception:
        # can't stat file for some reason; try reading and handle JSON errors
        pass

    try:
        with open(RAW_LEDGER_FILE, "r", encoding="utf-8") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.warning(
            "raw-ledger.json is present but invalid JSON; returning empty dict"
        )
        return {}
    except Exception as e:
        logger.exception("Unexpected error reading raw-ledger.json: %s", e)
        return {}
