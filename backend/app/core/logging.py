"""
Structured logging configuration.

Uses JSON formatting for production and plain text for development.
"""
import logging
import sys
from app.config import settings


def configure_logging() -> None:
    """Configure root logger with appropriate formatting."""
    level = getattr(logging, settings.log_level.upper(), logging.INFO)

    handler = logging.StreamHandler(sys.stdout)
    handler.setLevel(level)

    if settings.log_level.upper() == "DEBUG":
        formatter = logging.Formatter(
            "%(asctime)s [%(levelname)s] %(name)s: %(message)s"
        )
    else:
        formatter = logging.Formatter(
            "%(asctime)s %(levelname)s %(name)s %(message)s"
        )

    handler.setFormatter(formatter)

    root = logging.getLogger()
    root.setLevel(level)
    root.handlers = [handler]
