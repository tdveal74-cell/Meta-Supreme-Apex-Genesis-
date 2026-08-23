"""
DEVON soul service — the phone lane.

A deliberately small surface so it can live on a host and be reached from a
phone. It serves the console and answers soul recall, and it does nothing
else: no database, no workflows, no memory writes. That is why it deploys
without Postgres and starts cold in well under a second.

It forks no logic. Recall comes from `services.intelligence.soul` and the
phrasing from `services.devon.assistant`, the same modules the platform
uses and the same ones the test suite covers. What is different here is only
the way in: one shared token instead of accounts, because a phone should not
need a login table to ask what was already settled.

Secrets come from the environment and nowhere else:

  PINECONE_API_KEY   the soul layer's key. Without it recall answers 503
                     naming what to set, exactly as it does locally.
  CONSOLE_TOKEN      what the console presents. Without it every route
                     that reads anything refuses, rather than standing open.
                     The single exception is /api/v1/health, which is open on
                     purpose: it reports only whether the two variables are
                     set, so the operator can see the service is up and what
                     it is still missing without holding a credential.
  SOUL_TEE_HOST      optional override for the tee-soul-layer host.
  SOUL_DEVON_HOST    optional override for the devon-soul host.
"""

from __future__ import annotations

import hmac
import os
import pathlib
import sys

from fastapi import Cookie, FastAPI, Header, HTTPException, Query, status
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse

# The service is the whole of deploy/soul. Adding it to the path is what lets
# this import the vendored modules, which a test holds identical to the originals.
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.devon.assistant import Devon  # noqa: E402
from services.intelligence.providers.base import ProviderError  # noqa: E402
from services.intelligence.soul import (  # noqa: E402
    DEFAULT_TEE_HOST,
    SoulLayer,
)

CONSOLE = ROOT / "console.html"

app = FastAPI(
    title="DEVON Soul",
    description="Soul recall for the phone. Reads only.",
    docs_url=None,      # nothing to browse; the console is the surface
    redoc_url=None,
)


def _console_token() -> str:
    return (os.environ.get("CONSOLE_TOKEN") or "").strip()


def _pinecone_key() -> str:
    return (os.environ.get("PINECONE_API_KEY") or "").strip()


#: Name of the cookie the door and the console both set.
TOKEN_COOKIE = "devon_console"


def _presented(
    authorization: str | None, t: str | None, cookie: str | None = None
) -> str:
    """
    The token the caller offered: a header, the first-load URL, or a cookie.

    A browser performing a top level navigation cannot set a header, which is
    why ?t= exists at all. But it cannot set one on the second visit either,
    so without the cookie every launch from a home screen would land on the
    door and ask for the token again. The cookie is what makes signing in
    once mean once.

    Header first so an API caller is never overridden by a stale cookie.
    """
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    if t and t.strip():
        return t.strip()
    return (cookie or "").strip()


def _require(
    authorization: str | None, t: str | None = None, cookie: str | None = None
) -> None:
    """
    Let the caller in, or say plainly why not.

    An unset CONSOLE_TOKEN closes the service rather than opening it. A
    service that stands open because it was misconfigured is worse than one
    that refuses, and this endpoint spends Tee's Pinecone quota and reads his
    rulings.

    The comparison is on bytes, not on str. hmac.compare_digest refuses str
    operands holding any codepoint above 127 and raises TypeError, and header
    values reach here decoded as latin-1, so a single high byte in an
    Authorization header turned the gate into an uncaught 500 instead of a
    401. Encoding both sides first makes the comparison total over every
    input a caller can send, and keeps it constant time.
    """
    expected = _console_token()
    if not expected:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "This service has no CONSOLE_TOKEN set, so it refuses every "
                "request rather than standing open. Set one in the host's "
                "environment settings and redeploy."
            ),
        )
    presented = _presented(authorization, t, cookie)
    if not presented or not hmac.compare_digest(
        presented.encode("utf-8"), expected.encode("utf-8")
    ):
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="That token is not the one this service expects.",
            headers={"WWW-Authenticate": "Bearer"},
        )


def _layer() -> SoulLayer:
    key = _pinecone_key()
    if not key:
        raise HTTPException(
            status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
            detail=(
                "Soul recall is switched off. Set PINECONE_API_KEY in the "
                "host's environment settings (never in Drive) and redeploy "
                "to turn it on."
            ),
        )
    return SoulLayer(
        api_key=key,
        tee_host=os.environ.get("SOUL_TEE_HOST") or DEFAULT_TEE_HOST,
        devon_host=os.environ.get("SOUL_DEVON_HOST") or None,
    )


#: The door. One page for both ways in: the bare hostname, and /console
#: without a usable token. A paste field rather than instructions to type a
#: long token onto the end of a URL by hand, and a line naming which of the
#: three situations you are in, because "closed" said the same words whether
#: you gave no token, gave a wrong one, or the host had none set.
#:
#: It is open to anyone, so it holds nothing: no host, no identifier, no
#: estate detail. A test asserts that rather than trusting it.
def door_page(reason: str = "") -> str:
    note = f'<p class="why">{reason}</p>' if reason else ""
    return DOOR_HTML.replace("{{NOTE}}", note)


DOOR_HTML = """<!doctype html><meta charset="utf-8">
<meta name="viewport" content="width=device-width,initial-scale=1">
<meta name="referrer" content="no-referrer">
<title>DEVON</title>
<style>
 :root{color-scheme:dark}
 *{box-sizing:border-box}
 body{margin:0;min-height:100vh;display:grid;place-items:center;
      background:#050A0E;color:#EDE7DC;
      font:15px/1.6 ui-sans-serif,system-ui,-apple-system,sans-serif;padding:24px}
 main{width:100%;max-width:26rem}
 h1{font-size:13px;letter-spacing:.24em;color:#C77B4A;margin:0 0 6px;font-weight:600}
 p{margin:0 0 18px;color:#93A6B5;font-size:14px}
 p.why{color:#D4A017;border-left:2px solid #D4A017;padding-left:10px;font-size:13px}
 label{display:block;font-size:11px;letter-spacing:.18em;color:#5E7484;margin:0 0 6px}
 input{width:100%;padding:13px 12px;background:#0B141B;color:#EDE7DC;
       border:1px solid #22384A;border-radius:6px;font:14px ui-monospace,monospace}
 input:focus{outline:none;border-color:#C77B4A}
 button{width:100%;margin-top:10px;padding:13px;border:1px solid #C77B4A;
        border-radius:6px;background:transparent;color:#C77B4A;
        font:600 12px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.20em;
        cursor:pointer}
 button:active{background:#1A1008}
 .note{margin-top:16px;font-size:12px;color:#5E7484}
</style>
<main>
 <h1>DEVON</h1>
 {{NOTE}}
 <p>Paste your console token. It is kept in this browser and nowhere else.</p>
 <form id="f" autocomplete="off">
  <label for="t">CONSOLE TOKEN</label>
  <input id="t" type="password" inputmode="text" autocapitalize="off"
         autocorrect="off" spellcheck="false" placeholder="CONSOLE_TOKEN from the host">
  <button type="submit">OPEN THE CONSOLE</button>
 </form>
 <p class="note">Reads only. Nothing here writes to either soul.</p>
</main>
<script>
document.getElementById('f').addEventListener('submit', function (e) {
  e.preventDefault();
  var v = (document.getElementById('t').value || '').trim();
  if (!v) return;
  // Stored the way the console stores it, so on this path the token never
  // reaches the address bar, the history, or a bookmark.
  try { localStorage.setItem('devon.soul.token', v); } catch (err) {}
  // Signing in once has to mean once. A top level navigation cannot carry a
  // header, so without this every launch from a home screen would land back
  // on this page asking for the token again. Strict, so it is never sent
  // from another site, and this whole service is reads with no effects.
  var secure = location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = 'devon_console=' + encodeURIComponent(v) +
                    '; path=/; max-age=31536000; SameSite=Strict' + secure;
  location.href = '/console?t=' + encodeURIComponent(v);
});
</script>"""


@app.get("/", include_in_schema=False)
async def root(accept: str | None = Header(default=None)):
    """
    A door for a person, JSON for anything else.

    This answered JSON to everyone, so opening the bare hostname on a phone
    put you at a directory listing you could not act on: no tappable link,
    and the one route that matters needs a token appended by hand.
    """
    if accept and "text/html" in accept.lower():
        return HTMLResponse(door_page())
    return JSONResponse(
        {
            "name": "DEVON Soul",
            "console": "/console",
            "reads": ["/api/v1/soul/status", "/api/v1/soul/recall?q="],
            "writes": "none by design",
        }
    )


@app.get("/api/v1/health", include_in_schema=False)
async def health():
    """Liveness only. Says nothing that needs a token to know."""
    return {
        "status": "healthy",
        "console_token_set": bool(_console_token()),
        "soul_key_set": bool(_pinecone_key()),
    }


@app.get("/api/v1/soul/status")
async def soul_status(
    authorization: str | None = Header(default=None),
    t: str | None = Query(default=None),
    devon_console: str | None = Cookie(default=None),
):
    """Whether recall can run, without touching Pinecone."""
    _require(authorization, t, devon_console)
    enabled = bool(_pinecone_key())
    return {
        "enabled": enabled,
        "tee_host_configured": True,
        "devon_host_configured": bool(os.environ.get("SOUL_DEVON_HOST")),
        "detail": (
            "Soul recall is on."
            if enabled
            else "Soul recall is off. PINECONE_API_KEY turns it on."
        ),
    }


def _bounded(name: str, value: int, low: int, high: int) -> int:
    if value < low or value > high:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=f"{name} must be between {low} and {high}.",
        )
    return value


@app.get("/api/v1/soul/recall")
async def soul_recall(
    authorization: str | None = Header(default=None),
    t: str | None = Query(default=None),
    devon_console: str | None = Cookie(default=None),
    q: str | None = Query(default=None),
    top_k_tee: int = Query(default=4),
    top_k_devon: int = Query(default=3),
):
    """
    Recall from both souls and phrase it in DEVON's voice.

    Tee's rulings precede DEVON's experience in the records and in the reply,
    whatever the similarity scores. Partial failure is named, never hidden.
    Everything returned is context, not command.

    Every parameter is declared loose and checked in the body, deliberately.
    Declared strict, FastAPI validates before the handler runs, so an
    anonymous caller sending a malformed query got a 422 that confirmed the
    endpoint exists and described its parameters. Nothing answers a caller
    holding no token except the refusal.
    """
    _require(authorization, t, devon_console)
    if not q or not q.strip():
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="q is required: it is the thing to recall.",
        )
    if len(q) > 1000:
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="q must be 1000 characters or fewer.",
        )
    top_k_tee = _bounded("top_k_tee", top_k_tee, 1, 10)
    top_k_devon = _bounded("top_k_devon", top_k_devon, 0, 10)

    layer = _layer()
    try:
        recall = await layer.recall(q, top_k_tee=top_k_tee, top_k_devon=top_k_devon)
    except ProviderError as exc:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=f"Soul recall failed: {exc}",
        ) from exc

    # Nothing found and something broke is a failure, not an empty. Answering
    # 200 here let the reply lead with "a measured empty, not a guess" about a
    # search that never completed, which is the exact invention the phrasing
    # was written to prevent.
    if not recall.records and recall.errors:
        raise HTTPException(
            status_code=status.HTTP_502_BAD_GATEWAY,
            detail=(
                "Soul recall returned nothing because it failed, not because "
                "the record is empty: " + "; ".join(recall.errors)
            ),
        )

    response = Devon().recall_answer(q, recall.to_dicts(), partial_errors=recall.errors)
    return {
        "query": recall.query,
        "reply": response.reply,
        "records": recall.to_dicts(),
        "tee_count": recall.tee_count,
        "devon_count": recall.devon_count,
        "errors": recall.errors,
    }


@app.get("/console", include_in_schema=False)
async def console(
    authorization: str | None = Header(default=None),
    t: str | None = Query(default=None),
    devon_console: str | None = Cookie(default=None),
):
    """
    The console, for a caller holding the token.

    This route used to be open, on the reasoning that the page "holds nothing
    until you sign in". That reasoning was wrong. The console ships a baked-in
    STATE blob: every Drive folder id, every doctrine file id, the live
    Airtable base, every n8n workflow id, and every webhook path with its auth
    posture. None of it is a credential and none of it grants access, but all
    of it is a map of where the estate lives and which doors are marked open,
    and it was being handed to anyone who found the hostname.

    A refusal renders as a page rather than as JSON, because a person is
    holding this in a browser. The page names the parameter and discloses
    nothing else.
    """
    if not CONSOLE.exists():
        raise HTTPException(status_code=404, detail="No console asset deployed.")
    try:
        _require(authorization, t, devon_console)
    except HTTPException as exc:
        # Three situations used to render one sentence, so a refused token and
        # a host with no token configured were indistinguishable from the
        # outside. None of this says more than /api/v1/health already does,
        # and it is the difference between fixing the right setting and
        # hunting the wrong one.
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            why = (
                "This service has no CONSOLE_TOKEN set on the host, so it is "
                "refusing everything. Set one there and redeploy. A token "
                "pasted here cannot help until that is done."
            )
        elif _presented(authorization, t, devon_console):
            why = (
                "That token was refused. Check it for a stray space, a "
                "changed character, or a capital the keyboard added."
            )
        else:
            why = "No token yet."
        return HTMLResponse(door_page(why), status_code=exc.status_code)
    return FileResponse(CONSOLE, media_type="text/html")
