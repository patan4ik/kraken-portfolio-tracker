import os
import sys
from datetime import datetime
import types
import pytest

# Добавляем корень проекта в PYTHONPATH
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))


# ---- Фиксированная дата для воспроизводимости ----
class FixedDatetime(datetime):
    @classmethod
    def now(cls, tz=None):
        # Используем 2025-08-30 (соответствует формату %Y-%m-%d и %d.%m.%Y в коде)
        return cls(2025, 8, 30, 12, 0, 0, tzinfo=tz)

# ---- Мок для KrakenAPI ----
class MockKrakenAPI:
    """
    Имитация ответов Kraken для тестов:
    - Баланс: ETH, SOL, ZEUR
    - Пары: XETHZEUR, XSOLZEUR
    - Тикеры: XETHZEUR=2000.0, XSOLZEUR=100.0
    """
    def __init__(self, *args, **kwargs):
        pass

    def get_balance(self):
        # строки, как в реальном API
        return {
            "ETH": "1.0",
            "SOL": "2.0",
            "ZEUR": "100.0"
        }

    def get_asset_pairs(self):
        # структура, совместимая с твоим кодом
        return {
            "XETHZEUR": {"base": "XETH", "quote": "ZEUR"},
            "XSOLZEUR": {"base": "XSOL", "quote": "ZEUR"},
        }

    def get_ticker(self, pair_csv):
        # pair_csv вида "XETHZEUR,XSOLZEUR"
        pairs = [p.strip() for p in pair_csv.split(",") if p.strip()]
        out = {}
        for p in pairs:
            if p == "XETHZEUR":
                out[p] = {"c": ["2000.0", "1"]}
            elif p == "XSOLZEUR":
                out[p] = {"c": ["100.0", "1"]}
            else:
                out[p] = {"c": ["0.0", "1"]}
        return out


@pytest.fixture
def patch_env(tmp_path, monkeypatch):
    """
    Подменяем директории для файлов:
    - BALANCES_DIR -> tmp_path/"balances_history"
    - SNAPSHOTS_FILE -> внутри той же папки
    Также чиним sys.argv для argparse.
    """
    # Импортируем balances после фикстуры, чтобы можно было пропатчить уже импортированный модуль
    import balances

    balances_dir = tmp_path / "balances_history"
    balances_dir.mkdir(parents=True, exist_ok=True)

    monkeypatch.setattr(balances, "BALANCES_DIR", str(balances_dir), raising=True)
    monkeypatch.setattr(balances, "SNAPSHOTS_FILE", os.path.join(str(balances_dir), "portfolio_snapshots.csv"), raising=True)

    # Фиксируем argv (без лишних флагов)
    monkeypatch.setattr(sys, "argv", ["balances.py"], raising=True)

    return balances


@pytest.fixture
def patch_datetime(monkeypatch, patch_env):
    """
    Подменяем datetime в модуле balances на FixedDatetime.
    """
    balances = patch_env
    monkeypatch.setattr(balances, "datetime", FixedDatetime, raising=True)
    return balances


@pytest.fixture
def patch_api_and_keys(monkeypatch, patch_datetime):
    """
    Подменяем KrakenAPI и load_keyfile.
    """
    balances = patch_datetime
    monkeypatch.setattr(balances, "KrakenAPI", MockKrakenAPI, raising=True)
    monkeypatch.setattr(balances, "load_keyfile", lambda: ("KEY", "SECRET"), raising=True)
    return balances
