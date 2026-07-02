# ICT Trading OS Product Direction and Batch Tracker

Last updated: 2026-07-02

## Direction

ICT Trading OS should become a trading decision operating system, not a generic chart dashboard. The useful product center is:

1. Learn the trader's model from high-signal ICT sources.
2. Convert that model into deterministic checklists, risk rules, and journal tags.
3. Help the trader plan, execute, review, and improve without letting AI directly fire trades.
4. Keep every recommendation traceable to source evidence, current market data, and account risk constraints.

The immediate north star is a private, source-backed "coach and tracker" for one trader. Automation comes later, after the journal, risk ledger, and trade lifecycle are reliable.

## Current Usefulness Progress

| Area | Progress | Status | Next usefulness jump |
| --- | ---: | --- | --- |
| Deployment and CI/CD | 80% | Vercel production and dev previews are live; GitHub CI runs backend/frontend checks. | Add PR GrepLoop, preview smoke checks, and merge discipline. |
| Durable storage | 70% | Production Supabase Postgres is connected with pgvector in production schema. | Complete migrations for every runtime table and remove stale SQLite assumptions. |
| Knowledge base | 55% | YouTube transcript ingestion, chunking, source list, search, and pgvector path exist. | Make ingestion asynchronous, cited, repeatable, and standards-driven. |
| Trading planner | 45% | Plan APIs and UI exist. | Connect plans to daily bias, source-backed concepts, and execution checklists. |
| Execution and trade lifecycle | 35% | Trade/order services exist, but review found safety gaps around validation, locking, and precision. | Fix trade safety before any automation. |
| Journal and analytics tracker | 40% | Analytics routes and UI exist. | Persist journal decisions, link screenshots/entries to plans and outcomes. |
| ML/agent pipeline | 25% | Basic heuristic video analysis and vector retrieval exist. | Standardize pipeline contracts, eval sets, retrieval metrics, and hallucination checks. |
| Security and collaborator readiness | 35% | Private repo and env separation are set up. | Enable real auth, secret rotation process, user scoping, and role-based collaborator access. |

## Rizz Run Notes

`rizz` was run locally on 2026-07-02. Initial scan understood 5,000 files, 39 flows, and 2 components, but it also scanned local `.venv` and cache artifacts. The repo now includes `.rizzignore` so future rizz runs focus on source, docs, config, tests, and operational files.

After adding `.rizzignore`, the refreshed scan understood 209 files, 12 components, 43 flows, and 11 commands. That is the cleaner baseline for future agent dispatch.

Use this order before each agent batch:

1. `rizz`
2. Read `.rizz/brain/latest.json`
3. Run the relevant tests
4. Make one focused branch
5. Run `bash scripts/grep-loop.sh origin/dev`
6. Open PR into `dev`

## YouTube KB Dissection

Source URL: `https://youtu.be/pq9WuZ9q4Bg?si=KvDjw_nl_w_zBO1z`

Local transcript extraction succeeded from auto-generated captions:

| Metric | Value |
| --- | ---: |
| Video ID | `pq9WuZ9q4Bg` |
| Transcript words | 8,554 |
| Transcript segments | 1,284 |
| Inversion fair value gap mentions | 13 |
| Fair value gap mentions | 16 |
| Liquidity mentions | 25 |
| Consequent encroachment mentions | 23 |
| Macro window mentions | 12 |
| Stop/risk management mentions | 13 |
| Daily bias/block mentions | 43 |

Production KB status:

- The source was seeded into the live production KB through the manual source endpoint.
- Production status shows 1 source and 58 chunks.
- Production auto-transcribe could not fetch captions directly from the Vercel runtime for this URL, so Batch 3 must add a fallback path for serverless caption failures.
- Vector search returns relevant chunks for IFVG/consequent-encroachment queries.
- RAG answer quality is still weak because it retrieves passages but does not synthesize a clean setup/trigger/invalidation answer yet.

The video is useful as a trade-management and model-execution source. The main concepts to normalize into the KB are:

- Daily draw and daily block context before the entry.
- Macro window execution, especially the 9:50 to 10:10 window.
- Inversion fair value gap behavior as a validation/invalidation object.
- Consequent encroachment of wicks as a management level.
- Sell-side liquidity targeting and body-close confirmation.
- Risk reduction, stop movement, and partial profit management.
- Screenshot logging as evidence that the trade was one managed idea, not hindsight selection.

Product implication: the KB should not just store transcripts. It should extract a reusable trading playbook:

- Setup: market, session, bias, liquidity target, POI.
- Trigger: displacement, IFVG, body behavior, CE respect.
- Invalidation: body closes back into the wrong side of the IFVG or CE level.
- Management: partials, stop movement, target liquidity, screenshot evidence.
- Journal tags: `ifvg`, `consequent_encroachment`, `sellside_liquidity`, `macro_window`, `partial_management`.

## Batch List

### Batch 0: Repo Hygiene and PR GrepLoop

Goal: make every future PR reviewable and safe to merge to `dev`.

Deliverables:

- `.rizzignore` for cleaner project intelligence.
- PR GrepLoop workflow for all PRs into `dev` or `main`.
- PR template with risk, scope, and verification sections.
- Batch tracker committed as a durable planning artifact.

Acceptance:

- `bash scripts/grep-loop.sh origin/dev` runs locally.
- GitHub Actions shows CI and PR GrepLoop on new PRs.

### Batch 1: Production Safety Gate

Goal: make the live app private and prevent unsafe trading actions.

Deliverables:

- Enable auth by default outside local dev.
- Remove default production secrets and fail startup when required secrets are absent.
- Lock down destructive endpoints: orders, MT5, Telegram config, settings, trades.
- Add rate limiting or idempotency for execution-like endpoints.

Acceptance:

- Public unauthenticated requests cannot mutate state.
- Read-only health/status remains available.
- Tests cover auth on destructive routes.

### Batch 2: Trade Ledger Correctness

Goal: make trades, orders, PnL, and risk ledger reliable enough for real journaling.

Deliverables:

- Use `Decimal` for money, R, lot, and PnL calculations.
- Add side-aware stop-loss and take-profit validation.
- Add locking or optimistic concurrency for partial/full close.
- Standardize timestamps to UTC ISO strings.
- Align Kelly/risk calculations into one tested implementation.

Acceptance:

- Edge-case tests cover buy/sell validation, partial close races, BE stop logic, and rounding.
- Analytics and trade lifecycle agree on PnL and Kelly outputs.

### Batch 3: KB Ingestion Standard

Goal: make YouTube and manual transcript ingestion repeatable, cited, and evaluable.

Deliverables:

- Async ingestion jobs with durable job status.
- Transcript normalization with segment timestamps and source metadata.
- Chunking standard: 350 to 512 tokens, 50 to 80 token overlap, source and timestamp citation on every chunk.
- Idempotent upsert by canonical URL/video ID and content hash.
- Store extraction artifacts: concepts, playbook rules, uncertainty, and evidence spans.

Acceptance:

- Ingesting the same YouTube URL twice updates one source, not duplicates.
- Search result includes source URL, title, timestamp/span, chunk score, and concept tags.
- The `pq9WuZ9q4Bg` source can answer setup, trigger, invalidation, and management questions with citations.

### Batch 4: Retrieval and ML Pipeline

Goal: make RAG measurable instead of vibes.

Deliverables:

- Embedding provider abstraction with pgvector production path and deterministic local fallback.
- Retrieval eval set seeded from the YouTube source and future ICT sources.
- Metrics: recall@k, citation coverage, empty-answer rate, source freshness, ingestion latency.
- Answer contract: answer, citations, confidence, missing context, no-trade safety disclaimer when needed.
- Hallucination guard that refuses claims not supported by retrieved chunks.

Acceptance:

- CI can run a small offline retrieval regression suite.
- RAG answers cite chunks and refuse unsupported trade instructions.

### Batch 5: Planner and Checklist Integration

Goal: turn KB concepts into actual planning workflow.

Deliverables:

- Daily bias form connected to source-backed concept tags.
- Trade plan checklist generated from setup model: bias, liquidity, POI, trigger, invalidation, risk, target.
- Screenshot/evidence attachment model.
- Plan-to-trade link so execution can inherit risk and invalidation.

Acceptance:

- A plan can be created from a KB playbook and later linked to a trade and journal entry.

### Batch 6: Journal Tracker and Analytics Loop

Goal: make the product useful every day after trades close.

Deliverables:

- Persist journal entries to backend.
- Link journal entries to plan, trade, screenshots, KB concepts, and outcome.
- Analytics by setup, session, symbol, risk multiple, and rule compliance.
- "What to improve next" report based on journal evidence, not generic advice.

Acceptance:

- User can review a day and see expectancy, mistakes, screenshots, tags, and next practice focus.

### Batch 7: Market and Signal Reliability

Goal: make live data and signal suggestions dependable.

Deliverables:

- Normalize market data timestamps and provider fallback.
- Add stale-data warnings everywhere prices are shown.
- Separate demo/mock data from live data with visible state.
- Add websocket or polling discipline with explicit freshness.

Acceptance:

- UI never presents stale or demo prices as live.
- Signal suggestions include freshness and data-source provenance.

### Batch 8: MT5 and Telegram Hardening

Goal: make execution-adjacent integrations safe enough to turn on deliberately.

Deliverables:

- MT5 command schema with symbol whitelist, lot caps, risk caps, and approval token.
- Telegram token is write-only and never echoed to frontend state.
- Duplicate signal prevention and audit log for every execution intent.
- Manual approval required before bridge execution.

Acceptance:

- No API path can submit arbitrary MT5 commands without validation and audit.

### Batch 9: UX Polish and Operating Cadence

Goal: make the app feel like a focused operating cockpit.

Deliverables:

- Remove duplicate routes and stale pages.
- Complete loading, empty, and error states.
- Add mobile-safe layouts only where useful.
- Add release notes, backup/restore notes, and collaborator runbook.

Acceptance:

- A friend can clone, run, open PRs, preview changes, and understand the operating flow without using the owner account.

## Agent Dispatch Map

When ready to dispatch agents, use this map:

| Agent | Owns | First batch |
| --- | --- | --- |
| Product PM | scope, acceptance, user usefulness | Batch 1 and tracker updates |
| Backend safety | auth, trade lifecycle, DB correctness | Batch 1, Batch 2 |
| KB/ML engineer | ingestion, embeddings, retrieval evals | Batch 3, Batch 4 |
| Frontend engineer | planner, journal, UX states | Batch 5, Batch 6, Batch 9 |
| DevOps/QA | CI, Vercel, GrepLoop, smoke checks | Batch 0, then all PR gates |
| Integration engineer | MT5, Telegram, market data | Batch 7, Batch 8 |

## Merge Policy

- Base branch for work PRs: `dev`.
- Production branch: `main`.
- Merge to `main` only after `dev` is live, CI is green, PR GrepLoop is clean, and production smoke checks pass.
- Friend/source repo remains fetch-only and untouched.
