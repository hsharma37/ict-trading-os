# ICT Trading OS — Architecture & User Guide

> **Version:** 9.1.0 | **Last Updated:** July 2026
>
> *A complete trading command center built for the modern trader — powered by the ICT methodology, real-time market data, and AI-driven insights.*

---

## Table of Contents

1. [What Is This Thing? (For Non-Traders)](#1-what-is-this-thing-for-non-traders)
2. [The Big Picture: System Architecture](#2-the-big-picture-system-architecture)
3. [ICT Methodology: The Philosophy Behind the Code](#3-ict-methodology-the-philosophy-behind-the-code)
4. [Feature Deep Dive](#4-feature-deep-dive)
   - 4.1 [Dashboard](#41-dashboard)
   - 4.2 [MT5 Terminal](#42-mt5-terminal)
   - 4.3 [Execute (Trade Entry)](#43-execute-trade-entry)
   - 4.4 [Analytics](#44-analytics)
   - 4.5 [Research](#45-research)
   - 4.6 [Signals](#46-signals)
   - 4.7 [Telegram Feed](#47-telegram-feed)
   - 4.8 [Knowledge Base](#48-knowledge-base)
   - 4.9 [Library](#49-library)
   - 4.10 [What's Up](#410-whats-up)
   - 4.11 [Settings](#411-settings)
5. [Data Flow: The Life of a Trade](#5-data-flow-the-life-of-a-trade)
6. [Technology Stack](#6-technology-stack)
7. [Database Design](#7-database-design)
8. [API Architecture](#8-api-architecture)
9. [Screenshots & UI Walkthrough](#9-screenshots--ui-walkthrough)
10. [Glossary of Trading Terms](#10-glossary-of-trading-terms)

---

## 1. What Is This Thing? (For Non-Traders)

Imagine you're playing a complex strategy video game, but instead of battling dragons, you're navigating the global financial markets. The **ICT Trading OS** is your heads-up display (HUD) — a single-screen command center that tells you:

- **What's happening right now** in markets (prices, news, trends)
- **What the smart money is doing** (pattern detection, liquidity sweeps)
- **When to make your move** (trade signals, entry zones)
- **How well you're performing** (win rate, profit/loss, equity curve)
- **What you can learn** (AI-powered knowledge base from trading videos)

Think of it as a **fitness tracker for trading** — but instead of counting steps, it counts profits, analyzes your decision-making patterns, and helps you learn from the best traders in the world.

The system is built around a specific trading philosophy called **ICT** (Inner Circle Trader), developed by Michael J. Huddleston. It's like learning to read the "footprints" that big institutional players leave behind in price charts.

---

## 2. The Big Picture: System Architecture

```
┌─────────────────────────────────────────────────────────────────────────────┐
│                        ICT TRADING OS — SYSTEM ARCHITECTURE                    │
├─────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  ┌─────────────────────┐         ┌─────────────────────┐                   │
│  │   REACT + VITE      │◄───────►│   FASTAPI BACKEND   │                   │
│  │   (Frontend UI)     │  HTTP   │   (Python)          │                   │
│  │   Port: 5173        │         │   Port: 8000        │                   │
│  └─────────────────────┘         └─────────────────────┘                   │
│            │                                │                               │
│            │                                │                               │
│            ▼                                ▼                               │
│  ┌─────────────────────────────────────────────────────┐                    │
│  │                  DATA LAYER                          │                    │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────────────┐   │                    │
│  │  │  SQLite  │  │  Vector  │  │  In-Memory Cache │   │                    │
│  │  │  (DB)    │  │  Store   │  │  (Price Data)    │   │                    │
│  │  └──────────┘  └──────────┘  └──────────────────┘   │                    │
│  └─────────────────────────────────────────────────────┘                    │
│                                │                                             │
│  ┌─────────────────────────────┼─────────────────────────────┐               │
│  │                             ▼                             │               │
│  │  ┌──────────┐  ┌──────────┐  ┌──────────┐  ┌──────────┐ │               │
│  │  │  Yahoo   │  │   MT5    │  │ Telegram │  │  AI/LLM  │ │               │
│  │  │ Finance  │  │ Bridge   │  │  Bot API │  │ (Ollama) │ │               │
│  │  │  API     │  │ (Flask)  │  │          │  │          │ │               │
│  │  └──────────┘  └──────────┘  └──────────┘  └──────────┘ │               │
│  └───────────────────────────────────────────────────────────┘               │
│           EXTERNAL SERVICES & INTEGRATIONS                                   │
└─────────────────────────────────────────────────────────────────────────────┘
```

### How It All Connects

The frontend is a **React** single-page application that communicates with a **FastAPI** (Python) backend via REST API calls. The backend is the "brain" — it fetches market data, runs pattern detection algorithms, manages your trade history, and talks to external services like Yahoo Finance, MetaTrader 5, and Telegram.

---

## 3. ICT Methodology: The Philosophy Behind the Code

Before diving into features, let's understand the **ICT methodology** — the "secret sauce" that powers this platform. Think of financial markets as a giant poker game. The big players (banks, institutions, hedge funds) have more information and more money than retail traders like you and me. ICT teaches you to **watch what the big players are doing** and follow their lead.

### Key ICT Concepts Used in the System

| Concept | Simple Analogy | What the System Does |
|---------|---------------|---------------------|
| **Market Structure** | Reading the "trend" of a river | Detects if price is making higher highs (bullish) or lower lows (bearish) |
| **Liquidity** | The "bait" that attracts big players | Finds areas where many traders placed stop-losses — these become targets for institutional moves |
| **Fair Value Gaps (FVG)** | A "missing stair" in a price staircase | Identifies price gaps that the market often returns to fill |
| **Order Blocks (OB)** | The "launch pads" where institutions entered | Finds strong reversal candles that indicate institutional buying/selling |
| **Killzones** | The "rush hour" of trading | Highlights high-probability time windows (London Open, NY Open, etc.) |
| **Premium/Discount** | Shopping "on sale" vs. "full price" | Tells you if current price is cheap (discount) or expensive (premium) relative to recent range |
| **Inducement** | A "fake out" to trap traders | Detects moves designed to trigger retail stops before the real move |

### Multi-Timeframe Analysis

The system analyzes three timeframes simultaneously:

```
┌─────────────────────────────────────────────────────┐
│         MULTI-TIMEFRAME ANALYSIS FLOW               │
├─────────────────────────────────────────────────────┤
│                                                     │
│  ┌──────────────┐                                   │
│  │  HIGHER TF   │  ← 1 Hour Chart                   │
│  │  "The Map"   │    Determines overall bias         │
│  │  (1H)        │    (Bullish or Bearish)            │
│  └──────┬───────┘                                   │
│         │                                           │
│         ▼                                           │
│  ┌──────────────┐                                   │
│  │  INTERMEDIATE│  ← 15 Minute Chart                │
│  │  "The Route" │    Finds structure shifts,         │
│  │  (15M)       │    liquidity sweeps                │
│  └──────┬───────┘                                   │
│         │                                           │
│         ▼                                           │
│  ┌──────────────┐                                   │
│  │  LOWER TF    │  ← 5 Minute Chart                 │
│  │  "The Entry" │    Pinpoints exact entry zones,    │
│  │  (5M)        │    FVGs, and Order Blocks          │
│  └──────────────┘                                   │
│                                                     │
│  RULE: Only trade when ALL THREE agree!             │
└─────────────────────────────────────────────────────┘
```

---

## 4. Feature Deep Dive

### 4.1 Dashboard

**What It Looks Like:** A dark-themed command center with cards showing your account health, live prices, a news ticker, and today's biggest market movers.

**What It Does:** The Dashboard is your morning briefing. It gives you a "one-glance" summary of everything that matters:

- **KPI Cards:** Total trades, win rate, current profit/loss, open positions
- **Live Price Ticker:** Real-time prices for all tracked instruments (EURUSD, Gold, Nasdaq, Bitcoin, etc.)
- **Market News:** Curated headlines from sources like FXStreet, Reuters, and CME Group
- **Market Movers:** Which instruments moved the most today (biggest gainers/losers)
- **Session Clock:** Which trading session is currently active (London, New York, Asian)

**Technical Details:**
- Fetches prices every few seconds via the `/market/prices` endpoint
- News is a curated static feed (can be expanded to RSS/API feeds)
- Market movers are calculated by comparing current prices to previous close

```
┌────────────────────────────────────────────┐
│  DASHBOARD SCREEN (Conceptual)             │
├────────────────────────────────────────────┤
│  ┌────┐ ┌────┐ ┌────┐ ┌────┐              │
│  │Win%│ │ P&L│ │Open│ │Trades│             │
│  │62% │ │+450│ │  3 │ │  47  │             │
│  └────┘ └────┘ └────┘ └────┘              │
│  ──────────────────────────────────────    │
│  EURUSD  1.0845  ▲ +0.12%                │
│  XAUUSD  4021.50 ▲ +1.24%  ← MOVERS      │
│  NQ1!    22500   ▼ -0.45%                │
│  BTCUSD  108500  ▲ +2.10%                │
│  ──────────────────────────────────────    │
│  📰 Gold reclaims $4,000...              │
│  📰 US JOLTS job openings hit 2-year high │
│  📰 NFP report on Thursday...            │
└────────────────────────────────────────────┘
```

---

### 4.2 MT5 Terminal

**What It Looks Like:** A bridge panel showing your MetaTrader 5 account status, open positions, and buttons to execute trades directly on MT5.

**What It Does:** MetaTrader 5 (MT5) is the industry-standard trading platform used by most brokers. The ICT Trading OS doesn't replace MT5 — it **enhances** it. The MT5 Terminal page acts as a remote control:

- **Account Summary:** See your balance, equity, margin, and free margin
- **Open Positions:** View what's currently running on MT5
- **Trade History:** See closed trades from MT5
- **Execute on MT5:** Send trade orders directly from the OS to MT5
- **Manual Price Override:** Push MT5's live broker prices into the OS for more accurate lot calculations

**Technical Details:**
- Communicates with a local Flask bridge running on `localhost:5001`
- The bridge uses Python's `MetaTrader5` library to talk to the MT5 terminal
- Supports sending market orders with stop-loss and take-profit
- Can close positions by ticket ID

```
┌────────────────────────────────────────────┐
│  MT5 TERMINAL BRIDGE                        │
├────────────────────────────────────────────┤
│  Account: $12,450 | Equity: $12,520        │
│  Margin: $2,100 | Free Margin: $10,420     │
│  ──────────────────────────────────────    │
│  Open Positions:                           │
│  ┌────────┬──────┬───────┬────────┐       │
│  │ Symbol │ Size │ Entry │ P&L    │       │
│  │ EURUSD │ 0.5  │ 1.0840│ +$120  │       │
│  │ XAUUSD │ 0.2  │ 3980  │ +$83   │       │
│  └────────┴──────┴───────┴────────┘       │
│  [SYNC PRICES] [CLOSE ALL] [REFRESH]       │
└────────────────────────────────────────────┘
```

---

### 4.3 Execute (Trade Entry)

**What It Looks Like:** A form with dropdowns for instrument, side (Buy/Sell), stop-loss, take-profits, and an auto-calculated lot size. Plus a live P&L preview.

**What It Does:** This is where you "pull the trigger" on a trade. The Execute page is designed to make trade entry fast, accurate, and risk-managed:

- **Auto Lot Calculation:** Enter your account balance, risk percentage, and stop-loss — the system calculates the exact position size so you only risk what you specified (e.g., 1% of account)
- **Live Price Fetch:** If you don't enter an entry price, it uses the current market price
- **Three Take-Profit Levels:** Set TP1, TP2, TP3 for scaling out of positions
- **Quick Lot Calculator:** Calculate lot size by specifying stop-loss in pips instead of price
- **Risk Preview:** See your exact dollar risk before committing

**How Auto Lot Calculation Works:**

```
┌────────────────────────────────────────────┐
│  AUTO LOT CALCULATION FLOW                 │
├────────────────────────────────────────────┤
│                                             │
│  INPUTS:                                    │
│  • Account Balance: $10,000               │
│  • Risk %: 1%                               │
│  • Stop Loss: 50 pips                       │
│  • Symbol: EURUSD                           │
│                                             │
│  CALCULATION:                               │
│  Risk Amount = $10,000 × 1% = $100         │
│  Pip Distance = 50 pips                    │
│  Pip Value (per lot) = $10                 │
│  Total Risk per Lot = 50 × $10 = $500     │
│  Lot Size = $100 / $500 = 0.20 lots       │
│                                             │
│  OUTPUT: Trade with 0.20 lots              │
│          If SL hits → lose exactly $100    │
│          If TP hits → gain based on ratio  │
│                                             │
└────────────────────────────────────────────┘
```

**Technical Details:**
- Uses instrument-specific pip values, contract sizes, and tick values
- Supports Forex (EURUSD), Indices (NQ, ES), Metals (Gold), Crypto (BTC), and Commodities (Oil)
- Leverage is displayed for information but doesn't affect lot sizing (risk-based sizing is used)

---

### 4.4 Analytics

**What It Looks Like:** Charts, stats cards, and tables showing your trading performance over time. Think of it as a "report card" for your trading.

**What It Does:** The Analytics page answers the question: **"Am I actually good at this?"**

- **Summary Stats:** Total trades, win rate, total P&L, expectancy, average R-multiple
- **Equity Curve:** A line chart showing your account balance over time
- **Drawdown Analysis:** How much your account dropped from its peak (and for how long)
- **Session Heatmap:** Which trading sessions (London, NY, Asian) are most profitable for you
- **Monthly Breakdown:** P&L by month with win/loss counts
- **Per-Symbol Performance:** Which instruments you trade best
- **Kelly Criterion:** A mathematical formula suggesting optimal bet sizing based on your edge
- **Win/Loss Streaks:** Your longest winning and losing streaks

**Key Metrics Explained:**

| Metric | What It Means | Good Value |
|--------|--------------|------------|
| **Win Rate** | % of trades that made money | 50-60% is solid |
| **Expectancy** | Average profit per trade | > $0 means you're profitable |
| **R-Multiple** | Profit expressed in "risk units" | > 1.0 means you make more than you risk |
| **Max Drawdown** | Biggest peak-to-trough drop | < 10% is conservative, < 20% acceptable |
| **Kelly Fraction** | Optimal risk % per trade | Usually trade "half Kelly" for safety |

**Technical Details:**
- All metrics are calculated from the SQLite `trades` collection
- Open trades include unrealized P&L using live prices
- R-multiple tracks how many "risk units" each trade returned

---

### 4.5 Research

**What It Looks Like:** A technical analysis lab with charts, indicator values, and market summaries for each instrument. (Note: This page is labeled "Quant Lab" in the UI and "Research" in the navigation.)

**What It Does:** Before you trade, you need to research. The Research page provides:

- **Instrument Analysis:** For each symbol, see trend, volatility, support/resistance levels, SMAs, and sentiment
- **SMA (Simple Moving Average):** 20-period and 50-period moving averages to identify trend direction
- **ATR (Average True Range):** Measures volatility — how much the instrument typically moves per day
- **Support & Resistance:** Key price levels where the market has historically reversed
- **Correlation Matrix:** Shows how closely instruments move together (e.g., EURUSD and GBPUSD often move in tandem)
- **Market Summary:** A bird's-eye view of all instruments — how many are bullish vs. bearish

**Technical Details:**
- SMA crossover: 20 SMA above 50 SMA = Bullish trend
- ATR calculated using Wilder's method over 14 periods
- Support/resistance found by detecting swing highs and lows
- Correlation uses Pearson coefficient over 50 periods of returns

---

### 4.6 Signals

**What It Looks Like:** A list of active trading signals with quality badges (STRONG, MODERATE, WEAK), entry zones, stop-losses, and targets. Plus a "Scan All" button.

**What It Does:** The Signals engine is an **automated analyst** that watches the market 24/7 and tells you when a high-probability setup forms. It:

- Analyzes multiple timeframes simultaneously (1H, 15M, 5M)
- Detects ICT patterns (MSS, FVG, OB, Liquidity sweeps)
- Scores setups on a 6-point confluence scale
- Generates signals only when score ≥ 2 (with STRONG = 5+, MODERATE = 3+, WEAK = 2+)
- Provides entry zone, stop-loss, and three take-profit targets
- Checks for 2:1 reward-to-risk ratio minimum
- Applies cooldown periods after bias flips to avoid choppy signals

**Signal Quality Breakdown:**

```
┌────────────────────────────────────────────┐
│  SIGNAL CONFLUENCE SCORING (Max 6)         │
├────────────────────────────────────────────┤
│  +1  HTF Bias Aligned (1H trend confirmed) │
│  +1  ITF MSS (15M structure shift)         │
│  +1  LTF Entry POI (5M FVG or OB found)   │
│  +1  Liquidity Swept (stops cleared)       │
│  +1  Premium/Discount (price in right zone)│
│  +1  2R Target Viable (reward ≥ 2× risk) │
│                                             │
│  Score ≥ 2 → Signal Generated              │
│  Score ≥ 5 → STRONG Quality                │
│  Score ≥ 3 → MODERATE Quality              │
│  Score ≥ 2 → WEAK Quality                  │
└────────────────────────────────────────────┘
```

**Technical Details:**
- Signals expire after 60 minutes (configurable)
- Bias flip cooldown: 60 seconds after a bias change before new signals
- Session detection: London Open (7-10 UTC), NY AM (12-15 UTC), NY PM (17-21 UTC), etc.

---

### 4.7 Telegram Feed

**What It Looks Like:** A chat-like feed of messages from your subscribed Telegram channels, with parsed signals, acknowledge buttons, and auto-trade controls.

**What It Does:** Many professional traders share signals in private Telegram channels. The Telegram Feed page:

- **Polls Telegram:** Automatically fetches new messages from configured channels
- **Parses Signals:** Extracts symbol, side (Buy/Sell), entry, stop-loss, and take-profits from message text using regex patterns
- **Confidence Scoring:** Rates how well the message was parsed (high/medium/low)
- **Acknowledge:** Mark signals as "seen" to manage your workflow
- **Auto-Trade:** Convert a parsed signal directly into a trade in the system with one click
- **Strategy Detection:** Recognizes ICT terminology (FVG, OB, MSS, Killzone, etc.) in messages

**Supported Symbols:**
EURUSD, GBPUSD, USDJPY, AUDUSD, XAUUSD (Gold), US30, NAS100, NQ, ES, BTCUSD, ETHUSD, and 30+ more.

**Technical Details:**
- Uses Telegram Bot API (`getUpdates` polling)
- Regex patterns for entry, SL, TP, and symbol detection
- Supports both `-100` prefixed and plain numeric channel IDs

---

### 4.8 Knowledge Base

**What It Looks Like:** A searchable library of YouTube transcripts, an AI chat interface, and analysis summaries for each video.

**What It Does:** The Knowledge Base is your **AI trading mentor**. It lets you:

- **Ingest YouTube Videos:** Paste a YouTube URL (video, playlist, or channel) and the system automatically downloads the transcript
- **AI Analysis:** Analyzes transcripts to extract key concepts, trading insights, timestamps, and sentiment
- **Semantic Search:** Uses sentence-transformer embeddings to find relevant passages across all transcripts
- **AI Chat (RAG):** Ask questions like "What is a Fair Value Gap?" and get answers synthesized from your ingested videos
- **Concept Extraction:** Automatically tags content with ICT concepts (MSS, FVG, OB, Liquidity, etc.)

**How It Works:**

```
YouTube URL → Transcript (yt-dlp / youtube-transcript-api)
                    ↓
            Text Chunking (200 words, 50 overlap)
                    ↓
            Vector Embedding (sentence-transformers)
                    ↓
            Vector Store (SQLite + cosine similarity)
                    ↓
            User Query → Vector Search → Top 5 Chunks → Answer
```

**Technical Details:**
- Supports single videos, playlists, and entire channels
- Fallback to Whisper audio transcription if captions are disabled
- AI analysis uses Ollama (local LLM) or OpenAI API
- Chunks are stored in `kb_chunks` collection with embeddings

---

### 4.9 Library

**What It Looks Like:** A file/document management interface where you can upload, tag, and search trading documents, screenshots, and notes.

**What It Does:** The Library is your personal **trading document archive**. It stores:

- Trade screenshots and chart markings
- PDF strategy documents
- Personal notes and journals
- Any file you want to associate with your trading business

Documents can be tagged, searched, and linked to specific trades or strategies.

---

### 4.10 What's Up

**What It Looks Like:** A live trade tracking dashboard showing all open positions, their current P&L, and auto-management status. It's the "mission control" for your active trades.

**What It Does:** What's Up is where you **watch your trades live**. It features:

- **Open Trades Table:** Symbol, entry, current price, unrealized P&L, R-multiple, stop-loss status
- **Auto-Management:** The system automatically:
  - Detects when TP1 is hit → closes 33% of position, moves SL to breakeven
  - Detects SL hits → fully closes position
  - Detects breakeven stops → closes remaining position
- **Manual Controls:** Buttons to partial close, full close, or move SL to breakeven
- **Live Price Updates:** Prices refresh every few seconds for real-time P&L
- **Color Coding:** Green = profit, Red = loss, Yellow = breakeven

**Auto-Management Rules:**

```
┌────────────────────────────────────────────┐
│  AUTO-MANAGEMENT RULES                      │
├────────────────────────────────────────────┤
│                                             │
│  TP1 HIT:                                   │
│    → Close 33% of position at TP1 price     │
│    → Move Stop Loss to Entry (Breakeven)   │
│    → Mark TP1 as hit                        │
│                                             │
│  SL HIT (before BE):                        │
│    → Close 100% of position at SL price    │
│    → Record full loss                       │
│                                             │
│  SL HIT (at BE):                            │
│    → Close 100% of remaining position        │
│    → Record breakeven (0R)                  │
│                                             │
│  AFTER TP1: Manual management only          │
│    (No auto TP2/TP3 — trader discretion)    │
│                                             │
└────────────────────────────────────────────┘
```

**Technical Details:**
- `check_tp_hits()` runs automatically when `get_open_trades()` is called
- Uses live price data from Yahoo Finance or MT5 manual override
- Partial closes are recorded as "legs" with individual P&L and R-multiple

---

### 4.11 Settings

**What It Looks Like:** A preferences panel with toggles for theme, default symbol, risk percentage, account balance, notifications, and layout options.

**What It Does:** Settings lets you customize the OS to your preferences:

- **Theme:** Dark or light mode
- **Default Symbol:** Which instrument loads by default (e.g., EURUSD)
- **Risk %:** Your default risk per trade (e.g., 1%)
- **Account Balance:** Your default balance for lot calculations
- **Auto-Trade:** Enable/disable automatic trading from Telegram signals
- **Notifications:** Enable/disable browser/push notifications
- **Layout:** Choose different dashboard layouts

**Technical Details:**
- Settings stored in SQLite `settings` collection with ID `global`
- Exported as JSON via `/settings/export` endpoint

---

## 5. Data Flow: The Life of a Trade

Here's how a trade flows through the entire system, from idea to journal entry:

```
┌──────────────────────────────────────────────────────────────────────────────┐
│                    THE LIFE OF A TRADE — DATA FLOW                           │
├──────────────────────────────────────────────────────────────────────────────┤
│                                                                              │
│  PHASE 1: RESEARCH & SETUP                                                    │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                               │
│  User ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │
│  ────►│  Research    │────►│  ICT Engine  │────►│  Signal      │            │
│       │  (SMA, ATR)  │     │  (Patterns)  │     │  Engine      │            │
│       └──────────────┘     └──────────────┘     └──────────────┘            │
│                                                        │                      │
│                                                        ▼                      │
│                                               ┌──────────────┐              │
│                                               │  Signal      │             │
│                                               │  Generated?  │──YES──┐     │
│                                               │  (Score ≥2)  │       │     │
│                                               └──────────────┘       │     │
│                                                        NO            │     │
│                                                        │             │     │
│                                                        ▼             │     │
│                                               ┌──────────────┐       │     │
│                                               │  Wait /      │       │     │
│                                               │  Continue    │◄──────┘     │
│                                               │  Monitoring  │             │
│                                               └──────────────┘             │
│                                                                               │
│  PHASE 2: TRADE ENTRY                                                         │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                               │
│  User ┌──────────────┐     ┌──────────────┐     ┌──────────────┐            │
│  ────►│  Execute     │────►│  Lot Calc    │────►│  Trade       │            │
│       │  (Form)      │     │  (Auto Size) │     │  Created     │            │
│       └──────────────┘     └──────────────┘     └──────────────┘            │
│                                                        │                      │
│                                                        ▼                      │
│                                               ┌──────────────┐              │
│                                               │  SQLite DB   │              │
│                                               │  (trades)    │              │
│                                               └──────────────┘              │
│                                                                               │
│  PHASE 3: ACTIVE MANAGEMENT (What's Up)                                       │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                               │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │  Live Prices │────►│  Check       │────►│  Action      │                │
│  │  (Yahoo/MT5) │     │  TP/SL Hits? │     │  Taken       │                │
│  └──────────────┘     └──────────────┘     └──────────────┘                │
│                              │                                              │
│                              ├── TP1 Hit ──► Partial Close (33%) + BE SL   │
│                              ├── SL Hit  ──► Full Close (Loss)             │
│                              └── Nothing ──► Continue Monitoring             │
│                                                                               │
│  PHASE 4: CLOSURE & JOURNALING                                                │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                               │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                │
│  │  Full Close  │────►│  P&L         │────►│  Analytics   │                │
│  │  (Manual or  │     │  Calculated  │     │  Updated     │                │
│  │   Auto)      │     │  (R-Tracked) │     │  (Stats)     │                │
│  └──────────────┘     └──────────────┘     └──────────────┘                │
│                              │                      │                       │
│                              ▼                      ▼                       │
│                       ┌──────────────┐     ┌──────────────┐                  │
│                       │  Trade Log   │     │  Dashboard   │                  │
│                       │  (History)   │     │  KPIs        │                  │
│                       └──────────────┘     └──────────────┘                  │
│                                                                               │
│  PHASE 5: ANALYSIS & LEARNING                                                   │
│  ───────────────────────────────────────────────────────────────────────    │
│                                                                               │
│  ┌──────────────┐     ┌──────────────┐     ┌──────────────┐                  │
│  │  Analytics   │────►│  KB Chat    │────►│  Strategy    │                  │
│  │  (Review P&L)│     │  (Why did   │     │  Refinement  │                  │
│  │              │     │  I win/lose?)│     │              │                  │
│  └──────────────┘     └──────────────┘     └──────────────┘                  │
│                                                                               │
└──────────────────────────────────────────────────────────────────────────────┘
```

---

## 6. Technology Stack

### Backend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Web Framework** | FastAPI (Python) | REST API endpoints, request handling, validation |
| **Database** | SQLite | Persistent storage for trades, signals, KB, settings |
| **Vector Search** | sentence-transformers + SQLite | Semantic search across transcripts |
| **HTTP Client** | httpx | External API calls (Yahoo, Telegram, MT5 bridge) |
| **Data Processing** | NumPy | Pattern detection, indicator calculations |
| **YouTube Integration** | yt-dlp, youtube-transcript-api | Video transcript extraction |
| **AI Analysis** | Ollama / OpenAI | Video transcript analysis and chat |
| **Auth** | JWT (optional) | API key and token-based authentication |

### Frontend

| Component | Technology | Purpose |
|-----------|-----------|---------|
| **Framework** | React 18 | UI components, state management |
| **Build Tool** | Vite | Fast development builds and hot reload |
| **Styling** | Tailwind CSS | Utility-first CSS framework |
| **Routing** | React Router | Single-page app navigation |
| **State** | Zustand / Context | Global state management |
| **Charts** | Recharts / Lightweight Charts | Data visualization |
| **TypeScript** | TypeScript 5 | Type-safe development |

### External Services

| Service | Role | Integration |
|---------|------|-------------|
| **Yahoo Finance API** | Free market data for prices and history | Direct HTTP calls to `query1.finance.yahoo.com` |
| **MetaTrader 5** | Live broker execution and account data | Local Flask bridge on `localhost:5001` |
| **Telegram Bot API** | Signal fetching from channels | `getUpdates` polling via HTTP |
| **YouTube** | Educational video ingestion | `yt-dlp` and `youtube-transcript-api` libraries |

---

## 7. Database Design

The ICT Trading OS uses a **single-table JSON document store** design in SQLite. Instead of rigid relational tables, data is stored in a flexible `docs` table:

```sql
CREATE TABLE docs (
    collection TEXT NOT NULL,    -- "trades", "kb_sources", "settings", etc.
    id TEXT NOT NULL,            -- Unique document ID
    data TEXT NOT NULL,          -- JSON-serialized document
    created_at TEXT,             -- ISO timestamp
    updated_at TEXT,             -- ISO timestamp
    PRIMARY KEY (collection, id)
);
```

### Collections

| Collection | Stores | Example Documents |
|-----------|--------|-------------------|
| `trades` | All trade records | Open, closed, and partial trades with legs |
| `telegram_signals` | Parsed Telegram messages | Signal data, parsed fields, acknowledge status |
| `kb_sources` | Knowledge base entries | YouTube transcripts, analysis, metadata |
| `kb_chunks` | Vector search chunks | Text chunks with embeddings for semantic search |
| `settings` | User preferences | Theme, risk %, balance, layout |
| `plans` | Trading plans | Pre-trade plans with strategy and rules |
| `alerts` | Price alerts | Trigger conditions and notification status |

### Why SQLite?

- **Zero setup:** No database server to install or configure
- **Single file:** The entire database is one `.db` file
- **Portable:** Easy to backup, copy, or migrate
- **Sufficient:** For a personal trading OS, SQLite handles thousands of trades effortlessly
- **JSON flexibility:** Schema changes don't require migrations

---

## 8. API Architecture

### Router Structure

```
/                    → Health check & app info
/market              → Price data, history, instruments
/ict                 → ICT pattern analysis (single & multi-TF)
/signals             → Signal generation, scanning, stats
/trades              → Full trade lifecycle (CRUD + partial/close)
/orders              → Order entry with lot calculation
/analytics           → Performance metrics, expectancy, heatmap
/telegram            → Signal polling, acknowledge, auto-trade
/mt5                 → MetaTrader 5 bridge proxy
/kb                  → Knowledge base (sources, search, chat)
/research            → Technical analysis, correlation, summary
/news                → Curated market news feed
/settings            → User preferences
/quant               → Quant lab & backtesting tools
/alerts              → Price alerts & notifications
/bot                 → Trading bot engine
/playground          → Pattern detection playground
```

### Key API Patterns

- **RESTful design:** GET for reads, POST for creates/actions, DELETE for removal
- **Pydantic validation:** All request bodies are validated schemas
- **Error handling:** Consistent `{ "error": "message" }` format on failures
- **CORS enabled:** Frontend can communicate from `localhost:5173`
- **Optional auth:** JWT middleware can be enabled via `AUTH_ENABLED` env var

---

## 9. Screenshots & UI Walkthrough

While this document doesn't embed actual screenshots, here is a description of what each page looks like in the running application:

### Dashboard
> **Dark theme with neon accents.** Top row has 4 KPI cards (win rate, P&L, open trades, total trades). Middle section shows a live price ticker with green/red change indicators. Bottom-left has a news feed with headlines. Bottom-right shows the biggest market movers with sparkline charts. The navigation sidebar is on the left with icons for each page.

### Execute
> **Clean, focused form layout.** Large dropdown for instrument selection. Side toggle (Buy/Sell) with green/red color coding. Entry price field with "Use Live Price" button. Stop loss and three take-profit fields. Account balance and risk % sliders. A "Calculate Lot" button reveals the auto-calculated position size. A preview card shows exact dollar risk and potential reward.

### What's Up
> **Live mission control.** A table of open trades with real-time P&L updating every few seconds. Color-coded rows (green = profit, red = loss). Action buttons for each row: "Partial Close", "Move to BE", "Close All". Auto-management status indicator showing whether TP1 or SL has been hit. A summary banner at the top shows total unrealized P&L.

### Analytics
> **Data-rich dashboard.** A large equity curve line chart. Session heatmap bar chart. Stats grid with win rate, expectancy, max drawdown, average R, Kelly criterion. Monthly performance table with P&L and win rate. Per-symbol breakdown table. The design uses card-based layouts with subtle borders.

### Knowledge Base
> **Two-column layout.** Left side: list of ingested sources with titles, tags, and concept badges. Right side: AI chat interface with a text input at the bottom. Chat bubbles show questions and answers. Sources are cited with clickable links. An "Add Source" button opens a modal for YouTube URL input.

### Telegram Feed
> **Chat-style feed.** Messages appear in bubbles like a messaging app. Parsed signals show structured cards with symbol, side, entry, SL, TPs, and confidence badges. Acknowledge button (checkmark) on each message. Auto-trade button (lightning bolt) for high-confidence signals. A status bar at the top shows connection status and last poll time.

---

## 10. Glossary of Trading Terms

| Term | Simple Explanation |
|------|-------------------|
| **Pip** | The smallest price move in a forex pair (e.g., 0.0001 for EURUSD). Think of it as "one cent" for currencies. |
| **Lot** | The size of your trade. A standard lot = 100,000 units. You can trade mini (0.1) and micro (0.01) lots. |
| **Stop Loss (SL)** | An automatic order that closes your trade if it goes against you by a set amount. It's your "emergency exit." |
| **Take Profit (TP)** | An automatic order that closes your trade when it reaches your target profit. |
| **R-Multiple** | A way to measure profit in "risk units." If you risk $100 and make $300, that's a 3R trade. |
| **Breakeven (BE)** | Moving your stop loss to your entry price so you can't lose money on the trade. |
| **Partial Close** | Closing part of your position (e.g., 33%) to lock in some profit while letting the rest run. |
| **Drawdown** | How much your account drops from its highest point. A 10% drawdown means you lost 10% from your peak. |
| **Expectancy** | The average amount you expect to make (or lose) per trade over many trades. |
| **Liquidity** | Areas where many traders have placed orders. Big players often push price to these areas to trigger them. |
| **Support** | A price level where buying pressure has historically stopped the price from falling further. |
| **Resistance** | A price level where selling pressure has historically stopped the price from rising further. |
| **SMA** | Simple Moving Average — an average of past prices. The 20 SMA shows the average price over the last 20 periods. |
| **ATR** | Average True Range — measures how much an instrument typically moves. Higher ATR = more volatile. |
| **Kelly Criterion** | A math formula that tells you the optimal percentage of your account to risk per trade based on your edge. |
| **FundingPips** | A prop firm that provides traders with funded accounts. The system includes their leverage settings. |

---

## Closing Thoughts

The ICT Trading OS is more than just software — it's a **complete trading ecosystem**. It combines:

- **Market intelligence** (live data, news, research)
- **Pattern recognition** (ICT methodology engine)
- **Risk management** (auto lot sizing, structured trade management)
- **Performance tracking** (analytics, journaling, metrics)
- **Continuous learning** (knowledge base, AI chat, video analysis)
- **Automation** (signals, Telegram integration, MT5 bridge)

Whether you're a beginner trying to understand why the market moves, or an experienced trader looking for an edge, this system provides the tools, structure, and insights to trade with confidence.

> *"Trade what you see, not what you think."* — ICT Core Principle
