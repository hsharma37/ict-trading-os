"""Quantitative analysis service."""
import numpy as np
from typing import List, Dict, Optional
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP

try:
    from scipy import stats
    HAS_SCIPY = True
except ImportError:
    HAS_SCIPY = False
    stats = None

class QuantService:
    def _decimal(self, value) -> Decimal:
        try:
            return Decimal(str(value))
        except (InvalidOperation, ValueError):
            return Decimal("0")

    def calculate_kelly(self, returns: List[float]) -> Dict:
        n = len(returns)
        if n == 0:
            return {
                "n": 0,
                "win_rate": 0,
                "win_pct": 0,
                "loss_pct": 0,
                "avg_win": 0,
                "avg_loss": 0,
                "payoff_ratio": 0,
                "kelly_fraction": 0,
                "kelly_pct": 0,
                "kelly_half": 0,
                "half_kelly": 0,
                "quarter_kelly": 0,
            }
        values = [self._decimal(value) for value in returns]
        wins = [value for value in values if value > 0]
        losses = [value for value in values if value < 0]
        win_rate = Decimal(len(wins)) / Decimal(n)
        avg_win = sum(wins, Decimal("0")) / Decimal(len(wins)) if wins else Decimal("0")
        avg_loss_abs = abs(sum(losses, Decimal("0")) / Decimal(len(losses))) if losses else Decimal("0")
        payoff = avg_win / avg_loss_abs if avg_loss_abs > 0 else Decimal("0")
        kelly = win_rate - ((Decimal("1") - win_rate) / payoff) if payoff > 0 else Decimal("0")
        kelly = max(Decimal("0"), min(Decimal("1"), kelly))
        q4 = Decimal("0.0001")
        q2 = Decimal("0.01")
        return {
            "n": n,
            "win_rate": float(win_rate.quantize(q4, rounding=ROUND_HALF_UP)),
            "win_pct": float((win_rate * 100).quantize(q2, rounding=ROUND_HALF_UP)),
            "loss_pct": float(((Decimal("1") - win_rate) * 100).quantize(q2, rounding=ROUND_HALF_UP)),
            "avg_win": float(avg_win.quantize(q2, rounding=ROUND_HALF_UP)),
            "avg_loss": float(avg_loss_abs.quantize(q2, rounding=ROUND_HALF_UP)),
            "payoff_ratio": float(payoff.quantize(q2, rounding=ROUND_HALF_UP)) if payoff > 0 else 0,
            "kelly_fraction": float(kelly.quantize(q4, rounding=ROUND_HALF_UP)),
            "kelly_pct": float((kelly * 100).quantize(q2, rounding=ROUND_HALF_UP)),
            "kelly_half": float((kelly / 2).quantize(q4, rounding=ROUND_HALF_UP)),
            "half_kelly": float((kelly * 50).quantize(q2, rounding=ROUND_HALF_UP)),
            "quarter_kelly": float((kelly * 25).quantize(q2, rounding=ROUND_HALF_UP)),
        }

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

        skew = stats.skew(returns) if n > 2 and HAS_SCIPY else None
        kurt = stats.kurtosis(returns) if n > 2 and HAS_SCIPY else None

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
        kelly = self.calculate_kelly(returns)
        if not kelly["avg_win"] or not kelly["avg_loss"]:
            return None
        return kelly

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
