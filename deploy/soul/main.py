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

import asyncio
import hmac
import os
import pathlib
import re
import sys
import uuid
from datetime import datetime, timezone
from typing import Any

from fastapi import Cookie, FastAPI, Header, HTTPException, Query, Request, status
from fastapi.exception_handlers import http_exception_handler
from fastapi.responses import FileResponse, HTMLResponse, JSONResponse
from pydantic import BaseModel, Field
from starlette.exceptions import HTTPException as StarletteHTTPException

# The service is the whole of deploy/soul. Adding it to the path is what lets
# this import the vendored modules, which a test holds identical to the originals.
ROOT = pathlib.Path(__file__).resolve().parent
if str(ROOT) not in sys.path:
    sys.path.insert(0, str(ROOT))

from services.devon.assistant import Devon  # noqa: E402
from services.intelligence.providers.base import ProviderError  # noqa: E402
from services.intelligence.soul import (  # noqa: E402
    DEFAULT_TEE_HOST,
    DEVON_SOURCE,
    TEE_SOURCE,
    SoulLayer,
)

CONSOLE = ROOT / "console.html"

# Hard ceiling for conflict-search so a slow Pinecone call cannot hang the request.
CONFLICT_SEARCH_TIMEOUT_S = 12.0

app = FastAPI(
    title="DEVON Soul",
    description="Soul recall for the phone. Reads only.",
    docs_url=None,      # nothing to browse; the console is the surface
    redoc_url=None,
)


@app.exception_handler(StarletteHTTPException)
async def branded_http_exception(request: Request, exc: StarletteHTTPException):
    """Unknown paths get a flagship HTML page, not unstyled FastAPI JSON."""
    if exc.status_code == 404:
        return HTMLResponse(not_found_page(), status_code=404)
    return await http_exception_handler(request, exc)


@app.middleware("http")
async def never_cache(request, call_next):
    """
    Nothing this service returns may be stored by anything.

    Tee's home screen icon kept showing a refusal page from before a deploy,
    because iOS caches a standalone web app's start page hard and the
    responses went out as `public`. Stale is the mild half of the problem:
    `public` on the authenticated console meant an intermediary was entitled
    to store a page carrying the whole estate map and hand it to whoever
    asked next. Every response here is either gated or a refusal, and none of
    it is worth caching, so none of it is cacheable.
    """
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store, private, max-age=0"
    response.headers["Pragma"] = "no-cache"
    return response


def _console_token() -> str:
    return (os.environ.get("CONSOLE_TOKEN") or "").strip()


def _pinecone_key() -> str:
    return (os.environ.get("PINECONE_API_KEY") or "").strip()


#: Name of the cookie the door and the console both set.
TOKEN_COOKIE = "devon_console"


def _presented(
    authorization: str | None, cookie: str | None = None
) -> str:
    """
    The token the caller offered: a Bearer header or the SameSite cookie.

    A browser performing a top level navigation cannot set a header. The door
    therefore stores the token in sessionStorage and a SameSite cookie, then
    opens /console with no token in the URL. Query param t is never accepted
    as auth: it would land the credential in history, bookmarks, and referrer
    logs. The cookie is what makes signing in once mean once.

    Header first so an API caller is never overridden by a stale cookie.
    """
    if authorization and authorization.lower().startswith("bearer "):
        return authorization[7:].strip()
    return (cookie or "").strip()


def _require(
    authorization: str | None, cookie: str | None = None
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
    presented = _presented(authorization, cookie)
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
        timeout_seconds=10.0,  # keep individual Pinecone calls short
    )


def _new_ulid() -> str:
    """26-char Crockford-style id for receipt tracking."""
    alphabet = "0123456789ABCDEFGHJKMNPQRSTVWXYZ"
    raw = uuid.uuid4().hex + uuid.uuid4().hex
    return "".join(alphabet[int(raw[i], 16) % 32] for i in range(26))


def _now() -> str:
    return datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")


def _is_active(record: dict[str, Any]) -> bool:
    """Binding filter: status:active where the field exists; missing = active."""
    status_val = record.get("status")
    if status_val is None:
        meta = record.get("metadata") or {}
        status_val = meta.get("status")
    if status_val is None:
        return True
    return str(status_val).lower() == "active"


# ---------------------------------------------------------------------------
# Build 12 conflict policy
# ---------------------------------------------------------------------------
#
# Both souls embed with llama-text-embed-v2 on cosine, so a match score is a
# similarity in [0, 1]. Observed against live tee-soul-layer rulings: records
# that merely share territory with a claim land around 0.10-0.22. The old
# rule — any active match blocks — made those adjacent rulings a permanent
# veto on learning. The bands below say what a score is evidence OF:
#
#   score <= 0                     unknown: no usable score, a human decides
#   score <  CONFLICT_WEAK_BELOW   weak: shared territory, not a contradiction
#   score <  CONFLICT_STRONG_AT    adjacent: close enough that a human decides
#   score >= CONFLICT_STRONG_AT    strong: the claim sits inside ruled ground
#
# (A returned hit with no positive score is malformed upstream data, not a
# measured dissimilarity — it may not count toward "clear".)
#
# Nothing here auto-resolves a contradiction (the precedence doctrine: for
# contradictions, nothing wins — flag and let a human rule). The only outcome
# this policy reaches on its own is "clear", and only when every active match
# is weak and both souls were actually read in full. Everything stronger, and
# every partial or failed read, still stops at a human.
#
# Known residual: the claim text steers the embedding, so a caller could in
# principle pad or paraphrase a claim to dilute its similarity to a ruling.
# The endpoint is CONSOLE_TOKEN-gated and fed by the trusted Candidate
# Former, which the candidate itself never controls — the same trust that
# makes this issuer's receipts acceptable at all.
CONFLICT_WEAK_BELOW = 0.35
CONFLICT_STRONG_AT = 0.60
CONFLICT_POLICY_VERSION = "b12.1"

#: Prohibition language. Inside a strong match this upgrades the label from
#: "requires_human" to "conflict": a strongly similar ruling that forbids
#: something is the shape a live contradiction takes. It is a label for the
#: human reviewer, not a verdict — the claim may agree with the prohibition,
#: and either label stops the write.
_OPPOSITION_CUES = (
    "never",
    "must not",
    "may not",
    "do not",
    "don't",
    "not allowed",
    "forbidden",
    "forbid",
    "forbids",
    "prohibited",
    "prohibits",
    "banned",
    "refuse",
    "refuses",
    "refused",
    "reject",
    "rejects",
    "rejected",
    "overruled",
    "reversed",
    "no-write",
    "read-only",
)

_OPPOSITION_RE = re.compile(
    r"(?<![a-z0-9])("
    + "|".join(re.escape(cue) for cue in _OPPOSITION_CUES)
    + r")(?![a-z0-9])"
)


def _score_band(score: float) -> str:
    if score >= CONFLICT_STRONG_AT:
        return "strong"
    if score >= CONFLICT_WEAK_BELOW:
        return "adjacent"
    if score > 0.0:
        return "weak"
    return "unknown"


def _opposing_cue(text: str) -> str | None:
    """The first prohibition marker in a record's text, or None."""
    # Typographic apostrophes fold to ASCII first, or a ruling written
    # "don't" in a word processor would never match the cue.
    lowered = (text or "").lower().replace("’", "'")
    hit = _OPPOSITION_RE.search(lowered)
    return hit.group(1) if hit else None


def _saturated_window(
    retrieved: list[dict[str, Any]], limits: dict[str, int]
) -> str | None:
    """
    The source whose retrieval window may be hiding a non-weak hit, or None.

    The status:active filter runs after retrieval, so inactive records spend
    window slots. Every unretrieved hit scores at or below the lowest
    retrieved one — which means a window that came back full with its floor
    at or above the weak line could be concealing an active, non-weak match
    below the cutoff, and nothing may be cleared past that. A full window
    whose floor is weak conceals only weaker hits and clears safely.
    """
    for source, limit in limits.items():
        records = [r for r in retrieved if r.get("source") == source]
        if limit and len(records) >= limit:
            floor = min(float(r.get("score") or 0.0) for r in records)
            if floor >= CONFLICT_WEAK_BELOW:
                return source
    return None


def _conflict_decision(matched: list[dict[str, Any]]) -> tuple[str, str]:
    """
    Judge the active matches. Escalation only — "clear" is reached solely
    when every match is weak, and the caller still withholds it unless the
    recall was complete and whole.
    """
    if not matched:
        return "clear", "no active matches: nothing to conflict with"

    strong = [m for m in matched if m["band"] == "strong"]
    adjacent = [m for m in matched if m["band"] == "adjacent"]

    for m in strong:
        cue = _opposing_cue(str(m.get("text") or ""))
        if cue:
            return "conflict", (
                f"strong match {m.get('id')} (score {m['score']:.2f}) carries "
                f"prohibition language ({cue!r}): treated as a live conflict "
                "until a human rules"
            )
    if strong:
        top = max(strong, key=lambda m: m["score"])
        return "requires_human", (
            f"{len(strong)} strong match(es), top {top.get('id')} at "
            f"{top['score']:.2f} (>= {CONFLICT_STRONG_AT}): the claim sits "
            "inside ruled territory, a human decides"
        )
    if adjacent:
        top = max(adjacent, key=lambda m: m["score"])
        return "requires_human", (
            f"{len(adjacent)} adjacent match(es), top {top.get('id')} at "
            f"{top['score']:.2f} (>= {CONFLICT_WEAK_BELOW}): related enough "
            "that a human decides"
        )
    unknown = [m for m in matched if m["band"] == "unknown"]
    if unknown:
        return "requires_human", (
            f"{len(unknown)} match(es) carried no usable score: unbandable "
            "evidence cannot clear, a human decides"
        )
    top = max(matched, key=lambda m: m["score"])
    return "clear", (
        f"all {len(matched)} active match(es) weak, top score "
        f"{top['score']:.2f} (< {CONFLICT_WEAK_BELOW}): shared territory, "
        "not a contradiction"
    )


def door_page(reason: str = "") -> str:
    note = f'<p class="why">{reason}</p>' if reason else ""
    return DOOR_HTML.replace("{{NOTE}}", note)


def not_found_page() -> str:
    return NOT_FOUND_HTML


NOT_FOUND_HTML = """<!doctype html><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">
<meta name=\"referrer\" content=\"no-referrer\">
<title>DEVON</title>
<style>
 :root{color-scheme:dark;--navy:#0A1628;--amber:#D4A017;--surface:#F8F5F0}
 *{box-sizing:border-box}
 html,body{margin:0;overflow-x:hidden}
 body{min-height:100dvh;min-height:100vh;display:flex;align-items:flex-start;
      justify-content:flex-start;background:var(--navy);color:var(--surface);
      font:15px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif;
      padding:max(16px,env(safe-area-inset-top,0px)) 16px 24px}
 main{width:100%;max-width:26rem}
 h1{font-size:12px;letter-spacing:.24em;color:var(--amber);margin:0 0 8px;font-weight:700}
 p{margin:0 0 14px;color:#93A6B5;font-size:14px}
 a{color:var(--amber)}
 .note{margin-top:14px;font-size:12px;color:#8A9BAE}
</style>
<main>
 <h1>DEVON</h1>
 <p>No page at this path. This surface is the console door, not a public API browser.</p>
 <p><a href=\"/\">Return to the door</a></p>
 <p class=\"note\">Soul recall is reads only. Nothing here writes to either soul index. Propose is not live on this host; devon-soul.vercel.app has no Postgres. Remember goes through the platform API when that base URL is set. /terminal is a separate Operator sandbox and can write inside that isolated workspace.</p>
</main>"""


DOOR_HTML = """<!doctype html><meta charset=\"utf-8\">
<meta name=\"viewport\" content=\"width=device-width,initial-scale=1,viewport-fit=cover\">
<meta name=\"referrer\" content=\"no-referrer\">
<title>DEVON</title>
<style>
 :root{color-scheme:dark;--navy:#0A1628;--amber:#D4A017;--surface:#F8F5F0}
 *{box-sizing:border-box}
 html,body{margin:0;overflow-x:hidden}
 body{min-height:100dvh;min-height:100vh;display:flex;align-items:flex-start;
      justify-content:flex-start;background:var(--navy);color:var(--surface);
      font:15px/1.5 ui-sans-serif,system-ui,-apple-system,sans-serif;
      padding:max(16px,env(safe-area-inset-top,0px)) 16px 24px}
 main{width:100%;max-width:26rem}
 h1{font-size:12px;letter-spacing:.24em;color:var(--amber);margin:0 0 8px;font-weight:700}
 p{margin:0 0 14px;color:#93A6B5;font-size:14px}
 p.why{color:var(--amber);border-left:2px solid var(--amber);padding-left:10px;font-size:13px}
 label{display:block;font-size:11px;letter-spacing:.18em;color:#8A9BAE;margin:0 0 6px}
 input{width:100%;min-height:44px;padding:12px;background:#0C1A2E;color:var(--surface);
       border:1px solid #1E3348;border-radius:6px;font:14px ui-monospace,monospace}
 input:focus{outline:none;border-color:var(--amber)}
 button{width:100%;min-height:44px;margin-top:10px;padding:12px;border:1px solid var(--amber);
        border-radius:6px;background:transparent;color:var(--amber);
        font:700 12px/1 ui-sans-serif,system-ui,sans-serif;letter-spacing:.18em;
        cursor:pointer}
 button:active{background:#0C1A2E}
 .note{margin-top:14px;font-size:12px;color:#8A9BAE}
</style>
<main>
 <h1>DEVON</h1>
 {{NOTE}}
 <p>Paste your console token. It stays in this browser session (sessionStorage and a 12-hour SameSite cookie) and is not sent to another site.</p>
 <form id=\"f\" autocomplete=\"off\">
  <label for=\"t\">CONSOLE TOKEN</label>
  <input id=\"t\" type=\"password\" inputmode=\"text\" autocapitalize=\"off\"
         autocorrect=\"off\" spellcheck=\"false\" placeholder=\"CONSOLE_TOKEN from the host\">
  <button type=\"submit\">OPEN THE CONSOLE</button>
 </form>
 <p class=\"note\">Soul recall is reads only. Nothing here writes to either soul index. Propose is not live on this host; devon-soul.vercel.app has no Postgres. Remember goes through the platform API when that base URL is set. /terminal is a separate Operator sandbox and can write inside that isolated workspace.</p>
</main>
<script>
document.getElementById('f').addEventListener('submit', function (e) {
  e.preventDefault();
  var v = (document.getElementById('t').value || '').trim();
  if (!v) return;
  try { sessionStorage.setItem('devon.soul.token', v); } catch (err) {}
  try { localStorage.removeItem('devon.soul.token'); } catch (err) {}
  var secure = location.protocol === 'https:' ? '; Secure' : '';
  document.cookie = 'devon_console=' + encodeURIComponent(v) +
                    '; path=/; max-age=43200; SameSite=Strict' + secure;
  location.href = '/console';
});
</script>"""


@app.get("/", include_in_schema=False)
async def root(accept: str | None = Header(default=None)):
    wants = (accept or "").lower()
    if "application/json" in wants and "text/html" not in wants:
        return JSONResponse(
            {
                "name": "DEVON Soul",
                "console": "/console",
                "reads": [
                    "/api/v1/soul/status",
                    "/api/v1/soul/recall?q=",
                    "/api/v1/soul/conflict-search",
                ],
                "soul_writes": "none by design",
                "operator_terminal": "/terminal is a separate Operator sandbox when the wrapper is mounted; not a soul write",
            }
        )
    return HTMLResponse(door_page())


@app.get("/api/v1/health", include_in_schema=False)
async def health():
    return {
        "status": "healthy",
        "console_token_set": bool(_console_token()),
        "soul_key_set": bool(_pinecone_key()),
    }


@app.get("/api/v1/soul/status")
async def soul_status(
    authorization: str | None = Header(default=None),
    devon_console: str | None = Cookie(default=None),
):
    _require(authorization, devon_console)
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
    devon_console: str | None = Cookie(default=None),
    q: str | None = Query(default=None),
    top_k_tee: int = Query(default=4),
    top_k_devon: int = Query(default=3),
):
    _require(authorization, devon_console)
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


# ---------------------------------------------------------------------------
# Build 12 Trusted Conflict-Search Receipt Issuer
# ---------------------------------------------------------------------------

class ConflictSearchBody(BaseModel):
    claim: str = Field(..., min_length=8, max_length=2000)
    sources: list[str] = Field(
        default_factory=lambda: [
            "tee-soul-layer/rulings",
            "canon/rulings",
            "devon-soul",
        ]
    )
    top_k: int = Field(default=5, ge=1, le=20)
    context: dict[str, Any] | None = None


@app.post("/api/v1/soul/conflict-search")
async def conflict_search(
    body: ConflictSearchBody,
    authorization: str | None = Header(default=None),
    devon_console: str | None = Cookie(default=None),
):
    """
    Trusted higher-layer conflict search for the Build 12 learning gate.

    The candidate is forbidden from supplying its own receipt. This endpoint
    is the only place that may issue one. It is strictly read-only.

    Binding requirement: any layer that carries a status field must be
    filtered to status: active. A superseded lesson must never be retrieved
    as if it were still live.

    Hard timeout: if the search has not returned within CONFLICT_SEARCH_TIMEOUT_S
    the receipt is issued as incomplete + requires_human instead of hanging.

    Conflict policy (b12.1): matches are banded by score — weak matches are
    shared territory and do not block on their own; adjacent and strong
    matches defer to a human; a strong match carrying prohibition language
    is labeled a conflict outright. "clear" is only ever issued from a
    complete recall with both souls read — a timeout, failure, or partial
    read stays requires_human whatever was matched, and so does a retrieval
    window that came back full with no weak-scored floor, because such a
    window can hide an active non-weak match below the cutoff.
    """
    _require(authorization, devon_console)

    claim = body.claim.strip()
    if len(claim) < 8:
        # The schema's min_length runs on the raw string, so eight spaces
        # slip past it, strip to nothing, and an empty recall would come
        # back complete with no matches — a trusted "clear" receipt minted
        # without a single record read. Refuse instead.
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail="claim must be at least 8 characters once whitespace is trimmed.",
        )
    sources = body.sources or [
        "tee-soul-layer/rulings",
        "canon/rulings",
        "devon-soul",
    ]
    top_k = body.top_k

    matched: list[dict[str, Any]] = []
    notes_parts: list[str] = []
    recall_errors: list[str] = []
    saturated: str | None = None
    complete = True

    try:
        layer = _layer()
        top_k_tee = max(1, min(top_k, 5))
        top_k_devon = max(0, min(top_k, 3))

        recall = await asyncio.wait_for(
            layer.recall(claim, top_k_tee=top_k_tee, top_k_devon=top_k_devon),
            timeout=CONFLICT_SEARCH_TIMEOUT_S,
        )

        retrieved = recall.to_dicts()
        saturated = _saturated_window(
            retrieved, {TEE_SOURCE: top_k_tee, DEVON_SOURCE: top_k_devon}
        )

        for rec in retrieved:
            if not _is_active(rec):
                continue
            score = float(rec.get("score") or 0.0)
            matched.append({
                "id": rec.get("id"),
                "text": rec.get("text"),
                "score": score,
                "band": _score_band(score),
                "source": rec.get("source"),
                "kind": rec.get("kind"),
                "heading": rec.get("heading"),
                "area": rec.get("area"),
                "dated": rec.get("dated"),
            })

        notes_parts.append(
            f"tee={recall.tee_count} devon={recall.devon_count} "
            f"active_matched={len(matched)}"
        )
        if recall.errors:
            recall_errors = list(recall.errors)
            notes_parts.append("partial: " + "; ".join(recall.errors))
            if recall.tee_count == 0 and recall.devon_count == 0:
                complete = False

    except asyncio.TimeoutError:
        complete = False
        notes_parts.append(
            f"search timed out after {CONFLICT_SEARCH_TIMEOUT_S:.0f}s"
        )
    except HTTPException:
        raise
    except ProviderError as exc:
        complete = False
        notes_parts.append(f"search failed: {exc}")
    except Exception as exc:
        complete = False
        notes_parts.append(f"unexpected: {type(exc).__name__}: {str(exc)[:200]}")

    notes_parts.append("status:active filter applied where the field exists")

    conflict_status, decision = _conflict_decision(matched)
    if conflict_status == "clear":
        # Escalation may stand on partial evidence; clearance may not. A
        # claim is only clear when both souls were read, in full, and still
        # nothing stronger than weak adjacency came back.
        if not complete:
            conflict_status = "requires_human"
            decision = "the search did not complete, so nothing can be cleared"
        elif recall_errors:
            conflict_status = "requires_human"
            decision = (
                "a soul went unread (partial recall): weak evidence from a "
                "partial read cannot clear the claim"
            )
        elif saturated:
            conflict_status = "requires_human"
            decision = (
                f"the {saturated} retrieval window came back full with no "
                f"score below {CONFLICT_WEAK_BELOW}: an active non-weak match "
                "may sit below the cutoff, so a human decides"
            )
    notes_parts.append(f"policy {CONFLICT_POLICY_VERSION}: {decision}")

    return {
        "receipt_id": _new_ulid(),
        "complete": complete,
        "sources": sources,
        "conflict_status": conflict_status,
        "matched_records": matched,
        "notes": ". ".join(notes_parts) + ".",
        "policy": {
            "version": CONFLICT_POLICY_VERSION,
            "weak_below": CONFLICT_WEAK_BELOW,
            "strong_at": CONFLICT_STRONG_AT,
            "decision": decision,
        },
        "issued_at": _now(),
        "issued_by": "conflict-search-issuer",
    }


@app.get("/console", include_in_schema=False)
async def console(
    authorization: str | None = Header(default=None),
    devon_console: str | None = Cookie(default=None),
):
    if not CONSOLE.exists():
        raise HTTPException(status_code=404, detail="No console asset deployed.")
    try:
        _require(authorization, devon_console)
    except HTTPException as exc:
        if exc.status_code == status.HTTP_503_SERVICE_UNAVAILABLE:
            why = (
                "This service has no CONSOLE_TOKEN set on the host, so it is "
                "refusing everything. Set one there and redeploy. A token "
                "pasted here cannot help until that is done."
            )
        elif _presented(authorization, devon_console):
            why = (
                "That token was refused. Check it for a stray space, a "
                "changed character, or a capital the keyboard added."
            )
        else:
            why = "No token yet."
        return HTMLResponse(door_page(why), status_code=exc.status_code)
    return FileResponse(CONSOLE, media_type="text/html")
