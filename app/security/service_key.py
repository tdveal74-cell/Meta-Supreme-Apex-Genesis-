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

A key that is set but too short is refused the same way, and for the same
reason: both are a misconfigured service, not a bad caller. Without that floor
a one character key is accepted and the deployment reads as configured, which
is the unset bug wearing a different hat.
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

#: The shortest key this door will accept. 24 characters is roughly 128 bits
#: once the value carries real randomness, and it exists because without it a
#: one character key is accepted and reads as configured. The recommended way
#: to produce one is `secrets.token_urlsafe(32)`, which is 43 characters.
#:
#: A short key is refused the same way an unset one is, with a 503 naming the
#: setting, because both are a misconfigured service rather than a bad caller.
#: Telling a stranger apart from a bad deployment is the operator's job and
#: the log line is where that belongs, not the response body.
MINIMUM_KEY_LENGTH = 24


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
    if len(configured) < MINIMUM_KEY_LENGTH:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                f"DEVON_SERVICE_KEY is shorter than {MINIMUM_KEY_LENGTH} "
                "characters. The door stays closed rather than guarded by "
                "something guessable. Generate one with "
                "secrets.token_urlsafe(32)."
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
