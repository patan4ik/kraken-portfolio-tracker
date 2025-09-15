# tests/test_config.py
import pytest
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import config


def test_load_keyfile_secure_storage_ok(monkeypatch):
    """If keys.load_keys works → it should be used as priority."""
    monkeypatch.setattr("config.load_keys", lambda: ("SECUREKEY", "SECURESECRET"))
    api_key, api_secret = config.load_keyfile("irrelevant.key")
    assert api_key == "SECUREKEY"
    assert api_secret == "SECURESECRET"


def test_load_keyfile_secure_storage_fail(monkeypatch):
    """If secure storage fails, should fallback to env vars."""
    monkeypatch.setattr(
        "config.load_keys",
        lambda: (_ for _ in ()).throw(RuntimeError("no secure keys")),
    )
    monkeypatch.setenv("KRAKEN_API_KEY", "ENVKEY")
    monkeypatch.setenv("KRAKEN_API_SECRET", "ENVSECRET")

    api_key, api_secret = config.load_keyfile("nonexistent.key")
    assert api_key == "ENVKEY"
    assert api_secret == "ENVSECRET"


def test_load_keyfile_from_file(tmp_path, monkeypatch):
    """load_keyfile should read API key/secret from a file."""
    keyfile = tmp_path / "kraken.key"
    keyfile.write_text("KEY123\nSECRET456\n", encoding="utf-8")

    # disable secure storage so file path is tested
    monkeypatch.setattr(
        "config.load_keys",
        lambda: (_ for _ in ()).throw(RuntimeError("no secure keys")),
    )
    monkeypatch.chdir(tmp_path)

    api_key, api_secret = config.load_keyfile()
    assert api_key == "KEY123"
    assert api_secret == "SECRET456"


def test_load_keyfile_file_invalid(tmp_path, monkeypatch):
    """If file exists but does not have two lines → RuntimeError."""
    keyfile = tmp_path / "kraken.key"
    keyfile.write_text("ONLY_ONE_LINE\n", encoding="utf-8")

    # disable secure storage
    monkeypatch.setattr(
        "config.load_keys",
        lambda: (_ for _ in ()).throw(RuntimeError("no secure keys")),
    )
    monkeypatch.chdir(tmp_path)

    with pytest.raises(RuntimeError):
        config.load_keyfile()


def test_load_keyfile_from_env(monkeypatch):
    """If no file exists, but env vars are set → should read them."""
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)

    monkeypatch.setenv("KRAKEN_API_KEY", "ENVKEY")
    monkeypatch.setenv("KRAKEN_API_SECRET", "ENVSECRET")

    # disable secure storage
    monkeypatch.setattr(
        "config.load_keys",
        lambda: (_ for _ in ()).throw(RuntimeError("no secure keys")),
    )

    api_key, api_secret = config.load_keyfile("nonexistent.key")
    assert api_key == "ENVKEY"
    assert api_secret == "ENVSECRET"


def test_load_keyfile_missing(monkeypatch):
    """If no file and no env vars → should raise RuntimeError."""
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)

    # disable secure storage
    monkeypatch.setattr(
        "config.load_keys",
        lambda: (_ for _ in ()).throw(RuntimeError("no secure keys")),
    )

    with pytest.raises(RuntimeError):
        config.load_keyfile("definitely_missing.key")
