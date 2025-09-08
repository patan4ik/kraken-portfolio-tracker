import os
import csv
import pandas as pd


def _read_csv(path, sep=","):
    with open(path, "r", encoding="utf-8") as f:
        sample = f.read(1024)
    # быстрый детект разделителя
    if ";" in sample and sep == ",":
        sep = ";"
    return pd.read_csv(path, sep=sep, encoding="utf-8")


def test_main_creates_balance_and_snapshot(
    tmp_path, monkeypatch, patch_api_and_keys, capsys
):
    b = patch_api_and_keys

    # Папка для файлов
    balances_dir = tmp_path / "balances_history"
    balances_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(b, "BALANCES_DIR", str(balances_dir), raising=True)
    monkeypatch.setattr(
        b,
        "SNAPSHOTS_FILE",
        os.path.join(str(balances_dir), "portfolio_snapshots.csv"),
        raising=True,
    )

    # Запуск main()
    b.main()

    # Проверяем наличие balance_YYYY-MM-DD.csv
    saved = list(balances_dir.glob("balance_*.csv"))
    assert len(saved) == 1
    df_saved = _read_csv(str(saved[0]))
    # Колонки из твоего кода
    for col in [
        "Asset",
        "Amount",
        "Current Price (EUR)",
        "Value (EUR)",
        "Available",
        "Available EUR",
        "Staked",
        "Staked EUR",
        "Total Fees (EUR)",
        "Avg Buy Price (EUR)",
    ]:
        assert col in df_saved.columns

    # Проверяем snapshots
    snap_path = os.path.join(str(balances_dir), "portfolio_snapshots.csv")
    assert os.path.exists(snap_path)
    snap_df = _read_csv(snap_path, sep=";")
    assert list(snap_df.columns) == [
        "Timestamp",
        "Portfolio Value (EUR)",
        "Portfolio Trend Avg (EUR)",
        "Total Potential Value",
    ]
    assert len(snap_df) == 1  # первая запись


def test_snapshots_update_last_row(tmp_path, monkeypatch, patch_api_and_keys):
    b = patch_api_and_keys

    balances_dir = tmp_path / "balances_history"
    balances_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(b, "BALANCES_DIR", str(balances_dir), raising=True)
    snap_path = os.path.join(str(balances_dir), "portfolio_snapshots.csv")
    monkeypatch.setattr(b, "SNAPSHOTS_FILE", snap_path, raising=True)

    # Предсоздаём файл с записью на "сегодня" (30.08.2025), чтобы main() должен заменить последнюю строку
    pd.DataFrame(
        [
            {
                "Timestamp": "30.08.2025",
                "Portfolio Value (EUR)": 9999.99,
                "Portfolio Trend Avg (EUR)": 0.0,
                "Total Potential Value": 9999.99,
            }
        ]
    ).to_csv(snap_path, sep=";", index=False, encoding="utf-8")

    b.main()

    # Должна быть всё ещё одна строка, но уже обновлённая
    snap_df = pd.read_csv(snap_path, sep=";", encoding="utf-8")
    assert len(snap_df) == 1
    # Значение обновилось (у MockKrakenAPI другие суммы)
    assert snap_df.iloc[0]["Portfolio Value (EUR)"] != 9999.99
    assert snap_df.iloc[0]["Timestamp"] == "30.08.2025"


def test_snapshots_append_new_day(tmp_path, monkeypatch, patch_api_and_keys):
    b = patch_api_and_keys

    balances_dir = tmp_path / "balances_history"
    balances_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(b, "BALANCES_DIR", str(balances_dir), raising=True)
    snap_path = os.path.join(str(balances_dir), "portfolio_snapshots.csv")
    monkeypatch.setattr(b, "SNAPSHOTS_FILE", snap_path, raising=True)

    # Предсоздаём файл со вчерашней датой, чтобы добавилась новая строка
    pd.DataFrame(
        [
            {
                "Timestamp": "29.08.2025",
                "Portfolio Value (EUR)": 1234.56,
                "Portfolio Trend Avg (EUR)": 7.89,
                "Total Potential Value": 1242.45,
            }
        ]
    ).to_csv(snap_path, sep=";", index=False, encoding="utf-8")

    b.main()

    snap_df = pd.read_csv(snap_path, sep=";", encoding="utf-8")
    # Две строки: вчера и сегодня
    assert len(snap_df) == 2
    assert "30.08.2025" in snap_df["Timestamp"].tolist()
