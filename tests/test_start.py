# tests/test_start.py
import pytest
from unittest.mock import patch

import start


def test_main_runs_successfully_with_keys():
    """
    Проверяем, что main() корректно отрабатывает,
    когда load_keys возвращает кортеж (api_key, api_secret).
    """
    with patch("start.load_keys", return_value=("fake", "fake")):
        # mock balances.main чтобы не запускался реальный код
        with patch("start.balances.main", return_value=None) as mock_bal:
            result = start.main()
            mock_bal.assert_called_once()
            assert result is None


def test_main_exits_if_no_keys(caplog):
    """
    Проверяем, что при ошибке в load_keys main() завершает работу
    и пишет сообщение об ошибке в лог.
    """
    with patch("start.load_keys", side_effect=Exception("no keys")):
        with caplog.at_level("ERROR"):
            with pytest.raises(SystemExit) as e:
                start.main()
            assert e.value.code == 1
            assert "ERROR" in caplog.text


def test_main_calls_balances():
    """
    Проверяем, что balances.main вызывается, если ключи успешно загружены.
    """
    with patch("start.load_keys", return_value=("fake", "fake")):
        with patch("start.balances.main", return_value="done") as mock_bal:
            result = start.main()
            mock_bal.assert_called_once()
            assert result == "done"
