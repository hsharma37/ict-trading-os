"""ML baseline — walk-forward logistic regression on price features.

A deliberately simple, fully-transparent data-science baseline: can a linear
model on standard technical features predict the NEXT bar's direction better
than chance, out of sample? Implemented in pure numpy (no sklearn) so it runs
on the serverless deploy.

Honesty rules:
  • Walk-forward only — the model is refit on a rolling window and scored ONLY
    on bars it has never seen. No shuffling, no lookahead.
  • The verdict compares out-of-sample accuracy against the majority-class
    baseline (always guessing the more common direction), not against 50%.
  • ~52-55% OOS accuracy on FX bars is typical of weak/no edge; this is a
    research yardstick, NOT a signal generator.
"""
from __future__ import annotations

from typing import Dict, List, Optional

import numpy as np

from app.services.market_data import market_service, history_is_synthetic
from app.services.strategy_service import _sma, _rsi, _atr


def _features(candles: List[Dict]):
    """Feature matrix X[t] describing bar t, label y[t] = did bar t+1 close up."""
    c = np.array([x["close"] for x in candles])
    h = np.array([x["high"] for x in candles])
    l = np.array([x["low"] for x in candles])
    n = len(c)
    ret1 = np.zeros(n); ret1[1:] = np.diff(c) / c[:-1]
    def lag_ret(k):
        out = np.zeros(n); out[k:] = (c[k:] - c[:-k]) / c[:-k]; return out
    rsi = _rsi(c, 14)
    sma20 = _sma(c, 20)
    atr = _atr(h, l, c, 14)
    dist = np.where((~np.isnan(sma20)) & (~np.isnan(atr)) & (atr > 0),
                    (c - sma20) / np.where(atr > 0, atr, 1), 0.0)
    X = np.column_stack([
        ret1 * 100, lag_ret(3) * 100, lag_ret(5) * 100, lag_ret(10) * 100,
        np.nan_to_num(rsi, nan=50.0) / 100.0 - 0.5,
        np.clip(np.nan_to_num(dist), -5, 5),
    ])
    y = np.zeros(n); y[:-1] = (c[1:] > c[:-1]).astype(float)
    valid_from = 25  # first bar with all features defined
    return X[valid_from:-1], y[valid_from:-1]


def _fit_logistic(X: np.ndarray, y: np.ndarray, iters: int = 300, lr: float = 0.1):
    """Plain batch gradient-descent logistic regression with L2."""
    Xb = np.column_stack([np.ones(len(X)), X])
    w = np.zeros(Xb.shape[1])
    lam = 0.01
    for _ in range(iters):
        z = np.clip(Xb @ w, -30, 30)
        p = 1.0 / (1.0 + np.exp(-z))
        grad = Xb.T @ (p - y) / len(y) + lam * w
        w -= lr * grad
    return w


def _predict(w: np.ndarray, X: np.ndarray) -> np.ndarray:
    Xb = np.column_stack([np.ones(len(X)), X])
    z = np.clip(Xb @ w, -30, 30)
    return 1.0 / (1.0 + np.exp(-z))


def ml_baseline(symbol: str, timeframe: str = "1h", history_range: str = "1y",
                train_window: int = 400, test_step: int = 50) -> Dict:
    """Walk-forward next-bar direction prediction. Refits every `test_step` bars
    on the trailing `train_window`, scores only unseen bars."""
    candles = market_service.get_history(symbol, timeframe, 5000, history_range=history_range)
    if not candles or len(candles) < train_window + test_step + 30:
        return {"error": f"Not enough history for a walk-forward run (need ~{train_window + test_step + 30} bars) "
                         "— is the MT5 bridge connected?"}
    if history_is_synthetic(candles):
        return {"error": "Market data feed unavailable (would be simulated) — cannot evaluate."}

    X, y = _features(candles)
    n = len(X)
    preds: List[int] = []
    actual: List[int] = []
    folds = 0
    start = train_window
    while start + 1 < n:
        end = min(start + test_step, n)
        w = _fit_logistic(X[start - train_window:start], y[start - train_window:start])
        p = _predict(w, X[start:end])
        preds.extend((p > 0.5).astype(int).tolist())
        actual.extend(y[start:end].astype(int).tolist())
        folds += 1
        start = end

    if not preds:
        return {"error": "Walk-forward produced no out-of-sample predictions."}
    preds_a, actual_a = np.array(preds), np.array(actual)
    acc = float((preds_a == actual_a).mean())
    up_share = float(actual_a.mean())
    majority = max(up_share, 1 - up_share)
    edge = acc - majority
    hits_up = int(((preds_a == 1) & (actual_a == 1)).sum())
    hits_dn = int(((preds_a == 0) & (actual_a == 0)).sum())

    if edge > 0.03:
        verdict, tone = ("Beats the majority-class baseline by more than 3pp out of sample — rare; "
                         "verify on other symbols/timeframes before trusting it."), "good"
    elif edge > 0.01:
        verdict, tone = "Marginally above baseline — consistent with a weak, likely untradeable signal.", "warn"
    else:
        verdict, tone = ("No out-of-sample edge over always guessing the majority class — the honest, "
                         "expected result for a linear model on bare price features."), "bad"

    return {
        "symbol": symbol.upper(), "timeframe": timeframe, "history_range": history_range,
        "model": "logistic regression (6 features: lagged returns, RSI14, SMA20-distance in ATR)",
        "method": f"walk-forward: train {train_window} bars → predict next {test_step}, refit ({folds} folds)",
        "oos_predictions": len(preds),
        "oos_accuracy_pct": round(acc * 100, 1),
        "majority_baseline_pct": round(majority * 100, 1),
        "edge_pp": round(edge * 100, 1),
        "up_share_pct": round(up_share * 100, 1),
        "correct_up": hits_up, "correct_down": hits_dn,
        "verdict": verdict, "tone": tone,
        "caveat": ("Directional accuracy ignores costs and magnitude — even a real 2-3pp edge on "
                   "next-bar direction usually cannot pay the spread. Research yardstick, not a signal."),
    }
