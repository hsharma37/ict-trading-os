"""
MT5 Bridge — bridges ICT Trading OS to a local MetaTrader 5 terminal.

Must run on Windows, on the same machine as a running, logged-in MT5
terminal — MetaTrader5's Python API has no remote/cloud mode. Expose this
process to the internet (e.g. via ngrok or a reverse proxy) and set
MT5_BRIDGE_URL + MT5_BRIDGE_API_KEY on the main app to reach it. See
.env.example and README.md for full setup.
"""
import logging
import threading
import time
from datetime import datetime
from functools import wraps

import requests
from flask import Flask, request, jsonify

from config import config
from telegram_bot import TelegramNotifier
from mt5_client import Mt5Client, Mt5ConnectionError

# YouTube transcripts: fetched here (residential IP) because YouTube blocks
# caption requests from cloud/serverless IPs (i.e. from Vercel directly).
try:
    from youtube_transcript_api import YouTubeTranscriptApi
except ImportError:
    YouTubeTranscriptApi = None

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


@app.route("/order-check", methods=["POST"])
@require_bridge_key
def order_check():
    """Validate an order without placing it — for diagnosing rejections."""
    data = request.get_json(force=True)
    try:
        result = mt5_client.order_check(
            data.get("symbol", "UNKNOWN"),
            data.get("direction", "long"),
            data.get("lot_size", 0.0),
            data.get("stop_loss"),
            data.get("take_profit"),
        )
    except Mt5ConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503
    return jsonify(result)


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
        trades = mt5_client.history_deals()
    except Mt5ConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503

    # Key must be "history" -- MT5Terminal.tsx reads histData.history.
    return jsonify({"history": trades, "count": len(trades), "status": "connected"})


# ────────────────────────────────────────────────
# Market Data
# ────────────────────────────────────────────────


@app.route("/tick/<symbol>", methods=["GET"])
@require_bridge_key
def tick(symbol):
    """Live bid/ask/last for a symbol from the broker feed."""
    try:
        return jsonify(mt5_client.get_tick(symbol))
    except Mt5ConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/candles/<symbol>", methods=["GET"])
@require_bridge_key
def candles(symbol):
    """Historical OHLC candles. Query: timeframe (1m..1w), count."""
    timeframe = request.args.get("timeframe", "1h")
    count = request.args.get("count", 200)
    try:
        data = mt5_client.get_candles(symbol, timeframe, int(count))
        return jsonify({"candles": data, "count": len(data), "status": "connected"})
    except (Mt5ConnectionError, ValueError) as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/symbol/<symbol>", methods=["GET"])
@require_bridge_key
def symbol_spec(symbol):
    """Contract specification for a symbol."""
    try:
        return jsonify(mt5_client.symbol_spec(symbol))
    except Mt5ConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/symbols", methods=["GET"])
@require_bridge_key
def symbols():
    """All tradable symbols on this account."""
    try:
        names = mt5_client.list_symbols()
        return jsonify({"symbols": names, "count": len(names), "status": "connected"})
    except Mt5ConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503


# ────────────────────────────────────────────────
# YouTube transcript (residential-IP proxy for the app's KB)
# ────────────────────────────────────────────────


@app.route("/transcript/<video_id>", methods=["GET"])
@require_bridge_key
def transcript(video_id):
    """Fetch a YouTube video's transcript from this machine's IP. Query:
    languages (comma-separated, default en,en-US,en-GB)."""
    if YouTubeTranscriptApi is None:
        return jsonify({"status": "error", "error": "youtube-transcript-api not installed on bridge"}), 503
    languages = [s.strip() for s in request.args.get("languages", "en,en-US,en-GB").split(",") if s.strip()]
    try:
        fetched = YouTubeTranscriptApi().fetch(video_id, languages=languages)
        segments = [
            {"text": s.text, "start": s.start, "duration": getattr(s, "duration", 0)}
            for s in fetched
        ]
        return jsonify({
            "video_id": video_id,
            "text": " ".join(s["text"] for s in segments),
            "segments": segments,
            "language": getattr(fetched, "language", languages[0] if languages else "en"),
            "is_generated": getattr(fetched, "is_generated", False),
            "status": "ok",
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 502


@app.route("/video-meta/<video_id>", methods=["GET"])
@require_bridge_key
def video_meta(video_id):
    """Fetch a YouTube video's title/author from this machine's IP (YouTube's
    oembed is also blocked from cloud IPs, so the app can't get titles either)."""
    import requests
    try:
        r = requests.get(
            "https://www.youtube.com/oembed",
            params={"url": f"https://www.youtube.com/watch?v={video_id}", "format": "json"},
            timeout=15,
        )
        if r.status_code != 200:
            return jsonify({"status": "error", "error": f"oembed {r.status_code}"}), 502
        data = r.json()
        return jsonify({
            "video_id": video_id,
            "title": data.get("title"),
            "author": data.get("author_name"),
            "thumbnail": data.get("thumbnail_url"),
            "status": "ok",
        })
    except Exception as e:
        return jsonify({"status": "error", "error": str(e)}), 502


# ────────────────────────────────────────────────
# Order & Position Management
# ────────────────────────────────────────────────


@app.route("/modify", methods=["POST"])
@require_bridge_key
def modify():
    """Modify SL/TP on an open position. Body: ticket, stop_loss?, take_profit?."""
    data = request.get_json(force=True)
    try:
        result = mt5_client.modify_sltp(
            int(data["ticket"]), data.get("stop_loss"), data.get("take_profit")
        )
        return jsonify({"status": "modified", **result})
    except (Mt5ConnectionError, KeyError, TypeError, ValueError) as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/partial-close", methods=["POST"])
@require_bridge_key
def partial_close():
    """Close part of a position. Body: ticket, volume."""
    data = request.get_json(force=True)
    try:
        result = mt5_client.partial_close(int(data["ticket"]), float(data["volume"]))
        return jsonify({"status": "partial_closed", **result})
    except (Mt5ConnectionError, KeyError, TypeError, ValueError) as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/pending", methods=["POST"])
@require_bridge_key
def pending():
    """Place a pending order. Body: symbol, direction, order_kind, volume, price, sl?, tp?."""
    data = request.get_json(force=True)
    try:
        result = mt5_client.place_pending(
            data["symbol"], data["direction"], data["order_kind"],
            float(data["volume"]), float(data["price"]),
            data.get("stop_loss"), data.get("take_profit"),
        )
        return jsonify({"status": "placed", **result})
    except (Mt5ConnectionError, KeyError, TypeError, ValueError) as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/orders", methods=["GET"])
@require_bridge_key
def orders():
    """List working pending orders."""
    try:
        data = mt5_client.pending_orders()
        return jsonify({"orders": data, "count": len(data), "status": "connected"})
    except Mt5ConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/pending/cancel", methods=["POST"])
@require_bridge_key
def cancel_pending():
    """Cancel a pending order. Body: order_ticket."""
    data = request.get_json(force=True)
    try:
        result = mt5_client.cancel_pending(int(data["order_ticket"]))
        return jsonify({"status": "cancelled", **result})
    except (Mt5ConnectionError, KeyError, TypeError, ValueError) as e:
        return jsonify({"status": "error", "error": str(e)}), 503


# ────────────────────────────────────────────────
# Telegram Test
# ────────────────────────────────────────────────


@app.route("/test-telegram", methods=["POST"])
@require_bridge_key
def test_telegram():
    """Send a test message via Telegram."""
    return jsonify(telegram.test())


# ────────────────────────────────────────────────
# Background: hourly Telegram source-channel poll
# ────────────────────────────────────────────────
def _telegram_poll_loop():
    """Call the app's source-channel poll endpoint on a fixed interval.

    Runs from this always-on bridge so hourly polling works regardless of the
    app's hosting plan (Vercel Hobby crons can't run sub-daily). Enabled by
    setting APP_BASE_URL in the bridge's .env.
    """
    url = f"{config.app_base_url}/api/telegram/poll-source"
    interval = max(60, config.app_poll_interval_minutes * 60)
    headers = {"Authorization": f"Bearer {config.cron_secret}"} if config.cron_secret else {}
    logger.info(f"Telegram poll scheduler on: every {config.app_poll_interval_minutes}m -> {url}")
    while True:
        try:
            r = requests.get(url, headers=headers, timeout=45)
            if r.status_code == 200:
                body = r.json()
                logger.info(f"Telegram poll ok: {body.get('new_signals', 0)} new from {body.get('channel')}")
            else:
                logger.warning(f"Telegram poll HTTP {r.status_code}: {r.text[:200]}")
        except Exception as e:  # noqa: BLE001
            logger.warning(f"Telegram poll failed: {e}")
        time.sleep(interval)


def _start_telegram_scheduler():
    if not config.app_base_url:
        logger.info("Telegram poll scheduler off (set APP_BASE_URL to enable hourly polling from the bridge).")
        return
    t = threading.Thread(target=_telegram_poll_loop, name="telegram-poll", daemon=True)
    t.start()


# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────

if __name__ == "__main__":
    _start_telegram_scheduler()
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
