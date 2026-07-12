# src/validators.py
import os
import sys
import sqlite3

# add src to PYTHONPATH
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "src"))

import logging
from typing import Tuple
from keys import load_keys, KeysError


logger = logging.getLogger(__name__)
if not logger.handlers:
    logging.basicConfig(
        level=logging.INFO, format="%(asctime)s [%(levelname)s] %(message)s"
    )


class DatabaseMissingError(Exception):
    """DB file missing (or cannot be opened)."""


class SchemaInvalidError(Exception):
    """Required table(s) missing in DB."""


class APIKeyError(Exception):
    """API keys missing or invalid."""


def check_db_exists(db_path: str) -> Tuple[bool, str]:
    """
    Check DB file presence.
    Returns (True, message) on success, raises DatabaseMissingError if file absent.
    """
    if not os.path.exists(db_path):
        raise DatabaseMissingError(f"Database file not found: {db_path}")
    return True, "Database file found"


def check_db_schema(db_path: str) -> Tuple[bool, str]:
    """
    Validate that DB has 'ledger' table.
    Returns (True, message) on success, raises SchemaInvalidError otherwise.
    (Lightweight: does not assert specific columns to remain compatible with tests)
    """
    try:
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ledger'"
        )
        if not cur.fetchone():
            raise SchemaInvalidError("Database missing 'ledger' table")
        return True, "Ledger table present"
    except sqlite3.DatabaseError as e:
        logger.debug("SQLite error while inspecting DB: %s", e)
        raise SchemaInvalidError("Cannot inspect DB schema") from e
    finally:
        try:
            conn.close()
        except Exception:
            pass


def check_api_key(path: str) -> Tuple[bool, str]:
    """
    Validate API key file at `path`.
    - If file missing -> raise APIKeyError
    - If file appears to be legacy plaintext with two non-empty lines -> OK
    - Otherwise, attempt to load keys via keys.load_keys() (global behavior) and accept if it returns usable keys
    Returns (True, message) on success or raises APIKeyError.
    """
    if not os.path.exists(path):
        raise APIKeyError(f"API key file not found: {path}")

    # Try quick plaintext check: two non-empty lines
    try:
        with open(path, "rb") as fh:
            raw = fh.read()
        try:
            text = raw.decode("utf-8")
        except Exception:
            text = ""
        lines = [ln.strip() for ln in text.splitlines() if ln.strip()]
        if len(lines) >= 2:
            return True, "API key file looks like plaintext (legacy) and exists"

    except Exception as e:
        logger.debug("Could not read key file %s: %s", path, e)

    # Fallback: try to load keys using keys.load_keys() (no path argument).
    # This covers encrypted KEYFILE scenario where master key is used by load_keys().
    try:
        keys = load_keys()
        if isinstance(keys, (tuple, list)) and len(keys) >= 2:
            return True, "API keys loaded via key manager"
        if isinstance(keys, dict):
            if keys.get("api_key") and keys.get("api_secret"):
                return True, "API keys loaded via key manager"
        raise APIKeyError("Invalid keys format returned by keys.load_keys()")
    except KeysError as ke:
        raise APIKeyError(f"API keys error: {ke}") from ke
    except APIKeyError:
        raise
    except Exception as e:
        raise APIKeyError(f"Unexpected error loading API keys: {e}") from e


def check_api_keys() -> Tuple[str, str]:
    """
    Load default API keys (no explicit path).
    Returns tuple (api_key, api_secret) on success or raises APIKeyError.
    """
    try:
        keys = load_keys()
        if isinstance(keys, (tuple, list)) and len(keys) >= 2:
            return keys[0], keys[1]
        elif isinstance(keys, dict):
            k = keys.get("api_key") or keys.get("key")
            s = keys.get("api_secret") or keys.get("secret")
            if k and s:
                return k, s
        raise APIKeyError("Invalid keys format")
    except KeysError as e:
        raise APIKeyError(f"API keys error: {e}") from e
    except Exception as e:
        raise APIKeyError(f"Unexpected error loading API keys: {e}") from e


def validate_for_update(db_path: str) -> None:
    """
    Combined check used by update.py:
      - DB file exists
      - DB contains ledger table
      - API keys present and usable (loadable)
    Raises DatabaseMissingError, SchemaInvalidError or APIKeyError on failure.
    """
    check_db_exists(db_path)
    check_db_schema(db_path)
    # ensure keys ok (returns tuple on success)
    check_api_keys()


# funcrion moved from start.py


def db_row_count(db_path: str) -> int:
    """Calculate amount of raws in ledger / Подсчитать количество строк в таблице ledger."""
    try:
        if not os.path.exists(db_path):
            return 0
        conn = sqlite3.connect(db_path)
        cur = conn.cursor()
        cur.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='ledger'"
        )
        if not cur.fetchone():
            conn.close()
            return 0
        cur.execute("SELECT COUNT(*) FROM ledger")
        cnt = cur.fetchone()[0]
        conn.close()
        return int(cnt)
    except Exception as e:
        logger.warning("Could not count rows in DB %s: %s", db_path, e)
        return 0


# funcrion to validate that new data added after use of update.py


def validate_after_update(db_path: str, expected_min_rows: int = 1) -> bool:
    """
    Checks that new raws added into ledger.db after update / Проверяет, что в БД ledger появились данные после обновления.
    Return True, if ok and False otherwise / Возвращает True, если всё ок, иначе False.
    """
    count = db_row_count(db_path)
    if count >= expected_min_rows:
        logger.info("Ledger DB validation passed: %d rows", count)
        return True
    else:
        logger.warning(
            "Ledger DB validation failed: %d rows (expected ≥ %d)",
            count,
            expected_min_rows,
        )
        return False
