"""
The DEVON command language, and the single router that serves it.

Command phrases come from Devon Command Language
(Drive id 1aqct4_UZqlI11IDdRpPS4kbpiaHxoqph) and the Cross-Platform Capture
Protocol (1jVAQ6KwhFXoONg3cLYFDfi0zhLMjWAfi), both read 2026-08-22. The device
intents come from the upstream Jarvis assistant this module was rebuilt from
(github.com/Vannu07/jarvis, backend/nlp/command_parser.py at 21b9d63).

WHAT CHANGED FROM UPSTREAM, AND WHY

One router, not two. Upstream ran two parallel routing systems that disagreed:
`takeAllCommands` in backend/command.py matched raw substrings, so any utterance
containing "open" was routed to the app launcher, while `handle_user_text` in
backend/feature.py used the fuzzy parser. The same sentence could take either
path depending on which entry point received it. Everything routes here now.

Confidence is per intent, not global. Upstream returned the best fuzzy match at
a flat threshold of 60 across all intents, and that pool included `shutdown` and
`restart`. A 60 percent token match to a destructive intent is not consent. Here,
every intent declares its own floor, and effect intents sit far higher.

Effects are declared, not discovered. Each intent states whether it changes
state and whether it needs a human ruling before running. The router never
executes anything; it returns what it understood and lets the caller take it to
the approval gate. That keeps the parser free of any capability it could be
argued into using.

Matching uses difflib from the standard library rather than fuzzywuzzy plus
python-Levenshtein. Two reasons: it removes a compiled dependency from the
install path, and difflib is deterministic across versions, so a test asserting
a score still asserts the same thing next year.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from typing import Dict, List, Optional, Sequence, Tuple

SOURCES = {
    "command_language": "1aqct4_UZqlI11IDdRpPS4kbpiaHxoqph",
    "capture_protocol": "1jVAQ6KwhFXoONg3cLYFDfi0zhLMjWAfi",
    "upstream": "github.com/Vannu07/jarvis backend/nlp/command_parser.py at 21b9d63",
}

WAKE_WORDS: Tuple[str, ...] = ("devon", "jarvis")


class Kind(str, Enum):
    """What an intent does to the world."""

    READ = "read"
    CAPTURE = "capture"
    EFFECT = "effect"


@dataclass(frozen=True)
class Intent:
    """One thing DEVON knows how to be asked for."""

    name: str
    kind: Kind
    phrases: Tuple[str, ...]
    destination: Optional[str] = None
    requires_approval: bool = False
    min_score: float = 0.72
    takes_payload: bool = False
    payload_after: Tuple[str, ...] = ()
    description: str = ""


# ---------------------------------------------------------------------------
# The DEVON command language. Plain language triggers, no syntax to memorise.
# ---------------------------------------------------------------------------

DEVON_INTENTS: Tuple[Intent, ...] = (
    Intent(
        name="capture",
        kind=Kind.CAPTURE,
        phrases=("remember", "remember this", "make a note", "note this", "capture this"),
        destination="Live State Ledger (Postgres). Notion Inbox, Notes and Ideas is missing",
        min_score=0.80,
        takes_payload=True,
        payload_after=("remember that", "remember this", "remember", "make a note of", "note this", "capture this"),
        description="Captures anything, tagged and filed.",
    ),
    Intent(
        name="add_task",
        kind=Kind.CAPTURE,
        phrases=("add a task", "add task", "new task", "remind me to"),
        destination="Live State Ledger (Postgres). Notion Tasks is missing",
        min_score=0.80,
        takes_payload=True,
        payload_after=("add a task to", "add a task", "add task", "new task", "remind me to"),
        description="Creates a task with priority and due date.",
    ),
    Intent(
        name="whats_on_my_plate",
        kind=Kind.READ,
        phrases=(
            "what's on my plate",
            "whats on my plate",
            "what is on my plate",
            "what do i have on",
            "what's due",
        ),
        min_score=0.78,
        description="Reads back tasks, deadlines and project status.",
    ),
    Intent(
        name="start_project",
        kind=Kind.CAPTURE,
        phrases=("start a project called", "start a project", "new project called", "new project"),
        destination="Live State Ledger (Postgres). Notion Projects and Goals is missing",
        min_score=0.82,
        takes_payload=True,
        payload_after=("start a project called", "start a project", "new project called", "new project"),
        description="Creates a project record.",
    ),
    Intent(
        name="status_report",
        kind=Kind.READ,
        phrases=("status report", "give me a status report", "project status"),
        min_score=0.80,
        description="Project rollup.",
    ),
    Intent(
        name="episode_idea",
        kind=Kind.CAPTURE,
        phrases=("new episode idea", "episode idea", "add an episode idea"),
        destination="Live State Ledger (Postgres). Airtable Podcast HQ, Idea stage is missing",
        min_score=0.82,
        takes_payload=True,
        payload_after=("new episode idea", "episode idea", "add an episode idea"),
        description="Files into the episode pipeline.",
    ),
    Intent(
        name="brief",
        kind=Kind.READ,
        phrases=("brief me", "give me the briefing", "morning briefing", "briefing"),
        min_score=0.80,
        description="On demand briefing.",
    ),
    Intent(
        name="log_thread",
        kind=Kind.CAPTURE,
        phrases=("log this thread", "log this conversation", "receipt", "file a receipt"),
        destination="Live State Ledger (Postgres). Notion Conversations, Thread Log is missing",
        min_score=0.84,
        description="Emits and files a DEVON receipt for this thread.",
    ),
    Intent(
        name="recall",
        kind=Kind.READ,
        phrases=(
            "what do we already know about",
            "what do we know about",
            "what did we decide about",
            "have we discussed",
        ),
        min_score=0.76,
        takes_payload=True,
        payload_after=(
            "what do we already know about",
            "what do we know about",
            "what did we decide about",
            "have we discussed",
        ),
        description="Queries the thread log before answering.",
    ),
    Intent(
        name="triage",
        kind=Kind.READ,
        phrases=("show me untriaged captures", "untriaged captures", "what needs filing"),
        min_score=0.80,
        description="Lists captures awaiting the weekly review.",
    ),
    Intent(
        name="refresh_dashboard",
        kind=Kind.EFFECT,
        phrases=("refresh my dashboard", "refresh the dashboard", "rebuild my dashboard"),
        destination="regenerates the HUD snapshot",
        requires_approval=False,
        min_score=0.84,
        description="Regenerates the HUD snapshot. Output lives in the session, not on Drive.",
    ),
    Intent(
        name="refresh_brain_map",
        kind=Kind.EFFECT,
        phrases=("refresh my brain map", "refresh the brain map", "rebuild my brain map"),
        destination="regenerates the neural map",
        requires_approval=False,
        min_score=0.84,
        description="Regenerates the neural map. Output lives in the session, not on Drive.",
    ),
)


# ---------------------------------------------------------------------------
# Device and utility intents, carried over from upstream Jarvis.
# ---------------------------------------------------------------------------

DEVICE_INTENTS: Tuple[Intent, ...] = (
    Intent(
        name="get_time",
        kind=Kind.READ,
        phrases=("what time is it", "tell me the time", "current time", "what's the time", "time now"),
        min_score=0.72,
    ),
    Intent(
        name="get_date",
        kind=Kind.READ,
        phrases=("what's the date", "what is the date", "today's date", "current date", "what date is it"),
        min_score=0.72,
    ),
    Intent(
        name="get_weather",
        kind=Kind.READ,
        phrases=("what's the weather", "current weather", "weather report", "weather today", "how's the weather"),
        min_score=0.74,
        takes_payload=True,
        payload_after=("weather in", "weather for", "forecast in", "forecast for"),
    ),
    Intent(
        name="get_news",
        kind=Kind.READ,
        phrases=("latest news", "tell me the news", "news headlines", "what's the news"),
        min_score=0.74,
    ),
    Intent(
        name="search_web",
        kind=Kind.EFFECT,
        phrases=("search for", "look up", "google for", "find information about"),
        requires_approval=False,
        min_score=0.78,
        takes_payload=True,
        payload_after=("search for", "search google for", "look up", "google for", "find information about"),
        description="Opens a search in the browser.",
    ),
    Intent(
        name="play_youtube",
        kind=Kind.EFFECT,
        phrases=("play on youtube", "play youtube", "put on youtube"),
        requires_approval=False,
        min_score=0.80,
        takes_payload=True,
        description="Opens a video in the browser.",
    ),
    Intent(
        name="open_app",
        kind=Kind.EFFECT,
        phrases=("open calculator", "open browser", "open whatsapp", "launch"),
        requires_approval=True,
        min_score=0.86,
        takes_payload=True,
        payload_after=("open", "launch", "start"),
        description="Launches a program. Approval gated: the target comes from speech.",
    ),
    Intent(
        name="take_screenshot",
        kind=Kind.EFFECT,
        phrases=("take a screenshot", "capture screen", "screen capture"),
        requires_approval=True,
        min_score=0.84,
        description="Writes an image of the screen to disk. Approval gated: screens hold secrets.",
    ),
    Intent(
        name="send_message",
        kind=Kind.EFFECT,
        phrases=("send a message to", "send message", "message"),
        requires_approval=True,
        min_score=0.88,
        takes_payload=True,
        payload_after=("send a message to", "send message to", "send message", "message"),
        description="Sends on the user's behalf. Approval gated and irreversible.",
    ),
    Intent(
        name="shutdown",
        kind=Kind.EFFECT,
        phrases=("shut down the computer", "shutdown the computer", "power off the computer"),
        requires_approval=True,
        min_score=0.92,
        description="Powers the machine off. Approval gated at the highest floor.",
    ),
    Intent(
        name="restart",
        kind=Kind.EFFECT,
        phrases=("restart the computer", "reboot the computer", "restart the system"),
        requires_approval=True,
        min_score=0.92,
        description="Reboots the machine. Approval gated at the highest floor.",
    ),
    Intent(
        name="stop",
        kind=Kind.READ,
        phrases=("goodbye", "stop listening", "that's all", "exit"),
        min_score=0.82,
        description="Ends the listening session.",
    ),
)

ALL_INTENTS: Tuple[Intent, ...] = DEVON_INTENTS + DEVICE_INTENTS

INTENTS_BY_NAME: Dict[str, Intent] = {i.name: i for i in ALL_INTENTS}


class Method(str, Enum):
    EXACT = "exact phrase"
    PREFIX = "prefix match"
    FUZZY = "fuzzy match"
    NONE = "no match"


@dataclass
class ParsedCommand:
    """What the router understood, and how confident it is.

    `understood` false is a legitimate outcome. Declining is better than routing
    a half heard sentence into an effect.
    """

    intent: Optional[Intent] = None
    payload: str = ""
    score: float = 0.0
    method: Method = Method.NONE
    text: str = ""
    reason: str = ""

    @property
    def understood(self) -> bool:
        return self.intent is not None

    @property
    def name(self) -> str:
        return self.intent.name if self.intent else "unknown"

    @property
    def requires_approval(self) -> bool:
        return bool(self.intent and self.intent.requires_approval)

    @property
    def is_effect(self) -> bool:
        return bool(self.intent and self.intent.kind is Kind.EFFECT)


def strip_wake_word(text: str) -> str:
    """Remove a leading wake word and its punctuation.

    Only leading, and only once. Stripping every occurrence would eat the word
    out of "remember Devon owes me a callback", which is a capture about Devon,
    not a command to him.
    """
    cleaned = (text or "").strip()
    for wake in WAKE_WORDS:
        pattern = rf"^\s*{re.escape(wake)}\b[\s,:.!]*"
        match = re.match(pattern, cleaned, re.IGNORECASE)
        if match:
            return cleaned[match.end():].strip()
    return cleaned


def normalize(text: str) -> str:
    """Lowercase, collapse whitespace, drop terminal punctuation."""
    cleaned = re.sub(r"\s+", " ", (text or "").strip().lower())
    return cleaned.rstrip("?.!,")


def _token_sort_ratio(a: str, b: str) -> float:
    """Order insensitive similarity, 0.0 to 1.0.

    Sorting tokens before comparing means "the time what is" scores the same as
    "what is the time", which is the property upstream got from fuzzywuzzy's
    token_sort_ratio. Built on difflib so nothing compiled is required.
    """
    left = " ".join(sorted(a.split()))
    right = " ".join(sorted(b.split()))
    if not left or not right:
        return 0.0
    return SequenceMatcher(None, left, right).ratio()


def _extract_payload(text: str, intent: Intent) -> str:
    """Pull the argument out of a command.

    Tries the declared lead-ins longest first, so "add a task to" wins over
    "add a task" and the payload does not keep a dangling preposition.
    """
    lowered = text.lower()
    for lead in sorted(intent.payload_after, key=len, reverse=True):
        index = lowered.find(lead.lower())
        if index != -1:
            return text[index + len(lead):].strip(" ,:;-")
    for phrase in sorted(intent.phrases, key=len, reverse=True):
        index = lowered.find(phrase.lower())
        if index != -1:
            return text[index + len(phrase):].strip(" ,:;-")
    return ""


def parse(text: str, intents: Optional[Sequence[Intent]] = None) -> ParsedCommand:
    """Route one utterance to at most one intent.

    Order is exact, then prefix, then fuzzy. The first two are deterministic and
    carry a payload cleanly; fuzzy exists for misheard speech and is held to each
    intent's own floor.
    """
    pool = tuple(intents) if intents is not None else ALL_INTENTS
    original = strip_wake_word(text)
    normalized = normalize(original)

    if not normalized:
        return ParsedCommand(text=text, reason="empty after wake word removal")

    for intent in pool:
        for phrase in intent.phrases:
            if normalized == normalize(phrase):
                return ParsedCommand(
                    intent=intent,
                    payload=_extract_payload(original, intent) if intent.takes_payload else "",
                    score=1.0,
                    method=Method.EXACT,
                    text=original,
                    reason=f"exact phrase '{phrase}'",
                )

    prefix_hits: List[Tuple[Intent, str]] = []
    for intent in pool:
        for phrase in intent.phrases:
            normalized_phrase = normalize(phrase)
            if normalized.startswith(normalized_phrase + " ") or (
                normalized_phrase in normalized and intent.takes_payload
            ):
                prefix_hits.append((intent, phrase))

    if prefix_hits:
        # Longest matched phrase wins: "start a project called" beats "new project".
        intent, phrase = max(prefix_hits, key=lambda pair: len(pair[1]))
        return ParsedCommand(
            intent=intent,
            payload=_extract_payload(original, intent) if intent.takes_payload else "",
            score=0.95,
            method=Method.PREFIX,
            text=original,
            reason=f"phrase '{phrase}' found in utterance",
        )

    best_intent: Optional[Intent] = None
    best_phrase = ""
    best_score = 0.0
    for intent in pool:
        for phrase in intent.phrases:
            score = _token_sort_ratio(normalized, normalize(phrase))
            if score > best_score:
                best_score, best_intent, best_phrase = score, intent, phrase

    if best_intent is not None and best_score >= best_intent.min_score:
        return ParsedCommand(
            intent=best_intent,
            payload=_extract_payload(original, best_intent) if best_intent.takes_payload else "",
            score=round(best_score, 3),
            method=Method.FUZZY,
            text=original,
            reason=f"fuzzy match to '{best_phrase}' at {best_score:.2f}, "
            f"floor {best_intent.min_score}",
        )

    floor = best_intent.min_score if best_intent else 0.0
    return ParsedCommand(
        text=original,
        score=round(best_score, 3),
        reason=(
            f"best candidate was '{best_phrase}' at {best_score:.2f}, below its floor "
            f"of {floor}. Declining rather than guessing."
        )
        if best_intent
        else "no candidate",
    )


def effect_intents() -> List[Intent]:
    """Every intent that changes state. Useful for auditing the surface."""
    return [i for i in ALL_INTENTS if i.kind is Kind.EFFECT]


def approval_gated_intents() -> List[Intent]:
    """Every intent that cannot run without a human ruling."""
    return [i for i in ALL_INTENTS if i.requires_approval]
