# tests/test_keys.py
import pytest
from pathlib import Path
import src.keys as keys
from src.keys import KeysError


def test_store_and_load_keys(monkeypatch):
    store = {}

    # Fake keyring
    monkeypatch.setattr(
        keys,
        "keyring",
        type(
            "FakeRing",
            (),
            {
                "set_password": lambda self, svc, user, pw: store.setdefault(
                    (svc, user), pw
                ),
                "get_password": lambda self, svc, user: store.get((svc, user)),
            },
        )(),
    )

    keys.save_keys("API123", "SECRET456")
    api_key, api_secret = keys.load_keys()
    assert api_key == "API123"
    assert api_secret == "SECRET456"


def test_load_keys_missing(monkeypatch):
    monkeypatch.setattr(
        keys,
        "keyring",
        type(
            "FakeRing",
            (),
            {
                "get_password": lambda self, svc, user: None,
                "set_password": lambda self, svc, user, pw: None,
            },
        )(),
    )
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)

    # Ensure encrypted file not considered
    monkeypatch.setattr(keys, "KEYFILE", Path("nonexistent.json"))

    with pytest.raises(KeysError):
        keys.load_keys()


def test_legacy_file_fallback(tmp_path, monkeypatch):
    keyfile = tmp_path / "kraken.key"
    keyfile.write_text("FILEKEY\nFILESECRET\n", encoding="utf-8")

    # Ensure KEYFILE check is skipped
    monkeypatch.setattr(keys, "KEYFILE", Path("nonexistent.json"))

    # Change current working directory so legacy lookup finds our file
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        keys,
        "keyring",
        type(
            "FakeRing",
            (),
            {
                "get_password": lambda self, svc, user: None,
                "set_password": lambda self, svc, user, pw: None,
            },
        )(),
    )

    api_key, api_secret = keys.load_keys()
    assert api_key == "FILEKEY"
    assert api_secret == "FILESECRET"


def test_legacy_file_invalid(tmp_path, monkeypatch):
    keyfile = tmp_path / "kraken.key"
    keyfile.write_text("ONLY_ONE_LINE\n", encoding="utf-8")

    monkeypatch.setattr(keys, "KEYFILE", Path("nonexistent.json"))
    monkeypatch.setattr(Path, "home", lambda: tmp_path)
    monkeypatch.setattr(
        keys,
        "keyring",
        type(
            "FakeRing",
            (),
            {
                "get_password": lambda self, svc, user: None,
                "set_password": lambda self, svc, user, pw: None,
            },
        )(),
    )

    with pytest.raises(KeysError):
        keys.load_keys()


#    with pytest.raises(RuntimeError):
#        keys.load_keys()


def test_env_fallback(monkeypatch, tmp_path):
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    monkeypatch.setenv("KRAKEN_API_KEY", "ENVKEY")
    monkeypatch.setenv("KRAKEN_API_SECRET", "ENVSECRET")

    # Force skip encrypted file
    monkeypatch.setattr(keys, "KEYFILE", Path("nonexistent.json"))

    # Change CWD to empty tmpdir so legacy file is not accidentally picked up
    monkeypatch.chdir(tmp_path)

    monkeypatch.setattr(
        keys,
        "keyring",
        type(
            "FakeRing",
            (),
            {
                "get_password": lambda self, svc, user: None,
                "set_password": lambda self, svc, user, pw: None,
            },
        )(),
    )

    api_key, api_secret = keys.load_keys()
    assert api_key == "ENVKEY"
    assert api_secret == "ENVSECRET"
