# test_fetch_ledger_stop.py
import ledger_loader


class FakeAPI:
    """Fake Kraken API to simulate paginated ledger responses."""

    def __init__(self, batches):
        self.batches = batches
        self.calls = 0

    def get_ledgers(self, ofs=0, since=None):
        # Return one batch per page (50 offset step)
        page = ofs // 50
        if page < len(self.batches):
            return {"ledger": self.batches[page]}
        return {}


def test_fetch_ledger_stops_at_since_limit(monkeypatch):
    # First batch (newer entries), second batch (borderline), third batch (too old)
    batches = [
        {
            "tx1": {"time": 2000, "asset": "ETH", "amount": "0.1", "fee": "0"},
            "tx2": {"time": 1900, "asset": "ZEUR", "amount": "-1.98", "fee": "0.02"},
        },
        {
            "tx3": {"time": 1400, "asset": "BTC", "amount": "0.01", "fee": "0.01"},
        },
        {
            "tx4": {"time": 1300, "asset": "ADA", "amount": "50", "fee": "0"},
        },
    ]

    fake_api = FakeAPI(batches)

    # Patch delay to be instant (no random.sleep waiting in tests)
    monkeypatch.setattr("ledger_loader.random.uniform", lambda a, b: 0.01)

    # Run fetch with days=1 → since_limit will cut off tx3 and tx4
    entries = ledger_loader.fetch_ledger(fake_api, days=1)

    # Expected: tx1 and tx2 are included, tx3 and tx4 are filtered out
    assert "tx1" in entries
    assert "tx2" in entries
    assert "tx3" not in entries
    assert "tx4" not in entries
