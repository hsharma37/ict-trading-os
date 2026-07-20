#!/usr/bin/env python3
"""Draw ICT levels on a Mac (or any local) MT5 terminal's charts.

The containerized bridge writes level CSVs inside ITS OWN terminal — your Mac
terminal never sees them. This companion closes that gap: it fetches the same
levels from the app API and writes the same CSV files into YOUR terminal's
MQL5/Files folder, so the ICTOSLevels indicator renders identically on the
charts you actually watch. Stdlib only — no pip installs.

Usage:
  python3 scripts/mac_levels_writer.py \
      --app-url https://ict-trading-os-rho.vercel.app/api \
      --files-dir "<your terminal's MQL5/Files folder>" \
      --symbols EURUSD,XAUUSD --interval 300
  API key: --api-key or env ICTOS_API_KEY (required for /mt5 draw parity? no —
  /ict/levels is a read route; pass the key anyway if your deployment protects reads).

Find the Files folder from the Mac terminal: File → Open Data Folder → MQL5/Files.
"""
from __future__ import annotations

import argparse
import json
import os
import sys
import time
import urllib.request


def fetch_levels(app_url: str, symbol: str, api_key: str) -> dict:
    req = urllib.request.Request(f"{app_url.rstrip('/')}/ict/levels/{symbol}")
    if api_key:
        req.add_header("X-Api-Key", api_key)
    with urllib.request.urlopen(req, timeout=30) as r:
        return json.load(r)


def to_csv(symbol: str, data: dict) -> str:
    """Mirror mt5_client.write_levels_file exactly — the indicator parses this."""
    dr = data.get("dealing_range") or {}
    lines = [
        f"#META,{symbol.upper()},{data.get('current_price', '')},"
        f"{dr.get('high', '')},{dr.get('low', '')},{dr.get('equilibrium', '')},"
        f"{data.get('premium_discount', '')},{data.get('htf_bias', '') or ''}"
    ]
    for tf, r in (data.get("ranges") or {}).items():
        if r:
            lines.append(f"#RANGE,{tf},{r.get('high', '')},{r.get('low', '')},{r.get('equilibrium', '')}")
    for z in data.get("zones", []):
        lines.append(",".join(str(x) for x in [
            z.get("kind", "zone"), z.get("type", ""), z.get("direction", ""),
            z.get("timeframe", ""), z.get("high", ""), z.get("low", ""),
        ]))
    return "\n".join(lines) + "\n"


def run_once(app_url: str, files_dir: str, symbols: list[str], api_key: str) -> None:
    for sym in symbols:
        try:
            data = fetch_levels(app_url, sym, api_key)
            if data.get("error") or data.get("synthetic"):
                print(f"  {sym}: skipped — {data.get('error') or 'synthetic data'}")
                continue
            path = os.path.join(files_dir, f"ictos_levels_{sym.upper()}.csv")
            with open(path, "w", encoding="utf-8") as f:
                f.write(to_csv(sym, data))
            print(f"  {sym}: {len(data.get('zones', []))} zones -> {path}")
        except Exception as e:  # noqa: BLE001 — keep the loop alive per symbol
            print(f"  {sym}: FAILED — {e}", file=sys.stderr)


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--app-url", required=True, help="e.g. https://<your-app>/api")
    ap.add_argument("--files-dir", required=True,
                    help="Your terminal's MQL5/Files folder (File -> Open Data Folder)")
    ap.add_argument("--symbols", default="EURUSD,GBPUSD,XAUUSD")
    ap.add_argument("--api-key", default=os.environ.get("ICTOS_API_KEY", ""))
    ap.add_argument("--interval", type=int, default=0,
                    help="seconds between refreshes; 0 = run once and exit")
    args = ap.parse_args()

    if not os.path.isdir(args.files_dir):
        sys.exit(f"files-dir does not exist: {args.files_dir}")
    symbols = [s.strip().upper() for s in args.symbols.split(",") if s.strip()]

    while True:
        print(f"[{time.strftime('%H:%M:%S')}] writing levels…")
        run_once(args.app_url, args.files_dir, symbols, args.api_key)
        if not args.interval:
            break
        time.sleep(args.interval)


if __name__ == "__main__":
    main()
