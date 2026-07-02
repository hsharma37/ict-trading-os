# ICT Trading OS Backend 

Live API for market data, ICT pattern detection, trading signals, and quantitative analytics.

## Deployment

Use `main` for production and `dev` for integration/staging. See [docs/DEPLOYMENT.md](docs/DEPLOYMENT.md) for the dev/prod Vercel project split, stable URL plan, environment separation, and storage warning for the KB.

## API Endpoints

| Endpoint | Description |
|----------|-------------|
| `GET /market/price/{symbol}` | Live price (Yahoo Finance) |
| `GET /market/history/{symbol}?timeframe=1h` | Candle history |
| `GET /ict/analyze/{symbol}` | ICT pattern detection (MSS, FVG, OB, Liquidity) |
| `GET /ict/analyze/multi/{symbol}` | Multi-timeframe analysis |
| `GET /signals/analyze/{symbol}` | Generate trading signal |
| `GET /signals/active` | Active signals |
| `POST /trades/` | Create trade |
| `GET /trades/` | List trades |
| `POST /trades/{id}/close` | Close trade |
| `GET /quant/metrics` | Quant metrics (Sharpe, Sortino, etc.) |
| `GET /quant/kelly` | Kelly Criterion sizing |
| `GET /quant/coach` | Bot coaching recommendations |
| `POST /quant/monte-carlo` | Monte Carlo simulation |

## MT5 Bridge and Telegram Integration

This repository supports a local MT5 bridge that exposes real MetaTrader 5 actions and sends Telegram notifications for executed orders.

- `MT5_BRIDGE_URL` — URL of the local MT5 bridge (default: `http://localhost:5000`)
- `TELEGRAM_BOT_TOKEN` — Telegram bot token for notifications
- `TELEGRAM_CHAT_ID` — Target chat ID for Telegram messages

### Local setup

```bash
pip install -r requirements.txt
export MT5_BRIDGE_URL="http://localhost:5000"
export TELEGRAM_BOT_TOKEN="<your-bot-token>"
export TELEGRAM_CHAT_ID="<your-chat-id>"
python mt5bridgeScript.py
npm run dev
```

### Available MT5 proxy endpoints

| Endpoint | Description |
|----------|-------------|
| `POST /api/mt5/trade` | Proxy order requests to the MT5 bridge |
| `GET /api/mt5/account` | Get account summary from MT5 |
| `GET /api/mt5/positions` | Fetch open positions from MT5 |
| `GET /api/mt5/status` | Check bridge connectivity |

The app proxy forwards `/api/mt5/*` to the local bridge, and executed trades can be relayed to Telegram automatically.
