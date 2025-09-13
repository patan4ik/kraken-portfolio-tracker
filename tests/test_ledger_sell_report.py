# tests/test_ledger_sell_report.py
import unittest
from unittest.mock import patch
from datetime import datetime, timezone, timedelta
import pandas as pd
import sys
import os

sys.path.insert(
    0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..", "src"))
)
import ledger_sell_report as report


class TestLedgerSellReport(unittest.TestCase):

    def setUp(self):
        now = datetime.now(timezone.utc)
        self.recent_ts = now.timestamp()
        self.old_ts = (now - timedelta(days=10)).timestamp()

        self.entries = {
            "tx1": {
                "time": self.recent_ts,
                "amount": "-0.5",
                "asset": "BTC",
                "fee": "0.01",
            },
            "tx2": {
                "time": self.recent_ts,
                "amount": "1000",
                "asset": "EUR",
                "refid": "tx1",
            },
            "tx3": {
                "time": self.recent_ts,
                "amount": "-1.0",
                "asset": "ETH",
                "fee": "0.02",
            },
            "tx4": {
                "time": self.recent_ts,
                "amount": "500",
                "asset": "ZEUR",
                "refid": "tx3",
            },
            "tx5": {
                "time": self.old_ts,
                "amount": "-2.0",
                "asset": "BTC",
                "fee": "0.03",
            },  # outside cutoff
        }

    def test_build_sell_report_empty_input(self):
        df = report.build_sell_report({})
        self.assertTrue(df.empty)

    def test_build_sell_report_all_filtered_out(self):
        df = report.build_sell_report(
            {"tx": {"time": self.old_ts, "amount": "-1", "asset": "BTC"}}, days=7
        )
        self.assertTrue(df.empty)

    def test_build_sell_report_valid_entries(self):
        df = report.build_sell_report(self.entries, days=7)
        self.assertFalse(df.empty)
        self.assertIn("BTC", df.columns)
        self.assertIn("ETH", df.columns)
        self.assertIn("Total EUR", df.columns)
        self.assertIn("Total Fee", df.columns)
        self.assertEqual(df["BTC"].sum(), 0.5)
        self.assertEqual(df["ETH"].sum(), 1.0)
        self.assertEqual(df["Total EUR"].sum(), 1500)
        self.assertAlmostEqual(df["Total Fee"].sum(), 0.03)

    @patch("ledger_sell_report.storage.BALANCES_DIR", "mock_dir")
    @patch("ledger_sell_report.pd.DataFrame.to_csv")
    @patch("ledger_sell_report.os.makedirs")
    def test_save_sell_report(self, mock_makedirs, mock_to_csv):
        df = pd.DataFrame(
            [{"Date": "01.01.2023", "BTC": 0.5, "Total EUR": 1000, "Total Fee": 0.01}]
        )
        report.save_sell_report(df)
        mock_makedirs.assert_called_once_with("mock_dir", exist_ok=True)
        mock_to_csv.assert_called_once()

    @patch("ledger_sell_report.storage.load_entries_from_db")
    def test_update_sell_report_no_entries(self, mock_load):
        mock_load.return_value = {}
        result = report.update_sell_report()
        self.assertIsNone(result)

    @patch("ledger_sell_report.save_sell_report")
    @patch("ledger_sell_report.storage.load_entries_from_db")
    def test_update_sell_report_with_csv(self, mock_load, mock_save):
        mock_load.return_value = self.entries
        df = report.update_sell_report(write_csv=True)
        self.assertIsInstance(df, pd.DataFrame)
        mock_save.assert_called_once()

    @patch("ledger_sell_report.storage.load_entries_from_db")
    def test_update_sell_report_empty_df(self, mock_load):
        mock_load.return_value = {
            "tx": {"time": self.old_ts, "amount": "-1", "asset": "BTC"}
        }
        result = report.update_sell_report()
        self.assertIsNone(result)


if __name__ == "__main__":
    unittest.main()
