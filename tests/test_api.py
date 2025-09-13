# tests/test_api.py
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import api


class DummyAPI:
    """Fake krakenex.API with controllable responses."""

    def __init__(self, responses):
        # responses = {"Ledgers": {"result": {...}}, "Assets": {"error": ["EGeneral:Invalid"]}}
        self.responses = responses
        self.calls = []

    def query_private(self, method, data=None):
        self.calls.append(("private", method, data))
        return self.responses.get(method, {"result": {}})

    def query_public(self, method, data=None):
        self.calls.append(("public", method, data))
        return self.responses.get(method, {"result": {}})


def test_get_ledgers_returns_dict(monkeypatch):
    """Check that get_ledgers calls query_private and returns parsed dict."""
    dummy = DummyAPI({"Ledgers": {"result": {"ledger": {"tx1": {"time": "12345"}}}}})

    # Patch krakenex.API to return our dummy instead of real network client
    monkeypatch.setattr(api.krakenex, "API", lambda key, secret: dummy)

    k = api.KrakenAPI("dummy_key", "dummy_secret")
    result = k.get_ledgers(ofs=0)

    assert "ledger" in result
    assert "tx1" in result["ledger"]
    assert dummy.calls[0][0] == "private"  # ensure it used query_private


def test_get_assets_calls_public(monkeypatch):
    """Check that get_assets uses query_public and returns parsed dict."""
    dummy = DummyAPI({"Assets": {"result": {"XXBT": {"altname": "BTC"}}}})

    monkeypatch.setattr(api.krakenex, "API", lambda key, secret: dummy)

    k = api.KrakenAPI("dummy", "dummy")
    result = k.get_assets()

    assert "XXBT" in result
    assert dummy.calls[0][0] == "public"  # should call query_public


def test_call_retries_on_error(monkeypatch):
    """Simulate error response -> retries -> final success."""
    responses = {
        "Balance": {"error": ["EGeneral:Temporary error"]},  # first call fails
    }
    dummy = DummyAPI(responses)

    # Make second call return success
    def side_effect(method, data=None):
        if not hasattr(dummy, "called_once"):
            dummy.called_once = True
            return {"error": ["EGeneral:Temporary error"]}
        return {"result": {"ZEUR": "100.0"}}

    dummy.query_private = side_effect

    monkeypatch.setattr(api.krakenex, "API", lambda key, secret: dummy)
    # Patch time.sleep so test runs fast
    monkeypatch.setattr(api.time, "sleep", lambda s: None)

    k = api.KrakenAPI("dummy", "dummy")
    result = k.get_balance()

    assert "ZEUR" in result
