"""Walk-forward backtest of the ICT signal logic + Monte Carlo on the results.

HONESTY NOTES (surfaced in the UI too): this is a realistic *approximation*, not
a broker-accurate simulation.
  • Single timeframe — it replays `ict_engine` on one series, not the live 3-TF
    (1h/15m/5m) stack, so results won't exactly match the Signals page.
  • Limit-fill model — a signal only counts if price later trades into the
    pattern entry within `fill_window` bars (else it's a no-fill, discarded).
  • No spread / commission / slippage, and one open trade at a time.
  • Fixed structure — risk = |entry−SL| (=1R), target = `target_r`·R.
  • Sample size = whatever the data provider returns; small samples are noise.
No look-ahead: the signal at bar i is computed only from candles[:i]; the outcome
is walked forward bar-by-bar after entry.
"""
from __future__ import annotations

import random
from typing import Dict, List, Optional

from app.services.market_data import market_service, history_is_synthetic
from app.services.ict_engine import ict_engine


def run_backtest(symbol: str, timeframe: str = "1h", target_r: float = 2.0,
                 history_range: str = "1y", window: int = 100,
                 fill_window: int = 8, max_hold: int = 48, min_confluence: int = 2) -> Dict:
    """Replay the ICT signal over history and score each trade in R-multiples.

    `min_confluence` gates entries on the same confluence score the live engine
    uses (only trade higher-quality setups), so the backtest reflects the signals
    you'd actually take, not every pattern touch."""
    symbol = symbol.upper()
    candles = market_service.get_history(symbol, timeframe, 5000, history_range=history_range)
    if not candles or len(candles) < window + 20:
        return {"symbol": symbol, "error": "Not enough historical data to backtest.",
                "candles": len(candles or [])}
    if history_is_synthetic(candles):
        return {"symbol": symbol, "error": "Market data feed unavailable (would be simulated) — cannot backtest.",
                "data_quality": "synthetic"}

    trades: List[Dict] = []
    i = window
    n = len(candles)
    while i < n - 1:
        sub = candles[i - window:i]
        analysis = ict_engine.analyze(sub, symbol, timeframe)
        bias = analysis.get("current_bias", "NEUTRAL")
        if bias == "NEUTRAL" or analysis.get("confluence_score", 0) < min_confluence:
            i += 1
            continue
        zone = ict_engine.calculate_entry(analysis.get("patterns", []), bias, sub[-1]["close"])
        if not zone or not zone.get("risk"):
            i += 1
            continue

        entry, sl, risk = zone["entry"], zone["sl"], zone["risk"]
        long = bias == "BULLISH"
        target = entry + target_r * risk if long else entry - target_r * risk

        # 1) Wait for a limit fill at `entry` within fill_window bars.
        fill_idx = None
        for j in range(i, min(i + fill_window, n)):
            if candles[j]["low"] <= entry <= candles[j]["high"]:
                fill_idx = j
                break
        if fill_idx is None:
            i += 1
            continue

        # 2) Walk forward from the fill; SL and target checked each bar. If both
        #    are touched in the same bar we conservatively assume the STOP first.
        outcome_r = None
        exit_idx = fill_idx
        for k in range(fill_idx + 1, min(fill_idx + 1 + max_hold, n)):
            hi, lo = candles[k]["high"], candles[k]["low"]
            hit_sl = lo <= sl if long else hi >= sl
            hit_tp = hi >= target if long else lo <= target
            if hit_sl and hit_tp:
                outcome_r = -1.0  # ambiguous bar → assume stop (conservative)
                exit_idx = k
                break
            if hit_sl:
                outcome_r = -1.0
                exit_idx = k
                break
            if hit_tp:
                outcome_r = float(target_r)
                exit_idx = k
                break
        if outcome_r is None:
            # Timed out — mark to the last close as a fractional R.
            last = candles[min(fill_idx + max_hold, n - 1)]["close"]
            move = (last - entry) if long else (entry - last)
            outcome_r = round(move / risk, 2) if risk else 0.0
            exit_idx = min(fill_idx + max_hold, n - 1)

        trades.append({
            "dir": "long" if long else "short", "entry": entry, "sl": sl,
            "target": round(target, 5), "r": round(outcome_r, 2),
            "entry_time": candles[fill_idx].get("time"), "exit_time": candles[exit_idx].get("time"),
        })
        # One trade at a time: resume scanning after the exit.
        i = max(exit_idx + 1, i + 1)

    summary = _summarize_backtest(symbol, timeframe, target_r, history_range, len(candles), trades)
    summary["min_confluence"] = min_confluence
    return summary


def _summarize_backtest(symbol, timeframe, target_r, history_range, n_candles, trades) -> Dict:
    n = len(trades)
    if n == 0:
        return {"symbol": symbol, "timeframe": timeframe, "target_r": target_r,
                "history_range": history_range, "candles": n_candles, "trades": 0,
                "note": "No qualifying signals fired over this window."}
    rs = [t["r"] for t in trades]
    wins = [r for r in rs if r > 0]
    losses = [r for r in rs if r <= 0]
    gross_win = sum(wins)
    gross_loss = abs(sum(losses))
    # Equity curve in R + max drawdown.
    equity, peak, max_dd, cur = 0.0, 0.0, 0.0, 0.0
    curve = []
    max_loss_streak = streak = 0
    for r in rs:
        equity += r
        curve.append(round(equity, 2))
        peak = max(peak, equity)
        max_dd = max(max_dd, peak - equity)
        streak = streak + 1 if r <= 0 else 0
        max_loss_streak = max(max_loss_streak, streak)
    win_rate = round(len(wins) / n * 100, 1)
    expectancy = round(sum(rs) / n, 3)
    return {
        "symbol": symbol, "timeframe": timeframe, "target_r": target_r,
        "history_range": history_range, "candles": n_candles,
        "trades": n, "wins": len(wins), "losses": len(losses),
        "win_rate": win_rate,
        "expectancy_r": expectancy,                       # avg R per trade
        "total_r": round(sum(rs), 2),
        "profit_factor": round(gross_win / gross_loss, 2) if gross_loss else None,
        "avg_win_r": round(sum(wins) / len(wins), 2) if wins else 0,
        "avg_loss_r": round(sum(losses) / len(losses), 2) if losses else 0,
        "max_drawdown_r": round(max_dd, 2),
        "max_loss_streak": max_loss_streak,
        "equity_curve_r": curve,
        "r_values": rs,
        "sample_caveat": "Small sample — treat as indicative, not predictive." if n < 30 else None,
        "assumptions": "Single timeframe, limit fills, no spread/commission/slippage, 1 trade at a time.",
    }


def monte_carlo(r_values: List[float], n_sims: int = 1000, horizon: Optional[int] = None,
                risk_per_trade_pct: float = 1.0, start_equity: float = 10000.0,
                ruin_drawdown_pct: float = 50.0, seed: int = 12345) -> Dict:
    """Bootstrap the trade R-distribution into `n_sims` random sequences to show
    the *range* of outcomes luck can produce from the same edge.

    Each trade risks `risk_per_trade_pct` of current equity, so one R-unit = that
    % of equity (compounding). Reports percentile final returns, drawdown
    distribution, probability of loss, and risk-of-ruin (equity dropping
    `ruin_drawdown_pct`% below the start peak)."""
    r_values = [float(r) for r in (r_values or []) if r is not None]
    if len(r_values) < 5:
        return {"error": "Need at least 5 trade outcomes to run a Monte Carlo."}
    horizon = horizon or len(r_values)
    rng = random.Random(seed)
    risk = risk_per_trade_pct / 100.0
    ruin_level = start_equity * (1 - ruin_drawdown_pct / 100.0)

    finals, drawdowns = [], []
    ruin_count = 0
    sample_curves: List[List[float]] = []
    for s in range(n_sims):
        equity, peak, max_dd, ruined = start_equity, start_equity, 0.0, False
        curve = [round(equity, 2)]
        for _ in range(horizon):
            r = r_values[rng.randrange(len(r_values))]
            equity *= (1 + r * risk)          # compound: risk% of equity per R
            peak = max(peak, equity)
            dd = (peak - equity) / peak * 100 if peak else 0
            max_dd = max(max_dd, dd)
            if equity <= ruin_level:
                ruined = True
            curve.append(round(equity, 2))
        finals.append(equity)
        drawdowns.append(max_dd)
        if ruined:
            ruin_count += 1
        if s < 25:
            sample_curves.append(curve)

    finals.sort()
    drawdowns.sort()

    def pct(arr, p):
        if not arr:
            return None
        idx = min(len(arr) - 1, max(0, int(round(p / 100 * (len(arr) - 1)))))
        return arr[idx]

    ret = lambda eq: round((eq / start_equity - 1) * 100, 1)
    return {
        "n_sims": n_sims, "horizon": horizon, "risk_per_trade_pct": risk_per_trade_pct,
        "start_equity": start_equity, "trades_sampled": len(r_values),
        "final_return_pct": {
            "p5": ret(pct(finals, 5)), "p25": ret(pct(finals, 25)), "median": ret(pct(finals, 50)),
            "p75": ret(pct(finals, 75)), "p95": ret(pct(finals, 95)),
        },
        "max_drawdown_pct": {
            "median": round(pct(drawdowns, 50), 1), "p95": round(pct(drawdowns, 95), 1),
        },
        "prob_loss_pct": round(sum(1 for f in finals if f < start_equity) / len(finals) * 100, 1),
        "risk_of_ruin_pct": round(ruin_count / n_sims * 100, 1),
        "ruin_drawdown_pct": ruin_drawdown_pct,
        "sample_curves": sample_curves,
    }
