"""
MT5 Bridge — Refactored Server.

Replaces the monolithic `mt5bridgeScript.py` with a clean, modular
Flask-based bridge that proxies trades to MetaTrader 5 and sends
Telegram notifications.

For Phase 1, this is a scaffold. It will be populated with the
existing trade logic from `mt5bridgeScript.py` in a subsequent update.
"""
import logging
import json
from datetime import datetime
from flask import Flask, request, jsonify

from config import config
from telegram_bot import TelegramNotifier

# ────────────────────────────────────────────────
# Logging
# ────────────────────────────────────────────────
logging.basicConfig(
    level=getattr(logging, config.log_level.upper(), logging.INFO),
    format="[%(asctime)s] %(levelname)s %(name)s: %(message)s",
)
logger = logging.getLogger(__name__)

# ────────────────────────────────────────────────
# Flask App
# ────────────────────────────────────────────────
app = Flask(__name__)

# Telegram notifier instance
telegram = TelegramNotifier()

# ────────────────────────────────────────────────
# Health Check
# ────────────────────────────────────────────────


@app.route("/", methods=["GET"])
def index():
    """Bridge status endpoint."""
    return jsonify({
        "status": "ok",
        "service": "ict-os-mt5-bridge",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "telegram_configured": telegram.is_configured(),
    })


@app.route("/health", methods=["GET"])
def health():
    """Detailed health check."""
    return jsonify({
        "status": "healthy",
        "timestamp": datetime.utcnow().isoformat(),
    })


# ────────────────────────────────────────────────
# Trade Endpoints
# ────────────────────────────────────────────────


@app.route("/trade", methods=["POST"])
def trade():
    """
    Execute a trade via MetaTrader 5.

    Expected JSON body:
    {
        "symbol": "EURUSD",
        "direction": "long" | "short",
        "lot_size": 0.5,
        "stop_loss": 1.08000,
        "take_profit": 1.09000
    }
    """
    data = request.get_json(force=True)

    symbol = data.get("symbol", "UNKNOWN")
    direction = data.get("direction", "long")
    lot_size = data.get("lot_size", 0.0)
    stop_loss = data.get("stop_loss")
    take_profit = data.get("take_profit")

    # TODO: Phase 2 — integrate actual MT5 trade execution logic
    # For now, simulate a successful trade response
    logger.info(f"Trade request: {symbol} {direction} @ {lot_size} lots")

    trade_result = {
        "status": "simulated",
        "symbol": symbol,
        "direction": direction,
        "lot_size": lot_size,
        "stop_loss": stop_loss,
        "take_profit": take_profit,
        "ticket_id": "SIM-12345",
        "timestamp": datetime.utcnow().isoformat(),
    }

    # Send Telegram notification
    telegram.send_trade_notification(symbol, direction, lot_size, 0.0, stop_loss or 0.0, take_profit or 0.0)

    return jsonify(trade_result)


# ────────────────────────────────────────────────
# Account / Positions
# ────────────────────────────────────────────────


@app.route("/account", methods=["GET"])
def account():
    """Get MT5 account summary."""
    # TODO: Phase 2 — integrate actual MT5 account info
    return jsonify({
        "balance": 10000.00,
        "equity": 10000.00,
        "margin": 0.00,
        "free_margin": 10000.00,
        "margin_level": 0.0,
        "status": "simulated",
    })


@app.route("/positions", methods=["GET"])
def positions():
    """Get open positions from MT5."""
    # TODO: Phase 2 — integrate actual MT5 positions
    return jsonify({
        "positions": [],
        "count": 0,
        "status": "simulated",
    })


# ────────────────────────────────────────────────
# Telegram Test
# ────────────────────────────────────────────────


@app.route("/test-telegram", methods=["POST"])
def test_telegram():
    """Send a test message via Telegram."""
    result = telegram.test()
    return jsonify(result)


# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────

if __name__ == "__main__":
    logger.info(f"Starting MT5 Bridge on port {config.bridge_port}")
    app.run(host="0.0.0.0", port=config.bridge_port, debug=False)
