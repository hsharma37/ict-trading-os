"""Strategy Lab — classic open-source quant strategies on the SAME honest harness.

Every strategy here is a well-documented public-domain technique (sources noted
per strategy). They all emit signals in the exact shape the ICT backtester's
`_evaluate` expects, so every one is measured identically: net of estimated
spread+commission, limit-fill semantics, one-trade-at-a-time, conservative
stop-first on ambiguous bars. That makes results comparable with each other AND
with the ICT confluence strategy — same data, same costs, same referee.

Stops are 1.5×ATR(14) — a standard volatility stop — and the target is
`target_r` × risk, so R-multiples mean the same thing across strategies.
"""
from __future__ import annotations

from datetime import datetime
from typing import Dict, List, Optional

import numpy as np

from app.services.market_data import market_service, history_is_synthetic
from app.services import backtest_service as bt


# ── indicator helpers (numpy, no deps) ──────────────────────────────

def _sma(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) >= n:
        c = np.cumsum(np.insert(x, 0, 0.0))
        out[n - 1:] = (c[n:] - c[:-n]) / n
    return out


def _ema(x: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(x), np.nan)
    if len(x) < n:
        return out
    k = 2.0 / (n + 1)
    out[n - 1] = x[:n].mean()
    for i in range(n, len(x)):
        out[i] = x[i] * k + out[i - 1] * (1 - k)
    return out


def _rsi(close: np.ndarray, n: int) -> np.ndarray:
    out = np.full(len(close), np.nan)
    if len(close) <= n:
        return out
    delta = np.diff(close)
    gain = np.where(delta > 0, delta, 0.0)
    loss = np.where(delta < 0, -delta, 0.0)
    ag, al = gain[:n].mean(), loss[:n].mean()
    for i in range(n, len(delta)):
        ag = (ag * (n - 1) + gain[i]) / n
        al = (al * (n - 1) + loss[i]) / n
        out[i + 1] = 100.0 if al == 0 else 100.0 - 100.0 / (1.0 + ag / al)
    return out


def _atr(high: np.ndarray, low: np.ndarray, close: np.ndarray, n: int = 14) -> np.ndarray:
    tr = np.maximum(high[1:] - low[1:],
                    np.maximum(abs(high[1:] - close[:-1]), abs(low[1:] - close[:-1])))
    out = np.full(len(close), np.nan)
    if len(tr) >= n:
        out[n] = tr[:n].mean()
        for i in range(n, len(tr)):
            out[i + 1] = (out[i] * (n - 1) + tr[i]) / n
    return out


# ── strategy signal generators ──────────────────────────────────────
# Each returns a list of (bar_index, long?) entry events.

def _sig_sma_cross(o, h, l, c):
    fast, slow = _sma(c, 20), _sma(c, 50)
    for i in range(51, len(c)):
        if np.isnan(fast[i]) or np.isnan(slow[i]):
            continue
        if fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]:
            yield i, True
        elif fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]:
            yield i, False


def _sig_ema_cross(o, h, l, c):
    fast, slow = _ema(c, 12), _ema(c, 26)
    for i in range(27, len(c)):
        if np.isnan(fast[i]) or np.isnan(slow[i]) or np.isnan(fast[i - 1]) or np.isnan(slow[i - 1]):
            continue
        if fast[i - 1] <= slow[i - 1] and fast[i] > slow[i]:
            yield i, True
        elif fast[i - 1] >= slow[i - 1] and fast[i] < slow[i]:
            yield i, False


def _sig_rsi2(o, h, l, c):
    # Connors: RSI(2) extreme, traded WITH the long-term trend (SMA200 filter).
    r2, trend = _rsi(c, 2), _sma(c, 200)
    for i in range(201, len(c)):
        if np.isnan(r2[i]) or np.isnan(trend[i]):
            continue
        if r2[i] < 10 and c[i] > trend[i]:
            yield i, True
        elif r2[i] > 90 and c[i] < trend[i]:
            yield i, False


def _sig_bollinger(o, h, l, c):
    mid = _sma(c, 20)
    for i in range(21, len(c)):
        if np.isnan(mid[i]):
            continue
        sd = np.std(c[i - 19:i + 1])
        if sd == 0:
            continue
        if c[i] < mid[i] - 2 * sd:
            yield i, True     # revert up toward the mean
        elif c[i] > mid[i] + 2 * sd:
            yield i, False    # revert down


def _sig_donchian(o, h, l, c):
    # Turtle-style 20-bar channel breakout.
    for i in range(21, len(c)):
        hh = h[i - 20:i].max()
        ll = l[i - 20:i].min()
        if c[i] > hh:
            yield i, True
        elif c[i] < ll:
            yield i, False


def _sig_momentum(o, h, l, c):
    # 10-bar rate-of-change with SMA50 regime filter.
    trend = _sma(c, 50)
    for i in range(51, len(c)):
        if np.isnan(trend[i]):
            continue
        roc = (c[i] - c[i - 10]) / c[i - 10]
        if roc > 0.002 and c[i] > trend[i]:
            yield i, True
        elif roc < -0.002 and c[i] < trend[i]:
            yield i, False


STRATEGIES: Dict[str, Dict] = {
    "sma_cross": {"label": "SMA 20/50 cross", "style": "trend",
                  "source": "Classic moving-average crossover (textbook trend following)",
                  "fn": _sig_sma_cross},
    "ema_cross": {"label": "EMA 12/26 cross", "style": "trend",
                  "source": "MACD-line crossover family (Appel)",
                  "fn": _sig_ema_cross},
    "rsi2": {"label": "RSI(2) mean reversion", "style": "mean-reversion",
             "source": "Larry Connors' RSI-2 pullback, SMA200 trend filter",
             "fn": _sig_rsi2},
    "bollinger": {"label": "Bollinger band revert", "style": "mean-reversion",
                  "source": "Bollinger (20, 2σ) band-touch mean reversion",
                  "fn": _sig_bollinger},
    "donchian": {"label": "Donchian 20 breakout", "style": "breakout",
                 "source": "Turtle Traders 20-bar channel breakout (Dennis/Eckhardt)",
                 "fn": _sig_donchian},
    "momentum": {"label": "10-bar momentum", "style": "trend",
                 "source": "Time-series momentum (Moskowitz/Ooi/Pedersen family)",
                 "fn": _sig_momentum},
}


def list_strategies() -> List[Dict]:
    return [{"key": k, "label": v["label"], "style": v["style"], "source": v["source"]}
            for k, v in STRATEGIES.items()]


def _to_bt_signals(candles: List[Dict], events, atr: np.ndarray) -> List[Dict]:
    """Convert (index, long) events into the backtester's signal shape with a
    1.5×ATR volatility stop — so `_evaluate` applies identical fill/cost rules."""
    sigs: List[Dict] = []
    for i, long in events:
        if i >= len(candles) - 1 or np.isnan(atr[i]) or atr[i] <= 0:
            continue
        entry = candles[i]["close"]
        risk = 1.5 * float(atr[i])
        sl = entry - risk if long else entry + risk
        t = candles[i].get("time")
        try:
            hour = datetime.utcfromtimestamp(int(t)).hour if t else 12
        except (TypeError, ValueError, OSError):
            hour = 12
        sigs.append({"i": i, "long": bool(long), "entry": float(entry), "sl": float(sl),
                     "risk": risk, "hour": hour, "confluence": 0, "trend_ok": True})
    return sigs


def run_strategy_backtest(symbol: str, strategy: str, timeframe: str = "1h",
                          target_r: float = 2.0, history_range: str = "1y",
                          _candles: Optional[List[Dict]] = None) -> Dict:
    """Backtest one classic strategy on broker candles, net of costs — the same
    referee as the ICT backtest so results are directly comparable."""
    meta = STRATEGIES.get(strategy)
    if not meta:
        return {"error": f"Unknown strategy '{strategy}'. One of: {', '.join(STRATEGIES)}"}
    candles = _candles if _candles is not None else market_service.get_history(
        symbol, timeframe, 5000, history_range=history_range)
    if not candles or len(candles) < 60:
        return {"error": "Not enough historical data — is the MT5 bridge connected?"}
    if history_is_synthetic(candles):
        return {"error": "Market data feed unavailable (would be simulated) — cannot backtest."}

    o = np.array([c["open"] for c in candles]); h = np.array([c["high"] for c in candles])
    l = np.array([c["low"] for c in candles]); c_ = np.array([c["close"] for c in candles])
    atr = _atr(h, l, c_, 14)
    sigs = _to_bt_signals(candles, meta["fn"](o, h, l, c_), atr)
    cost = bt._round_trip_cost_price(symbol)
    trades = bt._evaluate(candles, sigs, target_r, 8, 48, False, False, cost)
    closed = [t for t in trades if not t.get("open")]
    summary = bt._summarize_backtest(symbol, timeframe, target_r, history_range, len(candles), closed)
    summary.update({
        "strategy": strategy, "strategy_label": meta["label"], "style": meta["style"],
        "source": meta["source"], "stop_model": "1.5×ATR(14)",
        "signals_found": len(sigs),
    })
    return summary


def compare_strategies(symbol: str, timeframe: str = "1h", target_r: float = 2.0,
                       history_range: str = "1y") -> Dict:
    """Run every strategy (plus the ICT confluence baseline) on the same candles
    and rank by expectancy — one table, one referee."""
    candles = market_service.get_history(symbol, timeframe, 5000, history_range=history_range)
    if not candles or len(candles) < 60:
        return {"error": "Not enough historical data — is the MT5 bridge connected?"}
    if history_is_synthetic(candles):
        return {"error": "Market data feed unavailable (would be simulated) — cannot compare."}
    rows = []
    for key in STRATEGIES:
        r = run_strategy_backtest(symbol, key, timeframe, target_r, history_range, _candles=candles)
        if not r.get("error"):
            rows.append({"strategy": key, "label": r["strategy_label"], "style": r["style"],
                         "trades": r.get("trades", 0), "win_rate": r.get("win_rate"),
                         "expectancy_r": r.get("expectancy_r"), "total_r": r.get("total_r"),
                         "max_drawdown_r": r.get("max_drawdown_r")})
    # ICT confluence baseline on the same candles, same costs.
    try:
        sigs = bt._scan_signals(candles, symbol, timeframe, 100, 2)
        trades = bt._evaluate(candles, sigs, target_r, 8, 48, False, False,
                              bt._round_trip_cost_price(symbol))
        closed = [t for t in trades if not t.get("open")]
        s = bt._summarize_backtest(symbol, timeframe, target_r, history_range, len(candles), closed)
        rows.append({"strategy": "ict_confluence", "label": "ICT confluence (baseline)",
                     "style": "ict", "trades": s.get("trades", 0), "win_rate": s.get("win_rate"),
                     "expectancy_r": s.get("expectancy_r"), "total_r": s.get("total_r"),
                     "max_drawdown_r": s.get("max_drawdown_r")})
    except Exception:
        pass
    rows.sort(key=lambda r: (r["expectancy_r"] is None, -(r["expectancy_r"] or 0)))
    return {"symbol": symbol.upper(), "timeframe": timeframe, "target_r": target_r,
            "history_range": history_range, "candles": len(candles), "strategies": rows,
            "note": ("All strategies measured on the same broker candles, net of estimated "
                     "spread+commission, 1.5×ATR stop, one-trade-at-a-time. Expectancy > 0 "
                     "after costs is the bar — most public strategies fail it on FX intraday.")}
