"""
Planner service — business logic for trading plans, bias, and confluence.

Currently a thin wrapper around the database. Will expand with
validation rules, AI grading hooks, and plan templates.
"""
from sqlmodel import Session
from app.models.plan import TradingPlan
from app.schemas.plan_schemas import PlanCreate


def create_plan(db: Session, plan: PlanCreate) -> TradingPlan:
    db_plan = TradingPlan(**plan.dict())
    db.add(db_plan)
    db.commit()
    db.refresh(db_plan)
    return db_plan


def get_plan_by_date(db: Session, user_id: str, plan_date: str) -> TradingPlan | None:
    from sqlmodel import select
    statement = (
        select(TradingPlan)
        .where(TradingPlan.user_id == user_id)
        .where(TradingPlan.date == plan_date)
    )
    return db.exec(statement).first()
