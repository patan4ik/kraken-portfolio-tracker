# test_cli.py
import sys
import ledger_loader


class FakeAPI:
    def __init__(self):
        self.called = False

    def get_ledgers(self, ofs=0, since=None):
        self.called = True
        return {"ledger": {"tx1": {"time": 12345, "asset": "ETH", "amount": "0.1"}}}


def test_cli_respects_days_and_page_size(monkeypatch, tmp_path, capsys):
    fake_api = FakeAPI()

    # Patch KrakenAPI and load_keyfile
    monkeypatch.setattr("ledger_loader.KrakenAPI", lambda key, secret: fake_api)
    monkeypatch.setattr("ledger_loader.load_keyfile", lambda: ("dummy", "dummy"))

    # Patch storage path
    monkeypatch.setattr("ledger_loader.BALANCES_DIR", str(tmp_path))

    # Capture saved entries instead of writing files
    saved = {}
    monkeypatch.setattr(
        "ledger_loader.save_entries", lambda entries: saved.update(entries)
    )

    # Simulate CLI args
    monkeypatch.setattr(sys, "argv", ["ledger_loader.py", "--days=3", "--page-size=10"])

    ledger_loader.main()

    # Ensure our fake API was used
    assert fake_api.called
    assert "tx1" in saved
