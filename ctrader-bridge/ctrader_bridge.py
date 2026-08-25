"""
cTrader Bridge — bridges ICT Trading OS to a cTrader account via the Open API.

Drop-in replacement for mt5-bridge: identical HTTP routes, identical response
shapes, identical X-Bridge-Key auth. The difference is underneath — cTrader's
Open API is server-side, so this runs on ANY Linux/macOS machine (or a $5
VPS). No Windows terminal, no Wine, no display.

Point the app at it exactly like the MT5 bridge: Settings → MT5 Bridge
Connection (the URL field is provider-agnostic), or MT5_BRIDGE_URL env.
"""
import logging
import os
import sys
import threading
import time
from datetime import datetime
from functools import wraps

# Make the bridge runnable no matter the working directory, and immune to a
# same-named PyPI package shadowing our local config.py (same guard as
# mt5_bridge.py).
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

import requests
from flask import Flask, request, jsonify

from config import config
from telegram_bot import TelegramNotifier
from ctrader_client import CTraderClient, CTraderConnectionError

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
ct_client = CTraderClient(config.ct_client_id, config.ct_client_secret,
                          config.ct_access_token, config.ct_account_id,
                          config.ct_host_type)


def require_bridge_key(fn):
    """Reject requests without the shared bridge key, once one is configured.

    Bypassed only when MT5_BRIDGE_API_KEY is unset (e.g. pure localhost dev).
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
    """Bridge status endpoint — deliberately unauthenticated so bridge-URL
    connectivity can be checked without a key. Keys mirror the MT5 bridge so
    the app's status UI works unchanged (provider label tells them apart)."""
    conn = ct_client.connection_status()
    return jsonify({
        "status": "ok",
        "service": "ict-os-ctrader-bridge",
        "provider": "ctrader",
        "version": "1.0.0",
        "timestamp": datetime.utcnow().isoformat(),
        "mt5_package_available": conn["package_available"],   # = ctrader-open-api installed
        "mt5_connected": conn["connected"],                   # = cTrader authenticated
        "mt5_status": conn["reason"],
        "mt5_login": conn["login"],                           # cTrader account id
        "mt5_server": conn["server"],                         # ctrader-demo / ctrader-live
        "telegram_configured": telegram.is_configured(),
    })


@app.route("/health", methods=["GET"])
def health():
    """Detailed health check."""
    return jsonify({"status": "healthy", "provider": "ctrader",
                    "timestamp": datetime.utcnow().isoformat()})


# ────────────────────────────────────────────────
# Generic sidecar utilities (residential-IP fetch — same as MT5 bridge)
# ────────────────────────────────────────────────


@app.route("/fetch", methods=["GET"])
@require_bridge_key
def fetch_url():
    """Fetch a public URL from this machine's (residential) IP and return the
    body — used by the app to reach news/RSS feeds that block cloud IPs."""
    url = request.args.get("url", "")
    if not url.startswith(("http://", "https://")):
        return jsonify({"error": "url must be http(s)"}), 400
    try:
        r = requests.get(url, timeout=15, headers={"User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64)"})
        return jsonify({"status": r.status_code, "body": r.text[:500000]})
    except Exception as e:  # noqa: BLE001
        return jsonify({"error": str(e)}), 502


@app.route("/draw-levels", methods=["POST"])
@require_bridge_key
def draw_levels():
    """MT5-terminal chart drawing is not available on cTrader (MQL5 indicator
    + CSV sandbox was MT5-specific). Honest 501 — chart DATA (candles, ticks)
    is unaffected and flows through /candles and /tick as usual."""
    return jsonify({
        "status": "error",
        "error": "On-terminal chart drawing is MT5-specific and not available on "
                 "the cTrader bridge. The app's own charts render level data "
                 "identically (levels come from /candles + app computation).",
    }), 501


@app.route("/order-check", methods=["POST"])
@require_bridge_key
def order_check():
    """Validate an order without placing it — for diagnosing rejections."""
    data = request.get_json(force=True)
    try:
        result = ct_client.order_check(
            data.get("symbol", "UNKNOWN"),
            data.get("direction", "long"),
            data.get("lot_size", 0.0),
            data.get("stop_loss"),
            data.get("take_profit"),
        )
    except CTraderConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503
    return jsonify(result)


@app.route("/trade", methods=["POST"])
@require_bridge_key
def trade():
    """
    Execute a real trade via cTrader.

    Expected JSON body (same as MT5 bridge):
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
        result = ct_client.send_order(symbol, direction, lot_size, stop_loss, take_profit)
    except CTraderConnectionError as e:
        logger.error(f"Trade failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 503

    logger.info(f"Trade result: retcode={result.get('retcode')} order={result.get('order')}")
    telegram.send_trade_notification(
        symbol, direction, lot_size, result.get("price") or 0.0, stop_loss or 0.0, take_profit or 0.0
    )
    return jsonify({"status": "executed", **result})


@app.route("/close", methods=["POST"])
@require_bridge_key
def close_position():
    """Close an open position by ticket ID."""
    data = request.get_json(force=True)
    ticket_id = data.get("ticket_id")

    try:
        result = ct_client.close_position(int(ticket_id))
    except (CTraderConnectionError, TypeError, ValueError) as e:
        logger.error(f"Close failed: {e}")
        return jsonify({"status": "error", "error": str(e)}), 503

    return jsonify({"status": "closed", **result})


# ────────────────────────────────────────────────
# Account / Positions / History
# ────────────────────────────────────────────────


@app.route("/account", methods=["GET"])
@require_bridge_key
def account():
    """Get real account summary."""
    try:
        info = ct_client.account_info()
    except CTraderConnectionError as e:
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
    """Get currently open positions."""
    try:
        pos = ct_client.positions()
    except CTraderConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503

    return jsonify({"positions": pos, "count": len(pos), "status": "connected"})


@app.route("/history", methods=["GET"])
@require_bridge_key
def history():
    """Get closed trade history (last 30 days by default; the client maps a
    full year like the MT5 bridge)."""
    try:
        trades = ct_client.history_deals()
    except CTraderConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503

    # Key must be "history" -- MT5Terminal.tsx reads histData.history.
    return jsonify({"history": trades, "count": len(trades), "status": "connected"})


@app.route("/history-summary", methods=["GET"])
@require_bridge_key
def history_summary():
    """Balance reconciliation (deposits vs realized P&L) to diagnose missing trades."""
    try:
        return jsonify(ct_client.history_summary())
    except CTraderConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503


# ────────────────────────────────────────────────
# Market Data
# ────────────────────────────────────────────────


@app.route("/tick/<symbol>", methods=["GET"])
@require_bridge_key
def tick(symbol):
    """Live bid/ask/mid for a symbol from the broker feed."""
    try:
        return jsonify(ct_client.get_tick(symbol))
    except CTraderConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/candles/<symbol>", methods=["GET"])
@require_bridge_key
def candles(symbol):
    """Historical OHLC candles. Query: timeframe (1m..1w), count."""
    timeframe = request.args.get("timeframe", "1h")
    count = request.args.get("count", 200)
    try:
        data = ct_client.get_candles(symbol, timeframe, int(count))
        return jsonify({"candles": data, "count": len(data), "status": "connected"})
    except (CTraderConnectionError, ValueError) as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/symbol/<symbol>", methods=["GET"])
@require_bridge_key
def symbol_spec(symbol):
    """Contract specification for a symbol."""
    try:
        return jsonify(ct_client.symbol_spec(symbol))
    except CTraderConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/symbols", methods=["GET"])
@require_bridge_key
def symbols():
    """All tradable symbols on this account."""
    try:
        names = ct_client.list_symbols()
        return jsonify({"symbols": names, "count": len(names), "status": "connected"})
    except CTraderConnectionError as e:
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
    """Fetch a YouTube video's title/author from this machine's IP."""
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
        result = ct_client.modify_sltp(
            int(data["ticket"]), data.get("stop_loss"), data.get("take_profit")
        )
        return jsonify({"status": "modified", **result})
    except (CTraderConnectionError, KeyError, TypeError, ValueError) as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/partial-close", methods=["POST"])
@require_bridge_key
def partial_close():
    """Close part of a position. Body: ticket, volume (in lots)."""
    data = request.get_json(force=True)
    try:
        result = ct_client.partial_close(int(data["ticket"]), float(data["volume"]))
        return jsonify({"status": "partial_closed", **result})
    except (CTraderConnectionError, KeyError, TypeError, ValueError) as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/pending", methods=["POST"])
@require_bridge_key
def pending():
    """Place a pending order. Body: symbol, direction, order_kind, volume, price, sl?, tp?."""
    data = request.get_json(force=True)
    try:
        result = ct_client.place_pending(
            data["symbol"], data["direction"], data["order_kind"],
            float(data["volume"]), float(data["price"]),
            data.get("stop_loss"), data.get("take_profit"),
        )
        return jsonify({"status": "placed", **result})
    except (CTraderConnectionError, KeyError, TypeError, ValueError) as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/orders", methods=["GET"])
@require_bridge_key
def orders():
    """List working pending orders."""
    try:
        data = ct_client.pending_orders()
        return jsonify({"orders": data, "count": len(data), "status": "connected"})
    except CTraderConnectionError as e:
        return jsonify({"status": "error", "error": str(e)}), 503


@app.route("/pending/cancel", methods=["POST"])
@require_bridge_key
def cancel_pending():
    """Cancel a pending order. Body: order_ticket."""
    data = request.get_json(force=True)
    try:
        result = ct_client.cancel_pending(int(data["order_ticket"]))
        return jsonify({"status": "cancelled", **result})
    except (CTraderConnectionError, KeyError, TypeError, ValueError) as e:
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
# Background: hourly Telegram source-channel poll (same as MT5 bridge)
# ────────────────────────────────────────────────
def _telegram_poll_loop():
    """Call the app's source-channel poll endpoint on a fixed interval —
    runs from this always-on bridge so hourly polling works regardless of the
    app's hosting plan. Enabled by setting APP_BASE_URL."""
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


def _planner_run_due_loop():
    """Fire the app's due TIME-triggered trade plans every minute."""
    url = f"{config.app_base_url}/api/planner/run-due"
    headers = {"Authorization": f"Bearer {config.cron_secret}"} if config.cron_secret else {}
    while True:
        try:
            r = requests.get(url, headers=headers, timeout=30)
            if r.status_code == 200 and (r.json().get("fired") or 0):
                logger.info(f"Planner fired {r.json().get('fired')} due plan(s).")
        except Exception as e:  # noqa: BLE001
            logger.debug(f"Planner run-due failed: {e}")
        time.sleep(60)


def _start_planner_scheduler():
    if not config.app_base_url:
        return
    t = threading.Thread(target=_planner_run_due_loop, name="planner-run-due", daemon=True)
    t.start()
    logger.info("Planner run-due scheduler on: every 60s.")


# ────────────────────────────────────────────────
# Main
# ────────────────────────────────────────────────

if __name__ == "__main__":
    _start_telegram_scheduler()
    _start_planner_scheduler()
    connected = ct_client.connect()
    if connected:
        logger.info("cTrader Open API connected at startup.")
    else:
        logger.warning(
            "cTrader not connected at startup (will retry on first request). "
            "Check CT_CLIENT_ID / CT_CLIENT_SECRET / CT_ACCESS_TOKEN / CT_ACCOUNT_ID."
        )
    if not config.bridge_api_key:
        logger.warning(
            "MT5_BRIDGE_API_KEY is not set — this bridge has NO authentication. "
            "Set it before exposing this process to the internet."
        )
    logger.info(f"Starting cTrader Bridge on port {config.bridge_port}")
    app.run(host="0.0.0.0", port=config.bridge_port, debug=False)
