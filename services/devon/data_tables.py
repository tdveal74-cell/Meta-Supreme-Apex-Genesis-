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

__all__ = ["containment_collisions", "describe_collisions"]


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
