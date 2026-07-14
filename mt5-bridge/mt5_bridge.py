"""
MT5 Bridge — bridges ICT Trading OS to a local MetaTrader 5 terminal.

Must run on Windows, on the same machine as a running, logged-in MT5
terminal — MetaTrader5's Python API has no remote/cloud mode. Expose this
process to the internet (e.g. via ngrok or a reverse proxy) and set
MT5_BRIDGE_URL + MT5_BRIDGE_API_KEY on the main app to reach it. See
.env.example and README.md for full setup.
"""
import logging
from datetime import datetime
from functools import wraps
from flask import Flask, request, jsonify

from config import config
from telegram_bot import TelegramNotifier
from mt5_client import Mt5Client, Mt5ConnectionError

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

telegram = TelegramNotifier()
mt5_client = Mt5Client(config.mt5_login, config.mt5_password, config.mt5_server, config.mt5_terminal_path)


def require_bridge_key(fn):
    """Reject requests without the shared bridge key, once one is configured.

    This bridge is meant to be tunneled to the internet so the deployed app
    can reach it; without this, anyone who finds the URL could read the
    account or place trades. Bypassed only when MT5_BRIDGE_API_KEY is unset
    (e.g. pure localhost dev).
    """
    @wraps(fn)
    def wrapper(*args, **kwargs):
        if config.bridge_api_key:
            provided = request.headers.get("X-Bridge-Key", "")
            if provided != config.bridge_api_key:
                return jsonify({"error": "Unauthorized. Provide X-Bridge-Key header."}), 401
        return fn(*args, **kwargs)
    return wrapper


# ────────────────────────────────────────────────
# Health Check
# ────────────────────────────────────────────────


@app.route("/", methods=["GET"])
def index():
    """Bridge status endpoint — deliberately unauthenticated so MT5_BRIDGE_URL
    connectivity can be checked without a key."""
    return jsonify({
        "status": "ok",
        "service": "ict-os-mt5-bridge",
        "version": "2.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "mt5_package_available": mt5_client.available(),
        "mt5_connected": mt5_client.is_connected(),
        "telegram_configured": telegram.is_configured(),
    })


@app.route("/health", methods=["GET"])
def health():
    """Detailed health check."""
    return jsonify({"status": "healthy", "timestamp": datetime.utcnow().isoformat()})


# ────────────────────────────────────────────────
# Trade Endpoints
# ────────────────────────────────────────────────


@app.route("/trade", methods=["POST"])
@require_bridge_key
def trade():
    """
    Execute a real trade via MetaTrader 5.

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

    logger.info(f"Trade request: {symbol} {direction} @ {lot_size} lots")

    try:
        result = mt5_client.send_order(symbol, direction, lot_size, stop_loss, take_profit)
    except Mt5ConnectionError as e:
        logger.error(f"Trade failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 503

    logger.info(f"Trade result: retcode={result.get('retcode')} order={result.get('order')}")
    telegram.send_trade_notification(
        symbol, direction, lot_size, result.get("price", 0.0), stop_loss or 0.0, take_profit or 0.0
    )
    return jsonify({"status": "executed", **result})


@app.route("/close", methods=["POST"])
@require_bridge_key
def close_position():
    """Close an open position by ticket ID."""
    data = request.get_json(force=True)
    ticket_id = data.get("ticket_id")

    try:
        result = mt5_client.close_position(int(ticket_id))
    except (Mt5ConnectionError, TypeError, ValueError) as e:
        logger.error(f"Close failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 503

    return jsonify({"status": "closed", **result})


# ────────────────────────────────────────────────
# Account / Positions / History
# ────────────────────────────────────────────────


@app.route("/account", methods=["GET"])
@require_bridge_key
def account():
    """Get real MT5 account summary."""
    try:
        info = mt5_client.account_info()
    except Mt5ConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503

    return jsonify({
        "balance": info.get("balance"),
        "equity": info.get("equity"),
        "margin": info.get("margin"),
        "free_margin": info.get("margin_free"),
        "margin_level": info.get("margin_level"),
        "currency": info.get("currency"),
        "status": "connected",
    })


@app.route("/positions", methods=["GET"])
@require_bridge_key
def positions():
    """Get currently open positions from MT5."""
    try:
        pos = mt5_client.positions()
    except Mt5ConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503

    return jsonify({"positions": pos, "count": len(pos), "status": "connected"})


@app.route("/history", methods=["GET"])
@require_bridge_key
def history():
    """Get closed trade history from MT5 (last 30 days)."""
    try:
        deals = mt5_client.history_deals()
    except Mt5ConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503

    return jsonify({"deals": deals, "count": len(deals), "status": "connected"})


# ────────────────────────────────────────────────
# Telegram Test
# ────────────────────────────────────────────────


@app.route("/test-telegram", methods=["POST"])
@require_bridge_key
def test_telegram():
    """Send a test message via Telegram."""
    return jsonify(telegram.test())


# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────

if __name__ == "__main__":
    connected = mt5_client.connect()
    if connected:
        logger.info("MT5 terminal connected at startup.")
    else:
        logger.warning(
            "MT5 terminal not connected at startup (will retry on first request). "
            "Check the terminal is running/logged in and MT5_LOGIN/MT5_PASSWORD/MT5_SERVER are set."
        )
    if not config.bridge_api_key:
        logger.warning(
            "MT5_BRIDGE_API_KEY is not set — this bridge has NO authentication. "
            "Set it before exposing this process to the internet."
        )
    logger.info(f"Starting MT5 Bridge on port {config.bridge_port}")
    app.run(host="0.0.0.0", port=config.bridge_port, debug=False)
