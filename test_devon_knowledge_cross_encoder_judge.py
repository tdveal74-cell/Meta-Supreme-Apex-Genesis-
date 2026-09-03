"""Fix PR 15's critic follow-up (H15), the second bug the follow-up left open.

The follow-up commit wrapped services/knowledge/pipeline.py's completion
provider in MeteredProvider so it could not become a second, unmetered path
to a provider, but it did not repair the two bugs that made the path inert:
_completion_provider imported a factory function, create_completion_provider,
that did not exist anywhere in the repository, and even if the import had
succeeded, synthesis.py's _llm_judge_score called provider.complete(system=,
user=, max_tokens=) instead of the real AIProvider.complete(request) contract.
Both bugs were caught by a bare except Exception, so the judge silently fell
back to the offline lexical score on every call, under every configuration,
and nothing ever noticed.

The pool the judge runs against was reachable the whole time: query_knowledge
is the body of POST /api/v1/knowledge/query (see test_devon_fkr_query_route.py),
and OPERATING.md and docs/devon/DEVON.md both name DEFAULT_AI_PROVIDER=
anthropic|openai|cerebras as real deployment configurations, not merely a
test default. What was unreachable under any configuration was the llm-judge
branch inside that call, because the completion provider it needed could
never be built. create_completion_provider now exists in
services.intelligence.providers.factory (mirroring create_embedding_provider:
a name and the matching keys in, a configured provider out) and the judge
call now builds a real CompletionRequest/ChatMessage pair and reads
response.text. These tests prove the judge branch actually runs a completion
now instead of always falling back, and that it still cannot spend past a
tenant's cap.
"""

from __future__ import annotations

import json

import pytest

from app.core.config import settings
from app.core.tenant_context import bind_tenant, reset_tenant
from app.services.provider_usage import ProviderSpendCapExceeded, record_usage
from services.intelligence.providers.base import (
    ChatMessage,
    CompletionRequest,
    CompletionResponse,
    TokenUsage,
)
from services.intelligence.providers.factory import create_completion_provider
from services.knowledge.pipeline import _completion_provider
from services.knowledge.retrieval import RetrievalCandidate
from services.knowledge.synthesis import cross_encoder_rerank, synthesize_with_cross_encoder


class _FakeJudge:
    """A non-mock completion provider with a deterministic, scripted verdict.

    Not `services.intelligence.providers.mock_provider.MockProvider`: that
    class always reports `name == "mock"`, which `cross_encoder_rerank`
    deliberately excludes from the llm-judge branch, so it could never prove
    the branch runs. This one exercises the same `complete(request)` contract
    a real provider does, without a key or the network.
    """

    name = "fake-judge"

    def __init__(self, score_for) -> None:
        self._score_for = score_for
        self.requests: list[CompletionRequest] = []

    async def complete(self, request: CompletionRequest) -> CompletionResponse:
        self.requests.append(request)
        assert request.system, "the judge instructions belong in system, not the user turn"
        document = request.messages[-1].content.split("Document:\n", 1)[1]
        score = self._score_for(document)
        return CompletionResponse(
            text=json.dumps({"score": score, "reason": "fake-judge verdict"}),
            usage=TokenUsage(input_tokens=20, output_tokens=8),
            model="fake-judge-v1",
            provider=self.name,
        )


def _candidate(title: str, content: str, *, rrf_score: float) -> RetrievalCandidate:
    return RetrievalCandidate(
        embedding_id=title.lower(),
        knowledge_item_id=title.lower(),
        title=title,
        content=content,
        chunk_index=0,
        score=rrf_score,
        signals={},
        distance=1.0 - rrf_score,
    )


# ---------------------------------------------------------------------------
# The factory function now exists and mirrors create_embedding_provider
# ---------------------------------------------------------------------------


def test_create_completion_provider_builds_the_named_provider():
    assert create_completion_provider("mock").name == "mock"
    assert create_completion_provider("anthropic", anthropic_api_key="k").name == "anthropic"
    assert create_completion_provider("openai", openai_api_key="k").name == "openai"
    assert create_completion_provider("cerebras", cerebras_api_key="k").name == "cerebras"


def test_create_completion_provider_rejects_an_unknown_name():
    from services.intelligence.providers.base import ProviderConfigError

    with pytest.raises(ProviderConfigError):
        create_completion_provider("skynet")


# ---------------------------------------------------------------------------
# services/knowledge/pipeline.py's _completion_provider builds a real one now
# ---------------------------------------------------------------------------


def test_completion_provider_no_longer_returns_none_for_a_configured_provider(monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_AI_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key-never-sent-over-the-wire")

    provider = _completion_provider()

    assert provider is not None, (
        "create_completion_provider exists and the call now succeeds; before this "
        "fix the import failure made this always None"
    )
    assert provider.name == "anthropic"
    assert provider.inner.__class__.__name__ == "AnthropicProvider"


def test_completion_provider_still_degrades_to_none_when_unconfigured(monkeypatch):
    """No key set is still a graceful None, not a crash: the judge falls back."""
    monkeypatch.setattr(settings, "DEFAULT_AI_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", None)

    assert _completion_provider() is None


def test_completion_provider_for_the_default_mock_setting_is_named_mock(monkeypatch):
    monkeypatch.setattr(settings, "DEFAULT_AI_PROVIDER", "mock")

    provider = _completion_provider()

    assert provider is not None
    assert provider.name == "mock"


# ---------------------------------------------------------------------------
# The judge branch now actually completes instead of always falling back
# ---------------------------------------------------------------------------


async def test_cross_encoder_rerank_runs_the_llm_judge_when_a_real_provider_is_given():
    judge = _FakeJudge(lambda doc: 9.0 if "solar" in doc.lower() else 1.0)
    candidates = [
        _candidate("Baking", "Knead the dough and let it rise.", rrf_score=0.9),
        _candidate("Solar", "Solar panels lose output as they heat up.", rrf_score=0.1),
    ]

    ranked, method = await cross_encoder_rerank(
        "how efficient are solar panels?", candidates, top_k=2, provider=judge
    )

    assert method == "llm-judge"
    assert len(judge.requests) == 2, "the judge was called once per candidate"
    # The RRF prior favored Baking by a wide margin; only a genuine completion
    # score, not the offline lexical fallback, flips the order.
    assert [c.title for c in ranked] == ["Solar", "Baking"]
    assert ranked[0].rerank_reason == "fake-judge verdict"


async def test_cross_encoder_rerank_still_falls_back_for_the_mock_provider():
    """Unchanged regression: DEFAULT_AI_PROVIDER=mock (the CI default) must
    keep taking the offline lexical path exactly as it did before this fix,
    now for the intended reason (provider.name == "mock") instead of the
    accidental one (the import always failing)."""
    from services.intelligence.providers.mock_provider import MockProvider

    candidates = [_candidate("Solar", "Solar panels are efficient.", rrf_score=0.5)]

    ranked, method = await cross_encoder_rerank(
        "solar panels", candidates, top_k=1, provider=MockProvider()
    )

    assert method == "offline-lexical"
    assert ranked[0].rerank_reason == "offline-lexical"


async def test_synthesize_with_cross_encoder_reports_the_llm_judge_method_end_to_end():
    judge = _FakeJudge(lambda doc: 8.0)
    candidates = [_candidate("Solar", "Solar cells convert light to current.", rrf_score=0.4)]

    answer = await synthesize_with_cross_encoder(
        query="how do solar cells work?",
        candidates=candidates,
        owner_id="owner-1",
        max_citations=1,
        provider=judge,
    )

    assert answer.rerank_method == "llm-judge"
    assert answer.cleared is True
    assert answer.citations[0].rerank_score == pytest.approx(0.85 * 8.0 + 0.15 * 0.4 * 10.0)
    assert judge.requests, "synthesize_with_cross_encoder must have driven a real completion"


# ---------------------------------------------------------------------------
# Still inside the spend cap on this lane
# ---------------------------------------------------------------------------


async def test_a_tenant_at_the_cap_is_refused_on_the_cross_encoder_lane_too(
    db_session, monkeypatch
):
    """The whole point of wrapping this path in MeteredProvider: an account
    already at its daily cap must be refused here too, and the underlying
    provider must never be reached to do it."""
    monkeypatch.setattr(settings, "DEFAULT_AI_PROVIDER", "anthropic")
    monkeypatch.setattr(settings, "ANTHROPIC_API_KEY", "test-key-never-sent-over-the-wire")
    monkeypatch.setattr(settings, "PROVIDER_DAILY_TOKEN_CAP", 10)

    provider = _completion_provider()
    assert provider is not None

    reached_inner = []

    async def fail_if_reached(request):
        reached_inner.append(request)
        raise AssertionError("the inner provider must not be called at the cap")

    monkeypatch.setattr(provider.inner, "_complete_once", fail_if_reached)

    tenant = "cross-encoder-cap-tester"
    await record_usage(tenant, input_tokens=10, output_tokens=0)
    token = bind_tenant(tenant)
    try:
        with pytest.raises(ProviderSpendCapExceeded):
            await provider.complete(
                CompletionRequest(messages=[ChatMessage(role="user", content="judge this")])
            )
    finally:
        reset_tenant(token)

    assert reached_inner == [], "the cap must refuse before any network call, not after"
