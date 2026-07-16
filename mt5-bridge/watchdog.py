"""MT5 Bridge watchdog — reliability supervisor for the Windows bridge machine.

Solves the three real-money infrastructure risks in one always-on process:

  1. AUTO-RESTART  — supervises the Flask bridge (and the Cloudflare tunnel) as
     child processes; if either dies it is restarted immediately.
  2. STABLE URL    — with a persistent NAMED Cloudflare tunnel the URL never
     changes. If you use a QUICK tunnel instead, the watchdog captures the fresh
     https://…trycloudflare.com URL and PUSHES it to the app's settings endpoint,
     so the app keeps working with no manual "paste the new URL" step.
  3. ALERTING      — sends a Telegram message on start, on bridge down/restart,
     when MT5 disconnects, and when the tunnel URL changes — so you KNOW the
     moment execution capability drops, instead of finding out on a trade.

Run it INSTEAD of launching mt5_bridge.py directly:

    python watchdog.py

Environment (reuses the bridge's own vars; extra ones for push/alerts):
    MT5_BRIDGE_PORT        bridge port (default 5000)
    MT5_BRIDGE_API_KEY     bridge key (passed through to the bridge)
    TELEGRAM_BOT_TOKEN     for alerts (optional but recommended)
    TELEGRAM_CHAT_ID       for alerts
    APP_BASE_URL           e.g. https://ict-trading-os-rho.vercel.app  (to push URL)
    APP_API_KEY            the app's X-Api-Key (to push URL)
    TUNNEL_NAME            optional: run a persistent NAMED tunnel instead of a
                           quick tunnel (URL never changes; no push needed)
    CLOUDFLARED           path to cloudflared (default: "cloudflared" on PATH)
    HEALTH_INTERVAL        seconds between health checks (default 20)

See docs/BRIDGE_RELIABILITY.md for the one-time named-tunnel setup and running
this as a boot service.
"""
import os
import re
import subprocess
import sys
import time
from datetime import datetime, timezone

try:
    import requests
except ImportError:
    sys.exit("watchdog needs `requests` — run: pip install requests")

PORT = int(os.getenv("MT5_BRIDGE_PORT", "5000"))
BOT = os.getenv("TELEGRAM_BOT_TOKEN", "")
CHAT = os.getenv("TELEGRAM_CHAT_ID", "")
APP_BASE = (os.getenv("APP_BASE_URL", "") or "").rstrip("/")
APP_KEY = os.getenv("APP_API_KEY", "")
TUNNEL_NAME = os.getenv("TUNNEL_NAME", "")
CLOUDFLARED = os.getenv("CLOUDFLARED", "cloudflared")
HEALTH_INTERVAL = int(os.getenv("HEALTH_INTERVAL", "20"))
LOCAL = f"http://127.0.0.1:{PORT}"
_QUICK_URL = re.compile(r"https://[a-z0-9-]+\.trycloudflare\.com")


def log(msg: str) -> None:
    print(f"[{datetime.now().strftime('%H:%M:%S')}] {msg}", flush=True)


def alert(msg: str) -> None:
    """Best-effort Telegram alert (never raises)."""
    log(f"ALERT: {msg}")
    if not (BOT and CHAT):
        return
    try:
        requests.post(f"https://api.telegram.org/bot{BOT}/sendMessage",
                      json={"chat_id": CHAT, "text": f"🖥️ MT5 bridge: {msg}"}, timeout=10)
    except Exception:
        pass


def push_url(url: str) -> None:
    """Tell the app the current bridge URL so it auto-reconnects (quick tunnels)."""
    if not (APP_BASE and APP_KEY):
        return
    try:
        r = requests.post(f"{APP_BASE}/api/settings/mt5-bridge-url",
                          json={"url": url}, headers={"X-Api-Key": APP_KEY}, timeout=20)
        ok = r.status_code == 200 and (r.json() or {}).get("reachable")
        log(f"pushed URL to app: {url} → {'reachable' if ok else r.status_code}")
    except Exception as e:
        log(f"URL push failed: {type(e).__name__}")


def start_bridge() -> subprocess.Popen:
    here = os.path.dirname(os.path.abspath(__file__))
    log("starting bridge (mt5_bridge.py)…")
    return subprocess.Popen([sys.executable, os.path.join(here, "mt5_bridge.py")], cwd=here)


def start_tunnel() -> subprocess.Popen:
    if TUNNEL_NAME:
        log(f"starting NAMED tunnel '{TUNNEL_NAME}' (stable URL)…")
        return subprocess.Popen([CLOUDFLARED, "tunnel", "run", TUNNEL_NAME],
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
    log("starting QUICK tunnel…")
    return subprocess.Popen([CLOUDFLARED, "tunnel", "--url", LOCAL],
                            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)


def capture_quick_url(proc: subprocess.Popen, timeout: int = 40) -> str:
    """Read cloudflared output until the trycloudflare URL appears."""
    deadline = time.time() + timeout
    while time.time() < deadline and proc.poll() is None:
        line = proc.stdout.readline() if proc.stdout else ""
        if not line:
            time.sleep(0.2)
            continue
        m = _QUICK_URL.search(line)
        if m:
            return m.group(0)
    return ""


def bridge_ok() -> tuple:
    """(reachable, mt5_connected) from the unauthenticated local status route."""
    try:
        r = requests.get(f"{LOCAL}/", timeout=8)
        if r.status_code == 200:
            b = r.json()
            return True, bool(b.get("mt5_connected"))
    except Exception:
        pass
    return False, False


def main() -> None:
    alert(f"watchdog started (port {PORT}, {'named' if TUNNEL_NAME else 'quick'} tunnel)")
    bridge = start_bridge()
    time.sleep(5)
    tunnel = start_tunnel()
    current_url = "" if TUNNEL_NAME else capture_quick_url(tunnel)
    if current_url:
        alert(f"tunnel up: {current_url}")
        push_url(current_url)
    elif not TUNNEL_NAME:
        alert("could not read quick-tunnel URL — check cloudflared")

    last_reachable, last_mt5 = True, True
    fail_streak = 0
    while True:
        time.sleep(HEALTH_INTERVAL)

        # Restart the bridge process if it exited.
        if bridge.poll() is not None:
            alert("bridge process exited — restarting")
            bridge = start_bridge()
            time.sleep(5)

        # Restart the tunnel process if it exited (URL changes for quick tunnels).
        if tunnel.poll() is not None:
            alert("tunnel process exited — restarting")
            tunnel = start_tunnel()
            new_url = "" if TUNNEL_NAME else capture_quick_url(tunnel)
            if new_url and new_url != current_url:
                current_url = new_url
                alert(f"tunnel URL changed: {current_url}")
                push_url(current_url)

        reachable, mt5 = bridge_ok()

        if not reachable:
            fail_streak += 1
            if last_reachable:
                alert("bridge is NOT responding locally")
            # Two consecutive failures → force a bridge restart.
            if fail_streak >= 2 and bridge.poll() is None:
                log("bridge unresponsive — killing to force a clean restart")
                try:
                    bridge.terminate()
                except Exception:
                    pass
        else:
            if not last_reachable:
                alert("bridge is back UP")
            fail_streak = 0
            if mt5 and not last_mt5:
                alert("MT5 terminal reconnected")
            if not mt5 and last_mt5:
                alert("MT5 terminal is DISCONNECTED (bridge up, but not logged in)")
            last_mt5 = mt5
        last_reachable = reachable


if __name__ == "__main__":
    try:
        main()
    except KeyboardInterrupt:
        log("watchdog stopped")
