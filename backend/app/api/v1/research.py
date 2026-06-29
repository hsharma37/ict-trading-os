from fastapi import APIRouter
from pydantic import BaseModel
from typing import Any
from app.services.research_service import run_vectorbt_backtest, run_monte_carlo, run_backtrader_strategy

router = APIRouter()

class BacktestRequest(BaseModel):
    strategy: str
    symbol: str
    timeframe: str
    start: str
    end: str
    params: dict[str, Any] = {}

class MonteCarloRequest(BaseModel):
    trials: int = 1000
    scenario: dict[str, Any] = {}

@router.post("/backtest", summary="Run vectorbt backtest")
async def backtest(request: BacktestRequest):
    return run_vectorbt_backtest(request.model_dump())

@router.post("/montecarlo", summary="Run Monte Carlo simulation")
async def montecarlo(request: MonteCarloRequest):
    return run_monte_carlo(request.model_dump())

@router.post("/backtrader", summary="Run Backtrader strategy")
async def backtrader(request: BacktestRequest):
    return run_backtrader_strategy(request.model_dump())
