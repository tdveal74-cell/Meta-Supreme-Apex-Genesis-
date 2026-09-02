"""Which account the current work is spent against.

Providers are called from services that never see the request: the council
controller, the agent runtime, the workflow engine, the knowledge pipeline.
Rather than thread a user id through every one of them, the authenticated
user is bound to a request-scoped context variable by the auth dependency,
and the metered provider wrapper reads it at the moment of the call. Nothing
in between has to know.

A context variable set inside a request is visible to everything awaited in
that request and to every task it spawns (asyncio copies the context at task
creation), which covers the streaming council worker and the agent runtime.
It is not visible to the schedule dispatcher, a startup job, or a
service-layer call made outside a request; those read as no tenant and are
spent under `SYSTEM_TENANT`. A lane that does know its owner without a
request, the dispatcher starting a scheduled workflow, binds the owner itself.
"""

from __future__ import annotations

from contextvars import ContextVar, Token
from typing import Optional

#: The bucket for work no account asked for.
SYSTEM_TENANT = "system"

_current_tenant: ContextVar[Optional[str]] = ContextVar(
    "devon_current_tenant", default=None
)


def current_tenant_id() -> Optional[str]:
    """The account bound to the current context, or None outside a request."""
    return _current_tenant.get()


def bind_tenant(user_id: Optional[str]) -> Token:
    """Bind an account to the current context. Returns the token for `reset_tenant`."""
    return _current_tenant.set(str(user_id) if user_id else None)


def reset_tenant(token: Token) -> None:
    """Restore the binding that was in place before the matching `bind_tenant`."""
    _current_tenant.reset(token)


class TenantContextMiddleware:
    """Pure ASGI middleware: every HTTP request starts and ends with no tenant.

    A production server serves each request in its own task, so a binding
    dies with the task. The test client serves every request in the caller's
    task, where a binding made by one request would still be in place for the
    next; clearing on entry and restoring on exit makes both behave the same.
    Pure ASGI rather than BaseHTTPMiddleware so the endpoint runs in this
    task and the binding the auth dependency makes is the one the response,
    streaming included, is served under.
    """

    def __init__(self, app) -> None:
        self.app = app

    async def __call__(self, scope, receive, send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return
        token = _current_tenant.set(None)
        try:
            await self.app(scope, receive, send)
        finally:
            _current_tenant.reset(token)
