"""
Application configuration.
Secrets are loaded from environment variables. Never hard-code them.
"""

from functools import lru_cache
from typing import List

from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict

from services.devon.persona import BOUNDARY as DEVON_PERSONA_BOUNDARY
from services.devon.persona import REGISTER as DEVON_PERSONA_REGISTER

DEFAULT_SECRET_KEY = "change-me-in-production-use-openssl-rand-hex-32"


def secret_key_refusal(environment: str, secret_key: str) -> str:
    """Why this process must not start, or an empty string when it may.

    Only production is refused. Development and test keep the default so the
    standalone and offline paths run with no environment at all, which is
    the same reason the default exists.
    """
    if (environment or "").strip().lower() != "production":
        return ""
    key = (secret_key or "").strip()
    if not key:
        return (
            "SECRET_KEY is empty and ENVIRONMENT is production. Refusing to start: "
            "every JWT would verify against nothing. Set SECRET_KEY to the output "
            "of `openssl rand -hex 32`."
        )
    if key == DEFAULT_SECRET_KEY:
        return (
            "SECRET_KEY is the public default and ENVIRONMENT is production. "
            "Refusing to start: anyone holding the repository could mint a token "
            "for any user. Set SECRET_KEY to the output of `openssl rand -hex 32`."
        )
    return ""


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

    # Security. The default exists so a fresh checkout can run offline. It is
    # public, so a production process that still carries it would let anyone
    # mint a JWT for any user id; the validator below refuses to start there.
    SECRET_KEY: str = DEFAULT_SECRET_KEY
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 24  # 24 hours
    ALGORITHM: str = "HS256"

    # DEVON Command Center passkeys. These defaults bind credentials to the
    # canonical production Vercel host. Railway can override them for a custom
    # domain without changing code. WebAuthn private keys never reach DEVON.
    #
    # The two must always name the SAME host, the origin with a scheme and the
    # rp id without one, or registration and login disagree about who is asking.
    # They previously defaulted to meta-supreme-web.vercel.app, a project that
    # served the same code and was retired on 2026-08-27 once production was
    # confirmed to override both. A default naming a host that no longer exists
    # is the worst kind: it applies only when the override is missing, and the
    # failure surfaces as a rejected passkey rather than as absent config.
    PASSKEY_RP_ID: str = "meta-supreme-apex-genesis-web.vercel.app"
    PASSKEY_RP_NAME: str = "DEVON Command Center"
    PASSKEY_ORIGIN: str = "https://meta-supreme-apex-genesis-web.vercel.app"
    PASSKEY_CHALLENGE_TTL_SECONDS: int = 300

    # Operator shell: a second, shell-only key distinct from the operator
    # key, plus an idle timeout (seconds). The shell also requires a valid
    # login JWT, so opening a bash PTY needs BOTH factors. Empty key leaves
    # the shell disabled even when the operator bridge is enabled.
    DEVON_SHELL_KEY: str = ""
    DEVON_SHELL_IDLE_TIMEOUT_SECONDS: int = 900  # 15 minutes of no input

    # Database
    DATABASE_URL: str = "postgresql+asyncpg://postgres:postgres@localhost:5432/meta_supreme"

    # CORS. Default is loopback. The operator console is served same-origin
    # from app.main GET /console, so the knowledge loop does not need CORS.
    # devon-soul.vercel.app is not on this list: that host has no Postgres
    # and must fail-close persist. I am not teaching a second origin.
    CORS_ORIGINS: List[str] = [
        "http://localhost:3000",
        "http://127.0.0.1:3000",
    ]

    # AI Providers (abstracted — keys injected at runtime, never hard-coded)
    # Offline default is "mock". Live DEVON voice and enrichment use Cerebras
    # (gpt-oss-120b, measured 42ms). start-devon.sh writes DEFAULT_AI_PROVIDER
    # and ENRICHMENT_PROVIDER to cerebras and prompts for CEREBRAS_API_KEY.
    # CI keeps mock explicitly. Missing keys fail loudly, never silently degrade.
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

    # The soul layer. tee-soul-layer is read-only recall of Tee's rulings
    # (fed by the n8n write-back lane); devon-soul is DEVON's own gated
    # memory. Off by default — turning it on needs the Pinecone key in the
    # environment, never in Drive.
    SOUL_RECALL_ENABLED: bool = False
    PINECONE_API_KEY: str | None = None
    SOUL_TEE_HOST: str = (
        "https://tee-soul-layer-jw37oa2.svc.aped-4627-b74a.pinecone.io"
    )
    # devon-soul was created 2026-08-22 (integrated embedding, same model and
    # metric as tee-soul-layer). An endpoint, not a secret.
    SOUL_DEVON_HOST: str | None = (
        "https://devon-soul-jw37oa2.svc.aped-4627-b74a.pinecone.io"
    )
    AI_TIMEOUT_SECONDS: float = 60.0
    AI_MAX_RETRIES: int = 2
    AI_TEMPERATURE: float = 0.2
    AI_MAX_TOKENS_PER_AGENT: int = 1200
    AI_MAX_TOKENS_SYNTHESIS: int = 2000
    # Live AgentTurn is an iterative loop, so these limits apply on every tool
    # step rather than once per Council request. Keep the newest context and a
    # compact completion budget; deployments can raise them with measurements.
    AI_MAX_TOKENS_AGENT_TURN: int = 600
    AI_TURN_HISTORY_MAX_MESSAGES: int = 12
    AI_TURN_HISTORY_MAX_CHARS: int = 12_000
    AI_TURN_OBSERVATIONS_MAX_CHARS: int = 6_000

    # DEVON remains the approval and orchestration authority. EditForge is the
    # authenticated media execution boundary. The token is never returned by
    # status routes or written into receipts.
    EDITFORGE_URL: str = "https://editforge.vercel.app"
    EDITFORGE_TOKEN: str | None = None
    EDITFORGE_TIMEOUT_SECONDS: float = 60.0

    # Council execution
    COUNCIL_PARALLEL_EXECUTION: bool = True  # parallel default (Phase 4); set false for sequential
    COUNCIL_MAX_CONCURRENCY: int = 3  # provider calls in flight (rate-limit friendly)
    COUNCIL_DELIBERATION_ROUNDS: int = 1  # 2 → always deliberate; per-request opt-in also supported
    COUNCIL_HISTORY_LIMIT: int = 10  # recent messages passed to agents

    # Model tiers (None → provider default). Fast for intent classification,
    # synthesis for the final combination step.
    AI_MODEL_FAST: str | None = None
    AI_MODEL_SYNTHESIS: str | None = None

    # DEVON's canonical voice is the default, not an optional decoration. The
    # source remains services.devon.persona so every surface has one owner for
    # register and anti-caricature boundaries. An environment override is still
    # allowed when a deployment needs a temporary voice experiment.
    SYNTHESIS_PERSONA: str = (
        "Speak as DEVON, Tee's second brain. "
        + DEVON_PERSONA_REGISTER
        + " "
        + DEVON_PERSONA_BOUNDARY
        + " Address Tee naturally when useful. Be direct, grounded, capable, and lightly charismatic. "
        "Never trade accuracy, uncertainty, or approval boundaries for personality."
    )

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

    @model_validator(mode="after")
    def _refuse_the_default_secret_in_production(self) -> "Settings":
        refusal = secret_key_refusal(self.ENVIRONMENT, self.SECRET_KEY)
        if refusal:
            raise ValueError(refusal)
        return self


@lru_cache
def get_settings() -> Settings:
    return Settings()


settings = get_settings()
