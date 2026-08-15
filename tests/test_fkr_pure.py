"""Pure-unit tests for FKR distillation, synthesis, and RRF wiring."""

from __future__ import annotations

from services.knowledge.distillation import distill_content
from services.knowledge.retrieval import RetrievalCandidate
from services.knowledge.synthesis import synthesize_with_governance


def test_distill_rejects_empty():
    try:
        distill_content(title="x", content="")
        assert False, "expected ValueError"
    except ValueError:
        pass


def test_distill_produces_searchable_text():
    doc = distill_content(
        title="EditForge dailies",
        content="EditForge review gates require human approval before publish. "
        "n8n pipelines feed the queue.",
        source="manual",
    )
    assert "EditForge" in doc.searchable_text
    assert doc.summary
    assert doc.simulated is True


def test_synthesize_refuses_without_candidates():
    result = synthesize_with_governance(
        query="what is the publish gate?",
        candidates=[],
        owner_id="00000000-0000-0000-0000-000000000001",
    )
    assert result.cleared is False
    assert result.refusal_reason == "no_candidates"
    assert "not invent" in result.answer.lower() or "will not invent" in result.answer.lower()


def test_synthesize_cites_candidates():
    candidates = [
        RetrievalCandidate(
            embedding_id="e1",
            knowledge_item_id="k1",
            title="Publish policy",
            content="Human approval is required before any Published status.",
            chunk_index=0,
            score=0.05,
            signals={"dense": 1.0, "sparse": 1.0, "rarity": 0.0, "age": 0.8},
        )
    ]
    result = synthesize_with_governance(
        query="publish rules",
        candidates=candidates,
        owner_id="00000000-0000-0000-0000-000000000001",
    )
    assert result.cleared is True
    assert len(result.citations) == 1
    assert result.citations[0].title == "Publish policy"
    assert "[1]" in result.answer
