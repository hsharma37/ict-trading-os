# MT5 Bridge

Bridges ICT Trading OS to a real MetaTrader 5 terminal. Trade execution,
account info, positions, and history all go through the official
`MetaTrader5` Python package, which wraps the native terminal API.

## Hard requirement: Windows

MetaTrader5's Python package only works on **Windows**, running on the same
machine as a MetaTrader 5 terminal that's installed and logged in.
MetaQuotes has no cloud/REST API — there is no way to "connect" to MT5 from
a Mac, Linux box, or serverless function directly. This bridge is the
process that must run next to the terminal; the main app then reaches it
over HTTP.

If the `MetaTrader5` package isn't installed (e.g. you're reading/editing
this code on Mac/Linux), every trade-related endpoint returns a clear `503`
error instead of crashing or faking a result — nothing here pretends to be
connected when it isn't.

## Setup (on the Windows machine/VPS)

1. Install and log into **MetaTrader 5** desktop with your broker's demo or
   live credentials, and leave it running.
2. Install Python 3.10+ and this bridge's dependencies:
   ```powershell
   cd mt5-bridge
   pip install -r requirements.txt
   ```
3. Copy `.env.example` to `.env` and fill in:
   - `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` — must match the account
     logged into the terminal.
   - `MT5_BRIDGE_API_KEY` — generate one (`openssl rand -hex 32` or similar)
     and keep it secret. **Do not run this bridge without it once it's
     reachable from the internet** — anyone with the URL could otherwise
     read the account or place trades.
   - Optionally `TELEGRAM_BOT_TOKEN` / `TELEGRAM_CHAT_ID` for trade
     execution/close notifications sent directly from this bridge.
4. Run it:
   ```powershell
   python mt5_bridge.py
   ```
   Startup logs report whether the terminal connection succeeded.

## Exposing it to the deployed app

Vercel (where the main app runs) can't reach a machine on your LAN directly, so
the bridge is exposed through a tunnel. Recommended: **Cloudflare Tunnel**
(reliable from cloud IPs, unlike free ngrok which Vercel often can't reach):

```powershell
# Quick tunnel — free, but the URL is random and CHANGES every restart
.\cloudflared.exe tunnel --url http://localhost:5000
```

Take the `https://...trycloudflare.com` URL and point the app at it. Two ways:

**Easiest — paste it in the app (no redeploy).** Open the app → **Settings →
MT5 Bridge Connection**, paste the tunnel URL, and hit **Save & Test**. It's
stored in the app's database, takes effect immediately, and is probed on save
so you get instant `reachable` / `MT5 connected` feedback. This override wins
over the env var and is the recommended way to handle the churning quick-tunnel
URL. (The shared secret still comes from `MT5_BRIDGE_API_KEY` — see below.)

**Or via env var (needs a redeploy).** On Vercel → Project → Settings →
Environment Variables:

- `MT5_BRIDGE_URL` = that tunnel URL
- `MT5_BRIDGE_API_KEY` = the **same** value you put in this bridge's `.env`

Redeploy the app. `GET /api/mt5/status` should then report `reachable: true`.
`MT5_BRIDGE_API_KEY` must always be set via env (it's a secret and isn't
editable from the UI); only the URL is overridable in Settings.

### Permanent URL (optional)

A **quick** tunnel URL changes on every restart. The in-app Settings field
above makes re-pointing a 5-second paste, but if you want a URL that never
changes at all, use a **Cloudflare named tunnel** (needs a domain on
Cloudflare):

```powershell
.\cloudflared.exe tunnel login
.\cloudflared.exe tunnel create mt5bridge
.\cloudflared.exe tunnel route dns mt5bridge bridge.yourdomain.com
.\cloudflared.exe tunnel run --url http://localhost:5000 mt5bridge
# permanent: https://bridge.yourdomain.com
```

Both the bridge (`python mt5_bridge.py`) and the tunnel must stay running.
An always-on Windows VPS avoids keeping a desktop awake.

## Optional: drive the hourly Telegram poll from the bridge

The app polls a public Telegram channel (`TELEGRAM_SOURCE_CHANNEL`, default
`xxictxx`) for ICT signals. Hosted crons on some plans (e.g. Vercel Hobby) can't
run hourly, so this always-on bridge can drive the schedule instead. In the
bridge's `.env`:

```
APP_BASE_URL=https://your-app.vercel.app
APP_POLL_INTERVAL_MINUTES=60
# CRON_SECRET=<same value as the app, only if you set one there>
```

On start, the bridge logs `Telegram poll scheduler on: every 60m` and calls
`<APP_BASE_URL>/api/telegram/poll-source` every hour; the app fetches the
channel's web preview and stores any new posts. Leave `APP_BASE_URL` empty to
disable. The bridge must be restarted to pick up the change.

## Endpoints

| Endpoint | Auth | Description |
|---|---|---|
| `GET /` | none | Status: package installed?, terminal connected?, Telegram configured? |
| `GET /health` | none | Liveness check |
| `GET /account` | `X-Bridge-Key` | Real account balance/equity/margin |
| `GET /positions` | `X-Bridge-Key` | Real open positions |
| `GET /history` | `X-Bridge-Key` | Closed trades (deals paired into open/close), last 30 days |
| `GET /tick/<symbol>` | `X-Bridge-Key` | Live bid/ask/last from the broker feed |
| `GET /candles/<symbol>?timeframe=&count=` | `X-Bridge-Key` | Historical OHLC candles (1m..1w) |
| `GET /symbol/<symbol>` | `X-Bridge-Key` | Contract spec (digits, contract size, volume min/max/step) |
| `GET /symbols` | `X-Bridge-Key` | All tradable symbols on the account |
| `GET /orders` | `X-Bridge-Key` | Working pending orders |
| `POST /trade` | `X-Bridge-Key` | Places a real market order (auto-selects a supported filling mode) |
| `POST /order-check` | `X-Bridge-Key` | Validates an order **without placing it** — diagnoses rejections (filling mode, stops, margin, market hours) |
| `POST /close` | `X-Bridge-Key` | Closes a position by ticket ID |
| `POST /partial-close` | `X-Bridge-Key` | Closes part of a position (`ticket`, `volume`) |
| `POST /modify` | `X-Bridge-Key` | Modify a position's SL/TP (`ticket`, `stop_loss?`, `take_profit?`) |
| `POST /pending` | `X-Bridge-Key` | Place a limit/stop order (`symbol`, `direction`, `order_kind`, `volume`, `price`, ...) |
| `POST /pending/cancel` | `X-Bridge-Key` | Cancel a pending order (`order_ticket`) |
| `GET /transcript/<video_id>` | `X-Bridge-Key` | Fetch a YouTube transcript from this machine's (residential) IP — used by the app's KB auto-transcribe, since YouTube blocks cloud/serverless IPs |
| `GET /video-meta/<video_id>` | `X-Bridge-Key` | Fetch a YouTube video's title/author (oembed) from the residential IP, for proper KB source names |
| `GET /fetch?url=` | `X-Bridge-Key` | Fetch a public URL from the residential IP — used for forex news/RSS feeds (e.g. FXStreet) that block datacenter IPs |
| `POST /test-telegram` | `X-Bridge-Key` | Sends a test Telegram message |

To price the app from the broker's own feed (so displayed prices match your
fills), set `MARKET_DATA_PROVIDER=mt5` on the main app (with `MT5_BRIDGE_URL`
+ `MT5_BRIDGE_API_KEY`). It uses `GET /tick/<symbol>` under the hood.

Every trade-related endpoint returns `503` with a clear error (not a fake
success) if the terminal isn't actually connected.
