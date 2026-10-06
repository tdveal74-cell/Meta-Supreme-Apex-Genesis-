"""The show registry: one record per show, lifted from the live TQO FINAL V5.

Ruled by Tee on 2026-10-06, as step one of splitting that workflow into one
small workflow per stage. The stages will couple through the content ledger
and this registry, so a new show becomes a record here rather than a new
branch in fifteen Code nodes.

WHERE THE VALUES COME FROM

Five Code nodes in the workflow each return a per show object selected on
`$json.nco === true`: `Show Context: Script`, `Show Context: Promote`,
`Show Context: Render`, `Show Context: Publish` and `Show Context: Brief`.
`Series Addendum` carries the series registries and their aliases. Every value
below was copied from the published version named in SOURCE, read through the
export this repository keeps under `n8n/tqo-v5/exports/`, and
`test_devon_show_registry.py` traces each value back into the node that
carries it, so a live edit that is not carried here turns the build red.

WHAT THE LIFT FOUND

The five nodes disagree with each other on one value. `Show Context: Script`
and `Show Context: Render` give NCO Forge the tagline "Leaders aren't born.
They're forged." with a comment citing the Aug 2026 brand audit, while
`Show Context: Promote` and `Show Context: Publish` still carry "Military
Mindset. Civilian Impact." This registry carries the audited line and names
the two stale nodes in KNOWN_NODE_DRIFT, which the test lets shrink and never
grow. Editing those two nodes is a ruling for Tee, not a side effect of this
module.

WHAT IS NOT HERE

The prompts. `Build Script Prompt`, `Series Addendum`, `Build QC Prompt` and
seven more builders still branch on `isNCO` in their bodies, so a third show
registered here would be written with TQO's prompt until the canon blocks move
behind the blind comparison `tqo_canon.py` reserves for Tee. This module is the
routing, limits, voice, publish and brief data, and the series map. Nothing in
it performs a network call or an effect.
"""

from __future__ import annotations

import json
import pathlib
from dataclasses import asdict, dataclass
from typing import Dict, Mapping, Optional, Tuple

SOURCE = {
    "upstream": (
        "n8n nodes 'Show Context: Script', 'Show Context: Promote', "
        "'Show Context: Render', 'Show Context: Publish', 'Show Context: Brief' "
        "and 'Series Addendum' in TQO FINAL V5"
    ),
    "workflow_id": "qEkGOUsNyVaRAmm6",
    "version_id": "b99b38ab-83dc-4106-9c70-32987310cc88",
    "export": "n8n/tqo-v5/exports/qEkGOUsNyVaRAmm6_active.json",
    "read": "2026-10-06",
}

#: The export this registry is traced against. Regenerate it with
#: scripts/tqo_v5_export.py, never by hand.
EXPORT = pathlib.Path(__file__).resolve().parents[2] / "n8n" / "tqo-v5" / "exports" / "qEkGOUsNyVaRAmm6_active.json"

#: Tee's Professional Voice Clone, trained 9 Aug 2026 on a purpose recorded
#: read. Both shows narrate in it: voice and identity owned, never rented.
TEE_CLONE = "ypnKDQtIhp4N3yn4UnqO"


@dataclass(frozen=True)
class VoiceLane:
    """What `Show Context: Render` hands the narration lane."""

    voice_id: str
    voice_ready: bool
    eleven_model: str
    speechify_voice_id: str
    speechify_model: str
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
        """The flat, JSON serialisable record for the `show_registry` table."""
        record = asdict(self)
        record.pop("series")
        record.pop("aliases")
        voice = record.pop("voice")
        brief = record.pop("brief")
        record.update({f"voice_{k}": v for k, v in voice.items()})
        record.update({f"brief_{k}": v for k, v in brief.items()})
        record["required_tags"] = list(self.required_tags)
        record["brief_sections"] = list(self.brief.sections)
        record["voice_settings"] = dict(self.voice.settings)
        return record


VOICE = VoiceLane(
    voice_id=TEE_CLONE,
    voice_ready=True,
    eleven_model="eleven_multilingual_v2",
    speechify_voice_id="geffen_32",
    speechify_model="simba-3.2",
    stale_claim_hours=3,
    settings={
        "stability": 0.5,
        "similarity_boost": 0.75,
        "style": 0.1,
        "use_speaker_boost": True,
        "speed": 0.99,
    },
)

#: One Reach profile serves both shows today: tqohq.online, uuid below.
REACH_PROFILE = "af497848-65de-40f7-82ac-b0f4f162a141"

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
    # to 'Upload to YouTube (NCO Forge)'. Both upload nodes carry the TQO
    # credential today, and an n8n credential binds to a node, not to a row.
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
    # Old Airtable select values still resolve, one hop, so no historical row
    # is orphaned. A segment on the alias rides onto the resolved series.
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
#: key names. The test traces every one of these into the node's source.
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
        "sectionNotes": "brief.section_notes",
        "audience": "brief.audience",
    },
}

#: Values a node still carries that this registry has moved past. Found while
#: lifting; each is one node edit on Tee's ruling. The test fails if a listed
#: drift is gone from the node and still listed here, so the map only shrinks.
KNOWN_NODE_DRIFT: Dict[Tuple[str, str, str], str] = {
    ("Show Context: Promote", "nco", "tagline"): "Military Mindset. Civilian Impact.",
    ("Show Context: Publish", "nco", "tagline"): "Military Mindset. Civilian Impact.",
}


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


def js_literal(value: object) -> Tuple[str, ...]:
    """The forms a registry value takes inside a Code node, any of which traces."""
    if isinstance(value, bool):
        return ("true" if value else "false",)
    if isinstance(value, (int, float)):
        return (repr(value),)
    if isinstance(value, (tuple, list)):
        if not value:
            return ("[]",)
        inner = ", ".join(f"'{item}'" for item in value)
        return (f"[{inner}]",)
    text = str(value)
    return (f"'{text}'", f'"{text}"')
