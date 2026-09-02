"""Fix PR 9 from the DEVON and Hermes audit, H9: the FKR query route.

POST /api/v1/knowledge/query returned 500 on every request. The ACL
predicate bound the untyped :project_id three times, and asyncpg raised
AmbiguousParameterError because a NULL check and two uuid comparisons
could not agree on one type. The binds now carry CAST(:project_id AS uuid).
No test exercised the route or its SQL before this one.
"""

from __future__ import annotations

import uuid


async def _ingest(client, auth_headers) -> None:
    for title, content in [
        ("Solar notes", "Solar panel efficiency depends on cell temperature."),
        ("Baking notes", "Knead the dough and let it rise until doubled in size."),
    ]:
        response = await client.post(
            "/api/v1/knowledge",
            json={"title": title, "content": content},
            headers=auth_headers,
        )
        assert response.status_code == 201, response.text


async def test_fkr_query_answers_without_a_project(client, auth_headers):
    await _ingest(client, auth_headers)
    response = await client.post(
        "/api/v1/knowledge/query",
        json={"query": "how efficient are solar panels?", "limit": 2},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    assert "Solar" in response.text


async def test_fkr_query_answers_with_a_project_filter(client, auth_headers):
    await _ingest(client, auth_headers)
    response = await client.post(
        "/api/v1/knowledge/query",
        json={"query": "solar panels", "limit": 2, "project_id": str(uuid.uuid4())},
        headers=auth_headers,
    )
    assert response.status_code == 200, response.text
    # The items were filed without a project, so a project filter matches nothing.
    assert "Solar" not in response.text


async def test_fkr_query_refuses_a_project_id_that_is_not_a_uuid(client, auth_headers):
    response = await client.post(
        "/api/v1/knowledge/query",
        json={"query": "solar panels", "project_id": "not-a-uuid"},
        headers=auth_headers,
    )
    assert response.status_code == 422, response.text
