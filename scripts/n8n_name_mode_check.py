#!/usr/bin/env python3
"""Fail when any ACTIVE n8n workflow still resolves a Data Table by name.

THE OTHER HALF OF THE COLLISION CHECK

``n8n_table_collision_check.py`` asks whether a colliding NAME exists right now.
This asks the prior question: how many locators a colliding name could reach at
all. Only this number shrinks permanently, because a locator resolved by id
cannot be captured by any name.

Tee ruled the conversion to id on 2026-09-16 and ruled that the arc carry a
check counting name mode nodes FROM THE ESTATE, so the count cannot drift the
way it did twice before and so a new name mode node cannot be added quietly.

    scripts/n8n_migrate.py export /tmp/estate      # needs N8N_SOURCE_URL/KEY
    python3 scripts/n8n_name_mode_check.py /tmp/estate

Takes a directory of exported workflow JSON, a single workflow file, or the
payload on stdin.

Exit 0 means no ACTIVE workflow resolves a table by name; inactive ones are
still reported, because an inactive workflow is a loaded gun rather than a
fired one and activating it reintroduces the hazard in full. Exit 1 names every
active one. Exit 2 means the input could not be read, which is deliberately NOT
exit 0: a check that cannot see the estate must never report it safe. That
third answer is the whole reason the original incident stayed quiet for four
and a half hours.
"""

from __future__ import annotations

import argparse
import json
import pathlib
import sys

sys.path.insert(0, str(pathlib.Path(__file__).resolve().parent.parent))

from services.devon.data_tables import describe_name_mode, name_mode_locators


def workflows_from(source: str | None) -> list[dict]:
    """Every workflow dict in a directory, a file, or stdin."""
    if source is None:
        return _as_list(json.load(sys.stdin))

    path = pathlib.Path(source)
    if path.is_dir():
        found: list[dict] = []
        for child in sorted(path.glob("*.json")):
            try:
                found.extend(_as_list(json.loads(child.read_text())))
            except (json.JSONDecodeError, OSError) as exc:
                raise ValueError(f"{child}: {exc}") from exc
        if not found:
            raise ValueError(f"{path} holds no workflow JSON")
        return found

    return _as_list(json.loads(path.read_text()))


def _as_list(payload: object) -> list[dict]:
    if isinstance(payload, dict):
        if "nodes" in payload:
            return [payload]
        payload = payload.get("data", [])
    if not isinstance(payload, list):
        raise ValueError("expected a workflow object, or a list of them")
    return [item for item in payload if isinstance(item, dict)]


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "source",
        nargs="?",
        help="directory of exported workflows, one workflow file, or omit for stdin",
    )
    args = parser.parse_args()

    try:
        workflows = workflows_from(args.source)
    except (OSError, ValueError, json.JSONDecodeError) as exc:
        print(f"could not read workflows: {exc}", file=sys.stderr)
        print("NOT reporting the estate clean: this check could not see it.", file=sys.stderr)
        return 2

    # The export writes one file per workflow AND an index carrying all of
    # them, so a directory read sees each workflow twice. Deduplicate by id
    # before counting: a check written to stop a count drifting must not be
    # the thing reporting 224 of 112.
    seen: set[str] = set()
    unique: list[dict] = []
    for workflow in workflows:
        key = str(workflow.get("id") or id(workflow))
        if key in seen:
            continue
        seen.add(key)
        unique.append(workflow)
    workflows = unique

    locators = name_mode_locators(workflows)
    print(f"{len(workflows)} workflow(s) read")
    print(describe_name_mode(locators))

    live = [record for record in locators if record["active"]]
    if live:
        print(
            f"\n{len(live)} ACTIVE name mode locator(s). Convert them with "
            "scripts/n8n_table_id_conversion.py.",
            file=sys.stderr,
        )
        return 1
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
