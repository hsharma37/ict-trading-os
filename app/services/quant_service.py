"""Quantitative analysis service."""
import numpy as np
from typing import List, Dict, Optional
from scipy import stats

class QuantService:
    def compute_metrics(self, trades: List[Dict]) -> Dict:
        if len(trades) < 2:
            return {"n_trades": len(trades), "message": "Need at least 2 closed trades"}

        returns = np.array([t.get("realized_pnl", 0) for t in trades])
        n = len(returns)
        mean = np.mean(returns)
        std = np.std(returns, ddof=1)
        total = np.sum(returns)
        wins = returns[returns > 0]
        win_rate = len(wins) / n if n > 0 else 0

        sharpe = mean / std if std > 0 else None
        downside = returns[returns < 0]
        downside_std = np.std(downside, ddof=1) if len(downside) > 0 else 0
        sortino = mean / downside_std if downside_std > 0 else None

        equity = np.cumsum(returns)
        peak = np.maximum.accumulate(equity)
        dd = peak - equity
        max_dd = np.max(dd)
        calmar = total / max_dd if max_dd > 0 else None

        sorted_r = np.sort(returns)
        var_idx = max(0, int(n * 0.05))
        var_95 = sorted_r[var_idx]
        tail = sorted_r[:var_idx + 1]
        cvar_95 = np.mean(tail) if len(tail) > 0 else var_95

        skew = stats.skew(returns) if n > 2 else None
        kurt = stats.kurtosis(returns) if n > 2 else None

        return {
            "n_trades": n, "sharpe_ratio": round(sharpe, 3) if sharpe else None,
            "sortino_ratio": round(sortino, 3) if sortino else None,
            "calmar_ratio": round(calmar, 3) if calmar else None,
            "max_drawdown": round(max_dd, 2), "var_95": round(var_95, 2),
            "cvar_95": round(cvar_95, 2), "win_rate": round(win_rate * 100, 1),
            "avg_r": round(mean, 2), "total_pnl": round(total, 2),
            "skewness": round(skew, 3) if skew else None,
            "kurtosis": round(kurt, 3) if kurt else None,
            "equity_curve": equity.tolist(), "return_distribution": returns.tolist()
        }

    def compute_kelly(self, trades: List[Dict]) -> Optional[Dict]:
        if len(trades) < 5: return None
        returns = [t.get("realized_pnl", 0) for t in trades]
        wins = [r for r in returns if r > 0]
        losses = [r for r in returns if r <= 0]
        if not wins or not losses: return None
        n = len(returns)
        win_pct = len(wins) / n
        avg_win = np.mean(wins)
        avg_loss = abs(np.mean(losses))
        payoff = avg_win / avg_loss if avg_loss > 0 else 0
        kelly = win_pct - ((1 - win_pct) / payoff) if payoff > 0 else 0
        return {
            "win_pct": round(win_pct * 100, 1), "loss_pct": round((1 - win_pct) * 100, 1),
            "avg_win": round(avg_win, 2), "avg_loss": round(avg_loss, 2),
            "payoff_ratio": round(payoff, 2), "kelly_pct": round(kelly * 100, 2),
            "half_kelly": round(kelly * 50, 2), "quarter_kelly": round(kelly * 25, 2), "n": n
        }

    def monte_carlo(self, trades: List[Dict], n_sims: int = 1000, n_trades: int = 100) -> Dict:
        if len(trades) < 5: return {"error": "Need 5+ trades"}
        returns = np.array([t.get("realized_pnl", 0) for t in trades])
        sims = []
        for _ in range(n_sims):
            sampled = np.random.choice(returns, size=n_trades, replace=True)
            equity = np.cumsum(sampled)
            sims.append(equity)
        sims = np.array(sims)
        final = sims[:, -1]
        max_dds = []
        for sim in sims:
            peak = np.maximum.accumulate(sim)
            max_dds.append(np.max(peak - sim))
        return {
            "n_simulations": n_sims, "median_final": round(np.median(final), 2),
            "mean_final": round(np.mean(final), 2), "p5": round(np.percentile(final, 5), 2),
            "p95": round(np.percentile(final, 95), 2),
            "prob_profit": round(np.mean(final > 0) * 100, 1),
            "median_max_dd": round(np.median(max_dds), 2)
        }

    def coach(self, trades: List[Dict]) -> List[Dict]:
        if len(trades) < 3:
            return [{"severity": "info", "metric": "Setup", "message": "Start trading to get coaching.", "action": "Execute your first trade."}]

        returns = np.array([t.get("realized_pnl", 0) for t in trades])
        wins = returns[returns > 0]
        win_rate = len(wins) / len(returns) if returns.size > 0 else 0

        recs = []
        if win_rate < 0.4:
            recs.append({"severity": "warning", "metric": "Win Rate", "message": f"Win rate at {win_rate*100:.0f}%.", "action": "Review entry confirmation before executing."})

        streak = 0
        for r in reversed(returns):
            if r < 0: streak += 1
            else: break
        if streak >= 3:
            recs.append({"severity": "warning", "metric": "Streak", "message": f"{streak} consecutive losses.", "action": "Take a break. Review setup quality."})

        if not recs:
            recs.append({"severity": "info", "metric": "Health", "message": "All metrics healthy. Keep executing your plan.", "action": "Maintain discipline."})
        return recs

quant_service = QuantService()
