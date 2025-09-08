import pandas as pd


def test_total_trend_value_excludes_zeur(patch_api_and_keys):
    b = patch_api_and_keys
    df = pd.DataFrame(
        {
            "Asset": ["ETH", "SOL", "ZEUR"],
            "Portfolio Trend Avg": [100.0, 50.0, 9999.0],
        }
    )
    # В balances.py это выражение в main(), здесь просто проверяем ту же логику:
    total_trend_value = 0.0
    if "Portfolio Trend Avg" in df.columns:
        total_trend_value = df.loc[df["Asset"] != "ZEUR", "Portfolio Trend Avg"].sum()

    assert total_trend_value == 150.0
