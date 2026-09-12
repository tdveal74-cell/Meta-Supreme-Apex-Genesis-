"""Fix PR 9 from the DEVON and Hermes audit, H9, and its critic's follow-up.

POST /api/v1/knowledge/query returned 500 on every request. The ACL
predicate bound the untyped :project_id three times, and asyncpg raised
AmbiguousParameterError because a NULL check and two uuid comparisons
could not agree on one type. The binds now carry CAST(:project_id AS uuid).
No test exercised the route or its SQL before this one.

The critic on that fix found the ingest route one line above untouched:
project_id was an untyped string with no owner check, so a non-uuid and an
unknown id failed as 500 inside the insert and another account's project id
was accepted with 201. It is typed and owner-checked now, and the project
filter is proven on a match, not only on a miss.
"""

from __future__ import annotations

import uuid


async def _ingest(client, auth_headers, project_id: str | None = None) -> None:
    for title, content in [
        ("Solar notes", "Solar panel efficiency depends on cell temperature."),
        ("Baking notes", "Knead the dough and let it rise until doubled in size."),
    ]:
        response = await client.post(
            "/api/v1/knowledge",
            json={"title": title, "content": content, "project_id": project_id},
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text


async def _project(client, auth_headers, name: str = "Solar study") -> str:
    created = await client.post(
        "/api/v1/projects", json={"name": name}, headers=auth_headers
    )
    assert created.status_code == 201, created.text
    return created.json()["id"]


async def _query(client, headers, **body):
    response = await client.post(
        "/api/v1/knowledge/query",
        json={"query": "how efficient are solar panels?", "limit": 3, **body},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return {candidate["title"] for candidate in response.json()["candidates"]}


async def _second_account(client) -> dict:
    email, password = "second-reader@example.com", "another-strong-password-123"
    registered = await client.post(
        "/api/v1/auth/register",
        json={"email": email, "password": password, "full_name": "Second Reader"},
    )
    assert registered.status_code == 201, registered.text
    login = await client.post("/api/v1/auth/login", json={"email": email, "password": password})
    assert login.status_code == 200, login.text
    return {"Authorization": f"Bearer {login.json()['access_token']}"}


async def test_fkr_query_answers_without_a_project(client, auth_headers):
    await _ingest(client, auth_headers)
    assert "Solar notes" in await _query(client, auth_headers)


async def test_fkr_query_project_filter_matches_what_was_filed_under_it(client, auth_headers):
    project_id = await _project(client, auth_headers)
    await _ingest(client, auth_headers, project_id=project_id)
    loose = await client.post(
        "/api/v1/knowledge",
        json={"title": "Loose solar", "content": "Solar cells lose output as they heat up."},
        headers=auth_headers,
    )
    assert loose.status_code == 201, loose.text

    filtered = await _query(client, auth_headers, project_id=project_id)
    assert "Solar notes" in filtered
    assert "Loose solar" not in filtered, "an item filed without a project is outside the filter"
    assert "Solar notes" in await _query(client, auth_headers)
    assert await _query(client, auth_headers, project_id=str(uuid.uuid4())) == set()


async def test_fkr_query_refuses_a_project_id_that_is_not_a_uuid(client, auth_headers):
    response = await client.post(
        "/api/v1/knowledge/query",
        json={"query": "solar panels", "project_id": "not-a-uuid"},
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text


async def test_fkr_ingest_files_under_an_owned_project_only(client, auth_headers):
    project_id = await _project(client, auth_headers)
    body = {"title": "FKR solar", "content": "Solar inverters clip above their rated output."}

    filed = await client.post(
        "/api/v1/knowledge/ingest",
        json={**body, "project_id": project_id},
        headers=auth_headers,
    )
    assert filed.status_code == 201, filed.text
    assert "FKR solar" in await _query(client, auth_headers, project_id=project_id)

    malformed = await client.post(
        "/api/v1/knowledge/ingest",
        json={**body, "project_id": "not-a-uuid"},
        headers=auth_headers,
    )
    assert malformed.status_code == 422, malformed.text

    unknown = await client.post(
        "/api/v1/knowledge/ingest",
        json={**body, "project_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert unknown.status_code == 404, unknown.text

    other = await _second_account(client)
    theirs = await client.post(
        "/api/v1/knowledge/ingest",
        json={**body, "project_id": project_id},
        headers=other,
    )
    assert theirs.status_code == 404, theirs.text
    assert theirs.json()["detail"] == unknown.json()["detail"], "unowned and unknown answer alike"
    assert await _query(client, other, project_id=project_id) == set()
