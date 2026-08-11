"""
Application configuration.
Secrets are loaded from environment variables. Never hard-code them.
"""

from functools import lru_cache
from typing import List

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra="ignore",
    )

    APP_NAME: str = "Meta Supreme Apex Genesis"
    ENVIRONMENT: str = "development"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24
    ALGORITHM: str = "HS256"

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme"

    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    DEFAULT_AI_PROVIDER: str = "mock"
    AI_MODEL: str | None = None
    ANTHROPIC_MODEL: str = "claude-sonnet-5"
    OPENAI_MODEL: str = "gpt-5.2"
    AI_TIMEOUT_SECONDS: float = 60.0
    AI_MAX_RETRIES: int = 2
    AI_TEMPERATURE: float = 0.2
    AI_MAX_TOKENS_PER_AGENT: int = 1200
    AI_MAX_TOKENS_SYNTHESIS: int = 2000

    COUNCIL_PARALLEL_EXECUTION: bool = True
    COUNCIL_MAX_CONCURRENCY: int = 3
    COUNCIL_DELIBERATION_ROUNDS: int = 1
    COUNCIL_HISTORY_LIMIT: int = 10

    AI_MODEL_FAST: str | None = None
    AI_MODEL_SYNTHESIS: str | None = None

    EMBEDDING_PROVIDER: str = "mock"
    EMBEDDING_MODEL: str | None = None
    RETRIEVAL_ENABLED: bool = True
    RETRIEVAL_TOP_K: int = 5

    MEMORY_ENABLED: bool = True
    MEMORY_RECALL_LIMIT: int = 5

    WORKFLOW_APPROVAL_REQUIRED: bool = True
    WORKFLOW_MAX_STEPS: int = 12
    WORKFLOW_RUN_HISTORY_LIMIT: int = 50
    WORKFLOW_SWEEP_ON_STARTUP: bool = True
    WORKFLOW_ORPHAN_TIMEOUT_MINUTES: int = 30

    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
