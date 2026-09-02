"""In-estate knowledge loop executor.

DEVON's compiler in ``services.devon`` stays effect-free: a capture is a
FilingPlan with ``executed: False``. This module is the caller that performs
the effect, outside that package.

The loop is: propose (enqueue plus Live State Ledger intent rows in
PostgreSQL; no consume, no soul write) -> human approve (existing queue,
hashed single-use token PLUS the out-of-band DEVON_RULING_KEY, so the
JWT that proposed can never approve by itself) -> consume-before-execute
commit. Commit always
persists a Live State Ledger artifact *with body* and a receipt so "if it
is not in the ledger it did not happen" is true even when Notion, Drive,
n8n, and Pinecone are unset. PostgreSQL is the store; ``estate://`` is a
path label. Kind ``ruling`` may enter the ledger so Tee's rulings outrank
DEVON notes on find; Layer 1 Tee Soul is still never written. Soul write
is additive and fail-closed: only devon-soul / subconscious per
``check_layer_write``, never Tee Soul, and skipped unless SOUL_RECALL_ENABLED
and PINECONE_API_KEY. n8n is routed only when a webhook env is actually set.
Missing connectors are named, never faked.
"""

from __future__ import annotations

import hashlib
import hmac
import os
from datetime import datetime, timezone
from typing import Any, Dict, Optional

from sqlalchemy import text
from sqlalchemy.ext.asyncio import AsyncSession

from app.services import soul as soul_service
from app.services.live_state_ledger import ledger
from services import memory as memory_store
from services.devon import ecosystem
from services.devon.approval import ApprovalQueue, ApprovalState
from services.devon.assistant import Devon, FilingPlan
from services.intelligence.soul import (
    ALLOWED_KINDS,
    SoulWriteCandidate,
    SoulWriteRefused,
)

#: Ledger kinds include Tee rulings and operator files (task, project,
#: thread, brief, plate, episode). Pinecone devon-soul still refuses
#: ``ruling`` and these operational kinds (ALLOWED_KINDS). A ruling here
#: is a ledger row, not Layer 1. Notion/Drive/n8n stay missing.
LEDGER_KINDS = frozenset(
    set(ALLOWED_KINDS) | {"ruling"} | set(memory_store.OPERATIONAL_KINDS)
)

LOOP = "knowledge_loop.v1"
#: requested_by on every card this loop raises. The shared decide route
#: refuses cards carrying it: they are ruled through the ruling-key lane.
REQUESTED_BY = "knowledge-loop"
DEFAULT_LAYER = 5  # Devon Soul
SUBCONSCIOUS_LAYER = 4


class KnowledgeLoopRefused(RuntimeError):
    """A knowledge-loop write the gate refuses. Carries an HTTP status."""

    def __init__(self, message: str, *, status_code: int = 403) -> None:
        self.status_code = status_code
        super().__init__(message)


class _ApprovedDecision:
    """Duck-typed for SoulLayer.commit after the approval has been consumed."""

    approved = True


def _now_date() -> str:
    return datetime.now(timezone.utc).date().isoformat()


def _sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _queue() -> ApprovalQueue:
    from app.api.v1.devon import _queue as shared

    return shared


def _require_ruling_key(presented: Optional[str]) -> None:
    """The approver's second credential, out of band from the platform JWT.

    The propose response hands the single-use token back to the proposer so
    the HUD can render the pending card, which means the token alone must
    never approve: a script holding one CurrentUser JWT would otherwise run
    propose, approve, and commit with no human anywhere, exactly the lane
    the deleted soul.py write endpoint was removed for. DEVON_RULING_KEY is
    held by the approver and typed into the HUD, never returned by any
    endpoint. Unset, the loop is propose-only and says so.
    """
    expected = (os.environ.get("DEVON_RULING_KEY") or "").strip()
    if not expected:
        raise KnowledgeLoopRefused(
            "The approve lane is not configured: DEVON_RULING_KEY is unset on "
            "this host, so the loop is propose-only. Set the key and hand it "
            "to the approver out of band; the platform JWT alone must never "
            "approve.",
            status_code=403,
        )
    if not presented or not hmac.compare_digest(expected, presented.strip()):
        raise KnowledgeLoopRefused(
            "The ruling key does not match. The platform JWT alone does not "
            "approve; the approver types DEVON_RULING_KEY into the HUD.",
            status_code=403,
        )


def _n8n_env() -> tuple[str, str]:
    url = (os.environ.get("N8N_WEBHOOK_URL") or "").strip()
    key = (
        os.environ.get("N8N_WEBHOOK_KEY")
        or os.environ.get("DEVON_CAPTURE_KEY")
        or ""
    ).strip()
    return url, key


def _connector_honesty(*, postgres_proven: bool = False) -> Dict[str, Any]:
    url, key = _n8n_env()
    notion = (os.environ.get("NOTION_TOKEN") or os.environ.get("NOTION_API_KEY") or "").strip()
    drive = (os.environ.get("GOOGLE_DRIVE_TOKEN") or os.environ.get("DRIVE_TOKEN") or "").strip()
    pinecone = bool(soul_service.get_soul_layer())
    db_url = (os.environ.get("DATABASE_URL") or "").strip()
    return {
        "postgres": {
            "engine": "PostgreSQL",
            "configured": bool(db_url),
            "store": "Live State Ledger (intents, events, artifacts.body)",
            "written": postgres_proven,
            "live": postgres_proven,
            "reason": (
                "This request used the PostgreSQL engine. live is not inferred "
                "from DATABASE_URL alone. estate:// is a path label; the capture "
                "body is on artifacts.body."
                if postgres_proven
                else (
                    "DATABASE_URL is set; that is env presence, not a proven live engine."
                    if db_url
                    else "DATABASE_URL unset. The loop cannot persist."
                )
            ),
        },
        "n8n": {
            "configured": bool(url),
            "live": False,
            "reason": (
                "N8N_WEBHOOK_URL is set; routing is attempted, not claimed live."
                if url
                else "N8N_WEBHOOK_URL unset. In-estate loop is the ledger."
            ),
            "key_set": bool(key),
        },
        "notion": {
            "configured": bool(notion),
            "written": False,
            "live": False,
            "reason": (
                "NOTION_TOKEN is set but this executor does not fake a Notion write."
                if notion
                else "Notion credentials absent. In-estate loop is the ledger."
            ),
        },
        "drive": {
            "configured": bool(drive),
            "written": False,
            "live": False,
            "reason": (
                "Drive token is set but this executor does not fake a Drive write."
                if drive
                else "Drive credentials absent. In-estate loop is the ledger."
            ),
        },
        "pinecone": {
            "configured": pinecone,
            "live": pinecone,
            "reason": (
                "Soul layer is on. Recall and devon-soul write use the injected or live client."
                if pinecone
                else "SOUL_RECALL_ENABLED and PINECONE_API_KEY are unset. Soul write skipped."
            ),
        },
    }


def _build_candidate(
    text: str, *, kind: str, area: Optional[str], source_note: str
) -> SoulWriteCandidate:
    cleaned = (text or "").strip()
    if not cleaned:
        raise SoulWriteRefused(
            "Nothing to remember: the candidate text is empty.",
            provider="knowledge-loop",
        )
    normalized = (kind or "").strip().lower()
    if normalized not in LEDGER_KINDS:
        raise SoulWriteRefused(
            f"Kind {kind!r} may not enter the in-estate ledger. Allowed: "
            f"{', '.join(sorted(LEDGER_KINDS))}. Kind ruling is a ledger "
            "row ranked above notes; it does not write Layer 1 Tee Soul.",
            provider="knowledge-loop",
        )
    return SoulWriteCandidate(
        candidate_id=f"devon-{_now_date()}-{os.urandom(6).hex()}",
        text=cleaned,
        kind=normalized,
        area=area,
        observed_on=_now_date(),
        source_note=source_note,
    )


def _plan_for(text: str) -> Optional[FilingPlan]:
    """Compiler plan only. executed stays False inside services.devon."""
    response = Devon().ask(text)
    if response.plan is not None:
        return response.plan
    utterance = text.strip()
    if not utterance.lower().startswith("remember"):
        utterance = f"remember {utterance}"
        return Devon().ask(utterance).plan
    return None


def _candidate_from_payload(payload: Dict[str, Any]) -> SoulWriteCandidate:
    raw = payload.get("candidate") or {}
    return SoulWriteCandidate(
        candidate_id=str(raw.get("candidate_id") or ""),
        text=str(raw.get("text") or ""),
        kind=str(raw.get("kind") or "lesson"),
        area=raw.get("area"),
        observed_on=str(raw.get("observed_on") or _now_date()),
        source_note=str(raw.get("source_note") or LOOP),
    )


def _action_started_for(events: list, request_id: str) -> Dict[str, Any]:
    """The ACTION_STARTED a commit of this request already wrote, if any."""
    for event in events:
        if event.get("name") != "ACTION_STARTED":
            continue
        payload = event.get("payload") or {}
        if str(payload.get("approval_request_id") or "") == request_id:
            return event
    return {}


def _plan_payload_for(events: list, request_id: str) -> Dict[str, Any]:
    """The PLAN_CREATED that propose wrote for this request.

    It is the one carrying this approval_request_id. PLAN_CREATED occurs at
    most once per intent by ledger law, and the generic event route refuses
    a plan that names a request id, so the plan found here is the proposer's
    own and the candidate in it is the one the ruling was given to.
    """
    for event in events:
        if event.get("name") != "PLAN_CREATED":
            continue
        payload = event.get("payload") or {}
        if str(payload.get("approval_request_id") or "") == request_id:
            return payload
    return {}


class KnowledgeLoop:
    """Propose, approve, consume, commit. One approval authority."""

    async def propose(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        text: str,
        kind: str = "lesson",
        area: Optional[str] = None,
        layer: int = DEFAULT_LAYER,
    ) -> Dict[str, Any]:
        """Enqueue a capture. Returns an approval request.

        Writes Live State Ledger intent rows in PostgreSQL (open_intent,
        CONTEXT_LOADED, PLAN_CREATED, plan_action, APPROVAL_REQUESTED). Does
        not consume the approval. Does not write soul, Notion, or Drive.
        The response carries the request's single-use token so the HUD can
        render the pending card; the token alone approves nothing, approve
        also demands DEVON_RULING_KEY, which no endpoint ever returns.
        """
        allowed, reason = ecosystem.check_layer_write(layer, approved_by_tee=False)
        if layer == 1:
            raise KnowledgeLoopRefused(
                "Tee Soul is never written from this loop. " + reason,
                status_code=403,
            )
        if layer not in (SUBCONSCIOUS_LAYER, DEFAULT_LAYER):
            raise KnowledgeLoopRefused(reason, status_code=422)

        plan = _plan_for(text)
        payload_text = (plan.payload if plan is not None else text).strip()
        if not payload_text:
            raise KnowledgeLoopRefused(
                "Nothing to remember. Say what should be kept.",
                status_code=422,
            )
        plan_area = area or (plan.area if plan is not None else None)
        candidate = _build_candidate(
            payload_text, kind=kind, area=plan_area, source_note=LOOP
        )
        plan_dict = plan.to_dict() if plan is not None else {
            "destination": "live-state-ledger",
            "area": plan_area,
            "payload": payload_text,
            "executed": False,
        }

        if candidate.kind == "ruling":
            what = (
                "Tee files a ruling on the Live State Ledger (PostgreSQL). "
                "Find ranks this above DEVON notes. Layer 1 Tee Soul is not "
                "written. Notion, Drive, and n8n are not written."
            )
        else:
            what = candidate.what_happens() + (
                " Also persists a ledger artifact with body so the capture is "
                "findable in-estate without Drive, Notion, or n8n sitting open."
            )
        record, token = _queue().request(
            title=f"Remember: {payload_text[:80]}",
            what_happens=what,
            requested_by=REQUESTED_BY,
            area=plan_area,
            reversible=True,
            blast_radius="devon-soul and live-state-ledger, never tee-soul-layer",
            owner_id=owner_id,
        )

        opened = await ledger.open_intent(
            db,
            owner_id=owner_id,
            channel="chat_voice",
            stated=payload_text,
            is_effect=True,
        )
        intent_id = opened["intent_id"]
        await ledger.append_event(
            db, owner_id=owner_id, intent_id=intent_id, name="CONTEXT_LOADED",
            payload={"loop": LOOP},
        )
        await ledger.append_event(
            db,
            owner_id=owner_id,
            intent_id=intent_id,
            name="PLAN_CREATED",
            payload={
                "loop": LOOP,
                "approval_request_id": record.request_id,
                "layer": layer,
                "kind": candidate.kind,
                "area": plan_area,
                "candidate": {
                    "candidate_id": candidate.candidate_id,
                    "text": candidate.text,
                    "kind": candidate.kind,
                    "area": candidate.area,
                    "observed_on": candidate.observed_on,
                    "source_note": candidate.source_note,
                },
                "filing_plan": plan_dict,
            },
        )
        action = await ledger.plan_action(
            db,
            owner_id=owner_id,
            intent_id=intent_id,
            duty="devon workflows",
            detail={"loop": LOOP, "approval_request_id": record.request_id},
        )
        await ledger.append_event(
            db,
            owner_id=owner_id,
            intent_id=intent_id,
            name="APPROVAL_REQUESTED",
            action_id=action["action_id"],
            payload={"approval_request_id": record.request_id},
        )
        # Bind the request to this intent on the ledger's own approvals row.
        # UNIQUE(approval_request_id) makes the binding permanent: approve and
        # commit resolve the intent from here, never from a PLAN_CREATED
        # payload that a later writer could imitate.
        await ledger.record_approval(
            db,
            owner_id=owner_id,
            intent_id=intent_id,
            approval_request_id=record.request_id,
            state="pending",
            what_happens=what,
            action_id=action["action_id"],
        )

        connectors = _connector_honesty(postgres_proven=True)
        return {
            "proposed": True,
            "executed": False,
            "intent_id": intent_id,
            "approval": {
                "request_id": record.request_id,
                "title": record.title,
                "what_happens": record.what_happens,
                "expires_at": record.expires_at.isoformat(),
                "state": record.state.value,
                "token": token,
            },
            "plan": plan_dict,
            "layer": layer,
            "layer_write_without_tee": allowed,
            "layer_note": reason,
            "connectors": connectors,
            "simulated": not connectors["pinecone"]["configured"],
        }

    async def approve(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        request_id: str,
        token: str,
        decided_by: str = "Tee",
        ruling_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Human ruling through the existing approval queue. Not a second grantor.

        Two credentials, in this order: the ruling key (DEVON_RULING_KEY,
        typed by the approver, never returned by any endpoint) and then the
        request's single-use token. Everything that can refuse does so BEFORE
        the queue decision is spent, so a refusal for any other reason leaves
        the approval still spendable. The ruling is then written onto the
        ledger's own approvals row, which is what commit verifies. And
        because a decision can succeed while the ledger write after it fails,
        an already-APPROVED request with a valid token repairs the missing
        ruling and APPROVAL_GRANTED event instead of wedging on "already
        approved" forever.
        """
        _require_ruling_key(ruling_key)
        # Resolve the binding first: a wrong owner or a missing binding must
        # refuse while the single-use decision is still unspent.
        binding = await ledger.approval_binding(
            db, owner_id=owner_id, request_id=request_id
        )
        intent_id = binding["intent_id"]
        if binding["state"] not in ("pending", "approved"):
            raise KnowledgeLoopRefused(
                f"The ledger records this request as {binding['state']}, so it "
                "cannot be approved. Propose it again.",
                status_code=403,
            )
        result = _queue().decide(request_id, token, "approve", decided_by)
        already_approved = (
            not result.ok and result.state is ApprovalState.APPROVED
        )
        # decide() verifies the token before it reports an already-decided
        # state, so this branch is only reachable with the right token.
        if not result.approved and not already_approved:
            raise KnowledgeLoopRefused(
                result.message or "Approval refused.",
                status_code=403,
            )

        # The ledger's own word that the ruling-key lane ruled. Commit reads
        # this row and never an event name, so a queue decision made anywhere
        # else (the shared decide route, a script holding the token) commits
        # nothing.
        ruled = await ledger.rule_approval(
            db, owner_id=owner_id, request_id=request_id, decided_by=decided_by
        )
        opened = await ledger.read_intent(db, owner_id=owner_id, intent_id=intent_id)
        names = [event["name"] for event in opened["events"]]
        granted_now = False
        if "APPROVAL_GRANTED" not in names:
            await ledger.append_event(
                db,
                owner_id=owner_id,
                intent_id=intent_id,
                name="APPROVAL_GRANTED",
                payload={"approval_request_id": request_id, "decided_by": decided_by},
            )
            granted_now = True

        return {
            "ok": True,
            "approved": True,
            "already_approved": already_approved,
            "repaired": already_approved and (granted_now or ruled["changed"]),
            "request_id": request_id,
            "intent_id": intent_id,
            "state": "approved",
            "message": (
                "Already approved; the ledger grant now stands. Commit it."
                if already_approved
                else result.message
            ),
            "executed": False,
        }

    async def commit(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        request_id: str,
    ) -> Dict[str, Any]:
        """Consume-before-execute. Ledger always; soul only when the layer is on.

        Three things must agree before the approval is spent: the queue says
        approved, the ledger's approvals row says approved (only ``approve``
        above writes that, after the ruling key), and the plan that names
        this request is on the bound intent. An APPROVAL_GRANTED event alone
        proves nothing here.
        """
        # The owner-scoped binding comes first, so another account's request
        # id learns nothing from the shared queue's state.
        binding = await ledger.approval_binding(
            db, owner_id=owner_id, request_id=request_id
        )
        intent_id = binding["intent_id"]
        record = _queue().get(request_id)
        if record is None:
            raise KnowledgeLoopRefused("No approval request with that id.", status_code=403)
        if record.state is ApprovalState.PENDING:
            raise KnowledgeLoopRefused(
                "Unapproved execute is refused. A human token must grant first.",
                status_code=403,
            )
        if record.state is ApprovalState.CONSUMED:
            raise KnowledgeLoopRefused(
                "This approval was already spent; raise a new one.",
                status_code=403,
            )
        if record.state is not ApprovalState.APPROVED:
            raise KnowledgeLoopRefused(
                f"State is {record.state.value}, not approved.",
                status_code=403,
            )

        if binding["state"] != "approved":
            raise KnowledgeLoopRefused(
                "The ledger holds no ruling for this request. The queue may say "
                "approved, but the approval did not come through the ruling-key "
                "lane. Approve it with POST /api/v1/soul/approve, the single-use "
                "token and DEVON_RULING_KEY.",
                status_code=403,
            )
        if await ledger.emergency_stopped(db, owner_id=owner_id):
            raise KnowledgeLoopRefused(
                ecosystem.EMERGENCY_STOP_RULE,
                status_code=403,
            )

        opened = await ledger.read_intent(db, owner_id=owner_id, intent_id=intent_id)
        plan_payload = _plan_payload_for(opened["events"], request_id)
        if not plan_payload:
            raise KnowledgeLoopRefused(
                "No knowledge-loop plan on this intent names this request, so "
                "there is no candidate the ruling was given to.",
                status_code=403,
            )
        layer = int(plan_payload.get("layer") or DEFAULT_LAYER)
        allowed, layer_reason = ecosystem.check_layer_write(layer, approved_by_tee=True)
        if not allowed:
            raise KnowledgeLoopRefused(layer_reason, status_code=403)

        names = [event["name"] for event in opened["events"]]
        if "APPROVAL_GRANTED" not in names:
            raise KnowledgeLoopRefused(
                ecosystem.EFFECT_GATE_RULE,
                status_code=403,
            )

        # The ledger rows that describe this commit are durable before the
        # approval is spent, and the spend is the last thing before the
        # effect. The approval store spends on its own connection and cannot
        # join this transaction, so the order of durability is the guarantee:
        # a failure after the spend leaves ACTION_STARTED and ACTION_FAILED on
        # the intent instead of a spent approval, a fired webhook and no row.
        # Commits of one request are serialized on the intent, and a second
        # commit finds the first one's ACTION_STARTED under the lock.
        await db.execute(
            text("SELECT pg_advisory_xact_lock(hashtext(CAST(:key AS text)))"),
            {"key": f"knowledge-loop:{intent_id}"},
        )
        opened = await ledger.read_intent(db, owner_id=owner_id, intent_id=intent_id)
        if _action_started_for(opened["events"], request_id):
            raise KnowledgeLoopRefused(
                "A commit of this approval already started: the ledger holds "
                f"ACTION_STARTED for it on intent {intent_id}. If it ended without "
                "ACTION_COMPLETED or ACTION_FAILED, the process died between the "
                "ledger rows and the spend; raise a new proposal rather than "
                "retrying this one.",
                status_code=409,
            )

        started = await ledger.append_event(
            db,
            owner_id=owner_id,
            intent_id=intent_id,
            name="ACTION_STARTED",
            payload={"approval_request_id": request_id, "consumed": False},
        )

        candidate = _candidate_from_payload(plan_payload)
        filing_plan = plan_payload.get("filing_plan") or {
            "payload": candidate.text,
            "executed": False,
        }
        path = (
            f"estate://ledger/captures/"
            f"{(candidate.area or 'unrouted')}/"
            f"{candidate.candidate_id}"
        )
        artifact = await ledger.record_artifact(
            db,
            owner_id=owner_id,
            intent_id=intent_id,
            path=path,
            sha256=_sha256(candidate.text),
            media_type="text/plain",
            body=candidate.text,
            kind=candidate.kind,
        )
        await ledger.append_event(
            db,
            owner_id=owner_id,
            intent_id=intent_id,
            name="ARTIFACT_CREATED",
            payload={"artifact_id": artifact["artifact_id"], "path": path},
        )

        if layer == SUBCONSCIOUS_LAYER:
            await ledger.record_learning_candidate(
                db,
                owner_id=owner_id,
                intent_id=intent_id,
                summary=candidate.text,
            )
            await ledger.append_event(
                db,
                owner_id=owner_id,
                intent_id=intent_id,
                name="LEARNING_CAPTURED",
                payload={"layer": SUBCONSCIOUS_LAYER},
            )
        await db.commit()

        spent = _queue().consume(request_id, consumed_by="knowledge-loop")
        if not spent.ok:
            reason = spent.reason.value if spent.reason else spent.message
            await self._record_failure(
                db,
                owner_id=owner_id,
                intent_id=intent_id,
                request_id=request_id,
                consumed=False,
                error=reason or "Approval could not be consumed.",
            )
            raise KnowledgeLoopRefused(
                reason or "Approval could not be consumed.",
                status_code=403,
            )

        try:
            soul_result = await self._maybe_write_soul(candidate, layer)
            n8n_result = await self._maybe_route_n8n(candidate, filing_plan)
        except Exception as exc:
            await self._record_failure(
                db,
                owner_id=owner_id,
                intent_id=intent_id,
                request_id=request_id,
                consumed=True,
                error=f"{type(exc).__name__}: {exc}",
            )
            raise KnowledgeLoopRefused(
                f"The effect failed after the approval was spent: {exc}. The ledger "
                f"holds ACTION_FAILED on intent {intent_id}; the approval stays "
                "spent, so raise a new proposal.",
                status_code=502,
            ) from exc

        await ledger.append_event(
            db,
            owner_id=owner_id,
            intent_id=intent_id,
            name="ACTION_COMPLETED",
            payload={
                "soul_written": bool(soul_result.get("written")),
                "n8n_routed": bool(n8n_result.get("routed")),
            },
        )
        receipt = await ledger.issue_receipt(
            db,
            owner_id=owner_id,
            intent_id=intent_id,
            what_happened=(
                f"Remembered in-estate: {candidate.text[:400]}. "
                f"Ledger artifact {artifact['artifact_id']}."
            ),
            verification=(
                f"Read the ledger row back: intent {intent_id} is receipted, "
                f"artifact path {path}."
            ),
            provenance="app.services.knowledge_loop",
            artifacts=[path],
            learned=candidate.text[:400],
            next_steps="Find via GET /api/v1/soul/find. Pinecone recall only when the layer is on.",
        )
        await db.commit()

        connectors = _connector_honesty(postgres_proven=True)
        pinecone_on = connectors["pinecone"]["configured"]
        return {
            "executed": True,
            "plan": filing_plan,
            "intent_id": intent_id,
            "request_id": request_id,
            "consumed": True,
            "action": started,
            "artifact": artifact,
            "receipt": receipt,
            "soul": soul_result,
            "n8n": n8n_result,
            "connectors": connectors,
            "simulated": not (pinecone_on and soul_result.get("written")),
            "live": bool(pinecone_on and soul_result.get("written")),
        }

    async def _record_failure(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        intent_id: str,
        request_id: str,
        consumed: bool,
        error: str,
    ) -> None:
        """ACTION_FAILED, committed on its own, so the trace survives the raise."""
        await db.rollback()
        await ledger.append_event(
            db,
            owner_id=owner_id,
            intent_id=intent_id,
            name="ACTION_FAILED",
            payload={
                "approval_request_id": request_id,
                "consumed": consumed,
                "error": error[:500],
            },
        )
        await db.commit()

    async def find(
        self,
        db: AsyncSession,
        *,
        owner_id: str,
        query: str,
        kind: Optional[str] = None,
    ) -> Dict[str, Any]:
        """Find a committed capture without Drive/Notion/n8n sitting open.

        ILIKE on stated+body. Tee rulings first. Not Pinecone hierarchy.
        """
        hits = await ledger.search_receipted_captures(
            db, owner_id=owner_id, query=query, kind=kind
        )
        hits = memory_store.from_receipted_artifacts(hits)
        layer = soul_service.get_soul_layer()
        soul_hits: list[dict] = []
        soul_errors: list[str] = []
        if layer is not None:
            try:
                recall = await layer.recall(query, top_k_tee=2, top_k_devon=5)
                soul_hits = [r.to_dict() for r in recall.records]
                soul_errors = list(recall.errors)
            except Exception as exc:
                soul_errors.append(str(exc)[:300])
        return {
            "query": query,
            "ledger": hits,
            "soul": soul_hits,
            "soul_errors": soul_errors,
            "soul_recall_enabled": layer is not None,
            "findable_without_vault_tools": bool(hits),
            "live": layer is not None,
            "simulated": layer is None,
        }

    async def _maybe_write_soul(
        self, candidate: SoulWriteCandidate, layer: int
    ) -> Dict[str, Any]:
        if candidate.kind not in ALLOWED_KINDS:
            return {
                "written": False,
                "live": False,
                "reason": (
                    f"Kind {candidate.kind} stays on the PostgreSQL ledger. "
                    "Layer 1 Tee Soul is never written from this loop. "
                    "Pinecone devon-soul only accepts lesson/correction/pattern/preference."
                ),
            }
        if layer != DEFAULT_LAYER:
            return {
                "written": False,
                "live": False,
                "reason": (
                    "Layer is subconscious. Durable mark is LEARNING_CAPTURED on the ledger, "
                    "not a devon-soul upsert."
                ),
            }
        layer_obj = soul_service.get_soul_layer()
        if layer_obj is None:
            return {
                "written": False,
                "live": False,
                "reason": (
                    "Soul layer is off. Set SOUL_RECALL_ENABLED=true and "
                    "PINECONE_API_KEY to write devon-soul. Ledger still holds the capture."
                ),
            }
        try:
            written = await layer_obj.commit(candidate, _ApprovedDecision())
        except SoulWriteRefused as exc:
            return {"written": False, "live": False, "reason": str(exc)}
        except Exception as exc:
            return {
                "written": False,
                "live": False,
                "reason": f"Soul write failed: {type(exc).__name__}: {str(exc)[:200]}",
            }
        return {
            "written": True,
            "live": True,
            "record_id": written.get("record_id"),
            "namespace": written.get("namespace"),
            "reason": "Committed to devon-soul after consumed approval. Tee Soul untouched.",
        }

    async def _maybe_route_n8n(
        self, candidate: SoulWriteCandidate, filing_plan: Dict[str, Any]
    ) -> Dict[str, Any]:
        url, key = _n8n_env()
        if not url:
            return {
                "routed": False,
                "live": False,
                "reason": "N8N_WEBHOOK_URL unset. In-estate loop is the ledger.",
            }
        try:
            import httpx

            headers = {"Content-Type": "application/json"}
            if key:
                headers["x-devon-key"] = key
            async with httpx.AsyncClient(timeout=8.0) as client:
                response = await client.post(
                    url,
                    headers=headers,
                    json={
                        "loop": LOOP,
                        "text": candidate.text,
                        "kind": candidate.kind,
                        "area": candidate.area,
                        "plan": filing_plan,
                    },
                )
            return {
                "routed": response.status_code < 400,
                "live": False,
                "status_code": response.status_code,
                "reason": (
                    "Posted to N8N_WEBHOOK_URL. Not claimed operator-live."
                    if response.status_code < 400
                    else f"n8n webhook returned HTTP {response.status_code}."
                ),
            }
        except Exception as exc:
            return {
                "routed": False,
                "live": False,
                "reason": f"n8n route failed: {type(exc).__name__}: {str(exc)[:200]}",
            }


knowledge_loop = KnowledgeLoop()
