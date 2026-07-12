"""Unit tests for api.py — KrakenAPI wrapper with retry/backoff."""

import sys
import types
import pytest

krakenex_stub = types.ModuleType("krakenex")


class _FakeKrakenexAPI:
    def __init__(self, key=None, secret=None):
        self.key = key
        self.secret = secret

    def query_public(self, method, data):
        return {"error": [], "result": {"public": method}}

    def query_private(self, method, data):
        return {"error": [], "result": {"private": method}}


krakenex_stub.API = _FakeKrakenexAPI
sys.modules["krakenex"] = krakenex_stub

import api as api_mod  # noqa: E402


def test_get_assets_calls_public(monkeypatch):
    k = api_mod.KrakenAPI("k", "s")
    monkeypatch.setattr(api_mod.time, "sleep", lambda *a, **k: None)
    result = k.get_assets()
    assert result == {"public": "Assets"}


def test_get_balance_calls_private(monkeypatch):
    k = api_mod.KrakenAPI("k", "s")
    monkeypatch.setattr(api_mod.time, "sleep", lambda *a, **k: None)
    result = k.get_balance()
    assert result == {"private": "Balance"}


def test_get_ticker_passes_pair(monkeypatch):
    k = api_mod.KrakenAPI("k", "s")
    monkeypatch.setattr(api_mod.time, "sleep", lambda *a, **k: None)
    captured = {}

    def fake_query_public(method, data):
        captured["method"] = method
        captured["data"] = data
        return {"error": [], "result": {}}

    k.api.query_public = fake_query_public
    k.get_ticker("XBTEUR")
    assert captured["data"] == {"pair": "XBTEUR"}


def test_get_ledgers_with_since_and_ofs(monkeypatch):
    k = api_mod.KrakenAPI("k", "s")
    monkeypatch.setattr(api_mod.time, "sleep", lambda *a, **k: None)
    captured = {}

    def fake_query_private(method, data):
        captured["data"] = data
        return {"error": [], "result": {}}

    k.api.query_private = fake_query_private
    k.get_ledgers(since=100, ofs=5)
    assert captured["data"] == {"since": 100, "ofs": 5}


def test_call_retries_on_error_then_succeeds(monkeypatch):
    k = api_mod.KrakenAPI("k", "s")
    monkeypatch.setattr(api_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(api_mod.random, "uniform", lambda a, b: 0.0)

    calls = {"n": 0}

    def flaky(method, data):
        calls["n"] += 1
        if calls["n"] < 2:
            return {"error": ["EGeneral:Temp"], "result": {}}
        return {"error": [], "result": {"ok": True}}

    k.api.query_public = flaky
    result = k._call("Assets", max_retries=5)
    assert result == {"ok": True}
    assert calls["n"] == 2


def test_call_raises_after_max_retries(monkeypatch):
    k = api_mod.KrakenAPI("k", "s")
    monkeypatch.setattr(api_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(api_mod.random, "uniform", lambda a, b: 0.0)

    def always_error(method, data):
        return {"error": ["EGeneral:Fail"], "result": {}}

    k.api.query_public = always_error
    with pytest.raises(RuntimeError):
        k._call("Assets", max_retries=2)


def test_call_retries_on_exception(monkeypatch):
    k = api_mod.KrakenAPI("k", "s")
    monkeypatch.setattr(api_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(api_mod.random, "uniform", lambda a, b: 0.0)

    calls = {"n": 0}

    def raises_then_ok(method, data):
        calls["n"] += 1
        if calls["n"] < 2:
            raise ConnectionError("boom")
        return {"error": [], "result": {"ok": True}}

    k.api.query_public = raises_then_ok
    result = k._call("Assets", max_retries=5)
    assert result == {"ok": True}
