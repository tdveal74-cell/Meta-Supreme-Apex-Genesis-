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

    # Application
    APP_NAME: str = "Meta Supreme Apex Genesis"
    ENVIRONMENT: str = "development"  # development | staging | production
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api/v1"

    # Security
    SECRET_KEY: str = "change-me-in-production-use-openssl-rand-hex-32"
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ALGORITHM: str = "HS256"

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme"

    # CORS
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # AI Providers (abstracted — keys injected at runtime, never hard-coded)
    # "mock" runs the full system offline with clearly-labeled simulated
    # output; switch to "anthropic" or "openai" (+ API key) for live intelligence.
    OPENAI_API_KEY: str | None = None
    ANTHROPIC_API_KEY: str | None = None
    CEREBRAS_API_KEY: str | None = None
    DEFAULT_AI_PROVIDER: str = "mock"  # mock | anthropic | openai | cerebras
    AI_MODEL: str | None = None  # override the provider's default model
    ANTHROPIC_MODEL: str = "claude-sonnet-5"
    OPENAI_MODEL: str = "gpt-5.2"
    CEREBRAS_MODEL: str = "gpt-oss-120b"

    # Capture enrichment. Cerebras is the measured lane for this job: it returns
    # an Area and a one line summary in tens of milliseconds, and the Area is
    # then validated against the nine rather than trusted.
    ENRICHMENT_PROVIDER: str = "mock"  # mock | cerebras | openai | anthropic
    ENRICHMENT_ENABLED: bool = True
    AI_TIMEOUT_SECONDS: float = 60.0
    AI_MAX_RETRIES: int = 2
    AI_TEMPERATURE: float = 0.2
    AI_MAX_TOKENS_PER_AGENT: int = 1200
    AI_MAX_TOKENS_SYNTHESIS: int = 2000

    # Council execution
    COUNCIL_PARALLEL_EXECUTION: bool = True  # parallel default (Phase 4); set false for sequential
    COUNCIL_MAX_CONCURRENCY: int = 3  # provider calls in flight (rate-limit friendly)
    COUNCIL_DELIBERATION_ROUNDS: int = 1  # 2 → always deliberate; per-request opt-in also supported
    COUNCIL_HISTORY_LIMIT: int = 10  # recent messages passed to agents

    # Model tiers (None → provider default). Fast for intent classification,
    # synthesis for the final combination step.
    AI_MODEL_FAST: str | None = None
    AI_MODEL_SYNTHESIS: str | None = None

    # Knowledge & retrieval (Phase 3)
    # "mock" embeddings are deterministic and offline (clearly labeled);
    # switch to "openai" (+ OPENAI_API_KEY) for real semantic retrieval.
    EMBEDDING_PROVIDER: str = "mock"  # mock | openai
    EMBEDDING_MODEL: str | None = None  # override the provider's default
    RETRIEVAL_ENABLED: bool = True
    RETRIEVAL_TOP_K: int = 5

    # Memory (Phase 5 slice)
    MEMORY_ENABLED: bool = True  # persist + recall transparent memories
    MEMORY_RECALL_LIMIT: int = 5

    # Workflows (Phase 5)
    #
    # WORKFLOW_APPROVAL_REQUIRED is deliberately not exposed through the API,
    # the UI, or `.env.example`. Turning it off lets automation write memory,
    # open decisions, and prepare exports with no human in the loop, which
    # contradicts the platform's central promise. It exists so the engine can
    # be tested end-to-end without stubbing approvals, and as the switch a
    # future trusted-automation mode would flip per workflow rather than
    # globally. Leave it True.
    WORKFLOW_APPROVAL_REQUIRED: bool = True
    WORKFLOW_MAX_STEPS: int = 12  # keeps one run's provider cost bounded
    WORKFLOW_RUN_HISTORY_LIMIT: int = 50  # default page size for run history

    # A run executes inside the request that started it, so a process death
    # mid-run strands the row at `running` forever. The startup sweep marks
    # those failed. The timeout must exceed the longest plausible run — a
    # full council deliberation against a live provider — or the sweep will
    # fail runs that are genuinely still working.
    WORKFLOW_SWEEP_ON_STARTUP: bool = True
    WORKFLOW_ORPHAN_TIMEOUT_MINUTES: int = 30

    # Observability
    LOG_LEVEL: str = "INFO"


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
