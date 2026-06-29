from sqlmodel import SQLModel

# Import all models so Alembic can detect them and SQLModel metadata is populated
from app.models.user import User
from app.models.plan import TradingPlan
from app.models.trade import Trade
from app.models.journal import JournalEntry
from app.models.kb import KBSource, KBChunk
from app.models.alert import Alert
from app.models.risk_ledger import DailyRiskLedger
from app.models.audit_log import AuditLog
from app.models.alert_history import AlertHistory
from app.models.suggestion import Suggestion
