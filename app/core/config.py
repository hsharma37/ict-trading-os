"""Application configuration for the active FastAPI app."""
import os
from pathlib import Path

class Settings:
    """Application settings from environment variables."""
    APP_NAME = os.getenv("APP_NAME", "ICT Trading OS API")
    APP_VERSION = os.getenv("APP_VERSION", "9.1.0")
    APP_ENV = (os.getenv("APP_ENV") or os.getenv("PYTHON_ENV") or os.getenv("VERCEL_ENV") or "development").lower()
    STORAGE_BACKEND = os.getenv("STORAGE_BACKEND", "auto").lower()
    CORS_ORIGINS = os.getenv("CORS_ORIGINS", "*")
    DEBUG = os.getenv("DEBUG", "false").lower() == "true"
    TELEGRAM_BOT_TOKEN: str = os.getenv("TELEGRAM_BOT_TOKEN", "")
    TELEGRAM_CHANNEL_ID: str = os.getenv("TELEGRAM_CHANNEL_ID", "")
    MT5_BRIDGE_URL: str = os.getenv("MT5_BRIDGE_URL", "http://localhost:5001")
    # MT5 execution guardrails. Empty allowlist -> all configured instruments.
    MT5_ALLOWED_SYMBOLS: str = os.getenv("MT5_ALLOWED_SYMBOLS", "")
    MT5_MAX_LOT: float = float(os.getenv("MT5_MAX_LOT", "10") or "10")
    MT5_REQUIRE_SL: bool = os.getenv("MT5_REQUIRE_SL", "false").lower() == "true"
    # Market data provider selection: "auto" uses OANDA when configured, else Yahoo.
    # Force with "oanda" or "yahoo".
    MARKET_DATA_PROVIDER: str = os.getenv("MARKET_DATA_PROVIDER", "auto").lower()
    # OANDA v20 REST (real-time FX/metals/index-CFD feed). Token from an OANDA
    # fxTrade practice or live account. Env selects the API host.
    OANDA_API_TOKEN: str = os.getenv("OANDA_API_TOKEN", "").strip()
    OANDA_ACCOUNT_ID: str = os.getenv("OANDA_ACCOUNT_ID", "").strip()
    OANDA_ENV: str = os.getenv("OANDA_ENV", "practice").strip().lower()  # practice | live
    DATABASE_URL: str = os.getenv("DATABASE_URL", "")
    DATABASE_SCHEMA: str = os.getenv("DATABASE_SCHEMA", "")
    DATABASE_PATH: str = os.getenv(
        "DATABASE_PATH",
        str(Path(__file__).resolve().parents[2] / "ictos.db"),
    )
    IS_VERCEL: bool = (
        os.getenv("VERCEL", "").lower() in {"1", "true"}
        or os.getenv("TRADINGOS_RUNTIME", "").lower() == "vercel"
    )
    PRODUCTION_LIKE: bool = APP_ENV in {"production", "preview"} or IS_VERCEL
    ALLOW_SQLITE_RUNTIME: bool = os.getenv("ALLOW_SQLITE_RUNTIME", "false").lower() == "true"
    REQUIRE_POSTGRES: bool = (
        os.getenv("REQUIRE_POSTGRES", "false").lower() == "true"
        or (PRODUCTION_LIKE and not ALLOW_SQLITE_RUNTIME)
    )
    AUTH_ENABLED: bool = os.getenv("AUTH_ENABLED", "false").lower() == "true"
    REQUIRE_API_AUTH: bool = os.getenv(
        "REQUIRE_API_AUTH",
        "true" if PRODUCTION_LIKE else "false",
    ).lower() == "true"
    ALLOW_PUBLIC_API_MUTATIONS: bool = os.getenv("ALLOW_PUBLIC_API_MUTATIONS", "false").lower() == "true"
    API_KEY: str = os.getenv("API_KEY", "")
    JWT_SECRET: str = os.getenv("JWT_SECRET", "" if PRODUCTION_LIKE else "ict-os-dev-secret-key")

    def auth_required(self) -> bool:
        """Whether private/sensitive API routes require API-key auth."""
        if self.ALLOW_PUBLIC_API_MUTATIONS:
            return False
        return self.AUTH_ENABLED or self.REQUIRE_API_AUTH or self.PRODUCTION_LIKE

    def validate_runtime_security(self) -> None:
        """Fail fast when required auth secrets are absent or still defaults."""
        if not self.auth_required():
            return
        default_api_keys = {
            "change-me",
            "change-me-in-production",
            "replace-with-production-64-char-random-api-key",
            "replace-with-production-api-key",
            "replace-with-preview-64-char-random-api-key",
            "replace-with-preview-api-key",
        }
        default_jwt_secrets = {
            "ict-os-dev-secret-key",
            "change-me-in-production-64-char-random-string",
            "replace-with-production-random-secret",
            "replace-with-preview-random-secret",
        }
        if not self.API_KEY or self.API_KEY in default_api_keys:
            raise RuntimeError("API_KEY must be set to a non-default value when API auth is required")
        if not self.JWT_SECRET or self.JWT_SECRET in default_jwt_secrets:
            raise RuntimeError("JWT_SECRET must be set to a non-default value when API auth is required")

settings = Settings()
