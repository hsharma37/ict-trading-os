# mt5bridgeScript.py — MT5 has no public API; this local bridge is the
# ONLY way to connect a real account.
# pip install -r requirements.txt

import os
import signal
import threading
import time
from datetime import datetime

try:
    import MetaTrader5 as mt5
    MT5_AVAILABLE = True
except ImportError:
    mt5 = None
    MT5_AVAILABLE = False
    print('[MT5 Bridge] MetaTrader5 package unavailable; MT5 functionality is disabled.')

import httpx
from flask import Flask, jsonify, request
from flask_cors import CORS
from dotenv import load_dotenv

load_dotenv()

app = Flask(__name__)
CORS(app)

TELEGRAM_BOT_TOKEN = os.getenv('TELEGRAM_BOT_TOKEN', '').strip()
TELEGRAM_CHAT_ID = os.getenv('TELEGRAM_CHAT_ID', '').strip()
MT5_BRIDGE_PORT = int(os.getenv('MT5_BRIDGE_PORT', '5000'))
MT5_PATH = os.getenv('MT5_PATH')
MT5_SERVER = os.getenv('MT5_SERVER')
MT5_ACCOUNT = os.getenv('MT5_ACCOUNT')
MT5_PASSWORD = os.getenv('MT5_PASSWORD')

# Runtime Telegram polling state for inbound channel messages
TELEGRAM_RUNTIME_TOKEN = None
TELEGRAM_RUNTIME_CHANNEL = None
TELEGRAM_POLL_INTERVAL = 30
TELEGRAM_UPDATE_OFFSET = 0
TELEGRAM_POLL_THREAD = None
TELEGRAM_POLL_RUNNING = False
TELEGRAM_MESSAGES = []
TELEGRAM_SIGNALS = []
TELEGRAM_AUTO_EXECUTE = True
TELEGRAM_CONNECTED = False
TELEGRAM_LOCK = threading.Lock()


def send_telegram_message(text: str) -> None:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        print('[MT5 Bridge] Telegram not configured. Skipping notification.')
        print(f'  TELEGRAM_BOT_TOKEN: {"SET" if TELEGRAM_BOT_TOKEN else "NOT SET"}')
        print(f'  TELEGRAM_CHAT_ID: {"SET" if TELEGRAM_CHAT_ID else "NOT SET"}')
        return

    url = f'https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage'
    payload = {
        'chat_id': TELEGRAM_CHAT_ID,
        'text': text,
        'parse_mode': 'HTML',
    }
    try:
        with httpx.Client(timeout=15.0) as client:
            resp = client.post(url, json=payload)
            resp.raise_for_status()
            print(f'[MT5 Bridge] Telegram message sent successfully')
    except Exception as exc:
        print(f'[MT5 Bridge] Telegram notification failed: {exc}')


def mt5_initialize() -> bool:
    if MT5_PATH:
        if not mt5.initialize(path=MT5_PATH):
            print(f'[MT5 Bridge] initialize failed: {mt5.last_error()}')
            return False
    else:
        if not mt5.initialize():
            print(f'[MT5 Bridge] initialize failed: {mt5.last_error()}')
            return False

    if MT5_SERVER and MT5_ACCOUNT and MT5_PASSWORD:
        if not mt5.login(int(MT5_ACCOUNT), password=MT5_PASSWORD, server=MT5_SERVER):
            print(f'[MT5 Bridge] login failed: {mt5.last_error()}')
            return False

    return True


def mt5_status() -> dict:
    info = mt5.terminal_info()
    error = mt5.last_error()
    return {
        'connected': bool(info),
        'terminal_info': info._asdict() if info else None,
        'last_error': error._asdict() if error else None,
        'timestamp': datetime.utcnow().isoformat()
    }

def parse_telegram_signal(text: str) -> dict | None:
    import re
    m = re.search(r"\b(BUY|SELL)\s+([A-Z0-9!]+)\s+Entry\s+([\d\.]+)\s+SL\s+([\d\.]+)\s+TP\s+([\d\.]+)(?:\s+RR\s+([\d\.]+))?", text, re.IGNORECASE)
    if not m:
        return None
    return {
        'side': m.group(1).upper(),
        'symbol': m.group(2).upper(),
        'entry': float(m.group(3)),
        'sl': float(m.group(4)),
        'tp': float(m.group(5)),
        'rr': float(m.group(6)) if m.group(6) else None,
    }


def fetch_telegram_updates(token: str, offset: int, timeout: int = 20):
    url = f'https://api.telegram.org/bot{token}/getUpdates'
    params = {'timeout': timeout, 'offset': offset, 'allowed_updates': ['message', 'channel_post']}
    with httpx.Client(timeout=timeout + 10) as client:
        resp = client.get(url, params=params)
        resp.raise_for_status()
        return resp.json()


def execute_signal(signal: dict) -> dict:
    symbol = signal.get('symbol')
    side = signal.get('side')
    if not symbol or side not in ('BUY', 'SELL'):
        raise ValueError('Invalid signal format')
    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        raise RuntimeError(f'Symbol {symbol} not available in MT5')
    if not symbol_info.visible and not mt5.symbol_select(symbol, True):
        raise RuntimeError(f'Unable to select symbol {symbol}: {mt5.last_error()}')
    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        raise RuntimeError(f'Unable to read market price for {symbol}: {mt5.last_error()}')
    volume = max(0.01, float(getattr(symbol_info, 'volume_min', 0.01)))
    trade_price = float(tick.ask) if side == 'BUY' else float(tick.bid)
    trade_type = mt5.ORDER_TYPE_BUY if side == 'BUY' else mt5.ORDER_TYPE_SELL
    request_payload = {
        'action': mt5.TRADE_ACTION_DEAL,
        'symbol': symbol,
        'volume': volume,
        'type': trade_type,
        'price': trade_price,
        'deviation': 20,
        'type_filling': mt5.ORDER_FILLING_IOC,
        'type_time': mt5.ORDER_TIME_GTC,
    }
    result = mt5.order_send(request_payload)
    if result is None:
        error = mt5.last_error()
        raise RuntimeError(f'Order send failed: {error._asdict() if error else None}')
    order_data = convert_mt5_result(result)
    message = (
        f"<b>Auto-executed Telegram signal</b>\n"
        f"Symbol: {symbol}\n"
        f"Side: {side}\n"
        f"Volume: {volume}\n"
        f"Price: {trade_price}\n"
        f"TP: {signal.get('tp')}\n"
        f"SL: {signal.get('sl')}\n"
        f"Channel: {signal.get('channel')}"
    )
    send_telegram_message(message)
    return order_data


def telegram_poll_loop():
    global TELEGRAM_UPDATE_OFFSET, TELEGRAM_POLL_RUNNING
    while TELEGRAM_POLL_RUNNING:
        if not TELEGRAM_RUNTIME_TOKEN or not TELEGRAM_RUNTIME_CHANNEL:
            time.sleep(1)
            continue
        try:
            data = fetch_telegram_updates(TELEGRAM_RUNTIME_TOKEN, TELEGRAM_UPDATE_OFFSET, timeout=TELEGRAM_POLL_INTERVAL)
            if data.get('ok') and data.get('result'):
                for update in data['result']:
                    TELEGRAM_UPDATE_OFFSET = update['update_id'] + 1
                    message = update.get('message') or {}
                    chat = message.get('chat', {})
                    text = message.get('text') or message.get('caption') or ''
                    if not text:
                        continue
                    sender = chat.get('title') or chat.get('username') or chat.get('id')
                    if TELEGRAM_RUNTIME_CHANNEL.lstrip('@') not in str(chat.get('username', '')).lstrip('@') and TELEGRAM_RUNTIME_CHANNEL not in str(chat.get('title', '')) and TELEGRAM_RUNTIME_CHANNEL not in str(chat.get('id', '')):
                        continue
                    with TELEGRAM_LOCK:
                        TELEGRAM_MESSAGES.insert(0, {'sender': sender, 'text': text, 'time': datetime.utcnow().isoformat()})
                        signal = parse_telegram_signal(text)
                        if signal:
                            signal['channel'] = sender
                            signal['time'] = datetime.utcnow().isoformat()
                            signal['conflict'] = False
                            TELEGRAM_SIGNALS.insert(0, signal)
                            if TELEGRAM_AUTO_EXECUTE and MT5_AVAILABLE:
                                execute_signal(signal)
                if len(TELEGRAM_MESSAGES) > 200:
                    TELEGRAM_MESSAGES[:] = TELEGRAM_MESSAGES[:200]
                if len(TELEGRAM_SIGNALS) > 100:
                    TELEGRAM_SIGNALS[:] = TELEGRAM_SIGNALS[:100]
        except Exception as exc:
            print(f'[MT5 Bridge] Telegram polling error: {exc}')
            time.sleep(5)


def start_telegram_poll(token: str, channel: str, interval: int):
    global TELEGRAM_RUNTIME_TOKEN, TELEGRAM_RUNTIME_CHANNEL, TELEGRAM_POLL_INTERVAL, TELEGRAM_POLL_THREAD, TELEGRAM_POLL_RUNNING, TELEGRAM_CONNECTED
    TELEGRAM_RUNTIME_TOKEN = token
    TELEGRAM_RUNTIME_CHANNEL = channel
    TELEGRAM_POLL_INTERVAL = max(10, interval)
    TELEGRAM_POLL_RUNNING = True
    TELEGRAM_CONNECTED = True
    TELEGRAM_UPDATE_OFFSET = 0
    TELEGRAM_MESSAGES.clear()
    TELEGRAM_SIGNALS.clear()
    if TELEGRAM_POLL_THREAD is None or not TELEGRAM_POLL_THREAD.is_alive():
        TELEGRAM_POLL_THREAD = threading.Thread(target=telegram_poll_loop, daemon=True)
        TELEGRAM_POLL_THREAD.start()


def stop_telegram_poll():
    global TELEGRAM_POLL_RUNNING, TELEGRAM_CONNECTED
    TELEGRAM_POLL_RUNNING = False
    TELEGRAM_CONNECTED = False


def get_telegram_state():
    with TELEGRAM_LOCK:
        return {
            'connected': TELEGRAM_CONNECTED,
            'messages': TELEGRAM_MESSAGES.copy(),
            'signals': TELEGRAM_SIGNALS.copy(),
        }


def convert_mt5_result(result):
    if hasattr(result, '_asdict'):
        return result._asdict()
    if isinstance(result, (list, tuple)):
        return [convert_mt5_result(r) for r in result]
    return result


@app.route('/', methods=['GET'])
def home():
    return jsonify({
        'status': 'MT5 Bridge is running',
        'telegram_configured': bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID),
        'mt5_available': MT5_AVAILABLE,
    })


@app.route('/test-telegram', methods=['POST'])
def test_telegram():
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        return jsonify({'error': 'Telegram not configured. Set TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID.'}), 400
    try:
        send_telegram_message('🔧 MT5 Bridge test message — Telegram connection is working!')
        return jsonify({'status': 'Test message sent', 'chat_id': TELEGRAM_CHAT_ID}), 200
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/status', methods=['GET'])
def status():
    if not MT5_AVAILABLE:
        return jsonify({'mt5_available': False, 'error': 'MetaTrader5 package unavailable', 'telegram_configured': bool(TELEGRAM_BOT_TOKEN and TELEGRAM_CHAT_ID)})
    return jsonify(mt5_status())


@app.route('/account', methods=['GET'])
def account():
    if not MT5_AVAILABLE:
        return jsonify({'error': 'MetaTrader5 package unavailable'}), 500
    account_info = mt5.account_info()
    if account_info is None:
        error = mt5.last_error()
        return jsonify({'error': 'MT5 account not available', 'last_error': error._asdict() if error else None}), 500
    return jsonify({'account': account_info._asdict()})


@app.route('/positions', methods=['GET'])
def positions():
    positions = mt5.positions_get()
    if positions is None:
        error = mt5.last_error()
        return jsonify({'positions': [], 'last_error': error._asdict() if error else None})
    return jsonify({'positions': convert_mt5_result(positions)})


@app.route('/trade', methods=['POST'])
def trade():
    payload = request.get_json(silent=True) or {}
    symbol = payload.get('symbol')
    side = payload.get('side', '').upper()
    volume = float(payload.get('volume', 0) or 0)
    price = payload.get('price')
    deviation = int(payload.get('deviation', 20))

    if not symbol or side not in ('BUY', 'SELL') or volume <= 0:
        return jsonify({'error': 'symbol, side (BUY|SELL), and volume are required'}), 400

    symbol_info = mt5.symbol_info(symbol)
    if symbol_info is None:
        return jsonify({'error': f'Symbol {symbol} not found'}), 404

    if not symbol_info.visible:
        if not mt5.symbol_select(symbol, True):
            return jsonify({'error': 'Unable to select symbol', 'last_error': mt5.last_error()._asdict()}), 500

    tick = mt5.symbol_info_tick(symbol)
    if tick is None:
        return jsonify({'error': 'Unable to read symbol tick', 'last_error': mt5.last_error()._asdict()}), 500

    trade_price = float(price) if price else (tick.ask if side == 'BUY' else tick.bid)
    trade_type = mt5.ORDER_TYPE_BUY if side == 'BUY' else mt5.ORDER_TYPE_SELL

    request_payload = {
        'action': mt5.TRADE_ACTION_DEAL,
        'symbol': symbol,
        'volume': volume,
        'type': trade_type,
        'price': trade_price,
        'deviation': deviation,
        'type_filling': mt5.ORDER_FILLING_IOC,
        'type_time': mt5.ORDER_TIME_GTC,
    }

    result = mt5.order_send(request_payload)
    if result is None:
        error = mt5.last_error()
        return jsonify({'error': 'Order send returned no result', 'last_error': error._asdict() if error else None}), 500

    data = convert_mt5_result(result)
    message = (
        f"<b>MT5 Order Executed</b>\n"
        f"Symbol: {symbol}\n"
        f"Side: {side}\n"
        f"Volume: {volume}\n"
        f"Price: {trade_price}\n"
        f"Retcode: {getattr(result, 'retcode', 'N/A')}\n"
        f"Comment: {getattr(result, 'comment', '')}"
    )
    send_telegram_message(message)
    return jsonify({'result': data})


@app.route('/reconnect', methods=['POST'])
def reconnect():
    mt5.shutdown()
    success = mt5_initialize()
    error = mt5.last_error()
    return jsonify({'reconnected': success, 'last_error': error._asdict() if error else None})


@app.route('/telegram/connect', methods=['POST'])
def telegram_connect():
    payload = request.get_json(silent=True) or {}
    token = payload.get('token', '').strip()
    channel = payload.get('channel', '').strip()
    interval = int(payload.get('interval', 30) or 30)
    if not token or not channel:
        return jsonify({'error': 'token and channel are required'}), 400
    try:
        resp = httpx.get(f'https://api.telegram.org/bot{token}/getMe', timeout=10.0)
        resp.raise_for_status()
        data = resp.json()
        if not data.get('ok'):
            raise RuntimeError('Invalid bot token')
        start_telegram_poll(token, channel, interval)
        return jsonify({'connected': True, 'channel': channel}), 200
    except Exception as exc:
        return jsonify({'error': str(exc)}), 400


@app.route('/telegram/disconnect', methods=['POST'])
def telegram_disconnect():
    stop_telegram_poll()
    return jsonify({'disconnected': True}), 200


@app.route('/telegram/status', methods=['GET'])
def telegram_status():
    state = get_telegram_state()
    return jsonify(state)


@app.route('/telegram/auto-execute', methods=['POST'])
def telegram_auto_execute():
    payload = request.get_json(silent=True) or {}
    enabled = bool(payload.get('enabled'))
    global TELEGRAM_AUTO_EXECUTE
    TELEGRAM_AUTO_EXECUTE = enabled
    return jsonify({'auto_execute': TELEGRAM_AUTO_EXECUTE})


def shutdown_handler(signum, frame):
    print('[MT5 Bridge] Shutting down MT5...')
    if MT5_AVAILABLE:
        mt5.shutdown()
    raise SystemExit()


signal.signal(signal.SIGINT, shutdown_handler)
signal.signal(signal.SIGTERM, shutdown_handler)


if __name__ == '__main__':
    if MT5_AVAILABLE:
        success = mt5_initialize()
        if not success:
            print('[MT5 Bridge] Failed to initialize MT5 bridge')
            raise SystemExit(1)
    else:
        print('[MT5 Bridge] Running in Telegram-only mode; MT5 is unavailable.')

    print(f'[MT5 Bridge] Running on http://localhost:{MT5_BRIDGE_PORT}')
    app.run(host='0.0.0.0', port=MT5_BRIDGE_PORT)
