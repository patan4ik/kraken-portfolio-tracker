import os
import pandas as pd


def test_compute_trends_adds_columns(tmp_path, monkeypatch, patch_api_and_keys):
    b = patch_api_and_keys

    # Подменяем рабочую папку на tmp_path/balances_history
    balances_dir = tmp_path / "balances_history"
    balances_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(b, "BALANCES_DIR", str(balances_dir), raising=True)

    # Текущий df (текущие значения)
    current_df = pd.DataFrame(
        {"Asset": ["ETH", "SOL", "ZEUR"], "Value (EUR)": [2200.0, 210.0, 100.0]}
    )

    # Предыдущий CSV файл
    prev_date = "2025-08-29"
    prev = pd.DataFrame(
        {"Asset": ["ETH", "SOL", "ZEUR"], "Value (EUR)": [2000.0, 200.0, 100.0]}
    )
    prev.to_csv(
        os.path.join(str(balances_dir), f"balance_{prev_date}.csv"),
        index=False,
        encoding="utf-8",
    )

    # Вызываем
    out = b.compute_trends(current_df.copy())

    # Проверки
    trend_col = f"Trend_{prev_date}"
    assert trend_col in out.columns
    # ETH: 2200 - 2000 = 200
    # SOL: 210 - 200 = 10
    # ZEUR: 100 - 100 = 0
    assert float(out.loc[out["Asset"] == "ETH", trend_col].values[0]) == 200.0
    assert float(out.loc[out["Asset"] == "SOL", trend_col].values[0]) == 10.0
    assert float(out.loc[out["Asset"] == "ZEUR", trend_col].values[0]) == 0.0

    # Portfolio Trend Avg присутствует и равен среднему по трендовым столбцам (у нас один)
    assert "Portfolio Trend Avg" in out.columns
    assert (
        float(out.loc[out["Asset"] == "ETH", "Portfolio Trend Avg"].values[0]) == 200.0
    )
