"""The agent roster door: the contract apps/web/components/roster is written against.

WHY THIS FILE EXISTS

GET /api/v1/agents and GET /api/v1/agents/{slug} (app/api/v1/agents.py) were
complete, registered at app/api/v1/router.py:36, and had no caller under apps/web.
Measured in the worktree at 32883cf on 2026-09-10: a grep of apps/web for "agents"
returned five hits and not one was a request. So the roster was real and
unreachable, and nothing failed. AgentRosterPanel is the missing caller.

That panel makes four claims that are only true because of how these two routes
behave, and every one of them is a claim a future refactor could quietly falsify:

  1. The LIST route sends six fields and no arrays, so a roster row cannot state
     how many capabilities an agent declares. The panel renders "not read" there
     until the detail route answers. Add capabilities to AgentSummary and that
     honest gap becomes a needless one; drop a field and the panel drops the row.
  2. The LIST route is filtered to active agents and the DETAIL route is not, so
     `is_active` is a tautology on one and a measurement on the other. The panel
     refuses to paint the list copy as a measurement. Remove the filter, or add
     one to the detail route, and that reasoning is wrong.
  3. An unknown slug is a 404, so the panel's "the two routes disagree about the
     registry" branch describes something that can actually happen.
  4. Neither route requires a session token, so the panel does not gate itself on
     one. Add a dependency and a tokenless device silently reads nothing.

These are checked here rather than only in scripts/roster-check.ts because
web-ci.yml is path filtered to the web workspace: a change to app/api/v1/agents.py
alone never triggers it. ci.yml has no path filter. The same reasoning as
test_devon_owned_voice.py.

Nothing here needs the database. The registry is module level Python, so a bare
TestClient is enough, and neither database fixture in conftest.py is autouse.
"""

from __future__ import annotations

import pathlib

import pytest
from fastapi.testclient import TestClient

from app.main import app
from services.agents.registry import AGENT_REGISTRY, SKEPTIC

LIST_FIELDS = {"slug", "name", "purpose", "mission", "version", "is_active"}
DETAIL_ONLY_FIELDS = {
    "capabilities",
    "limitations",
    "output_format",
    "evaluation_criteria",
}

REPO_ROOT = pathlib.Path(__file__).resolve().parent


@pytest.fixture(scope="module")
def roster_client() -> TestClient:
    return TestClient(app)


def test_the_list_route_answers_and_carries_exactly_the_six_summary_fields(roster_client):
    response = roster_client.get("/api/v1/agents")
    assert response.status_code == 200, response.text
    rows = response.json()
    assert isinstance(rows, list) and rows, "the roster route returned no agents"
    for row in rows:
        assert set(row) == LIST_FIELDS, (
            f"{row.get('slug')} carries {sorted(set(row))} on the list route. "
            "AgentRosterPanel renders 'not read' for capability counts because this "
            "payload has no arrays in it; changing the shape changes what the panel "
            "is allowed to say."
        )
        for absent in DETAIL_ONLY_FIELDS:
            assert absent not in row, (
                f"{row['slug']} now sends {absent} on the list route, so the roster "
                "row can state a count it previously had to admit it had not read"
            )


def test_every_listed_slug_is_readable_on_the_detail_route(roster_client):
    slugs = [row["slug"] for row in roster_client.get("/api/v1/agents").json()]
    assert slugs, "no slugs to expand"
    for slug in slugs:
        response = roster_client.get(f"/api/v1/agents/{slug}")
        assert response.status_code == 200, (
            f"the list route offered {slug} and the detail route answered "
            f"{response.status_code}. The panel reports that as the two routes "
            "disagreeing, which is correct and is also a defect."
        )
        body = response.json()
        assert set(body) == LIST_FIELDS | DETAIL_ONLY_FIELDS, sorted(set(body))
        for field in ("capabilities", "limitations", "evaluation_criteria"):
            assert isinstance(body[field], list), f"{slug}.{field} is not a list"
            assert all(isinstance(item, str) for item in body[field]), (
                f"{slug}.{field} holds a non string; the panel drops the whole "
                "definition as malformed rather than rendering a partial one"
            )
        assert isinstance(body["output_format"], dict), (
            f"{slug}.output_format is {type(body['output_format']).__name__}. The "
            "panel walks whatever keys arrive, but it needs an object to walk and "
            "reports 'was not an object' otherwise."
        )


def test_an_unknown_slug_is_a_404_rather_than_an_empty_definition(roster_client):
    response = roster_client.get("/api/v1/agents/not-an-agent")
    assert response.status_code == 404, response.text
    assert response.json()["detail"] == "Agent not found"


def test_neither_route_requires_a_session_token(roster_client):
    # The measurement AgentRosterPanel's missing token gate is built on. A panel
    # that refused to read without a token would render a lock that is not there.
    assert "authorization" not in {
        key.lower() for key in roster_client.headers
    }, "the fixture is sending a token, so this proves nothing"
    assert roster_client.get("/api/v1/agents").status_code == 200
    assert roster_client.get("/api/v1/agents/oracle").status_code == 200
    # And a token that is not a token must not change the answer either, or the
    # panel's "send it when the device has one" would be a risk rather than a
    # convenience.
    garbage = {"Authorization": "Bearer garbage"}
    assert roster_client.get("/api/v1/agents", headers=garbage).status_code == 200
    assert roster_client.get("/api/v1/agents/oracle", headers=garbage).status_code == 200


def test_the_list_filters_by_is_active_and_the_detail_route_does_not(monkeypatch, roster_client):
    """The asymmetry the roster panel's two is_active claims rest on.

    On the list route, `is_active` can only ever read true, because list_agents()
    iterates list_active_agents(), which filters on that field. Painting it as a
    green tick there draws the filter rather than the agent. On the detail route
    it is a real read. This makes an agent inactive and measures both.
    """
    assert SKEPTIC.is_active is True, "the fixture agent is already inactive"
    monkeypatch.setattr(SKEPTIC, "is_active", False)

    listed = roster_client.get("/api/v1/agents").json()
    slugs = [row["slug"] for row in listed]
    assert "skeptic" not in slugs, "the list route no longer filters on is_active"
    assert all(row["is_active"] is True for row in listed), (
        "a list row now carries is_active false, so the field has become a real "
        "measurement on that route and the panel's non informative claim is stale"
    )

    detail = roster_client.get("/api/v1/agents/skeptic")
    assert detail.status_code == 200, (
        "the detail route has grown an is_active filter, so an inactive agent is "
        "no longer reachable by slug and the panel's 'still served by slug' line "
        "is now false"
    )
    assert detail.json()["is_active"] is False


def test_the_registry_holds_every_slug_the_two_routes_share():
    # Cheap structural cross check: the detail route reads AGENT_REGISTRY directly,
    # so a slug in the list that is not a key in the registry is impossible today
    # and is exactly the 404 branch the panel warns about.
    assert AGENT_REGISTRY, "the registry is empty"
    for slug, agent in AGENT_REGISTRY.items():
        assert slug == agent.slug, f"{slug} is filed under a different slug"


def test_the_roster_door_stays_closed():
    """A route with no caller is how every door in this estate opened.

    Deleting the panel would restore the exact condition this work was opened to
    fix, and nothing else in the estate would notice, because a component with no
    importer breaks no test and no build. So the caller is asserted here, in the
    lane with no path filter.
    """
    panel = REPO_ROOT / "apps/web/components/roster/AgentRosterPanel.tsx"
    assert panel.exists(), (
        "AgentRosterPanel.tsx is gone, so GET /api/v1/agents has no caller under "
        "apps/web again and the roster is a door once more"
    )
    source = panel.read_text(encoding="utf-8")
    assert "${API_BASE}/agents`" in source, (
        "the panel no longer fetches the roster list route"
    )
    assert "${API_BASE}/agents/${encodeURIComponent(slug)}`" in source, (
        "the panel no longer fetches the agent detail route"
    )

    page = REPO_ROOT / "apps/web/app/control/roster/page.tsx"
    assert page.exists(), "the roster panel has no page, so no person can open it"
    assert "AgentRosterPanel" in page.read_text(encoding="utf-8")
