"""
Custom exceptions for the application.
"""
from fastapi import HTTPException


class TradingError(HTTPException):
    """Base trading-related exception."""
    pass


class RiskViolationError(TradingError):
    """Raised when a trade violates risk rules."""
    def __init__(self, detail: str, violations: list[str]):
        super().__init__(status_code=400, detail=detail)
        self.violations = violations


class DailyLockoutError(TradingError):
    """Raised when daily trading is locked."""
    def __init__(self, lock_reason: str):
        super().__init__(status_code=403, detail=f"Trading locked: {lock_reason}")
        self.lock_reason = lock_reason
