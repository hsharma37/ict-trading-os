"""
Analytics service — metrics, expectancy, session stats, and confluence scoring.

Will integrate with vectorbt and pandas for statistical analysis.
"""
from typing import List
from app.models.trade import Trade


def calculate_expectancy(trades: List[Trade]) -> dict:
    """
    Calculate trading expectancy:
    (Win Rate * Avg Win) - (Loss Rate * Avg Loss)
    """
    if not trades:
        return {"expectancy": 0, "win_rate": 0, "avg_win": 0, "avg_loss": 0, "total_trades": 0}

    closed = [t for t in trades if t.status == "closed" and t.outcome is not None]
    if not closed:
        return {"expectancy": 0, "win_rate": 0, "avg_win": 0, "avg_loss": 0, "total_trades": 0}

    wins = [t for t in closed if t.outcome == "win"]
    losses = [t for t in closed if t.outcome == "loss"]

    win_count = len(wins)
    loss_count = len(losses)
    total = win_count + loss_count

    win_rate = win_count / total if total > 0 else 0
    avg_win = sum(t.pnl for t in wins if t.pnl) / win_count if win_count > 0 else 0
    avg_loss = sum(abs(t.pnl) for t in losses if t.pnl) / loss_count if loss_count > 0 else 0

    expectancy = (win_rate * avg_win) - ((1 - win_rate) * avg_loss)

    return {
        "expectancy": round(expectancy, 2),
        "win_rate": round(win_rate * 100, 2),
        "avg_win": round(avg_win, 2),
        "avg_loss": round(avg_loss, 2),
        "total_trades": len(closed),
        "win_count": win_count,
        "loss_count": loss_count,
    }
