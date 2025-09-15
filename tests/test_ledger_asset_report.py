# tests/test_ledger_asset_report.py
import unittest
from datetime import datetime, timedelta, timezone
from unittest.mock import patch
import pandas as pd
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import ledger_asset_report as report


class TestLedgerAssetReport(unittest.TestCase):

    def setUp(self):
        # self.now = datetime.utcnow()
        self.now = datetime.now(timezone.utc)  # instead of UTC
        self.timestamp = self.now.timestamp()
        self.old_timestamp = (self.now - timedelta(days=10)).timestamp()

        self.valid_entries = {
            "tx1": {"time": self.timestamp, "amount": "1.5", "asset": "BTC"},
            "tx2": {
                "time": self.timestamp,
                "amount": "2.0",
                "asset": "ETH",
                "refid": "tx1",
            },
            "tx3": {
                "time": self.timestamp,
                "amount": "-1.0",
                "asset": "BTC",
            },  # negative amount
            "tx4": {
                "time": self.timestamp,
                "amount": "1.0",
                "asset": "EUR",
            },  # excluded asset
            "tx5": {
                "time": self.old_timestamp,
                "amount": "3.0",
                "asset": "BTC",
            },  # outside cutoff
        }

    def test_build_asset_report_empty_input(self):
        df = report.build_asset_report({})
        self.assertTrue(df.empty)

    def test_build_asset_report_all_filtered_out(self):
        df = report.build_asset_report(
            {"tx": {"time": self.old_timestamp, "amount": "1", "asset": "BTC"}}, days=7
        )
        self.assertTrue(df.empty)

    def test_build_asset_report_valid_entries(self):
        df = report.build_asset_report(self.valid_entries, days=7)
        self.assertFalse(df.empty)
        self.assertIn("BTC", df.columns)
        self.assertIn("ETH", df.columns)
        self.assertNotIn("EUR", df.columns)
        self.assertEqual(df["BTC"].sum(), 1.5)
        self.assertEqual(df["ETH"].sum(), 2.0)

    @patch("ledger_asset_report.storage.BALANCES_DIR", "mock_dir")
    @patch("ledger_asset_report.pd.DataFrame.to_csv")
    @patch("ledger_asset_report.os.makedirs")
    def test_save_asset_report(self, mock_makedirs, mock_to_csv):
        df = pd.DataFrame([{"Date": "01.01.2023", "BTC": 1.5}])
        report.save_asset_report(df)
        mock_makedirs.assert_called_once_with("mock_dir", exist_ok=True)
        mock_to_csv.assert_called_once()

        @patch("ledger_asset_report.storage.load_entries_from_db")
        def test_update_asset_report_no_entries(mock_load):
            mock_load.return_value = {}
            result = report.update_asset_report()
            assert isinstance(result, pd.DataFrame)
            assert result.empty

    @patch("ledger_asset_report.save_asset_report")
    @patch("ledger_asset_report.storage.load_entries_from_db")
    def test_update_asset_report_with_csv(self, mock_load, mock_save):
        mock_load.return_value = self.valid_entries
        df = report.update_asset_report(write_csv=True)
        self.assertIsInstance(df, pd.DataFrame)
        mock_save.assert_called_once()

    @patch("ledger_asset_report.storage.load_entries_from_db")
    def test_update_asset_report_empty_df(self, mock_load):
        mock_load.return_value = {
            "tx": {"time": self.old_timestamp, "amount": "1", "asset": "BTC"}
        }
        result = report.update_asset_report()
        assert isinstance(result, pd.DataFrame)
        assert result.empty  # instead of self.assertIsNone(result)
        # self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
