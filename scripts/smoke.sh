#!/usr/bin/env bash
# Post-deploy smoke check (PROGRESS P5). Usage: ./scripts/smoke.sh [BASE_URL]
# Exits non-zero if the deploy is not serving the app + API + data routes.
set -euo pipefail
BASE="${1:-https://ict-trading-os-rho.vercel.app}"
fail() { echo "SMOKE FAIL: $1" >&2; exit 1; }

# 1. SPA shell
curl -sf -o /dev/null "$BASE/" || fail "SPA index not serving"
# 2. API health — must report a durable backend
H=$(curl -sf "$BASE/api/health") || fail "/api/health unreachable"
echo "$H" | grep -q '"status"' || fail "health has no status: $H"
# 3. One real data route (public read)
curl -sf "$BASE/api/research/instruments" | grep -q "EURUSD" || fail "instruments route broken"
# 4. Protected route is deployed AND guarded: 200 (keyed env) or 401 (fail-closed)
#    both prove the route exists; 404/5xx means the deploy is broken.
CODE=$(curl -s -o /dev/null -w "%{http_code}" "$BASE/api/mt5/status")
[ "$CODE" = "200" ] || [ "$CODE" = "401" ] || fail "/api/mt5/status returned $CODE"
echo "SMOKE OK: $BASE"
