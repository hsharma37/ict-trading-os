from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from app.database import get_db
from app.models.trade import Trade
from app.services.analytics_service import (
    calculate_expectancy,
    calculate_heatmap,
    calculate_kelly,
    calculate_confluence,
    calculate_drawdown,
)

router = APIRouter()

@router.get("/expectancy", summary="Trade expectancy metrics")
async def get_expectancy(db: Session = Depends(get_db)):
    trades = db.exec(select(Trade)).all()
    return calculate_expectancy(trades)

@router.get("/heatmap", summary="Session performance heatmap")
async def get_heatmap(db: Session = Depends(get_db)):
    trades = db.exec(select(Trade)).all()
    return calculate_heatmap(trades)

@router.get("/kelly", summary="Kelly Criterion position sizing")
async def get_kelly(db: Session = Depends(get_db)):
    trades = db.exec(select(Trade)).all()
    return calculate_kelly(trades)

@router.get("/confluence", summary="ICT concept confluence scoring")
async def get_confluence(db: Session = Depends(get_db)):
    trades = db.exec(select(Trade)).all()
    return calculate_confluence(trades)

@router.get("/drawdown", summary="Max drawdown and equity curve")
async def get_drawdown(db: Session = Depends(get_db)):
    trades = db.exec(select(Trade)).all()
    return calculate_drawdown(trades)
