# src/keys.py
import os
import json
import logging
from cryptography.fernet import Fernet, InvalidToken
from appdirs import user_data_dir
from typing import Tuple

logger = logging.getLogger(__name__)

APP_NAME = "kraken-portfolio-tracker"
DATA_DIR = user_data_dir(APP_NAME)
os.makedirs(DATA_DIR, exist_ok=True)

KEYFILE = os.path.join(DATA_DIR, "kraken.key")  # encrypted API keys
MASTER_FILE = os.path.join(DATA_DIR, ".master")  # master key file


class KeysError(Exception):
    pass


# ---------------- Master Key ---------------- #


def _get_master_key(create_if_missing: bool = False) -> bytes:
    """Load or create a master key for Fernet encryption."""
    if os.path.exists(MASTER_FILE):
        mk = open(MASTER_FILE, "rb").read().strip()
        try:
            Fernet(mk)  # validate
            return mk
        except Exception:
            raise KeysError("❌ Corrupted master key file (.master)")

    if not create_if_missing:
        raise KeysError("❌ Master key missing. Run with --setup-keys to create it.")

    # Generate new key
    mk = Fernet.generate_key()
    with open(MASTER_FILE, "wb") as f:
        try:
            os.fchmod(f.fileno(), 0o600)
        except Exception:
            pass
        f.write(mk)
    return mk


def _get_fernet(create_if_missing: bool = False) -> Fernet:
    return Fernet(_get_master_key(create_if_missing))


# ---------------- API Keys ---------------- #


def save_keys(api_key: str, api_secret: str):
    """Encrypt and save API keys to KEYFILE, creating master if needed."""
    f = _get_fernet(create_if_missing=True)
    payload = json.dumps(
        {"api_key": api_key.strip(), "api_secret": api_secret.strip()}
    ).encode()
    token = f.encrypt(payload)

    with open(KEYFILE, "wb") as fh:
        try:
            os.fchmod(fh.fileno(), 0o600)
        except Exception:
            pass
        fh.write(token)

    logger.info("✅ API keys saved successfully to %s", KEYFILE)


def load_keys() -> Tuple[str, str]:
    """Load API keys from encrypted file, plaintext fallback, or env vars."""
    # 1. Encrypted file
    if os.path.exists(KEYFILE):
        token = open(KEYFILE, "rb").read()
        try:
            f = _get_fernet(create_if_missing=False)
            raw = f.decrypt(token)
            dd = json.loads(raw.decode("utf-8"))

            # Ensure secret is properly base64-padded
            api_secret = dd["api_secret"].strip()
            missing_padding = len(api_secret) % 4
            if missing_padding:
                api_secret += "=" * (4 - missing_padding)

            return dd["api_key"].strip(), api_secret
        except InvalidToken:
            raise KeysError("❌ Cannot decrypt kraken.key – master key mismatch.")
        except KeysError:
            raise
        except Exception as e:
            raise KeysError(f"❌ Failed to load encrypted kraken.key: {e}")

    # 2. Plaintext fallback
    legacy = os.path.join(os.getcwd(), "kraken.key")
    if os.path.exists(legacy):
        lines = [
            line.strip() for line in open(legacy).read().splitlines() if line.strip()
        ]
        if len(lines) >= 2:
            return lines[0], lines[1]

    # 3. Environment variables
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    if api_key and api_secret:
        return api_key.strip(), api_secret.strip()

    raise KeysError("❌ API keys not found. Run: python start.py --setup-keys")


# try load existing keys
def keys_exist() -> bool:
    try:
        load_keys()
        return True
    except Exception:
        return False
