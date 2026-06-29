"""
Analytics service — real metrics: expectancy, session heatmap, confluence, drawdown, Kelly.
"""
from typing import List, Any
from datetime import datetime
from app.models.trade import Trade


def calculate_expectancy(trades: List[Trade]) -> dict:
    """Calculate trading expectancy with R-factor."""
    if not trades:
        return {
            "expectancy": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "total_trades": 0,
            "r_factor": 0,
        }

    closed = [t for t in trades if t.status == "closed" and t.outcome is not None]
    if not closed:
        return {
            "expectancy": 0,
            "win_rate": 0,
            "avg_win": 0,
            "avg_loss": 0,
            "total_trades": 0,
            "r_factor": 0,
        }

    wins = [t for t in closed if t.outcome == "win"]
    losses = [t for t in closed if t.outcome == "loss"]

    win_count = len(wins)
    loss_count = len(losses)
    total = win_count + loss_count

    win_rate = win_count / total if total > 0 else 0
    avg_win = sum(t.pnl for t in wins if t.pnl) / win_count if win_count > 0 else 0
    avg_loss = sum(abs(t.pnl) for t in losses if t.pnl) / loss_count if loss_count > 0 else 0

    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    r_wins = [t.pnl_pips for t in wins if t.pnl_pips]
    r_losses = [abs(t.pnl_pips) for t in losses if t.pnl_pips]
    r_factor = (
        (sum(r_wins) / len(r_wins)) / (sum(r_losses) / len(r_losses))
        if r_wins and r_losses and sum(r_losses) > 0
        else 0.0
    )

    return {
        "expectancy": round(expectancy, 2),
        "win_rate": round(win_rate * 100, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "total_trades": len(closed),
        "win_count": win_count,
        "loss_count": loss_count,
        "r_factor": round(r_factor, 2),
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def calculate_heatmap(trades: List[Trade]) -> dict:
    """Session performance heatmap by time-of-day."""
    buckets: dict[str, dict[str, Any]] = {}
    for trade in trades:
        session = trade.entry_time.strftime("%H:%M") if trade.entry_time else "unknown"
        if session not in buckets:
            buckets[session] = {"count": 0, "wins": 0, "losses": 0, "pnl": 0.0}
        buckets[session]["count"] += 1
        pnl = trade.pnl or 0
        buckets[session]["pnl"] += pnl
        if pnl > 0:
            buckets[session]["wins"] += 1
        else:
            buckets[session]["losses"] += 1

    for session in buckets:
        count = buckets[session]["count"]
        buckets[session]["win_rate"] = buckets[session]["wins"] / count if count > 0 else 0.0

    return {
        "sessions": buckets,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def calculate_confluence(trades: List[Trade]) -> dict:
    """Score which confluence levels correlate with better performance."""
    scores: dict[int, dict[str, Any]] = {}
    for trade in trades:
        score = getattr(trade, "confluence_score", 0) or 0
        if score not in scores:
            scores[score] = {"count": 0, "wins": 0, "total_pnl": 0.0}
        scores[score]["count"] += 1
        pnl = trade.pnl or 0
        scores[score]["total_pnl"] += pnl
        if pnl > 0:
            scores[score]["wins"] += 1

    for score in scores:
        count = scores[score]["count"]
        scores[score]["win_rate"] = scores[score]["wins"] / count if count > 0 else 0.0
        scores[score]["avg_pnl"] = scores[score]["total_pnl"] / count if count > 0 else 0.0

    return {
        "confluence_scores": scores,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def calculate_drawdown(trades: List[Trade]) -> dict:
    """Calculate max drawdown and equity curve from trade history."""
    if not trades:
        return {
            "max_drawdown": 0.0,
            "max_drawdown_duration": 0,
            "equity_curve": [],
            "generated_at": datetime.utcnow().isoformat() + "Z",
        }

    sorted_trades = sorted(trades, key=lambda t: t.entry_time or datetime.min)
    equity = 0.0
    peak = 0.0
    max_dd = 0.0
    dd_start = 0
    max_dd_duration = 0
    equity_curve = []

    for i, trade in enumerate(sorted_trades):
        equity += trade.pnl or 0
        equity_curve.append({"trade": i + 1, "equity": round(equity, 2)})
        if equity > peak:
            peak = equity
            dd_start = i
        dd = peak - equity
        if dd > max_dd:
            max_dd = dd
            max_dd_duration = i - dd_start

    return {
        "max_drawdown": round(max_dd, 2),
        "max_drawdown_duration": max_dd_duration,
        "equity_curve": equity_curve,
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def calculate_kelly(trades: List[Trade]) -> dict:
    """Kelly Criterion optimal position sizing fraction."""
    closed = [t for t in trades if t.status == "closed" and t.outcome is not None]
    wins = [t for t in closed if t.outcome == "win"]
    losses = [t for t in closed if t.outcome == "loss"]
    total = len(wins) + len(losses)

    win_rate = len(wins) / total if total > 0 else 0.0
    avg_win = sum(t.pnl for t in wins if t.pnl) / len(wins) if wins else 0.0
    avg_loss = abs(sum(t.pnl for t in losses if t.pnl) / len(losses)) if losses else 0.0

    if total == 0 or avg_win == 0.0:
        fraction = 0.0
    elif not losses:
        fraction = 1.0
    else:
        odds = avg_win / avg_loss if avg_loss > 0 else 0.0
        fraction = win_rate - (1 - win_rate) / odds if odds > 0 else 0.0
    fraction = max(min(fraction, 1.0), 0.0)

    return {
        "win_rate": win_rate,
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "kelly_fraction": round(fraction, 4),
        "kelly_half": round(fraction / 2, 4),
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
