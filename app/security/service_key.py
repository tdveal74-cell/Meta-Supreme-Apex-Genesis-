"""Machine authentication for DEVON's read only service doors.

No account is behind these calls. A workflow presents a shared key on
`x-devon-key`, the header every n8n door in this estate already uses, and gets
a pure answer back. An account token cannot do this job: it expires in 24
hours, so a workflow holding one is broken by the next morning.

What this module does NOT do is make a route safe. A route reached through
this dependency is read only because of what it calls, not because of a flag
set here. The hearing door calls `parse`, which is a pure function in an effect
free package, and never `Devon.ask`, which gates and raises approval cards. If
a future route wants this dependency, check what it calls first.

The refusal when the key is unset is the load bearing line in the file. The
settings default is `""`, and `"" == ""` is a match, so a service that simply
forgot to set `DEVON_SERVICE_KEY` would authenticate every caller rather than
none: the door would read as configured while standing open. So this refuses
first and compares second, and an unset key is a 503 naming the missing
setting rather than a 200 to a stranger.
"""

import secrets
from typing import Annotated, Optional

from fastapi import Depends, Header, HTTPException, status

from app.core.config import settings

#: The header every DEVON door already takes, so a caller that can reach the
#: n8n webhooks can reach this with the same shim.
SERVICE_KEY_HEADER = "x-devon-key"

#: What a route is handed once the key checks out. Deliberately a constant and
#: deliberately not the key itself, so the secret cannot reach a log line, a
#: response body or a stored row by way of a route that meant well.
SERVICE_PRINCIPAL = "machine"


def require_service_key(
    x_devon_key: Annotated[Optional[str], Header(alias=SERVICE_KEY_HEADER)] = None,
) -> str:
    """Refuse unless the caller presents the estate's service key.

    Returns `SERVICE_PRINCIPAL`, never the presented key.
    """
    configured = (settings.DEVON_SERVICE_KEY or "").strip()
    if not configured:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "This door needs DEVON_SERVICE_KEY set on the service. It is "
                "unset, so the door is closed rather than open to everyone."
            ),
        )

    presented = (x_devon_key or "").strip()
    if not presented or not secrets.compare_digest(presented, configured):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or missing service key.",
            headers={"WWW-Authenticate": SERVICE_KEY_HEADER},
        )

    return SERVICE_PRINCIPAL


#: Type alias matching the house style of `CurrentUser` in `app.security.deps`.
ServiceCaller = Annotated[str, Depends(require_service_key)]
