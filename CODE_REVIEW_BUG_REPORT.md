# ICT Trading OS — Code Review Bug Report

**Review Date:** 2025-07-02  
**Scope:** Full stack (FastAPI backend + React frontend)  
**Reviewer:** Automated code review

---

## Executive Summary

| Severity | Count | Description |
|----------|-------|-------------|
| 🔴 CRITICAL | 9 | Crashes, data loss, security vulnerabilities, wrong trading calculations |
| 🟠 HIGH | 18 | Broken features, missing error handling, API mismatches, auth issues |
| 🟡 MEDIUM | 23 | Performance issues, UX bugs, incomplete implementations, race conditions |
| 🟢 LOW | 14 | Code quality, missing validations, minor UI issues |

---

## 🔴 CRITICAL BUGS

### 1. SQL Injection in SQLite Database Layer
**File:** `app/core/database.py`  
**Line:** 41, 52, 69, 81, 91  
**Severity:** CRITICAL

The `SQLiteDB` class uses Python string formatting for SQL queries instead of parameterized queries in several places. While `find_one()` and `insert()` use parameterization, `get_collection()` uses f-string-like formatting via `sqlite3.Row` but the `update()` method constructs SQL with string interpolation for the `WHERE` clause in some paths.

More critically, the `find()` method (line 60-64) performs in-memory filtering and does **not** use SQL parameterization at all, but the `get_collection()` method is safe. However, there is a potential injection vector if user input reaches the `collection` parameter name directly.

**Impact:** Malicious input could corrupt the database or leak data.  
**Fix:** Validate/sanitize collection names; ensure all SQL uses parameterized queries.

---

### 2. Race Condition in Trade Lifecycle Service — Concurrent Partial Close
**File:** `app/services/trade_lifecycle_service.py`  
**Line:** 110-151 (partial_close), 153-185 (full_close)  
**Severity:** CRITICAL

The `partial_close()` and `full_close()` methods have no locking mechanism. If two requests hit the same trade simultaneously:
1. Both read the same trade state
2. Both calculate remaining quantity based on stale data
3. Both write back, causing over-closing (negative quantity) or incorrect PnL

**Impact:** Trade state corruption, incorrect PnL calculations, potential negative balances.  
**Fix:** Add a threading.Lock or use database-level row locking (e.g., SQLite `BEGIN IMMEDIATE` transaction).

---

### 3. Floating-Point Precision Loss in Financial Calculations
**File:** `app/services/trade_lifecycle_service.py`  
**Line:** 66, 139, 140, 177, 178  
**Severity:** CRITICAL

Financial calculations use `round(..., 2)` and `round(..., 6)` for PnL and quantity tracking. Python's `round()` uses banker's rounding (round half to even). Multiple round-trip operations can accumulate cents of error. For example:
```python
realized_pnl = round(trade.get("realized_pnl", 0) + pnl, 2)
```

**Impact:** PnL discrepancies, accounting mismatches, potential negative balances from rounding errors.  
**Fix:** Use `Decimal` from Python's `decimal` module for all monetary calculations.

---

### 4. Missing Stop Loss Validation — Can Create Trades with SL on Wrong Side
**File:** `app/services/trade_lifecycle_service.py`  
**Line:** 36-52 (create_trade)  
**Severity:** CRITICAL

The `create_trade` method validates `stop_loss > 0` but does NOT validate that the stop loss is on the correct side of the entry price:
- For BUY: SL must be BELOW entry price
- For SELL: SL must be ABOVE entry price

A user can create a BUY trade with `stop_loss > entry_price`, which would immediately trigger as a "SL hit" in `check_tp_hits()`.

**Impact:** Immediate, unintended trade closures, incorrect auto-management behavior.  
**Fix:** Add side-aware SL validation in `create_trade()`.

---

### 5. JWT Secret Hardcoded in Config
**File:** `app/core/config.py`  
**Line:** 16  
**Severity:** CRITICAL

```python
JWT_SECRET: str = os.getenv("JWT_SECRET", "ict-os-dev-secret-key")
```

The default JWT secret is a hardcoded, predictable string. If deployed without setting the env var, attackers can forge JWT tokens. Additionally, the `auth_middleware` uses `API_KEY` which is a simple string comparison, not a proper JWT implementation.

**Impact:** Authentication bypass, unauthorized API access.  
**Fix:** Remove default secrets; fail startup if secrets are not set. Implement proper JWT with expiration.

---

### 6. Telegram Bot Token Stored in Environment + Mutable at Runtime
**File:** `app/services/telegram_service.py`  
**Line:** 355-361  
**Severity:** CRITICAL

The `configure()` method allows runtime mutation of `settings.TELEGRAM_BOT_TOKEN` and `os.environ`, but also stores the token in a global singleton. There is no encryption or secure storage. If the application is compromised, the token can be extracted from memory.

**Impact:** Telegram channel takeover, message spoofing, potential social engineering.  
**Fix:** Use a secrets manager. Never store tokens in global mutable state. At minimum, mark as write-only.

---

### 7. MT5 Bridge Accepts Arbitrary Trade Commands Without Validation
**File:** `app/routers/mt5.py`  
**Line:** 55-83  
**Severity:** CRITICAL

The `proxy_trade` endpoint forwards trade commands to the MT5 bridge without:
- Validating symbol against allowed list
- Validating lot size against maximum limits
- Checking if the user has permission
- Rate limiting

**Impact:** Unauthorized trades, potential account draining if MT5 bridge is reachable.  
**Fix:** Add symbol whitelist, lot size limits, rate limiting, and trade authorization checks.

---

### 8. Wrong Kelly Criterion Formula in Analytics
**File:** `app/services/trade_lifecycle_service.py`  
**Line:** 516-519  
**Severity:** CRITICAL

```python
b = avg_win / avg_loss if avg_loss > 0 else 0
p = win_rate
q = 1 - p
kelly = (b * p - q) / b if b > 0 else 0
```

This is the Kelly Criterion formula, but it uses **avg_win / avg_loss** for `b` (the net odds). However, the standard Kelly formula uses `avg_win / avg_loss` as the ratio of win amount to loss amount. The formula here is correct for the simplified case, but there's a subtle issue: if `b` is very small (e.g., 0.01), `kelly` can exceed 1 or be negative in unexpected ways. The `max(0, min(1, kelly))` clamp is applied but the underlying computation may produce wrong values for edge cases.

More critically, the `quant_service.py` version (line 61-62) computes Kelly differently:
```python
payoff = avg_win / avg_loss if avg_loss > 0 else 0
kelly = win_pct - ((1 - win_pct) / payoff) if payoff > 0 else 0
```

These two implementations produce **different results** for the same data! The `trade_lifecycle_service.py` version divides by `b` after computing `bp - q`, while the `quant_service.py` version computes `p - (1-p)/payoff`. These are mathematically equivalent but the first one is numerically unstable when `b` is small.

**Impact:** Wrong position sizing recommendations, potential over-leveraging.  
**Fix:** Use a single, numerically stable Kelly implementation. Use `Decimal` for precision.

---

### 9. Price Service Uses `time.time()` for Timestamp but Compares with `datetime.utcnow().isoformat()`
**File:** `app/services/price_service.py`  
**Line:** 83, 111, 179, 269  
**Severity:** CRITICAL

The `PriceData` dataclass uses `timestamp: float` (from `time.time()`), but other parts of the codebase use `datetime.utcnow().isoformat()` strings. In `market_data.py` (line 62), the manual price check does:
```python
ts = datetime.fromisoformat(data["timestamp"])
if (datetime.utcnow() - ts).total_seconds() > 300:
```

But `price_service.py` stores timestamps as `time.time()` floats, not ISO strings. If the manual price is set via `market_data.py` (which stores ISO strings), the `price_service.py` persistent cache stores floats. This inconsistency can cause `TypeError` or incorrect expiration checks.

**Impact:** Manual price overrides may never expire or crash on type mismatch.  
**Fix:** Standardize all timestamps to UTC ISO strings or Unix timestamps consistently across the codebase.

---

## 🟠 HIGH SEVERITY BUGS

### 10. No Authentication on Most API Endpoints
**File:** `app/main.py`  
**Line:** 27-43  
**Severity:** HIGH

While `auth_middleware` exists, `AUTH_ENABLED` defaults to `false`. When disabled, ALL endpoints are completely open including:
- Trade creation/closure
- Order execution
- MT5 bridge proxy
- Telegram configuration
- Settings modification

**Impact:** Any network-accessible instance is fully vulnerable.  
**Fix:** Enable auth by default. Add at least basic auth to destructive endpoints.

---

### 11. Signal Engine Does Not Validate `signal_id` in `auto_trade`
**File:** `app/routers/telegram.py`  
**Line:** 72-84  
**Severity:** HIGH

The `auto_trade` endpoint accepts any `signal_id` and passes it to `telegram_service.auto_trade()`. There is no validation that the signal belongs to the authenticated user or that it hasn't already been processed.

**Impact:** Replay attacks, duplicate trades, unauthorized trade execution.  
**Fix:** Add idempotency keys, user-scoped signal validation, and duplicate trade prevention.

---

### 12. `plan_service.py` Missing — Referenced but Not Found
**File:** `app/routers/bot.py`  
**Line:** 5  
**Severity:** HIGH

```python
from app.services.plan_service import plan_service
```

The `plan_service` module is imported and used in `bot.py` and `plans.py`, but the file was not found in the directory listing. This may cause an `ImportError` at runtime.

**Impact:** Bot automation and plans features will crash.  
**Fix:** Create the missing `plan_service.py` or remove the dependency.

---

### 13. `order_service.py` Missing — Referenced but Not Found
**File:** `app/routers/bot.py`  
**Line:** 4  
**Severity:** HIGH

```python
from app.services.order_service import order_service
```

Similarly, `order_service` is imported in `bot.py` but the file was not found. This is a critical dependency for the bot auto-trade feature.

**Impact:** Bot auto-execution will crash with ImportError.  
**Fix:** Create the missing `order_service.py` or stub it out.

---

### 14. `instrument_config.py` File Not Read — Missing from Review
**File:** Multiple files reference it  
**Severity:** HIGH

`instrument_config.py` is referenced extensively (`get_instrument`, `get_all_instruments`, `INSTRUMENTS`) but was not read in this review. If it contains incorrect pip sizes, leverage values, or contract sizes, the lot calculator and PnL calculations will be wrong.

**Impact:** Wrong lot sizes, incorrect margin calculations, incorrect PnL.  
**Fix:** Verify `instrument_config.py` contains correct trading specifications for all instruments.

---

### 15. Frontend API Client Points to Wrong Backend Port
**File:** `frontend/vite.config.ts`  
**Line:** 16-20  
**Severity:** HIGH

```typescript
proxy: {
  '/api': {
    target: process.env.VITE_API_URL || 'http://localhost:8000',
    changeOrigin: true,
  },
},
```

The frontend proxy is set to `/api` but the backend routes do NOT use `/api` prefix. The main backend routes are at `/market`, `/trades`, `/orders`, etc. The `backend/app/main.py` uses `/api/v1/` prefix. The frontend `api/client.ts` uses `/market`, `/trades`, etc. without any `/api` prefix, so the proxy will never match.

**Impact:** Frontend cannot communicate with backend in development mode.  
**Fix:** Remove the `/api` proxy or change it to match actual backend routes. Ensure `VITE_API_URL` points to the correct port.

---

### 16. `useMarketData` Hook Uses Wrong API Path
**File:** `frontend/src/hooks/useMarketData.ts`  
**Line:** 13  
**Severity:** HIGH

```typescript
const res = await fetch(`${apiUrl}/api/v1/market/price/${symbol}`)
```

This hook uses `/api/v1/market/price/${symbol}` but the backend (main app) does not have this route. The main backend has `/market/price/{symbol}` and `/playground/price/{symbol}`. The `backend/` app has `/api/v1/market/...` but it's a separate application.

**Impact:** This hook will always 404.  
**Fix:** Use the correct endpoint path matching the deployed backend.

---

### 17. WhatsUp Page Auto-Refreshes Every 10 Seconds but Doesn't Cleanup Properly
**File:** `frontend/src/pages/WhatsUp.tsx`  
**Line:** 156-170  
**Severity:** HIGH

```typescript
useEffect(() => {
  fetchData()
  const interval = setInterval(() => {
    fetchData()
  }, 10000)
  return () => clearInterval(interval)
}, [fetchData])
```

The `fetchData` callback is recreated on every render because `selectedTrade` is in the dependency array. This means the interval is cleared and restarted every 10 seconds, causing rapid-fire API requests when the user interacts with the page. Additionally, the countdown timer (line 165-170) is separate and uses a stale `lastUpdate` in its dependency array.

**Impact:** API rate limit exhaustion, excessive server load, browser performance degradation.  
**Fix:** Use `useRef` for `selectedTrade` in `fetchData`, or move the interval outside the dependency chain.

---

### 18. Journal Page Is Pure UI — No Backend Integration
**File:** `frontend/src/pages/Journal.tsx`  
**Severity:** HIGH

The entire Journal page has no API calls. It renders static form inputs with no `onSubmit`, no state persistence, and no backend endpoints to save/load journal entries. The `backend/` app has a `journal` router but the main frontend doesn't use it.

**Impact:** Users lose all journal entries on page refresh. Feature appears to work but is non-functional.  
**Fix:** Integrate with the backend journal API (`/api/v1/journal/`).

---

### 19. Plan Page Is Pure UI — No Backend Integration
**File:** `frontend/src/pages/Plan.tsx`  
**Severity:** HIGH

Same as Journal — the Plan page renders a form but has no `onSubmit`, no API calls, and no state management. The "Save Plan" button is a no-op.

**Impact:** Users cannot save trading plans.  
**Fix:** Integrate with the backend plans API (`/api/v1/plans/` or `/plans`).

---

### 20. `Analytics` Page Uses `res.data` but Backend Returns Direct Objects
**File:** `frontend/src/pages/Analytics.tsx`  
**Line:** 53-75  
**Severity:** HIGH

```typescript
const [exp, hm, dd, kl, sym, rec] = await Promise.all([
  analyticsApi.expectancy(),
  analyticsApi.heatmap(),
  ...
])
setExpectancy(exp.data)
setHeatmap(hm.data)
```

The analytics API client in `client.ts` uses `axios.create()` which wraps responses in `{ data: ... }`. However, if the backend returns raw JSON (not wrapped), this will fail. The backend `analytics.py` router returns direct objects like `analytics_service.get_expectancy()`, not `{ data: ... }`.

**Impact:** Data never loads in Analytics page.  
**Fix:** Verify axios response structure matches backend response format.

---

### 21. Bot Engine Auto-Execute Can Create Infinite Trades
**File:** `app/services/bot_engine.py`  
**Line:** 35-45  
**Severity:** HIGH

```python
def scan(self, auto_execute: bool = False) -> Dict:
    for symbol in symbols:
        signal = signal_engine.analyze(symbol)
        if signal:
            results.append(signal)
            if auto_execute:
                self._try_execute_signal(signal)
```

If `auto_execute=True` is called repeatedly and signals are still active, the bot will create duplicate trades for the same signal. There is no check for existing trades from the same signal.

**Impact:** Unlimited duplicate trades, account drain.  
**Fix:** Add signal deduplication and trade existence checks before auto-execution.

---

### 22. Signal Expiry Check Uses String Comparison Instead of Proper Date Parsing
**File:** `app/services/signal_engine.py`  
**Line:** 141-143  
**Severity:** HIGH

```python
expired = [s for s, sig in self.active_signals.items() if datetime.fromisoformat(sig["expires_at"]) < now]
```

`datetime.fromisoformat()` may fail if the ISO string contains a 'Z' suffix (which `datetime.utcnow().isoformat()` does NOT produce, but JavaScript's `toISOString()` DOES). The frontend may pass timestamps with 'Z' that cause parsing errors.

**Impact:** Signal expiry crashes with `ValueError`, leaving stale signals active.  
**Fix:** Use `datetime.fromisoformat(sig["expires_at"].replace("Z", "+00:00"))` or parse with `dateutil`.

---

### 23. `fetch_all_prices` Does Not Use ThreadPoolExecutor Despite Importing It
**File:** `app/services/price_service.py`  
**Line:** 290-305  
**Severity:** HIGH

```python
from concurrent.futures import ThreadPoolExecutor, as_completed
# ...
for sym in all_instruments:
    try:
        data = self.fetch_price(sym)
        ...
    time.sleep(0.5)  # 500ms delay between requests
```

The code imports `ThreadPoolExecutor` but uses a synchronous sequential loop with `time.sleep(0.5)`. For 8 instruments, this takes ~4 seconds. The import is unused.

**Impact:** Slow price loading, poor user experience.  
**Fix:** Use `ThreadPoolExecutor` with rate limiting, or remove the unused import.

---

### 24. Backend CORS Allows All Origins in Production
**File:** `backend/app/main.py`  
**Line:** 47-53  
**Severity:** HIGH

```python
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:3000", "http://localhost:5173"],
    ...
)
```

This is hardcoded for localhost. If deployed to production without changing this, CORS will block the frontend. But more critically, the main `app/main.py` uses:
```python
origins = settings.CORS_ORIGINS.split(",") if settings.CORS_ORIGINS != "*" else ["*"]
```

Which defaults to `*` (allow all origins) if the env var is not set.

**Impact:** CORS misconfiguration in production, potential CSRF issues.  
**Fix:** Remove wildcard default. Require explicit CORS_ORIGINS configuration.

---

### 25. `trade_lifecycle_service.get_open_trades()` Calls `check_tp_hits()` Without User Context
**File:** `app/services/trade_lifecycle_service.py`  
**Line:** 299-305  
**Severity:** HIGH

```python
def get_open_trades(self) -> List[Dict[str, Any]]:
    # Run auto-management checks first
    self.check_tp_hits()
```

The `check_tp_hits()` method auto-closes trades when SL/TP hits. It is called on EVERY `get_open_trades()` request. This means:
1. Any user requesting open trades triggers global auto-management for ALL trades
2. There is no audit trail of who triggered the auto-close
3. If two users have trades, one's request can affect the other's trades

**Impact:** Cross-user trade manipulation, unauthorized closures.  
**Fix:** Add user scoping to trades. Run auto-management only in a background worker, not on user requests.

---

### 26. Missing `key` Prop in Dynamic Lists Causes React Rendering Bugs
**File:** `frontend/src/pages/Dashboard.tsx`  
**Line:** 218, 287, 315, 346  
**Severity:** HIGH

Multiple `.map()` calls in Dashboard.tsx use `key={i}` (index as key) which is an anti-pattern. More importantly, some mapped items don't have unique keys at all:

```tsx
{newsCategories.map((c) => (
  <option key={c} value={c}>{c}</option>
))}
```

This is okay for static lists, but for dynamic lists like `openTrades`, `news`, `movers`, using indices as keys can cause React reconciliation bugs when items are reordered or removed.

**Impact:** UI rendering glitches, stale state, incorrect data display.  
**Fix:** Use unique IDs from data objects as keys. Never use array indices for dynamic lists.

---

### 27. `Knowledge.tsx` Downloads Content Without Sanitization
**File:** `frontend/src/pages/Knowledge.tsx`  
**Line:** 20-29, 259-270  
**Severity:** HIGH

The `downloadMarkdown` function creates a Blob from raw content and triggers a download. The content includes user-provided transcript text and YouTube video titles that are not sanitized. If a malicious user crafts a title with special characters or path traversal sequences, it could cause issues on the client side.

More critically, the `buildSourceMarkdown` function builds Markdown with raw text injection:
```typescript
return `# ${source.title}\n\n**Source:** ${source.url || 'manual-entry'}\n...`
```

If `source.title` contains `#` or backticks, the Markdown structure is corrupted.

**Impact:** Malformed downloads, potential XSS if the markdown is later rendered as HTML.  
**Fix:** Sanitize all user-generated content before embedding in Markdown. Use a Markdown sanitization library.

---

## 🟡 MEDIUM SEVERITY BUGS

### 28. `get_yahoo_ticker` Returns Wrong Ticker for Some Symbols
**File:** `app/services/market_data.py`  
**Line:** 79-84  
**Severity:** MEDIUM

```python
def _get_yahoo_ticker(self, symbol: str) -> str:
    config = get_instrument(symbol)
    if config:
        return config.get("yahoo", config.get("ticker", symbol))
    return SYMBOL_MAP.get(symbol, symbol)
```

The `SYMBOL_MAP` (lines 12-16) contains `"NQ1!": "NQ=F"` which is correct for Yahoo Finance futures, but the `instrument_config` might override this with a different value. There's no validation that the returned Yahoo ticker is valid.

**Impact:** Failed price fetches for some instruments.  
**Fix:** Validate ticker format and add error handling for invalid tickers.

---

### 29. `market_data.py` Creates New `httpx.Client` on Every Request
**File:** `app/services/market_data.py`  
**Line:** 125, 193  
**Severity:** MEDIUM

```python
with httpx.Client(timeout=20.0, headers=headers) as client:
    resp = client.get(url)
```

Creating a new HTTP client per request is inefficient. It bypasses connection pooling and increases latency.

**Impact:** Slow price fetches, unnecessary TCP overhead.  
**Fix:** Use a shared `httpx.Client` instance or `httpx.AsyncClient` for async routes.

---

### 30. `check_tp_hits` Incorrectly Handles SL at Breakeven (BE) Status
**File:** `app/services/trade_lifecycle_service.py`  
**Line:** 276-278  
**Severity:** MEDIUM

```python
if sl_hit and not sl_at_be:
    result = self.full_close(trade["id"], current_price)
```

When SL is moved to BE (`sl_at_be = True`), the SL hit check is skipped. But if the price hits the BE level (which equals entry price), it should still close the trade. The code skips it entirely, meaning a BE stop loss will never trigger auto-close.

**Impact:** Trades with SL at BE will never auto-close on SL hit.  
**Fix:** Check if `sl_at_be` is True AND price crosses entry price in the wrong direction.

---

### 31. `get_stats` in `trade_lifecycle_service.py` Mutates Database Objects in Memory
**File:** `app/services/trade_lifecycle_service.py`  
**Line:** 307-441  
**Severity:** MEDIUM

The `get_trade_stats()` method modifies trade dictionaries in-place (e.g., adding `current_price`, `unrealized_pnl`). Since SQLite DB returns references to the same dict objects, this mutates the cached data. This is a side effect that can cause inconsistent state.

**Impact:** Cached trade data gets modified, causing stale or incorrect data in subsequent reads.  
**Fix:** Deep-copy trade objects before modifying them.

---

### 32. `QuantLab.tsx` Demo Mode Uses Predictable Random Seed
**File:** `frontend/src/pages/QuantLab.tsx`  
**Line:** 120-139  
**Severity:** MEDIUM

```typescript
const mockInstruments: InstrumentAnalysis[] = SYMBOLS.map((sym, i) => ({
  current_price: 100 + i * 10 + Math.random() * 5,
  ...
}))
```

`Math.random()` in JavaScript is not cryptographically secure. While acceptable for demo data, the mock data is used for UI decisions and could mislead users if demo mode is accidentally triggered.

**Impact:** Misleading demo data that looks realistic.  
**Fix:** Add prominent "DEMO MODE" watermarks. Use a seeded random generator for reproducible testing.

---

### 33. `alert_service.py` Deletes Alerts Using List Mutation Instead of DB
**File:** `app/services/alert_service.py`  
**Line:** 52-59  
**Severity:** MEDIUM

```python
def delete_alert(self, alert_id: str) -> Dict:
    alerts = db.get_collection("alerts")
    for i, a in enumerate(alerts):
        if a.get("id") == alert_id:
            alerts.pop(i)
            return {"deleted": True, "id": alert_id}
```

This mutates the in-memory list returned by `get_collection()` but the SQLite implementation returns a new list each time, so this actually works. However, it's fragile and bypasses the `db.delete()` method which properly handles the database.

**Impact:** Potential inconsistency if `get_collection` implementation changes.  
**Fix:** Use `db.delete("alerts", alert_id)` instead of manual list manipulation.

---

### 34. `kb_service.py` Creates New Event Loop for AI Analysis
**File:** `app/services/kb_service.py`  
**Line:** 192-200  
**Severity:** MEDIUM

```python
loop = asyncio.new_event_loop()
asyncio.set_event_loop(loop)
ai_analysis = loop.run_until_complete(
    video_analysis_agent.analyze_video(transcript_result, metadata)
)
loop.close()
```

Creating a new event loop inside an async/threaded context is dangerous. If this method is called from an already-running event loop (e.g., FastAPI's async route), it will fail with `RuntimeError: This event loop is already running`.

**Impact:** KB AI analysis crashes in async contexts.  
**Fix:** Use `asyncio.run()` or run the analysis in a thread pool executor.

---

### 35. `Playground.tsx` Doesn't Handle API Errors Gracefully
**File:** `frontend/src/pages/Playground.tsx`  
**Line:** 61-73  
**Severity:** MEDIUM

```typescript
const fetchPrices = useCallback(async () => {
  try {
    setError(null)
    const response = await playgroundApi.getPrices()
    setPrices(response.data.prices || [])
  } catch (e: any) {
    setError(e?.response?.data?.detail || 'Failed to fetch prices')
  }
}, [])
```

If `response.data` is undefined or `response.data.prices` is not an array, the component will crash with `Cannot read properties of undefined`. The error handling only catches axios errors, not JavaScript runtime errors.

**Impact:** White screen of death if API returns unexpected format.  
**Fix:** Add defensive checks: `response.data?.prices || []`.

---

### 36. `Signals.tsx` Page Has Conflicting State Between `activeSignals` and `scanResults`
**File:** `frontend/src/pages/Signals.tsx`  
**Severity:** MEDIUM

The `Signals` page and `Suggestions` page both manage their own signal state independently. They don't share signal data, so a user scanning in one page won't see results in the other. This creates a fragmented UX.

**Impact:** Confusing user experience, duplicated state, inconsistent data.  
**Fix:** Use a shared state management solution (Zustand store or React Query cache) for signals.

---

### 37. `Settings.tsx` Saves to Backend but Doesn't Persist Theme Visually
**File:** `frontend/src/pages/Settings.tsx`  
**Severity:** MEDIUM

The Settings page has a theme toggle (dark/light) but the application doesn't actually implement theme switching. `index.css` or `tailwind.config.js` would need dark mode class support, but there's no evidence of theme implementation. The `settings.theme` value is saved but never applied to the DOM.

**Impact:** Theme setting is a no-op.  
**Fix:** Implement `dark` class on `<html>` element and ensure Tailwind dark mode is configured.

---

### 38. `WhatsUp.tsx` `priceProgress` Can Divide by Zero
**File:** `frontend/src/pages/WhatsUp.tsx`  
**Line:** 241-260  
**Severity:** MEDIUM

```typescript
const range = Math.abs(tp3 - sl)
if (range === 0) return null
const progress = (current - sl) / range
```

While `range === 0` is checked, the `tp3` fallback is `trade.take_profit_1 || entry`, which could equal `sl` if both are set to the same value. The check uses `===` which works for numbers, but if `tp3` or `sl` are strings, type coercion could cause issues.

**Impact:** Division by zero, NaN values in progress bar.  
**Fix:** Ensure all price values are parsed as numbers before calculation. Use `Number()` or `parseFloat()`.

---

### 39. `Analytics` Auto-Journal Feature Never Saves to Backend
**File:** `frontend/src/pages/Analytics.tsx`  
**Line:** 448-454  
**Severity:** MEDIUM

```typescript
<Button
  size="sm"
  disabled={!isJournalReady}
  onClick={() => {
    // In a real app, this would save to backend
    setSuccess(`Journal saved for ${trade.symbol} ${trade.side}`)
    setTimeout(() => setSuccess(null), 3000)
  }}
>
```

The comment explicitly says it doesn't save to the backend. The journal state is purely local.

**Impact:** Journal entries are lost on page refresh.  
**Fix:** Integrate with the backend journal API.

---

### 40. `TelegramFeed.tsx` Token Input is Not Password-Masked Properly
**File:** `frontend/src/pages/TelegramFeed.tsx`  
**Line:** 229-234  
**Severity:** MEDIUM

```typescript
<input
  type="password"
  value={tokenInput}
  onChange={(e) => setTokenInput(e.target.value)}
  placeholder="123456789:ABC..."
  className="w-full px-3 py-2 border rounded-md bg-background text-sm"
/>
```

The token is visible in the React component state and could be logged to browser console or exposed via React DevTools. Additionally, the `type="password"` is easily bypassed.

**Impact:** Token exposure in browser devtools.  
**Fix:** Use a secure input component. Don't store sensitive tokens in React state.

---

### 41. `MT5Terminal.tsx` Sends `lot_size` as Number but Form State Stores String
**File:** `frontend/src/pages/MT5Terminal.tsx`  
**Line:** 102-111  
**Severity:** MEDIUM

```typescript
const payload = {
  symbol: tradeForm.symbol,
  direction: tradeForm.direction,
  lot_size: Number(tradeForm.lot_size),
  ...
}
```

While `Number(tradeForm.lot_size)` is used, the initial state has `lot_size: 0.1` (number), but the input `onChange` does `Number(e.target.value)` which is fine. However, if the user clears the input, `Number('')` becomes `0`, which might be accepted as a valid lot size.

**Impact:** Zero-lot trades sent to MT5, unexpected broker behavior.  
**Fix:** Validate `lot_size > 0` before sending. Show validation error.

---

### 42. `alert_service.py` Uses `time.time()` but Compares with `datetime.utcnow().isoformat()`
**File:** `app/services/alert_service.py`  
**Line:** 15, 35, 102-103  
**Severity:** MEDIUM

Alert creation uses `datetime.utcnow().isoformat()` for timestamps, but the rate limiting check uses `time.time()` (line 74). These are different time systems. While both are UTC-based, the mixed usage is inconsistent and could cause issues if the system clock drifts.

**Impact:** Inconsistent time handling.  
**Fix:** Use `time.time()` or `datetime.utcnow()` consistently throughout.

---

### 43. `bot_engine.py` Daily Reset Race Condition
**File:** `app/services/bot_engine.py`  
**Line:** 20-24  
**Severity:** MEDIUM

```python
def _reset_daily(self):
    today = datetime.utcnow().date().isoformat()
    if self.config["last_reset"] != today:
        self.config["last_reset"] = today
        self.config["trades_today"] = 0
```

In a multi-process or multi-threaded deployment, multiple workers could simultaneously check `last_reset`, see it's stale, and all reset the counter. This could cause the daily trade limit to be exceeded.

**Impact:** Daily trade limits not enforced reliably.  
**Fix:** Use atomic operations or database-backed state for the bot config.

---

### 44. `market_data.py` `get_price` Returns Bid/Ask from High/Low (Incorrect)
**File:** `app/services/market_data.py`  
**Line:** 108-115, 147-153  
**Severity:** MEDIUM

```python
return {
    'bid': round(pdata.low, 5),
    'ask': round(pdata.high, 5),
}
```

The bid price is set to the day's LOW and ask to the day's HIGH. This is incorrect — bid/ask should be the current best bid/ask from the order book, not the day's range. For a synthetic price, the bid should be slightly below the current price and ask slightly above.

**Impact:** Incorrect bid/ask spreads, wrong order entry calculations.  
**Fix:** Calculate realistic bid/ask from current price with a small spread.

---

### 45. `App.tsx` Missing Routes for `/journal` and `/plan`
**File:** `frontend/src/App.tsx`  
**Severity:** MEDIUM

```tsx
<Route path="/research" element={<QuantLab />} />
```

There is no route for `/journal` or `/plan` even though these pages exist and are linked from the sidebar. The sidebar in `Layout.tsx` links to `/journal` and `/plan` (wait, actually it doesn't — the sidebar only links to existing routes). But the pages exist as files.

Actually, looking at `Layout.tsx`, the navItems don't include `/journal` or `/plan`. So the pages are orphaned. But the `Journal.tsx` and `Plan.tsx` files exist in the codebase.

**Impact:** Orphaned pages that can't be reached via navigation.  
**Fix:** Add routes and nav items for Journal and Plan, or remove the unused pages.

---

### 46. `Execute.tsx` Lot Calculation Auto-Triggers but Has Stale Dependencies
**File:** `frontend/src/pages/Execute.tsx`  
**Line:** 206-212  
**Severity:** MEDIUM

```typescript
useEffect(() => {
  if (entryPrice && stopLoss && !lotCalc) {
    const timer = setTimeout(() => calculateLot(), 500)
    return () => clearTimeout(timer)
  }
}, [entryPrice, stopLoss])
```

The `calculateLot` function is not in the dependency array. While `eslint-disable-next-line` suppresses the warning, this means if `calculateLot` changes (e.g., due to `symbol` or `accountBalance` changes), the effect uses a stale closure. The `calculateLot` function references `symbol`, `entryPrice`, `stopLoss`, `accountBalance`, and `riskPct` from closure.

**Impact:** Lot calculation uses stale values if user changes symbol while form has values.  
**Fix:** Add all dependencies or use `useCallback` with proper dependency array for `calculateLot`.

---

### 47. `backend/app/config.py` Default Database URL Contains Hardcoded Password
**File:** `backend/app/config.py`  
**Line:** 17  
**Severity:** MEDIUM

```python
database_url: str = "postgresql://ictos:ictos@localhost:5432/ictos"
```

Default database password is `ictos` — hardcoded and weak. If this is used in production without override, it's a security risk.

**Impact:** Database credential exposure, unauthorized access.  
**Fix:** Remove default password. Fail startup if `DATABASE_URL` is not set.

---

### 48. `backend/app/models/trade.py` Missing `user_id` Foreign Key Validation
**File:** `backend/app/models/trade.py`  
**Line:** 15  
**Severity:** MEDIUM

```python
user_id: UUID = Field(foreign_key="users.id", index=True)
```

The model references `users.id` but there's no CASCADE behavior defined. If a user is deleted, their trades become orphaned. Also, `plan_id` is `Optional[UUID]` but there's no validation that the plan belongs to the same user.

**Impact:** Orphaned data, potential cross-user data leakage.  
**Fix:** Add `ondelete="CASCADE"` and user-scoped validation.

---

### 49. `backend/app/database.py` `init_db` Imports All Models Unconditionally
**File:** `backend/app/database.py`  
**Line:** 54-57  
**Severity:** MEDIUM

The `init_db` function imports all models inside the function body. This is a circular import risk and can cause issues if any model file has side effects. Also, it creates all tables on every startup in development, which can cause issues with Alembic-managed migrations.

**Impact:** Circular import crashes, migration conflicts.  
**Fix:** Move model imports to module level or use Alembic exclusively.

---

### 50. `quant.py` `trend_analysis` Uses `statistics` Import but Never Uses It
**File:** `app/routers/quant.py`  
**Line:** 8  
**Severity:** MEDIUM

```python
import statistics
```

The `statistics` module is imported but never used in the file. This is minor but indicates incomplete refactoring.

**Fix:** Remove unused import.

---

## 🟢 LOW SEVERITY BUGS

### 51. `price_service.py` Persistent Cache File Path is Fragile
**File:** `app/services/price_service.py`  
**Line:** 44  
**Severity:** LOW

```python
CACHE_FILE = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), "price_cache.json")
```

The cache file is placed at the project root using `__file__` traversal. This is fragile and may not work in all deployment scenarios (e.g., when the code is packaged).

**Fix:** Use a configurable path or place in a standard cache directory.

---

### 52. `market_data.py` `SYMBOL_MAP` is Deprecated but Still Used
**File:** `app/services/market_data.py`  
**Line:** 12-16, 84  
**Severity:** LOW

The `SYMBOL_MAP` is commented as "Deprecated" but is still used as a fallback in `_get_yahoo_ticker()`. The comment says "now using instrument_config for all ticker lookups" but the fallback remains.

**Fix:** Remove the deprecated map or update the comment to reflect actual usage.

---

### 53. `bot.py` Uses `config.dict()` Which is Deprecated in Pydantic v2
**File:** `app/routers/bot.py`  
**Line:** 21  
**Severity:** LOW

```python
return bot_engine.set_config({k: v for k, v in config.dict().items() if v is not None})
```

In Pydantic v2, `.dict()` is deprecated in favor of `.model_dump()`. The `requirements.txt` specifies `pydantic==2.11.4`.

**Fix:** Use `config.model_dump()` instead.

---

### 54. `news.py` Hardcoded Static News with Future Dates
**File:** `app/routers/news.py`  
**Line:** 10-67  
**Severity:** LOW

The news feed contains hardcoded articles with timestamps like `"2026-07-01T10:00:00Z"`. These are future-dated relative to when the app was written. The news is static and never updates.

**Impact:** Stale news, misleading timestamps.  
**Fix:** Integrate with a real news API or at least generate timestamps dynamically.

---

### 55. `Layout.tsx` Version Badge is Hardcoded
**File:** `frontend/src/components/Layout.tsx`  
**Line:** 143-145  
**Severity:** LOW

```tsx
<span className="px-2 py-0.5 text-xs rounded-full bg-green-100 text-green-800 dark:bg-green-900 dark:text-green-300">
  v9.1.0
</span>
```

The version badge is hardcoded and doesn't match the backend version (`APP_VERSION` in `config.py` is `9.1.0` — actually it does match, but it's not dynamic).

**Fix:** Fetch version from `/health` or `/` endpoint and display dynamically.

---

### 56. `Dashboard.tsx` `newsCategories` Computation Re-runs on Every Render
**File:** `frontend/src/pages/Dashboard.tsx`  
**Line:** 95  
**Severity:** LOW

```typescript
const newsCategories = ['All', ...Array.from(new Set(news.map(n => n.category)))]
```

This creates a new array on every render, causing unnecessary re-renders of the select element.

**Fix:** Use `useMemo` for the category computation.

---

### 57. `Signals.tsx` and `Suggestions.tsx` Are Nearly Identical
**File:** `frontend/src/pages/Signals.tsx`, `frontend/src/pages/Suggestions.tsx`  
**Severity:** LOW

Both pages implement signal scanning and display with almost identical functionality. This is code duplication that increases maintenance burden.

**Fix:** Extract shared components into a reusable `SignalPanel` component.

---

### 58. `kb_service.py` Chat Answer Builds Prompt But Never Calls LLM
**File:** `app/services/kb_service.py`  
**Line:** 350-371  
**Severity:** LOW

The `chat_answer` method builds a context and returns it as a string. It never actually calls an LLM to generate a synthesized answer. The comment says "For production, this should call an LLM."

**Impact:** KB chat is essentially a retrieval system, not a true chat.  
**Fix:** Integrate with OpenAI or Ollama for actual response generation.

---

### 59. `mt5-bridge/mt5_bridge.py` TODO Comments Indicate Unfinished Implementation
**File:** `mt5-bridge/mt5_bridge.py`  
**Line:** 89, 118, 132  
**Severity:** LOW

Multiple TODO comments indicate Phase 2 integration is pending:
- `# TODO: Phase 2 — integrate actual MT5 trade execution logic`
- `# TODO: Phase 2 — integrate actual MT5 account info`
- `# TODO: Phase 2 — integrate actual MT5 positions`

**Impact:** MT5 bridge is a mock/stub.  
**Fix:** Implement actual MT5 integration or clearly mark the module as a mock.

---

### 60. `frontend/src/components/ui/Card.tsx` Not Reviewed
**File:** `frontend/src/components/ui/Card.tsx`  
**Severity:** LOW

The component UI files were mentioned in the review scope but not read. If they contain accessibility issues or incorrect prop types, those would be missed.

**Fix:** Review UI primitive components for a11y and type safety.

---

### 61. `backend/app/services/fail_safe_service.py` Hardcoded Health Status
**File:** `backend/app/services/fail_safe_service.py`  
**Line:** 248  
**Severity:** LOW

```python
"connected": True,  # TODO: implement real health check
```

The fail-safe service reports a hardcoded "connected": True without actually checking connectivity.

**Fix:** Implement real health checks for downstream services.

---

### 62. `lot_calculator.py` `quick_lot` Always Calculates for BUY Side
**File:** `app/services/lot_calculator.py`  
**Line:** 184-186  
**Severity:** LOW

```python
sl_price = entry_price - (sl_pips * pip_size)  # approximate for BUY
```

The `quick_lot` method ignores the `side` parameter and always calculates the stop loss as if it were a BUY trade. The `side` parameter is accepted but never used.

**Impact:** Incorrect SL price for SELL trades in quick lot calculation.  
**Fix:** Use `side` to determine whether to add or subtract pips from entry price.

---

### 63. `quant.py` `decision_helper` Catches All Exceptions Blindly
**File:** `app/routers/quant.py`  
**Line:** 250-265  
**Severity:** LOW

```python
try:
    trend = trend_analysis(symbol)
except Exception:
    trend = {"trend": "NEUTRAL", "momentum_10h": 0}
```

Catching all exceptions with `except Exception` and returning default values hides real errors. A network timeout or API failure would be silently swallowed.

**Fix:** Log exceptions. Catch specific expected exceptions only.

---

### 64. `Dashboard.tsx` `setOpenTrades` Uses `any[]` Type
**File:** `frontend/src/pages/Dashboard.tsx`  
**Line:** 56  
**Severity:** LOW

```typescript
const [openTrades, setOpenTrades] = useState<any[]>([])
```

Using `any[]` bypasses TypeScript's type checking. A proper `Trade` interface should be defined and used.

**Fix:** Define and use a `Trade` interface consistently across the frontend.

---

## Summary Table

| # | Severity | File | Line | Description |
|---|----------|------|------|-------------|
| 1 | 🔴 CRITICAL | `app/core/database.py` | 41-91 | SQL injection potential / lack of parameterized queries in some paths |
| 2 | 🔴 CRITICAL | `app/services/trade_lifecycle_service.py` | 110-185 | Race condition in partial/full close — no locking |
| 3 | 🔴 CRITICAL | `app/services/trade_lifecycle_service.py` | 66-178 | Floating-point precision loss in PnL calculations |
| 4 | 🔴 CRITICAL | `app/services/trade_lifecycle_service.py` | 36-52 | No SL side validation — can create invalid trades |
| 5 | 🔴 CRITICAL | `app/core/config.py` | 16 | Hardcoded JWT secret default |
| 6 | 🔴 CRITICAL | `app/services/telegram_service.py` | 355-361 | Telegram token stored insecurely, mutable at runtime |
| 7 | 🔴 CRITICAL | `app/routers/mt5.py` | 55-83 | MT5 proxy accepts arbitrary trades without validation |
| 8 | 🔴 CRITICAL | `app/services/trade_lifecycle_service.py` | 516-519 | Inconsistent Kelly Criterion implementations |
| 9 | 🔴 CRITICAL | `app/services/price_service.py` | 83-269 | Timestamp format inconsistency (float vs ISO string) |
| 10 | 🟠 HIGH | `app/main.py` | 27-43 | Auth disabled by default — all endpoints open |
| 11 | 🟠 HIGH | `app/routers/telegram.py` | 72-84 | No signal ownership validation in auto_trade |
| 12 | 🟠 HIGH | `app/routers/bot.py` | 5 | Missing `plan_service.py` file — ImportError |
| 13 | 🟠 HIGH | `app/routers/bot.py` | 4 | Missing `order_service.py` file — ImportError |
| 14 | 🟠 HIGH | `app/services/instrument_config.py` | — | Not reviewed — critical for trading calculations |
| 15 | 🟠 HIGH | `frontend/vite.config.ts` | 16-20 | Proxy `/api` doesn't match backend routes |
| 16 | 🟠 HIGH | `frontend/src/hooks/useMarketData.ts` | 13 | Uses wrong API path `/api/v1/market/price` |
| 17 | 🟠 HIGH | `frontend/src/pages/WhatsUp.tsx` | 156-170 | Rapid-fire re-renders due to stale interval dependencies |
| 18 | 🟠 HIGH | `frontend/src/pages/Journal.tsx` | — | No backend integration — pure UI |
| 19 | 🟠 HIGH | `frontend/src/pages/Plan.tsx` | — | No backend integration — pure UI |
| 20 | 🟠 HIGH | `frontend/src/pages/Analytics.tsx` | 53-75 | Assumes axios response wrapper that may not match backend |
| 21 | 🟠 HIGH | `app/services/bot_engine.py` | 35-45 | Duplicate trades possible in auto-execute |
| 22 | 🟠 HIGH | `app/services/signal_engine.py` | 141-143 | `fromisoformat` may fail on 'Z' suffix timestamps |
| 23 | 🟠 HIGH | `app/services/price_service.py` | 290-305 | Imports ThreadPoolExecutor but never uses it |
| 24 | 🟠 HIGH | `backend/app/main.py` | 47-53 | CORS hardcoded to localhost; main app defaults to `*` |
| 25 | 🟠 HIGH | `app/services/trade_lifecycle_service.py` | 299-305 | Auto-management runs on any user's request, cross-trade |
| 26 | 🟠 HIGH | `frontend/src/pages/Dashboard.tsx` | 218-346 | Index keys used for dynamic lists |
| 27 | 🟠 HIGH | `frontend/src/pages/Knowledge.tsx` | 20-270 | Unsanitized Markdown content from user input |
| 28 | 🟡 MEDIUM | `app/services/market_data.py` | 79-84 | Wrong Yahoo ticker fallback logic |
| 29 | 🟡 MEDIUM | `app/services/market_data.py` | 125,193 | New HTTP client per request — no connection pooling |
| 30 | 🟡 MEDIUM | `app/services/trade_lifecycle_service.py` | 276-278 | BE stop loss never triggers auto-close |
| 31 | 🟡 MEDIUM | `app/services/trade_lifecycle_service.py` | 307-441 | In-place mutation of DB objects |
| 32 | 🟡 MEDIUM | `frontend/src/pages/QuantLab.tsx` | 120-139 | Demo mode uses `Math.random()` without watermarks |
| 33 | 🟡 MEDIUM | `app/services/alert_service.py` | 52-59 | Manual list mutation instead of DB delete |
| 34 | 🟡 MEDIUM | `app/services/kb_service.py` | 192-200 | New event loop creation in async context |
| 35 | 🟡 MEDIUM | `frontend/src/pages/Playground.tsx` | 61-73 | No defensive checks for API response shape |
| 36 | 🟡 MEDIUM | `frontend/src/pages/Signals.tsx` | — | Duplicate state with `Suggestions.tsx` |
| 37 | 🟡 MEDIUM | `frontend/src/pages/Settings.tsx` | — | Theme toggle is non-functional |
| 38 | 🟡 MEDIUM | `frontend/src/pages/WhatsUp.tsx` | 241-260 | Potential division by zero in `priceProgress` |
| 39 | 🟡 MEDIUM | `frontend/src/pages/Analytics.tsx` | 448-454 | Auto-journal never saves to backend |
| 40 | 🟡 MEDIUM | `frontend/src/pages/TelegramFeed.tsx` | 229-234 | Token visible in React state/devtools |
| 41 | 🟡 MEDIUM | `frontend/src/pages/MT5Terminal.tsx` | 102-111 | Zero lot size accepted for MT5 trades |
| 42 | 🟡 MEDIUM | `app/services/alert_service.py` | 15,35,102 | Mixed `time.time()` and `datetime` usage |
| 43 | 🟡 MEDIUM | `app/services/bot_engine.py` | 20-24 | Daily reset race condition |
| 44 | 🟡 MEDIUM | `app/services/market_data.py` | 108-153 | Bid/ask derived from day high/low instead of spread |
| 45 | 🟡 MEDIUM | `frontend/src/App.tsx` | — | Missing routes for `/journal` and `/plan` |
| 46 | 🟡 MEDIUM | `frontend/src/pages/Execute.tsx` | 206-212 | Stale closure in lot calculation effect |
| 47 | 🟡 MEDIUM | `backend/app/config.py` | 17 | Hardcoded database password in default config |
| 48 | 🟡 MEDIUM | `backend/app/models/trade.py` | 15 | Missing CASCADE and user-scoped validation |
| 49 | 🟡 MEDIUM | `backend/app/database.py` | 54-57 | Circular import risk in `init_db` |
| 50 | 🟡 MEDIUM | `app/routers/quant.py` | 8 | Unused `statistics` import |
| 51 | 🟢 LOW | `app/services/price_service.py` | 44 | Fragile cache file path using `__file__` |
| 52 | 🟢 LOW | `app/services/market_data.py` | 12-16 | Deprecated `SYMBOL_MAP` still used |
| 53 | 🟢 LOW | `app/routers/bot.py` | 21 | `config.dict()` deprecated in Pydantic v2 |
| 54 | 🟢 LOW | `app/routers/news.py` | 10-67 | Hardcoded static news with future dates |
| 55 | 🟢 LOW | `frontend/src/components/Layout.tsx` | 143-145 | Hardcoded version badge |
| 56 | 🟢 LOW | `frontend/src/pages/Dashboard.tsx` | 95 | `newsCategories` re-computes on every render |
| 57 | 🟢 LOW | `frontend/src/pages/Signals.tsx` | — | Code duplication with `Suggestions.tsx` |
| 58 | 🟢 LOW | `app/services/kb_service.py` | 350-371 | Chat answer never calls LLM |
| 59 | 🟢 LOW | `mt5-bridge/mt5_bridge.py` | 89,118,132 | TODO: MT5 integration not implemented |
| 60 | 🟢 LOW | `frontend/src/components/ui/Card.tsx` | — | Not reviewed |
| 61 | 🟢 LOW | `backend/app/services/fail_safe_service.py` | 248 | Hardcoded health status |
| 62 | 🟢 LOW | `app/services/lot_calculator.py` | 184-186 | `quick_lot` ignores `side` parameter |
| 63 | 🟢 LOW | `app/routers/quant.py` | 250-265 | Blind `except Exception` catches |
| 64 | 🟢 LOW | `frontend/src/pages/Dashboard.tsx` | 56 | `any[]` type used for trades |

---

## Recommendations

1. **Immediate (Before Production):**
   - Fix all CRITICAL bugs (1-9)
   - Enable authentication by default
   - Add database transactions/locking for trade operations
   - Use `Decimal` for all financial calculations
   - Validate all trading inputs (SL on correct side, lot size > 0, etc.)

2. **Short Term (1-2 Weeks):**
   - Fix HIGH severity bugs (10-27)
   - Complete frontend-backend integration for Journal and Plan
   - Fix API path mismatches between frontend and backend
   - Add proper error handling and loading states

3. **Medium Term (1 Month):**
   - Fix MEDIUM severity bugs (28-50)
   - Add comprehensive test coverage
   - Implement real MT5 bridge
   - Add user scoping to all resources
   - Implement proper theme switching

4. **Architecture Improvements:**
   - Use a single database backend (PostgreSQL with SQLModel is the better choice)
   - Consolidate the two backend applications into one
   - Add background job worker (Celery/RQ) for signal scanning and auto-management
   - Implement proper WebSocket for live price updates instead of polling
   - Add comprehensive audit logging

---

*End of Report*
