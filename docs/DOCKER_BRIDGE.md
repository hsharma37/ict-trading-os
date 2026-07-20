# MT5 bridge in Docker — no Windows machine

The Windows MT5 terminal, Windows Python, and the bridge run under **Wine**
inside one Linux container; `cloudflared` runs as a compose sidecar. You log
into the terminal **from your Mac's browser** (noVNC). No Windows license,
no Windows box.

## The two facts this design lives with

1. **The MetaTrader5 Python package only talks to a Windows terminal.** The
   Mac MT5 app can never serve the API — so the *authoritative* terminal
   (the one the bridge trades and reads through) lives in the container.
   Your Mac terminal stays for watching charts.
2. **Wine is the trade-off.** This pattern is widely used, but it is less
   bulletproof than native Windows. For real-money reliability the Windows
   VPS route (`docs/VPS_MIGRATION.md`) remains the boring, safest option.
   Run this container for a week on demo before trusting it live.

## Where to host

An **x86_64 Linux VPS** (~$5–8/mo — cheaper than Windows VPS, no license).

**Apple Silicon Macs are a verified dead end** (tested 2026-07-20): the image
builds and the tunnel mints a URL, but Wine's preloader cannot start under
either emulator — Rosetta punts it (static binary, fixed low-address
mappings) and QEMU dies on `anon_mmap_fixed` page-mask assertions. On a real
x86 host no emulation is involved and this pattern is well-proven.

## Setup (~20 min + first-boot installs)

```bash
# on the VPS
git clone https://github.com/hsharma37/ict-trading-os.git && cd ict-trading-os
cp mt5-bridge/.env.example mt5-bridge/.env && nano mt5-bridge/.env
#   MT5_LOGIN / MT5_PASSWORD / MT5_SERVER (exact string)
#   MT5_BRIDGE_API_KEY  = same as the app's Vercel env
#   MT5_TERMINAL_PATH   = C:\Program Files\MetaTrader 5\terminal64.exe

docker compose -f docker-compose.mt5.yml up -d --build
docker compose -f docker-compose.mt5.yml logs -f mt5bridge   # watch first-boot installs
```

First boot downloads + installs MT5 and Python under Wine into a persistent
volume (several minutes). Broker builds: set `MT5_DOWNLOAD_URL` to your
broker's installer if you don't want the MetaQuotes default.

**One-time terminal login, from your Mac:**
```bash
ssh -L 6080:localhost:6080 <user>@<vps>     # noVNC is localhost-only on the VPS
# then open http://localhost:6080 in your Mac browser
```
Log the terminal into your account, enable **Algo Trading** (Ctrl+E). The
login persists in the `wineprefix` volume.

**Tunnel URL:**
```bash
docker compose -f docker-compose.mt5.yml logs cloudflared | grep trycloudflare
```
Paste it into **Settings → MT5 Bridge Connection → Save & Test** → expect
green "MT5 terminal connected". For a URL that never changes, switch the
sidecar to a named tunnel (`TUNNEL_TOKEN` — see compose comments).

## Chart levels on your Mac terminal

The bridge draws levels inside the *container's* terminal — your Mac terminal
has its own files sandbox and won't see them. Two options:

- **Watch via noVNC** — attach `ICTOSLevels.mq5` in the containerized
  terminal once (copy it in via the VNC session, F7-compile).
- **Better: draw on your Mac charts** with the companion script — it fetches
  levels from the app and writes the same CSVs into your Mac terminal's
  `MQL5/Files` (File → Open Data Folder to find it):

```bash
python3 scripts/mac_levels_writer.py \
  --app-url https://<your-app>/api \
  --files-dir "/Users/you/…/MQL5/Files" \
  --symbols EURUSD,XAUUSD --interval 300
```

Same indicator, same drawings, on the charts you actually look at.

## Operations

| Task | Command |
|---|---|
| Update bridge code | `git pull` on the VPS, then `docker compose -f docker-compose.mt5.yml restart mt5bridge` (the repo is bind-mounted) |
| Bridge logs | `docker compose -f docker-compose.mt5.yml logs -f mt5bridge` |
| New tunnel URL after restart | `logs cloudflared`, re-paste in Settings (or use a named tunnel) |
| Full reset (keeps nothing) | `docker compose -f docker-compose.mt5.yml down -v` |

## Security

- Port 5000 is never published — only the tunnel reaches the bridge, same
  posture as before. `X-Bridge-Key` still guards every route.
- noVNC binds to `127.0.0.1` on the VPS — reach it only over SSH tunnels.
  Never map it publicly: it is your logged-in trading terminal.
- The `wineprefix` volume + `.env` hold live credentials. Same rule as the
  Windows VPS: this machine runs the bridge and nothing else.

## Honest status

This scaffold follows the widely-used Wine/MT5 container pattern, but it was
authored without a live broker login to verify end-to-end (that requires your
credentials via noVNC). Expect possibly one iteration: if the terminal or
`mt5.initialize()` misbehaves under your broker's build, capture
`logs mt5bridge` and the `/` status JSON (`mt5_status` says exactly what
failed) and iterate from there.
