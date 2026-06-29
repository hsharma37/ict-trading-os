"""
Research service — backtesting and quantitative analysis.

Supports vectorbt (fast backtesting), Backtrader (event-driven),
and Monte Carlo simulation for risk-of-ruin analysis.
"""
from typing import Any
from datetime import datetime
import numpy as np
import pandas as pd

try:
    import vectorbt as vbt
except ImportError:  # pragma: no cover
    vbt = None

try:
    import backtrader as bt
except ImportError:  # pragma: no cover
    bt = None


def _generate_synthetic_data(symbol: str, start: str, end: str, timeframe: str = "1h") -> pd.DataFrame:
    """Generate synthetic OHLCV data for backtesting demonstrations."""
    np.random.seed(hash(symbol) % 2**32)
    freq_map = {"1m": "min", "5m": "5min", "15m": "15min", "1h": "h", "4h": "4h", "1d": "D"}
    freq = freq_map.get(timeframe, "h")
    days = pd.date_range(start=start, end=end, freq=freq)
    n = len(days)

    returns = np.random.randn(n) * 0.005
    price = 100 * np.exp(np.cumsum(returns))

    df = pd.DataFrame({
        "open": price * (1 + np.random.randn(n) * 0.001),
        "high": price * (1 + np.abs(np.random.randn(n)) * 0.003 + 0.001),
        "low": price * (1 - np.abs(np.random.randn(n)) * 0.003 - 0.001),
        "close": price * (1 + np.random.randn(n) * 0.001),
        "volume": np.random.randint(1000, 100000, n),
    }, index=days)
    return df


class SmaCross(bt.SignalStrategy):
    params = (("fast", 10), ("slow", 30))

    def __init__(self):
        sma_fast = bt.ind.SMA(period=self.p.fast)
        sma_slow = bt.ind.SMA(period=self.p.slow)
        self.signal_add(bt.SIGNAL_LONG, bt.ind.CrossOver(sma_fast, sma_slow))


def run_vectorbt_backtest(config: dict[str, Any]) -> dict[str, Any]:
    if vbt is None:
        return {
            "error": "vectorbt is not installed",
            "required": "vectorbt>=0.26.0",
        }

    symbol = config.get("symbol", "SYNTH")
    start = config.get("start", "2024-01-01")
    end = config.get("end", "2024-06-01")
    params = config.get("params", {})

    df = _generate_synthetic_data(symbol, start, end, params.get("timeframe", "1h"))
    fast = params.get("fast", 10)
    slow = params.get("slow", 30)

    fast_ma = df["close"].rolling(window=fast).mean()
    slow_ma = df["close"].rolling(window=slow).mean()

    entries = fast_ma > slow_ma
    exits = fast_ma < slow_ma

    pf = vbt.Portfolio.from_signals(
        df["close"], entries=entries, exits=exits,
        init_cash=10000, fees=0.001, slippage=0.0005
    )

    total_trades = int(pf.trades.count()) if hasattr(pf.trades, "count") else 0
    win_rate = float(pf.trades.win_rate()) if total_trades > 0 and hasattr(pf.trades, "win_rate") else 0.0

    return {
        "status": "completed",
        "symbol": symbol,
        "strategy": "SMA Crossover",
        "params": {"fast": fast, "slow": slow},
        "metrics": {
            "total_return": float(pf.total_return()),
            "sharpe_ratio": float(pf.sharpe_ratio()),
            "max_drawdown": float(pf.max_drawdown()),
            "total_trades": total_trades,
            "win_rate": win_rate,
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def run_monte_carlo(config: dict[str, Any]) -> dict[str, Any]:
    """Run Monte Carlo simulation for trade sequence risk analysis."""
    trials = config.get("trials", 1000)
    scenario = config.get("scenario", {})

    win_rate = scenario.get("win_rate", 0.55)
    avg_win = scenario.get("avg_win", 150)
    avg_loss = scenario.get("avg_loss", 100)
    num_trades = scenario.get("num_trades", 100)
    initial_capital = scenario.get("initial_capital", 10000)

    np.random.seed(42)
    results = []
    for _ in range(trials):
        capital = initial_capital
        for _ in range(num_trades):
            if np.random.random() < win_rate:
                capital += avg_win
            else:
                capital -= avg_loss
            if capital <= 0:
                break
        results.append(capital)

    results = np.array(results)

    return {
        "status": "completed",
        "trials": trials,
        "scenario": scenario,
        "summary": {
            "median_final_capital": float(np.median(results)),
            "mean_final_capital": float(np.mean(results)),
            "probability_of_ruin": float(np.mean(results <= 0)),
            "probability_of_profit": float(np.mean(results > initial_capital)),
            "percentile_5": float(np.percentile(results, 5)),
            "percentile_95": float(np.percentile(results, 95)),
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }


def run_backtrader_strategy(config: dict[str, Any]) -> dict[str, Any]:
    if bt is None:
        return {
            "error": "backtrader is not installed",
            "required": "backtrader>=1.9.76.123",
        }

    symbol = config.get("symbol", "SYNTH")
    start = config.get("start", "2024-01-01")
    end = config.get("end", "2024-06-01")
    params = config.get("params", {})

    df = _generate_synthetic_data(symbol, start, end, params.get("timeframe", "1h"))
    df_feed = bt.feeds.PandasData(dataname=df)

    cerebro = bt.Cerebro()
    cerebro.addstrategy(SmaCross, fast=params.get("fast", 10), slow=params.get("slow", 30))
    cerebro.adddata(df_feed)
    cerebro.broker.setcash(10000.0)
    cerebro.broker.setcommission(commission=0.001)

    start_value = cerebro.broker.getvalue()
    cerebro.run()
    end_value = cerebro.broker.getvalue()
    total_return = (end_value - start_value) / start_value if start_value > 0 else 0.0

    return {
        "status": "completed",
        "symbol": symbol,
        "strategy": "SMA Crossover",
        "params": params,
        "metrics": {
            "start_value": start_value,
            "end_value": end_value,
            "total_return": total_return,
        },
        "generated_at": datetime.utcnow().isoformat() + "Z",
    }
