"""Application configuration - simple version without pydantic-settings."""
import os

class Settings:
    """Application settings from environment variables."""
    APP_NAME = os.getenv("APP_NAME", "ICT Trading OS API")
    APP_VERSION = os.getenv("APP_VERSION", "8.0.0")
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")

settings = Settings()
