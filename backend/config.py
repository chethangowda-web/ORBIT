"""
ORBIT Application Configuration
Loads environment variables using Pydantic Settings
"""

from typing import List
from pydantic import Field, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-secret-key-orbit-multi-agent-task-system-jwt-2026"


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
    )

    # General App Settings
    APP_NAME: str = "ORBIT"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    PORT: int = 8001
    HOST: str = "0.0.0.0"
    API_V1_PREFIX: str = "/api"
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
        "http://localhost:8001",
    ]

    # Database Settings
    DATABASE_URL: str = "postgresql+asyncpg://orbit:password@localhost:5432/orbit"
    DB_ECHO: bool = False

    # Redis Settings
    REDIS_URL: str = "redis://localhost:6379/0"

    # Authentication & Security
    JWT_SECRET_KEY: str = DEV_JWT_SECRET
    JWT_ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 1440

    # Google OAuth 2.0 / OpenID Connect
    GOOGLE_OAUTH_CLIENT_ID: str = ""
    GOOGLE_OAUTH_CLIENT_SECRET: str = ""
    GOOGLE_OAUTH_REDIRECT_URI: str = "http://localhost:3000/auth/callback"

    # LLM & AI Settings
    GOOGLE_GEMINI_API_KEY: str = ""
    OPENAI_API_KEY: str = ""
    DEFAULT_LLM_MODEL: str = "gemini/gemini-3.8-flash"
    FAST_LLM_MODEL: str = "gemini/gemini-3.8-flash"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048

    # Google Chat Integration
    GOOGLE_CHAT_WEBHOOK_SECRET: str = ""
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "credentials/service-account.json"
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    GOOGLE_CHAT_SPACE_ID: str = ""
    GOOGLE_CHAT_AUDIENCE: str = ""
    GOOGLE_CHAT_VERIFY_AUTH: bool = False

    # Observability & Checkpointing
    LANGCHAIN_TRACING_V2: bool = False
    LANGCHAIN_API_KEY: str = ""
    LANGCHAIN_PROJECT: str = "orbit"
    CHECKPOINTER_BACKEND: str = "redis"  # "redis" | "memory"
    ALLOW_IN_MEMORY_CHECKPOINTER_FALLBACK: bool = True
    REDIS_CONNECT_TIMEOUT: float = 3.0
    REDIS_SOCKET_TIMEOUT: float = 5.0

    # Scheduler
    SCHEDULER_ENABLED: bool = True
    SCHEDULER_INTERVAL_MINUTES: int = 5
    SCHEDULER_JOBSTORE: str = "redis"  # "redis" | "memory"

    # Product behaviour
    APP_TIMEZONE: str = "Asia/Kolkata"  # defines "today" for due dates and digests
    ALLOW_REGISTRATION: bool = False  # public self-registration is opt-in
    LOG_LEVEL: str = "INFO"
    LOG_WEBHOOK_PAYLOADS: bool = False  # raw Chat payloads contain PII

    # Login brute-force protection (per client IP + email)
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 10
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> "Settings":
        """Refuse to boot in production with unsafe defaults."""
        if self.ENVIRONMENT.lower() != "production":
            return self
        problems: list[str] = []
        if self.JWT_SECRET_KEY == DEV_JWT_SECRET or len(self.JWT_SECRET_KEY) < 32:
            problems.append("JWT_SECRET_KEY must be a unique secret of at least 32 characters")
        if "*" in self.CORS_ORIGINS:
            problems.append("CORS_ORIGINS must not contain '*' when credentials are allowed")
        if not self.GOOGLE_CHAT_VERIFY_AUTH:
            problems.append("GOOGLE_CHAT_VERIFY_AUTH must be true")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self


settings = Settings()
