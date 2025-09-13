# tests/test_start.py
import start


class DummyDF:
    def __init__(self, rows=5):
        self._rows = rows
        self.empty = False  # атрибут, а не метод

    def __len__(self):
        return self._rows


def test_start_main(monkeypatch, caplog):
    calls = []

    monkeypatch.setattr(start.balances, "main", lambda: calls.append("portfolio"))
    monkeypatch.setattr(start.storage, "DB_FILE", "fake.db")
    monkeypatch.setattr(start.os.path, "exists", lambda _: False)

    monkeypatch.setattr(
        start.ledger_loader,
        "update_raw_ledger",
        lambda **_: calls.append("update_raw_ledger"),
    )
    monkeypatch.setattr(
        start.storage, "save_entries", lambda entries=None: calls.append("save_entries")
    )

    monkeypatch.setattr(
        start.ledger_eur_report, "build_eur_report", lambda *a, **k: DummyDF()
    )
    monkeypatch.setattr(
        start.ledger_eur_report, "save_eur_report", lambda df: calls.append("save_eur")
    )

    monkeypatch.setattr(
        start.ledger_asset_report, "build_asset_report", lambda *a, **k: DummyDF()
    )
    monkeypatch.setattr(
        start.ledger_asset_report,
        "save_asset_report",
        lambda df: calls.append("save_asset"),
    )

    monkeypatch.setattr(
        start.ledger_sell_report, "build_sell_report", lambda *a, **k: DummyDF()
    )
    monkeypatch.setattr(
        start.ledger_sell_report,
        "save_sell_report",
        lambda df: calls.append("save_sell"),
    )

    monkeypatch.setattr(start.storage, "load_entries_from_db", lambda: {"dummy": {}})

    caplog.set_level("INFO")
    start.main()

    assert "portfolio" in calls
    assert "update_raw_ledger" in calls or "save_entries" in calls
    assert "save_eur" in calls
    assert "save_asset" in calls
    assert "save_sell" in calls

    assert any("EUR report" in rec.message for rec in caplog.records)
    assert any("Asset report" in rec.message for rec in caplog.records)
    assert any("Sell report" in rec.message for rec in caplog.records)


def test_start_empty_raw_json(monkeypatch, caplog):
    calls = []

    monkeypatch.setattr(start.balances, "main", lambda: calls.append("portfolio"))
    monkeypatch.setattr(start.storage, "DB_FILE", "fake.db")

    def fake_exists(path):
        if "raw-ledger.json" in path:
            return True
        return False

    monkeypatch.setattr(start.os.path, "exists", fake_exists)
    monkeypatch.setattr(start.storage, "load_entries", lambda: {})

    monkeypatch.setattr(
        start.ledger_loader,
        "update_raw_ledger",
        lambda **_: calls.append("update_raw_ledger"),
    )
    monkeypatch.setattr(start.storage, "init_db", lambda: calls.append("init_db"))

    monkeypatch.setattr(
        start.ledger_eur_report, "build_eur_report", lambda *a, **k: None
    )
    monkeypatch.setattr(
        start.ledger_asset_report, "build_asset_report", lambda *a, **k: None
    )
    monkeypatch.setattr(
        start.ledger_sell_report, "build_sell_report", lambda *a, **k: None
    )

    caplog.set_level("INFO")
    start.main()

    assert "portfolio" in calls
    assert "update_raw_ledger" in calls
    assert "init_db" in calls
    assert any("raw-ledger.json is empty" in rec.message for rec in caplog.records)


def test_start_only_db(monkeypatch, caplog):
    calls = []

    monkeypatch.setattr(start.balances, "main", lambda: calls.append("portfolio"))
    monkeypatch.setattr(start.storage, "DB_FILE", "ledger.db")

    def fake_exists(path):
        if "ledger.db" in path:
            return True
        return False

    monkeypatch.setattr(start.os.path, "exists", fake_exists)

    monkeypatch.setattr(
        start.ledger_loader,
        "update_raw_ledger",
        lambda **_: calls.append("update_raw_ledger"),
    )

    monkeypatch.setattr(
        start.ledger_eur_report, "build_eur_report", lambda *a, **k: DummyDF()
    )
    monkeypatch.setattr(
        start.ledger_asset_report, "build_asset_report", lambda *a, **k: DummyDF()
    )
    monkeypatch.setattr(
        start.ledger_sell_report, "build_sell_report", lambda *a, **k: DummyDF()
    )

    monkeypatch.setattr(
        start.ledger_eur_report, "save_eur_report", lambda df: calls.append("save_eur")
    )
    monkeypatch.setattr(
        start.ledger_asset_report,
        "save_asset_report",
        lambda df: calls.append("save_asset"),
    )
    monkeypatch.setattr(
        start.ledger_sell_report,
        "save_sell_report",
        lambda df: calls.append("save_sell"),
    )

    monkeypatch.setattr(start.storage, "load_entries_from_db", lambda: {"dummy": {}})

    caplog.set_level("INFO")
    start.main()

    assert "portfolio" in calls
    assert "update_raw_ledger" not in calls
    assert "save_eur" in calls
    assert "save_asset" in calls
    assert "save_sell" in calls
    assert any("ledger.db already exists" in rec.message for rec in caplog.records)


def test_start_raw_json_with_data(monkeypatch, caplog):
    calls = []

    monkeypatch.setattr(start.balances, "main", lambda: calls.append("portfolio"))
    monkeypatch.setattr(start.storage, "DB_FILE", "fake.db")

    def fake_exists(path):
        if "raw-ledger.json" in path:
            return True
        return False

    monkeypatch.setattr(start.os.path, "exists", fake_exists)

    # JSON возвращает непустые данные
    monkeypatch.setattr(
        start.storage,
        "load_entries",
        lambda: {"tx1": {"asset": "ZEUR", "amount": "10.0"}},
    )
    monkeypatch.setattr(
        start.storage, "save_entries", lambda e: calls.append("save_entries")
    )

    monkeypatch.setattr(
        start.ledger_loader,
        "update_raw_ledger",
        lambda **_: calls.append("update_raw_ledger"),
    )

    monkeypatch.setattr(
        start.ledger_eur_report, "build_eur_report", lambda *a, **k: DummyDF()
    )
    monkeypatch.setattr(
        start.ledger_asset_report, "build_asset_report", lambda *a, **k: DummyDF()
    )
    monkeypatch.setattr(
        start.ledger_sell_report, "build_sell_report", lambda *a, **k: DummyDF()
    )

    monkeypatch.setattr(
        start.ledger_eur_report, "save_eur_report", lambda df: calls.append("save_eur")
    )
    monkeypatch.setattr(
        start.ledger_asset_report,
        "save_asset_report",
        lambda df: calls.append("save_asset"),
    )
    monkeypatch.setattr(
        start.ledger_sell_report,
        "save_sell_report",
        lambda df: calls.append("save_sell"),
    )

    monkeypatch.setattr(start.storage, "load_entries_from_db", lambda: {"dummy": {}})

    caplog.set_level("INFO")
    start.main()

    assert "portfolio" in calls
    assert "save_entries" in calls
    assert "update_raw_ledger" not in calls  # Kraken API не должен дёргаться
    assert "save_eur" in calls
    assert "save_asset" in calls
    assert "save_sell" in calls
    assert any(
        "SQLite DB created from raw-ledger.json" in rec.message
        for rec in caplog.records
    )
