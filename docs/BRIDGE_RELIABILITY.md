# MT5 Bridge Reliability (infra hardening)

The single biggest real-money risk in this system is **not the code** — it's that
execution depends on one Windows machine running MetaTrader 5 + the Flask bridge,
exposed over a tunnel. If the bridge crashes, the PC sleeps, or the tunnel URL
changes, orders silently can't be placed. The app now **fails safe** (it blocks
orders and shows a red banner when it can't reach a live bridge), but that's
detection, not prevention.

`mt5-bridge/watchdog.py` is the prevention layer. It supervises the bridge + the
tunnel, restarts either on failure, keeps the app pointed at the right URL, and
**alerts you on Telegram the moment execution capability drops.**

---

## Option A — Persistent named tunnel (recommended: the URL never changes)

A Cloudflare *quick* tunnel gets a new random URL every restart. A *named* tunnel
gives you a fixed hostname forever. One-time setup (needs a free Cloudflare
account + a domain on Cloudflare):

```powershell
# 1. Install cloudflared (https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/)
winget install --id Cloudflare.cloudflared

# 2. Authenticate (opens a browser)
cloudflared tunnel login

# 3. Create a named tunnel (once)
cloudflared tunnel create ictos-bridge

# 4. Route a hostname to it (pick a subdomain on your Cloudflare domain)
cloudflared tunnel route dns ictos-bridge bridge.yourdomain.com

# 5. Create config file  %USERPROFILE%\.cloudflared\config.yml :
#    tunnel: ictos-bridge
#    credentials-file: C:\Users\<you>\.cloudflared\<tunnel-id>.json
#    ingress:
#      - hostname: bridge.yourdomain.com
#        service: http://localhost:5000
#      - service: http_status:404
```

Then in the app **once**: Settings → MT5 Bridge Connection → set the URL to
`https://bridge.yourdomain.com`. It never changes again. Run the watchdog with
`TUNNEL_NAME=ictos-bridge` and it won't touch the URL.

## Option B — Quick tunnel with auto-push (zero Cloudflare account)

Keep using quick tunnels, but let the watchdog **auto-update the app** with each
new URL (no manual paste). Set `APP_BASE_URL` + `APP_API_KEY` and leave
`TUNNEL_NAME` unset.

---

## Running the watchdog

Set environment variables (PowerShell example), then run it **instead of**
`mt5_bridge.py`:

```powershell
$env:MT5_BRIDGE_API_KEY = "<your bridge key>"
$env:TELEGRAM_BOT_TOKEN = "<bot token>"     # for alerts
$env:TELEGRAM_CHAT_ID   = "<your chat id>"
# For Option B (quick-tunnel auto-push):
$env:APP_BASE_URL = "https://ict-trading-os-rho.vercel.app"
$env:APP_API_KEY  = "<the app's X-Api-Key>"
# For Option A (named tunnel):
# $env:TUNNEL_NAME = "ictos-bridge"

cd mt5-bridge
python watchdog.py
```

You'll get a Telegram message on startup, and thereafter on: bridge down/restart,
MT5 disconnect/reconnect, and tunnel URL change.

## Run it automatically at boot

**Task Scheduler (simplest):** create a Basic Task → Trigger: *At log on* →
Action: Start a program → `python` with argument `C:\path\to\mt5-bridge\watchdog.py`
and *Start in* = the `mt5-bridge` folder. Tick *Run whether user is logged on or
not* and *Restart on failure*.

**As a Windows service (most robust):** use [NSSM](https://nssm.cc):
```powershell
nssm install ICTOSBridge "C:\Python\python.exe" "C:\path\to\mt5-bridge\watchdog.py"
nssm set ICTOSBridge AppDirectory "C:\path\to\mt5-bridge"
nssm set ICTOSBridge AppEnvironmentExtra MT5_BRIDGE_API_KEY=... TELEGRAM_BOT_TOKEN=... TELEGRAM_CHAT_ID=... APP_BASE_URL=... APP_API_KEY=...
nssm start ICTOSBridge
```

## Also worth doing (OS-level)

- **Disable sleep/hibernate** on the bridge PC (`powercfg /change standby-timeout-ac 0`).
- Set the MT5 terminal to **launch on startup** and auto-login (Tools → Options →
  keep the account logged in). The watchdog restarts the *bridge*, but MT5 itself
  must be running for the bridge to connect — the watchdog will alert you if MT5
  is disconnected so you can intervene.

## What the watchdog does NOT do

It can't force-launch or log into the MT5 terminal for you (that's a GUI app with
its own login) — it detects and *alerts* on an MT5 disconnect. Everything else
(bridge process, tunnel, URL, notifications) is automatic.
