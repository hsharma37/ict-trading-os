# QuantLab (Research) & Signals — functionality and July 2026 upgrade report

Everything below runs on **broker candles from the MT5 bridge only** — no Yahoo/OANDA,
no synthetic data. If the bridge is down, these tools say so instead of analysing a
different broker's prices.

## Signals section — what it does

| Piece | What it tells you |
|---|---|
| **ICT Confluence Signal** | Direction + a 9-point ICT checklist (HTF bias, MSS, FVG, OB, liquidity sweep, premium/discount, killzone, R:R viability, MTF alignment). Direction comes from the fused **Signal Intelligence** read (news sentiment + technical trend + momentum + ICT playbook); ICT structure is the fallback when SI is neutral. The card names its direction source. |
| **Target R selector** | 1.5/2/3 R — sets the reward:risk of the proposed entry/SL/TP levels (TPs staged at ⅓/⅔/full R). Also on `/signals/scan`. |
| **Signal Intelligence** | The fused per-symbol read with factor breakdown, reasoning, and suggestions. Heuristic weights (0.5 news / 0.35 trend / 0.15 momentum) — labelled as such, not backtested win-rates. |
| **Strength calibration** | Measured historical win rate + expectancy per STRONG/MODERATE/WEAK tier, net of costs, on **any of 5m/15m/30m/1h/4h/1d** and at the chosen R. Honest bar: expectancy > 0. |
| **MT5 chart levels** | Pushes OB/FVG/BSL/SSL/MSS/BoS + per-TF fib/OTE/premium-discount to the MT5 chart via the bridge + `ICTOSLevels.mq5`. |

## QuantLab (Research) — what it does

| Tool | What it tells you |
|---|---|
| **Instrument analysis / correlation / market summary** | Technical snapshot per instrument, cross-instrument correlation, market overview annotated with your live MT5 positions. |
| **ICT Backtest** | Walk-forward replay of the ICT signal logic. Now on **5m–1d** timeframes. Net of estimated spread+commission, limit fills, one trade at a time. |
| **Parameter sweep** | Grid-search target-R × killzone × trend with an out-of-sample column to expose curve-fitting. |
| **Honest walk-forward test** | Picks the best config on the first 60% of history, locks it, reports ONLY the untouched last 40%. |
| **Monte Carlo** | Resamples the backtest's R-series (which inherits its timeframe) → percentile outcomes, drawdown distribution, risk of ruin at your risk-per-trade. |
| **Strategy Lab** *(new)* | Six classic open-source strategies — SMA 20/50 cross, EMA 12/26 cross, Connors RSI(2), Bollinger 20/2σ revert, Donchian 20 breakout (Turtle), 10-bar momentum — plus the ICT confluence baseline, all on the same candles/costs/stop model (1.5×ATR), ranked by after-cost expectancy. |
| **ML baseline** *(new)* | Pure-numpy walk-forward logistic regression on 6 price features predicting next-bar direction. Scored only out-of-sample vs the majority-class baseline. A research yardstick — near-baseline accuracy is the honest, expected result. |
| **Live paper-forward test** | Lock a config **with a name**, then count only signals on candles printed after you started — un-fittable out-of-sample. No orders placed. |

## What was fixed/improved in this pass

1. **Forward-test error fixed** — the list endpoint recomputed every running test by
   pulling 5000 bars each through the tunnel on every page load, which timed out the
   serverless function. Now: list serves stored stats instantly; per-test **Refresh**
   recomputes with a fetch bounded to the test's age (≤3000 bars); the background tick
   probes staleness with a 2-bar fetch.
2. **Forward tests are nameable** — `name` on create, shown as the row title, so
   concurrent strategy variants are tellable apart.
3. **Timeframe parity** — backtest, sweep, honest test, Monte Carlo (via the backtest's
   R-series), calibration and forward tests all accept 5m/15m/30m/1h/4h/1d.
4. **Strategy Lab + ML baseline added** (see above) — same referee as ICT, so numbers
   are comparable.
5. **Stale code removed** — dead Yahoo-era `SYMBOL_MAP`/`price_history`/`_last_valid_value`
   in market_data; stale "no spread/commission" assumptions string corrected to
   "net of estimated spread+commission" (the backtester has charged costs since the
   cost-model change — the label was wrong, not the math).

## Honest limitations (unchanged by this upgrade)

- Backtests model spread+commission but not slippage or requotes.
- MT5 history is capped at 5000 bars per request — "1y" on 5m is not attainable; the
  effective window is whatever the broker serves.
- Strength tiers and strategy results with <30 trades are flagged as small-sample.
- The ML baseline predicting near the majority baseline is *expected* — it exists to
  keep the rest of the app honest, not to trade.
