# src/keys.py
import os
import json
import keyring
from cryptography.fernet import Fernet
from appdirs import user_data_dir
from typing import Tuple, Optional

APP_NAME = "kraken-portfolio-tracker"
_SERVICE = f"{APP_NAME}-kraken-api"

DATA_DIR = user_data_dir(APP_NAME)
os.makedirs(DATA_DIR, exist_ok=True)

KEYFILE = os.path.join(DATA_DIR, "kraken.key")  # encrypted API keys
MASTER_FILE = os.path.join(DATA_DIR, ".master")  # local master key backup


class KeysError(Exception):
    """Raised when API keys are missing or invalid."""

    pass


# ---------------- Master Key Management ---------------- #


def _derive_master_key_from_keyring() -> Optional[bytes]:
    """Try to fetch master key from system keyring."""
    val = keyring.get_password(_SERVICE, "master")
    if not val:
        return None
    try:
        Fernet(val.encode("utf-8"))  # validate
        return val.encode("utf-8")
    except Exception:
        return None


def _store_master_key_in_keyring(key: bytes):
    """Store master key in keyring."""
    keyring.set_password(_SERVICE, "master", key.decode("utf-8"))


def _store_master_key_in_file(key: bytes):
    """Store master key in .master file (0600 permissions)."""
    with open(MASTER_FILE, "wb") as f:
        try:
            os.fchmod(f.fileno(), 0o600)
        except AttributeError:
            pass  # Windows doesn't support fchmod
        f.write(key)


def _load_master_key_from_file() -> Optional[bytes]:
    """Load master key from local .master file."""
    if os.path.exists(MASTER_FILE):
        mk = open(MASTER_FILE, "rb").read()
        try:
            Fernet(mk)  # validate
            return mk
        except Exception:
            raise KeysError("❌ Corrupted master key file (.master)")
    return None


def _get_master_key() -> bytes:
    """
    Get the Fernet master key.
    Priority:
      1. Keyring
      2. .master file
      3. Generate new -> store in both
    """
    # 1. Keyring
    mk = _derive_master_key_from_keyring()
    if mk:
        return mk

    # 2. Local file
    mk = _load_master_key_from_file()
    if mk:
        return mk

    # 3. Generate new key and store in both
    mk = Fernet.generate_key()
    try:
        _store_master_key_in_keyring(mk)
    except Exception:
        # fallback only .master
        _store_master_key_in_file(mk)
    else:
        # also keep backup file
        _store_master_key_in_file(mk)

    return mk


def _get_fernet() -> Fernet:
    """Return a Fernet instance bound to the master key."""
    return Fernet(_get_master_key())


# ---------------- API Keys Management ---------------- #


def save_keys(api_key: str, api_secret: str):
    """Encrypt and save Kraken API keys securely."""
    f = _get_fernet()
    payload = json.dumps({"api_key": api_key, "api_secret": api_secret}).encode("utf-8")
    token = f.encrypt(payload)

    with open(KEYFILE, "wb") as fh:
        try:
            os.fchmod(fh.fileno(), 0o600)
        except AttributeError:
            pass
        fh.write(token)

    keyring.set_password(_SERVICE, "saved", "1")


def load_keys() -> Tuple[str, str]:
    """Load Kraken API keys from encrypted file, legacy file, or env vars."""
    # 1. Encrypted keyfile
    if os.path.exists(KEYFILE):
        try:
            token = open(KEYFILE, "rb").read()
            f = _get_fernet()
            raw = f.decrypt(token)
            dd = json.loads(raw.decode("utf-8"))
            return dd["api_key"], dd["api_secret"]
        except Exception:
            raise KeysError(
                "❌ Encrypted kraken.key exists but cannot be decrypted. "
                "Master key missing or corrupted."
            )

    # 2. Legacy plain text file
    legacy = os.path.join(os.getcwd(), "kraken.key")
    if os.path.exists(legacy):
        with open(legacy, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.read().splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]

    # 3. Environment variables
    api_key = os.getenv("KRAKEN_API_KEY")
    api_secret = os.getenv("KRAKEN_API_SECRET")
    if api_key and api_secret:
        return api_key, api_secret

    # Nothing found
    raise KeysError(
        "❌ Kraken API keys not found.\n"
        "1) Run: python start.py --setup-keys   (recommended)\n"
        "2) Or store them securely using keys.py helper:\n"
        "   python -c \"from keys import save_keys; save_keys('API_KEY','API_SECRET')\"\n"
        "3) Or create a file kraken.key with two lines: <API key> and <API secret>\n"
        "4) Or set environment variables KRAKEN_API_KEY and KRAKEN_API_SECRET\n"
        "After that, restart the script."
    )


def keys_exist() -> bool:
    """Return True if API keys can be loaded, else False."""
    try:
        load_keys()
        return True
    except Exception:
        return False
