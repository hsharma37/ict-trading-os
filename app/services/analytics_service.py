"""Analytics service for trade performance metrics."""
from typing import Dict, List
from app.core.database import db
from app.services.trade_lifecycle_service import trade_lifecycle_service, utc_now_iso


class AnalyticsService:
    """Comprehensive analytics for trading performance."""

    def get_summary(self) -> Dict:
        """Get full analytics summary."""
        stats = trade_lifecycle_service.get_trade_stats()
        kelly = trade_lifecycle_service.get_kelly_criterion()
        return {
            "summary": stats,
            "kelly": kelly,
            "timestamp": utc_now_iso(),
        }

    def get_expectancy(self) -> Dict:
        """Get expectancy metrics."""
        stats = trade_lifecycle_service.get_trade_stats()
        return {
            "expectancy": stats.get("expectancy", 0),
            "win_rate": stats.get("win_rate", 0),
            "avg_win": stats.get("avg_win", 0),
            "avg_loss": stats.get("avg_loss", 0),
            "total_trades": stats.get("closed_trades", 0),
            "win_count": stats.get("winning_trades", 0),
            "loss_count": stats.get("losing_trades", 0),
            "r_factor": stats.get("avg_r", 0),
            "total_pnl": stats.get("total_pnl", 0),
            "source": stats.get("source", "ledger"),
            "stats_basis": stats.get("stats_basis"),
        }

    def get_heatmap(self) -> Dict:
        """Get session performance heatmap."""
        stats = trade_lifecycle_service.get_trade_stats()
        return {"sessions": stats.get("sessions", {})}

    def get_drawdown(self) -> Dict:
        """Get drawdown and equity curve."""
        stats = trade_lifecycle_service.get_trade_stats()
        return {
            "max_drawdown": stats.get("max_drawdown", 0),
            "max_drawdown_duration": stats.get("max_drawdown_duration", 0),
            "equity_curve": stats.get("equity_curve", []),
        }

    def get_kelly(self) -> Dict:
        """Get Kelly criterion."""
        return trade_lifecycle_service.get_kelly_criterion()

    def get_symbols(self) -> Dict:
        """Get per-symbol performance."""
        stats = trade_lifecycle_service.get_trade_stats()
        return {"symbols": stats.get("by_symbol", {})}

    def get_monthly(self) -> Dict:
        """Get monthly performance breakdown."""
        stats = trade_lifecycle_service.get_trade_stats()
        return {"monthly": stats.get("monthly", {})}

    def get_recent(self, limit: int = 10) -> List[Dict]:
        """Get recent trades."""
        return trade_lifecycle_service.get_recent_trades(limit)


analytics_service = AnalyticsService()
