"""Name collisions between n8n Data Tables, caught before they bite.

WHY THIS EXISTS

On 2026-09-15 at 23:38Z a session created two Airtable mirror tables in the VPS
n8n project, ``at_tqo_content`` and ``at_tqo_content_primitives``. Both contain
the name of an existing table, ``tqo_content``, inside their own. n8n's Data
Table resource locator in NAME mode stopped reaching the real table from that
minute.

Nothing announced it. Counted from the estate afterwards: 73 Data Table nodes
across 106 workflows resolve a table by name, 31 of them inside the active TQO
FINAL V5. Exactly one threw, because it alone filtered on a column the wrong
table lacks. The other 72 returned zero rows and carried on, so for four and a
half hours the TQO half of the pipeline was not failing, it was finding no work
and saying nothing. The loud failure was hiding the silent one that mattered.

Tee ruled on 2026-09-16 to rename the mirrors rather than edit the workflow: one
rename each fixes all 73 nodes, while editing V5 means 31 changes inside 240
nodes. That closed the incident and left the hazard, because the next table
anyone creates can reopen it exactly the same way.

WHAT THIS DOES ABOUT IT

The hazard is a property of the NAME SET, not of any workflow, so it is checkable
in one place for all 73 nodes at once. ``containment_collisions`` returns every
ordered pair where one table's name appears inside another's. An empty result is
the safe state. ``scripts/n8n_table_collision_check.py`` runs it against a live
project and exits non-zero when it is not empty.

It is deliberately CONTAINMENT and not equality. n8n rejects duplicate names
itself, so equality never reaches production; containment is the case it allows
and the case that broke the lane.

This module is pure: it takes names and returns pairs. It reads nothing, writes
nothing and calls nothing, which is what keeps ``services/devon`` effect free.
"""

from __future__ import annotations

from typing import Iterable

__all__ = [
    "containment_collisions",
    "describe_collisions",
    "name_mode_locators",
    "describe_name_mode",
]


def containment_collisions(names: Iterable[str]) -> list[tuple[str, str]]:
    """Return every ``(inner, outer)`` pair where ``inner`` sits inside ``outer``.

    ``inner`` is the table a NAME mode locator can no longer reliably reach once
    ``outer`` exists. Pairs come back sorted so two runs over the same estate
    produce the same report, and a name never collides with itself.

    Blank and whitespace-only names are ignored rather than reported: an empty
    string is contained in everything, which would drown the real finding.
    """
    cleaned = sorted({name.strip() for name in names if name and name.strip()})
    return [
        (inner, outer)
        for inner in cleaned
        for outer in cleaned
        if inner != outer and inner in outer
    ]


def describe_collisions(collisions: Iterable[tuple[str, str]]) -> str:
    """One line per pair, naming which table becomes unreachable and why.

    The wording says what a reader has to do next. "Collision" alone sent one
    session looking for a duplicate name, which is not what this is.
    """
    lines = [
        f"{inner!r} is contained in {outer!r}: a NAME mode locator for "
        f"{inner!r} can resolve to {outer!r} and return the wrong rows, or none"
        for inner, outer in collisions
    ]
    return "\n".join(lines)


# ---------------------------------------------------------------------------
# Counting the exposure itself, rather than the hazard that triggers it
# ---------------------------------------------------------------------------
#
# ``containment_collisions`` answers "is a colliding name present right now".
# This answers the prior question: "how many locators could a colliding name
# reach at all". The two are different jobs and only the second one shrinks
# permanently, because a locator resolved by id can never be captured.
#
# Tee ruled on 2026-09-16 that the conversion arc must carry a check counting
# name mode nodes FROM THE ESTATE, so the number cannot drift the way it did
# twice before, eleven then thirteen then fifteen, and so a new name mode node
# cannot be added quietly. This is that check.


def name_mode_locators(workflows: Iterable[dict]) -> list[dict]:
    """Every Data Table locator still resolving a table by NAME.

    Takes exported workflow dicts and returns one record per locator, carrying
    the workflow name, whether that workflow is ACTIVE, and the node name.
    Sorted so two runs over the same estate produce the same report.

    Only ``mode == "name"`` counts. ``list`` mode stores an id and resolves like
    one; a locator with no mode at all belongs to an operation that names no
    table, such as creating one.
    """
    found: list[dict] = []
    for workflow in workflows:
        if not isinstance(workflow, dict):
            continue
        for node in workflow.get("nodes") or []:
            if node.get("type") != "n8n-nodes-base.dataTable":
                continue
            locator = (node.get("parameters") or {}).get("dataTableId")
            if not isinstance(locator, dict) or locator.get("mode") != "name":
                continue
            found.append(
                {
                    "workflow": workflow.get("name") or workflow.get("id") or "unnamed",
                    "active": bool(workflow.get("active")),
                    "node": node.get("name") or "unnamed",
                    "value": locator.get("value"),
                }
            )
    return sorted(found, key=lambda r: (not r["active"], r["workflow"], r["node"]))


def describe_name_mode(locators: Iterable[dict]) -> str:
    """A report that leads with the ones that can bite today.

    An ACTIVE workflow on name mode is live exposure. An inactive one is a
    loaded gun rather than a fired one, so it is reported separately instead of
    being counted in the same number, which is how "73 nodes" once read as
    urgent when most of it was not.
    """
    rows = list(locators)
    live = [r for r in rows if r["active"]]
    idle = [r for r in rows if not r["active"]]

    lines: list[str] = []
    if live:
        lines.append(f"{len(live)} locator(s) resolve by NAME in ACTIVE workflows:")
        lines += [f"  {r['workflow']} :: {r['node']}" for r in live]
    else:
        lines.append("No ACTIVE workflow resolves a Data Table by name.")

    if idle:
        per: dict[str, int] = {}
        for record in idle:
            per[record["workflow"]] = per.get(record["workflow"], 0) + 1
        lines.append(f"{len(idle)} more sit in inactive workflows:")
        lines += [
            f"  {count:3d}  {name}"
            for name, count in sorted(per.items(), key=lambda kv: (-kv[1], kv[0]))
        ]
    return "\n".join(lines)
