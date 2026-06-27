from fastapi import APIRouter, Depends, HTTPException
from sqlmodel import Session, select
from typing import List
from uuid import UUID

from app.database import get_db
from app.models.plan import TradingPlan
from app.schemas.plan_schemas import PlanCreate, PlanRead, PlanUpdate

router = APIRouter()


@router.get("/", response_model=List[PlanRead])
async def list_plans(skip: int = 0, limit: int = 100, db: Session = Depends(get_db)):
    statement = select(TradingPlan).offset(skip).limit(limit)
    return db.exec(statement).all()


@router.get("/{plan_id}", response_model=PlanRead)
async def get_plan(plan_id: UUID, db: Session = Depends(get_db)):
    plan = db.get(TradingPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    return plan


@router.post("/", response_model=PlanRead, status_code=201)
async def create_plan(plan: PlanCreate, db: Session = Depends(get_db)):
    db_plan = TradingPlan(**plan.dict())
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan


@router.patch("/{plan_id}", response_model=PlanRead)
async def update_plan(plan_id: UUID, plan_update: PlanUpdate, db: Session = Depends(get_db)):
    plan = db.get(TradingPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    plan_data = plan_update.dict(exclude_unset=True)
    for key, value in plan_data.items():
        setattr(plan, key, value)
    db.add(plan)
    db.commit()
    db.refresh(plan)
    return plan


@router.delete("/{plan_id}", status_code=204)
async def delete_plan(plan_id: UUID, db: Session = Depends(get_db)):
    plan = db.get(TradingPlan, plan_id)
    if not plan:
        raise HTTPException(status_code=404, detail="Plan not found")
    db.delete(plan)
    db.commit()
