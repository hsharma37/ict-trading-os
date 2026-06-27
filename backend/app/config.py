"""
Pydantic Settings for the application.

Loads configuration from environment variables or .env file.
"""
from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # Database
    database_url: str = "postgresql://ictos:ictos@localhost:5432/ictos"

    # Redis
    redis_url: str = "redis://localhost:6379/0"

    # API
    api_host: str = "0.0.0.0"
    api_port: int = 8000
    api_secret_key: str = "dev-secret-change-in-production"

    # AI / Ollama
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "llama3.1:8b"
    embedding_model: str = "nomic-embed-text:latest"

    # Celery
    celery_broker_url: str = "redis://localhost:6379/0"
    celery_result_backend: str = "db+postgresql://ictos:ictos@localhost:5432/ictos"

    # MT5 Bridge
    mt5_bridge_url: str = "http://localhost:5000"

    # Telegram
    telegram_bot_token: str = ""
    telegram_chat_id: str = ""

    # Logging
    log_level: str = "INFO"


settings = Settings()
