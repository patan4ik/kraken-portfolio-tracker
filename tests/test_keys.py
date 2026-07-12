"""Unit tests for keys.py — encrypted API key storage, plaintext fallback, env vars."""

import importlib
import json
import os
import sys
import types

import pytest


@pytest.fixture()
def keys_mod(tmp_path, monkeypatch):
    """(Re)import keys.py pointed at an isolated tmp data dir."""
    fake_appdirs = types.ModuleType("appdirs")
    fake_appdirs.user_data_dir = lambda app_name: str(tmp_path / "appdata")
    monkeypatch.setitem(sys.modules, "appdirs", fake_appdirs)

    if "keys" in sys.modules:
        del sys.modules["keys"]
    import keys as keys_mod  # noqa: E402

    importlib.reload(keys_mod)
    yield keys_mod
    if "keys" in sys.modules:
        del sys.modules["keys"]


def test_save_and_load_keys_roundtrip(keys_mod):
    keys_mod.save_keys("myapikey", "myapisecretkey12")
    assert os.path.exists(keys_mod.KEYFILE)
    k, s = keys_mod.load_keys()
    assert k == "myapikey"
    assert s == "myapisecretkey12"


def test_load_keys_corrupted_master_raises(keys_mod):
    keys_mod.save_keys("k", "s")
    with open(keys_mod.MASTER_FILE, "wb") as f:
        f.write(b"not-a-valid-fernet-key")
    with pytest.raises(keys_mod.KeysError):
        keys_mod.load_keys()


def test_get_master_key_missing_raises(keys_mod):
    with pytest.raises(keys_mod.KeysError):
        keys_mod._get_master_key(create_if_missing=False)


def test_load_keys_plaintext_fallback(keys_mod, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    legacy = tmp_path / "kraken.key"
    legacy.write_text("plainkey\nplainsecret\n")
    k, s = keys_mod.load_keys()
    assert k == "plainkey"
    assert s == "plainsecret"


def test_load_keys_env_var_fallback(keys_mod, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("KRAKEN_API_KEY", "envkey")
    monkeypatch.setenv("KRAKEN_API_SECRET", "envsecret")
    k, s = keys_mod.load_keys()
    assert k == "envkey"
    assert s == "envsecret"


def test_load_keys_none_found_raises(keys_mod, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    with pytest.raises(keys_mod.KeysError):
        keys_mod.load_keys()


def test_keys_exist_true_false(keys_mod, tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("KRAKEN_API_KEY", raising=False)
    monkeypatch.delenv("KRAKEN_API_SECRET", raising=False)
    assert keys_mod.keys_exist() is False
    keys_mod.save_keys("a", "b")
    assert keys_mod.keys_exist() is True


def test_load_keys_secret_padding_fixed(keys_mod):
    f = keys_mod._get_fernet(create_if_missing=True)
    payload = json.dumps({"api_key": "k", "api_secret": "abc"}).encode()
    token = f.encrypt(payload)
    with open(keys_mod.KEYFILE, "wb") as fh:
        fh.write(token)
    k, s = keys_mod.load_keys()
    assert k == "k"
    assert len(s) % 4 == 0
