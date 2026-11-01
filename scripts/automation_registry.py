"""Check the automation ownership registry against the live n8n instance.

`registry/automations.json` holds one row per ACTIVE workflow on the VPS n8n
instance: who owns it, which lane it belongs to, and the date a human last
read it end to end. This script reads the instance's own workflow list and
diffs the two, so the registry cannot quietly stop describing the estate.

    python3 scripts/automation_registry.py --check     # read the instance, diff, exit 1 on a finding
    python3 scripts/automation_registry.py --validate  # check the file's shape only, no network

Ruled by Tee 2026-10-31 on a card, "Build the registry", after a read of Nate
Herk's five step agent management framework found one gap in the estate: no
record of who owns each automation or when it was last reviewed. The dead SMTP
and Drive credentials of September ran for days because nothing was looking at
the lanes they fed.

IT ONLY READS. It makes GET requests to the n8n public API and never writes to
the instance or to the file. Settling a finding is a commit to the file, made
by a person, which is the ownership the registry exists to record.

WHAT TURNS IT RED, exit 1:
  - an active workflow with no row (an automation nobody has claimed)
  - a row whose workflow is gone or no longer active (a stale claim)
  - a row whose review is overdue: `reviewed` older than `review_every_days`,
    or the workflow's `updatedAt` later than the day it was reviewed, because a
    review of an earlier version is not a review of what runs now
  - a `reviewed` date after today, which would otherwise silence both alarms

WHAT IT REPORTS AND DOES NOT ALARM ON: rows with `reviewed: null`. The file was
seeded on 2026-10-31 with no review dates, because none had been recorded and
inventing one would be a false record. Alarming on all 68 would turn the job
red on day one and teach nothing, so the never reviewed backlog is counted on
every run instead and shrinks as reviews are recorded.

A MISSING KEY IS EXIT 2, which also turns the job red. A check that skipped
quietly when unconfigured would report green while reading nothing.

It needs `N8N_VPS_KEY`, the secret the two watchdogs and the registry check
already use, and reads `N8N_VPS_URL` with the same default.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, datetime, timezone
from typing import Any, Dict, List, Optional, Sequence, Tuple

REPO = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
REGISTRY_PATH = os.path.join(REPO, "registry", "automations.json")

#: Same instance and default as scripts/pulse_watchdog.py.
DEFAULT_BASE_URL = "https://n8n.editforge.online"
TIMEOUT = 30
#: 100 a page; 20 pages is 2,000 workflows. A listing that still has a cursor
#: after that refuses rather than diffs a partial estate (see fetch_workflows).
MAX_PAGES = 20

#: The fields a row must carry, and nothing else, so a typo such as `reveiwed`
#: fails the shape check instead of reading as a never reviewed row.
ROW_KEYS = ("id", "name", "lane", "owner", "reviewed")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")

OK = 0
FINDING = 1
CANNOT_CHECK = 2


def parse_iso(value: Any) -> Optional[datetime]:
    if not isinstance(value, str) or not value.strip():
        return None
    text = value.strip()
    if text.endswith(("Z", "z")):
        text = text[:-1] + "+00:00"
    try:
        parsed = datetime.fromisoformat(text)
    except ValueError:
        return None
    if parsed.tzinfo is None:
        parsed = parsed.replace(tzinfo=timezone.utc)
    return parsed.astimezone(timezone.utc)


def validate(doc: Any) -> List[str]:
    """Problems with the file's shape. An empty list means it is well formed."""
    problems: List[str] = []
    if not isinstance(doc, dict):
        return ["the registry is not a JSON object"]
    every = doc.get("review_every_days")
    if not isinstance(every, int) or isinstance(every, bool) or every < 1:
        problems.append("review_every_days must be a whole number of days, 1 or more")
    rows = doc.get("workflows")
    if not isinstance(rows, list):
        return problems + ["workflows must be a list"]
    seen: Dict[str, int] = {}
    for index, row in enumerate(rows):
        where = f"row {index}"
        if not isinstance(row, dict):
            problems.append(f"{where} is not an object")
            continue
        keys = set(row)
        if keys != set(ROW_KEYS):
            missing = sorted(set(ROW_KEYS) - keys)
            extra = sorted(keys - set(ROW_KEYS))
            problems.append(f"{where} has the wrong fields (missing {missing}, unexpected {extra})")
            continue
        for field in ("id", "name", "lane", "owner"):
            if not isinstance(row[field], str) or not row[field].strip():
                problems.append(f"{where} ({row.get('id')}) has an empty {field}")
        reviewed = row["reviewed"]
        if reviewed is not None:
            if not isinstance(reviewed, str) or not DATE_RE.match(reviewed):
                problems.append(f"{where} ({row['id']}) reviewed must be YYYY-MM-DD or null")
            else:
                try:
                    date.fromisoformat(reviewed)
                except ValueError:
                    problems.append(f"{where} ({row['id']}) reviewed is not a real date: {reviewed}")
        if isinstance(row["id"], str):
            if row["id"] in seen:
                problems.append(f"{where} repeats id {row['id']} from row {seen[row['id']]}")
            seen.setdefault(row["id"], index)
    return problems


def diff(
    doc: Dict[str, Any], live: Sequence[Dict[str, Any]], today: date
) -> Tuple[List[str], List[str]]:
    """(findings that turn the job red, notes that do not).

    `live` is every workflow the instance listed, active or not, so a row whose
    workflow was deactivated can be told apart from one that was deleted.
    """
    every = int(doc["review_every_days"])
    rows = {row["id"]: row for row in doc["workflows"]}
    by_id = {str(w.get("id")): w for w in live if isinstance(w, dict) and w.get("id")}
    findings: List[str] = []
    notes: List[str] = []

    for wid, workflow in sorted(by_id.items(), key=lambda kv: str(kv[1].get("name"))):
        if workflow.get("active") is True and wid not in rows:
            findings.append(f"UNOWNED: active workflow {wid} \"{workflow.get('name')}\" has no row")

    never = 0
    for wid, row in sorted(rows.items(), key=lambda kv: kv[1]["name"]):
        workflow = by_id.get(wid)
        label = f"{wid} \"{row['name']}\""
        if workflow is None:
            findings.append(f"STALE: {label} is not on the instance")
            continue
        if workflow.get("active") is not True:
            findings.append(f"STALE: {label} is on the instance but not active")
            continue
        live_name = workflow.get("name")
        if live_name != row["name"]:
            notes.append(f"RENAMED: {wid} is now \"{live_name}\", the row says \"{row['name']}\"")
        if row["reviewed"] is None:
            never += 1
            continue
        reviewed = date.fromisoformat(row["reviewed"])
        if reviewed > today:
            findings.append(
                f"BAD REVIEW DATE: {label} says it was reviewed on {row['reviewed']}, after today "
                f"{today.isoformat()}, which would silence its review alarms until then"
            )
            continue
        age = (today - reviewed).days
        if age > every:
            findings.append(
                f"REVIEW DUE: {label} owner {row['owner']}, last reviewed {row['reviewed']}, "
                f"{age} days ago against a {every} day period"
            )
            continue
        updated = parse_iso(workflow.get("updatedAt"))
        if updated is not None and updated.date() > reviewed:
            findings.append(
                f"REVIEW DUE: {label} owner {row['owner']}, changed {updated.date().isoformat()} "
                f"after its review on {row['reviewed']}"
            )
    if never:
        notes.append(f"NEVER REVIEWED: {never} of {len(rows)} rows carry no review date")
    return findings, notes


def fetch_workflows(base: str, key: str) -> List[Dict[str, Any]]:
    """Every workflow the instance lists, following the cursor.

    Refuses rather than returns a partial list, because a diff against half the
    estate would call the other half stale.
    """
    out: List[Dict[str, Any]] = []
    cursor = ""
    for _ in range(MAX_PAGES):
        path = "/api/v1/workflows?limit=100"
        if cursor:
            path += "&cursor=" + urllib.parse.quote(cursor)
        request = urllib.request.Request(base.rstrip("/") + path)
        request.add_header("X-N8N-API-KEY", key)
        request.add_header("Accept", "application/json")
        with urllib.request.urlopen(request, timeout=TIMEOUT) as response:
            page = json.load(response)
        if not isinstance(page, dict) or not isinstance(page.get("data"), list):
            raise ValueError("the workflow listing was not {data: [...]}")
        for w in page["data"]:
            if isinstance(w, dict):
                out.append(
                    {"id": w.get("id"), "name": w.get("name"), "active": w.get("active"),
                     "updatedAt": w.get("updatedAt")}
                )
        cursor = str(page.get("nextCursor") or "")
        if not cursor:
            return out
    raise ValueError(f"the workflow listing still had a cursor after {MAX_PAGES} pages")


def load(path: str = REGISTRY_PATH) -> Any:
    with open(path, encoding="utf-8") as handle:
        return json.load(handle)


def main(argv: Optional[List[str]] = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    mode = parser.add_mutually_exclusive_group(required=True)
    mode.add_argument("--check", action="store_true")
    mode.add_argument("--validate", action="store_true")
    parser.add_argument("--registry", default=REGISTRY_PATH)
    args = parser.parse_args(argv)

    try:
        doc = load(args.registry)
    except (OSError, ValueError) as error:
        print(f"CANNOT CHECK: could not read {args.registry}: {error}")
        return CANNOT_CHECK
    problems = validate(doc)
    if problems:
        print("INVALID REGISTRY:")
        for problem in problems:
            print(f"  {problem}")
        return FINDING
    if args.validate:
        print(f"OK: {len(doc['workflows'])} rows, well formed")
        return OK

    key = os.environ.get("N8N_VPS_KEY", "")
    if not key:
        print("CANNOT CHECK: N8N_VPS_KEY is not set, so nothing was read")
        return CANNOT_CHECK
    base = os.environ.get("N8N_VPS_URL", "").strip() or DEFAULT_BASE_URL
    try:
        live = fetch_workflows(base, key)
    except (urllib.error.URLError, OSError, ValueError) as error:
        print(f"CANNOT CHECK: reading {base} failed: {type(error).__name__}: {error}")
        return CANNOT_CHECK

    findings, notes = diff(doc, live, datetime.now(timezone.utc).date())
    active = sum(1 for w in live if w.get("active") is True)
    print(f"Read {len(live)} workflows, {active} active, against {len(doc['workflows'])} rows.")
    for note in notes:
        print(f"  {note}")
    if findings:
        print(f"FINDINGS: {len(findings)}")
        for finding in findings:
            print(f"  {finding}")
        return FINDING
    print("OK: every active workflow has an owner and no recorded review is overdue")
    return OK


if __name__ == "__main__":
    sys.exit(main())
