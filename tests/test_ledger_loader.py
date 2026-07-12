"""Unit tests for ledger_loader.py — Kraken ledger fetch with retry/pagination."""

import sys
import types

import pytest


@pytest.fixture()
def ll_mod(monkeypatch):
    keys_stub = types.ModuleType("keys")
    keys_stub.load_keys = lambda: ("k", "s")
    monkeypatch.setitem(sys.modules, "keys", keys_stub)

    storage_stub = types.ModuleType("storage")
    storage_stub.save_entries = lambda entries: None
    storage_stub.load_entries = lambda: {}
    monkeypatch.setitem(sys.modules, "storage", storage_stub)

    if "ledger_loader" in sys.modules:
        del sys.modules["ledger_loader"]
    import ledger_loader as ll_mod  # noqa: E402

    yield ll_mod
    if "ledger_loader" in sys.modules:
        del sys.modules["ledger_loader"]


class _FakeAPI:
    def __init__(self, pages):
        self.pages = pages
        self.calls = 0

    def get_ledgers(self, ofs=0, since=None, page_size=None):
        self.calls += 1
        if ofs < len(self.pages):
            return (
                self.pages[ofs]
                if isinstance(self.pages, dict)
                else self.pages[self.calls - 1]
            )
        return {}


def test_fetch_ledger_single_page_below_page_size(ll_mod, monkeypatch):
    monkeypatch.setattr(ll_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(ll_mod.random, "uniform", lambda a, b: 0.0)

    api = _FakeAPI(
        [{"ledger": {"t1": {"time": 1700000000.0}, "t2": {"time": 1700000001.0}}}]
    )
    entries = ll_mod.fetch_ledger(api, page_size=50, delay_min=0, delay_max=0)
    assert len(entries) == 2


def test_fetch_ledger_stops_on_known_txid(ll_mod, monkeypatch):
    monkeypatch.setattr(ll_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(ll_mod.random, "uniform", lambda a, b: 0.0)

    api = _FakeAPI(
        [{"ledger": {"known1": {"time": 1700000000.0}, "new1": {"time": 1700000001.0}}}]
    )
    entries = ll_mod.fetch_ledger(api, page_size=50, stop_on_txids={"known1"})
    assert "known1" not in entries
    assert "new1" in entries


def test_fetch_ledger_empty_response_stops(ll_mod, monkeypatch):
    monkeypatch.setattr(ll_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(ll_mod.random, "uniform", lambda a, b: 0.0)

    api = _FakeAPI([{}])
    entries = ll_mod.fetch_ledger(api, page_size=50)
    assert entries == {}


def test_fetch_ledger_reaches_since_limit(ll_mod, monkeypatch):
    monkeypatch.setattr(ll_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(ll_mod.random, "uniform", lambda a, b: 0.0)

    api = _FakeAPI([{"ledger": {"t1": {"time": 100.0}}}])
    entries = ll_mod.fetch_ledger(api, page_size=50, since_ts=1000)
    assert "t1" in entries


def test_fetch_page_with_retry_gives_up_after_max(ll_mod, monkeypatch):
    monkeypatch.setattr(ll_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(ll_mod.random, "uniform", lambda a, b: 0.0)

    class AlwaysFails:
        def get_ledgers(self, ofs=0, since=None, page_size=None):
            raise ConnectionError("down")

    result = ll_mod._fetch_page_with_retry(AlwaysFails(), 0, 0, 50, max_retries=2)
    assert result is None


def test_fetch_page_with_retry_typeerror_fallback(ll_mod, monkeypatch):
    monkeypatch.setattr(ll_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(ll_mod.random, "uniform", lambda a, b: 0.0)

    class FallbackAPI:
        def get_ledgers(self, ofs=0, since=None, page_size=None):
            raise TypeError("bad kwargs")

    with pytest.raises(TypeError):
        FallbackAPI().get_ledgers(ofs=0)


def test_fetch_ledger_consecutive_failures_stops(ll_mod, monkeypatch):
    monkeypatch.setattr(ll_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(ll_mod.random, "uniform", lambda a, b: 0.0)

    class AlwaysFails:
        def get_ledgers(self, ofs=0, since=None, page_size=None):
            raise ConnectionError("down")

    entries = ll_mod.fetch_ledger(
        AlwaysFails(), page_size=50, max_consecutive_page_failures=1
    )
    assert entries == {}


def test_update_raw_ledger_calls_save(ll_mod, monkeypatch):
    monkeypatch.setattr(ll_mod.time, "sleep", lambda *a, **k: None)
    monkeypatch.setattr(ll_mod.random, "uniform", lambda a, b: 0.0)
    saved = {}
    monkeypatch.setattr(ll_mod, "save_entries", lambda e: saved.update(e))

    api = _FakeAPI([{"ledger": {"t1": {"time": 1700000000.0}}}])
    ll_mod.update_raw_ledger(api=api, page_size=50)
    assert "t1" in saved


def test_load_raw_ledger_delegates(ll_mod, monkeypatch):
    monkeypatch.setattr(ll_mod, "load_entries", lambda: {"x": 1})
    assert ll_mod.load_raw_ledger() == {"x": 1}
