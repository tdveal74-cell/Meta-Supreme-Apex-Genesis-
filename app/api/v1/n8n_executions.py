"""Read only n8n execution telemetry. One route, one verb.

WHY THE SURFACE IS THIS SMALL

n8n's own API can trigger a workflow, retry an execution, delete one and resume
a waiting one. This router exposes none of it, and not by convention: there is
exactly one route on it and it is declared with `@router.get`, so FastAPI's
route table carries GET (with the HEAD it derives) and nothing else. A POST or
DELETE cannot be reached here because none is registered.

`test_n8n_telemetry.py` walks this router's live route table and fails if any
method other than GET or HEAD appears on it, and walks this file's syntax tree
and fails if a `router.post`, `router.put`, `router.patch` or `router.delete`
decorator is added. That is a guard on the structure rather than on the prose
above it, which is the only kind worth having: the placeholder this arc
replaced was honest for months precisely because nothing pretended.

WHY IT IS AUTHENTICATED

The payload names the estate's workflows and the host serving them. That is
Tee's private estate, so the route sits behind the same session the rest of the
control plane uses. It never returns the API key, and the key is not in the
payload shape at all: `app/services/n8n_telemetry.py` builds the response from
execution rows and configured variable NAMES, never their values.
"""

from typing import Any, Dict

from fastapi import APIRouter, Query

from app.security.deps import CurrentUser
from app.services import n8n_telemetry

router = APIRouter(prefix="/n8n", tags=["n8n Executions"])


@router.get("/executions", summary="Read only execution telemetry for the configured instances")
async def n8n_executions(
    # The gate, and only the gate. The payload is not scoped per account: the
    # instances are the estate's, not the caller's, so nothing below reads this
    # user. It is here so an unauthenticated caller cannot read the estate's
    # workflow names and hosts.
    current_user: CurrentUser,
    limit: int = Query(
        default=n8n_telemetry.DEFAULT_LIMIT,
        ge=1,
        le=n8n_telemetry.MAX_LIMIT,
        description=(
            "How many saved executions to walk per instance, newest first. The window is "
            "reported with the answer, because the rate and the burn derived from it are only "
            "as good as the window they came from."
        ),
    ),
) -> Dict[str, Any]:
    """Execution telemetry for the configured instance or instances.

    Each instance is reported on its own, labelled by the host actually
    reached, and never merged with the other. There is no fallback from one to
    the other: a cutover question is always about a named instance, and an
    answer that quietly came from the wrong one is the failure this route is
    shaped to make visible.

    An unconfigured instance says so. An unreachable one is its own state,
    separate from one that answered with nothing saved. A cap is reported only
    when configuration states it, and is labelled as stated rather than
    measured every time it appears.
    """
    return await n8n_telemetry.read_all(limit=limit)
