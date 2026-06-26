"""Plans Router."""
from fastapi import APIRouter
from pydantic import BaseModel
from typing import Optional, List
from app.services.plan_service import plan_service

router = APIRouter(prefix="/plans", tags=["Plans"])

class PlanCreate(BaseModel):
    symbol: str
    bias: Optional[str] = "NEUTRAL"
    entry_zone: Optional[float] = None
    stop_loss: Optional[float] = None
    take_profit_1: Optional[float] = None
    take_profit_2: Optional[float] = None
    take_profit_3: Optional[float] = None
    strategy: Optional[str] = "ICT"
    narrative: Optional[str] = ""
    tags: Optional[List[str]] = []
    session: Optional[str] = ""
    status: Optional[str] = "OPEN"

@router.post("/")
def create_plan(plan: PlanCreate):
    return plan_service.create_plan(plan.dict())

@router.get("/")
def list_plans(status: Optional[str] = None, symbol: Optional[str] = None):
    return plan_service.list_plans(status=status, symbol=symbol)

@router.get("/{plan_id}")
def get_plan(plan_id: str):
    return plan_service.get_plan(plan_id)

@router.post("/{plan_id}")
def update_plan(plan_id: str, updates: dict):
    return plan_service.update_plan(plan_id, updates)
