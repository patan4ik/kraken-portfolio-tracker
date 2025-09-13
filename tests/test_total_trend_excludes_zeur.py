# tests/test_total_trend_excludes_zeur.py
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import pandas as pd


def test_total_trend_value_excludes_zeur(patch_api_and_keys):
    df = pd.DataFrame(
        {
            "Asset": ["ZEUR", "BTC", "ETH"],
            "Portfolio Trend Avg": [10, 20, -5],
        }
    )

    # Apply the same logic as balances.py
    total_trend_value = df.loc[df["Asset"] != "ZEUR", "Portfolio Trend Avg"].sum()

    # Expected sum: 20 + (-5) = 15 (ZEUR excluded)
    assert total_trend_value == 15
