# cTrader Bridge — MT5-bridge replacement that runs anywhere

Drop-in replacement for `mt5-bridge/`. **Same HTTP routes, same response
shapes, same `X-Bridge-Key` auth** — the app cannot tell the difference. The
point: cTrader's Open API is **server-side**, so this bridge is a plain
Python process. No Windows terminal, no Wine, no Docker emulation, no noVNC
login dance. It runs on your Mac, a Linux box, or a $5 VPS.

## Why this exists

The MetaTrader5 Python package only talks to a *running Windows desktop
terminal*. That single constraint produced the whole Wine/Docker/quick-tunnel
apparatus (see `docs/DOCKER_BRIDGE.md`). The cTrader Open API removes the
terminal from the equation entirely: your code authenticates to the broker's
cTrader servers directly.

## Setup (~10 min)

1. **Create an Open API application** at https://openapi.ctrader.com → get
   `CT_CLIENT_ID` / `CT_CLIENT_SECRET`.
2. **Connect your trading account** (cTrader Web/Mobile → Settings →
   Advanced → API access, or the developer portal) → get `CT_ACCESS_TOKEN`
   and the numeric `CT_ACCOUNT_ID`. Demo and live accounts both work —
   set `CT_HOST_TYPE` accordingly.
3. ```bash
   cd ctrader-bridge
   cp .env.example .env   # fill in the CT_* values + MT5_BRIDGE_API_KEY
   pip install -r requirements.txt
   python ctrader_bridge.py
   ```
4. In the app: **Settings → MT5 Bridge Connection** → paste this bridge's
   URL (localhost, LAN, or tunnel) → Save & Test. The status JSON reports
   `"provider": "ctrader"` so you can tell which engine you're on.

Everything — prices, candles (charts), levels data, signals, backtests,
forward tests, execution, journal sync — now flows through this bridge.

## Contract compatibility notes

- **Order results speak MT5 retcodes** (`10008` placed / `10009` filled /
  `10013` rejected with the cTrader error code in `comment`), because
  `planner_service` and the `/mt5` router pattern-match those numbers.
- **Market orders + SL/TP:** cTrader MARKET orders reject absolute SL/TP, so
  protection is attached as *relative* SL/TP computed from the live spot at
  send time (proto fields `relativeStopLoss`/`relativeTakeProfit`). Pending
  orders take absolute SL/TP directly.
- **Volumes:** the app sends lots; the bridge converts via each symbol's
  `lotSize` (cents-of-units per lot, usually 10,000,000 = 100k units).
- **History:** cTrader closing deals carry their own realized P&L and entry
  price (`closePositionDetail`), so no IN/OUT deal pairing is needed. SL/TP
  on historical trades are not recoverable from the deal list (v1: `null`).
- **`/draw-levels` returns 501.** On-terminal chart drawing was an MQL5
  indicator trick; cTrader charts use cAlgo (C#). The app's own charts are
  unaffected — they render from `/candles` + app-computed levels.

## Honest differences vs the MT5 bridge

| Thing | MT5 bridge | cTrader bridge |
|---|---|---|
| Terminal required | Yes (Windows, logged in, Ctrl+E) | **None** |
| Equity/margin | Read from terminal | Derived (balance + unrealized PnL; Σ used margin) |
| Tick value / contract currencies | From terminal spec | Not exposed (PnL is computed account-side on cTrader) |
| SL/TP on history rows | Recovered from opening orders | `null` in v1 |
| Deposits in history-summary | From deal ledger | `null` (separate cash-flow API, v2) |

## Running permanently

Any always-on Linux box: `systemd`, `supervisord`, or
`docker run --restart unless-stopped` (plain x86/ARM Linux container — no
emulation needed, so Apple Silicon is fine). A tunnel is only needed if the
bridge and the app can't otherwise reach each other; on a VPS use a
Cloudflare **named** tunnel for a stable URL.
