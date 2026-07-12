# src/storage.py
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
UPDATE_LEDGER_FILE = os.path.join(BALANCES_DIR, "update-ledger.json")
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
    Save ledger entries to raw-ledger.json and to SQLite.
    Used by start.py during initialization (full save).
    IMPORTANT: if entries is empty -> skip to avoid accidental wipe.
    """
    if not entries:
        logger.warning("save_entries called with empty entries — skipping write.")
        return
    _ensure_dir()
    try:
        _backup_file(RAW_LEDGER_FILE)
    except Exception:
        pass
    try:
        _atomic_write_json(RAW_LEDGER_FILE, entries)
        logger.info("raw-ledger.json written (%d entries)", len(entries))
    except Exception as e:
        logger.exception("Failed to write raw-ledger.json: %s", e)
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


# ------------------ NEW: save_update_entries ------------------
def save_update_entries(entries: Dict[str, Any]) -> int:
    """
    Save incremental update entries to a separate JSON file (update-ledger.json)
    AND insert/replace those entries into the SQLite DB.

    Returns the number of *new* txids actually inserted (not counting
    already-present txids that were replaced).

    Safe to call multiple times — ensures:
      - all entries written atomically to update-ledger.json
      - DB always contains up-to-date records
      - returns count of newly inserted txids
    """
    if not entries:
        logger.info("save_update_entries called with empty entries — nothing to do.")
        return 0

    _ensure_dir()

    # --- Step 1: Backup and save JSON file ---
    try:
        _backup_file(UPDATE_LEDGER_FILE)
    except Exception:
        pass  # ignore missing old file

    try:
        _atomic_write_json(UPDATE_LEDGER_FILE, entries)
        logger.info("update-ledger.json written (%d entries)", len(entries))
    except Exception as e:
        logger.exception("Failed to write update-ledger.json: %s", e)

    # --- Step 2: Insert entries into SQLite DB ---
    inserted_new = 0
    conn = None

    try:
        init_db()
        conn = sqlite3.connect(LEDGER_DB_FILE)
        cur = conn.cursor()

        # Load only txid column (fast)
        cur.execute("SELECT txid FROM ledger")
        existing_txids = {r[0] for r in cur.fetchall()}

        for txid, entry in entries.items():
            # Convert timestamp to ISO date
            ts_val = 0.0
            if entry.get("time"):
                try:
                    ts_val = float(entry["time"])
                except Exception:
                    pass
            date_iso = None
            if ts_val:
                try:
                    date_iso = (
                        datetime.fromtimestamp(ts_val, tz=timezone.utc)
                        .date()
                        .isoformat()
                    )
                except Exception:
                    pass

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

            # count as new only if txid wasn't already in DB
            if txid not in existing_txids:
                inserted_new += 1

        conn.commit()
        logger.info(
            "Saved %d entries into ledger.db (new=%d)", len(entries), inserted_new
        )

    except sqlite3.Error as e:
        logger.exception("SQLite error while saving entries: %s", e)
    except Exception as e:
        logger.exception("Failed to save update entries into DB: %s", e)
    finally:
        if conn:
            conn.close()

    return inserted_new


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
    """Load ledger from raw-ledger.json (used by start.py)."""
    if not os.path.exists(RAW_LEDGER_FILE):
        return {}
    try:
        if os.path.getsize(RAW_LEDGER_FILE) == 0:
            return {}
    except Exception:
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
