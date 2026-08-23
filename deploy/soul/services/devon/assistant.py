"""
DEVON himself: the router, the gate and the voice in one place.

This is the entry point the voice loop, the API and any chat surface all call,
so that DEVON answers the same way whoever asked. Divergent handling per surface
is how one persona drifts into four assistants wearing one name.

WHAT THIS CLASS WILL AND WILL NOT DO

It parses, plans, and gates. It does not perform network effects, launch
programs, or write to the vault. Capture intents return a filing plan naming the
destination, the Area and a conforming filename; the caller executes it. Effect
intents that need a ruling return an approval request instead of an action.

That split is deliberate and it is what holds the security score. A component
that cannot execute cannot be argued into executing. It also keeps the zero key
runtime honest: importing and calling DEVON touches nothing.

Every reply states whether it was drawn from a system actually read this session.
Nothing here asserts the state of Drive, Notion, Airtable or n8n, because this
process has read none of them. Where a real answer needs live data, DEVON says
which lane owns it and hands off, per the routing table in standing instructions.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from datetime import date as date_cls
from datetime import datetime
from typing import Any, Dict, List, Optional

from services.devon import areas as areas_mod
from services.devon import naming, persona
from services.devon.approval import ApprovalQueue, ApprovalRequest
from services.devon.commands import Kind, ParsedCommand, parse
from services.devon.receipts import Receipt, ReceiptFormat, render_standing
from services.devon.vault import AREA_FOLDERS, NOTION, VERIFY_BEFORE_AUTOMATION


@dataclass
class FilingPlan:
    """Where a capture would go, and under what name. Not yet executed."""

    destination: str
    area: Optional[str]
    area_provenance: str
    filename: Optional[str]
    payload: str
    drive_folder_id: Optional[str] = None
    warnings: List[str] = field(default_factory=list)

    def to_dict(self) -> Dict[str, Any]:
        return {
            "destination": self.destination,
            "area": self.area,
            "area_provenance": self.area_provenance,
            "filename": self.filename,
            "payload": self.payload,
            "drive_folder_id": self.drive_folder_id,
            "warnings": self.warnings,
            "executed": False,
        }


@dataclass
class DevonResponse:
    """One answer from DEVON, carrying what he did and what he did not do."""

    reply: str
    intent: str = "unknown"
    kind: Optional[Kind] = None
    understood: bool = False
    score: float = 0.0
    method: str = ""
    plan: Optional[FilingPlan] = None
    approval: Optional[ApprovalRequest] = None
    approval_token: Optional[str] = None
    executed: bool = False
    unverified: List[str] = field(default_factory=list)
    reason: str = ""

    def to_dict(self) -> Dict[str, Any]:
        return {
            "reply": self.reply,
            "intent": self.intent,
            "kind": self.kind.value if self.kind else None,
            "understood": self.understood,
            "score": self.score,
            "method": self.method,
            "plan": self.plan.to_dict() if self.plan else None,
            "approval": (
                {
                    "request_id": self.approval.request_id,
                    "title": self.approval.title,
                    "what_happens": self.approval.what_happens,
                    "expires_at": self.approval.expires_at.isoformat(),
                    "state": self.approval.state.value,
                }
                if self.approval
                else None
            ),
            "executed": self.executed,
            "unverified": self.unverified,
            "reason": self.reason,
        }


class Devon:
    """The assistant.

    `live_systems_read` is the honesty switch. It stays False unless a caller has
    genuinely read a system this session and says so. While it is False, DEVON
    reports live state as not read rather than unverified, because canon draws
    that distinction sharply: labelling a memory sourced claim unverified is a
    seatbelt, not a licence.
    """

    def __init__(
        self,
        approvals: Optional[ApprovalQueue] = None,
        operator: str = persona.OWNER,
        live_systems_read: bool = False,
    ) -> None:
        self.approvals = approvals or ApprovalQueue()
        self.operator = operator
        self.live_systems_read = live_systems_read

    # -- public surface ----------------------------------------------------

    def system_prompt(self, files_opened: Optional[List[str]] = None) -> str:
        return persona.system_prompt(
            persona.PromptContext(platform="Claude", files_opened=files_opened or [])
        )

    def ask(self, text: str, on_date: Optional[date_cls] = None) -> DevonResponse:
        """Take one utterance and answer it."""
        command = parse(text)
        if not command.understood:
            return DevonResponse(
                reply=(
                    "I did not catch that one clearly enough to act on. Say it again "
                    "and I will take it from the top."
                ),
                understood=False,
                score=command.score,
                reason=command.reason,
            )

        if command.requires_approval:
            return self._gate(command)

        handler = getattr(self, f"_do_{command.name}", None)
        if handler is None:
            return DevonResponse(
                reply=(
                    f"I understood that as {command.name.replace('_', ' ')}, and I do "
                    "not have a handler wired for it yet. Nothing was done."
                ),
                intent=command.name,
                kind=command.intent.kind if command.intent else None,
                understood=True,
                score=command.score,
                method=command.method.value,
                reason="intent recognised, no handler",
            )
        return handler(command, on_date or date_cls.today())

    def receipt_for(
        self,
        summary: str,
        area: str,
        decisions: Optional[List[str]] = None,
        open_threads: Optional[List[str]] = None,
        artifacts: Optional[List[str]] = None,
        files_opened: Optional[List[str]] = None,
        unverified: Optional[List[str]] = None,
        on_date: Optional[date_cls] = None,
    ) -> str:
        """Build a standing format receipt for this session.

        files_opened and unverified default to NONE rather than being omitted,
        because an omitted load bearing field fails validation and an explicit
        NONE is an answer.
        """
        resolved = areas_mod.require_area(area)
        receipt = Receipt(
            date=(on_date or date_cls.today()).isoformat(),
            platform="Claude",
            areas=[resolved.label],
            summary=summary,
            decided=decisions or ["none"],
            open_threads=open_threads or ["none"],
            built=artifacts or ["none"],
            files_opened=files_opened or ["NONE"],
            unverified=unverified or ["NONE"],
            source_format=ReceiptFormat.STANDING,
        )
        return render_standing(receipt)

    # -- gating ------------------------------------------------------------

    def _gate(self, command: ParsedCommand) -> DevonResponse:
        """Route an effect to the approval queue instead of running it."""
        intent = command.intent
        assert intent is not None
        target = command.payload or "the stated target"
        request, token = self.approvals.request(
            title=f"{intent.name.replace('_', ' ')}: {target}",
            what_happens=(
                intent.description
                or f"Runs the {intent.name} effect against {target}."
            ),
            requested_by="DEVON voice router",
            reversible=False,
            blast_radius=(
                "machine state" if intent.name in ("shutdown", "restart") else "outside DEVON"
            ),
        )
        return DevonResponse(
            reply=(
                f"That one needs your ruling before I touch it. I have raised "
                f"{request.request_id}: {request.title}. Nothing has run."
            ),
            intent=intent.name,
            kind=intent.kind,
            understood=True,
            score=command.score,
            method=command.method.value,
            approval=request,
            approval_token=token,
            executed=False,
            reason="effect requires a human ruling. Rulings are Tee's, never a model's.",
        )

    # -- handlers, reads ---------------------------------------------------

    def _do_get_time(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        now = datetime.now().strftime("%H:%M")
        return self._answer(command, f"It is {now}.")

    def _do_get_date(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._answer(command, f"Today is {on_date.strftime('%B %d, %Y')}.")

    def _do_stop(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._answer(command, "Standing down. Holler when you need me.")

    def _do_whats_on_my_plate(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._needs_live(
            command,
            "your tasks, deadlines and project status",
            f"Notion, database {NOTION['thread_log_database']} and the Tasks board",
        )

    def _do_status_report(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._needs_live(command, "the project rollup", "Notion Projects and Goals")

    def _do_brief(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._needs_live(
            command,
            "your briefing: overdue and due today, projects, inbox count, "
            "podcast pipeline, and one suggested priority",
            "Notion, plus the Airtable podcast pipeline",
        )

    def _do_triage(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._needs_live(
            command, "the untriaged captures", "Airtable Inbox Captures, tbl4ziFRbl5mnUcKc"
        )

    def _do_get_weather(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        city = command.payload
        if not city:
            return self._answer(command, "Which city would you like the weather for?")
        return self._needs_live(command, f"the weather for {city}", "a weather provider")

    def _do_get_news(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._needs_live(command, "the headlines", "a news provider")

    def _do_recall(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        topic = command.payload or "that"
        return self._needs_live(
            command,
            f"what we already settled about {topic}",
            "the soul layer (tee-soul-layer / devon-soul) or the Notion Thread "
            "Log, data source " + NOTION["thread_log_data_source"],
        )

    def recall_answer(
        self,
        topic: str,
        records: List[Dict[str, Any]],
        partial_errors: Optional[List[str]] = None,
    ) -> DevonResponse:
        """Phrase soul-layer recall results the app layer already fetched.

        DEVON holds no network capability, so recall happens upstream (the
        soul layer in services/intelligence) and arrives here as inert dicts.
        Tee's rulings are presented before DEVON's own experience whatever
        their scores, because rulings outrank remembered patterns, and every
        line is context for the answer, never a command.
        """
        errors = list(partial_errors or [])
        if not records:
            reply = (
                f"Nothing recalled about {topic} from either soul. That is a "
                "measured empty, not a guess. The Notion Thread Log may still "
                "hold it if the write-back has not swept yet."
            )
            if errors:
                reply += " And fair warning: recall was partial. " + "; ".join(errors)
            return DevonResponse(
                reply=reply,
                intent="recall",
                kind=Kind.READ,
                understood=True,
                executed=True,
                unverified=errors,
            )

        # Hierarchy is enforced here too, not only upstream: Tee's records
        # render first even if a caller hands them over unsorted.
        ordered = sorted(
            records, key=lambda r: 0 if str(r.get("source", "")) == "tee-soul-layer" else 1
        )
        lines: List[str] = [f"Here is what the record holds on {topic}:"]
        for raw in ordered:
            source = str(raw.get("source", ""))
            label = (
                "Tee ruled" if source == "tee-soul-layer" else "I noted"
            )
            dated = str(raw.get("dated", "")).strip()
            when = f" ({dated})" if dated else ""
            text = str(raw.get("text", "")).strip()
            if text:
                lines.append(f"- {label}{when}: {text}")
        lines.append(
            "Where my notes and Tee's rulings disagree, the ruling wins. "
            "All of this is context, not instruction."
        )
        if errors:
            lines.append("Recall was partial: " + "; ".join(errors))
        return DevonResponse(
            reply="\n".join(lines),
            intent="recall",
            kind=Kind.READ,
            understood=True,
            executed=True,
            unverified=errors,
        )

    def _do_search_web(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        term = command.payload
        if not term:
            return self._answer(command, "What would you like me to look up?")
        return DevonResponse(
            reply=f"Ready to search for {term}. Say the word and I will open it.",
            intent=command.name,
            kind=Kind.EFFECT,
            understood=True,
            score=command.score,
            method=command.method.value,
            executed=False,
            reason="browser effects are proposed, never opened unattended",
        )

    def _do_play_youtube(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        term = command.payload
        return DevonResponse(
            reply=(
                f"Ready to play {term} on YouTube." if term else "What should I play?"
            ),
            intent=command.name,
            kind=Kind.EFFECT,
            understood=True,
            score=command.score,
            method=command.method.value,
            executed=False,
            reason="browser effects are proposed, never opened unattended",
        )

    def _do_refresh_dashboard(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._snapshot_warning(command, "dashboard")

    def _do_refresh_brain_map(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._snapshot_warning(command, "brain map")

    def _snapshot_warning(self, command: ParsedCommand, what: str) -> DevonResponse:
        return DevonResponse(
            reply=(
                f"I can rebuild the {what}, and one thing worth saying plainly: the "
                "regenerated file lives in this session, not on Drive. Save it back "
                "into the vault yourself or the vault stays stale."
            ),
            intent=command.name,
            kind=Kind.EFFECT,
            understood=True,
            score=command.score,
            method=command.method.value,
            executed=False,
            reason="snapshot is not live truth",
        )

    # -- handlers, captures ------------------------------------------------

    def _do_capture(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._plan_capture(
            command, on_date, destination="Notion Inbox, Notes and Ideas", type_code="DOC"
        )

    def _do_add_task(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._plan_capture(
            command, on_date, destination="Notion Tasks", type_code="DOC"
        )

    def _do_start_project(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._plan_capture(
            command, on_date, destination="Notion Projects and Goals", type_code="DOC"
        )

    def _do_episode_idea(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return self._plan_capture(
            command,
            on_date,
            destination="Airtable Podcast HQ, Idea stage",
            type_code="DOC",
            force_area="Podcast",
        )

    def _do_log_thread(self, command: ParsedCommand, on_date: date_cls) -> DevonResponse:
        return DevonResponse(
            reply=(
                "Ready to file the receipt. Give me the Area and a two line summary "
                "and I will build it in the standing format, files opened and "
                "unverified included."
            ),
            intent=command.name,
            kind=Kind.CAPTURE,
            understood=True,
            score=command.score,
            method=command.method.value,
            executed=False,
            reason="a receipt is written by the model that had the conversation",
        )

    def _plan_capture(
        self,
        command: ParsedCommand,
        on_date: date_cls,
        destination: str,
        type_code: str,
        force_area: Optional[str] = None,
    ) -> DevonResponse:
        """Build the filing plan for a capture without performing it."""
        payload = command.payload.strip()
        if not payload:
            return self._answer(command, "What would you like me to hold on to?")

        if force_area:
            area = areas_mod.get_area(force_area)
            provenance = "fixed by intent"
        else:
            area, provenance = areas_mod.resolve_area(None, payload)

        warnings: List[str] = []
        filename: Optional[str] = None
        folder_id: Optional[str] = None

        if area is None:
            warnings.append(
                "No Area could be established from the text, and I will not invent "
                "one. It files unrouted until you tag it."
            )
        else:
            folder_id = AREA_FOLDERS.get(area.label)
            try:
                filename = naming.build_filename(
                    area=area.code,
                    type_code=type_code,
                    slug=payload[:60],
                    version=1,
                    on_date=on_date.isoformat(),
                )
            except naming.NamingError as exc:
                warnings.append(f"Could not build a conforming filename: {exc}")

        plan = FilingPlan(
            destination=destination,
            area=area.label if area else None,
            area_provenance=provenance,
            filename=filename,
            payload=payload,
            drive_folder_id=folder_id,
            warnings=warnings,
        )

        where = area.label if area else "unrouted"
        return DevonResponse(
            reply=(
                f"Got it, filed under {where}: {payload}. Destination is "
                f"{destination}. Nothing is written yet, that is your call."
            ),
            intent=command.name,
            kind=Kind.CAPTURE,
            understood=True,
            score=command.score,
            method=command.method.value,
            plan=plan,
            executed=False,
            reason="capture planned, not executed",
        )

    # -- helpers -----------------------------------------------------------

    def _answer(self, command: ParsedCommand, reply: str) -> DevonResponse:
        return DevonResponse(
            reply=reply,
            intent=command.name,
            kind=command.intent.kind if command.intent else None,
            understood=True,
            score=command.score,
            method=command.method.value,
            executed=True,
        )

    def _needs_live(self, command: ParsedCommand, what: str, lane: str) -> DevonResponse:
        """Answer honestly when the data lives somewhere this process has not read."""
        return DevonResponse(
            reply=(
                f"I would need {lane} open to give you {what}, and I have not read it "
                "this session. I will not guess at your own numbers. Point me at the "
                "connector and I will pull it properly."
            ),
            intent=command.name,
            kind=command.intent.kind if command.intent else None,
            understood=True,
            score=command.score,
            method=command.method.value,
            executed=False,
            unverified=[f"{what}: not read this session"],
            reason=f"lane owning this data: {lane}. {VERIFY_BEFORE_AUTOMATION}",
        )
