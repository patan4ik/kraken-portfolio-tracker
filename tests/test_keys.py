# tests/test_keys.py
import json
import pytest
from pathlib import Path
from cryptography.fernet import Fernet
import src.keys as keys


@pytest.fixture(autouse=True)
def clean_env(tmp_path, monkeypatch):
    """Каждый тест работает в изолированной директории."""
    monkeypatch.setattr(keys, "DATA_DIR", str(tmp_path))
    monkeypatch.setattr(keys, "KEYFILE", str(tmp_path / "kraken.key"))
    monkeypatch.setattr(keys, "MASTER_FILE", str(tmp_path / ".master"))
    yield
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)


def test_save_and_load_keys(tmp_path):
    keys.save_keys("API123", "SECRET456")
    api_key, api_secret = keys.load_keys()
    assert api_key == "API123"
    assert api_secret.startswith("SECRET456")
    assert Path(keys.KEYFILE).exists()
    assert Path(keys.MASTER_FILE).exists()


def test_snapshot_encrypted_file(tmp_path):
    """Убеждаемся, что kraken.key не хранит JSON в открытом виде."""
    keys.save_keys("SNAPKEY", "SNAPSECRET")

    content = Path(keys.KEYFILE).read_bytes()
    text_preview = content[:50]  # первые байты, не всё

    # Должно выглядеть как Fernet-токен (base64, начинается с b'gAAAA')
    assert content.startswith(b"gAAAA")

    # Внутри НЕ должно быть открытого текста ключей
    assert b"SNAPKEY" not in content
    assert b"SNAPSECRET" not in content
    assert b"{" not in text_preview and b"}" not in text_preview


def test_load_keys_missing_master_raises(tmp_path):
    fernet = Fernet(Fernet.generate_key())
    token = fernet.encrypt(json.dumps({"api_key": "x", "api_secret": "y"}).encode())
    Path(keys.KEYFILE).write_bytes(token)
    with pytest.raises(keys.KeysError):
        keys.load_keys()


def test_load_keys_plaintext_fallback(tmp_path, monkeypatch):
    legacy = tmp_path / "kraken.key"
    legacy.write_text("PLAINKEY\nPLAINSECRET\n", encoding="utf-8")
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr(keys, "KEYFILE", str(tmp_path / "nonexistent"))
    k, s = keys.load_keys()
    assert k == "PLAINKEY"
    assert s == "PLAINSECRET"


def test_load_keys_env_fallback(monkeypatch):
    monkeypatch.setenv("KRAKEN_API_KEY", "ENVKEY")
    monkeypatch.setenv("KRAKEN_API_SECRET", "ENVSECRET")
    monkeypatch.setattr(keys, "KEYFILE", "nonexistent")
    k, s = keys.load_keys()
    assert k == "ENVKEY"
    assert s == "ENVSECRET"


def test_keys_exist_returns_true_after_save():
    keys.save_keys("EXISTKEY", "EXISTSECRET")
    assert keys.keys_exist()


def test_keys_exist_returns_false_without_files(monkeypatch):
    monkeypatch.setattr(keys, "KEYFILE", "nonexistent")
    monkeypatch.setattr(keys, "MASTER_FILE", "nonexistent")
    assert keys.keys_exist() is False


def test_corrupted_master_file(tmp_path):
    Path(keys.MASTER_FILE).write_bytes(b"not-a-valid-fernet-key")
    with pytest.raises(keys.KeysError):
        keys._get_master_key()


def test_corrupted_encrypted_keyfile(tmp_path):
    mk = Fernet.generate_key()
    Path(keys.MASTER_FILE).write_bytes(mk)
    Path(keys.KEYFILE).write_bytes(b"not-a-valid-token")
    with pytest.raises(keys.KeysError):
        keys.load_keys()
