"""Application configuration. Secrets from environment only."""

import os
from functools import lru_cache

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

DEFAULT_SECRET_KEY = "dev-only-change-me-in-production"
LOCAL_ENVIRONMENTS = frozenset({"development", "dev", "test", "local", ""})
PLATFORM_MARKERS = ("RAILWAY_ENVIRONMENT_NAME", "RAILWAY_PROJECT_ID", "VERCEL_ENV")


def secret_key_refusal(app_env: str, secret_key: str) -> str:
    """The same rule as the root tree: a deployed process never boots on the default."""
    env = (app_env or "").strip().lower()
    deployed = env not in LOCAL_ENVIRONMENTS or any(
        (os.environ.get(marker) or "").strip() for marker in PLATFORM_MARKERS
    )
    if not deployed:
        return ""
    key = (secret_key or "").strip()
    if not key or key == DEFAULT_SECRET_KEY:
        return (
            "SECRET_KEY is the public default or empty on a deployed process. "
            "Refusing to start. Set SECRET_KEY to the output of `openssl rand -hex 32`."
        )
    return ""


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8", extra="ignore")

    APP_NAME: str = "Meta Supreme Apex Genesis"
    APP_ENV: str = "development"
    DEBUG: bool = True
    API_PREFIX: str = "/api/v1"

    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ALGORITHM: str = "HS256"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24

    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme"

    DEFAULT_AI_PROVIDER: str = "mock"  # mock | anthropic | openai
    ANTHROPIC_API_KEY: str | None = None
    OPENAI_API_KEY: str | None = None
    AI_MODEL: str | None = None
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

    @model_validator(mode="after")
    def _refuse_the_default_secret_when_deployed(self) -> "Settings":
        refusal = secret_key_refusal(self.APP_ENV, self.SECRET_KEY)
        if refusal:
            raise ValueError(refusal)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
