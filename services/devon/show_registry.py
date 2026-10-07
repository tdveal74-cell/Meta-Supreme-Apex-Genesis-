"""The show registry: one record per show, lifted from the live TQO FINAL V5.

Ruled by Tee on 2026-10-06, as step one of splitting that workflow into one
small workflow per stage. The stages will couple through the content ledger
and this registry, so a new show becomes a record here rather than a new
branch in the Code nodes that V5_SHOW_BRANCHES counts.

WHERE THE VALUES COME FROM

Five Code nodes in the workflow each return a per show object selected on
`$json.nco === true`: `Show Context: Script`, `Show Context: Promote`,
`Show Context: Render`, `Show Context: Publish` and `Show Context: Brief`.
`Series Addendum` carries the series registries and their aliases. Every value
below was copied from the published version named in SOURCE, read through the
export this repository keeps under `n8n/tqo-v5/exports/`, and
`test_devon_show_registry.py` traces each value back into the node that
carries it, keyed on the node's own field name and inside the branch that
builds this show's object, so a live edit that is not carried here turns the
build red, and so a value borrowed from the other show's branch does not pass.

WHAT THE LIFT FOUND

Four of the five nodes carry a tagline, and they disagreed on it; `Show
Context: Brief` carries none. `Show Context: Script`
gave NCO Forge the tagline "Leaders aren't born. They're forged." under a
comment citing the Aug 2026 audit, `Show Context: Render` carried the same
line, and `Show Context: Promote` and `Show Context: Publish` still carried
"Military Mindset. Civilian Impact." Nothing downstream read `tagline` off
either stale node (the only consumer is `Build Script Prompt`, which reads
`Show Context: Script`), so the blast radius was zero. Tee ruled the two
nodes fixed on 2026-10-06; the one line edits were published as version
3befd7a5 and read back, and the exports were regenerated from it, which is
why KNOWN_NODE_DRIFT is empty. The map stays: the test pins its keys, so a
new entry is a visible test edit rather than a data edit, and it can only
shrink.

WHAT IS NOT HERE

The prompts. `Build Script Prompt` branches on `ctx.show === 'NCO'` and sixteen
Code nodes carry `isNCO`, `Series Addendum` and `Build QC Prompt` among them;
V5_SHOW_BRANCHES counts every spelling from the export. A third show
registered here would therefore be written with TQO's prompt until the canon
blocks move behind the blind comparison `tqo_canon.py` reserves for Tee. This
module is the routing, limits, voice, publish and brief data, and the series
map. `voiceNote` from the Render node is the one per show value left out: it
is a comment string with no consumer. Nothing in this module performs a
network call or an effect.
"""

from __future__ import annotations

import json
import pathlib
import re
from dataclasses import asdict, dataclass
from typing import Dict, Mapping, Optional, Tuple

SOURCE = {
    "upstream": (
        "n8n nodes 'Show Context: Script', 'Show Context: Promote', "
        "'Show Context: Render', 'Show Context: Publish', 'Show Context: Brief' "
        "and 'Series Addendum' in TQO FINAL V5"
    ),
    "workflow_id": "qEkGOUsNyVaRAmm6",
    "version_id": "54e8154d-56df-43a5-9fcb-f0b906c47288",
    "export": "n8n/tqo-v5/exports/qEkGOUsNyVaRAmm6_active.json",
    "read": "2026-10-07",
}

#: The export this registry is traced against, resolved from the repository
#: checkout. Regenerate it with scripts/tqo_v5_export.py, never by hand. The
#: byte identical copy under deploy/soul cannot see it, and nothing there calls
#: export_nodes(); the read is for the test, not for the service.
EXPORT = pathlib.Path(__file__).resolve().parents[2] / "n8n" / "tqo-v5" / "exports" / "qEkGOUsNyVaRAmm6_active.json"

#: How many Code nodes in the export still branch on the show, in any of the
#: spellings below. Counted by the test from the export; do not edit by hand.
#: It went from 25 to 28 on 2026-10-07 with 61d4aeeb, when Sources Rule,
#: Doctor Sources and Sources Gate arrived TQO only, and to 26 with d7f4d56f the
#: same day, when NCO was ruled to the same standard and those three stopped
#: branching, while Token Budget: Script began to, for the TQO close line.
V5_SHOW_BRANCHES = 26
SHOW_BRANCH_SPELLINGS: Tuple[str, ...] = (
    r"\bisNCO\b",
    r"\$json\.nco\b",
    r"ctx\.show\s*===\s*['\"]NCO['\"]",
    r"===\s*['\"]NCO['\"]",
)

#: Tee's Professional Voice Clone. The Render node's own comment records it as
#: trained 9 Aug 2026 on a purpose recorded read; that comment is the only
#: provenance in the tree. Both shows narrate in it: voice and identity owned,
#: never rented.
TEE_CLONE = "ypnKDQtIhp4N3yn4UnqO"


@dataclass(frozen=True)
class VoiceLane:
    """What `Show Context: Render` hands the narration lane.

    `provider_eleven` and `provider_speechify` are the two candidate narrator
    strings; `Mark Ready + Save URL` picks one from the run's own execution
    record, so the row names who actually spoke. Neither is a prediction.
    """

    voice_id: str
    voice_ready: bool
    eleven_model: str
    speechify_voice_id: str
    speechify_model: str
    provider_eleven: str
    provider_speechify: str
    stale_claim_hours: int
    settings: Mapping[str, float]


@dataclass(frozen=True)
class Brief:
    """What `Show Context: Brief` hands the newsletter lane on Hostinger Reach."""

    name: str
    from_name: str
    reach_profile_uuid: str
    mailerlite_group_id: str
    voice: str
    move_label: str
    sections: Tuple[str, ...]
    section_notes: str
    audience: str


@dataclass(frozen=True)
class Series:
    """One canonical series inside a show, as `Series Addendum` registers it."""

    key: str
    canon: str
    role: str
    tier: str
    mandate: str


@dataclass(frozen=True)
class Show:
    """One show. The key is the registry row id; `show` is the lane's own label."""

    key: str
    show: str
    channel: str
    table_name: str
    table_id: str
    brand: str
    kicker: str
    tagline: str
    tagline2: str
    positioning: str
    thesis: str
    required_tags: Tuple[str, ...]
    script_limit: int
    promote_limit: int
    package_limit: int
    youtube_ready: bool
    voice: VoiceLane
    brief: Brief
    series: Tuple[Series, ...]
    aliases: Mapping[str, Tuple[str, Optional[str]]]

    def resolve_series(self, name: str) -> Optional[Tuple[Series, Optional[str]]]:
        """Resolve a row's Show value the way `Series Addendum` does.

        Lower cased and trimmed, one alias hop at most, and None when nothing
        matches. The node then falls back to prose that says the show is not
        in the registry; callers here get None and decide for themselves.
        """
        key = str(name or "").strip().lower()
        segment: Optional[str] = None
        if key in self.aliases:
            key, segment = self.aliases[key]
        for entry in self.series:
            if entry.key == key:
                return entry, segment
        return None

    def row(self) -> Dict[str, object]:
        """The flat record for the `show_registry` data table step two creates.

        Every value is a string, a number or a boolean, which with date are the
        four column types an n8n data table takes, so the lists and the voice
        settings travel as JSON strings and a stage workflow parses them.
        """
        record = asdict(self)
        record.pop("series")
        record.pop("aliases")
        voice = record.pop("voice")
        brief = record.pop("brief")
        for name, value in voice.items():
            record[name if name.startswith("voice_") else f"voice_{name}"] = value
        for name, value in brief.items():
            record[f"brief_{name}"] = value
        record["required_tags"] = json.dumps(list(self.required_tags))
        record["brief_sections"] = json.dumps(list(self.brief.sections))
        record["voice_settings"] = json.dumps(dict(self.voice.settings))
        return record


VOICE = VoiceLane(
    voice_id=TEE_CLONE,
    voice_ready=True,
    eleven_model="eleven_multilingual_v2",
    speechify_voice_id="geffen_32",
    speechify_model="simba-3.2",
    provider_eleven="elevenlabs, Tee clone",
    provider_speechify="speechify geffen_32 STOPGAP VOICE, not for publish",
    stale_claim_hours=3,
    settings={
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.1,
        "use_speaker_boost": True,
        "speed": 0.99,
    },
)

#: One Reach profile serves both shows today, the uuid both Brief branches carry.
REACH_PROFILE = "af497848-65de-40f7-82ac-b0f4f162a141"

#: The two data tables on the n8n instance that carry registry_rows() and
#: series_rows(), created 2026-10-06 in project qbrcjkbIoorbwot6 and seeded by
#: scripts/show_registry_seed.py, which also reads them back against this module.
REGISTRY_TABLES: Dict[str, str] = {
    "show_registry": "xmNWLUm49QyZ4ysO",
    "show_series": "s1IxySUuphOVrOqU",
}

TQO = Show(
    key="tqo",
    show="TQO",
    channel="The Quiet Operator",
    table_name="tqo_content",
    table_id="2GtmrFcTNqVMbddh",
    brand="tqo",
    kicker="THE QUIET OPERATOR",
    tagline="AI Strategy for the Next Economy.",
    tagline2="Quiet Leverage. Real Results.",
    positioning="Leverage for the people the AI economy is quietly repricing.",
    thesis=(
        "The Quiet Operator is where professional judgment survives automation. "
        "Receipts, not predictions."
    ),
    required_tags=(),
    script_limit=2,
    promote_limit=1,
    package_limit=3,
    youtube_ready=True,
    voice=VOICE,
    brief=Brief(
        name="The Quiet Brief",
        from_name="The Quiet Operator",
        reach_profile_uuid=REACH_PROFILE,
        mailerlite_group_id="192288476556690941",
        voice=(
            "Premium and understated. No exclamation marks, no clickbait, no emojis, "
            "no in-todays-fast-paced-world. Every line earns its place."
        ),
        move_label="THIS WEEK'S QUIET MOVE",
        sections=("THE SHIFT", "THE EVIDENCE", "WHAT IT MEANS FOR YOU", "THIS WEEK'S QUIET MOVE"),
        section_notes=(
            "THE SHIFT is the specific change. THE EVIDENCE is what actually happened, "
            "with receipts and with the gaps named. WHAT IT MEANS FOR YOU is the "
            "transformation, not the topic. THE QUIET MOVE is one measurable action "
            "doable this week."
        ),
        audience=(
            "mid-career professionals 35-50 quietly building income and leverage "
            "before AI reaches their jobs"
        ),
    ),
    series=(
        Series(
            key="the ai shift",
            canon="THE AI SHIFT",
            role="evidence-led read on what actually changed",
            tier="OPERATOR I and II",
            mandate=(
                "What changed, who it reaches first, and what the receipts actually say. "
                "Never AI news, never prediction dressed as analysis. Name what is not "
                "yet known."
            ),
        ),
        Series(
            key="the quiet advantage",
            canon="THE QUIET ADVANTAGE",
            role="personal leverage playbook",
            tier="OPERATOR II and III",
            mandate=(
                "One measurable advantage per episode, built inside a working week. "
                "Method before the list: show how the decision was made, not just what "
                "was chosen."
            ),
        ),
        Series(
            key="i built it with ai",
            canon="I BUILT IT WITH AI",
            role="build log with honest failure",
            tier="OPERATOR III",
            mandate=(
                "A real build, on a real timeline, with what broke left in. The "
                "abandoned part of the build is the most valuable part of the episode. "
                "If nothing failed, the episode is not honest yet."
            ),
        ),
        Series(
            key="the operator brief",
            canon="THE OPERATOR BRIEF",
            role="recurring orientation",
            tier="all tiers",
            mandate=(
                "Orientation, not roundup. One thing worth acting on, why now, and what "
                "to do about it in fifteen minutes a day. Reject anything that is merely "
                "interesting."
            ),
        ),
    ),
    aliases={},
)

NCO = Show(
    key="nco",
    show="NCO",
    channel="NCO Forge",
    table_name="nco_content",
    table_id="DSH1tn4TZjzAEKxp",
    brand="nco",
    kicker="NCO FORGE",
    tagline="Leaders aren't born. They're forged.",
    tagline2="Built by Discipline. Living on Purpose.",
    positioning="Where doctrine ends and leadership begins.",
    thesis=(
        "NCO Forge is where military experience becomes leadership judgment. "
        "The situations nobody can teach you from a slide."
    ),
    required_tags=("NCO Forge",),
    script_limit=2,
    promote_limit=1,
    package_limit=3,
    # Flip only after the NCO Forge channel's own YouTube credential is attached
    # to 'Upload to YouTube (NCO Forge)'. Both upload nodes carry the same
    # credential today, 'YouTube account 1', and an n8n credential binds to a
    # node, not to a row.
    youtube_ready=False,
    voice=VOICE,
    brief=Brief(
        name="The Forge Report",
        from_name="NCO Forge",
        reach_profile_uuid=REACH_PROFILE,
        mailerlite_group_id="",
        voice=(
            "Direct, practical, respectful of service. No ego, no hype, no "
            "exclamation marks, no emojis. Doctrine, then reality, then judgment."
        ),
        move_label="THE FORGE RULE",
        sections=("THE SITUATION", "THE CALL", "THE LESSON", "THE FORGE RULE", "YOUR CALL"),
        section_notes=(
            "THE SITUATION is one leadership scenario in plain language. THE CALL is "
            "the decision that was actually made and the options that were live. THE "
            "LESSON is the analysis. THE FORGE RULE is one numbered, repeatable "
            "principle. YOUR CALL asks the reader what they would have done and "
            "invites a reply, because those replies become Hard Call and NCO "
            "Confessions episodes."
        ),
        audience="NCOs, junior leaders about to pin, and veterans leading in civilian organisations",
    ),
    series=(
        Series(
            key="the forge",
            canon="THE FORGE",
            role="flagship leadership story",
            tier="FORGE II and III",
            mandate=(
                "Cinematic storytelling. Not a tutorial, not a regulation summary, not "
                "commentary. One leadership situation carried end to end, with a "
                "decision inside it that cost something."
            ),
        ),
        Series(
            key="after action",
            canon="AFTER ACTION",
            role="decision breakdown",
            tier="FORGE III",
            mandate=(
                "Four beats, in order: what happened, what decision was made, why it "
                "worked or failed, what you would do differently. Then the rule."
            ),
        ),
        Series(
            key="hard call",
            canon="HARD CALL",
            role="interactive dilemma",
            tier="FORGE II",
            mandate=(
                "Give the viewer the scenario before you give them the answer. Let them "
                "decide. Then walk the consequences of each live option, including the "
                "one most leaders pick and regret."
            ),
        ),
        Series(
            key="nco school",
            canon="NCO SCHOOL",
            role="practical education and search",
            tier="FORGE I and II",
            mandate=(
                "Evergreen and procedural. Counselling, NCOER, the promotion board, the "
                "leader book, the first week as a team leader. Built to be found and to "
                "still be correct in three years, not to go viral."
            ),
        ),
        Series(
            key="nco confessions",
            canon="NCO CONFESSIONS",
            role="anonymous leadership experience",
            tier="FORGE III and IV",
            mandate=(
                "Human truth, never leadership preaching and never sensationalism. The "
                "admission has to be specific and uncomfortable. If it is tidy, it is "
                "engineered, and it does not belong on this show."
            ),
        ),
        Series(
            key="forge rules",
            canon="FORGE RULES",
            role="short-form principle",
            tier="all tiers",
            mandate=(
                "One principle, one minute, no preamble. Formats rotate: 60 Second "
                "Leadership, Forge Rule, NCO Mistake, What Would You Do, Never Do This, "
                "One Thing I Learned."
            ),
        ),
    ),
    # The node's own comment: old Airtable select values still resolve, one
    # hop, so no historical row is orphaned. A segment on the alias rides onto
    # the resolved series.
    aliases={
        "nco after action": ("after action", None),
        "the hard conversation": ("hard call", None),
        "before you pin": ("nco school", "Before You Pin"),
        "the standard": ("nco school", "The Standard"),
        "60-second forge": ("forge rules", None),
        "forge shorts": ("forge rules", None),
    },
)

SHOWS: Dict[str, Show] = {TQO.key: TQO, NCO.key: NCO}

#: Which registry fields each Show Context node carries, by the node's own
#: key names. The test traces every one of these into the branch of the node
#: that builds this show's object, keyed on the node's field name.
NODE_FIELDS: Dict[str, Dict[str, str]] = {
    "Show Context: Script": {
        "show": "show",
        "channel": "channel",
        "tableId": "table_name",
        "tableRef": "table_id",
        "brand": "brand",
        "kicker": "kicker",
        "tagline": "tagline",
        "positioning": "positioning",
        "tagline2": "tagline2",
        "thesis": "thesis",
        "requiredTags": "required_tags",
        "scriptLimit": "script_limit",
        "promoteLimit": "promote_limit",
        "packageLimit": "package_limit",
    },
    "Show Context: Promote": {
        "show": "show",
        "channel": "channel",
        "tableId": "table_name",
        "tableRef": "table_id",
        "brand": "brand",
        "kicker": "kicker",
        "tagline": "tagline",
        "tagline2": "tagline2",
        "requiredTags": "required_tags",
        "scriptLimit": "script_limit",
        "promoteLimit": "promote_limit",
    },
    "Show Context: Render": {
        "show": "show",
        "channel": "channel",
        "tableId": "table_name",
        "tableRef": "table_id",
        "brand": "brand",
        "kicker": "kicker",
        "tagline": "tagline",
        "positioning": "positioning",
        "tagline2": "tagline2",
        "requiredTags": "required_tags",
        "scriptLimit": "script_limit",
        "promoteLimit": "promote_limit",
        "staleClaimHours": "voice.stale_claim_hours",
    },
    "Show Context: Publish": {
        "show": "show",
        "channel": "channel",
        "tableId": "table_name",
        "tableRef": "table_id",
        "brand": "brand",
        "kicker": "kicker",
        "tagline": "tagline",
        "tagline2": "tagline2",
        "requiredTags": "required_tags",
        "scriptLimit": "script_limit",
        "promoteLimit": "promote_limit",
    },
    "Show Context: Brief": {
        "show": "show",
        "channel": "channel",
        "tableId": "table_name",
        "tableRef": "table_id",
        "briefName": "brief.name",
        "fromName": "brief.from_name",
        "reachProfileUuid": "brief.reach_profile_uuid",
        "mlGroupId": "brief.mailerlite_group_id",
        "voice": "brief.voice",
        "moveLabel": "brief.move_label",
        "sections": "brief.sections",
        "sectionNotes": "brief.section_notes",
        "audience": "brief.audience",
    },
}

#: Values a node still carries that this registry has moved past, keyed
#: (node name, show key, registry path). The lift found two, the NCO tagline on
#: Promote and Publish, and both were repaired and published as 3befd7a5 on
#: 2026-10-06. The test pins this map's keys and checks each entry in both
#: directions, so an entry can only be removed, and only once the node has
#: been fixed.
KNOWN_NODE_DRIFT: Dict[Tuple[str, str, str], str] = {}


def get_show(key: str) -> Show:
    return SHOWS[key]


def show_for_table(table_id: str) -> Optional[Show]:
    """The show whose content table carries this id, or None."""
    for entry in SHOWS.values():
        if entry.table_id == table_id:
            return entry
    return None


def field_value(entry: Show, path: str) -> object:
    """Read a dotted registry path such as `brief.name` off a Show."""
    value: object = entry
    for part in path.split("."):
        value = getattr(value, part)
    return value


def registry_rows() -> Tuple[Dict[str, object], ...]:
    """One flat record per show, for the `show_registry` data table."""
    return tuple(entry.row() for entry in SHOWS.values())


def series_rows() -> Tuple[Dict[str, object], ...]:
    """One record per canonical series and per alias, for `show_series`."""
    rows = []
    for entry in SHOWS.values():
        for position, series in enumerate(entry.series, start=1):
            rows.append(
                {
                    "show": entry.key,
                    "key": series.key,
                    "position": position,
                    "canon": series.canon,
                    "role": series.role,
                    "tier": series.tier,
                    "mandate": series.mandate,
                    "alias_of": "",
                    "segment": "",
                }
            )
        for alias, (target, segment) in entry.aliases.items():
            rows.append(
                {
                    "show": entry.key,
                    "key": alias,
                    "position": 0,
                    "canon": "",
                    "role": "",
                    "tier": "",
                    "mandate": "",
                    "alias_of": target,
                    "segment": segment or "",
                }
            )
    return tuple(rows)


def export_nodes() -> Dict[str, str]:
    """Node name to Code body, read from the export this module is traced against."""
    payload = json.loads(EXPORT.read_text(encoding="utf-8"))
    return {
        node["name"]: node["parameters"]["jsCode"]
        for node in payload["nodes"]
        if node.get("type") == "n8n-nodes-base.code"
    }


def js_pattern(value: object) -> str:
    """A regex matching this registry value as a Code node would write it.

    A string may be quoted either way, a list is its items in order, a bool is
    the bare keyword and an integer is its digits with nothing numeric after
    them. Floats are compared numerically by the caller, not matched here.
    """
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, int):
        return re.escape(str(value)) + r"(?![\d.])"
    if isinstance(value, (tuple, list)):
        if not value:
            return r"\[\s*\]"
        return r"\[\s*" + r"\s*,\s*".join(js_pattern(item) for item in value) + r"\s*\]"
    text = re.escape(str(value))
    return f"(?:'{text}'|\"{text}\")"


def keyed(js_key: str, value: object) -> str:
    """The regex for `js_key: <value>` as one field of a node's object."""
    return rf"(?<![\w$]){re.escape(js_key)}:\s*{js_pattern(value)}"


def show_segment(code: str, show_label: str) -> str:
    """The slice of a Show Context node that builds one show's object.

    Every Show Context node returns `nco ? {...} : {...}`, each object opening
    on its `show:` field, so the segment runs from this show's `show:` marker
    to the next show's marker or to the end of the node.
    """
    markers = {match.group(1): match.start() for match in re.finditer(r"\bshow:\s*'([A-Z]+)'", code)}
    if show_label not in markers:
        raise KeyError(f"no show: '{show_label}' object in this node")
    start = markers[show_label]
    later = [position for position in markers.values() if position > start]
    return code[start : min(later)] if later else code[start:]
