# Moving the MT5 bridge to a Windows VPS — migration checklist

Goal: your home PC no longer needs to stay on. The terminal + bridge + tunnel move to
an always-on Windows VPS; the app needs **zero code changes** — only the tunnel URL
in Settings changes.

## 0. Pick a VPS (~10 min)

- Any **Windows Server** VPS works. Forex-focused hosts (ForexVPS, FXVM) or generic
  (Contabo, Vultr, AWS Lightsail Windows) — ~$10–25/mo.
- Specs: **2 vCPU / 4 GB RAM / 40 GB disk** is comfortable (MT5 + Python + tunnel are light).
- Region: near your **broker's server** (check ping in MT5: Tools → Options → Server),
  not near you — execution latency beats RDP comfort.

## 1. Install the stack on the VPS (~30 min)

Connect via RDP (Remote Desktop), then:

1. **MetaTrader 5** — download from your broker (not metatrader.com — brokers ship
   their own build). Log into your account. **Enable Algo Trading** (Ctrl+E).
2. **Python 3.12 (64-bit)** — python.org installer. ⚠️ NOT 3.13: the MetaTrader5
   package has no 3.13 wheel. Tick "Add to PATH".
3. **Git** — git-scm.com.
4. **cloudflared** — `winget install --id Cloudflare.cloudflared` (or download
   `cloudflared-windows-amd64.exe` from Cloudflare's official GitHub releases only).

## 2. Deploy the bridge (~15 min)

```powershell
git clone https://github.com/hsharma37/ict-trading-os.git
cd ict-trading-os\mt5-bridge
pip install -r requirements.txt
copy .env.example .env
notepad .env
```

Fill `.env` (copy the values from your home PC's `mt5-bridge\.env`):
- `MT5_LOGIN` / `MT5_PASSWORD` / `MT5_SERVER` — the server string must match the
  terminal's login dialog EXACTLY.
- `MT5_BRIDGE_API_KEY` — same value as the app's `MT5_BRIDGE_API_KEY` on Vercel.
- `APP_BASE_URL` + `CRON_SECRET` if you use the hourly Telegram poll.

Then start and verify locally on the VPS:

```powershell
python mt5_bridge.py
# in a second terminal:
curl http://localhost:5000/
#  → "mt5_connected": true  (if false, the mt5_status field says exactly why)
```

## 3. Tunnel (~10 min)

Quick tunnel (URL changes each restart — fine to start):
```powershell
cloudflared tunnel --url http://localhost:5000
```
Paste the printed `https://….trycloudflare.com` URL into the app:
**Settings → MT5 Bridge Connection → Save & Test** → expect green
"Bridge reachable · MT5 terminal connected (<your server>)".

**Recommended upgrade once settled:** a **named tunnel** (needs a domain on
Cloudflare) gives a URL that NEVER changes — no more re-pasting:
```powershell
cloudflared tunnel login
cloudflared tunnel create mt5bridge
cloudflared tunnel route dns mt5bridge bridge.yourdomain.com
cloudflared tunnel run mt5bridge
```

## 4. Make it survive reboots (~15 min)

Task Scheduler → two "At startup" tasks (Run whether user is logged on or not):
1. `python C:\...\ict-trading-os\mt5-bridge\mt5_bridge.py`
2. `cloudflared tunnel run mt5bridge` (or the quick-tunnel command)

MT5 terminal: put a shortcut in `shell:startup`, and in MT5 options enable
auto-login. The bridge's `watchdog.py` can also supervise the bridge process.
Set Windows Update to a maintenance window (unplanned reboots = downtime).

## 5. Verify end-to-end (~5 min)

- App header shows **Live · MT5**.
- `./scripts/smoke.sh` passes (from any machine).
- Draw levels on a chart → indicator renders (pull + compile `ICTOSLevels.mq5`
  in the VPS terminal's MetaEditor once).
- Forward tests tick without your home PC on.

## 6. Decommission the home PC

Only after a full trading day of VPS stability: stop the home bridge/tunnel and
remove its Task Scheduler entries. Keep the home `.env` as backup — or delete it
if the VPS is now canonical (it holds your MT5 password).

## Security notes

- The bridge is exposed only through the tunnel; `X-Bridge-Key` guards every
  data/trade route. Never open port 5000 in the VPS firewall directly.
- Use a **strong, unique Windows password** — RDP on a public IP gets brute-forced;
  restrict RDP to your IP in the VPS firewall if the host allows it.
- The VPS holds live account credentials (`.env` + logged-in terminal). Treat it
  like your trading account itself: no other software, no browsing on it.

## Ongoing

- **Update flow is unchanged** — when a PR touches `mt5-bridge/`: RDP in,
  `git pull`, restart the bridge (F7-recompile the indicator if it changed).
- If the quick-tunnel URL rotates (VPS reboot), paste the new one in Settings —
  or eliminate that forever with the named tunnel above.
