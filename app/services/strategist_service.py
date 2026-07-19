"""Trading Strategist — the app plans the trade for you, honestly.

The one lesson every Strategy Lab run has taught: performance is decided by
REGIME. Trend/breakout strategies won on trending gold; mean-reversion and
premium/discount fading lost. So the strategist:

  1. Detects the CURRENT regime on the broker's own candles (ADX trend
     strength + direction, Kaufman Efficiency Ratio, ATR-percentile
     volatility) — transparent numpy math, no black box.
  2. Backtests every Strategy Lab entry on those same candles (net of costs)
     and keeps only strategies whose style FITS the regime AND whose
     after-cost expectancy is positive with a non-trivial sample.
  3. Emits a concrete plan: the chosen strategy, the evidence for it, the
     live setup (entry/SL/TP) if one is fresh, and what to do otherwise —
     or an explicit STAND ASIDE when nothing earns the recommendation.

What it deliberately does NOT do: place orders (Execute page, human hands),
invent an edge when none is measured, or hide the sample sizes. The regime
read is descriptive of the last ~5000 bars, not a prophecy.

Indicator note: this uses vendored pure-numpy indicators (shared with the
Strategy Lab) instead of pandas-ta — pandas-ta's current release drags in
numba, which neither builds against numpy 2.x here nor fits a serverless
deploy. Same formulas, fraction of the footprint.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from app.services.market_data import market_service, history_is_synthetic
from app.services import backtest_service as bt
from app.services.strategy_service import (
    STRATEGIES, _adx, _atr, signals_for, compare_strategies,
)

# Which strategy styles are allowed to be recommended in each regime.
_REGIME_STYLES = {
    "trending_up": {"trend", "breakout", "trend-pullback"},
    "trending_down": {"trend", "breakout", "trend-pullback"},
    "ranging": {"mean-reversion"},
    "unclear": set(),   # nothing auto-qualifies in chop — stand aside by default
}

_MIN_TRADES = 20          # below this a backtest row is anecdote, not evidence
_FRESH_BARS = 3           # a signal older than this many bars is "wait", not "act"


def _efficiency_ratio(close: np.ndarray, n: int = 10) -> float:
    """Kaufman ER: |net move| / sum(|bar moves|) over n bars. 1.0 = straight
    line (perfect trend), ~0 = pure chop."""
    if len(close) < n + 1:
        return 0.0
    seg = close[-(n + 1):]
    noise = float(np.abs(np.diff(seg)).sum())
    return float(abs(seg[-1] - seg[0]) / noise) if noise > 0 else 0.0


def detect_regime(candles: List[Dict]) -> Dict:
    """Classify the current regime from broker candles. Every threshold is
    stated in the output so the read is checkable, not oracular."""
    h = np.array([c["high"] for c in candles])
    l = np.array([c["low"] for c in candles])
    c_ = np.array([c["close"] for c in candles])
    adx, dip, dim = _adx(h, l, c_, 14)
    atr = _atr(h, l, c_, 14)
    er = _efficiency_ratio(c_, 10)

    adx_now = float(adx[-1]) if not np.isnan(adx[-1]) else 0.0
    di_bull = bool(dip[-1] > dim[-1]) if not np.isnan(dip[-1]) else False

    # Volatility state: current ATR vs its own trailing distribution.
    atr_valid = atr[~np.isnan(atr)]
    atr_pctile = float((atr_valid < atr_valid[-1]).mean() * 100) if len(atr_valid) > 20 else 50.0
    vol_state = "high" if atr_pctile >= 75 else "low" if atr_pctile <= 25 else "normal"

    if adx_now > 25 and er >= 0.25:
        regime = "trending_up" if di_bull else "trending_down"
    elif adx_now < 20 and er < 0.25:
        regime = "ranging"
    else:
        regime = "unclear"

    return {
        "regime": regime,
        "adx": round(adx_now, 1),
        "direction": "bullish" if di_bull else "bearish",
        "efficiency_ratio": round(er, 3),
        "atr_percentile": round(atr_pctile, 1),
        "volatility": vol_state,
        "rules": ("trend: ADX>25 & ER≥0.25 (direction from DI+/DI-) · "
                  "range: ADX<20 & ER<0.25 · otherwise unclear · "
                  "vol high/low = ATR above 75th / below 25th percentile"),
    }


def _live_setup(candles: List[Dict], strategy_key: str, target_r: float) -> Dict:
    """Latest signal from the chosen strategy: actionable if it fired within
    the last _FRESH_BARS bars, else 'wait for the next one'."""
    sigs = signals_for(candles, strategy_key)
    if not sigs:
        return {"status": "wait", "note": "No signal from this strategy in the loaded history."}
    last = sigs[-1]
    bars_ago = (len(candles) - 1) - last["i"]
    entry, sl, risk = last["entry"], last["sl"], last["risk"]
    tp = entry + target_r * risk if last["long"] else entry - target_r * risk
    setup = {
        "direction": "LONG" if last["long"] else "SHORT",
        "entry": round(entry, 5), "stop_loss": round(sl, 5),
        "take_profit": round(tp, 5), "risk_price": round(risk, 5),
        "bars_ago": int(bars_ago),
    }
    if bars_ago <= _FRESH_BARS:
        setup["status"] = "actionable"
        setup["note"] = (f"Signal fired {bars_ago} bar(s) ago — still fresh. Size it on the "
                         "Execute page (auto-lot from balance × risk%); the app never "
                         "places orders itself.")
    else:
        setup["status"] = "wait"
        setup["note"] = (f"Last signal was {bars_ago} bars ago — stale. Wait for the next "
                         "one; the forward test will catch it as it fires.")
    return setup


def build_plan(symbol: str, timeframe: str = "1h", target_r: float = 2.0) -> Dict:
    """The full 'plan my trading' pipeline for one symbol/timeframe."""
    symbol = symbol.upper()
    candles = market_service.get_history(symbol, timeframe, 5000, history_range="1y")
    if not candles or len(candles) < 250:
        return {"error": "Not enough broker history to plan from — is the MT5 bridge connected?"}
    if history_is_synthetic(candles):
        return {"error": "Market data feed unavailable (would be simulated) — refusing to plan on fake data."}

    regime = detect_regime(candles)
    allowed = _REGIME_STYLES.get(regime["regime"], set())

    # Evidence: every strategy on THESE candles, net of costs (fair ICT row).
    compare = compare_strategies(symbol, timeframe, target_r, "1y",
                                 ict_min_confluence=4, ict_atr_stop=True,
                                 _candles=candles)
    rows = compare.get("strategies", []) if not compare.get("error") else []
    qualified = [r for r in rows
                 if (r.get("expectancy_r") or 0) > 0
                 and r.get("trades", 0) >= _MIN_TRADES
                 and r.get("style") in allowed]
    profitable_wrong_style = [r for r in rows
                              if (r.get("expectancy_r") or 0) > 0
                              and r.get("trades", 0) >= _MIN_TRADES
                              and r.get("style") not in allowed]

    plan: Dict = {
        "symbol": symbol, "timeframe": timeframe, "target_r": target_r,
        "candles_analysed": len(candles),
        "regime": regime,
        "evidence": rows,          # the full ranked table backs every claim
        "caveats": [
            "Regime + expectancy describe the last ~5000 bars — a regime flip invalidates the pick.",
            "Costs modelled (spread+commission) but not slippage.",
            f"Rows under {_MIN_TRADES} trades were never eligible.",
            "Forward-test the recommendation by name before real size; execution stays manual.",
        ],
    }

    if not qualified:
        plan["action"] = "STAND_ASIDE"
        reason = (f"Regime is {regime['regime']} and no {'/'.join(sorted(allowed)) or 'any'}-style "
                  f"strategy shows positive after-cost expectancy with ≥{_MIN_TRADES} trades here.")
        if profitable_wrong_style:
            names = ", ".join(r["label"] for r in profitable_wrong_style[:3])
            reason += (f" ({names} measured positive, but their style doesn't fit this regime — "
                       "chasing that mismatch is how backtest winners lose live.)")
        plan["reason"] = reason
        return plan

    best = qualified[0]                     # compare rows arrive expectancy-sorted
    plan["action"] = "TRADE_CANDIDATE"
    plan["recommendation"] = {
        "strategy": best["strategy"], "label": best["label"], "style": best["style"],
        "why": (f"{regime['regime'].replace('_', ' ')} regime (ADX {regime['adx']}, "
                f"ER {regime['efficiency_ratio']}) fits {best['style']} — and on these exact "
                f"candles it measured +{best['expectancy_r']}R/trade after costs over "
                f"{best['trades']} trades (win rate {best['win_rate']}%, "
                f"max drawdown {best['max_drawdown_r']}R)."),
        "expectancy_r": best["expectancy_r"], "trades": best["trades"],
        "win_rate": best["win_rate"], "max_drawdown_r": best["max_drawdown_r"],
    }
    if len(qualified) > 1:
        plan["alternatives"] = [{"label": r["label"], "expectancy_r": r["expectancy_r"],
                                 "trades": r["trades"]} for r in qualified[1:3]]
    if best["strategy"] in STRATEGIES:
        plan["setup"] = _live_setup(candles, best["strategy"], target_r)
    else:
        plan["setup"] = {"status": "wait",
                         "note": "ICT confluence setups come from the Signals page checklist."}
    plan["risk_guidance"] = ("Risk ≤1% of account per trade. The Execute page auto-sizes lots "
                             "from balance × risk% at this stop distance.")
    return plan
