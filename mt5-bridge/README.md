# MT5 Bridge Refactor

This directory contains the refactored MT5 bridge service.

## Structure

- `mt5_bridge.py` — Main bridge server (FastAPI/Flask style, replaces old script)
- `telegram_bot.py` — Telegram notification handler
- `config.py` — Bridge configuration and settings
- `Dockerfile` — Container image (for future use, MT5 runs on Windows natively)
- `requirements.txt` — Python dependencies

## Status

Phase 1: Scaffold created. Full implementation will port the existing
`mt5bridgeScript.py` logic into a clean, modular service with:
- Proper error handling and reconnection
- Health check endpoint
- Structured logging
- Telegram integration with retry logic
- FastAPI-style endpoints (if running standalone) or direct Python API

## Run

```bash
cd mt5-bridge
pip install -r requirements.txt
python mt5_bridge.py
```

Or via Docker Compose (when MT5 is available in container):

```bash
docker compose up mt5-bridge
```
