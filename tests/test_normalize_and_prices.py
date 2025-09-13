# tests/test_normalize_and_prices.py
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)


def test_normalize_asset_code_variants(patch_api_and_keys):
    b = patch_api_and_keys
    assert b.normalize_asset_code("ETH") == "ETH"
    assert b.normalize_asset_code("XETH") == "XETH"
    assert b.normalize_asset_code("ETH.S") == "ETH"
    assert b.normalize_asset_code("SOL.F") == "SOL"
    assert b.normalize_asset_code("USDT.Z") == "USDT"
    assert b.normalize_asset_code("XRP10") == "XRP"


def test_fetch_asset_pairs_and_prices(patch_api_and_keys):
    b = patch_api_and_keys
    api = b.KrakenAPI("k", "s")
    pairs = b.fetch_asset_pairs(api)
    assert "XETHZEUR" in pairs and pairs["XETHZEUR"]["quote"] == "ZEUR"

    prices = b.fetch_prices_batch(api, ["XETHZEUR", "XSOLZEUR"])
    # fetch_prices_batch возвращает Decimal
    assert str(prices["XETHZEUR"]) == "2000.0"
    assert str(prices["XSOLZEUR"]) == "100.0"
