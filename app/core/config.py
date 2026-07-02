"""Application configuration for the active FastAPI app."""
import os
from pathlib import Path

class Settings:
    """Application settings from environment variables."""
    APP_NAME = os.getenv("APP_NAME", "ICT Trading OS API")
    APP_VERSION = os.getenv("APP_VERSION", "9.1.0")
    APP_ENV = os.getenv("APP_ENV") or os.getenv("PYTHON_ENV") or os.getenv("VERCEL_ENV") or "development"
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "auto").lower()
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")
    MT5_BRIDGE_URL: str = os.getenv("MT5_BRIDGE_URL", "http://localhost:5001")
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATABASE_PATH: str = os.getenv(
        "DATABASE_PATH",
        str(Path(__file__).resolve().parents[2] / "ictos.db"),
    )
    IS_VERCEL: bool = (
        os.getenv("VERCEL", "").lower() in {"1", "true"}
        or os.getenv("TRADINGOS_RUNTIME", "").lower() == "vercel"
    )
    ALLOW_SQLITE_RUNTIME: bool = os.getenv("ALLOW_SQLITE_RUNTIME", "false").lower() == "true"
    REQUIRE_POSTGRES: bool = (
        os.getenv("REQUIRE_POSTGRES", "false").lower() == "true"
        or ((APP_ENV in {"production", "preview"} or IS_VERCEL) and not ALLOW_SQLITE_RUNTIME)
    )
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    API_KEY: str = os.getenv("API_KEY", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "ict-os-dev-secret-key")

settings = Settings()
