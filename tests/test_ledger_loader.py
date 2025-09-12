# test_ledger_loader.py
from storage import save_entries, load_entries
from ledger_loader import fetch_ledger


class DummyAPI:
    def __init__(self, ledgers_per_page):
        self.ledgers_per_page = ledgers_per_page

    def get_ledgers(self, ofs=0, since=None):
        # Возвращаем заранее подготовленные записи по страницам
        if ofs >= len(self.ledgers_per_page) * 50:
            return {}
        page = ofs // 50
        data = self.ledgers_per_page[page]
        return {"ledger": data}


def test_save_and_load_entries(tmp_path, monkeypatch):
    # Переопределяем пути на временные
    monkeypatch.setattr("storage.RAW_LEDGER_FILE", tmp_path / "raw-ledger.json")
    monkeypatch.setattr("storage.LEDGER_DB_FILE", tmp_path / "ledger.db")

    entries = {"tx1": {"time": "12345", "asset": "XXBT", "amount": "1.0"}}
    save_entries(entries)

    loaded = load_entries()
    assert "tx1" in loaded
    assert loaded["tx1"]["asset"] == "XXBT"


def test_fetch_ledger_stops_at_since_limit(monkeypatch):
    # Создаём тестовые записи с убывающим временем
    now = 2_000_000
    ledgers_page1 = {
        "tx1": {"time": str(now), "asset": "XXBT", "amount": "1.0"},
        "tx2": {"time": str(now - 1000), "asset": "ADA", "amount": "2.0"},
    }
    ledgers_page2 = {
        "tx3": {"time": str(now - 10 * 86400), "asset": "DOT", "amount": "3.0"},
    }

    dummy_api = DummyAPI([ledgers_page1, ledgers_page2])

    # Патчим datetime, чтобы since_limit считался от "now"
    import datetime

    monkeypatch.setattr("ledger_loader.datetime", datetime.datetime)
    monkeypatch.setattr("ledger_loader.timezone", datetime.timezone)

    entries = fetch_ledger(dummy_api, days=5)

    assert "tx1" in entries
    assert "tx2" in entries
    # tx3 слишком старый → не должен попасть
    assert "tx3" not in entries
