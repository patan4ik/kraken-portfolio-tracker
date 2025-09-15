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
KEYFILE = os.path.join(DATA_DIR, "kraken.key")  # encrypted JSON or plainlines


def _derive_master_key_from_keyring() -> Optional[bytes]:
    """Try to get a master key from OS keyring; if not present return None."""
    val = keyring.get_password(_SERVICE, "master")
    if val:
        return val.encode("utf-8")
    return None


def _store_master_key_in_keyring(key: bytes):
    keyring.set_password(_SERVICE, "master", key.decode("utf-8"))


def _prompt_and_create_master_key() -> bytes:
    # Generate new master key (Fernet) and store in keyring if possible
    new_key = Fernet.generate_key()
    try:
        _store_master_key_in_keyring(new_key)
    except Exception:
        # If keyring fails (headless), fallback to writing the key to a local file with restricted permissions
        keypath = os.path.join(DATA_DIR, ".master")
        with open(keypath, "wb") as f:
            os.fchmod(f.fileno(), 0o600)
            f.write(new_key)
    return new_key


def _get_fernet() -> Fernet:
    mk = _derive_master_key_from_keyring()
    if mk is None:
        # try local file
        local_keyfile = os.path.join(DATA_DIR, ".master")
        if os.path.exists(local_keyfile):
            mk = open(local_keyfile, "rb").read()
        else:
            mk = _prompt_and_create_master_key()
    return Fernet(mk)


def save_keys(api_key: str, api_secret: str):
    """
    Save keys encrypted (preferred) and also store a small hint in keyring.
    """
    f = _get_fernet()
    payload = json.dumps({"api_key": api_key, "api_secret": api_secret}).encode("utf-8")
    token = f.encrypt(payload)
    with open(KEYFILE, "wb") as fh:
        os.fchmod(fh.fileno(), 0o600)
        fh.write(token)
    # Optionally store last-used username in keyring as metadata (not secrets)
    keyring.set_password(_SERVICE, "saved", "1")


def load_keys() -> Tuple[str, str]:
    """
    Load keys: tries keyring -> encrypted file -> legacy plain kraken.key in repo root.
    Raises RuntimeError with user friendly instructions.
    """
    # 1) Try keyring username/secret (rare, keyring usually stores single password, so better to use file)
    # Here we expect keyring usage for master key, not API keys

    # 2) Try encrypted KEYFILE
    if os.path.exists(KEYFILE):
        try:
            token = open(KEYFILE, "rb").read()
            f = _get_fernet()
            raw = f.decrypt(token)
            dd = json.loads(raw.decode("utf-8"))
            return dd["api_key"], dd["api_secret"]
        except Exception:
            raise RuntimeError(
                "Encrypted kraken.key exists but cannot be decrypted. Maybe master key missing or corrupted."
            )

    # 3) Legacy: kraken.key in CWD (two-line plain text) — only as last resort
    legacy = os.path.join(os.getcwd(), "kraken.key")
    if os.path.exists(legacy):
        with open(legacy, "r", encoding="utf-8") as f:
            lines = [line.strip() for line in f.read().splitlines() if line.strip()]
        if len(lines) >= 2:
            return lines[0], lines[1]

    # No keys found — instruct the user
    raise RuntimeError(
        "API keys not found. Create keys using the UI or place encrypted keys at: "
        f"{KEYFILE} or put a two-line kraken.key in the current directory.\n"
        "To save keys securely use the included helper: python -c \"from keys import save_keys; save_keys('API_KEY','API_SECRET')\""
    )
