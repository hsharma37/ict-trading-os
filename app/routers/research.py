"""Research Router — Instrument technical analysis and market overview."""
from fastapi import APIRouter, HTTPException
from pydantic import BaseModel
from typing import Optional, List
from app.services.research_service import research_service
from app.services.instrument_config import get_instrument, get_all_instruments
from app.services.mt5_trades_service import mt5_trades_service
from app.services import backtest_service

router = APIRouter(prefix="/research", tags=["Research"])


@router.get("/instrument/{symbol}")
def analyze_instrument(symbol: str):
    """Get full technical analysis for an instrument."""
    try:
        result = research_service.analyze_instrument(symbol)
        if result.get("error"):
            raise HTTPException(status_code=404, detail=result.get("error"))
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/all")
def analyze_all():
    """Get analysis for all instruments."""
    try:
        return {"instruments": research_service.analyze_all()}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/correlation")
def get_correlation():
    """Get correlation matrix between instruments."""
    try:
        return research_service.get_correlation_matrix()
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/summary")
def get_market_summary():
    """Get market-wide summary, annotated with the user's live MT5 holdings."""
    try:
        summary = research_service.get_market_summary()
        if isinstance(summary, dict) and mt5_trades_service.is_active():
            summary["open_positions"] = mt5_trades_service.get_open_trades()
        return summary
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/instruments")
def list_instruments():
    """List all available instruments with config."""
    return {"instruments": get_all_instruments()}


@router.get("/backtest/{symbol}")
def backtest(symbol: str, timeframe: str = "1h", target_r: float = 2.0, history_range: str = "1y"):
    """Walk-forward backtest of the ICT signal logic over historical candles.
    Returns win rate, expectancy (R), profit factor, drawdown, and the R-series."""
    try:
        if target_r <= 0 or target_r > 10:
            raise HTTPException(status_code=400, detail="target_r must be between 0 and 10.")
        result = backtest_service.run_backtest(symbol, timeframe=timeframe,
                                               target_r=target_r, history_range=history_range)
        if result.get("error"):
            raise HTTPException(status_code=422, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/calibrate/{symbol}")
def calibrate_strength(symbol: str, timeframe: str = "1h", target_r: float = 3.0):
    """Measured historical win rate + expectancy for each signal-strength tier —
    turns 'STRONG/MODERATE/WEAK' into real, cost-adjusted numbers."""
    try:
        result = backtest_service.calibrate_strength(symbol, timeframe=timeframe, target_r=target_r)
        if result.get("error"):
            raise HTTPException(status_code=422, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/sweep/{symbol}")
def parameter_sweep(symbol: str, timeframe: str = "1h", history_range: str = "1y"):
    """Grid-search target-R × session × trend filters to find whether ANY config
    has a positive edge, with an out-of-sample check to expose curve-fitting."""
    try:
        result = backtest_service.run_sweep(symbol, timeframe=timeframe, history_range=history_range)
        if result.get("error"):
            raise HTTPException(status_code=422, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


@router.get("/honest-test/{symbol}")
def honest_test(symbol: str, timeframe: str = "1h", history_range: str = "1y"):
    """Walk-forward validation: pick the best config on the first 60% of history,
    lock it, and report performance ONLY on the untouched last 40%."""
    try:
        result = backtest_service.run_honest_test(symbol, timeframe=timeframe, history_range=history_range)
        if result.get("error"):
            raise HTTPException(status_code=422, detail=result["error"])
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


class MonteCarloRequest(BaseModel):
    r_values: Optional[List[float]] = None      # explicit outcomes, else derived from `source`
    source: Optional[str] = None                # "backtest:<SYMBOL>" or "journal"
    n_sims: int = 1000
    horizon: Optional[int] = None
    risk_per_trade_pct: float = 1.0
    start_equity: float = 10000.0
    ruin_drawdown_pct: float = 50.0
    timeframe: str = "1h"
    target_r: float = 2.0


@router.post("/monte-carlo")
def monte_carlo(body: MonteCarloRequest):
    """Monte Carlo on a set of trade R-outcomes — backtest results, the real
    journal, or an explicit list. Shows the distribution of outcomes luck can
    produce from the same edge (percentile returns, drawdown, risk of ruin)."""
    try:
        r_values = body.r_values
        origin = "explicit"
        if not r_values and body.source:
            if body.source.lower().startswith("backtest"):
                sym = body.source.split(":", 1)[1] if ":" in body.source else "EURUSD"
                bt = backtest_service.run_backtest(sym, timeframe=body.timeframe, target_r=body.target_r)
                if bt.get("error"):
                    raise HTTPException(status_code=422, detail=bt["error"])
                r_values = bt.get("r_values", [])
                origin = f"backtest:{sym.upper()}"
            elif body.source.lower() == "journal":
                from app.services.trade_journal_service import trade_journal_service
                rows = trade_journal_service.list_trades(limit=100000)
                r_values = [float(r["r"]) for r in rows if r.get("r") is not None]
                origin = "journal (real trades)"
        if not r_values:
            raise HTTPException(status_code=422, detail="No trade outcomes to simulate. Run a backtest first or provide r_values.")
        if body.n_sims < 100 or body.n_sims > 20000:
            raise HTTPException(status_code=400, detail="n_sims must be between 100 and 20000.")
        result = backtest_service.monte_carlo(
            r_values, n_sims=body.n_sims, horizon=body.horizon,
            risk_per_trade_pct=body.risk_per_trade_pct, start_equity=body.start_equity,
            ruin_drawdown_pct=body.ruin_drawdown_pct,
        )
        if result.get("error"):
            raise HTTPException(status_code=422, detail=result["error"])
        result["origin"] = origin
        return result
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
