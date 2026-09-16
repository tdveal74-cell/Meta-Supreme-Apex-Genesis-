"""Has Tee already said this on air, and can DEVON be trusted when it says no.

Three shows shipping weekly means the failure mode is not forgetting an idea,
it is making the same episode twice. Nothing in the estate watched for that
before, and there was nothing to ask it against either: measured 2026-09-16,
three rendered episodes landed in Drive inside 48 hours and not one carried a
transcript beside it.

Two properties here matter more than the rest of the file, and each is written
as the wrong answer it prevents:

1. **A draft is not an episode.** Outlines and transcripts share one table. A
   search that matches the outline and reports "you covered that" sends Tee
   looking for an episode that does not exist, and he would find the outline
   and believe the tooling. ``test_a_draft_on_the_same_subject_is_not_coverage``
   is that exact wrong answer written down.

2. **A weak match is not coverage.** Past the floor the answer is "no", with
   the nearest miss and its distance reported so the number is visible rather
   than a verdict alone. Same discipline as the parser's 0.78 floor.

The embedding provider under test is the mock, which is a normalised hashed
bag-of-words, so overlapping vocabulary really does produce a shorter distance
and an unrelated question really does land far away. The distances asserted
here are earned rather than stubbed.
"""

import pytest

from app.services.episodes import (
    COVERAGE_FLOOR,
    EPISODE_SOURCE_TYPE,
    UNTRUSTED_FOR_COVERAGE,
    decide_coverage,
    transcript_fingerprint,
)

TRANSCRIPTS = "/api/v1/episodes/transcripts"
COVERED = "/api/v1/episodes/covered"

# Written to overlap in vocabulary the way two real episodes on one subject do.
DECOMPOSE = (
    "Jobs do not disappear when a model gets good. Jobs decompose. A role is a "
    "bundle of tasks, and a model takes some tasks and leaves the rest, so the "
    "bundle gets rewritten rather than deleted. The mid career question is "
    "which tasks in your bundle are the ones a model takes first, and what the "
    "remaining bundle is worth once it has."
)

AGENT_LOG = (
    "I gave an agent seven days of my actual work and kept an honest log. It "
    "shipped four things, broke two, and spent an afternoon confidently wrong "
    "about a file path. The log is the point: the wins are boring and the "
    "failures are specific, and nobody publishes the failures."
)

SOURDOUGH = (
    "The starter wants a warm shelf and a fed schedule. Discard half, feed it "
    "flour and water by weight, and wait for the rise to double before you "
    "shape the loaf. Steam for the first fifteen minutes gives you the crust."
)


async def add(client, headers, title, transcript, **extra):
    body = {"title": title, "transcript": transcript}
    body.update(extra)
    return await client.post(TRANSCRIPTS, json=body, headers=headers)


# ---------------------------------------------------------------------------
# Storing an episode


@pytest.mark.asyncio
async def test_a_transcript_is_stored_and_listed(client, auth_headers):
    answered = await add(
        client, auth_headers, "Jobs decompose", DECOMPOSE, show="TQO", spoken_at="2026-09-16"
    )
    assert answered.status_code == 201, answered.text
    body = answered.json()
    assert body["created"] is True
    assert body["show"] == "TQO"
    assert body["chunk_count"] >= 1
    assert body["fingerprint"] == transcript_fingerprint(DECOMPOSE)

    listed = await client.get(TRANSCRIPTS, headers=auth_headers)
    assert listed.status_code == 200, listed.text
    episodes = listed.json()["episodes"]
    assert [e["title"] for e in episodes] == ["Jobs decompose"]
    assert episodes[0]["spoken_at"] == "2026-09-16"


@pytest.mark.asyncio
async def test_the_same_episode_twice_is_one_episode(client, auth_headers):
    """Renders repeat. Three exports of one episode landed in Drive under a
    single title on 2026-09-15, and three copies in the store would let one
    episode outvote the whole catalogue on every later query."""
    first = await add(client, auth_headers, "Jobs decompose", DECOMPOSE)
    second = await add(client, auth_headers, "Jobs decompose (final)", DECOMPOSE)

    assert first.json()["created"] is True
    assert second.status_code == 201, second.text
    assert second.json()["created"] is False
    assert second.json()["id"] == first.json()["id"]

    listed = await client.get(TRANSCRIPTS, headers=auth_headers)
    assert listed.json()["count"] == 1, "the same words were stored twice"


@pytest.mark.asyncio
async def test_whitespace_alone_does_not_make_a_new_episode(client, auth_headers):
    """A re-render whose container changed and whose words did not."""
    respaced = "  ".join(DECOMPOSE.split()) + "\n"
    first = await add(client, auth_headers, "Jobs decompose", DECOMPOSE)
    second = await add(client, auth_headers, "Jobs decompose", respaced)
    assert second.json()["created"] is False
    assert second.json()["id"] == first.json()["id"]


@pytest.mark.asyncio
async def test_an_empty_transcript_is_refused(client, auth_headers):
    answered = await client.post(
        TRANSCRIPTS, json={"title": "Nothing", "transcript": "   "}, headers=auth_headers
    )
    assert answered.status_code == 422, answered.text


@pytest.mark.asyncio
async def test_the_routes_need_an_account(client):
    assert (await client.get(COVERED, params={"q": "anything"})).status_code == 401
    assert (await client.get(TRANSCRIPTS)).status_code == 401
    assert (
        await client.post(TRANSCRIPTS, json={"title": "x", "transcript": "y"})
    ).status_code == 401


# ---------------------------------------------------------------------------
# The verdict, tested where it can actually be tested
#
# decide_coverage is pure, so these run on distances chosen by the test
# rather than on a provider that cannot rank these documents. That split is
# the point: tuning a threshold until an end-to-end test goes green is how a
# floor ends up meaning nothing.


def hit(title, distance, chunk=0):
    return {
        "knowledge_item_id": f"id-{title}",
        "title": title,
        "content": f"a passage from {title}",
        "chunk_index": chunk,
        "distance": distance,
    }


def test_nothing_stored_is_an_empty_catalogue_not_a_no():
    """"I have never covered that" and "I have nothing to check" are different
    claims, and reporting the second as the first is how an empty store reads
    as a confident answer."""
    verdict = decide_coverage([], question="anything", floor=0.45)
    assert verdict["covered"] is False
    assert verdict["answerable"] is True
    assert "empty catalogue" in verdict["reason"]
    assert verdict["nearest"] is None


def test_a_passage_inside_the_floor_is_coverage():
    verdict = decide_coverage(
        [hit("Jobs decompose", 0.21), hit("Agent log", 0.88)],
        question="do jobs decompose",
        floor=0.45,
    )
    assert verdict["covered"] is True
    assert [m["title"] for m in verdict["matches"]] == ["Jobs decompose"]
    assert verdict["nearest"]["title"] == "Jobs decompose"


def test_every_passage_past_the_floor_is_not_coverage():
    verdict = decide_coverage(
        [hit("Jobs decompose", 0.61), hit("Agent log", 0.94)],
        question="sourdough starter schedule",
        floor=0.45,
    )
    assert verdict["covered"] is False
    assert verdict["matches"] == []
    # The nearest miss carries its number, so the floor is visible rather than
    # a verdict handed down.
    assert verdict["nearest"]["title"] == "Jobs decompose"
    assert verdict["nearest"]["distance"] == pytest.approx(0.61)
    assert "past the floor" in verdict["reason"]


def test_the_boundary_is_inclusive_so_the_floor_is_a_floor():
    assert decide_coverage([hit("A", 0.45)], question="q", floor=0.45)["covered"] is True
    assert (
        decide_coverage([hit("A", 0.4501)], question="q", floor=0.45)["covered"] is False
    )


def test_moving_the_floor_moves_the_verdict_and_nothing_else():
    hits = [hit("Jobs decompose", 0.50)]
    assert decide_coverage(hits, question="q", floor=0.45)["covered"] is False
    assert decide_coverage(hits, question="q", floor=0.60)["covered"] is True


def test_the_closest_of_several_is_the_one_reported():
    verdict = decide_coverage(
        [hit("Agent log", 0.40), hit("Jobs decompose", 0.12), hit("Third", 0.44)],
        question="q",
        floor=0.45,
    )
    assert verdict["covered"] is True
    assert verdict["nearest"]["title"] == "Jobs decompose"
    assert len(verdict["matches"]) == 3


def test_the_floor_is_a_distance_and_not_a_similarity():
    """pgvector's <=> is a DISTANCE: smaller is closer. A floor above 1.0 would
    accept nearly anything as coverage, which is the failure that reads as a
    working feature."""
    assert 0.0 < COVERAGE_FLOOR < 1.0
    assert EPISODE_SOURCE_TYPE == "episode_transcript"


# ---------------------------------------------------------------------------
# The provider that cannot answer


def test_the_mock_provider_is_named_untrusted_for_a_verdict():
    assert "mock" in UNTRUSTED_FOR_COVERAGE


@pytest.mark.asyncio
async def test_coverage_refuses_rather_than_guessing_on_a_mock_provider(
    client, auth_headers
):
    """The load bearing test.

    Measured 2026-09-16 on MockEmbeddingProvider, a normalised hashed
    bag-of-words: an on topic question scored 0.6170 against the jobs episode
    and a SOURDOUGH RECIPE scored 0.6406 against the same episode. Two
    hundredths. No floor separates those, so a deployment that fell back to
    mock embeddings would answer "yes, you covered that" about an episode
    that does not exist, in this feature's own confident voice.

    `answerable` false is a different claim from `covered` false, and the
    route has to keep them apart.
    """
    await add(client, auth_headers, "Jobs decompose", DECOMPOSE, show="TQO")

    answered = await client.get(
        COVERED,
        params={"q": "do jobs disappear or do the tasks inside a role get rewritten"},
        headers=auth_headers,
    )
    assert answered.status_code == 200, answered.text
    body = answered.json()
    assert body["answerable"] is False, body
    assert body["covered"] is False
    assert body["matches"] == []
    assert "mock" in body["reason"]
    assert "not a claim about the catalogue" in body["reason"]


@pytest.mark.asyncio
async def test_the_recipe_gets_the_same_refusal_rather_than_a_different_one(
    client, auth_headers
):
    """A refusal that varied with the question would be a verdict wearing a
    refusal's clothes."""
    await add(client, auth_headers, "Jobs decompose", DECOMPOSE, show="TQO")
    on_topic = await client.get(
        COVERED, params={"q": "do jobs decompose into tasks"}, headers=auth_headers
    )
    recipe = await client.get(COVERED, params={"q": SOURDOUGH}, headers=auth_headers)
    assert on_topic.json()["reason"] == recipe.json()["reason"]
    assert on_topic.json()["answerable"] is False
    assert recipe.json()["answerable"] is False


# ---------------------------------------------------------------------------
# The filter on the path that actually asks the question


@pytest.mark.asyncio
async def test_the_coverage_query_always_asks_for_episodes_only(monkeypatch):
    """Found by mutation: deleting ``source_types`` from ``already_covered``
    changed nothing any test could see.

    The refusal on a mock provider returns before the query runs, so on this
    estate's test configuration the filter is never reached end to end. It is
    still the line that stops a draft outline being reported as something said
    on air. This pins it on the real path by standing in for the search and
    reading what it was asked for.
    """
    import app.services.episodes as episodes

    seen = {}

    async def fake_search(db, **kwargs):
        seen.update(kwargs)
        return []

    monkeypatch.setattr(episodes, "search_knowledge", fake_search)
    monkeypatch.setattr(episodes, "embedding_provider_name", lambda: "openai")

    await episodes.already_covered(None, owner_id="owner-1", question="jobs decompose")

    assert seen.get("source_types") == [episodes.EPISODE_SOURCE_TYPE], (
        "the coverage query stopped narrowing to episode transcripts, so a "
        "draft can now be reported as something said on air"
    )
    assert seen.get("owner_id") == "owner-1"


@pytest.mark.asyncio
async def test_a_trusted_provider_actually_reaches_the_search(monkeypatch):
    """Guards the guard: if the refusal ever swallowed every provider, the
    test above would pass while the feature answered nothing to anyone."""
    import app.services.episodes as episodes

    called = []

    async def fake_search(db, **kwargs):
        called.append(kwargs)
        return [hit("Jobs decompose", 0.10)]

    monkeypatch.setattr(episodes, "search_knowledge", fake_search)
    monkeypatch.setattr(episodes, "embedding_provider_name", lambda: "openai")

    verdict = await episodes.already_covered(
        None, owner_id="owner-1", question="jobs decompose"
    )
    assert called, "a trusted provider never reached the search"
    assert verdict["answerable"] is True
    assert verdict["covered"] is True


# ---------------------------------------------------------------------------
# The source filter, which is what keeps a draft out of the answer


@pytest.mark.asyncio
async def test_the_search_filter_separates_drafts_from_episodes(client, auth_headers):
    """An outline and a transcript sit in the same table. If the coverage
    query ever matched the outline, DEVON would tell Tee he had already made
    an episode that exists only as a note, and he would find the note and
    trust the tooling.

    Asserted on the filter itself rather than through a verdict, because the
    verdict is refused on this provider and would pass for the wrong reason.
    """
    from app.db.session import AsyncSessionLocal
    from app.services.knowledge import search_knowledge

    await client.post(
        "/api/v1/knowledge",
        json={
            "title": "TQO 13 outline, jobs decompose",
            "content": DECOMPOSE,
            "source_type": "markdown",
        },
        headers=auth_headers,
    )
    stored = await add(client, auth_headers, "Jobs decompose", AGENT_LOG, show="TQO")
    assert stored.status_code == 201, stored.text

    listed = await client.get(TRANSCRIPTS, headers=auth_headers)
    owner_id = None
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        from app.models.knowledge import KnowledgeItem

        rows = (await session.execute(select(KnowledgeItem))).scalars().all()
        assert {r.source_type for r in rows} == {"markdown", EPISODE_SOURCE_TYPE}, rows
        owner_id = rows[0].owner_id

        episodes_only = await search_knowledge(
            session,
            owner_id=owner_id,
            query="jobs decompose into tasks",
            source_types=[EPISODE_SOURCE_TYPE],
        )
        everything = await search_knowledge(
            session, owner_id=owner_id, query="jobs decompose into tasks"
        )

    assert episodes_only, "the filter returned nothing at all"
    assert {h["source_type"] for h in episodes_only} == {EPISODE_SOURCE_TYPE}
    # The draft is still in the store and still findable; the filter narrows
    # the question rather than hiding the item. Without this, a bug that
    # dropped the draft entirely would pass the assertion above.
    assert "markdown" in {h["source_type"] for h in everything}
    assert listed.json()["count"] == 1


@pytest.mark.asyncio
async def test_an_empty_source_type_list_matches_nothing_rather_than_everything(
    client, auth_headers
):
    """Collapsing [] to None would turn a caller that filtered down to nothing
    into a caller that searched the whole store, which is the direction that
    invents an answer."""
    from app.db.session import AsyncSessionLocal
    from app.services.knowledge import search_knowledge

    await add(client, auth_headers, "Jobs decompose", DECOMPOSE)
    async with AsyncSessionLocal() as session:
        from sqlalchemy import select

        from app.models.knowledge import KnowledgeItem

        owner_id = (await session.execute(select(KnowledgeItem))).scalars().first().owner_id
        none_wanted = await search_knowledge(
            session, owner_id=owner_id, query="jobs", source_types=[]
        )
        any_wanted = await search_knowledge(session, owner_id=owner_id, query="jobs")

    assert none_wanted == []
    assert any_wanted, "the unfiltered search returned nothing, so the test proves little"


@pytest.mark.asyncio
async def test_a_nonsense_floor_is_refused(client, auth_headers):
    for bad in (0, -1, 2.5):
        answered = await client.get(
            COVERED, params={"q": "anything", "floor": bad}, headers=auth_headers
        )
        assert answered.status_code == 422, f"floor {bad} was accepted"


@pytest.mark.asyncio
async def test_an_empty_question_searches_nothing(client, auth_headers):
    await add(client, auth_headers, "Jobs decompose", DECOMPOSE)
    answered = await client.get(COVERED, params={"q": "   "}, headers=auth_headers)
    body = answered.json()
    assert body["covered"] is False
    assert body["matches"] == []
    assert "no question" in body["reason"]
