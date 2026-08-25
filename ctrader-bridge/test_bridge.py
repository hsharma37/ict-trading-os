"""
Unit tests for the cTrader bridge — conversion math and normalizers.
No network: the OpenApiPy client is not exercised (it needs real credentials);
these tests pin the unit conventions and output shapes the app depends on.
"""
import os
import sys
import unittest

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from ctrader_client import (  # noqa: E402
    CTraderClient, normalize_tick, _price, _money, moneyDigits_or_default,
    RETCODE_DONE, RETCODE_PLACED, RETCODE_REJECTED,
)


class TestUnitConventions(unittest.TestCase):
    """The proto's wire units — getting these wrong silently mis-prices everything."""

    def test_wire_price_division(self):
        # Proto: "1/100000 of unit of a price" — 123000 means 1.23.
        self.assertAlmostEqual(_price(123000), 1.23)
        self.assertAlmostEqual(_price(53423782), 534.23782)

    def test_money_scaling_default_digits(self):
        self.assertAlmostEqual(_money(10053099944, 8), 100.53099944)
        self.assertEqual(_money(None, 8), 0.0)

    def test_money_digits_default(self):
        self.assertEqual(moneyDigits_or_default(0), 8)
        self.assertEqual(moneyDigits_or_default(None), 8)
        self.assertEqual(moneyDigits_or_default(2), 2)

    def test_retcode_vocabulary_matches_mt5(self):
        # planner_service + the /mt5 router accept exactly 10008/10009/10010.
        self.assertIn(RETCODE_DONE, (10008, 10009, 10010))
        self.assertIn(RETCODE_PLACED, (10008, 10009, 10010))
        self.assertNotIn(RETCODE_REJECTED, (10008, 10009, 10010))


class TestTickShape(unittest.TestCase):
    """Must match mt5_client.normalize_tick — the app's price contract."""

    def test_shape_and_mid(self):
        tick = normalize_tick("EURUSD", bid_raw=108500, ask_raw=108510,
                              ts_ms=1_700_000_000_000)
        self.assertEqual(tick["symbol"], "EURUSD")
        self.assertAlmostEqual(tick["bid"], 1.08500)
        self.assertAlmostEqual(tick["ask"], 1.08510)
        self.assertAlmostEqual(tick["price"], 1.08505)  # mid
        self.assertAlmostEqual(tick["spread"], 0.0001, places=7)
        self.assertEqual(tick["source"], "ctrader")
        self.assertIsNotNone(tick["time"])

    def test_bid_only(self):
        tick = normalize_tick("XAUUSD", bid_raw=250050000, ask_raw=0, ts_ms=None)
        self.assertAlmostEqual(tick["price"], 2500.50)
        self.assertEqual(tick["spread"], 0)


class TestLotConversion(unittest.TestCase):
    """lots <-> cents-of-units via the symbol's lotSize (default 100k units)."""

    def _client(self) -> CTraderClient:
        c = CTraderClient.__new__(CTraderClient)  # bypass __init__ (no network)
        c._symbols_by_name = {"EURUSD": 1}
        c._symbol_names = {1: "EURUSD"}
        c._symbol_details = {}
        return c

    def test_lots_to_volume_standard_lot(self):
        c = self._client()
        c._lot_size_cents = lambda sid: 10_000_000  # 100k units == 1 lot
        self.assertEqual(c.lots_to_volume("EURUSD", 1.0), 10_000_000)
        self.assertEqual(c.lots_to_volume("EURUSD", 0.01), 100_000)

    def test_volume_to_lots_roundtrip(self):
        c = self._client()
        c._lot_size_cents = lambda sid: 10_000_000
        self.assertEqual(c.volume_to_lots(1, 10_000_000), 1.0)
        self.assertEqual(c.volume_to_lots(1, 150_000), 0.015)

    def test_gold_lot_size(self):
        # Brokers where 1 lot of XAUUSD = 100 oz: lotSize = 100 units * 100.
        c = self._client()
        c._lot_size_cents = lambda sid: 10_000
        self.assertEqual(c.lots_to_volume("EURUSD", 2.0), 20_000)


class TestSymbolNameNorm(unittest.TestCase):
    def test_normalization(self):
        self.assertEqual(CTraderClient._norm_name("EUR/USD"), "EURUSD")
        self.assertEqual(CTraderClient._norm_name("xauusd"), "XAUUSD")
        self.assertEqual(CTraderClient._norm_name("USD_JPY"), "USDJPY")


class TestTrendbarDecoding(unittest.TestCase):
    """Trendbar: low is absolute, open/high/close are deltas from low."""

    def test_delta_decoding(self):
        low_raw = 108_500            # 1.08500
        d_open, d_high, d_close = 50, 120, 100  # +0.00050, +0.00120, +0.00100
        low = _price(low_raw)
        bar = {
            "open": low + _price(d_open),
            "high": low + _price(d_high),
            "low": low,
            "close": low + _price(d_close),
        }
        self.assertAlmostEqual(bar["open"], 1.0855)
        self.assertAlmostEqual(bar["high"], 1.0862)
        self.assertAlmostEqual(bar["close"], 1.0860)
        self.assertGreaterEqual(bar["high"], bar["low"])  # invariant


if __name__ == "__main__":
    unittest.main()
