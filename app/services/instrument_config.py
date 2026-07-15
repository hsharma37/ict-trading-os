"""Comprehensive instrument configuration with FundingPips leverage."""
from typing import Dict, Any

# Only instruments the app actively trades/prices. Kept to the set that exists
# on the MT5 broker (MetaQuotes-Demo) and has exact lot-calc config, so the
# real-time price feed, the execution allow-list, and research all stay within
# what can actually be traded. (TradingView-only tickers like NQ1!/ES1!/BTCUSD/
# CL1! were removed — the broker doesn't carry them.)
INSTRUMENTS: Dict[str, Dict[str, Any]] = {
    "EURUSD": {
        "label": "EUR/USD",
        "ticker": "EURUSD=X",
        "yahoo": "EURUSD=X",
        "oanda": "EUR_USD",
        "kind": "fx",
        "digits": 5,
        "pip_digits": 4,
        "pip_val": 10.0,
        "mult": 100000,
        "contract_size": 100000,
        "leverage": 100,
        "tick_size": 0.00001,
        "tick_value": 1.0,
        "min_qty": 0.01,
        "qty_step": 0.01,
        "point_value": 100000.0,
        "unit": "lot",
        "session_open_utc": "22:00",
        "session_close_utc": "21:00",
    },
    "GBPUSD": {
        "label": "GBP/USD",
        "ticker": "GBPUSD=X",
        "yahoo": "GBPUSD=X",
        "oanda": "GBP_USD",
        "kind": "fx",
        "digits": 5,
        "pip_digits": 4,
        "pip_val": 10.0,
        "mult": 100000,
        "contract_size": 100000,
        "leverage": 100,
        "tick_size": 0.00001,
        "tick_value": 1.0,
        "min_qty": 0.01,
        "qty_step": 0.01,
        "point_value": 100000.0,
        "unit": "lot",
        "session_open_utc": "22:00",
        "session_close_utc": "21:00",
    },
    "AUDUSD": {
        "label": "AUD/USD",
        "ticker": "AUDUSD=X",
        "yahoo": "AUDUSD=X",
        "oanda": "AUD_USD",
        "kind": "fx",
        "digits": 5,
        "pip_digits": 4,
        "pip_val": 10.0,
        "mult": 100000,
        "contract_size": 100000,
        "leverage": 100,
        "tick_size": 0.00001,
        "tick_value": 1.0,
        "min_qty": 0.01,
        "qty_step": 0.01,
        "point_value": 100000.0,
        "unit": "lot",
        "session_open_utc": "22:00",
        "session_close_utc": "21:00",
    },
    "NZDUSD": {
        "label": "NZD/USD",
        "ticker": "NZDUSD=X",
        "yahoo": "NZDUSD=X",
        "oanda": "NZD_USD",
        "kind": "fx",
        "digits": 5,
        "pip_digits": 4,
        "pip_val": 10.0,
        "mult": 100000,
        "contract_size": 100000,
        "leverage": 100,
        "tick_size": 0.00001,
        "tick_value": 1.0,
        "min_qty": 0.01,
        "qty_step": 0.01,
        "point_value": 100000.0,
        "unit": "lot",
        "session_open_utc": "22:00",
        "session_close_utc": "21:00",
    },
    "USDCAD": {
        "label": "USD/CAD",
        "ticker": "USDCAD=X",
        "yahoo": "USDCAD=X",
        "oanda": "USD_CAD",
        "kind": "fx",
        "digits": 5,
        "pip_digits": 4,
        # CAD-quoted: pip value in USD ≈ 10 / USDCAD ≈ $7.1/lot at ~1.40. Static
        # approximation for sizing; actual P&L/R come from the broker (exact).
        "pip_val": 7.1,
        "mult": 100000,
        "contract_size": 100000,
        "leverage": 100,
        "tick_size": 0.00001,
        "tick_value": 0.71,
        "min_qty": 0.01,
        "qty_step": 0.01,
        "point_value": 100000.0,
        "unit": "lot",
        "session_open_utc": "22:00",
        "session_close_utc": "21:00",
    },
    "XAUUSD": {
        "label": "XAU/USD (Gold)",
        "ticker": "GC=F",
        "yahoo": "GC=F",
        "oanda": "XAU_USD",
        "kind": "metal",
        "digits": 2,
        "pip_digits": 2,
        "pip_val": 1.0,  # gold: $1 per 0.01 move per 1.0 lot (100 oz) — not the FX $10
        "mult": 100,
        "contract_size": 100,
        "leverage": 10,
        "tick_size": 0.01,
        "tick_value": 1.0,
        "min_qty": 0.01,
        "qty_step": 0.01,
        "point_value": 100.0,
        "unit": "oz",
        "session_open_utc": "22:00",
        "session_close_utc": "21:00",
    },
    "USDJPY": {
        "label": "USD/JPY",
        "ticker": "USDJPY=X",
        "yahoo": "USDJPY=X",
        "oanda": "USD_JPY",
        "kind": "fx",
        "digits": 3,
        "pip_digits": 2,
        "pip_val": 9.1,
        "mult": 100000,
        "contract_size": 100000,
        "leverage": 100,
        "tick_size": 0.001,
        "tick_value": 100.0,
        "min_qty": 0.01,
        "qty_step": 0.01,
        "point_value": 1000.0,
        "unit": "lot",
        "session_open_utc": "22:00",
        "session_close_utc": "21:00",
    },
}

KIND_LABELS = {
    "fx": "Forex",
    "index": "Index",
    "metal": "Metal",
    "crypto": "Crypto",
    "commodity": "Commodity",
}


def get_instrument(symbol: str) -> Dict[str, Any]:
    """Get instrument config by symbol."""
    return INSTRUMENTS.get(symbol.upper(), INSTRUMENTS.get(symbol, {}))


def get_all_instruments() -> Dict[str, Dict[str, Any]]:
    """Get all instrument configs."""
    return INSTRUMENTS


def get_kind_label(kind: str) -> str:
    """Get human-readable label for kind."""
    return KIND_LABELS.get(kind, kind.title())
