# tests/test_config.py
import os
import importlib


import config


def test_config_defaults_exist():
    assert hasattr(config, "DATA_DIR")
    assert isinstance(config.DATA_DIR, str)
    # by default project expects balances_history
    assert config.DATA_DIR == "balances_history"


def test_config_dir_created(tmp_path, monkeypatch):
    # simulate running with a new temp DATA_DIR
    monkeypatch.setattr(config, "DATA_DIR", str(tmp_path / "my_balances"))
    # reload or ensure directory creation if config code does it lazily
    # if config module creates os.makedirs at import, reload module:
    importlib.reload(config)
    assert os.path.exists(config.DATA_DIR)


def test_default_parameters_types_and_ranges():
    assert hasattr(config, "DEFAULT_PAGE_SIZE")
    assert isinstance(config.DEFAULT_PAGE_SIZE, int)
    assert config.DEFAULT_PAGE_SIZE > 0

    assert hasattr(config, "DEFAULT_DAYS")
    assert isinstance(config.DEFAULT_DAYS, int)
    assert config.DEFAULT_DAYS >= 0

    assert hasattr(config, "DEFAULT_DELAY_MIN")
    assert isinstance(config.DEFAULT_DELAY_MIN, float)
    assert hasattr(config, "DEFAULT_DELAY_MAX")
    assert isinstance(config.DEFAULT_DELAY_MAX, float)
    assert config.DEFAULT_DELAY_MIN <= config.DEFAULT_DELAY_MAX
