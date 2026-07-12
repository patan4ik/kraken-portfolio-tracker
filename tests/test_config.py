"""Unit tests for config.py — default constants + directory creation."""

import importlib
import os


def test_config_defaults(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    import config as config_mod

    importlib.reload(config_mod)
    assert config_mod.DEFAULT_PAGE_SIZE == 50
    assert config_mod.DEFAULT_DAYS == 7
    assert config_mod.DEFAULT_DELAY_MIN == 1.0
    assert config_mod.DEFAULT_DELAY_MAX == 2.5
    assert config_mod.BALANCES_HISTORY_DIR == config_mod.DATA_DIR
    assert os.path.isdir(config_mod.DATA_DIR)
