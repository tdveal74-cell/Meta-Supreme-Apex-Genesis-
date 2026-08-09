"""Knowledge pipeline tests: chunking, embeddings, API, and Council wiring."""

import pytest

from services.intelligence.providers import (
    MockEmbeddingProvider,
    ProviderConfigError,
    create_embedding_provider,
)
from services.knowledge import chunk_text

# ---------------------------------------------------------------------------
# Chunking (pure unit)
# ---------------------------------------------------------------------------

def test_chunk_text_empty_yields_nothing():
    assert chunk_text("") == []
    assert chunk_text("   \n\n  ") == []


def test_chunk_text_short_text_is_one_chunk():
    chunks = chunk_text("A short note about pricing strategy.")
    assert len(chunks) == 1
    assert chunks[0].index == 0
    assert "pricing" in chunks[0].content


def test_chunk_text_long_text_splits_with_overlap():
    paragraph = "The quarterly numbers show steady growth in every region. " * 8
    text = "\n\n".join(paragraph for _ in range(6))
    chunks = chunk_text(text, chunk_chars=600, overlap_chars=100)
    assert len(chunks) > 1
    assert [c.index for c in chunks] == list(range(len(chunks)))
    # Overlap: the start of chunk N shares text with the tail of chunk N-1.
    assert chunks[1].content[:50] in chunks[0].content


# ---------------------------------------------------------------------------
# Embedding providers
# ---------------------------------------------------------------------------

async def test_mock_embeddings_are_deterministic_and_normalized():
    provider = MockEmbeddingProvider()
    first = await provider.embed(["solar panel efficiency"])
    second = await provider.embed(["solar panel efficiency"])
    assert first.vectors == second.vectors
    assert len(first.vectors[0]) == 1536
    norm = sum(v * v for v in first.vectors[0]) ** 0.5
    assert abs(norm - 1.0) < 1e-6


async def test_mock_embeddings_shared_vocabulary_is_closer():
    provider = MockEmbeddingProvider()
    result = await provider.embed(
        [
            "solar panel efficiency and irradiance",
            "solar panel efficiency metrics",
            "bread dough kneading technique",
        ]
    )
    base, related, unrelated = result.vectors

    def cosine(a, b):
        return sum(x * y for x, y in zip(a, b, strict=True))

    assert cosine(base, related) > cosine(base, unrelated)


def test_embedding_factory_validates_config():
    assert create_embedding_provider("mock").name == "mock"
    with pytest.raises(ProviderConfigError):
        create_embedding_provider("openai")  # no key
    with pytest.raises(ProviderConfigError):
        create_embedding_provider("faiss")  # unknown


# ---------------------------------------------------------------------------
# Knowledge API (integration)
# ---------------------------------------------------------------------------

async def test_knowledge_ingest_list_get_delete(client, auth_headers):
    created = await client.post(
        "/api/v1/knowledge",
        json={
            "title": "Solar research",
            "content": "Solar panel efficiency depends on temperature and irradiance.",
            "source_type": "manual",
        },
        headers=auth_headers,
    )
    assert created.status_code == 201, created.text
    item = created.json()
    assert item["status"] == "ready"
    assert item["chunk_count"] == 1
    assert item["metadata"]["simulated_embeddings"] is True  # transparent

    listed = await client.get("/api/v1/knowledge", headers=auth_headers)
    assert [i["id"] for i in listed.json()] == [item["id"]]

    fetched = await client.get(f"/api/v1/knowledge/{item['id']}", headers=auth_headers)
    assert fetched.status_code == 200
    assert fetched.json()["chunk_count"] == 1

    deleted = await client.delete(
        f"/api/v1/knowledge/{item['id']}", headers=auth_headers
    )
    assert deleted.status_code == 204
    assert (await client.get("/api/v1/knowledge", headers=auth_headers)).json() == []


async def test_knowledge_search_ranks_relevant_first(client, auth_headers):
    for title, content in [
        ("Solar notes", "Solar panel efficiency depends on cell temperature."),
        ("Baking notes", "Knead the dough and let it rise until doubled in size."),
    ]:
        response = await client.post(
            "/api/v1/knowledge",
            json={"title": title, "content": content},
            headers=auth_headers,
        )
        assert response.status_code == 201

    search = await client.post(
        "/api/v1/knowledge/search",
        json={"query": "how efficient are solar panels?", "limit": 2},
        headers=auth_headers,
    )
    assert search.status_code == 200, search.text
    hits = search.json()
    assert hits[0]["title"] == "Solar notes"
    assert hits[0]["distance"] < hits[-1]["distance"]


async def test_knowledge_ownership_enforced(client, auth_headers):
    created = await client.post(
        "/api/v1/knowledge",
        json={"title": "Private doc", "content": "Sensitive planning details."},
        headers=auth_headers,
    )
    item_id = created.json()["id"]

    await client.post(
        "/api/v1/auth/register",
        json={"email": "other-k@example.com", "password": "password-123456"},
    )
    login = await client.post(
        "/api/v1/auth/login",
        json={"email": "other-k@example.com", "password": "password-123456"},
    )
    other = {"Authorization": f"Bearer {login.json()['access_token']}"}

    assert (await client.get("/api/v1/knowledge", headers=other)).json() == []
    assert (
        await client.get(f"/api/v1/knowledge/{item_id}", headers=other)
    ).status_code == 404
    search = await client.post(
        "/api/v1/knowledge/search",
        json={"query": "sensitive planning"},
        headers=other,
    )
    assert search.json() == []  # other users' knowledge is invisible


async def test_council_response_cites_knowledge_sources(client, auth_headers):
    await client.post(
        "/api/v1/knowledge",
        json={
            "title": "Beta launch criteria",
            "content": "The beta launch requires ninety percent test coverage and "
            "a completed security review before any public availability.",
        },
        headers=auth_headers,
    )

    conversation = await client.post(
        "/api/v1/conversations", json={}, headers=auth_headers
    )
    sent = await client.post(
        f"/api/v1/conversations/{conversation.json()['id']}/messages",
        json={"content": "Should we proceed with the beta launch?"},
        headers=auth_headers,
    )
    assert sent.status_code == 200, sent.text
    meta = sent.json()["assistant_message"]["metadata"]
    sources = meta["knowledge_sources"]
    assert sources, "expected retrieved knowledge to be cited"
    assert sources[0]["title"] == "Beta launch criteria"
    assert "distance" in sources[0]  # transparency: scores are exposed
