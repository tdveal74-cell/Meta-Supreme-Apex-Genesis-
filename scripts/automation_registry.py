"""Check the automation ownership registry against what actually runs.

`registry/automations.json` holds one row per ACTIVE workflow on the VPS n8n
instance, and one row per automation that runs from this repository by itself:
every GitHub Actions workflow file and every hook script `.claude/settings.json`
wires in. Each row says who owns it, which lane it belongs to, and the date a
human last read it end to end. This script reads the instance's own workflow
list and the repository's own files and diffs them against the registry, so it
cannot quietly stop describing the estate.

    python3 scripts/automation_registry.py --check     # read the instance and git, diff, exit 1 on a finding
    python3 scripts/automation_registry.py --validate  # shape and repository coverage only, no network

`--validate` runs in the standalone CI job through test_automation_registry.py,
so a new workflow file or hook that nobody has claimed turns the pull request
that adds it red. Review dates for repository rows are measured against the
last commit that touched the file, which needs full history: `--check` refuses
a shallow clone rather than date every file to the one commit it fetched.
The repository rows were added 2026-11-01, ruled by Tee on a card the day
before, "Add them in a second PR".

Ruled by Tee 2026-10-31 on a card, "Build the registry", after a read of Nate
Herk's five step agent management framework found one gap in the estate: no
record of who owns each automation or when it was last reviewed. The dead SMTP
and Drive credentials of September ran for days because nothing was looking at
the lanes they fed.

IT ONLY READS. It makes GET requests to the n8n public API and never writes to
the instance or to the file. Settling a finding is a commit to the file, made
by a person, which is the ownership the registry exists to record.

WHAT TURNS IT RED, exit 1:
  - an active workflow, a workflow file or a wired hook with no row (an
    automation nobody has claimed)
  - a row whose workflow is gone or no longer active, or whose file is not
    wired in (a stale claim)
  - a row whose review is overdue: `reviewed` older than `review_every_days`,
    or the workflow's `updatedAt` (the file's last commit, for a repository
    row) later than the day it was reviewed, because a
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
import subprocess
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
#: The same for an automation that runs from this repository, keyed by its path.
REPO_ROW_KEYS = ("path", "lane", "owner", "reviewed")
#: A hook script named in a `.claude/settings.json` command, in either spelling
#: of the variable. A command that names no script this way is still claimed,
#: under `SETTINGS_PATH#<event>/<n>`, so a hook written another way (a relative
#: path, an absolute one, an inline command) cannot go undiscovered.
HOOK_PATH_RE = re.compile(r"\$(?:CLAUDE_PROJECT_DIR|\{CLAUDE_PROJECT_DIR\})/([A-Za-z0-9_./-]+)")
SETTINGS_PATH = ".claude/settings.json"
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
    problems += _validate_rows(doc.get("workflows"), "workflows", ROW_KEYS, "id")
    problems += _validate_rows(doc.get("repo"), "repo", REPO_ROW_KEYS, "path")
    return problems


def _validate_rows(rows: Any, section: str, row_keys: Sequence[str], id_key: str) -> List[str]:
    if not isinstance(rows, list):
        return [f"{section} must be a list"]
    problems: List[str] = []
    seen: Dict[str, int] = {}
    for index, row in enumerate(rows):
        where = f"{section} row {index}"
        if not isinstance(row, dict):
            problems.append(f"{where} is not an object")
            continue
        keys = set(row)
        if keys != set(row_keys):
            missing = sorted(set(row_keys) - keys)
            extra = sorted(keys - set(row_keys))
            problems.append(f"{where} has the wrong fields (missing {missing}, unexpected {extra})")
            continue
        for field in row_keys:
            if field == "reviewed":
                continue
            if not isinstance(row[field], str) or not row[field].strip():
                problems.append(f"{where} ({row.get(id_key)}) has an empty {field}")
        reviewed = row["reviewed"]
        if reviewed is not None:
            if not isinstance(reviewed, str) or not DATE_RE.match(reviewed):
                problems.append(f"{where} ({row[id_key]}) reviewed must be YYYY-MM-DD or null")
            else:
                try:
                    date.fromisoformat(reviewed)
                except ValueError:
                    problems.append(f"{where} ({row[id_key]}) reviewed is not a real date: {reviewed}")
        if isinstance(row[id_key], str):
            if row[id_key] in seen:
                problems.append(f"{where} repeats {id_key} {row[id_key]} from row {seen[row[id_key]]}")
            seen.setdefault(row[id_key], index)
    return problems


def review_finding(
    label: str, row: Dict[str, Any], changed: Optional[date], every: int, today: date
) -> Optional[str]:
    """The one finding a reviewed row can raise, or None. Never called for a null review."""
    reviewed = date.fromisoformat(row["reviewed"])
    if reviewed > today:
        return (
            f"BAD REVIEW DATE: {label} says it was reviewed on {row['reviewed']}, after today "
            f"{today.isoformat()}, which would silence its review alarms until then"
        )
    age = (today - reviewed).days
    if age > every:
        return (
            f"REVIEW DUE: {label} owner {row['owner']}, last reviewed {row['reviewed']}, "
            f"{age} days ago against a {every} day period"
        )
    if changed is not None and changed > reviewed:
        return (
            f"REVIEW DUE: {label} owner {row['owner']}, changed {changed.isoformat()} "
            f"after its review on {row['reviewed']}"
        )
    return None


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
        updated = parse_iso(workflow.get("updatedAt"))
        finding = review_finding(label, row, updated.date() if updated else None, every, today)
        if finding:
            findings.append(finding)
    if never:
        notes.append(f"NEVER REVIEWED: {never} of {len(rows)} workflow rows carry no review date")
    return findings, notes


def repo_automations(root: str = REPO) -> List[str]:
    """Every automation the repository runs by itself, as paths from its root.

    The GitHub Actions workflow files, and every hook script that
    `.claude/settings.json` wires in through `$CLAUDE_PROJECT_DIR`. Derived
    from the files rather than listed, so a new workflow or hook has to be
    claimed in the registry before CI goes green.
    """
    found = set()
    workflows = os.path.join(root, ".github", "workflows")
    if os.path.isdir(workflows):
        for name in os.listdir(workflows):
            if name.endswith((".yml", ".yaml")):
                found.add(f".github/workflows/{name}")
    settings = os.path.join(root, ".claude", "settings.json")
    if os.path.isfile(settings):
        with open(settings, encoding="utf-8") as handle:
            hooks = (json.load(handle) or {}).get("hooks") or {}
        for event, groups in sorted(hooks.items()):
            count = 0
            for group in groups or []:
                for hook in (group or {}).get("hooks") or []:
                    count += 1
                    command = str((hook or {}).get("command") or "")
                    paths = [m.group(1) for m in HOOK_PATH_RE.finditer(command)]
                    if paths:
                        found.update(paths)
                    else:
                        found.add(f"{SETTINGS_PATH}#{event}/{count}")
    return sorted(found)


def repo_coverage(doc: Dict[str, Any], present: Sequence[str]) -> List[str]:
    """Findings for repository automations nobody claimed, and claims on nothing."""
    rows = {row["path"] for row in doc["repo"]}
    findings = [f"UNOWNED: {path} runs from this repository and has no row" for path in present
                if path not in rows]
    findings += [f"STALE: the row for {path} names a file that is not wired in" for path in sorted(rows)
                 if path not in set(present)]
    return findings


def git_changed(root: str, path: str) -> Optional[date]:
    """The committer date of the last commit that touched `path`.

    Refuses a shallow clone, where every file would date from the one commit
    fetched and every review would read as overtaken.
    """
    shallow = subprocess.run(
        ["git", "-C", root, "rev-parse", "--is-shallow-repository"],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    if shallow == "true":
        raise ValueError("the checkout is shallow, so file dates would all read as the newest commit")
    stamp = subprocess.run(
        ["git", "-C", root, "log", "-1", "--format=%ct", "--", path.split("#", 1)[0]],
        capture_output=True, text=True, check=True,
    ).stdout.strip()
    # %ct is seconds since the epoch, read as a UTC date to match `today`.
    return datetime.fromtimestamp(int(stamp), tz=timezone.utc).date() if stamp else None


def changed_dates(root: str, present: Sequence[str]) -> Dict[str, Optional[date]]:
    """Last change for each automation. A hook also changes when its wiring
    in `.claude/settings.json` does, so it takes the later of the two dates."""
    hooks = [path for path in present if path.startswith(".claude/")]
    settings_date = git_changed(root, SETTINGS_PATH) if hooks else None
    out: Dict[str, Optional[date]] = {}
    for path in present:
        own = git_changed(root, path)
        if path in hooks:
            known = [d for d in (own, settings_date) if d is not None]
            own = max(known) if known else None
        out[path] = own
    return out


def repo_diff(
    doc: Dict[str, Any], present: Sequence[str], changed: Dict[str, Optional[date]], today: date
) -> Tuple[List[str], List[str]]:
    every = int(doc["review_every_days"])
    findings = repo_coverage(doc, present)
    never = 0
    for row in sorted(doc["repo"], key=lambda r: r["path"]):
        if row["path"] not in set(present):
            continue
        if row["reviewed"] is None:
            never += 1
            continue
        finding = review_finding(row["path"], row, changed.get(row["path"]), every, today)
        if finding:
            findings.append(finding)
    notes = [f"NEVER REVIEWED: {never} of {len(doc['repo'])} repository rows carry no review date"] if never else []
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
    try:
        present = repo_automations()
    except (OSError, ValueError) as error:
        print(f"CANNOT CHECK: could not read the repository's automations: {type(error).__name__}: {error}")
        return CANNOT_CHECK
    if args.validate:
        uncovered = repo_coverage(doc, present)
        if uncovered:
            print("REPOSITORY COVERAGE:")
            for finding in uncovered:
                print(f"  {finding}")
            return FINDING
        print(f"OK: {len(doc['workflows'])} workflow rows and {len(doc['repo'])} repository rows, well formed")
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

    today = datetime.now(timezone.utc).date()
    findings, notes = diff(doc, live, today)
    try:
        changed = changed_dates(REPO, present)
    except (OSError, ValueError, subprocess.CalledProcessError) as error:
        print(f"CANNOT CHECK: reading file dates from git failed: {type(error).__name__}: {error}")
        return CANNOT_CHECK
    repo_findings, repo_notes = repo_diff(doc, present, changed, today)
    findings += repo_findings
    notes += repo_notes
    active = sum(1 for w in live if w.get("active") is True)
    print(f"Read {len(live)} workflows, {active} active, against {len(doc['workflows'])} rows.")
    print(f"Read {len(present)} repository automations against {len(doc['repo'])} rows.")
    for note in notes:
        print(f"  {note}")
    if findings:
        print(f"FINDINGS: {len(findings)}")
        for finding in findings:
            print(f"  {finding}")
        return FINDING
    print("OK: every active workflow and repository automation has an owner and no recorded review is overdue")
    return OK


if __name__ == "__main__":
    sys.exit(main())
