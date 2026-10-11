"""
ORBIT Application Configuration
Loads environment variables using Pydantic Settings
"""

from typing import List
from pydantic import Field, field_validator, model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEV_JWT_SECRET = "dev-secret-key-orbit-multi-agent-task-system-jwt-2026"


class Settings(BaseSettings):
    """Application configuration settings."""

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        extra="ignore",
        # Pasted values often carry a trailing newline or space (seen in a Render dashboard); that
        # silently breaks exact comparisons such as the Google Chat audience.
        str_strip_whitespace=True,
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
    DEFAULT_LLM_MODEL: str = "gemini/gemini-2.5-flash"  # answers in about 2s; gemini-3.x "thinking" models take 15s+
    FAST_LLM_MODEL: str = "gemini/gemini-2.5-flash"
    LLM_TEMPERATURE: float = 0.1
    LLM_MAX_TOKENS: int = 2048
    LLM_TIMEOUT_SECONDS: float = 8.0  # per attempt; a hung provider must not stall a chat reply
    LLM_MAX_ATTEMPTS: int = 1
    LLM_BREAKER_FAILURES: int = 3  # consecutive failures before the LLM is skipped for a while
    LLM_BREAKER_COOLDOWN_SECONDS: float = 60.0
    # Google Chat gives up after 30s, so the agent must answer (or apologise) before that.
    AGENT_TIMEOUT_SECONDS: float = 22.0

    # Google Chat Integration
    GOOGLE_CHAT_WEBHOOK_SECRET: str = ""
    GOOGLE_SERVICE_ACCOUNT_FILE: str = "credentials/service-account.json"
    GOOGLE_SERVICE_ACCOUNT_JSON: str = ""
    GOOGLE_CHAT_SPACE_ID: str = ""
    GOOGLE_CHAT_AUDIENCE: str = ""
    GOOGLE_CHAT_VERIFY_AUTH: bool = False
    # Only for Chat apps published as a Workspace add-on: the Google Cloud project number whose
    # add-on service agent (service-<number>@gcp-sa-gsuiteaddons...) may sign requests.
    GOOGLE_CHAT_ADDON_PROJECT_NUMBER: str = ""

    # Email notifications (optional; off unless SMTP_HOST and EMAIL_FROM are set)
    SMTP_HOST: str = ""
    SMTP_PORT: int = 587
    SMTP_USERNAME: str = ""
    SMTP_PASSWORD: str = ""
    SMTP_SECURITY: str = "starttls"  # "starttls" | "ssl" | "none"
    SMTP_TIMEOUT: float = 10.0
    EMAIL_FROM: str = ""
    APP_BASE_URL: str = "http://localhost:3000"  # used for links inside emails

    # Task attachments
    UPLOAD_DIR: str = "uploads"
    MAX_UPLOAD_MB: int = 10
    MAX_ATTACHMENTS_PER_TASK: int = 20

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

    # Prometheus endpoint (/metrics). Off by default; when METRICS_TOKEN is set it must be
    # presented as a Bearer token.
    METRICS_ENABLED: bool = False
    METRICS_TOKEN: str = ""

    # Login brute-force protection (per client IP + email)
    LOGIN_RATE_LIMIT_ATTEMPTS: int = 10
    LOGIN_RATE_LIMIT_WINDOW_SECONDS: int = 300

    @field_validator("DATABASE_URL")
    @classmethod
    def _use_async_driver(cls, value: str) -> str:
        """Hosts such as Render and Heroku hand out postgres:// or postgresql:// URLs; the app
        needs the asyncpg driver prefix."""
        for plain in ("postgres://", "postgresql://"):
            if value.startswith(plain):
                return "postgresql+asyncpg://" + value[len(plain):]
        return value

    @model_validator(mode="after")
    def _enforce_production_safety(self) -> "Settings":
        """Refuse to boot in production with unsafe defaults."""
        if self.ENVIRONMENT.lower() != "production":
            return self
        problems: list[str] = []
        placeholder = "change-this" in self.JWT_SECRET_KEY.lower()
        if self.JWT_SECRET_KEY == DEV_JWT_SECRET or placeholder or len(self.JWT_SECRET_KEY) < 32:
            problems.append("JWT_SECRET_KEY must be a unique secret of at least 32 characters")
        if "*" in self.CORS_ORIGINS:
            problems.append("CORS_ORIGINS must not contain '*' when credentials are allowed")
        if not self.GOOGLE_CHAT_VERIFY_AUTH:
            problems.append("GOOGLE_CHAT_VERIFY_AUTH must be true")
        elif not self.GOOGLE_CHAT_AUDIENCE:
            problems.append("GOOGLE_CHAT_AUDIENCE must be set when verification is on")
        if problems:
            raise ValueError("Unsafe production configuration: " + "; ".join(problems))
        return self


settings = Settings()
