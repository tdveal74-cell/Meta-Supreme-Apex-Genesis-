import json
import time
from uuid import uuid4

import httpx
import pytest

from app.services.devon_browser import DevonBrowserAdapter
from services.agent_runtime.governance import (
    APPROVAL_METADATA_KEY,
    RUNTIME_REQUESTED_BY,
    approval_binding,
    approval_marker,
)
from services.agent_runtime.tools import ToolRegistry
from services.devon.approval import ApprovalQueue, ApprovalState

OWNER = str(uuid4())
KEY = "fixture-only-" + "x" * 32


def adapter(**changes):
    return DevonBrowserAdapter(
        approvals=ApprovalQueue(), owner_id=OWNER, key=KEY, enabled=True, **changes
    )


def approve(a, action="open", owner=OWNER, **extra):
    clean = {"session_id": str(uuid4()), "allowed_hosts": list(a.allowed_hosts), **extra}
    tool = "browser.session." + action
    binding = approval_binding(
        task_id="fixture-task", step_id="fixture-step", tool_name=tool, arguments=clean
    )
    record, token = a.approvals.request(
        title="fixture only",
        what_happens="fixture action " + approval_marker(binding),
        requested_by=RUNTIME_REQUESTED_BY,
        owner_id=owner,
    )
    assert a.approvals.decide(record.request_id, token, "approve").ok
    return {
        **clean,
        APPROVAL_METADATA_KEY: {
            "request_id": record.request_id,
            "binding": binding,
            "task_id": "fixture-task",
            "step_id": "fixture-step",
            "tool_name": tool,
        },
    }, record


def transport(monkeypatch, mutate=None, fail=False):
    calls = []

    async def handler(request):
        calls.append(request)
        if fail:
            raise httpx.ReadTimeout("PRIVATE failure", request=request)
        body = json.loads(request.content)
        receipt = {
            k: body[k] for k in ("protocol", "owner_id", "request_id", "session_id", "action")
        }
        receipt.update(
            state="completed",
            receipt_id=str(uuid4()),
            isolation="dedicated-owner-context",
            network_policy="deny-all-v1",
        )
        if mutate:
            receipt = mutate(receipt)
        return httpx.Response(200, json=receipt)

    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(handler))
    return calls


def test_disabled_adapter_registers_nothing():
    a = DevonBrowserAdapter(approvals=ApprovalQueue(), owner_id=OWNER, key=KEY)
    registry = ToolRegistry()
    a.register(registry)
    assert registry.describe() == []


def test_all_browser_tools_are_effects_with_declared_arguments():
    registry = ToolRegistry()
    adapter().register(registry)
    assert len(registry.describe()) == 4
    assert all(
        t["approval_required"] and t["risk"] == "write" and t["parameters"]
        for t in registry.describe()
    )


async def test_bound_owner_approval_spent_once_before_transport(monkeypatch):
    a = adapter()
    args, record = approve(a)
    calls = transport(monkeypatch)
    assert (await a.execute("open", args)).ok
    assert a.approvals.get(record.request_id).state is ApprovalState.CONSUMED
    assert not (await a.execute("open", args)).ok
    assert len(calls) == 1
    body = json.loads(calls[0].content)
    assert body["owner_id"] == OWNER
    assert body["approval_binding"] == args[APPROVAL_METADATA_KEY]["binding"]
    assert calls[0].headers["Authorization"] == "Bearer " + KEY


@pytest.mark.parametrize("change", ["owner", "session", "hosts", "extra", "binding", "missing"])
async def test_substitution_refused_without_spending_or_transport(monkeypatch, change):
    a = adapter()
    args, record = approve(a, owner=str(uuid4()) if change == "owner" else OWNER)
    if change == "session":
        args["session_id"] = str(uuid4())
    elif change == "hosts":
        args["allowed_hosts"] = ["evil.example"]
    elif change == "extra":
        args["shell"] = "no"
    elif change == "binding":
        args[APPROVAL_METADATA_KEY]["binding"] = "a" * 64
    elif change == "missing":
        args.pop(APPROVAL_METADATA_KEY)
    calls = transport(monkeypatch)
    assert not (await a.execute("open", args)).ok
    assert calls == []
    assert a.approvals.get(record.request_id).state is ApprovalState.APPROVED


async def test_ambiguous_transport_never_retries_and_redacts(monkeypatch):
    a = adapter()
    args, record = approve(a)
    calls = transport(monkeypatch, fail=True)
    result = await a.execute("open", args)
    assert not result.ok and result.metadata["outcome"] == "unknown"
    assert "PRIVATE" not in result.error
    assert a.approvals.get(record.request_id).state is ApprovalState.CONSUMED
    assert len(calls) == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("owner_id", str(uuid4())),
        ("session_id", str(uuid4())),
        ("request_id", "REQ-OTHER"),
        ("network_policy", "unrestricted"),
        ("state", "made-up"),
        ("receipt_id", "../bad"),
    ],
)
async def test_forged_receipts_are_unknown(monkeypatch, field, value):
    a = adapter()
    args, _ = approve(a)
    transport(monkeypatch, lambda receipt: {**receipt, field: value})
    result = await a.execute("open", args)
    assert not result.ok and result.metadata["outcome"] == "unknown"


@pytest.mark.parametrize(
    "url",
    [
        "http://example.org/",
        "https://127.0.0.1/",
        "https://example.org.evil.test/",
        "https://user@example.org/",
        "https://example.org:444/",
        "https://example.org/\nprivate",
    ],
)
async def test_nonapproved_navigation_never_spends(monkeypatch, url):
    a = adapter(allowed_hosts=("example.org",), network_policy="public-proxy-v1")
    args, record = approve(a, action="navigate", url=url)
    calls = transport(monkeypatch)
    assert not (await a.execute("navigate", args)).ok
    assert calls == [] and a.approvals.get(record.request_id).state is ApprovalState.APPROVED


async def test_dispatch_does_not_share_nested_caller_arguments(monkeypatch):
    a = adapter(allowed_hosts=("example.org",), network_policy="public-proxy-v1")
    args, _ = approve(a)
    captured = []

    async def receive(request):
        captured.append(json.loads(request.content))
        body = captured[-1]
        receipt = {
            k: body[k] for k in ("protocol", "owner_id", "request_id", "session_id", "action")
        }
        receipt.update(
            state="completed",
            receipt_id=str(uuid4()),
            isolation="dedicated-owner-context",
            network_policy="public-proxy-v1",
        )
        return httpx.Response(200, json=receipt)

    original_client = httpx.AsyncClient

    class MutatingClient(original_client):
        async def __aenter__(self):
            args["allowed_hosts"].clear()
            return await super().__aenter__()

    monkeypatch.setattr(httpx, "AsyncClient", MutatingClient)
    monkeypatch.setattr(httpx, "AsyncHTTPTransport", lambda **kwargs: httpx.MockTransport(receive))
    await a.execute("open", args)
    assert len(captured) == 1
    assert captured[0]["allowed_hosts"] == ["example.org"]


def test_real_registry_keeps_private_browser_default_off(monkeypatch):
    from app.services.agent_tasks import build_tool_registry

    monkeypatch.delenv("DEVON_PRIVATE_BROWSER_ENABLED", raising=False)
    assert not any(
        t["name"].startswith("browser.session.") for t in build_tool_registry().describe()
    )


def test_real_registry_registers_only_under_explicit_owner_configuration(monkeypatch):
    from app.services.agent_tasks import build_tool_registry

    monkeypatch.setenv("DEVON_PRIVATE_BROWSER_ENABLED", "1")
    monkeypatch.setenv("DEVON_BROWSER_SESSION_OWNER_ID", OWNER)
    monkeypatch.setenv("DEVON_BROWSER_SESSION_KEY", KEY)
    monkeypatch.setenv("DEVON_BROWSER_ALLOWED_HOSTS", "example.org")
    monkeypatch.setenv("DEVON_BROWSER_NETWORK_POLICY", "public-proxy-v1")
    tools = [
        t for t in build_tool_registry().describe() if t["name"].startswith("browser.session.")
    ]
    assert len(tools) == 4 and all(t["approval_required"] for t in tools)


async def test_valid_multicommand_receipt_can_outlast_old_read_deadline(monkeypatch, tmp_path):
    """Real HTTPX UDS read: the former15s timeout loses a valid16s receipt."""
    import asyncio

    socket = str(tmp_path / "browser.sock")
    completed = asyncio.Event()
    calls = []

    async def handle(reader, writer):
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(
                int(line.split(b":", 1)[1])
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            body = json.loads(await reader.readexactly(length))
            calls.append(body)
            await asyncio.sleep(16.05)
            receipt = {
                key: body[key]
                for key in ("protocol", "owner_id", "request_id", "session_id", "action")
            }
            receipt.update(
                state="completed",
                receipt_id=str(uuid4()),
                isolation="dedicated-owner-context",
                network_policy="deny-all-v1",
            )
            raw = json.dumps(receipt).encode()
            completed.set()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(raw)).encode()
                + b"\r\nConnection: close\r\n\r\n"
                + raw
            )
            await writer.drain()
        except (ConnectionError, asyncio.IncompleteReadError):
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass

    server = await asyncio.start_unix_server(handle, path=socket)
    original = httpx.AsyncHTTPTransport
    monkeypatch.setattr(
        httpx, "AsyncHTTPTransport", lambda **kwargs: original(uds=socket, retries=0)
    )
    a = adapter()
    args, record = approve(a)
    try:
        result = await a.execute("open", args)
        await asyncio.wait_for(completed.wait(), timeout=3)
        assert result.ok, "adapter timed out while the valid worker action completed"
        assert a.approvals.get(record.request_id).state is ApprovalState.CONSUMED
        assert len(calls) == 1
    finally:
        server.close()
        await server.wait_closed()


async def test_total_deadline_bounds_trickle_response_without_retry(monkeypatch, tmp_path):
    import asyncio

    import app.services.devon_browser as module

    socket = str(tmp_path / "trickle.sock")
    calls = []
    finished = asyncio.Event()
    release = asyncio.Event()

    async def handle(reader, writer):
        try:
            headers = await reader.readuntil(b"\r\n\r\n")
            length = next(
                int(line.split(b":", 1)[1])
                for line in headers.split(b"\r\n")
                if line.lower().startswith(b"content-length:")
            )
            body = json.loads(await reader.readexactly(length))
            calls.append(body)
            receipt = {
                key: body[key]
                for key in ("protocol", "owner_id", "request_id", "session_id", "action")
            }
            receipt.update(
                state="completed",
                receipt_id=str(uuid4()),
                isolation="dedicated-owner-context",
                network_policy="deny-all-v1",
            )
            raw = json.dumps(receipt).encode()
            writer.write(
                b"HTTP/1.1 200 OK\r\nContent-Type: application/json\r\nContent-Length: "
                + str(len(raw)).encode()
                + b"\r\nConnection: close\r\n\r\n"
            )
            # The first 40 bytes go out at once and the rest wait until the
            # test releases them, so the response cannot finish inside the
            # total deadline however slow the runner is. The read timeout
            # stays at its 35 s default, so only the total deadline can end
            # the call, and the elapsed time assertion below is what proves
            # it did: a stall is also bounded by the read timeout, and without
            # that assertion the test passed with the total deadline deleted.
            # The earlier shape trickled 40 byte chunks on a 30 ms sleep
            # against a 70 ms deadline; each chunk reset the read timeout,
            # which was the point, but on a loaded runner the 70 ms were spent
            # before this handler had read the request, so `calls` read empty
            # (reproduced under CPU load on 2026-10-31).
            writer.write(raw[:40])
            await writer.drain()
            await release.wait()
            writer.write(raw[40:])
            await writer.drain()
        except ConnectionError:
            pass
        finally:
            writer.close()
            try:
                await writer.wait_closed()
            except ConnectionError:
                pass
            finished.set()

    server = await asyncio.start_unix_server(handle, path=socket)
    original = httpx.AsyncHTTPTransport
    monkeypatch.setattr(
        httpx, "AsyncHTTPTransport", lambda **kwargs: original(uds=socket, retries=0)
    )
    monkeypatch.setattr(module, "ADAPTER_TOTAL_TIMEOUT_SECONDS", 1.0)
    a = adapter()
    args, record = approve(a)
    try:
        started = time.monotonic()
        result = await a.execute("open", args)
        elapsed = time.monotonic() - started
        release.set()
        assert not result.ok and result.metadata["outcome"] == "unknown"
        # Well under the 35 s read timeout, so the total deadline ended the
        # call and not the read timeout.
        assert elapsed < 10, elapsed
        assert len(calls) == 1
        assert a.approvals.get(record.request_id).state is ApprovalState.CONSUMED
        await asyncio.wait_for(finished.wait(), timeout=1)
    finally:
        # On every path, or a handler blocked on the event outlives the
        # server and `wait_closed` hangs on Python 3.12 and later.
        release.set()
        server.close()
        await server.wait_closed()
