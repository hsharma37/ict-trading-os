"""
Simple Lot Calculator — calculates position size based on risk % and stop loss distance.
No leverage used in lot sizing (leverage only affects margin, not position size).
"""
from typing import Dict, Optional
from app.services.instrument_config import get_instrument
from app.services.market_data import market_service


# Standard pip/point value per 1.0 lot in USD (industry standard)
# These are the actual monetary values of 1 pip/point move per 1.0 lot
PIP_VALUES = {
    "EURUSD": 10.0,      # $10 per pip (0.0001) per 1.0 lot (100k units)
    "GBPUSD": 10.0,      # $10 per pip per 1.0 lot
    "USDJPY": 6.67,      # ~$6.67 per pip (0.01) per 1.0 lot (varies with rate)
    "XAUUSD": 1.0,       # $1 per pip (0.01) per 1.0 lot (100 oz)
    "NQ1!": 20.0,        # $20 per point per 1.0 contract
    "ES1!": 50.0,        # $50 per point per 1.0 contract
    "BTCUSD": 1.0,       # $1 per $1 move per 1.0 lot (1 BTC)
    "CL1!": 10.0,        # $10 per 0.01 move per 1.0 lot (1000 barrels)
}

# Minimum lot size and step size
LOT_CONFIG = {
    "EURUSD": {"min": 0.01, "step": 0.01},
    "GBPUSD": {"min": 0.01, "step": 0.01},
    "USDJPY": {"min": 0.01, "step": 0.01},
    "XAUUSD": {"min": 0.01, "step": 0.01},
    "NQ1!": {"min": 0.01, "step": 0.01},
    "ES1!": {"min": 0.01, "step": 0.01},
    "BTCUSD": {"min": 0.001, "step": 0.001},
    "CL1!": {"min": 0.01, "step": 0.01},
}

# Pip/point size for each instrument
PIP_SIZES = {
    "EURUSD": 0.0001,
    "GBPUSD": 0.0001,
    "USDJPY": 0.01,
    "XAUUSD": 0.01,
    "NQ1!": 1.0,
    "ES1!": 1.0,
    "BTCUSD": 1.0,
    "CL1!": 0.01,
}


class LotCalculator:
    """Calculate lot size based on risk % and stop loss distance."""

    def calculate(
        self,
        symbol: str,
        entry_price: float,
        stop_loss: float,
        account_balance: float = 10000.0,
        risk_pct: float = 1.0,
    ) -> Dict:
        """
        Calculate lot size for a trade.

        Formula:
        risk_amount = account_balance * (risk_pct / 100)
        price_distance = abs(entry_price - stop_loss)
        pip_distance = price_distance / pip_size
        lot_size = risk_amount / (pip_distance * pip_value_per_lot)

        Where pip_value_per_lot is the standard USD value of 1 pip per 1.0 lot.
        """
        symbol = symbol.upper()
        config = get_instrument(symbol)
        if not config:
            return {"symbol": symbol, "error": "Unknown symbol"}

        price_distance = abs(entry_price - stop_loss)
        if price_distance <= 0:
            return {
                "symbol": symbol,
                "error": "Entry price and stop loss must differ",
                "entry_price": entry_price,
                "stop_loss": stop_loss,
            }

        pip_size = PIP_SIZES.get(symbol, 0.0001)
        pip_value = PIP_VALUES.get(symbol, 10.0)
        lot_cfg = LOT_CONFIG.get(symbol, {"min": 0.01, "step": 0.01})
        digits = config.get("digits", 5)

        # Calculate risk amount
        risk_amount = account_balance * (risk_pct / 100.0)

        # Calculate pip distance
        pip_distance = price_distance / pip_size if pip_size > 0 else price_distance

        # Total monetary risk per 1.0 lot for this SL distance. Prefer the
        # broker's REAL tick value (exact for any quote currency, e.g. USDCAD);
        # fall back to the static pip value when the bridge isn't connected.
        #
        # BUT sanity-check the broker value against static — for USD-QUOTED
        # symbols only. A broker that reports an understated tick_value/tick_size
        # ratio (seen on XAUUSD) makes risk-per-lot too small and the lot
        # balloons. The static pip value is EXACT for USD-quoted symbols (majors,
        # gold), so there we trust the broker figure only within a sane band
        # (0.5×–2×) of static and reject 10×/100× spec errors. For non-USD-quoted
        # pairs (USDCAD, USDJPY) static is a rough default and the broker value is
        # the authority, so we take it unconditionally.
        rate_source = "static"
        static_rpl = pip_distance * pip_value
        risk_per_lot = static_rpl
        usd_quoted = symbol.endswith("USD")
        try:
            from app.services.broker_specs import money_per_lot
            broker_rpl = money_per_lot(symbol, price_distance)
            if broker_rpl and broker_rpl > 0:
                if usd_quoted and static_rpl > 0 and not (0.5 * static_rpl <= broker_rpl <= 2.0 * static_rpl):
                    rate_source = "static (broker spec rejected)"  # implausible broker value
                else:
                    risk_per_lot = broker_rpl
                    rate_source = "mt5"
        except Exception:
            pass

        if risk_per_lot <= 0:
            return {
                "symbol": symbol,
                "error": "Cannot calculate lot size: risk per lot is zero",
            }

        # Raw lot size
        raw_lot = risk_amount / risk_per_lot

        # Round to lot step
        step = lot_cfg["step"]
        lot_size = round(raw_lot / step) * step
        lot_size = max(lot_cfg["min"], lot_size)
        lot_size = round(lot_size, 6)

        # Actual risk with rounded lot size (uses the same broker/static basis)
        actual_risk = risk_per_lot * lot_size
        actual_risk_pct = (actual_risk / account_balance * 100) if account_balance > 0 else 0

        # Notional value (position value) — for info only
        contract_size = config.get("contract_size", 100000)
        notional_value = lot_size * contract_size * entry_price

        # Margin (at 1:100 leverage for display only — leverage doesn't affect lot size)
        leverage = config.get("leverage", 100)
        margin_required = notional_value / leverage if leverage > 0 else 0

        return {
            "symbol": symbol,
            "label": config.get("label", symbol),
            "kind": config.get("kind", "unknown"),
            "entry_price": round(entry_price, digits),
            "stop_loss": round(stop_loss, digits),
            "price_distance": round(price_distance, digits),
            "pip_distance": round(pip_distance, 2),
            "risk_amount": round(risk_amount, 2),
            "risk_pct": round(risk_pct, 2),
            "lot_size": lot_size,
            "unit": config.get("unit", "lot"),
            "contract_size": contract_size,
            "pip_size": pip_size,
            "pip_value": pip_value,
            "notional_value": round(notional_value, 2),
            "margin_required": round(margin_required, 2),
            "actual_risk": round(actual_risk, 2),
            "actual_risk_pct": round(actual_risk_pct, 2),
            "risk_per_lot": round(risk_per_lot, 2),
            "rate_source": rate_source,  # "mt5" (broker tick value) or "static"
            "digits": digits,
            "leverage": leverage,  # for display only
        }

    def calculate_with_live_price(
        self,
        symbol: str,
        stop_loss: float,
        account_balance: float = 10000.0,
        risk_pct: float = 1.0,
        side: str = "BUY",
    ) -> Dict:
        """Calculate lot size using live market price."""
        live = market_service.get_price(symbol)
        price = live.get("price", 0)
        if price <= 0:
            return {"symbol": symbol, "error": "Could not fetch live price", "live_response": live}
        return self.calculate(symbol, price, stop_loss, account_balance, risk_pct)

    def quick_lot(
        self,
        symbol: str,
        account_balance: float,
        risk_pct: float,
        sl_pips: float,
        entry_price: Optional[float] = None,
        side: str = "BUY",
    ) -> Dict:
        """Quick lot calculation using pip distance instead of absolute price."""
        symbol = symbol.upper()
        side = side.upper()
        config = get_instrument(symbol)
        if not config:
            return {"symbol": symbol, "error": "Unknown symbol"}

        if entry_price is None or entry_price <= 0:
            live = market_service.get_price(symbol)
            entry_price = live.get("price", 0)
            if entry_price <= 0:
                return {"symbol": symbol, "error": "Could not fetch live price"}

        pip_size = PIP_SIZES.get(symbol, 0.0001)
        if side == "BUY":
            sl_price = entry_price - (sl_pips * pip_size)
        else:  # SELL
            sl_price = entry_price + (sl_pips * pip_size)

        return self.calculate(symbol, entry_price, sl_price, account_balance, risk_pct)

    def calculate_pnl(self, symbol: str, entry: float, exit: float, lot_size: float, side: str = "BUY") -> Dict:
        """Calculate P&L for a closed trade."""
        symbol = symbol.upper()
        pip_size = PIP_SIZES.get(symbol, 0.0001)
        pip_value = PIP_VALUES.get(symbol, 10.0)
        config = get_instrument(symbol)
        digits = config.get("digits", 5) if config else 5

        price_diff = exit - entry if side.upper() == "BUY" else entry - exit
        pip_diff = price_diff / pip_size if pip_size > 0 else price_diff
        pnl = pip_diff * pip_value * lot_size

        return {
            "symbol": symbol,
            "entry": round(entry, digits),
            "exit": round(exit, digits),
            "lot_size": lot_size,
            "side": side.upper(),
            "price_diff": round(price_diff, digits),
            "pip_diff": round(pip_diff, 2),
            "pnl": round(pnl, 2),
            "pnl_currency": "USD",
        }


lot_calculator = LotCalculator()
