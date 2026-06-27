"""
Migrate data from the old ICT Trading OS v7 HTML/localStorage format.

This script reads the old data sources and inserts them into PostgreSQL.
To be run once after the new database schema is created.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from uuid import uuid4
from datetime import datetime
from sqlmodel import Session

from app.database import engine
from app.models.user import User
from app.models.trade import Trade
from app.models.journal import JournalEntry
from app.models.plan import TradingPlan


def migrate_trades(old_trades: list[dict]) -> int:
    """Migrate old trade records to the new schema."""
    with Session(engine) as session:
        user = session.exec(select(User)).first()
        if not user:
            print("No user found. Run init_db.py first.")
            return 0

        count = 0
        for old in old_trades:
            trade = Trade(
                id=uuid4(),
                user_id=user.id,
                symbol=old.get("symbol", "UNKNOWN"),
                direction=old.get("direction", "long"),
                entry_price=old.get("entryPrice"),
                stop_loss=old.get("stopLoss"),
                take_profit_1=old.get("takeProfit1"),
                take_profit_2=old.get("takeProfit2"),
                take_profit_3=old.get("takeProfit3"),
                lot_size=old.get("lotSize"),
                leverage=old.get("leverage", 1),
                risk_amount=old.get("riskAmount"),
                status=old.get("status", "closed"),
                outcome=old.get("outcome"),
                pnl=old.get("pnl"),
                pnl_pips=old.get("pnlPips"),
                exit_price=old.get("exitPrice"),
                exit_time=old.get("exitTime"),
                entry_time=old.get("entryTime", datetime.utcnow()),
            )
            session.add(trade)
            count += 1

        session.commit()
        print(f"Migrated {count} trades")
        return count


def migrate_journal(old_entries: list[dict]) -> int:
    """Migrate old journal entries to the new schema."""
    with Session(engine) as session:
        user = session.exec(select(User)).first()
        if not user:
            print("No user found. Run init_db.py first.")
            return 0

        count = 0
        for old in old_entries:
            entry = JournalEntry(
                id=uuid4(),
                user_id=user.id,
                trade_id=None,  # Will need manual mapping if available
                pre_trade_notes=old.get("preTradeNotes"),
                post_trade_notes=old.get("postTradeNotes"),
                emotion_score=old.get("emotionScore"),
                setup_grade=old.get("setupGrade"),
                execution_grade=old.get("executionGrade"),
                management_grade=old.get("managementGrade"),
                tags=old.get("tags", []),
                lessons=old.get("lessons"),
            )
            session.add(entry)
            count += 1

        session.commit()
        print(f"Migrated {count} journal entries")
        return count


if __name__ == "__main__":
    print("Data migration script")
    print("This script should be customized with your old data export.")
    print("Provide old_trades and old_entries as Python lists of dicts.")
