# test_cli.py
import sys

import ledger_loader


class FakeAPI:
    """Фейковый API, чтобы не ходить в Kraken"""

    def __init__(self):
        self.calls = []

    def get_ledgers(self, ofs=0):
        self.calls.append(ofs)
        if ofs > 0:
            return {}  # стоп после первой страницы
        return {
            "ledger": {
                "tx1": {
                    "time": 1234567890,
                    "asset": "ETH",
                    "amount": "0.1",
                    "fee": "0",
                },
                "tx2": {
                    "time": 1234567891,
                    "asset": "ZEUR",
                    "amount": "-1.98",
                    "fee": "0.02",
                },
            }
        }


def test_cli_respects_days_and_page_size(monkeypatch, tmp_path, capsys):
    fake_api = FakeAPI()

    # Подменяем KrakenAPI и пути
    monkeypatch.setattr("ledger_loader.KrakenAPI", lambda key, secret: fake_api)
    monkeypatch.setattr("ledger_loader.BALANCES_DIR", str(tmp_path))

    # Подменяем save_entries, чтобы не писать файлы
    saved = {}
    monkeypatch.setattr(
        "ledger_loader.save_entries", lambda entries: saved.update(entries)
    )

    # Подменяем sys.argv
    monkeypatch.setattr(sys, "argv", ["ledger_loader.py", "--days=3", "--page-size=10"])

    # Запускаем main()
    ledger_loader.main()

    # Проверяем, что FakeAPI вызывался хотя бы раз
    assert fake_api.calls[0] == 0
    # Проверяем, что данные сохранились
    assert "tx1" in saved
    assert "tx2" in saved
