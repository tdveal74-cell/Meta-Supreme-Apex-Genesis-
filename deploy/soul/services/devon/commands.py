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

WHAT CHANGED ON 2026-09-10, AND WHY

Fourteen of twenty four realistic paraphrases were declined, so the floors were
doing their job and the vocabulary was not. Four changes, none of which touches
a floor.

Aliases, not wider canon. `Intent.phrases` still holds only what the two Drive
documents and upstream actually say. Colloquial ways of asking for the same
thing live in `Intent.aliases`, matched identically but kept separate so the
provenance claim above stays true and so a suggestion can quote a canonical
phrase rather than somebody's paraphrase. `test_devon_commands.py` holds the
canon list shut, so widening can only ever be additive.

The normaliser earns its keep. It now joins contractions by dropping
apostrophes, so "whats the date" is an exact match rather than a 0.97 fuzzy one;
it strips leading and trailing politeness, so "can you brief me" stops being a
0.67 decline; and it repairs the two split compounds speech to text actually
produces here, "screen shot" and "you tube". Every one of those converts a fuzzy
guess into a deterministic match, which is the only kind of widening that is
strictly an improvement.

Anchored beats incidental. A prefix hit at the start of the utterance now wins
over one found in the middle of it, and a mid utterance hit must be a whole word
run of at least two words. Measured at 5ff4348, the old longest-wins rule sent
"the podcast launch is on Friday" and "kick off a project called NCO relaunch"
to `open_app` and "I left a message for Karrie on her desk" to `send_message`,
all three approval gated effects, the last two because "launch" was matched
inside "relaunch" with no word boundary. Those are approval cards a person never
asked for, and a stream of cards nobody asked for is how a gate stops being read.

The decline carries the near miss. `parse` already knew what it almost matched
and threw it away. It now returns that as a structured suggestion, under three
rules that `test_devon_commands.py` enforces: an EFFECT intent is never
suggested, at any score; a suggestion must sit inside a narrow band below the
intent's own floor rather than being whatever scored highest; and a suggestion
is a question for a person, never a route, so `understood` stays False and no
caller can mistake one for a match. The same rule governs the decline text: it
names a candidate only when that candidate passed the suggestion gate, so a near
miss on a destructive intent never reaches a person as a thing to confirm.
"""

from __future__ import annotations

import re
from dataclasses import dataclass
from difflib import SequenceMatcher
from enum import Enum
from functools import lru_cache
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
    """One thing DEVON knows how to be asked for.

    `phrases` is canon: it says what the Drive documents and upstream say, and
    nothing else goes in it. `aliases` is how people actually ask, and it is
    matched exactly the same way. Keeping them apart means the module can still
    say where its vocabulary came from, and it gives a suggestion a canonical
    phrase to quote back rather than a colloquialism.
    """

    name: str
    kind: Kind
    phrases: Tuple[str, ...]
    destination: Optional[str] = None
    requires_approval: bool = False
    min_score: float = 0.72
    takes_payload: bool = False
    payload_after: Tuple[str, ...] = ()
    description: str = ""
    aliases: Tuple[str, ...] = ()
    #: How many words this intent's payload may hold, or None for unbounded.
    #:
    #: Only consulted for an EFFECT intent reached by an ANCHORED prefix hit, and
    #: it exists because a payload with no shape is how ordinary prose becomes an
    #: approval card. Measured 2026-09-10 over real commands: a genuine open_app
    #: payload is an application name and ran 0, 1, 0, 0 words, while
    #: "fire up the grill on Saturday" carries 4 and "boot up sequence for the rig
    #: takes ten minutes" carries 7. send_message legitimately runs to 4
    #: ("Marcus about the render") and a search_web query to 6, so a single global
    #: cap cannot serve all three. It is declared per intent for the same reason
    #: min_score is: the intents differ, and a flat number across them is the bug.
    max_payload_words: Optional[int] = None

    @property
    def triggers(self) -> Tuple[str, ...]:
        """Everything that routes to this intent, canon first."""
        return self.phrases + self.aliases

    @property
    def canonical(self) -> str:
        """The phrase to quote back to a person. Always canon, never an alias."""
        return self.phrases[0] if self.phrases else self.name.replace("_", " ")


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
        payload_after=(
            "remember that",
            "remember this",
            "remember",
            "make a note of",
            "make a note that",
            "note this",
            "note that",
            "capture this",
            "jot that down",
            "jot this down",
            "jot down",
            "write that down",
            "write this down",
            "write down",
            "scribble that down",
            "scribble down",
            "take a note of",
            "take a note that",
            "save this",
            "keep a note of",
            "keep a note that",
        ),
        description="Captures anything, tagged and filed.",
        aliases=(
            "jot that down",
            "jot this down",
            "jot down",
            "write that down",
            "write this down",
            "write down",
            "scribble that down",
            "scribble this down",
            "note that",
            "make a note that",
            "take a note",
            "take a note of",
            "keep a note of",
            "keep a note that",
            "save this",
            "hang on to this",
            "capture that",
        ),
    ),
    Intent(
        name="add_task",
        kind=Kind.CAPTURE,
        phrases=("add a task", "add task", "new task", "remind me to"),
        destination="Live State Ledger (Postgres). Notion Tasks is missing",
        min_score=0.80,
        takes_payload=True,
        payload_after=(
            "add a task to",
            "add a task",
            "add task",
            "new task",
            "remind me to",
            "stick a task on the list to",
            "stick a task on my list to",
            "stick a task on the list",
            "stick a task on my list",
            "put a task on the list to",
            "put a task on my list to",
            "put a task on the list",
            "put a task on my list",
            "add a todo to",
            "add a to do to",
            "add a todo",
            "add a to do",
            "put on my task list",
            "on my task list",
            "add to my task list",
            "add to my list",
        ),
        description="Creates a task with priority and due date.",
        aliases=(
            "stick a task on the list",
            "stick a task on my list",
            "put a task on the list",
            "put a task on my list",
            "add a todo",
            "add a to do",
            "new todo",
            "add to my task list",
            "add to my list",
            "on my task list",
            "put it on the list",
            "put that on the list",
            "task me to",
        ),
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
        aliases=(
            "what's my day looking like",
            "whats my day looking like",
            "what does my day look like",
            "how does my day look",
            "how busy am i",
            "how busy am i today",
            "what have i got on",
            "what do i have today",
            "what am i doing today",
            "what's on today",
            "what's on my list",
            "what's next",
            "what am i on the hook for",
            "what's outstanding",
        ),
    ),
    Intent(
        name="start_project",
        kind=Kind.CAPTURE,
        phrases=("start a project called", "start a project", "new project called", "new project"),
        destination="Live State Ledger (Postgres). Notion Projects and Goals is missing",
        min_score=0.82,
        takes_payload=True,
        payload_after=(
            "start a project called",
            "start a project",
            "new project called",
            "new project",
            "kick off a project called",
            "kick off a project",
            "spin up a project called",
            "spin up a project",
            "open a project called",
            "stand up a project called",
            "stand up a project",
        ),
        description="Creates a project record.",
        aliases=(
            "kick off a project called",
            "kick off a project",
            "spin up a project called",
            "spin up a project",
            "stand up a project called",
            "stand up a project",
            "start a new project called",
            "start a new project",
        ),
    ),
    Intent(
        name="status_report",
        kind=Kind.READ,
        phrases=("status report", "give me a status report", "project status"),
        min_score=0.80,
        description="Project rollup.",
        aliases=(
            "give me the status",
            "what's the status",
            "status",
            "where's everything at",
            "wheres everything at",
            "where are we",
            "where are we with",
            "where do things stand",
            "how are things going",
            "how's everything going",
            "give me a rollup",
            "project rollup",
            "state of play",
        ),
    ),
    Intent(
        name="episode_idea",
        kind=Kind.CAPTURE,
        phrases=("new episode idea", "episode idea", "add an episode idea"),
        destination="Live State Ledger (Postgres). Airtable Podcast HQ, Idea stage is missing",
        min_score=0.82,
        takes_payload=True,
        payload_after=(
            "new episode idea about",
            "add an episode idea about",
            "i have an idea for an episode about",
            "i have an idea for an episode",
            "idea for an episode about",
            "idea for an episode",
            "new episode idea",
            "episode idea",
            "add an episode idea",
            "episode concept",
            "podcast idea",
            "show idea",
            "a thought for the show",
            "thought for the show",
        ),
        description="Files into the episode pipeline.",
        aliases=(
            "i have an idea for an episode",
            "ive got an idea for an episode",
            "idea for an episode",
            "episode concept",
            "podcast idea",
            "show idea",
            "a thought for the show",
            "thought for the show",
            "got a thought for the show",
        ),
    ),
    Intent(
        name="brief",
        kind=Kind.READ,
        phrases=("brief me", "give me the briefing", "morning briefing", "briefing"),
        min_score=0.80,
        description="On demand briefing.",
        aliases=(
            "brief",
            "give me the rundown",
            "give me the rundown for this morning",
            "the rundown",
            "rundown",
            "catch me up",
            "bring me up to speed",
            "what do i need to know",
            "morning brief",
            "daily brief",
        ),
    ),
    Intent(
        name="log_thread",
        kind=Kind.CAPTURE,
        phrases=("log this thread", "log this conversation", "receipt", "file a receipt"),
        destination="Live State Ledger (Postgres). Notion Conversations, Thread Log is missing",
        min_score=0.84,
        description="Emits and files a DEVON receipt for this thread.",
        aliases=(
            "log this to the thread",
            "log this to the thread log",
            "log the thread",
            "log this session",
            "log this chat",
            "log this",
            "save this thread",
            "write this up as a receipt",
            "write this conversation up as a receipt",
            "receipt this thread",
            "receipt for this thread",
            "emit a receipt",
            "cut a receipt",
        ),
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
            "pull up what we said about",
            "pull up what we said before about",
            "pull up what we said before",
            "pull up what we said",
            "what did we say about",
            "what have we said about",
            "what was decided about",
            "did we ever settle",
            "did we ever decide",
            "did we talk about",
            "have we talked about",
            "remind me what we decided about",
            "remind me what we decided",
        ),
        description="Queries the thread log before answering.",
        aliases=(
            "pull up what we said before",
            "pull up what we said",
            "what did we say about",
            "what did we say",
            "what have we said about",
            "what was decided about",
            "did we ever settle",
            "did we ever decide",
            "did we talk about",
            "have we talked about",
            "remind me what we decided",
            "what do we already know",
        ),
    ),
    Intent(
        name="triage",
        kind=Kind.READ,
        phrases=("show me untriaged captures", "untriaged captures", "what needs filing"),
        min_score=0.80,
        description="Lists captures awaiting the weekly review.",
        aliases=(
            "triage",
            "triage that",
            "triage the inbox",
            "run triage",
            "what needs triaging",
            "what's untriaged",
            "whats untriaged",
            "what needs sorting",
            "what's waiting to be filed",
            "anything waiting to be filed",
            "show me the inbox",
        ),
    ),
    Intent(
        name="refresh_dashboard",
        kind=Kind.EFFECT,
        phrases=("refresh my dashboard", "refresh the dashboard", "rebuild my dashboard"),
        destination="regenerates the HUD snapshot",
        requires_approval=False,
        min_score=0.84,
        description="Regenerates the HUD snapshot. Output lives in the session, not on Drive.",
        aliases=(
            "rebuild the dashboard",
            "redraw my dashboard",
            "redraw the dashboard",
            "update my dashboard",
            "refresh the hud",
            "rebuild the hud",
        ),
    ),
    Intent(
        name="refresh_brain_map",
        kind=Kind.EFFECT,
        phrases=("refresh my brain map", "refresh the brain map", "rebuild my brain map"),
        destination="regenerates the neural map",
        requires_approval=False,
        min_score=0.84,
        description="Regenerates the neural map. Output lives in the session, not on Drive.",
        aliases=(
            "rebuild the brain map",
            "redraw my brain map",
            "redraw the brain map",
            "refresh the neural map",
            "rebuild the neural map",
            "update my brain map",
        ),
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
        aliases=(
            "got the time",
            "have you got the time",
            "do you have the time",
            "the time",
            "what's the time now",
            "whats the hour",
        ),
    ),
    Intent(
        name="get_date",
        kind=Kind.READ,
        phrases=("what's the date", "what is the date", "today's date", "current date", "what date is it"),
        min_score=0.72,
        aliases=(
            "what day is it",
            "what day is it today",
            "what's today",
            "whats todays date",
            "the date",
            "what's the date today",
        ),
    ),
    Intent(
        name="get_weather",
        kind=Kind.READ,
        phrases=("what's the weather", "current weather", "weather report", "weather today", "how's the weather"),
        min_score=0.74,
        takes_payload=True,
        payload_after=("weather in", "weather for", "forecast in", "forecast for"),
        aliases=(
            "what's it like outside",
            "what is it like outside",
            "how's it looking outside",
            "is it going to rain",
            "do i need a coat",
            "the forecast",
            "what's the forecast",
        ),
    ),
    Intent(
        name="get_news",
        kind=Kind.READ,
        phrases=("latest news", "tell me the news", "news headlines", "what's the news"),
        min_score=0.74,
        aliases=(
            "give me the headlines",
            "the headlines",
            "headlines",
            "news",
            "any news",
            "what's happening in the world",
            "what is going on in the world",
            "catch me up on the news",
        ),
    ),
    Intent(
        name="search_web",
        kind=Kind.EFFECT,
        phrases=("search for", "look up", "google for", "find information about"),
        requires_approval=False,
        min_score=0.78,
        takes_payload=True,
        payload_after=(
            "search for",
            "search google for",
            "look up",
            "look that up for me",
            "look this up for me",
            "look that up",
            "look this up",
            "google for",
            "google",
            "find information about",
            "search the web for",
            "search the internet for",
        ),
        description="Opens a search in the browser.",
        # A bare "google" is not here on purpose. Measured 2026-09-10: it turned
        # "google is a company not a verb here", which declined at 5ff4348, into
        # a search. A single common word at the front of a sentence is the
        # upstream substring bug wearing a different hat.
        aliases=(
            "look that up",
            "look this up",
            "look that up for me",
            "google the",
            "search the web for",
            "search the internet for",
            "web search for",
        ),
    ),
    Intent(
        name="play_youtube",
        kind=Kind.EFFECT,
        phrases=("play on youtube", "play youtube", "put on youtube"),
        requires_approval=False,
        min_score=0.80,
        takes_payload=True,
        payload_after=(
            "play on youtube",
            "play youtube",
            "put on youtube",
            "pull up on youtube",
            "put on some music",
            "put some music on",
            "play some music",
            "play music",
            "play a video",
            "play the video",
        ),
        description="Opens a video in the browser.",
        aliases=(
            "put on some music",
            "put some music on",
            "play some music",
            "play music",
            "play a video",
            "play the video",
            "pull up on youtube",
        ),
    ),
    Intent(
        name="open_app",
        kind=Kind.EFFECT,
        phrases=("open calculator", "open browser", "open whatsapp", "launch"),
        requires_approval=True,
        min_score=0.86,
        takes_payload=True,
        payload_after=("fire up", "boot up", "open", "launch", "start"),
        # An application name, not a sentence. See max_payload_words on Intent
        # for the measurement; two words covers "visual studio code" style names
        # once the article is stripped, and refuses "the grill on Saturday".
        max_payload_words=2,
        description="Launches a program. Approval gated: the target comes from speech.",
        # A bare "open" is deliberately absent, and this is the one place it is
        # most tempting: it would make "open spotify" work. Measured 2026-09-10,
        # it also turns "open questions remain on the render" into an approval
        # card, and "open" is the exact word whose substring matching this
        # module was rebuilt to kill. "open spotify" declining is the price, and
        # it is the same decline 5ff4348 gave. Two word imperatives are safe
        # because "fire up" and "boot up" are not general purpose English the
        # way "open" is.
        aliases=(
            "fire up",
            "boot up",
            "open chrome",
            "open the browser",
            "launch chrome",
        ),
    ),
    Intent(
        name="take_screenshot",
        kind=Kind.EFFECT,
        phrases=("take a screenshot", "capture screen", "screen capture"),
        requires_approval=True,
        min_score=0.84,
        description="Writes an image of the screen to disk. Approval gated: screens hold secrets.",
        aliases=(
            "grab a screenshot",
            "snap a screenshot",
            "screenshot this",
            "capture the screen",
            "snap the screen",
            "grab the screen",
            "take a picture of the screen",
        ),
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
        aliases=("send a text to", "drop a message to", "shoot a message to", "send a dm to"),
    ),
    Intent(
        name="shutdown",
        kind=Kind.EFFECT,
        phrases=("shut down the computer", "shutdown the computer", "power off the computer"),
        requires_approval=True,
        min_score=0.92,
        description="Powers the machine off. Approval gated at the highest floor.",
        aliases=(
            "shut the computer down",
            "shut the machine down",
            "shut down the machine",
            "power the computer off",
            "turn off the computer",
            "turn the computer off",
        ),
    ),
    Intent(
        name="restart",
        kind=Kind.EFFECT,
        phrases=("restart the computer", "reboot the computer", "restart the system"),
        requires_approval=True,
        min_score=0.92,
        description="Reboots the machine. Approval gated at the highest floor.",
        aliases=(
            "reboot the machine",
            "restart the machine",
            "reboot the system",
            "restart this computer",
            "reboot this computer",
        ),
    ),
    Intent(
        name="stop",
        kind=Kind.READ,
        phrases=("goodbye", "stop listening", "that's all", "exit"),
        min_score=0.82,
        description="Ends the listening session.",
        aliases=(
            "that will be all",
            "thats all for now",
            "that's it",
            "we're done",
            "were done",
            "stand down",
            "bye",
            "see you",
        ),
    ),
)

ALL_INTENTS: Tuple[Intent, ...] = DEVON_INTENTS + DEVICE_INTENTS

INTENTS_BY_NAME: Dict[str, Intent] = {i.name: i for i in ALL_INTENTS}


# ---------------------------------------------------------------------------
# Normalisation. Every rule here converts a fuzzy guess into a deterministic
# match, which is the only widening that costs nothing in confidence.
# ---------------------------------------------------------------------------

# Split compounds that speech to text actually produces for phrases this module
# already carries. Deliberately two entries: a longer list would be speculation
# about words no intent uses.
COMPOUND_FIXES: Tuple[Tuple[str, str], ...] = (
    ("screen shot", "screenshot"),
    ("you tube", "youtube"),
)

# Politeness and address wrappers. Written without apostrophes because they are
# applied after contractions are joined.
#
# "now" is in neither list on purpose: `get_time` carries the canon phrase
# "time now", and stripping a trailing "now" would delete it. "today" is out for
# the same reason, since `get_weather` carries "weather today".
LEADING_FILLERS: Tuple[str, ...] = (
    "i would like you to",
    "i would like to",
    "id like you to",
    "id like to",
    "i want you to",
    "i need you to",
    "go ahead and",
    "go on and",
    "could you please",
    "can you please",
    "would you please",
    "could you",
    "can you",
    "would you",
    "will you",
    "lets",
    "let us",
    "please",
    "hey",
    "okay",
    "ok",
    "alright",
    "erm",
    "um",
    "uh",
    "so",
    "just",
)

TRAILING_FILLERS: Tuple[str, ...] = (
    "if you could",
    "if you can",
    "thank you",
    "thanks",
    "for me",
    "please",
    "real quick",
)

_PUNCTUATION_TO_SPACE = str.maketrans({c: " " for c in ".,!?;:\"()[]{}"})

# A mid utterance phrase must be at least this many words before it may claim an
# utterance it does not start. One word phrases ("launch", "message",
# "remember") match far too much prose to be trusted anywhere but the front.
MIN_WORDS_FOR_MID_UTTERANCE_MATCH = 2

# No alias on an approval gated intent may be a single word, and
# `test_devon_commands.py` enforces it. Canon is exempt because canon is what
# the Drive documents say and this module does not get to edit them; "message"
# and "launch" are both canon and both one word. An alias is ours, so it has to
# earn its place, and each one word alias tried here cost more than it returned:
# "text" turned "text me when the render lands" into a message to send,
# "screenshot" turned "screenshot from yesterday is stale" into a card, and both
# declined cleanly at 5ff4348. Two words is enough to read as an imperative.
MAX_ONE_WORD_ALIASES_ON_GATED_INTENTS = 0

# How far below its own floor a candidate may sit and still be offered to a
# person as a question, and how low it may go whatever its floor.
#
# The score on its own turned out to be the wrong discriminator, in both
# directions, and both were measured on 2026-09-10 rather than reasoned about.
# Tightening the band enough to stop "what about the render" drawing "did you
# mean get time" at 0.69 also threw away "give me the status" against "give me
# a status report" at 0.68, which is the right intent and the whole point of
# suggesting. difflib is comparing letters, so a long utterance can score 0.69
# against a phrase it shares no word with, while a near miss on a high floor
# intent sits lower than a coincidence on a low floor one.
#
# So the band is deliberately loose and `SUGGESTION_STOPWORDS` does the real
# work: a suggestion must share a word that carries meaning. That is a property
# a person can check by reading, which the score is not.
SUGGESTION_MARGIN = 0.15
SUGGESTION_MIN_SCORE = 0.55

# A shared word only counts as evidence if it carries meaning. These are the
# words that turned up doing the opposite: "what about the render" and "i dunno
# what i want" both drew a suggestion off nothing but "what".
SUGGESTION_STOPWORDS = frozenset(
    {
        "what", "whats", "that", "this", "with", "have", "your", "about",
        "there", "here", "some", "does", "will", "would", "could", "from",
        "them", "they", "then", "than", "into", "just", "like", "want",
        "need", "tell", "give", "show", "make", "more", "much", "very",
        "when", "where", "which", "were", "been", "being", "over", "back",
    }
)

# A word has to be at least this long to count as content. Below it, difflib
# noise and English glue are indistinguishable.
MIN_CONTENT_WORD_LENGTH = 4


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

    A declined parse may carry a `suggestion`: the intent DEVON nearly matched,
    for a caller to put to a person as a question. It is never a route. `intent`
    stays None and `understood` stays False, so nothing downstream can act on a
    suggestion by mistake, and an EFFECT intent never appears here at all.
    """

    intent: Optional[Intent] = None
    payload: str = ""
    score: float = 0.0
    method: Method = Method.NONE
    text: str = ""
    reason: str = ""
    suggestion: Optional[Intent] = None
    suggestion_score: float = 0.0

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

    @property
    def has_suggestion(self) -> bool:
        return self.suggestion is not None

    @property
    def suggestion_name(self) -> str:
        return self.suggestion.name if self.suggestion else ""

    @property
    def suggestion_phrase(self) -> str:
        """The canonical phrase to quote back, never an alias and never an effect."""
        return self.suggestion.canonical if self.suggestion else ""


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


# Sorted once at import, longest first, because `_strip_fillers` runs to a fixed
# point and re-sorting inside that loop was costing more than the stripping.
_LEADING_FILLERS_LONGEST_FIRST = tuple(sorted(LEADING_FILLERS, key=len, reverse=True))
_TRAILING_FILLERS_LONGEST_FIRST = tuple(sorted(TRAILING_FILLERS, key=len, reverse=True))


def _strip_fillers(text: str) -> str:
    """Peel politeness off both ends until nothing more comes away.

    Runs to a fixed point so "can you please just brief me for me please" ends
    at "brief me". Each pass strictly shortens the string, so it terminates.
    """
    while True:
        before = text
        for lead in _LEADING_FILLERS_LONGEST_FIRST:
            if text == lead:
                return ""
            if text.startswith(lead + " "):
                text = text[len(lead) + 1:]
                break
        for tail in _TRAILING_FILLERS_LONGEST_FIRST:
            if text == tail:
                return ""
            if text.endswith(" " + tail):
                text = text[: -(len(tail) + 1)]
                break
        text = text.strip()
        if text == before:
            return text


@lru_cache(maxsize=4096)
def normalize(text: str) -> str:
    """Lowercase, join contractions, drop punctuation and politeness.

    Joining contractions by deleting the apostrophe is what turns "whats the
    date" from a 0.97 fuzzy match into an exact one. It is safe for payloads
    because `_extract_payload` works on the original text, not on this.

    Cached because `parse` normalises every trigger of every intent on every
    call, and there are a few hundred of them and they never change. Measured
    2026-09-10: with the widened vocabulary and no cache a parse cost 17.4ms,
    against 3.3ms at 5ff4348. Pure function of its argument, so the cache
    cannot go stale.
    """
    cleaned = (text or "").strip().lower()
    cleaned = cleaned.replace("’", "").replace("'", "")
    cleaned = cleaned.translate(_PUNCTUATION_TO_SPACE)
    cleaned = re.sub(r"\s+", " ", cleaned).strip()
    for split, joined in COMPOUND_FIXES:
        if split in cleaned:
            cleaned = cleaned.replace(split, joined)
    cleaned = _strip_fillers(cleaned)
    return cleaned.strip(" -")


def _contains_whole_phrase(haystack: str, needle: str) -> bool:
    """True when `needle` appears in `haystack` on both word boundaries.

    Plain `in` matched "launch" inside "relaunch", which sent "kick off a
    project called NCO relaunch" to the approval gated app launcher. Written as
    an index scan rather than a regex so there is no pattern to backtrack.
    """
    if not needle:
        return False
    span = len(needle)
    start = 0
    while True:
        found = haystack.find(needle, start)
        if found == -1:
            return False
        before = haystack[found - 1] if found > 0 else " "
        after = haystack[found + span] if found + span < len(haystack) else " "
        if not _is_word_char(before) and not _is_word_char(after):
            return True
        start = found + 1


def _is_word_char(character: str) -> bool:
    return character.isalnum() or character == "_"


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
    for phrase in sorted(intent.triggers, key=len, reverse=True):
        index = lowered.find(phrase.lower())
        if index != -1:
            return text[index + len(phrase):].strip(" ,:;-")
    return ""


def content_words(text: str) -> frozenset:
    """The words in `text` that carry meaning rather than grammar."""
    return frozenset(
        word
        for word in text.split()
        if len(word) >= MIN_CONTENT_WORD_LENGTH and word not in SUGGESTION_STOPWORDS
    )


def shares_meaning(utterance: str, phrase: str) -> bool:
    """Whether a suggestion would be recognisable as related to what was said.

    Both arguments must already be normalised. This is the check that lets the
    score band stay loose: "give me the status" and "give me a status report"
    share `status`, so 0.68 against a floor of 0.80 is a near miss worth
    raising, while "what about the render" and "what time is it" share only
    `what`, so 0.69 is a coincidence and gets nothing.
    """
    return bool(content_words(utterance) & content_words(phrase))


def may_be_suggested(intent: Optional[Intent], score: float) -> bool:
    """Whether a below floor candidate may be put to a person as a question.

    Three rules, and the first is absolute. An EFFECT intent is never suggested,
    at any score, however close it came: "fire up chrome" scored highest against
    "reboot the computer" at 5ff4348, and a prompt built on that top candidate
    would be asking a person to confirm rebooting their machine because they
    asked to open a browser. The other two keep a suggestion honest: it has to
    be near the intent's own floor, and it has to clear an absolute minimum, so
    a chance 0.44 collision is never dressed up as a near miss.
    """
    if intent is None:
        return False
    if intent.kind is Kind.EFFECT:
        return False
    if score < SUGGESTION_MIN_SCORE:
        return False
    return score >= intent.min_score - SUGGESTION_MARGIN


def _anchored_effect_is_a_command(
    intent: Intent, normalized: str, normalized_phrase: str
) -> bool:
    """Whether an utterance OPENING with an effect trigger is asking for it.

    WHY THIS EXISTS, measured rather than argued.

    An anchored prefix hit takes a flat score of 0.95 and never consults the
    intent's floor. That was true before 2026-09-10 and it was survivable while
    the parser knew 91 triggers. Widening to 299 widened exactly that undefended
    lane, and an adversary measured the result: of 299 triggers followed by
    neutral prose, 197 routed, 49 to an EFFECT and 24 to an approval gated one.
    "restart the machine learning job" raised a durable card to reboot the
    machine. "turn off the computer in the studio" raised one to shut it down.
    The gate held and nothing executed, but a stream of cards nobody asked for is
    how a gate stops being read.

    The floors cannot fix it: they are never consulted on this path, and making
    an anchored effect clear its floor was measured too and breaks real commands
    ("search for the grid spec" scores far below search_web's 0.78 once the query
    dilutes it). The discriminator is not confidence, it is whether the REMAINDER
    IS EXPLAINED.

      * An effect intent with no payload has nowhere to put a remainder. A real
        request is the trigger and nothing else: "restart the computer" IS the
        whole utterance. Anything after it is prose that happens to open with a
        verb this parser knows. Measured: this alone closes 8 of 10 leaks and
        breaks 0 of 18 real commands.
      * An effect intent WITH a payload has somewhere to put it, and the bound is
        the intent's own business, which is why it is declared per intent. With
        open_app's two word bound the same corpus reads 0 leaks of 10 and 0 broken
        of 18.

    READ and CAPTURE intents are not consulted here at all. They raise no card
    and run nothing, so a false positive there costs a wrong answer rather than a
    ruling, and the existing floors and the incidental rules already cover them.
    """
    if intent.kind is not Kind.EFFECT:
        return True
    remainder = normalized[len(normalized_phrase):].split()
    if not remainder:
        return True
    if not intent.takes_payload:
        return False
    if intent.max_payload_words is None:
        return True
    return len(remainder) <= intent.max_payload_words


def parse(text: str, intents: Optional[Sequence[Intent]] = None) -> ParsedCommand:
    """Route one utterance to at most one intent.

    Order is exact, then prefix, then fuzzy. The first two are deterministic and
    carry a payload cleanly; fuzzy exists for misheard speech and is held to each
    intent's own floor. Nothing below a floor is ever routed; at most it comes
    back as a suggestion for a person to answer.
    """
    pool = tuple(intents) if intents is not None else ALL_INTENTS
    original = strip_wake_word(text)
    normalized = normalize(original)

    # A wake word can sit behind politeness, as in "hey Devon, brief me", where
    # the first strip found "hey" at the front and gave up. Normalising has now
    # removed the politeness, so try once more on what is left.
    without_wake = strip_wake_word(normalized)
    if without_wake != normalized:
        normalized = normalize(without_wake)

    if not normalized:
        return ParsedCommand(text=text, reason="empty after wake word removal")

    for intent in pool:
        for phrase in intent.triggers:
            if normalized == normalize(phrase):
                return ParsedCommand(
                    intent=intent,
                    payload=_extract_payload(original, intent) if intent.takes_payload else "",
                    score=1.0,
                    method=Method.EXACT,
                    text=original,
                    reason=f"exact phrase '{phrase}'",
                )

    # Two pools, because where a phrase sits in the sentence is evidence. A
    # phrase the speaker opened with is what they asked for; the same phrase
    # buried mid sentence is usually them talking about it.
    #
    # An incidental hit may never claim an EFFECT intent, whatever it scores.
    # Politeness is stripped before this runs, so every real request for an
    # effect ("can you search for the grid spec", "I want you to look up the
    # quota") arrives anchored at the front anyway. What remains mid sentence is
    # prose: at 5ff4348 "the search for a new editor is on" opened a browser
    # search, "the launch went well on Friday" raised an approval card to launch
    # a program, and "her message was pretty blunt" raised one to send a message.
    anchored: List[Tuple[Intent, str, str]] = []
    incidental: List[Tuple[Intent, str, str]] = []
    for intent in pool:
        for phrase in intent.triggers:
            normalized_phrase = normalize(phrase)
            if not normalized_phrase:
                continue
            if normalized.startswith(normalized_phrase + " "):
                if _anchored_effect_is_a_command(intent, normalized, normalized_phrase):
                    anchored.append((intent, phrase, normalized_phrase))
            elif (
                intent.takes_payload
                and intent.kind is not Kind.EFFECT
                and len(normalized_phrase.split()) >= MIN_WORDS_FOR_MID_UTTERANCE_MATCH
                and _contains_whole_phrase(normalized, normalized_phrase)
            ):
                incidental.append((intent, phrase, normalized_phrase))

    prefix_hits = anchored or incidental
    if prefix_hits:
        # Longest matched phrase wins within a pool: "start a project called"
        # beats "new project".
        intent, phrase, _ = max(prefix_hits, key=lambda hit: len(hit[2]))
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
    # The best candidate that would be legal to suggest, tracked alongside the
    # best overall. They differ when an effect intent scored highest, which is
    # the case the suggestion rules exist for, and when the top candidate shares
    # no word with what was actually said.
    suggestible_intent: Optional[Intent] = None
    suggestible_score = 0.0
    for intent in pool:
        for phrase in intent.triggers:
            normalized_phrase = normalize(phrase)
            score = _token_sort_ratio(normalized, normalized_phrase)
            if score > best_score:
                best_score, best_intent, best_phrase = score, intent, phrase
            if (
                intent.kind is not Kind.EFFECT
                and score > suggestible_score
                and shares_meaning(normalized, normalized_phrase)
            ):
                suggestible_score, suggestible_intent = score, intent

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

    suggestion = suggestible_intent if may_be_suggested(suggestible_intent, suggestible_score) else None

    if best_intent is None:
        reason = "no candidate"
    elif best_intent.kind is Kind.EFFECT:
        # Deliberately does not name the phrase. This string reaches an API
        # caller through DevonResponse.reason, and naming a destructive intent
        # here would put it in front of a person who asked for something else.
        reason = (
            f"best candidate was an effect intent at {best_score:.2f}, below its floor "
            f"of {best_intent.min_score}. Declining rather than guessing, and an "
            "effect is never offered as a suggestion."
        )
    else:
        reason = (
            f"best candidate was '{best_phrase}' at {best_score:.2f}, below its floor "
            f"of {best_intent.min_score}. Declining rather than guessing."
        )

    return ParsedCommand(
        text=original,
        score=round(best_score, 3),
        reason=reason,
        suggestion=suggestion,
        suggestion_score=round(suggestible_score, 3) if suggestion else 0.0,
    )


def effect_intents() -> List[Intent]:
    """Every intent that changes state. Useful for auditing the surface."""
    return [i for i in ALL_INTENTS if i.kind is Kind.EFFECT]


def approval_gated_intents() -> List[Intent]:
    """Every intent that cannot run without a human ruling."""
    return [i for i in ALL_INTENTS if i.requires_approval]


def all_triggers() -> List[Tuple[str, str]]:
    """Every routable string with the intent it routes to. For auditing."""
    return [(trigger, intent.name) for intent in ALL_INTENTS for trigger in intent.triggers]
