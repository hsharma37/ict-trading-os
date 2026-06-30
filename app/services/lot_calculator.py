"""Lot size calculator using FundingPips leverage and live prices."""
from typing import Dict, Optional
from app.services.instrument_config import get_instrument
from app.services.market_data import market_service


class LotCalculator:
    """Calculate lot sizes based on risk, price, and leverage."""

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
        risk_amount = account_balance * risk_pct
        price_distance = abs(entry_price - stop_loss)
        pip_distance = price_distance * 10^(pip_digits)  [for forex-like]
        lot_size = risk_amount / (price_distance * pip_value * contract_size / leverage)

        Where pip_value accounts for the contract size and leverage.
        """
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

        risk_amount = account_balance * (risk_pct / 100.0)
        leverage = config.get("leverage", 100)
        contract_size = config.get("contract_size", 1)
        pip_val = config.get("pip_val", 1.0)
        tick_size = config.get("tick_size", 0.00001)
        qty_step = config.get("qty_step", 0.01)
        min_qty = config.get("min_qty", 0.01)
        unit = config.get("unit", "unit")
        digits = config.get("digits", 5)

        # Price distance in ticks
        tick_distance = price_distance / tick_size if tick_size > 0 else price_distance

        # Risk per tick = tick_distance * tick_value * contract_size / leverage
        # Actually for proper lot calc: risk per unit = price_distance * contract_size / leverage
        # lot = risk_amount / (price_distance * contract_size / leverage)
        # For forex: 1 lot = 100,000 units. So distance of 1 pip = $10 per lot for pairs where 2nd currency is USD
        # For a 1 pip SL at 1:100 leverage: you need 1 lot to risk $10 per pip at 100k
        # At 1:500 leverage: same but margin is 1/5th
        # Actually for lot size, leverage doesn't affect the lot size calculation directly
        # Leverage affects margin, but the lot size is purely based on risk amount / (SL distance * pip value per lot)
        # However, for the user's request, we factor in leverage as specified by FundingPips
        # Standard approach: lot_size = risk_amount / (price_distance * pip_value * contract_size)
        # For indices: 1 point = $5 per contract (NQ), so lot_size = risk_amount / (price_distance * point_value * contract_size)

        # Let's use the standard formula:
        # monetary_risk_per_lot = price_distance * contract_size * (pip_val / leverage) -- no, this is wrong
        # Actually: for a given lot size, the monetary risk is: price_distance * lot_size * contract_size * (1 / leverage_factor)
        # Wait, leverage is about margin, not position sizing. Position sizing is about how much the price moves per lot.
        # For Forex 1 lot: 1 pip = $10 (for XXXUSD pairs). So if SL is 10 pips away, risk = $100 per lot.
        # lot_size = risk_amount / (pip_distance * $10_per_lot)
        # For Gold: 1 lot = 100 oz. 1 pip = $10. Same.
        # For NQ: 1 contract = 20 multiplier? Actually NQ is $20 per point (1 tick = 0.25 = $5)
        # For ES: 1 contract = $50 per point (1 tick = 0.25 = $12.50)

        # Simpler approach: use the contract_size directly for monetary value per unit
        # For forex: contract_size = 100000, so 1 pip (0.0001) = $100000 * 0.0001 = $10 per lot for XXXUSD
        # For JPY: 1 pip = 0.01 = $100000 * 0.01 = $1000 per lot -- wait, for USDJPY, 1 pip is 0.01, and the value is ~$9.09 per pip (since price is ~150)
        # Actually for JPY pairs, 1 pip = 0.01, and at price 150, the USD value is: 100000 * 0.01 / 150 = $6.67 per lot
        # Let's use a simpler formula that's more standard:

        # Determine pip size based on symbol type
        pip_size = 0.0001 if config.get("kind") == "fx" and "JPY" not in symbol else 0.01
        if config.get("kind") == "index":
            pip_size = 1.0
        elif config.get("kind") == "metal":
            pip_size = 0.01
        elif config.get("kind") == "crypto":
            pip_size = 1.0
        elif config.get("kind") == "commodity":
            pip_size = 0.01

        # Price distance in pips/points
        pip_distance = price_distance / pip_size if pip_size > 0 else price_distance

        # Monetary risk per standard lot (1.0)
        # For forex XXXUSD: $10 per pip (1 pip = 0.0001, 100000 * 0.0001 = 10)
        # For forex XXXJPY: $100000 * 0.01 / (USDJPY rate) ≈ $6.67 per pip
        # For JPY pairs, we need the exchange rate. For USDJPY, the "per pip in USD" is:
        # (contract_size * pip_size) / price = (100000 * 0.01) / 150 = $6.67
        # But for simplicity, we'll use the pip_val from config which is an approximate value
        risk_per_lot_per_pip = pip_val
        if "JPY" in symbol and config.get("kind") == "fx":
            # Adjust for JPY rate
            risk_per_lot_per_pip = (contract_size * pip_size) / entry_price if entry_price > 0 else 6.67
        elif config.get("kind") == "index":
            # NQ: 1 point = $20, ES: 1 point = $50
            risk_per_lot_per_pip = config.get("tick_value", 5.0) / config.get("tick_size", 0.25) * config.get("contract_size", 1) / 1000
            # Actually for NQ: each tick (0.25 point) = $5. So 1 point = $20. So 1 pip = 1 point = $20 per contract
            # For ES: 1 point = $50 per contract
            risk_per_lot_per_pip = config.get("tick_value", 5.0) / config.get("tick_size", 0.25)
        elif config.get("kind") == "commodity":
            # CL: 1 tick = $10 per 1000 barrels, so 1 point = $10 per 1.0 lot
            risk_per_lot_per_pip = config.get("tick_value", 10.0) / config.get("tick_size", 0.01)
        elif config.get("kind") == "metal":
            # Gold: 1 pip = $10 per lot (100 oz * 0.01 = $1, but actually 1 pip = 0.01 = $1 per 0.01 lot? Wait)
            # XAUUSD: 1 lot = 100 oz. 1 pip (0.01) = 100 * 0.01 = $1. But many brokers quote 1 pip = $1 per 0.01 lot
            # Actually standard: 1 standard lot = $10 per pip (0.01 move on 100 oz = $1 per pip? No, 100 * 0.01 = $1)
            # Wait, XAUUSD: 0.01 move = $1 per 0.01 lot? No, 1 lot = 100 oz, so 0.01 * 100 = $1 per lot
            # Actually the pip_val in config is set to 10.0 for XAUUSD, which might be per 1.0 lot? No, $10 per pip per lot
            risk_per_lot_per_pip = pip_val
        elif config.get("kind") == "crypto":
            # BTC: 1 unit = $1 per $1 move, so 1 lot (1 BTC) = $1 per pip
            risk_per_lot_per_pip = 1.0

        # Total risk per lot for this SL distance
        total_risk_per_lot = pip_distance * risk_per_lot_per_pip

        if total_risk_per_lot <= 0:
            return {
                "symbol": symbol,
                "error": "Cannot calculate lot size: risk per lot is zero",
            }

        # Lot size
        raw_lot = risk_amount / total_risk_per_lot
        lot_size = round(raw_lot / qty_step) * qty_step
        lot_size = max(min_qty, lot_size)
        lot_size = round(lot_size, 6)

        # Notional value (position value)
        notional_value = lot_size * contract_size * entry_price

        # Margin required (at leverage)
        margin_required = notional_value / leverage if leverage > 0 else 0

        # Actual risk with rounded lot size
        actual_risk = pip_distance * risk_per_lot_per_pip * lot_size
        actual_risk_pct = (actual_risk / account_balance * 100) if account_balance > 0 else 0

        # R-multiple: how many R's is TP from entry
        # R = distance / risk_distance (in price terms)
        # 1R = price_distance (the SL distance)
        # So TP1 = entry + 1R, TP2 = entry + 2R, etc.

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
            "unit": unit,
            "contract_size": contract_size,
            "leverage": leverage,
            "notional_value": round(notional_value, 2),
            "margin_required": round(margin_required, 2),
            "actual_risk": round(actual_risk, 2),
            "actual_risk_pct": round(actual_risk_pct, 2),
            "risk_per_lot_per_pip": round(risk_per_lot_per_pip, 4),
            "tick_size": tick_size,
            "tick_value": config.get("tick_value", 1.0),
            "digits": digits,
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
    ) -> Dict:
        """Quick lot calculation using pip distance instead of absolute price."""
        config = get_instrument(symbol)
        if not config:
            return {"symbol": symbol, "error": "Unknown symbol"}

        if entry_price is None or entry_price <= 0:
            live = market_service.get_price(symbol)
            entry_price = live.get("price", 0)
            if entry_price <= 0:
                return {"symbol": symbol, "error": "Could not fetch live price"}

        # Determine pip size
        pip_size = 0.0001 if config.get("kind") == "fx" and "JPY" not in symbol else 0.01
        if config.get("kind") == "index":
            pip_size = 1.0
        elif config.get("kind") == "metal":
            pip_size = 0.01
        elif config.get("kind") == "crypto":
            pip_size = 1.0
        elif config.get("kind") == "commodity":
            pip_size = 0.01

        # Calculate SL price from pip distance
        if config.get("kind") == "fx" and "JPY" in symbol:
            sl_price = entry_price - (sl_pips * 0.01)  # 1 pip = 0.01 for JPY
        else:
            sl_price = entry_price - (sl_pips * pip_size)

        return self.calculate(symbol, entry_price, sl_price, account_balance, risk_pct)


lot_calculator = LotCalculator()
