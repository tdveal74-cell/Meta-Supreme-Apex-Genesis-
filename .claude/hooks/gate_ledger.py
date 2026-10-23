#!/usr/bin/env python3
"""Gate and ledger for outward, hard to undo tool calls.

Ruled by Tee 2026-10-14, after a read of all 67 cloud sessions found 1,810
outward high tier calls and, among them, 45 merges, 49 workflow edits, 36
publishes, 29 workflow executions and 29 force pushes that ran with no answered
card and no message from Tee in the 30 minutes before.

Two jobs, one file.

  pre   PreToolUse. A GATED call is refused unless a human signal exists inside
        WINDOW_MIN minutes before it: a message Tee typed, or an answered
        AskUserQuestion card. Every other call passes. Every decision is logged.
  post  PostToolUse. Appends the executed call to the ledger.
  fail  PostToolUseFailure. Appends the failed call to the ledger.

Design choices that are rulings, not defaults:

  * The gate FAILS CLOSED. If the transcript cannot be read, a gated call is
    refused with that reason. A gate that fails open reports safety while
    watching nothing, which is the failure this repository's watchdogs were
    built around. Only gated calls are affected, so a broken reader cannot lock
    the session out of reading or editing files. A ledger that cannot be
    written does NOT refuse a call: the decision does not depend on it.
  * There is no environment switch and no flag that disables it. Compliance
    items have no exception path. Changing what is gated means editing the
    lists below, in a commit.
  * Merges are ledger only. Tee's standing merge approval of 2026-10-11 covers
    them, and the CI green condition lives in CLAUDE.md, where a hook cannot
    check it.
  * A signal counts only if it is Tee's. Webhook turns, scheduled check-ins,
    task notifications, peer agent reports and summaries all arrive as user
    turns in the transcript and none of them is a person. The discriminator is
    origin.kind == "human" on the entry. A transcript with no origin field at
    all (an older format) falls back to a prefix test.
  * An answered card is PRESENCE, not consent. The hook cannot read what the
    answer was, so a card answered "no" still opens the window. Reading the
    answer before acting stays the model's job.
  * What this is not: a sandbox. It reads the command text of the tools it was
    taught, and Claude could route an HTTP write through a client it does not
    know (wget, an inline python script). It exists to catch the unprompted
    call, which is what the audit measured, not a deliberate evasion.

The ledger is JSON lines at .claude/ledger/gate-ledger.jsonl under the project
directory. It lives in the container, which is reclaimed after inactivity, so it
is a record of the session, not a durable archive. Long strings in it are
scrubbed of anything shaped like a token before they are written.
"""

import json
import os
import re
import shlex
import subprocess
import sys
from datetime import datetime, timedelta, timezone
from urllib.parse import urlparse

WINDOW_MIN = 30
# A signal stamped later than this beyond now is clock skew or a forgery, and
# is ignored instead of counting as "just now" forever.
SKEW_MIN = 5

# Tool name suffixes, matched after the last "__" so a connector that arrives
# under a UUID instead of a name is still caught. The executed high tier outward
# set from the 2026-10-14 audit, less merges, plus the sibling write tools of
# the same platforms.
GATED_SUFFIXES = {
    # n8n
    "publish_workflow", "unpublish_workflow", "archive_workflow", "execute_workflow",
    "update_workflow", "restore_workflow_version", "create_workflow_from_code",
    "rename_data_table", "rename_data_table_column", "add_data_table_rows",
    "create_data_table", "add_data_table_column", "delete_data_table_column",
    "move_workflows_to_folder",
    # Railway, Vercel, Supabase, deploy surfaces
    "set-variables", "railway-agent", "redeploy", "restart-service",
    "create-deployment", "create_deployment", "deploy_to_vercel", "create_git_project",
    "apply_migration", "execute_sql",
    # GitHub, Drive, media
    "actions_run_trigger", "trash_file", "submit_media_job",
    # Airtable
    "update_records_for_table", "create_records_for_table", "delete_records_for_table",
    "update_field", "create_field", "create_table", "update_table", "delete_table",
    "create_automation", "update_automation", "delete_automation", "submit_form",
    # Rakazo
    "update_bot", "create_bot", "give_bot_n8n",
    # Hostinger
    "DNS_updateDNSRecordsV1",
}

# Servers where every tool is gated unless it is a read, not just the listed
# suffixes, so a sibling tool nobody listed is still caught. Servers outside
# this list rely on GATED_SUFFIXES alone, and a connector under a UUID name is
# matched by those suffixes and by the Hostinger prefixes only.
NAMED_SERVERS = (
    "n8n", "railway", "airtable", "vercel", "supabase", "hostinger", "rakazo",
    "blotato", "docusign", "zapier",
    # Remote Desktop Commander runs commands as root on the VPS. Ruled by Tee
    # 2026-10-15 on a card, after a Codex review of PR #344 found the allow rule
    # left it with no human check at all. The underscore form matches the cloud
    # name and the claude_ai_ connector name, not the local plugin server
    # "desktop-commander", which runs inside this container.
    "desktop_commander",
    # Runpod starts, stops and deletes paid GPU pods. Ruled by Tee 2026-10-16 on
    # a card, the day the runpod@runpod plugin was installed. Matches the plugin
    # server (plugin_runpod_runpod), a direct "runpod" registration and a
    # claude.ai connector name. Reads such as list-pods and get-pod still pass.
    "runpod",
    # Graphify, the code graph server registered in .mcp.json. Ruled by Tee
    # 2026-10-17, the day it was added: only its non-read tools need a human
    # signal. Its reads are listed by name in GRAPHIFY_READS below.
    "graphify",
)
# Graphify's read tools, by exact name, read from the live connector on
# 2026-10-22. Most of them start "graphify_" or name a noun (graph_stats,
# shortest_path, recall), so READ_VERB, anchored on the first word, missed 21 of
# 26 and refused them whenever Tee had been quiet for 30 minutes. They are
# listed here for this server only, so no other server gains a read verb. The
# two writes, remember and set_workspace, and any tool added later stay gated.
GRAPHIFY_READS = frozenset({
    "graphify_find", "graphify_rank_files", "graphify_trace", "graphify_callers",
    "graphify_callees", "graphify_node", "graphify_expand", "graphify_file_neighbors",
    "graphify_find_seeds", "graphify_impact", "graphify_imports_exports",
    "graphify_references", "graphify_render_subgraph", "graphify_tests_for",
    "impact_and_risk", "graph_stats", "shortest_path", "memories_about", "recall",
    "list_workspaces", "list_repositories", "query_graph", "search", "fetch",
})
# Reads named per server, for tools READ_VERB cannot see. Ruled by Tee
# 2026-10-22 on a card: Graphify's list above, and blotato-help askQuestion,
# which answers a question from Blotato's docs. Unlike NAMED_SERVERS, which
# tightens on a substring, this loosens, so it matches only the exact name, its
# claude_ai_ connector form and a plugin_<plugin>_<name> form. A server merely
# containing the name, graphify-evil or blotato-help-x, gains nothing.
SERVER_READS = {
    "graphify": GRAPHIFY_READS,
    "blotato-help": frozenset({"askQuestion"}),
}
# Connectors that arrive under a UUID instead of a name, mapped to the name the
# rules above use. Ruled by Tee 2026-10-22 on a card, after this cloud session
# found Graphify registered as 89245824-... and its writes ungated, because no
# rule matched the UUID. A new connector UUID is covered only once it is listed.
SERVER_ALIASES = {
    "89245824-e0dd-4d6f-94dc-d0712a46ef78": "graphify",
}
# On a named server every tool is gated EXCEPT a read. Listing the reads is the
# safer direction: a write verb nobody thought of is caught, and the cost of a
# read nobody listed is one refusal while no human signal is fresh.
READ_VERB = re.compile(
    r"^(get|list|search|read|describe|fetch|analyze|query|show|find|check|validate|explore|"
    r"prepare|whoami|ping|status|inspect|lookup|count|aggregate|help|view|preview|download|"
    r"resolve|compare|calculate|discover|learn|health|artifact_query|web_fetch|git_namespaces|"
    r"filter_project|thread_status|rakazo_status|generate_typescript_types|domain-status|"
    r"environment-status|http-|execute_zapier_read_action|create_observability_query|"
    r"send_feedback|test_workflow$)",
    re.I,
)
# Hostinger tools carry their own prefix, so they are caught under any server
# name, a UUID included.
HOSTINGER_WRITE = re.compile(
    r"^(VPS_(create|delete|update|restart|recreate|stop|start|purchase|set|attach|detach|restore)"
    r"|DNS_(update|delete|reset|create)|domains_(purchase|update|enable|disable|create|delete)"
    r"|hosting_(deploy|import|create|delete|update))",
    re.I,
)
# send_message is gated only on the Rakazo bot platform. The Claude Code Remote
# send_message is a message to a sibling session, which is not outward.
RAKAZO = "rakazo"

# Ledger only: recorded, never refused.
LEDGER_ONLY_SUFFIXES = {"merge_pull_request", "test_workflow"}

# The daily reflection's own row is ledger only too, and nothing else on that
# table or any other. Ruled by Tee 2026-10-22 on a card: "Exempt that one row".
# The routine (trig_01XCKFGEbojhkPRnNbMd8yCP) fires with nobody in the session,
# so the gate refused its one write on 2026-10-16 and 2026-10-17, as it would on
# any scheduled run, and the Pulse raised reflection_missing on every beat from
# 233 to 258 (the runs from 10-18 to 10-22 also found the n8n connector signed
# out, which no change here touches).
#
# The call passes only in the shape the routine's prompt names, narrowed where
# the prompt is loose: an n8n server, this table in this project, exactly the
# three call keys and one row of exactly the six row keys, every value a
# string, kind "reflection", vitals and findings "", emailed "no", a non-empty
# text of at most 900 characters, and a beat_at in UTC (a Z or +00:00 suffix,
# at most six fractional digits, ASCII digits only) within REFLECTION_SKEW_MIN
# of the hook's clock. The Pulse anchors its reflection watch on any reflection
# whose beat_at is up to 1h ahead, so a forward-dated row could silence
# reflection_missing; the freshness bound is what stops that.
#
# And at most one per REFLECTION_EVERY_H in a session. Ruled by Tee on a second
# card the same day, after a critic showed that a session stuck in a loop could
# write the row without end: each one replaces the reflection the Pulse email
# shows, twenty hide every pulse from the routine's own read, and fifty turn the
# GitHub pulse watchdog red. Before the row passes, the session's transcripts
# (the main file and every subagent file under it) are read for a completed
# write to this table, and one inside the window sends the call to the ordinary
# gate. A refused or failed write carries is_error and does not count. Across
# the 16 completed reflection writes this session's transcript still holds
# (from 2026-09-23) the shortest gap is 14.9h, 2026-10-14T20:52Z to
# 2026-10-15T11:44Z, so the cap would have refused none of them. A transcript
# that cannot be read refuses too, and so does one that restarts at a compact
# boundary inside the window, which a session rebuilt on a fresh disk does.
#
# PostToolUse and PostToolUseFailure record the call by its shape alone. The
# decision was taken at PreToolUse; reclassifying on the clock afterwards
# recorded a call allowed at the 10 minute edge as an executed gated write.
REFLECTION_TABLE = "RuPMZKXkqcbuHRKa"
REFLECTION_PROJECT = "qbrcjkbIoorbwot6"
REFLECTION_KEYS = {"beat_at", "kind", "vitals", "findings", "reflection", "emailed"}
REFLECTION_MAX = 900
REFLECTION_SKEW_MIN = 10
REFLECTION_EVERY_H = 12
REFLECTION_BEAT = re.compile(r"\d{4}-\d{2}-\d{2}T\d{2}:\d{2}:\d{2}(\.\d{1,6})?(Z|\+00:00)", re.ASCII)

SHELL_WRAPPERS = {"sudo", "command", "env", "time", "nohup", "exec", "nice", "builtin"}
SHELLS = {"bash", "sh", "zsh", "dash"}

# (pattern, keep): keep is None to replace the whole match, 2 to keep group 1
# and replace group 2, 3 to keep groups 1 and 3 and replace group 2.
TOKEN_SHAPES = [
    (re.compile(r"eyJ[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}\.[A-Za-z0-9_-]{8,}"), None),
    (re.compile(r"\b[0-9a-fA-F]{48,}\b"), None),
    (re.compile(r"\b(?:sk|pk|csk|key|ghp|gho|ghs|xox[bp])[-_][A-Za-z0-9_-]{16,}"), None),
    (re.compile(r"\bAKIA[0-9A-Z]{12,}\b"), None),
    # user:password@host in a URL, and curl -u user:password
    (re.compile(r"(://[^/\s:@]+:)([^/\s@]{3,})(@)"), 3),
    (re.compile(r"(\s-u\s+[^\s:]+:)(\S{3,})"), 2),
    # NAME=value where the name ends in a secret word, including SMTP_PASS and
    # STRIPE_SECRET, which a leading word boundary would miss. A match starts
    # only where a name starts, and the whitespace on each side of the separator
    # is capped at 64 characters, so a long name followed by a long run of spaces
    # costs linear time. Uncapped, one padded 2.5 KB command took 25 s here and
    # outran the hook's 15 s timeout before its deny was printed (found
    # 2026-10-17). The cap is the one thing this changes in what is redacted: a
    # value more than 64 whitespace characters from its name is no longer caught.
    # A first cap of 16 missed values an independent verifier placed 17 away.
    (re.compile(
        r"(?i)(?<![A-Za-z0-9_.-])([A-Za-z0-9_.-]*(?:authorization|bearer|api[_-]?key|secret[_-]?access[_-]?key|"
        r"key|token|secret|passwd|password|pass)['\"]?\s{0,64}[:= ]\s{0,64}['\"]?)([^\s'\",}&]{8,})"
    ), 2),
    # a long mixed case token with no hyphen or slash, which a branch name or a
    # path never is
    (re.compile(r"\b(?=[A-Za-z0-9+=_]*[A-Z])(?=[A-Za-z0-9+=_]*[a-z])(?=[A-Za-z0-9+=_]*\d)[A-Za-z0-9+=_]{40,}\b"), None),
]


def scrub(text):
    text = str(text)
    for shape, keep in TOKEN_SHAPES:
        if keep is None:
            text = shape.sub("[REDACTED]", text)
        elif keep == 2:
            text = shape.sub(lambda m: m.group(1) + "[REDACTED]", text)
        else:
            text = shape.sub(lambda m: m.group(1) + "[REDACTED]" + m.group(3), text)
    return text


def project_dir():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def ledger_path():
    return os.path.join(project_dir(), ".claude", "ledger", "gate-ledger.jsonl")


# --------------------------------------------------------- reading a shell line


def _strip_heredocs(command):
    """Removes heredoc bodies, which are data and are full of words that look
    like commands."""
    out = []
    lines = command.split("\n")
    i = 0
    while i < len(lines):
        line = lines[i]
        out.append(line)
        m = re.search(r"(?<!<)<<(?!<)-?\s*(['\"]?)([A-Za-z_][A-Za-z0-9_]*)\1", line)
        i += 1
        if m and line[:m.start()].count("'") % 2 == 0 and line[:m.start()].count('"') % 2 == 0:
            term = m.group(2)
            while i < len(lines) and lines[i].strip() != term:
                i += 1
            i += 1  # the terminator
    return "\n".join(out)


def _paren_body(command, start):
    """Given the index just after an opening "$(", returns (body, end_index)."""
    n = len(command)
    j, depth = start, 1
    while j < n and depth:
        depth += (command[j] == "(") - (command[j] == ")")
        j += 1
    return command[start:j - 1], j - 1


def _statements(command, depth=0):
    """Splits a shell line into statements, quote aware, and pulls the bodies
    of $( ) and backticks out as statements of their own."""
    command = _strip_heredocs(command).replace("\\\n", " ")
    stmts, buf, subs = [], [], []
    i, n = 0, len(command)
    quote = None
    while i < n:
        ch = command[i]
        if quote == "'":
            buf.append(ch)
            if ch == "'":
                quote = None
        elif ch == "\\" and i + 1 < n:
            buf.append(ch + command[i + 1])
            i += 1
        elif ch == "#" and quote is None and (i == 0 or command[i - 1] in " \t\n;&|("):
            nl = command.find("\n", i)
            i = (n if nl < 0 else nl) - 1
        elif ch == "$" and command[i:i + 2] == "$(":
            body, i = _paren_body(command, i + 2)
            subs.append(body)
            buf.append(" ")
        elif ch == "`":
            j = command.find("`", i + 1)
            j = n if j < 0 else j
            subs.append(command[i + 1:j])
            buf.append(" ")
            i = j
        elif quote == '"':
            buf.append(ch)
            if ch == '"':
                quote = None
        elif ch in "'\"":
            quote = ch
            buf.append(ch)
        elif ch in ";|&\n()":
            stmts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    stmts.append("".join(buf))
    out = [s.strip() for s in stmts if s.strip()]
    if depth < 4:
        for body in subs:
            out.extend(_statements(body, depth + 1))
    return out


RESERVED = {"then", "do", "else", "elif", "if", "while", "until", "!", "{", "}", "time", "coproc"}
ASSIGNMENT = re.compile(r"^[A-Za-z_][A-Za-z0-9_]*=")
REDIRECT_BARE = re.compile(r"^(\d*>{1,2}|\d*<|&>{1,2})$")
REDIRECT_ATTACHED = re.compile(r"^(\d*>{1,2}|\d*<|&>{1,2})\S")


def _short_flags_with(token, letters):
    """True for a bundled short flag, a dash and then ASCII letters only, that
    carries any of `letters`: -c, -lc, -rf, -fR. It means exactly what the
    fullmatch -[a-zA-Z]*x[a-zA-Z]* meant, without the backtracking that made one
    long flag token quadratic: an 80 KB "-rrr...r1" took 15 s, the hook's whole
    timeout (found 2026-10-17 by an independent verifier)."""
    body = token[1:]
    return token[:1] == "-" and body.isascii() and body.isalpha() and any(c in body for c in letters)
# wrapper -> flags that consume a value
WRAPPER_VALUE_FLAGS = {
    "sudo": {"-u", "-g", "-h", "-p", "-C", "-D", "-R", "-T"},
    "env": {"-u", "-C", "-S"},
    "nice": {"-n"},
    "timeout": {"-s", "-k"},
    "xargs": {"-I", "-n", "-P", "-d", "-L", "-s", "-E", "-a"},
    "command": set(),
}


def _unwrap(argv):
    """Strips shell reserved words, redirections, env assignments and wrappers
    that carry their own flags (timeout 10 curl, sudo -n git, xargs curl)."""
    out, skip = [], False
    for t in argv:
        if skip:
            skip = False
            continue
        if REDIRECT_BARE.match(t):
            skip = True  # the redirect target, or nothing when the statement ends
            continue
        if REDIRECT_ATTACHED.match(t):
            continue
        out.append(t)
    argv = out
    for _ in range(8):
        # Walk an index and slice once. Dropping one word at a time with
        # argv[1:] copied the list on every step, so a statement made of a long
        # run of reserved words took quadratic time: 13 s for a 300 KB run of
        # "{ " before a gated call, close to the 15 s hook timeout (found
        # 2026-10-17 by an independent verifier).
        k = 0
        while k < len(argv) and (argv[k] in RESERVED or ASSIGNMENT.match(argv[k])):
            k += 1
        argv = argv[k:]
        if not argv:
            return argv
        prog = os.path.basename(argv[0])
        if prog in ("nohup", "exec", "builtin"):
            argv = argv[1:]
        elif prog in WRAPPER_VALUE_FLAGS:
            value_flags = WRAPPER_VALUE_FLAGS[prog]
            rest, i = argv[1:], 0
            while i < len(rest) and rest[i].startswith("-"):
                i += 2 if rest[i] in value_flags else 1
            if prog == "timeout" and i < len(rest):
                i += 1  # the duration
            argv = rest[i:]
        else:
            return argv
    return argv


def _argv(statement):
    if len(statement) > 20000:
        argv = statement.split()  # shlex is quadratic on one huge token
    else:
        try:
            argv = shlex.split(statement)
        except ValueError:
            argv = statement.split()
    return _unwrap(argv)


def _expand(statement, depth=0):
    """Yields argv lists, recursing into bash -c and eval."""
    argv = _argv(statement)
    if not argv:
        return
    prog = os.path.basename(argv[0])
    if depth < 4 and prog in SHELLS:
        for i, a in enumerate(argv[1:], 1):
            if _short_flags_with(a, "c") and i + 1 < len(argv):
                for s in _statements(argv[i + 1]):
                    yield from _expand(s, depth + 1)
                return
    if depth < 4 and prog == "find" and ("-exec" in argv or "-execdir" in argv):
        k = next(i for i, a in enumerate(argv) if a in ("-exec", "-execdir"))
        inner = []
        for a in argv[k + 1:]:
            if a in (";", "+"):
                break
            inner.append(a)
        sub = _unwrap(inner)
        if sub:
            yield sub
    if depth < 4 and prog == "eval":
        for s in _statements(" ".join(argv[1:])):
            yield from _expand(s, depth + 1)
        return
    yield argv


def _git_cwd(argv, cwd):
    for i, a in enumerate(argv):
        if a == "-C" and i + 1 < len(argv):
            path = argv[i + 1]
            return path if os.path.isabs(path) or not cwd else os.path.join(cwd, path)
    return cwd


# Each git lookup starts a process, a few milliseconds, and a padded command can
# name thousands of directories with -C. Past this many lookups in one classify
# a lookup reads as failed, so the branch is unknown and the remote unnamed,
# both of which gate. Found 2026-10-23 while fixing #405.
GIT_LOOKUPS = 16
_BRANCH, _REMOTES, _DEFAULT = {}, {}, {}
_SPENT = [0]


def _fresh_lookups():
    _BRANCH.clear()
    _REMOTES.clear()
    _DEFAULT.clear()
    _SPENT[0] = 0


def _git_out(cwd, *args):
    """git's output, "" when git answers with an error, None when this call's
    lookups are spent or git cannot run."""
    if _SPENT[0] >= GIT_LOOKUPS:
        return None
    _SPENT[0] += 1
    try:
        out = subprocess.run(["git", *args], cwd=cwd or None, capture_output=True, text=True, timeout=5)
    except Exception:
        return None
    return out.stdout.strip() if out.returncode == 0 else ""


def _current_branch(cwd):
    if cwd not in _BRANCH:
        _BRANCH[cwd] = _git_out(cwd, "rev-parse", "--abbrev-ref", "HEAD") or ""
    return _BRANCH[cwd]


def _named_remote(remote, cwd):
    """True when the push goes to a remote configured in the repository by
    name. With no remote given, git picks one in this order. A lookup that
    fails reads as not named, which gates."""
    if cwd not in _REMOTES:
        names = _git_out(cwd, "remote")
        _REMOTES[cwd] = None if names is None else set(names.split())
    if not remote:
        if cwd not in _DEFAULT:
            branch = _current_branch(cwd)
            _DEFAULT[cwd] = "origin"
            for key in (f"branch.{branch}.pushRemote", "remote.pushDefault", f"branch.{branch}.remote"):
                value = _git_out(cwd, "config", "--get", key)
                if value is None or value:
                    _DEFAULT[cwd] = value
                    break
        remote = _DEFAULT[cwd]
    return _REMOTES[cwd] is not None and remote in _REMOTES[cwd]


PUSH_ARG_FLAGS = {"-o", "--push-option", "--repo", "--receive-pack", "--exec"}
PUSH_VALUE_LONG = {"repo", "push-option", "receive-pack", "exec", "recurse-submodules"}

# Every long option `git push -h` lists (git 2.43), with what it does to the
# gate. The full list is needed so that a prefix is matched against all of
# them, the way git matches it.
PUSH_LONG = {
    "force": "force", "force-with-lease": "lease", "force-if-includes": "lease",
    "delete": "delete", "prune": "delete", "mirror": "mirror",
    "all": "every", "branches": "every", "tags": "every",
    "repo": "", "push-option": "", "receive-pack": "", "exec": "",
    "recurse-submodules": "", "verbose": "", "quiet": "", "dry-run": "",
    "porcelain": "", "thin": "", "set-upstream": "", "progress": "",
    "no-verify": "", "verify": "", "follow-tags": "", "signed": "", "atomic": "",
    "ipv4": "", "ipv6": "",
}
# Every prefix of every option, built once, so a command of many long options
# costs one lookup per word rather than a scan of the whole list.
PUSH_PREFIXES = {}
for _option in PUSH_LONG:
    for _end in range(1, len(_option) + 1):
        PUSH_PREFIXES.setdefault(_option[:_end], []).append(_option)


def _push_long(name):
    """The options git push reads `--name` as. Git takes the exact name, or any
    unambiguous prefix of one, so --del is --delete and --mir is --mirror (both
    measured against git 2.43 on 2026-10-17). A prefix of two or more options
    makes git refuse the push, so returning all of them only ever over-gates.
    A --no- form turns an option off and matches nothing that gates here."""
    if name in PUSH_LONG:
        return [name]
    return PUSH_PREFIXES.get(name, [])


def _git_push(argv, cwd):
    """Returns (cls, gated) for a git argv, or None when it is not a push.

    Git reads a short bundle one letter at a time, so -4f, -uf and -f6 all
    force and -ud deletes; until 2026-10-17 a digit in the bundle let a force
    or a delete through ungated. Any f or d in a bundle counts here, even one
    git would read as the value of -o, which only over-gates. Only the exact
    value flags skip the next word: skipping after a bundle that ends in o
    would hide a following -f, so that word is read as if it were its own.

    That word may still be a value to git, so the word taken for the remote
    may be one and the real remote may sit where a refspec is read. Until
    2026-10-22 a lease to the session's own branch went open through -uo v
    followed by a URL, through a host:path remote with no @, and through a
    path such as /tmp/r.git. The lease is open only when nothing can have
    shifted the remote, no word is URL shaped, and the remote is one the
    repository has configured by name."""
    if os.path.basename(argv[0]) != "git" or "push" not in argv:
        return None
    pi = argv.index("push")
    cwd = _git_cwd(argv[:pi], cwd)
    force = lease = delete = mirror = every = shifted = False
    positional = []
    repo = ""
    rest = argv[pi + 1:]
    i = 0
    while i < len(rest):
        a = rest[i]
        i += 1
        if a in PUSH_ARG_FLAGS:
            if a == "--repo" and i < len(rest):
                repo = rest[i]
            i += 1
        elif a.startswith("--"):
            name, eq, value = a[2:].partition("=")
            hits = _push_long(name)
            effects = {PUSH_LONG[o] for o in hits}
            force = force or "force" in effects
            # Kept from the check this replaced, which gated any word starting
            # --force-with-lease. Git refuses one with junk after the name, but
            # nothing main gates is let through here.
            lease = lease or "lease" in effects or a.startswith("--force-with-lease")
            delete = delete or "delete" in effects
            mirror = mirror or "mirror" in effects
            every = every or "every" in effects
            if eq and hits == ["repo"]:
                repo = value
            shifted = shifted or (not eq and any(o in PUSH_VALUE_LONG for o in hits))
        elif a.startswith("-"):
            bundle = a[1:]
            force = force or "f" in bundle
            delete = delete or "d" in bundle
            shifted = shifted or bundle.endswith("o")
        else:
            positional.append(a)
    remote = positional[0] if positional else repo
    refspecs = positional[1:]
    plus = any(s.startswith("+") for s in refspecs)
    delete = delete or any(s.startswith(":") for s in refspecs)
    targets = []
    for spec in refspecs:
        spec = spec.lstrip("+")
        dst = spec.split(":")[-1] if ":" in spec else spec
        dst = re.sub(r"^refs/heads/", "", dst)
        if dst in ("HEAD", ""):
            dst = _current_branch(cwd)
        targets.append(dst)
    if not refspecs:
        targets = [_current_branch(cwd)]
    if not (force or plus or lease or delete or mirror):
        return "git_push", False
    parts = [name for name, on in (
        ("plain", force), ("plus", plus), ("lease", lease), ("delete", delete), ("mirror", mirror)
    ) if on]
    own = bool(targets) and all(t.startswith("claude/") for t in targets)
    url_remote = any("://" in w or "@" in w for w in positional + [repo])
    gated = force or plus or delete or mirror or every or not own or url_remote or shifted
    # Only a lease to the session's own branch is left. Found 2026-10-23 by
    # Codex on #405: a path such as /tmp/r.git carries no URL punctuation, and
    # git force-pushed to it while this read the lease as open. Checked last so
    # git runs only for a lease that would otherwise be open.
    gated = gated or not _named_remote(remote, cwd)
    return "git_force_push:" + "+".join(parts), gated


CURL_ARG_LETTERS = set("oHuAebcxwmKEQrCyYzZ")
CURL_BODY_LONG = {
    "--data", "--data-raw", "--data-binary", "--data-urlencode", "--data-ascii",
    "--json", "--form", "--form-string", "--upload-file",
}
WRITE_METHODS = ("POST", "PUT", "PATCH", "DELETE")


def _curl_mutating(argv):
    if os.path.basename(argv[0]) != "curl":
        return False
    mutating = False
    explicit = False
    get_mode = False
    urls = []
    for i in range(1, len(argv)):
        a = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else ""
        if a.startswith("--"):
            name, _, val = a.partition("=")
            if name in CURL_BODY_LONG:
                mutating = True
            elif name == "--get":
                get_mode = True
            elif name == "--request" and (val or nxt).upper() in WRITE_METHODS:
                mutating = explicit = True
        elif a.startswith("-") and len(a) > 1:
            letters = a[1:]
            for k, ch in enumerate(letters):
                if ch == "G":
                    get_mode = True
                if ch in "dFT":
                    mutating = True
                    break
                if ch == "X":
                    if (letters[k + 1:] or nxt).upper() in WRITE_METHODS:
                        mutating = explicit = True
                    break
                if ch in CURL_ARG_LETTERS:
                    break
        elif (
            re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", a)
            or re.match(r"^[\w.-]+\.[A-Za-z]{2,}(/|:|$)", a)
            or re.match(r"^[\w.\[\]:-]+:\d+(/\S*)?$", a)
            or re.match(r"^localhost(/|$)", a)
        ):
            urls.append(a)
    if get_mode and not explicit:
        return False
    if not mutating:
        return False
    if not urls:
        return True
    for u in urls:
        host = (urlparse(u if "://" in u else "http://" + u).hostname or "").lower()
        if host not in ("localhost", "0.0.0.0", "::1") and not re.fullmatch(r"127\.\d+\.\d+\.\d+", host):
            return True
    return False


def _is_local_url(u):
    host = (urlparse(u if "://" in u else "http://" + u).hostname or "").lower()
    return host in ("localhost", "0.0.0.0", "::1") or bool(re.fullmatch(r"127\.\d+\.\d+\.\d+", host))


def _wget_mutating(argv):
    """wget writing to a non-local host: --post-data, --post-file, --body-data,
    --body-file, or --method with a write verb."""
    if os.path.basename(argv[0]) != "wget":
        return False
    mutating, urls = False, []
    for i in range(1, len(argv)):
        a = argv[i]
        nxt = argv[i + 1] if i + 1 < len(argv) else ""
        name, _, val = a.partition("=")
        if name in ("--post-data", "--post-file", "--body-data", "--body-file"):
            mutating = True
        elif name == "--method" and (val or nxt).upper() in WRITE_METHODS:
            mutating = True
        elif re.match(r"^[A-Za-z][A-Za-z0-9+.-]*://", a) or (
            not a.startswith("-") and re.match(r"^[\w.\[\]-]+(:\d+)?(/\S*)?$", a) and ("." in a or ":" in a or a.startswith("localhost"))
        ):
            urls.append(a)
    return mutating and not (urls and all(_is_local_url(u) for u in urls))


GH_VALUE_FLAGS = {
    "-R", "--repo", "--hostname", "-H", "--header", "-q", "--jq", "-t", "--template", "--cache",
    "-f", "-F", "--field", "--raw-field", "--input", "-X", "--method", "-p", "--preview",
}
GH_GATED = {
    "workflow": {"run", "enable", "disable"},
    "run": {"rerun", "cancel", "delete"},
    "release": {"create", "delete", "upload", "edit", "delete-asset"},
    "repo": {"create", "delete", "edit", "archive", "unarchive", "rename", "fork"},
    "secret": {"set", "delete"},
    "variable": {"set", "delete"},
    "ssh-key": {"add", "delete"},
    "gpg-key": {"add", "delete"},
    "ruleset": {"delete"},
    "label": {"delete"},
    "pr": {"delete"},
    "issue": {"delete", "transfer"},
}


GRAPHQL_MUTATION = re.compile(r"(?<![\w$\-\"'.])mutation\b\s*[\w({]")


def _gh_graphql(argv):
    """A GraphQL call is read only when its query is written inline and holds no
    mutation. A query read from a file, a variable or stdin cannot be read here,
    so it is treated as a write rather than guessed at."""
    inline = []
    for j, a in enumerate(argv):
        if a in ("-f", "-F", "--field", "--raw-field") and j + 1 < len(argv):
            val = argv[j + 1]
        elif re.match(r"^-[fF]\S", a):
            val = a[2:]
        elif a.startswith(("--field=", "--raw-field=")):
            val = a.split("=", 1)[1]
        else:
            continue
        if val.startswith("query="):
            inline.append(val[len("query="):])
    if not inline or any(q.startswith("@") for q in inline):
        return "gh_api_graphql_unreadable", True
    if any(GRAPHQL_MUTATION.search(q) for q in inline):
        return "gh_api_graphql_mutation", True
    if not all(re.match(r"^\s*(query\b|\{|subscription\b)", q) for q in inline):
        return "gh_api_graphql_unreadable", True  # a variable, a substitution, an empty value
    return None


def _gh_class(argv):
    """Returns (cls, gated) for a gh argv, or None when it is ordinary work.
    pr create, comment, edit, review and close are the daily flow and are not
    gated. pr merge is ledger only, like the merge tool."""
    if os.path.basename(argv[0]) != "gh":
        return None
    positional, i = [], 1
    while i < len(argv):
        a = argv[i]
        if a in GH_VALUE_FLAGS and "=" not in a:
            i += 2
            continue
        if a.startswith("-"):
            i += 1
            continue
        positional.append(a)
        i += 1
    if not positional:
        return None
    group = positional[0]
    verb = positional[1] if len(positional) > 1 else ""
    if group == "pr" and verb == "merge":
        return "gh_pr_merge", False
    if group == "api":
        method, fields, endpoint = "", False, ""
        for j, a in enumerate(argv[1:], 1):
            name, _, val = a.partition("=")
            nxt = argv[j + 1] if j + 1 < len(argv) else ""
            if name in ("-X", "--method"):
                method = (val or nxt).upper()
            elif re.fullmatch(r"-X\w+", a):
                method = a[2:].upper()
            elif name in ("-f", "-F", "--field", "--raw-field", "--input") or re.match(r"^-[fF]\S", a):
                fields = True
        endpoint = positional[1] if len(positional) > 1 else ""
        if endpoint == "graphql":
            return _gh_graphql(argv)
        if method in WRITE_METHODS or (fields and method in ("", "POST")):
            return "gh_api_write", True
        return None
    if verb in GH_GATED.get(group, set()):
        return "gh_%s_%s" % (group, verb), True
    return None


# ---------------------------------------------------------------- classification


def _is_reflection_row(server, tool_input, now):
    """True only for the daily reflection's own row, exactly as its routine
    writes it. Every check compares exact types and values, so a near miss is
    an ordinary gated call rather than a guess. A now of None checks the shape
    alone, for recording a call after its decision was taken."""
    if "n8n" not in server or set(tool_input) != {"dataTableId", "projectId", "rows"}:
        return False
    if tool_input["dataTableId"] != REFLECTION_TABLE or tool_input["projectId"] != REFLECTION_PROJECT:
        return False
    rows = tool_input["rows"]
    if type(rows) is not list or len(rows) != 1 or type(rows[0]) is not dict:
        return False
    row = rows[0]
    if set(row) != REFLECTION_KEYS or any(type(row[k]) is not str for k in REFLECTION_KEYS):
        return False
    if row["kind"] != "reflection" or row["vitals"] != "" or row["findings"] != "" or row["emailed"] != "no":
        return False
    if not row["reflection"].strip() or len(row["reflection"]) > REFLECTION_MAX:
        return False
    if not REFLECTION_BEAT.fullmatch(row["beat_at"]):
        return False
    beat = _parse_ts(row["beat_at"])
    if beat is None:
        return False
    return now is None or abs((beat - now).total_seconds()) <= REFLECTION_SKEW_MIN * 60


def _is_server(server, name):
    """True when server is name itself, its claude.ai connector or a plugin's."""
    return (
        server == name
        or server == "claude_ai_" + name
        or (server.startswith("plugin_") and server.endswith("_" + name))
    )


def classify(tool_name, tool_input, cwd="", now=None, shape_only=False):
    """Returns (cls, gated). cls is None for a call that is not tracked.
    shape_only skips the clock in the reflection row check, for post and fail."""
    tool_input = tool_input if isinstance(tool_input, dict) else {}

    if tool_name.lower() == "bash":
        command = str(tool_input.get("command", ""))
        _fresh_lookups()
        classes, gated = [], False
        for stmt in _statements(command):
            for argv in _expand(stmt):
                prog = os.path.basename(argv[0])
                push = _git_push(argv, cwd)
                if push:
                    classes.append(push[0])
                    gated = gated or push[1]
                elif prog == "curl" and _curl_mutating(argv):
                    classes.append("curl_mutating")
                    gated = True
                elif prog == "wget" and _wget_mutating(argv):
                    classes.append("wget_mutating")
                    gated = True
                elif prog == "gh" and _gh_class(argv):
                    cls_gh, gated_gh = _gh_class(argv)
                    classes.append(cls_gh)
                    gated = gated or gated_gh
                elif prog == "git" and "reset" in argv and "--hard" in argv:
                    classes.append("git_reset_hard")
                elif prog == "git" and "branch" in argv and ("-d" in argv or "-D" in argv):
                    classes.append("git_branch_delete")
                elif prog == "rm" and any(
                    a == "--recursive" or _short_flags_with(a, "rR") for a in argv[1:]
                ):
                    classes.append("rm_recursive")
        if not classes:
            return None, False
        return ",".join(classes), gated

    if not tool_name.startswith("mcp__"):
        return None, False
    parts = tool_name.split("__")
    suffix = parts[-1]
    server = parts[1].lower() if len(parts) > 2 else ""
    server = SERVER_ALIASES.get(server, server)
    if suffix in LEDGER_ONLY_SUFFIXES:
        return suffix, False
    if suffix == "add_data_table_rows" and _is_reflection_row(
        server, tool_input, None if shape_only else (now or datetime.now(timezone.utc))
    ):
        return "reflection_row", False
    if suffix in GATED_SUFFIXES:
        return suffix, True
    if suffix == "send_message" and RAKAZO in server:
        return suffix, True
    if HOSTINGER_WRITE.match(suffix):
        return suffix, True
    if any(_is_server(server, name) and suffix in reads
           for name, reads in SERVER_READS.items()):
        return None, False
    verb = re.sub(r"^(blotato|zapier|VPS|DNS|domains|hosting|billing|reach)_", "", suffix)
    if any(name in server for name in NAMED_SERVERS) and not READ_VERB.match(verb):
        return suffix, True
    return None, False


# ------------------------------------------------------------------ the signal


NOT_HUMAN_PREFIXES = (
    "<system-reminder", "[SYSTEM NOTIFICATION", "<task-notification", "<wake",
    "Another Claude session sent a message", "<agent-message", "[Request interrupted",
    "This session is being continued", "<command-name>", "<local-command",
)


def _parse_ts(value):
    try:
        ts = datetime.fromisoformat(str(value).replace("Z", "+00:00"))
        return ts if ts.tzinfo else ts.replace(tzinfo=timezone.utc)
    except Exception:
        return None


def _message_text(content):
    """Returns (text, has_image) for a content that is a string or a block list."""
    if isinstance(content, str):
        return content, False
    if isinstance(content, list):
        texts, image = [], False
        for b in content:
            if isinstance(b, dict):
                if b.get("type") == "text":
                    texts.append(str(b.get("text", "")))
                elif b.get("type") == "image":
                    image = True
        return "\n".join(texts), image
    return "", False


def _is_human(entry):
    if entry.get("type") != "user" or entry.get("isMeta"):
        return False
    content = (entry.get("message") or {}).get("content")
    if isinstance(content, list) and any(isinstance(b, dict) and b.get("type") == "tool_result" for b in content):
        return False
    text, has_image = _message_text(content)
    if not text.strip() and not has_image:
        return False
    if text.lstrip().startswith("[Request interrupted"):
        return False
    origin = entry.get("origin")
    if isinstance(origin, dict):
        return origin.get("kind") == "human"
    return has_image or not text.lstrip().startswith(NOT_HUMAN_PREFIXES)


def main_transcript(path):
    """A subagent's hook can point at a file under <session>/subagents/, or
    deeper (<session>/subagents/workflows/wf_x/agent-y.jsonl). The person spoke
    in the session file, so read that one."""
    marker = "/subagents/"
    if marker in path:
        return path[:path.index(marker)] + ".jsonl"
    return path


def latest_signal(path, now):
    """Returns (signal_kind, age_minutes) of the newest human signal, or None
    when the transcript holds none. Raises when it cannot be read."""
    card_ids = set()
    newest = None
    horizon = now + timedelta(minutes=SKEW_MIN)
    with open(path, encoding="utf-8", errors="replace") as fh:
        for line in fh:
            try:
                entry = json.loads(line, strict=False)
            except Exception:
                continue
            ts = _parse_ts(entry.get("timestamp"))
            if ts is None or ts > horizon:
                continue
            kind = None
            if _is_human(entry):
                kind = "message"
            elif entry.get("type") == "assistant":
                blocks = (entry.get("message") or {}).get("content")
                if isinstance(blocks, list):
                    for b in blocks:
                        if isinstance(b, dict) and b.get("type") == "tool_use" and b.get("name") == "AskUserQuestion":
                            card_ids.add(b.get("id"))
            elif entry.get("type") == "user":
                blocks = (entry.get("message") or {}).get("content")
                if isinstance(blocks, list):
                    for b in blocks:
                        if (
                            isinstance(b, dict)
                            and b.get("type") == "tool_result"
                            and b.get("tool_use_id") in card_ids
                            and not b.get("is_error")
                        ):
                            kind = "card"
            if kind and (newest is None or ts > newest[1]):
                newest = (kind, ts)
    if newest is None:
        return None
    return newest[0], max(0.0, (now - newest[1]).total_seconds() / 60.0)


def _session_files(path):
    """The session's main transcript and every subagent transcript under it,
    so a write a subagent made counts the same as one the session made."""
    main = main_transcript(path)
    files = [main]
    sub = os.path.join(main[: -len(".jsonl")], "subagents") if main.endswith(".jsonl") else ""
    if sub and os.path.isdir(sub):
        # A directory that cannot be listed raises rather than being skipped,
        # so a write inside it cannot go uncounted.
        for dirpath, dirs, names in os.walk(sub, onerror=_raise):
            dirs.sort()
            files += [os.path.join(dirpath, n) for n in sorted(names) if n.endswith(".jsonl")]
    return files


def _raise(err):
    raise err


# The id in a tool_result line, read once per line so the lookup is a set
# membership test. Searching every line for every tracked id grew with lines
# times ids: 3,000 refused attempts took 20.6 s, past the hook's 15 s.
RESULT_ID = re.compile(r'"tool_use_id"\s*:\s*"([^"\\]+)"')


def last_reflection_write(path, now, since=None):
    """Returns the time of the newest completed write to the reflection table
    anywhere in the session, or None. A write counts when its tool_result came
    back without is_error, which a refusal and a failure both carry. Any write
    to the table counts, whatever its shape. Raises when a file cannot be read,
    so the caller fails closed.

    Speed matters because the hook has 15 s and a session's files grow without
    bound: this one held 167 MB across 106 files on 2026-10-22, and parsing it
    all took 5.4 s. A file last modified before since cannot hold a result
    inside the window, so it is skipped unread, and a line is parsed only when
    it names the tool or carries the id of a write already seen in that file.

    A file whose first entry is a compact boundary dated inside the window
    cannot prove the window is clean, and raises. Compaction during a session
    only appends a boundary after the history it summarises, but a session
    rebuilt on a fresh disk restarts its file at the newest boundary: this one's
    main file was born 2026-09-24T11:41:33Z with a first entry dated
    2026-09-22T23:26:39Z. A write made before such a boundary is no longer on
    disk to count."""
    newest = None
    horizon = now + timedelta(minutes=SKEW_MIN)
    floor = since.timestamp() if since is not None else None
    for name in _session_files(path):
        if floor is not None and name != main_transcript(path) and os.path.getmtime(name) < floor:
            continue
        writes = set()
        with open(name, encoding="utf-8", errors="replace") as fh:
            first = True
            for line in fh:
                if first:
                    first = False
                    _refuse_a_restarted_window(line, since)
                if "add_data_table_rows" not in line and not (
                    writes and any(m in writes for m in RESULT_ID.findall(line))
                ):
                    continue
                try:
                    entry = json.loads(line, strict=False)
                except Exception:
                    continue
                blocks = (entry.get("message") or {}).get("content") if isinstance(entry, dict) else None
                if not isinstance(blocks, list):
                    continue
                for b in blocks:
                    if not isinstance(b, dict):
                        continue
                    if (
                        entry.get("type") == "assistant"
                        and b.get("type") == "tool_use"
                        and str(b.get("name", "")).endswith("__add_data_table_rows")
                        and isinstance(b.get("input"), dict)
                        and b["input"].get("dataTableId") == REFLECTION_TABLE
                        and isinstance(b.get("id"), str)
                        and b["id"]
                    ):
                        writes.add(b["id"])
                    elif (
                        entry.get("type") == "user"
                        and b.get("type") == "tool_result"
                        and b.get("tool_use_id") in writes
                        and not b.get("is_error")
                    ):
                        ts = _parse_ts(entry.get("timestamp"))
                        if ts is not None and ts <= horizon and (newest is None or ts > newest):
                            newest = ts
    return newest


def _refuse_a_restarted_window(line, since):
    """Raises when the file's first entry is a compact boundary inside the
    window, because the history before it is not in the file."""
    if since is None or "compact_boundary" not in line:
        return
    try:
        entry = json.loads(line, strict=False)
    except Exception:
        return
    if not (isinstance(entry, dict) and entry.get("type") == "system" and entry.get("subtype") == "compact_boundary"):
        return
    ts = _parse_ts(entry.get("timestamp"))
    if ts is None or ts > since:
        raise ValueError(
            "the transcript starts at a compact boundary dated %s, inside the window, so a write "
            "before it cannot be counted" % (entry.get("timestamp"),))


def reflection_capped(payload, now):
    """Returns the reason a reflection row must take the ordinary gate, or None
    when it may pass: one completed inside REFLECTION_EVERY_H, or a session that
    cannot be read."""
    try:
        last = last_reflection_write(
            payload.get("transcript_path") or "", now, since=now - timedelta(hours=REFLECTION_EVERY_H))
    except Exception as exc:
        return "the session could not be read to count earlier reflection rows (%s: %s)" % (
            type(exc).__name__, exc)
    if last is not None and now - last < timedelta(hours=REFLECTION_EVERY_H):
        return "a reflection row was already written in this session at %s, inside %d hours" % (
            last.strftime("%Y-%m-%dT%H:%M:%SZ"), REFLECTION_EVERY_H)
    return None


def decide(cls, gated, payload, now):
    """Returns (allow, reason, signal). Pure apart from reading the transcript."""
    if not gated:
        return True, "not gated", None
    path = payload.get("transcript_path") or ""
    if not path:
        return False, "the hook input carried no transcript_path, so no human signal could be checked", None
    try:
        sig = latest_signal(main_transcript(path), now)
    except Exception as exc:
        return False, "the transcript could not be read (%s: %s)" % (type(exc).__name__, exc), None
    if sig is None:
        return False, "the session holds no message from Tee and no answered card", None
    kind, age = sig
    if age <= WINDOW_MIN:
        return True, "%s %.1f min ago" % (kind, age), sig
    return False, "the newest human signal is a %s %.0f min old, outside the %d min window" % (kind, age, WINDOW_MIN), sig


# ----------------------------------------------------------------------- ledger


PRIORITY_KEYS = re.compile(r"(^|_)(id|ids|name|workflowid|pullnumber|number|repo|owner|branch|url|path)$", re.I)


SUMMARY_SLICE = 2400


def _clip(text, limit=SUMMARY_SLICE):
    """The first limit characters, less any word the cut split, so the scrub
    sees a bounded text and no fragment of a token is left too short for the
    rules to know it."""
    text = str(text)
    if len(text) <= limit:
        return text
    end = limit
    while end and not text[end - 1].isspace():
        end -= 1
    return text[:end]


def summarize(tool_name, tool_input):
    if tool_name.lower() == "bash":
        return scrub(_clip((tool_input or {}).get("command", "")))[:600]
    try:
        if isinstance(tool_input, dict):
            keys = sorted(tool_input, key=lambda k: (0 if PRIORITY_KEYS.search(str(k)) else 1, str(k)))
            ordered = {k: tool_input[k] for k in keys}
        else:
            ordered = tool_input
        return scrub(_clip(json.dumps(ordered, default=str)))[:600]
    except Exception:
        return ""


def write_ledger(row):
    path = ledger_path()
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "a", encoding="utf-8") as fh:
        fh.write(json.dumps(row, sort_keys=True) + "\n")


def _try_ledger(row):
    """A ledger that cannot be written is reported on stderr and never changes a
    decision."""
    try:
        write_ledger(row)
    except Exception as exc:
        sys.stderr.write("gate_ledger: ledger write failed: %s: %s\n" % (type(exc).__name__, exc))


def _row(event, payload, cls, gated, now, **extra):
    row = {
        "ts": now.strftime("%Y-%m-%dT%H:%M:%SZ"),
        "event": event,
        "session": payload.get("session_id", ""),
        "agent": payload.get("agent_id", ""),
        "tool": payload.get("tool_name", ""),
        "class": cls,
        "gated": gated,
        "input": summarize(payload.get("tool_name", ""), payload.get("tool_input")),
    }
    row.update(extra)
    return row


def run(mode, payload, now=None):
    """Returns the JSON object to print on stdout, or None to print nothing."""
    now = now or datetime.now(timezone.utc)
    name = payload.get("tool_name", "")
    cls, gated = classify(name, payload.get("tool_input"), payload.get("cwd", ""), now, shape_only=mode != "pre")
    if cls is None:
        return None

    if mode == "pre":
        capped = reflection_capped(payload, now) if cls == "reflection_row" else None
        if capped:
            cls, gated = "add_data_table_rows", True
        allow, reason, _sig = decide(cls, gated, payload, now)
        if capped:
            reason = capped + ", so this one needs a human signal and " + reason
        _try_ledger(_row("gate-allow" if allow else "gate-deny", payload, cls, gated, now, reason=reason))
        if allow:
            return None
        return {
            "hookSpecificOutput": {
                "hookEventName": "PreToolUse",
                "permissionDecision": "deny",
                "permissionDecisionReason": (
                    "Gate refused %s (%s): %s. If Tee is in this session, put the "
                    "decision to him on an AskUserQuestion card with the recommended "
                    "option first, wait for the answer, then retry. If no one is "
                    "present (a scheduled or webhook session), stop and leave this "
                    "action in your report for him. Do not rephrase the call to get "
                    "around the gate." % (name, cls, reason)
                ),
            }
        }

    event = "executed" if mode == "post" else "failed"
    extra = {}
    if mode == "fail":
        extra["error"] = scrub(_clip(payload.get("error", ""), 1200))[:300]
    _try_ledger(_row(event, payload, cls, gated, now, **extra))
    return None


def main(argv):
    mode = argv[1] if len(argv) > 1 else ""
    if mode not in ("pre", "post", "fail"):
        sys.stderr.write("usage: gate_ledger.py pre|post|fail\n")
        return 0
    try:
        payload = json.load(sys.stdin)
    except Exception:
        payload = {}
    try:
        out = run(mode, payload)
    except Exception as exc:
        if mode == "pre":
            name = payload.get("tool_name", "")
            try:
                tracked = classify(name, payload.get("tool_input"), payload.get("cwd", ""))
            except Exception:
                tracked = ("unknown", True)
            # A reflection row passes only after its cap is checked, which the
            # failure skipped, so it fails closed with the gated calls.
            if tracked[1] or tracked[0] == "reflection_row":
                out = {
                    "hookSpecificOutput": {
                        "hookEventName": "PreToolUse",
                        "permissionDecision": "deny",
                        "permissionDecisionReason": (
                            "Gate failed closed on a gated call: %s: %s" % (type(exc).__name__, exc)
                        ),
                    }
                }
            else:
                out = None
        else:
            sys.stderr.write("ledger write failed: %s: %s\n" % (type(exc).__name__, exc))
            out = None
    if out is not None:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main(sys.argv))
