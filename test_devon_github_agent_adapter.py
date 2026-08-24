"""Network-isolated tests for the DEVON GitHub capability adapter."""

import base64
import json

import httpx
import pytest

REPO = "tdveal74-cell/Meta-Supreme-Apex-Genesis-"
BASE_SHA = "b" * 40
EXPECTED_HEAD_SHA = "a" * 40


def _configure_github(monkeypatch, handler):
    from app.services.agent_tasks import github_client

    monkeypatch.setattr(github_client, "token", "test-secret-token")
    monkeypatch.setattr(github_client, "allowed_repos", {REPO})
    monkeypatch.setattr(github_client, "base_url", "https://api.github.test")
    monkeypatch.setattr(github_client, "transport", httpx.MockTransport(handler))
    return github_client


@pytest.mark.asyncio
async def test_github_read_file_runs_without_approval_and_never_exposes_token(
    client,
    auth_headers,
    monkeypatch,
):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.headers["authorization"] == "Bearer test-secret-token"
        assert request.method == "GET"
        assert request.url.path.endswith("/contents/README.md")
        raw = b"DEVON github read works\n"
        return httpx.Response(
            200,
            json={
                "type": "file",
                "encoding": "base64",
                "sha": "c" * 40,
                "size": len(raw),
                "content": base64.b64encode(raw).decode("ascii"),
                "html_url": "https://github.test/readme",
            },
        )

    _configure_github(monkeypatch, handler)

    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Read the canonical README",
            "steps": [
                {
                    "title": "Read README",
                    "tool": "github.read_file",
                    "arguments": {
                        "repository": REPO,
                        "path": "README.md",
                        "ref": "main",
                    },
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]

    run = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    assert run.status_code == 200, run.text
    task = run.json()["task"]
    assert task["state"] == "completed"
    assert "DEVON github read works" in task["observations"][0]["output"]
    assert "test-secret-token" not in task["observations"][0]["output"]
    assert "response" not in task["observations"][0]["metadata"]
    assert len(requests) == 1

    catalog = await client.get("/api/v1/agent-tasks/tools", headers=auth_headers)
    assert catalog.status_code == 200
    rendered = catalog.text
    assert "test-secret-token" not in rendered
    assert catalog.json()["github"]["configured"] is True
    assert catalog.json()["github"]["allowed_repositories"] == [REPO]
    assert catalog.json()["github"]["token_exposed"] is False


@pytest.mark.asyncio
async def test_github_create_branch_waits_for_exact_approval_and_replays_once(
    client,
    auth_headers,
    monkeypatch,
):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append((request.method, request.url.path, request.content))
        assert request.headers["authorization"] == "Bearer test-secret-token"
        if request.method == "GET" and "/git/ref/heads/" in request.url.path:
            return httpx.Response(200, json={"object": {"sha": BASE_SHA}})
        if request.method == "POST" and request.url.path.endswith("/git/refs"):
            return httpx.Response(
                201,
                json={
                    "ref": "refs/heads/devon-test-branch",
                    "object": {"sha": BASE_SHA},
                },
            )
        return httpx.Response(500, json={"message": "unexpected request"})

    _configure_github(monkeypatch, handler)

    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Create an approved GitHub branch",
            "steps": [
                {
                    "title": "Create branch",
                    "tool": "github.create_branch",
                    "arguments": {
                        "repository": REPO,
                        "branch": "devon-test-branch",
                        "base_ref": "main",
                    },
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]

    waiting = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    assert waiting.status_code == 200, waiting.text
    body = waiting.json()
    assert body["task"]["state"] == "waiting_approval"
    assert requests == []

    step = body["task"]["plan"]["steps"][0]
    decision = await client.post(
        "/api/v1/devon/approvals/decide",
        json={
            "request_id": step["approval_request_id"],
            "token": body["approval_token"],
            "decision": "approve",
            "decided_by": "Tee",
        },
    )
    assert decision.status_code == 200, decision.text
    assert decision.json()["approved"] is True

    resumed = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["task"]["state"] == "completed"
    assert [item[0] for item in requests] == ["GET", "POST"]

    replay = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    assert replay.status_code == 200
    assert replay.json()["task"]["state"] == "completed"
    assert [item[0] for item in requests] == ["GET", "POST"]


@pytest.mark.asyncio
async def test_github_non_allowlisted_repository_fails_closed_without_network(
    client,
    auth_headers,
    monkeypatch,
):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={})

    _configure_github(monkeypatch, handler)

    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Attempt an out-of-scope repository read",
            "steps": [
                {
                    "title": "Read other repo",
                    "tool": "github.repo_status",
                    "arguments": {"repository": "someone/other-repo"},
                }
            ],
        },
    )
    assert created.status_code == 201, created.text

    run = await client.post(
        f"/api/v1/agent-tasks/{created.json()['task_id']}/run",
        headers=auth_headers,
        json={},
    )
    assert run.status_code == 200
    task = run.json()["task"]
    assert task["state"] == "failed"
    assert "not allowlisted" in task["failure_reason"]
    assert requests == []


@pytest.mark.asyncio
async def test_github_merge_is_pinned_to_exact_head_and_replays_once(
    client,
    auth_headers,
    monkeypatch,
):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        assert request.method == "PUT"
        assert request.url.path.endswith("/pulls/25/merge")
        payload = json.loads(request.content.decode("utf-8"))
        assert payload == {"merge_method": "merge", "sha": EXPECTED_HEAD_SHA}
        return httpx.Response(200, json={"merged": True, "sha": "d" * 40})

    _configure_github(monkeypatch, handler)

    catalog = await client.get("/api/v1/agent-tasks/tools", headers=auth_headers)
    specs = {item["name"]: item for item in catalog.json()["tools"]}
    assert specs["github.merge_pull_request"]["risk"] == "high_impact"
    assert specs["github.merge_pull_request"]["approval_required"] is True

    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Merge a verified PR",
            "steps": [
                {
                    "title": "Merge PR",
                    "tool": "github.merge_pull_request",
                    "arguments": {
                        "repository": REPO,
                        "number": 25,
                        "merge_method": "merge",
                        "expected_head_sha": EXPECTED_HEAD_SHA,
                    },
                }
            ],
        },
    )
    assert created.status_code == 201, created.text
    task_id = created.json()["task_id"]
    waiting = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    assert waiting.status_code == 200
    waiting_body = waiting.json()
    assert waiting_body["task"]["state"] == "waiting_approval"
    assert requests == []

    step = waiting_body["task"]["plan"]["steps"][0]
    decision = await client.post(
        "/api/v1/devon/approvals/decide",
        json={
            "request_id": step["approval_request_id"],
            "token": waiting_body["approval_token"],
            "decision": "approve",
            "decided_by": "Tee",
        },
    )
    assert decision.status_code == 200
    assert decision.json()["approved"] is True

    resumed = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    assert resumed.status_code == 200, resumed.text
    assert resumed.json()["task"]["state"] == "completed"
    assert len(requests) == 1

    replay = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    assert replay.status_code == 200
    assert replay.json()["task"]["state"] == "completed"
    assert len(requests) == 1


@pytest.mark.asyncio
async def test_github_merge_without_expected_head_fails_after_approval_without_network(
    client,
    auth_headers,
    monkeypatch,
):
    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(200, json={"merged": True})

    _configure_github(monkeypatch, handler)
    created = await client.post(
        "/api/v1/agent-tasks",
        headers=auth_headers,
        json={
            "goal": "Attempt an unpinned merge",
            "steps": [
                {
                    "title": "Merge PR without revision pin",
                    "tool": "github.merge_pull_request",
                    "arguments": {"repository": REPO, "number": 25},
                }
            ],
        },
    )
    assert created.status_code == 201
    task_id = created.json()["task_id"]
    waiting = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    step = waiting.json()["task"]["plan"]["steps"][0]
    decision = await client.post(
        "/api/v1/devon/approvals/decide",
        json={
            "request_id": step["approval_request_id"],
            "token": waiting.json()["approval_token"],
            "decision": "approve",
        },
    )
    assert decision.json()["approved"] is True

    resumed = await client.post(
        f"/api/v1/agent-tasks/{task_id}/run",
        headers=auth_headers,
        json={},
    )
    assert resumed.status_code == 200
    assert resumed.json()["task"]["state"] == "failed"
    assert "expected_head_sha is required" in resumed.json()["task"]["failure_reason"]
    assert requests == []


@pytest.mark.asyncio
async def test_github_approved_binding_cannot_be_reused_for_changed_arguments():
    from services.agent_runtime.governance import (
        APPROVAL_METADATA_KEY,
        RUNTIME_REQUESTED_BY,
        approval_binding,
        approval_marker,
    )
    from services.agent_runtime.tools import ToolRegistry
    from services.devon.approval import ApprovalQueue
    from services.github.agent_adapter import GitHubCapabilityAdapter
    from services.github.client import GitHubRESTClient

    requests = []

    def handler(request: httpx.Request) -> httpx.Response:
        requests.append(request)
        return httpx.Response(500, json={"message": "network must not be reached"})

    approvals = ApprovalQueue()
    original = {
        "repository": REPO,
        "branch": "approved-branch",
        "base_ref": "main",
    }
    binding = approval_binding(
        task_id="TASK-BOUND",
        step_id="STEP-01",
        tool_name="github.create_branch",
        arguments=original,
    )
    record, token = approvals.request(
        title="Bound GitHub branch",
        what_happens=f"Create the approved branch. {approval_marker(binding)}",
        requested_by=RUNTIME_REQUESTED_BY,
    )
    assert approvals.decide(record.request_id, token, "approve").approved is True

    client = GitHubRESTClient(
        token="test-secret-token",
        allowed_repos=[REPO],
        base_url="https://api.github.test",
        transport=httpx.MockTransport(handler),
    )
    registry = ToolRegistry()
    GitHubCapabilityAdapter(client, approvals).register(registry)

    mutated = dict(original)
    mutated["branch"] = "substituted-branch"
    mutated[APPROVAL_METADATA_KEY] = {
        "request_id": record.request_id,
        "binding": binding,
        "task_id": "TASK-BOUND",
        "step_id": "STEP-01",
        "tool_name": "github.create_branch",
    }
    result = await registry.execute("github.create_branch", mutated)
    assert result.ok is False
    assert "does not match these arguments" in result.error
    assert requests == []


def test_github_client_requires_exact_allowlisted_repository():
    from services.github.client import GitHubRESTClient, GitHubRESTError

    gh = GitHubRESTClient(token="token", allowed_repos=[REPO])
    assert gh.require_repository(REPO) == REPO
    with pytest.raises(GitHubRESTError, match="not allowlisted"):
        gh.require_repository("tdveal74-cell/something-else")
    with pytest.raises(GitHubRESTError, match="exact owner/name"):
        gh.require_repository("https://github.com/tdveal74-cell/Meta-Supreme-Apex-Genesis-")


def test_github_client_does_not_fall_back_to_generic_github_token(monkeypatch):
    from services.github.client import GitHubRESTClient

    monkeypatch.delenv("DEVON_GITHUB_TOKEN", raising=False)
    monkeypatch.setenv("GITHUB_TOKEN", "generic-token-that-must-not-be-used")
    gh = GitHubRESTClient(allowed_repos=[REPO])
    assert gh.token == ""
    assert gh.configured is False


@pytest.mark.asyncio
async def test_github_read_refuses_non_utf8_file_content():
    from services.github.client import GitHubRESTClient, GitHubRESTError

    def handler(request: httpx.Request) -> httpx.Response:
        raw = b"\xff\xfe\x00"
        return httpx.Response(
            200,
            json={
                "type": "file",
                "encoding": "base64",
                "sha": "e" * 40,
                "size": len(raw),
                "content": base64.b64encode(raw).decode("ascii"),
            },
        )

    gh = GitHubRESTClient(
        token="token",
        allowed_repos=[REPO],
        base_url="https://api.github.test",
        transport=httpx.MockTransport(handler),
    )
    with pytest.raises(GitHubRESTError, match="not valid UTF-8"):
        await gh.read_file(REPO, "binary.dat", ref="main")
