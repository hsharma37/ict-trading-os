# ICT Trading OS — Feature Assessment & Trust Report

> Last updated: 2026-07-16. This is an **honest, real-money-grade** assessment of every
> feature: what works, how much you can trust it, and what still needs improvement.
> Trust ratings are deliberately conservative — a trading tool should under-promise.

## How to read the trust ratings

| Rating | Meaning |
|---|---|
| 🟢 **Trust** | Correct and verified; rely on it (still cross-check money-moving actions in MT5). |
| 🟡 **Trust with care** | Works, but it's a model/heuristic or has caveats you must understand. |
| 🟠 **Fragile / context-only** | Functions, but don't bet on it — infra risk or unproven signal quality. |
| 🔴 **Do not rely on** | Present but not trustworthy for decisions yet. |

**One rule above all:** MetaTrader 5 is the source of truth. This app is a decision & analytics
layer on top of it. Trust it, verify against the terminal.

---

## Summary table

| Area | Status | Trust | One-line verdict |
|---|---|---|---|
| Order execution (MT5) | Shipped | 🟢/🟠 | Correct & self-verifying; infra (tunnel) is the weak link |
| Position management | Shipped | 🟢 | Close/modify/partial are reliable; no double-fire |
| Trade tracking / journal | Shipped | 🟢 | Mirrors the MT5 deal ledger exactly |
| Risk & R calibration | Shipped | 🟡 | Deterministic & editable, but a proxy not measured risk |
| Analytics (per-lot stats) | Shipped | 🟡 | Math is right; normalized stats are a modelling choice |
| Data integrity / provenance | Shipped | 🟢 | Refuses/flag fabricated data — the big trust win |
| Research (technical analysis) | Shipped | 🟡 | Real data now; levels are simple S/R + SMAs |
| Signals (ICT + intelligence) | Shipped | 🟠 | No proven edge at 2R; context, not a trigger |
| Backtest / MC / sweep / honest / forward | Shipped | 🟡 | Rigorous research loop; single-TF, no costs modelled |
| Telegram ingestion | Shipped | 🟡 | Safe now (won't auto-trade a guessed stop); parsing is basic |
| News + sentiment | Shipped | 🟠 | Real headlines; sentiment is a keyword heuristic |
| Knowledge base (chat) | Shipped | 🟡 | Honest (cites/refuses); answers are quoted chunks, not synthesised |
| Infrastructure (bridge/tunnel/deploy) | Shipped | 🟠 | Single-operator & fragile; fails safe but needs hardening |

---

## Feature-by-feature detail

### 1. Order execution — 🟢 correctness / 🟠 infrastructure
**Works:** Market + pending orders go to a real `order_send` on the broker via the bridge, with
server-side guardrails (symbol allow-list, max lot, side-aware SL/TP), auto filling-mode
selection (FOK/IOC/RETURN), and lot auto-sizing.
**Trust:** The scary bugs are fixed and deployed — the double/triple-order fan-out (scale-out is
now opt-in), the timeout-retry double-send, and XAUUSD oversizing. Every market order does an
**independent read-back from MT5** and shows "Confirmed in MT5: ticket #… @ price," or warns you
to check the terminal. Placement is **hard-blocked when the bridge is offline or data is stale.**
**Improvements needed:** (a) no client-side idempotency key — an ambiguous network failure is
handled by *not* retrying and asking you to verify, which is safe but manual; (b) the bridge tunnel
is the real risk (see §13); (c) no partial-fill/slippage surfacing beyond broker retcodes.

### 2. Position management (close / modify / partial) — 🟢
**Works & trustworthy.** The retry-on-timeout double-execution bug is fixed (non-idempotent ops
no longer retry). Broker rejections surface as real errors. Available identically on Execute and
What's Up via one shared hook.
**Improvements:** surface partial-fill details; add a confirmation read-back to close/partial like
the one on entries.

### 3. Trade tracking / journal — 🟢
**Works well.** Sourced from MT5's own deal ledger (ground truth), mirrored into a durable store,
deduped by unique deal ticket, with the broker-server-time window bug fixed so recent closes
aren't dropped. Balance and closed trades reconcile to the terminal.
**Improvements:** an alert when the app's journal and the terminal disagree would close the loop.

### 4. Risk & R calibration — 🟡
**Works:** R and money-at-risk come from your editable per-instrument lot→$ calibration
(Settings), so R = P&L ÷ your risk. Deterministic, no more garbage values.
**Trust with care:** this is a *calibration/proxy* — it assumes your standard sizing. It is not the
exact risk of a specific trade unless that trade used your standard lot. When an actual stop-loss
is known it's used; otherwise the calibration fills in.
**Improvements:** prefer the real per-trade SL distance whenever it's captured; fall back to
calibration only when it isn't.

### 5. Analytics (per-standard-lot stats) — 🟡
**Works:** avg win/loss, expectancy, best/worst are normalized to your standard lot so big-lot
trades don't dominate; totals stay raw money. Math verified by tests.
**Trust with care:** "normalized" is a modelling choice — make sure you read the per-lot figures as
per-standard-lot, not raw account P&L (the headline balance is raw).

### 6. Data integrity / provenance — 🟢 (the biggest trust improvement)
**Works:** fabricated fallback candles are now flagged; research **refuses** ("DATA UNAVAILABLE —
simulated") rather than showing invented levels; signals return a NEUTRAL "unavailable" instead of
a confident call on noise; heuristics are labelled as heuristics.
**Improvement:** the data-quality **badge UI** currently lives on an orphan page (`Research.tsx`),
not the live research page (`QuantLab`). The backend refusal works everywhere; the *visual badge*
needs porting to QuantLab (and `Research.tsx` deleted). See §Known gaps.

### 7. Research / technical analysis — 🟡
**Works:** live quote + candles → trend, ATR, support/resistance, SMA20/50, correlation. The
candle-window bug (`period=` vs `range=`) is fixed, so SMAs and levels actually populate now.
**Trust with care:** the levels are **simple** (SMA + swing-based S/R), not institutional-grade
zones. Good for orientation, not precise entries.
**Improvements:** richer level logic; surface the data-quality badge here (see §6).

### 8. Signals (ICT engine + news-fusion intelligence) — 🟠 context-only
**Works mechanically** and the honest bugs are fixed (multi-timeframe alignment now really checks
alignment; bias no longer depends on a pattern type nothing emits).
**Trust:** **Do not treat as a profit trigger.** The backtest is blunt: at a 2R target the signal
wins ~32% → no edge. It only turns positive at ~3R with session/trend filters, and even then
modestly (see §9). The news-fusion "confidence" is a hand-tuned heuristic (labelled as such); news
sentiment is a keyword tally (labelled `keyword-polarity`), not an NLP model.
**Improvements:** (a) treat signals as a **watchlist/context**, not auto-execution; (b) a real
sentiment model; (c) backtest the *exact* live multi-TF signal (the backtester is single-TF).

### 9. Backtest / Monte Carlo / sweep / honest test / forward test — 🟡
**Works & tested (238 tests).** A genuine research loop:
- **Backtest** — walk-forward, no look-ahead, limit-fill model.
- **Monte Carlo** — bootstraps outcomes → percentile returns, probability of loss, risk of ruin.
- **Parameter sweep** — target-R × session × trend, ranked, with an out-of-sample column.
- **Honest test** — picks the best config on the first 60%, reports only the untouched 40%.
- **Live paper-forward test** — locks a config and counts only signals on *future* candles.

**Findings it produced (real):** 2R = no edge; **3R + trend/killzone filters** turns positive and
*held out-of-sample* on GBPUSD (+0.22R test) and EURUSD (+0.08R), but was inconclusive on XAUUSD
(curve-fit). So there is a *candidate* edge, not a proven one.
**Trust with care — caveats baked into the UI:** single timeframe (not the live 3-TF stack),
**no spread/commission/slippage**, limit-fill assumption, conservative "stop-first" on ambiguous
bars. Treat backtest expectancy as an **optimistic ceiling**.
**Improvements:** model spread+commission (this alone may erase the thin edge); multi-timeframe
replay; let the forward test run for weeks before trusting; more instruments/timeframes.

### 10. Telegram signal ingestion — 🟡
**Works & now safe:** posts parse into signals; **auto-trade refuses when the stop-loss was
inferred** from stray numbers (a real prior danger). "Confidence" was renamed to what it actually
is — parse **completeness**. Unnecessary posts can be discarded/kept.
**Trust with care:** the parser is regex-based; it can still misread oddly formatted posts —
review before acting. Chart-image analysis is not implemented (images are stored, not read).
**Improvements:** more robust parsing; optional LLM/vision read of chart images.

### 11. News + sentiment — 🟠
**Works:** real forex/gold headlines are fetched, deduped, tagged to instruments, with an impact
tier (now including a real "low"). 
**Trust:** low for *interpretation* — impact and sentiment are keyword heuristics (no negation,
no NLP), honestly labelled. Fine as a "what's happening" feed; don't trade the sentiment score.
**Improvements:** a real sentiment/NLP model; higher-quality sources.

### 12. Knowledge base / chat — 🟡
**Works and is the most honest AI surface:** it retrieves real KB chunks, **cites sources**, and
**refuses** when it has no supporting context ("I don't have enough cited context…").
**Trust with care:** the "answer" is currently the **quoted chunk text**, not an LLM synthesis
(the code notes this). So it's accurate-but-literal. A richer RAG tree exists under `backend/`
but is **dead code** — the shipped app never uses it.
**Improvements:** wire a real LLM for synthesis on top of the (good) retrieval+refusal layer;
delete or integrate the dead `backend/` engine.

### 13. Infrastructure (bridge / tunnel / deploy / auth) — 🟠 fragile but fails safe
**Reality:** execution depends on a **single Windows machine** running the MT5 terminal + a Flask
bridge, exposed over a **Cloudflare quick tunnel whose URL changes on every restart**. Restarts
are manual. There is no proactive alert when the bridge drops — though the app now **blocks orders
and shows a red banner** when it can't reach a live, fresh bridge (fails safe).
**Improvements (highest priority for real money):**
1. **Persistent named tunnel** so the URL stops changing.
2. **Bridge supervisor/auto-restart** (Task Scheduler / NSSM) + reconnect.
3. **Proactive "bridge down" alert** (Telegram/email), not just in-app gating.
4. Deploy hygiene: the Python version is pinned to 3.12 (Vercel builder was resolving 3.14 and
   failing); keep it pinned.

---

## Known gaps / tech debt (cross-cutting)

- **Orphan page:** `frontend/src/pages/Research.tsx` is **not routed** (the Research nav renders
  `QuantLab`). Some data-quality badge UI landed there and isn't visible. Fix: port the badge into
  QuantLab and delete `Research.tsx`.
- **Dead backend:** the `backend/` RAG/vector tree is not used by the Vercel app. Delete or wire in.
- **Heuristics vs models:** signal confidence and news sentiment are heuristics (now labelled).
  They are not backtested-to-a-hit-rate models.
- **Backtest realism:** no spread/commission/slippage; single timeframe. Edges are optimistic.
- **Repo hygiene:** recurring "stranded commit" risk when PRs merge mid-stack — always merge the
  latest PR promptly so `main` matches production.

---

## Bottom line: can you trust it with real money?

- **For execution and tracking — yes, with discipline.** Orders are real and self-verifying;
  tracking mirrors the broker. Start with **micro lots**, keep the MT5 terminal open, and
  reconcile for a couple of weeks. The app now refuses to act blind and confirms every fill.
- **For the signal as an edge — no, not yet.** Backtesting shows at best a thin, filter-dependent
  edge that hasn't been proven live. Use signals as **context**, run the **forward test** for
  weeks, and only then consider trading a validated config small.
- **Biggest risk is infrastructure, not code.** Harden the tunnel/bridge before scaling size.

## Priority improvement roadmap

1. **Persistent tunnel + bridge auto-restart + down-alert** (infra reliability). *P0*
2. **Model spread/commission in the backtest** — confirm whether the 3R edge survives costs. *P0*
3. **Port data-quality badges to QuantLab; delete orphan `Research.tsx` + dead `backend/`.** *P1*
4. **Prefer real per-trade SL for risk/R** when captured; calibration as fallback. *P1*
5. **Multi-timeframe backtest** of the exact live signal. *P2*
6. **Real sentiment/NLP model** (replace keyword tally); optional LLM synthesis for KB chat. *P2*
7. **Chart-image reading** for Telegram signals. *P3*
