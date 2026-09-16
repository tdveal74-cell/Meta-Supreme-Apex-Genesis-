#!/usr/bin/env python3
"""Fail when any n8n Data Table name is contained in another table's name.

Run it before and after creating a Data Table in the VPS project. It reads the
name set, not the workflows, because the hazard belongs to the name set: one
colliding name silently redirects every NAME mode locator that names the shorter
table, wherever it lives. On 2026-09-15 that was 73 nodes across 106 workflows,
and 72 of them failed by returning zero rows rather than by throwing.

    # from a session that has the n8n MCP, save the search_data_tables result:
    python3 scripts/n8n_table_collision_check.py tables.json

    # or pipe any JSON carrying the same shape, or a bare list of names:
    echo '["tqo_content", "at_tqo_content"]' | python3 scripts/n8n_table_collision_check.py

Accepts the MCP response verbatim (``{"data": [{"name": ...}]}``), a bare list of
objects, or a bare list of strings, so nothing has to be reshaped by hand at the
moment somebody is trying to find out whether they just broke production.

Exit 0 means the hazard set is empty. Exit 1 names every pair. Exit 2 means the
input could not be read as names at all, which is deliberately NOT exit 0: a
check that cannot see the estate must never report it safe.
"""

from __future__ import annotations

import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from services.devon.data_tables import containment_collisions, describe_collisions


def names_from(payload: object) -> list[str]:
    """Pull table names out of whichever of the three shapes arrived."""
    if isinstance(payload, dict):
        payload = payload.get("data", [])
    if not isinstance(payload, list):
        raise ValueError(f"expected a list of tables, got {type(payload).__name__}")
    names: list[str] = []
    for entry in payload:
        if isinstance(entry, str):
            names.append(entry)
        elif isinstance(entry, dict) and isinstance(entry.get("name"), str):
            names.append(entry["name"])
        else:
            raise ValueError(f"table entry carries no readable name: {entry!r:.120}")
    if not names:
        raise ValueError("no table names in the input; refusing to report an empty estate safe")
    return names


def main(argv: list[str]) -> int:
    try:
        raw = pathlib.Path(argv[1]).read_text() if len(argv) > 1 else sys.stdin.read()
        names = names_from(json.loads(raw))
    except (OSError, ValueError, json.JSONDecodeError) as error:
        # A mistyped path is an unreadable estate, not a clean one and not a
        # collision either. Without OSError here it fell out as an uncaught
        # exception, which Python exits 1 on, and 1 is the alarm code: the
        # report would have named a fault that was never looked for.
        print(f"could not read table names: {error}", file=sys.stderr)
        return 2

    collisions = containment_collisions(names)
    if not collisions:
        print(f"{len(names)} table names, no containment collisions")
        return 0

    print(f"{len(names)} table names, {len(collisions)} containment collision(s):", file=sys.stderr)
    print(describe_collisions(collisions), file=sys.stderr)
    print(
        "\nRename the LONGER table so it does not carry the shorter one's name, "
        "which is what Tee ruled on 2026-09-16: one rename fixes every node at "
        "once, while editing the workflows means dozens of changes.",
        file=sys.stderr,
    )
    return 1


if __name__ == "__main__":
    raise SystemExit(main(sys.argv))
