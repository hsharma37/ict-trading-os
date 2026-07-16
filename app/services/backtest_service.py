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
                 fill_window: int = 8, max_hold: int = 48, min_confluence: int = 2,
                 session_filter: bool = False, trend_filter: bool = False,
                 include_costs: bool = True, min_stop_pips: float = 0.0) -> Dict:
    """Replay the ICT signal over history and score each trade in R-multiples.

    `min_confluence` gates entries on the same confluence score the live engine
    uses (only trade higher-quality setups), so the backtest reflects the signals
    you'd actually take, not every pattern touch."""
    symbol = symbol.upper()
    candles = market_service.get_history(symbol, timeframe, 5000, history_range=history_range)
    guard = _data_guard(symbol, candles, window)
    if guard:
        return guard
    cost_price = _round_trip_cost_price(symbol) if include_costs else 0.0
    min_stop_price = min_stop_pips * _pip_size(symbol)
    signals = _scan_signals(candles, symbol, timeframe, window, min_confluence)
    trades = _evaluate(candles, signals, target_r, fill_window, max_hold, session_filter, trend_filter,
                       cost_price, min_stop_price)
    summary = _summarize_backtest(symbol, timeframe, target_r, history_range, len(candles), trades)
    summary["min_confluence"] = min_confluence
    summary["filters"] = {"session": session_filter, "trend": trend_filter, "min_stop_pips": min_stop_pips}
    summary["costs_included"] = include_costs
    summary["cost_per_trade_note"] = ("net of estimated spread + commission" if include_costs
                                      else "gross — no trading costs modelled")
    return summary


# Killzone hours (UTC-ish) — London Open, NY AM, NY PM, matching the live engine.
_KILLZONE_HOURS = set(range(7, 10)) | set(range(12, 15)) | set(range(17, 21))

# Typical retail round-trip trading costs, so backtests reflect NET results, not
# a frictionless fantasy. Spread is in PRICE units (half-spread each side, paid
# once round-trip); commission is $/lot round-turn converted to price via the
# contract size. These are conservative estimates — the point is to see whether
# a thin edge survives costs at all.
_SPREAD_PRICE = {
    "EURUSD": 0.00008, "GBPUSD": 0.00012, "USDJPY": 0.008, "AUDUSD": 0.00010,
    "NZDUSD": 0.00015, "USDCAD": 0.00012, "XAUUSD": 0.25, "BTCUSD": 5.0,
}
_COMMISSION_USD_PER_LOT_RT = 7.0


def _pip_size(symbol: str) -> float:
    s = symbol.upper()
    if s.endswith("JPY"):
        return 0.01
    if s == "XAUUSD":
        return 0.1
    if s == "BTCUSD":
        return 1.0
    return 0.0001


def _round_trip_cost_price(symbol: str, spread_price: Optional[float] = None) -> float:
    """Estimated round-trip cost in PRICE units (spread + commission)."""
    sp = spread_price if spread_price is not None else _SPREAD_PRICE.get(symbol.upper(), 0.00012)
    try:
        from app.services.instrument_config import get_instrument
        cs = float((get_instrument(symbol.upper()) or {}).get("contract_size", 100000) or 100000)
    except Exception:
        cs = 100000.0
    commission = _COMMISSION_USD_PER_LOT_RT / cs if cs else 0.0
    return sp + commission


def _data_guard(symbol, candles, window) -> Optional[Dict]:
    if not candles or len(candles) < window + 20:
        return {"symbol": symbol, "error": "Not enough historical data to backtest.",
                "candles": len(candles or [])}
    if history_is_synthetic(candles):
        return {"symbol": symbol, "error": "Market data feed unavailable (would be simulated) — cannot backtest.",
                "data_quality": "synthetic"}
    return None


def _scan_signals(candles, symbol, timeframe, window, min_confluence) -> List[Dict]:
    """The expensive pass (ICT pattern detection per bar) — done ONCE and reused
    across every sweep config. Emits candidate entries with the metadata the
    filters need (killzone hour, trend alignment)."""
    from datetime import datetime
    sigs: List[Dict] = []
    n = len(candles)
    for i in range(window, n - 1):
        sub = candles[i - window:i]
        a = ict_engine.analyze(sub, symbol, timeframe)
        bias = a.get("current_bias", "NEUTRAL")
        if bias == "NEUTRAL" or a.get("confluence_score", 0) < min_confluence:
            continue
        zone = ict_engine.calculate_entry(a.get("patterns", []), bias, sub[-1]["close"])
        if not zone or not zone.get("risk"):
            continue
        closes = [c["close"] for c in sub]
        sma = sum(closes[-50:]) / 50 if len(closes) >= 50 else sum(closes) / len(closes)
        long = bias == "BULLISH"
        t = candles[i].get("time")
        try:
            hour = datetime.utcfromtimestamp(int(t)).hour if t else 12
        except (TypeError, ValueError, OSError):
            hour = 12
        sigs.append({"i": i, "long": long, "entry": zone["entry"], "sl": zone["sl"],
                     "risk": zone["risk"], "hour": hour,
                     "confluence": int(a.get("confluence_score", 0)),
                     "trend_ok": (zone["entry"] > sma) if long else (zone["entry"] < sma)})
    return sigs


def _evaluate(candles, signals, target_r, fill_window, max_hold, session_filter, trend_filter,
              cost_price: float = 0.0, min_stop_price: float = 0.0) -> List[Dict]:
    """Cheap pass: apply a config's filters + target to the pre-scanned signals
    and walk each trade to its outcome. One trade at a time (no overlap).

    `cost_price` (spread+commission in price units) is charged to every trade,
    expressed in R as cost_price/risk — so tight-stop trades pay proportionally
    more, exactly as in reality."""
    n = len(candles)
    trades: List[Dict] = []
    busy_until = -1
    for s in signals:
        i = s["i"]
        if i <= busy_until:
            continue
        if session_filter and s["hour"] not in _KILLZONE_HOURS:
            continue
        if trend_filter and not s["trend_ok"]:
            continue
        if min_stop_price and s["risk"] < min_stop_price:
            continue  # skip tight-stop setups where spread would dominate
        entry, sl, risk, long = s["entry"], s["sl"], s["risk"], s["long"]
        target = entry + target_r * risk if long else entry - target_r * risk
        # Limit fill at `entry` within fill_window bars.
        fill_idx = None
        for j in range(i, min(i + fill_window, n)):
            if candles[j]["low"] <= entry <= candles[j]["high"]:
                fill_idx = j
                break
        if fill_idx is None:
            continue
        # Walk forward; stop assumed first on an ambiguous bar (conservative).
        end_k = min(fill_idx + 1 + max_hold, n)
        outcome_r, exit_idx, is_open = None, fill_idx, False
        for k in range(fill_idx + 1, end_k):
            hi, lo = candles[k]["high"], candles[k]["low"]
            hit_sl = lo <= sl if long else hi >= sl
            hit_tp = hi >= target if long else lo <= target
            if hit_sl:
                outcome_r, exit_idx = -1.0, k
                break
            if hit_tp:
                outcome_r, exit_idx = float(target_r), k
                break
        if outcome_r is None:
            if end_k >= fill_idx + 1 + max_hold:
                # Completed the max-hold window without a hit → timed out (closed).
                exit_idx = fill_idx + max_hold
            else:
                # Ran out of candles before resolving → the trade is still OPEN
                # (its R below is unrealized; forward-test excludes it from stats).
                is_open = True
                exit_idx = n - 1
            last = candles[exit_idx]["close"]
            move = (last - entry) if long else (entry - last)
            outcome_r = round(move / risk, 2) if risk else 0.0
        # Charge round-trip cost (in R) to closed trades — the honest, net figure.
        cost_r = (cost_price / risk) if (cost_price and risk) else 0.0
        net_r = outcome_r if is_open else round(outcome_r - cost_r, 3)
        trades.append({
            "dir": "long" if long else "short", "entry": entry, "sl": sl,
            "target": round(target, 5), "r": net_r, "gross_r": round(outcome_r, 2),
            "entry_idx": fill_idx, "open": is_open, "confluence": s.get("confluence", 0),
            "entry_time": candles[fill_idx].get("time"), "exit_time": candles[exit_idx].get("time"),
        })
        busy_until = exit_idx
    return trades


def run_sweep(symbol: str, timeframe: str = "1h", history_range: str = "1y",
              window: int = 100, min_confluence: int = 2, oos_split: float = 0.6) -> Dict:
    """Grid-search target-R × session-filter × trend-filter to see if ANY config
    has a positive edge — and whether it survives out-of-sample (the anti-curve-
    fit check). The costly pattern scan runs once; each config is a cheap eval."""
    symbol = symbol.upper()
    candles = market_service.get_history(symbol, timeframe, 5000, history_range=history_range)
    guard = _data_guard(symbol, candles, window)
    if guard:
        return guard
    n = len(candles)
    split_idx = int(n * oos_split)
    cost_price = _round_trip_cost_price(symbol)
    pip = _pip_size(symbol)
    signals = _scan_signals(candles, symbol, timeframe, window, min_confluence)

    configs: List[Dict] = []
    for target_r in (1.5, 2.0, 3.0):
      for min_stop in (0, 15, 25):
        for sess in (False, True):
            for trend in (False, True):
                trades = _evaluate(candles, signals, target_r, 8, 48, sess, trend, cost_price, min_stop * pip)
                if len(trades) < 15:
                    continue
                rs = [t["r"] for t in trades]
                is_r = [t["r"] for t in trades if t["entry_idx"] < split_idx]   # in-sample (train)
                oos_r = [t["r"] for t in trades if t["entry_idx"] >= split_idx]  # out-of-sample (test)
                mc = monte_carlo(rs, n_sims=500, risk_per_trade_pct=1.0)
                configs.append({
                    "target_r": target_r, "session_filter": sess, "trend_filter": trend, "min_stop_pips": min_stop,
                    "trades": len(trades),
                    "win_rate": round(sum(1 for r in rs if r > 0) / len(rs) * 100, 1),
                    "expectancy_r": round(sum(rs) / len(rs), 3),
                    "is_expectancy_r": round(sum(is_r) / len(is_r), 3) if is_r else None,
                    "oos_expectancy_r": round(sum(oos_r) / len(oos_r), 3) if oos_r else None,
                    "total_r": round(sum(rs), 2),
                    "risk_of_ruin_pct": mc.get("risk_of_ruin_pct") if not mc.get("error") else None,
                })
    configs.sort(key=lambda c: c["expectancy_r"], reverse=True)
    best = configs[0] if configs else None
    verdict = _sweep_verdict(best)
    return {
        "symbol": symbol, "timeframe": timeframe, "history_range": history_range,
        "candles": n, "signals_scanned": len(signals), "configs_tested": len(configs),
        "oos_split_pct": int(oos_split * 100), "configs": configs, "best": best, "verdict": verdict,
    }


def calibrate_strength(symbol: str, timeframe: str = "1h", target_r: float = 3.0,
                       history_range: str = "1y", trend_filter: bool = True) -> Dict:
    """What each signal-STRENGTH tier actually won historically (net of costs) —
    so 'STRONG' stops being an arbitrary label and gets a measured win rate.
    Buckets every backtested trade by the confluence score at its entry."""
    symbol = symbol.upper()
    if timeframe == "1d":
        history_range = "2y"
    candles = market_service.get_history(symbol, timeframe, 5000, history_range=history_range)
    guard = _data_guard(symbol, candles, 100)
    if guard:
        return guard
    cost = _round_trip_cost_price(symbol)
    signals = _scan_signals(candles, symbol, timeframe, 100, 0)  # all setups, no gate
    trades = _evaluate(candles, signals, target_r, 8, 48, False, trend_filter, cost)
    closed = [t for t in trades if not t.get("open")]
    breakeven = round(100 / (1 + target_r), 1)

    def tier(c: int) -> str:
        return "STRONG" if c >= 4 else "MODERATE" if c == 3 else "WEAK"

    buckets: Dict[str, list] = {"STRONG": [], "MODERATE": [], "WEAK": []}
    for t in closed:
        buckets[tier(int(t.get("confluence", 0)))].append(t["r"])

    tiers = {}
    for name, rs in buckets.items():
        if rs:
            wins = sum(1 for r in rs if r > 0)
            exp = sum(rs) / len(rs)
            tiers[name] = {
                "trades": len(rs), "win_rate": round(wins / len(rs) * 100, 1),
                "expectancy_r": round(exp, 3),
                # Truth = expectancy net of costs (NOT the frictionless breakeven,
                # which a positive win-rate can beat while still losing money).
                "profitable": exp > 0,
                "small_sample": len(rs) < 30,
            }
        else:
            tiers[name] = {"trades": 0}
    return {
        "symbol": symbol, "timeframe": timeframe, "target_r": target_r,
        "history_range": history_range, "breakeven_win_rate": breakeven,
        "total_trades": len(closed), "tiers": tiers,
        "note": "Net of estimated spread + commission. Confluence tier: STRONG ≥4, MODERATE =3, WEAK ≤2 ICT confluences.",
    }


def run_honest_test(symbol: str, timeframe: str = "1h", history_range: str = "1y",
                    window: int = 100, min_confluence: int = 2, train_split: float = 0.6) -> Dict:
    """The anti-self-deception test. Choose the best config using ONLY the first
    `train_split` of history, lock it, then report its performance on the
    untouched remainder. If the blind-picked config still makes money on data it
    never saw, the edge is far more likely real than curve-fit."""
    symbol = symbol.upper()
    candles = market_service.get_history(symbol, timeframe, 5000, history_range=history_range)
    guard = _data_guard(symbol, candles, window)
    if guard:
        return guard
    n = len(candles)
    split = int(n * train_split)
    cost_price = _round_trip_cost_price(symbol)
    pip = _pip_size(symbol)
    signals = _scan_signals(candles, symbol, timeframe, window, min_confluence)  # one scan, reused

    # ── Phase 1: pick the best config on TRAIN only (candles[:split]) ──
    train_candles = candles[:split]
    train_signals = [s for s in signals if s["i"] < split]
    best = None
    for target_r in (1.5, 2.0, 3.0):
      for min_stop in (0, 15, 25):
        for sess in (False, True):
            for trend in (False, True):
                tr = _evaluate(train_candles, train_signals, target_r, 8, 48, sess, trend, cost_price, min_stop * pip)
                if len(tr) < 20:
                    continue
                exp = sum(t["r"] for t in tr) / len(tr)
                if best is None or exp > best["train_expectancy_r"]:
                    best = {"target_r": target_r, "session_filter": sess, "trend_filter": trend,
                            "min_stop_pips": min_stop,
                            "train_expectancy_r": round(exp, 3), "train_trades": len(tr)}
    if not best:
        return {"symbol": symbol, "timeframe": timeframe, "history_range": history_range,
                "candles": n, "train_split_pct": int(train_split * 100),
                "note": "Not enough training-period trades to choose a config."}

    # ── Phase 2: apply the LOCKED config to the untouched TEST period ──
    test_signals = [s for s in signals if s["i"] >= split]
    test_trades = _evaluate(candles, test_signals, best["target_r"], 8, 48,
                            best["session_filter"], best["trend_filter"], cost_price,
                            best.get("min_stop_pips", 0) * pip)
    test = _summarize_backtest(symbol, timeframe, best["target_r"], history_range, n, test_trades)
    test_mc = monte_carlo([t["r"] for t in test_trades], n_sims=1000, risk_per_trade_pct=1.0) if test_trades else {}
    verdict = _honest_verdict(best, test)
    return {
        "symbol": symbol, "timeframe": timeframe, "history_range": history_range, "candles": n,
        "train_split_pct": int(train_split * 100),
        "chosen_config": best, "test": test, "test_monte_carlo": test_mc, "verdict": verdict,
    }


def _config_label(best: Dict) -> str:
    return (f"target {best['target_r']}R"
            + (f", ≥{best['min_stop_pips']}-pip stop" if best.get("min_stop_pips") else "")
            + (", killzone-only" if best.get("session_filter") else "")
            + (", trend-aligned" if best.get("trend_filter") else ""))


def _honest_verdict(best: Dict, test: Dict) -> Dict:
    label = _config_label(best)
    if not test or test.get("trades", 0) < 10:
        return {"tone": "warn", "text": f"The blind-chosen config ({label}, train {best['train_expectancy_r']:+.3f}R) produced too few trades in the test period to judge — inconclusive."}
    te = test["expectancy_r"]
    if te > 0.05:
        return {"tone": "good", "text": f"PASSED. Chosen blind on the training data ({label}, {best['train_expectancy_r']:+.3f}R), it earned {te:+.3f}R/trade on the {test['trades']} unseen test trades too. That's real out-of-sample evidence — the strongest signal we can give short of live forward-testing. Trade small and confirm live before size."}
    if te < -0.02:
        return {"tone": "bad", "text": f"FAILED. The config that looked best on training ({label}, {best['train_expectancy_r']:+.3f}R) LOST {te:+.3f}R/trade on the unseen test data — textbook curve-fitting. The 'edge' was noise. Do not trade it."}
    return {"tone": "warn", "text": f"INCONCLUSIVE. The blind-chosen config ({label}) was {te:+.3f}R on unseen data — essentially break-even, so no reliable edge survived out-of-sample."}


def _sweep_verdict(best: Optional[Dict]) -> Dict:
    if not best:
        return {"tone": "bad", "text": "No configuration produced enough trades to judge — this signal isn't a mechanical strategy on this data."}
    label = _config_label(best)
    exp, oos = best["expectancy_r"], best.get("oos_expectancy_r")
    if exp <= 0.03:
        return {"tone": "bad", "text": f"No config crossed into a real edge. The best ({label}) is only {exp:+.3f}R/trade — break-even at best, negative after costs. Treat the signal as context, not a trigger."}
    if oos is None or oos <= 0:
        return {"tone": "warn", "text": f"The best config ({label}) looks positive in-sample ({exp:+.3f}R) but its edge does NOT hold out-of-sample ({oos if oos is not None else 'n/a'}R) — that's curve-fitting. Don't trust it."}
    return {"tone": "good", "text": f"Promising: {label} is {exp:+.3f}R/trade AND stays positive out-of-sample ({oos:+.3f}R). Forward-test it on new data before risking size — this is a candidate, not a guarantee."}


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
