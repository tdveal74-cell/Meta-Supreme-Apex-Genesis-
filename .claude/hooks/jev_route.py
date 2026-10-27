#!/usr/bin/env python3
"""
Ask Jev two questions about a tool call before it runs.

Ruled by Tee 2026-10-16 to wire it, and on 2026-10-17, on a card, "Hold it,
rebuild as allowlist". The first version scrubbed secret values out of the raw
call, and every scrubber misses something: Basic auth, Cookie headers, a value
under a field name nobody listed, and one long leaf that outran the hook's
timeout. This version never starts from the raw call. It assembles the outbound
text from a short list of allowed pieces and sends nothing else.

Jev is TypeSafe's typed decision model, called at POST
https://api.typesafe.ai/v1/systemone with a Bearer key. Each call asks two
independent noul questions in one request:

    better_tool  a dedicated tool (Read, Grep, Glob, Edit, Write) would do
                 this step better than the tool being called
    needs_human  the step changes something outside the repository or cannot
                 be undone

A noul is the probability of yes. At or above CONFIDENCE, needs_human asks Tee
and, failing that, better_tool denies the call with a reason. Every other
answer prints nothing and the normal permission flow runs. The hook never
prints allow, because allow would skip the permission system, so it can only
narrow what runs. With ENFORCE false it prints nothing at all and only records
what it would have decided. Enforcement is a separate ruling.

What leaves the container, and nothing else:

    the tool name
    Bash       each program name, each flag name (-X, --force) and never a
               flag's value, plus the file paths the call names
    Edit, Write, NotebookEdit
               the file path and the names of the input fields
    any other tool (every MCP tool)
               the names of the input fields, never a value

A piece outside the character class [A-Za-z0-9._/~-] is dropped, not escaped.
A path over MAX_PATH characters is dropped. The home directory is written as ~.
The whole text, tool name included, stops at MAX_OUT characters at a piece
boundary. Nothing is ever cut out of a longer string, because no longer string
is ever sent.

In a Bash command a word is read only as one of: the program (first word of a
command, or the word after sudo, env and the like), a flag, the target of a
redirect, or a path. A word that is none of those, a quoted string, a heredoc
body, an assignment like TOKEN=abc, a here-string and a comment are all read
past and never sent. A bare word counts as a path only when it names something
that exists on this machine, so a secret that happens to fit the character
class cannot pass as a path. A redirect target is a path by syntax and needs
no such test. A single dash flag is kept only when it is one to three letters,
because -phunter2 cannot be told from a cluster of flags, or when it is one of
the few find primaries in FIND_FLAGS. A flag's name has to be typed bare: a
quoted string that starts with a dash is a value, and so is whatever follows
the = in --name="value".

The shell reader models a small part of the shell and stops at the first thing
outside it. It does not guess at syntax it lacks, because a reader that guesses
reads data as commands and sends every program word: an array literal, a case
pattern, an operand of [[ ]] or $(( )), a word after a closing parenthesis and
the tail of a quoted string have all been read as programs by a reader that
guessed. What it models is in the Shell docstring. A construct it cannot model
ends the read through Shell.halt(): what was read before stays, nothing after it
is read, and nothing is sent that was guessed. A word is read whole, with every
quote, escape and expansion in it, before it is judged, and a program name is
taken from a whole word that is a plain piece and never from the tail of a
longer string.

Building the text is linear. Only the first MAX_SCAN characters of a command
are read, no regex has a nested or adjacent unbounded quantifier, and the
whole hook, request included, stays inside HOOK_BUDGET_S of its 5 second
timeout whatever the input. The request itself gets what is left of that
budget once RESERVE_S is set aside for start up and the ledger write.

It fails open. With no TYPESAFE_API_KEY, a refused host, a redirect, the
deadline passing, an HTTP error or a malformed answer, it prints nothing and
the call runs exactly as it would without this file. So a quiet hook proves
nothing. Each call it sees gets one row in .claude/ledger/jev-route.jsonl,
which is the only evidence that Jev decided anything. A deny is printed only
after its ledger row is written, because that row is what lets the identical
call through the second time. After BREAKER_ERRORS failed requests in a row it
stops asking for BREAKER_S seconds, so a dead vendor costs three deadlines and
not one per call.

The key is read from TYPESAFE_API_KEY and from nowhere else. It goes into one
request header and is never written to the ledger, to stderr or to any
message: an error row holds the exception's class name and never its text. The
ledger holds a hash of the raw call, so "the identical call" means identical
input, and no copy of the input.

CONFIDENCE is a starting guess, to be set from the ledger once real answers
exist. The request and answer shapes were taken from the first version, which
recorded checking them against TypeSafe's OpenAPI spec (version 0.2.0) and the
official typesafe-sdk 0.7.5 on 2026-10-16. This rebuild did not re-read the
spec, and no authenticated call has been made.
"""

from __future__ import annotations

import hashlib
import itertools
import json
import os
import re
import sys
import threading
import time
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timezone

ENDPOINT = "https://api.typesafe.ai/v1/systemone"
MODEL = "jev-latest"
CONFIDENCE = 0.8
HOOK_BUDGET_S = 2.5
RESERVE_S = 0.6
MAX_OUT = 2000
MAX_SCAN = 64 * 1024
MAX_STDIN = 8 * 1024 * 1024
MAX_PATH = 200
MAX_STATS = 64
MAX_FIELDS = 60
MAX_FIELD_LEN = 30
MAX_DIGITS = 4
MAX_NODES = 5000
MAX_FANOUT = 200
MAX_DEPTH = 8
MAX_NEST = 8
TAIL_BYTES = 256 * 1024
BREAKER_ERRORS = 3
BREAKER_S = 600
ENFORCE = False

STATE_NOTE = (
    "`tool_name` is the tool a coding agent is about to call. `tool_input` is an "
    "outline of its input and never holds a value: for a shell command it lists "
    "each program, each flag name and the files named, one command per line; for "
    "a file tool it gives `path` and the file, then `fields` and the input field "
    "names; for any other tool it gives `fields` and the input field names. The "
    "agent also has dedicated tools: Read reads a file, Grep searches file "
    "contents, Glob finds files by name, Edit changes part of a file and Write "
    "creates one."
)

QUESTIONS = {
    "better_tool": {
        "type": "noul",
        "instructions": STATE_NOTE + " Would one of those dedicated tools do this step better than `tool_name`?",
        "criteria": {
            "true": (
                "A dedicated tool does the same thing more directly, for example "
                "cat, head, grep, find or sed run through Bash only to read, "
                "search, list or edit files."
            ),
            "false": (
                "The step needs this tool: it runs a program, a test, a build, git, "
                "a network call, or a pipeline that no dedicated tool performs, or "
                "the tool already is the dedicated one."
            ),
        },
    },
    "needs_human": {
        "type": "noul",
        "instructions": STATE_NOTE + " Does this step change something outside the repository, or something that cannot be undone?",
        "criteria": {
            "true": (
                "It deploys, publishes, sends a message to a person, moves money, "
                "deletes or overwrites data outside the repository, force pushes, "
                "or changes a live service or its credentials."
            ),
            "false": (
                "It reads, or it changes only files in the working tree that git "
                "can restore, or it runs a local check."
            ),
        },
    },
}

# Every pattern here is one character class under at most one bounded or
# unbounded quantifier, so none can backtrack. test_jev_route.py parses each one
# and refuses a nested or adjacent unbounded quantifier.
PIECE = re.compile(r"[A-Za-z0-9._/~-]{1,200}")
TOOL_NAME = re.compile(r"[A-Za-z0-9._-]{1,120}")
PROGRAM = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,39}")
FIELD = re.compile(r"[A-Za-z][A-Za-z0-9_.-]{0,29}")
KEY_SHAPE = re.compile(r"[\x21-\x7e]+")
WORD_RUN = re.compile(r"[^ \t\r\n\f\v'\"\\$`;&|<>()]+")
DQ_SPECIAL = re.compile(r"[\"\\$`]")
# One character each, so no quantifier at all. They find the next character that
# ends or changes the reading of a region the reader skips without looking in.
ARITH_STOP = re.compile(r"[()'\"`\\]")
BRACE_STOP = re.compile(r"[}$'\"`\\{\n]")
ANSI_STOP = re.compile(r"[\\']")

WS = " \t\r\f\v"
SEPARATORS = "\n;&|<>()"
# The only words a command may start with that are not themselves the program.
# A case statement is not here: its patterns are words that look like commands,
# so the reader stops at it instead.
OPENERS = frozenset(("if", "then", "else", "elif", "do", "while", "until", "!", "{"))
CLOSERS = frozenset(("fi", "done", "esac", "}"))
HEADERS = frozenset(("for", "select", "function"))
# Programs whose next word is a program too. timeout and nice are left out on
# purpose: their next word is a number.
WRAPPERS = frozenset(("sudo", "doas", "env", "time", "nohup", "exec", "command", "builtin", "xargs", "watch"))
FIND_FLAGS = frozenset((
    "-name", "-iname", "-type", "-exec", "-execdir", "-ok", "-delete", "-maxdepth", "-mindepth",
    "-print", "-print0", "-mtime", "-mmin", "-size", "-path", "-regex", "-newer", "-perm", "-user",
    "-group", "-prune", "-empty",
))
PATH_FIELDS = {"Edit": ("file_path",), "Write": ("file_path",), "NotebookEdit": ("notebook_path",)}


def project_dir():
    return os.environ.get("CLAUDE_PROJECT_DIR") or os.getcwd()


def ledger_path():
    return os.path.join(project_dir(), ".claude", "ledger", "jev-route.jsonl")


def home_dir():
    """The home directory without a trailing slash, or "" when it is / or unknown."""
    home = os.path.expanduser("~")
    return "" if home in ("", "~") else home.rstrip("/")


# ------------------------------------------------------- the allowed pieces


def vet_path(raw, home):
    """A path piece with the home directory as ~, or None."""
    if not isinstance(raw, str) or not 0 < len(raw) <= MAX_PATH:
        return None
    if home and (raw == home or raw.startswith(home + "/")):
        raw = "~" + raw[len(home):]
    return raw if PIECE.fullmatch(raw) else None


def is_assignment(word):
    """NAME=, NAME+= and NAME[subscript]=, which set a variable and run nothing."""
    name, eq, _ = word.partition("=")
    if not eq:
        return False
    if name.endswith("+"):
        name = name[:-1]
    if name.endswith("]"):
        name, bracket, _ = name.partition("[")
        if not bracket:
            return False
    return name.isascii() and name.isidentifier()


def few_digits(name):
    """Names carry a few digits (python3, sha256). A long run of them is data."""
    return sum(ch.isdigit() for ch in name) <= MAX_DIGITS


def program_name(word):
    """The program a whole word names, or None. The whole word has to be a plain
    piece before its last path component is taken: a word with a space, a colon
    or an = in it is a string or an assignment, and its tail is not a program."""
    if not PIECE.fullmatch(word):
        return None
    base = word.rsplit("/", 1)[-1]
    return base if PROGRAM.fullmatch(base) and few_digits(base) else None


def flag_name(word):
    """The name of a flag, never its value, or None."""
    head = word.split("=", 1)[0]
    if head.startswith("--"):
        body = head[2:]
        ok = (0 < len(body) <= MAX_FIELD_LEN and body.isascii()
              and all(ch.isalnum() or ch == "-" for ch in body) and few_digits(body)
              and not body.startswith("-") and not body.endswith("-") and "--" not in body)
        return head if ok else None
    if head in FIND_FLAGS:
        return head
    body = head[1:]
    return head if 1 <= len(body) <= 3 and body.isascii() and body.isalpha() else None


class Outline:
    """The outbound text, one piece at a time, under a character budget. A piece
    that would not fit ends the text there, so the cut is at a piece boundary."""

    def __init__(self, budget):
        self.budget, self.size, self.full = budget, 0, False
        self.lines, self.line = [], []

    def add(self, piece):
        if self.full:
            return False
        cost = len(piece) + (1 if (self.line or self.lines) else 0)
        if self.size + cost > self.budget:
            self.full = True
            return False
        self.line.append(piece)
        self.size += cost
        return True

    def newline(self):
        if self.line:
            self.lines.append(self.line)
            self.line = []

    def mark(self):
        self.newline()
        return len(self.lines), self.size, self.full

    def rewind(self, mark):
        """Take back every piece added since the mark."""
        count, self.size, self.full = mark
        del self.lines[count:]
        self.line = []

    def text(self):
        self.newline()
        return "\n".join(" ".join(line) for line in self.lines)


class Shell:
    """One pass over a shell command. It reads words and decides what each one
    is, and only a program, a flag, a redirect target or an existing path is
    handed to the outline.

    It models a small part of the shell and stops at the first thing outside it:
    halt() drops the rest of the command, so what was read before it stays and
    nothing after it is guessed at. A reader that guesses at syntax it lacks
    reads data as commands, and every program word is sent. The parts it models
    are simple commands, pipelines, lists, if, while, until, for and select
    lists, brace groups and subshells, quotes and escapes, $( ), backticks and
    <( ), heredocs and here-strings, and it reads past $(( )), (( )), [[ ]],
    ${ }, $' ' and the literal of an array assignment without looking inside. A
    case statement, a function definition, an extglob group or a quote nested in
    a way it cannot follow ends the read."""

    def __init__(self, text, out, cwd, home):
        self.t, self.n, self.i = text, len(text), 0
        self.out, self.cwd, self.home = out, cwd, home
        self.stats = 0
        self.heredocs = []
        self.frames = []
        self.halted = False
        self.quoted_at = None
        self.reset()

    def reset(self):
        self.program = None
        self.wrapper = False
        self.skip = False
        self.ddash = False

    def saved(self):
        return self.program, self.wrapper, self.skip, self.ddash

    def restore(self, state):
        self.program, self.wrapper, self.skip, self.ddash = state

    def end_command(self):
        self.out.newline()
        self.reset()

    def halt(self):
        """Syntax the reader does not model. Everything after this is read past."""
        self.halted = True
        self.i = self.n
        return self.n

    def run(self):
        self.commands(None)
        self.out.newline()

    def commands(self, closer):
        """Commands up to the closer of the enclosing $( ), ( ) or pair of
        backticks, or to the end of the text at the top. True when the closer was
        found."""
        t, n = self.t, self.n
        while self.i < n and not self.out.full:
            i = self.i
            c = t[i]
            if c in WS:
                self.i += 1
            elif c == "\n":
                self.end_command()
                self.i += 1
                self.skip_heredocs()
            elif c == "#":
                j = t.find("\n", i)
                self.i = n if j < 0 else j
            elif c in ";&|":
                self.end_command()
                self.i += 1
            elif c == ")":
                if closer != ")":
                    self.halt()
                    return False
                self.i += 1
                return True
            elif c == "`" and "`" in self.frames:
                if closer != "`":
                    self.halt()
                    return False
                self.i += 1
                return True
            elif c == "(":
                self.paren()
            elif c in "<>":
                self.redirect()
            else:
                word = self.word()
                if self.i == i:
                    self.i += 1
                elif not (word.isdigit() and self.i < n and t[self.i] in "<>"):
                    self.take(word, self.quoted_at)
            if self.halted:
                return False
        return False

    def substitution(self, closer):
        """A command list inside $( ), ( ) or backticks, read with its own quote
        state. The command around it is put back afterwards. One that cannot be
        read to its closer sends nothing: a list that never closes is not known to
        be a list."""
        if len(self.frames) >= MAX_NEST:
            self.halt()
            return
        outer = self.saved()
        mark = self.out.mark()
        self.reset()
        self.frames.append(closer)
        found = self.commands(closer)
        self.frames.pop()
        self.out.newline()
        self.restore(outer)
        if not found:
            self.out.rewind(mark)
            self.halt()

    def paren(self):
        """A ( where a word does not start. Only a subshell at the start of a
        command is read; an array literal, an arithmetic command and a bare group
        are read past; anything else is syntax this reader does not model."""
        t, i = self.t, self.i
        prev = t[i - 1] if i else "\n"
        if prev == "=":
            self.i = self.skip_array(i + 1)
        elif prev not in WS and prev not in SEPARATORS:
            self.halt()
        elif t.startswith("((", i):
            j = self.skip_arith(i + 2)
            if j < 0:
                self.halt()
            else:
                self.i = j
                self.skip = True
        elif self.program is None and not self.skip:
            self.i = i + 1
            self.substitution(")")
            self.skip = True
        else:
            self.halt()

    def word(self):
        """The next word with its quotes and escapes resolved. An expansion is
        left as a literal $, which no piece rule accepts. self.quoted_at is the
        length of the plain text before the first quote, escape or expansion in the
        word, or None when the word has none."""
        t, n, i = self.t, self.n, self.i
        buf = []
        plain = 0
        quoted_at = None
        while i < n:
            c = t[i]
            if c in WS or c in SEPARATORS or (c == "`" and "`" in self.frames):
                break
            j = self.special(i, buf)
            if j is not None:
                if quoted_at is None:
                    quoted_at = plain
                i = j
                continue
            m = WORD_RUN.match(t, i)
            if m is None:
                i += 1
            else:
                buf.append(m.group())
                plain += m.end() - i
                i = m.end()
        self.i = min(i, n)
        self.quoted_at = quoted_at
        return "".join(buf)

    def special(self, i, buf):
        """A quote, an escape or an expansion starting at i. Its text goes into
        buf, an expansion as a literal $, and the index after it comes back. None
        when t[i] is a plain character."""
        t, n = self.t, self.n
        c = t[i]
        if c == "\\":
            if "`" in self.frames:
                return self.halt()
            if i + 1 < n and t[i + 1] != "\n":
                buf.append(t[i + 1])
            return i + 2
        if c == "'":
            j = t.find("'", i + 1)
            if j < 0:
                buf.append(t[i + 1:])
                return n
            buf.append(t[i + 1:j])
            return j + 1
        if c == '"':
            return self.double(i + 1, buf)
        if c == "`":
            if "`" in self.frames:
                return self.halt()
            self.i = i + 1
            self.substitution("`")
            buf.append("$")
            return self.i
        if c != "$":
            return None
        buf.append("$")
        nxt = t[i + 1:i + 2]
        if nxt == "(":
            if t.startswith("((", i + 1):
                j = self.skip_arith(i + 3)
                return self.halt() if j < 0 else j
            self.i = i + 2
            self.substitution(")")
            return self.i
        if nxt == "{":
            return self.skip_brace(i)
        if nxt == "'":
            return self.skip_ansi(i)
        return i + 1

    def double(self, i, buf):
        """The inside of a double quoted string, from after the opening quote to
        after the closing one. A $( ) or pair of backticks inside it is a command
        list with its own quotes, so it is read as one and not as text."""
        t, n = self.t, self.n
        while i < n:
            m = DQ_SPECIAL.search(t, i)
            if m is None:
                buf.append(t[i:])
                return n
            j = m.start()
            buf.append(t[i:j])
            c = t[j]
            if c == '"':
                return j + 1
            if c == "\\":
                if "`" in self.frames:
                    return self.halt()
                nxt = t[j + 1:j + 2]
                if nxt in ("$", "`", '"', "\\"):
                    buf.append(nxt)
                elif nxt != "\n":
                    buf.append("\\" + nxt)
                i = j + 2
            elif c == "`" or t.startswith(("$(", "${"), j):
                i = self.special(j, buf)
                if self.halted:
                    return n
            else:
                buf.append(c)
                i = j + 1
        return n

    def skip_arith(self, i):
        """From after (( or $(( to after the matching )), or -1. A quote, an escape
        or a backtick inside, or a ) that does not close it, is not modelled."""
        t, n = self.t, self.n
        depth = 0
        while i < n:
            m = ARITH_STOP.search(t, i)
            if m is None:
                return -1
            c = m.group()
            i = m.end()
            if c == "(":
                depth += 1
            elif c != ")":
                return -1
            elif depth:
                depth -= 1
            elif t.startswith(")", i):
                return i + 1
            else:
                return -1
        return -1

    def skip_brace(self, i):
        """From the $ of ${ to after the } that closes it. Only a plain body is
        read: a quote, an escape, a nested expansion or a newline ends the read."""
        t = self.t
        j = i + 2
        while True:
            m = BRACE_STOP.search(t, j)
            if m is None:
                return self.halt()
            if m.group() == "}":
                return m.end()
            if m.group() != "$" or t[m.end():m.end() + 1] in ("(", "{", "'", '"'):
                return self.halt()
            j = m.end()

    def skip_ansi(self, i):
        """From the $ of $' to after the closing quote, a \\' inside not closing it."""
        t = self.t
        j = i + 2
        while True:
            m = ANSI_STOP.search(t, j)
            if m is None:
                return self.halt()
            if m.group() == "'":
                return m.end()
            j = m.end() + 1

    def skip_array(self, i):
        """From after the ( of NAME=( to after its ). Quotes and expansions inside
        are read as they are in a word, so a ) in one does not close it."""
        t, n = self.t, self.n
        while i < n:
            c = t[i]
            if c == ")":
                return i + 1
            if c == "(" or (c == "#" and t[i - 1] in WS + "\n("):
                return self.halt()
            j = self.special(i, [])
            if self.halted:
                return n
            i = i + 1 if j is None else j
        return self.halt()

    def skip_test(self, i):
        """From after [[ to after the ]] that closes it. Operators and a regular
        expression can hold ( ) | & < >, so only the closing ]] word ends it."""
        t, n = self.t, self.n
        boundary = False
        while i < n:
            if boundary and t.startswith("]]", i) and t[i + 2:i + 3] in ("", " ", "\t", "\n", ";", "&", "|", ")"):
                return i + 2
            j = self.special(i, [])
            if self.halted:
                return n
            if j is None:
                boundary = t[i] in WS + "\n"
                i += 1
            else:
                boundary = False
                i = j
        return self.halt()

    def redirect(self):
        t, n, i = self.t, self.n, self.i
        two = t[i:i + 2]
        if t.startswith("<<<", i):
            kind, width = "operand", 3
        elif t.startswith("<<-", i):
            kind, width = "heredoc-", 3
        elif two == "<<":
            kind, width = "heredoc", 2
        elif two in ("<(", ">("):
            self.i = i + 2
            self.substitution(")")
            self.take("$")
            return
        elif two in (">&", "<&"):
            kind, width = "operand", 2
        elif two in (">>", ">|", "<>"):
            kind, width = "path", 2
        else:
            kind, width = "path", 1
        self.i = i + width
        while self.i < n and t[self.i] in WS:
            self.i += 1
        if self.i >= n or t[self.i] in SEPARATORS:
            return
        start = self.i
        operand = self.word()
        if self.halted:
            return
        if self.i == start:
            self.i += 1
        elif kind == "path":
            piece = vet_path(operand, self.home)
            if piece:
                self.out.add(piece)
        elif kind != "operand":
            self.heredocs.append((operand, kind == "heredoc-"))

    def skip_heredocs(self):
        pending, self.heredocs = self.heredocs, []
        for delimiter, tabs in pending:
            while self.i < self.n:
                j = self.t.find("\n", self.i)
                end = self.n if j < 0 else j
                line = self.t[self.i:end]
                self.i = self.n if j < 0 else end + 1
                if (line.lstrip("\t") if tabs else line) == delimiter:
                    break

    def test_expression(self):
        """A [[ just read: read past the expression to its ]] and past whatever
        follows it on the command."""
        j = self.skip_test(self.i)
        if not self.halted:
            self.i = j
            self.skip = True

    def take(self, word, quoted_at=None):
        """One resolved word. quoted_at is where its first quote, escape or
        expansion begins, as word() reports it."""
        if self.skip:
            return
        if self.program is None:
            if word in OPENERS or word in CLOSERS:
                return
            if word in HEADERS:
                self.skip = True
                return
            if word == "case":
                self.halt()
                return
            if word == "[[" and quoted_at is None:
                self.test_expression()
                return
            if is_assignment(word):
                return
            self.program = word
            name = program_name(word)
            if name:
                self.out.add(name)
            self.wrapper = name in WRAPPERS
            return
        if self.wrapper:
            if is_assignment(word):
                return
            if word == "[[" and quoted_at is None:
                # time [[ a > b ]] is a test, and sudo [[ ... is not a command at all.
                self.test_expression()
                return
            if not word.startswith("-"):
                name = program_name(word)
                if name:
                    self.out.add(name)
                self.wrapper = name in WRAPPERS
                return
            self.wrapper = False
        if word == "--":
            self.ddash = True
        elif word.startswith("-") and len(word) > 1 and not self.ddash:
            # A flag's name is typed bare. A quoted string that starts with a dash
            # is a value, and so is anything after the = whatever its quoting.
            eq = word.find("=")
            if quoted_at is None or (eq >= 0 and quoted_at > eq):
                name = flag_name(word)
                if name:
                    self.out.add(name)
            else:
                self.positional(word)
        else:
            self.positional(word)

    def positional(self, word):
        """A bare word is a path only if it names something that exists."""
        if self.stats >= MAX_STATS or len(word) > MAX_PATH or not PIECE.fullmatch(word):
            return
        self.stats += 1
        if word == "~" or word.startswith("~/"):
            if not self.home:
                return
            full = self.home + word[1:]
        else:
            full = os.path.join(self.cwd, word)
        if os.path.lexists(full):
            piece = vet_path(word, self.home)
            if piece:
                self.out.add(piece)


def shell_pieces(command, out, cwd, home):
    text = command[:MAX_SCAN]
    if len(command) > MAX_SCAN:
        cut = max(text.rfind(ch) for ch in " \t\n;|&")
        text = text[:cut] if cut > 0 else ""
    Shell(text, out, cwd, home).run()


def field_names(value):
    """The dict keys of a JSON value that are plain names, shallowest first.
    Never a value. A key that is long, or carries more than MAX_DIGITS digits,
    or leaves the character class, is data and is dropped."""
    names, seen = [], set()
    stack, visited = [(value, 0)], 0
    while stack and visited < MAX_NODES and len(names) < MAX_FIELDS:
        node, depth = stack.pop()
        visited += 1
        if isinstance(node, dict):
            children = []
            for key, child in itertools.islice(node.items(), MAX_FANOUT):
                if (isinstance(key, str) and key not in seen and len(key) <= MAX_FIELD_LEN
                        and FIELD.fullmatch(key) and few_digits(key)):
                    seen.add(key)
                    names.append(key)
                children.append(child)
            if depth < MAX_DEPTH:
                stack.extend((child, depth + 1) for child in reversed(children))
        elif isinstance(node, (list, tuple)) and depth < MAX_DEPTH:
            children = list(itertools.islice(node, MAX_FANOUT))
            stack.extend((child, depth + 1) for child in reversed(children))
    return names[:MAX_FIELDS]


def build_text(name, tool_input, cwd, home):
    """The whole outbound text for one call, from allowed pieces only."""
    out = Outline(MAX_OUT - len(name) - 1)
    if name.lower() == "bash":
        command = tool_input.get("command") if isinstance(tool_input, dict) else None
        if isinstance(command, str):
            shell_pieces(command, out, cwd, home)
        return out.text()
    if isinstance(tool_input, dict):
        for field in PATH_FIELDS.get(name, ()):
            piece = vet_path(tool_input.get(field), home)
            if piece:
                out.add("path")
                out.add(piece)
                out.newline()
    names = field_names(tool_input)
    if names and out.add("fields"):
        for field in names:
            if not out.add(field):
                break
    return out.text()


def input_digest(name, tool_input):
    """A hash of the raw call, so the identical call is identical to the byte.
    It is kept in the ledger and never sent."""
    try:
        raw = json.dumps(tool_input, sort_keys=True, default=str)
    except (TypeError, ValueError, RecursionError):
        raw = repr(tool_input)
    return hashlib.sha256((name + "\0" + raw).encode("utf-8", "surrogatepass")).hexdigest()[:16]


# ----------------------------------------------------------- the request


def endpoint_ok(url):
    """HTTPS only, except plain HTTP to loopback for the test stub."""
    parsed = urllib.parse.urlparse(url)
    if parsed.username or parsed.password or parsed.query or parsed.fragment:
        return False
    if parsed.scheme == "https" and parsed.hostname:
        return True
    return parsed.scheme == "http" and parsed.hostname in ("127.0.0.1", "localhost", "::1")


class _NoRedirect(urllib.request.HTTPRedirectHandler):
    def redirect_request(self, req, fp, code, msg, headers, newurl):
        raise urllib.error.HTTPError(req.full_url, code, "redirect refused", headers, fp)


_OPENER = urllib.request.build_opener(_NoRedirect)


def ask_jev(body, key, endpoint, timeout):
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Authorization": "Bearer " + key, "Content-Type": "application/json"},
        method="POST",
    )
    with _OPENER.open(req, timeout=timeout) as resp:
        return json.loads(resp.read(1 << 20).decode("utf-8"))


def ask_within(body, key, endpoint, deadline):
    """The request, DNS and every read included, inside one deadline."""
    box = {}

    def work():
        try:
            box["response"] = ask_jev(body, key, endpoint, deadline)
        except BaseException as exc:
            box["error"] = exc

    worker = threading.Thread(target=work, daemon=True)
    worker.start()
    worker.join(deadline)
    if worker.is_alive():
        raise TimeoutError("no answer inside %.1fs" % deadline)
    if "error" in box:
        raise box["error"]
    return box["response"]


def read_answers(response):
    """(better_tool, needs_human, model), or ValueError on any shape it does not know."""
    model = response.get("model")
    if not isinstance(model, str) or not model.startswith("jev-"):
        raise ValueError("model is not a jev model")
    answers = response.get("answers") or {}
    values = []
    for name in ("better_tool", "needs_human"):
        answer = answers.get(name) or {}
        p = answer.get("noul")
        if answer.get("type") != "noul" or isinstance(p, bool) or not isinstance(p, (int, float)) or not 0 <= p <= 1:
            raise ValueError("bad %s answer" % name)
        values.append(float(p))
    return values[0], values[1], model


def decision_for(better_tool, needs_human):
    if needs_human >= CONFIDENCE:
        return "ask"
    if better_tool >= CONFIDENCE:
        return "deny"
    return None


# ------------------------------------------------------------ the ledger


def ledger_tail():
    """The newest rows, read from at most the last TAIL_BYTES of the ledger."""
    try:
        with open(ledger_path(), "rb") as fh:
            fh.seek(0, os.SEEK_END)
            size = fh.tell()
            fh.seek(max(0, size - TAIL_BYTES))
            data = fh.read()
    except OSError:
        return []
    lines = data.split(b"\n")
    if size > TAIL_BYTES:
        lines = lines[1:]
    rows = []
    for line in lines:
        try:
            row = json.loads(line)
        except ValueError:
            continue
        if isinstance(row, dict):
            rows.append(row)
    return rows


def denied_before(rows, session, digest):
    """True when this session was denied this exact call, enforced. An ask is
    never a pass: the same call is asked again."""
    return any(row.get("session") == session and row.get("input_sha") == digest
               and row.get("decision") == "deny" and row.get("enforced") is True for row in rows)


def breaker_open(rows, now):
    """True after BREAKER_ERRORS failed requests in a row, the newest of them
    under BREAKER_S old. A row with no latency made no request, so it neither
    adds to the streak nor ends it."""
    failures, newest = 0, None
    for row in reversed(rows):
        if "latency_ms" not in row:
            continue
        if row.get("outcome") != "error":
            break
        failures += 1
        if newest is None:
            newest = row.get("ts")
        if failures >= BREAKER_ERRORS:
            break
    if failures < BREAKER_ERRORS:
        return False
    try:
        then = datetime.strptime(newest, "%Y-%m-%dT%H:%M:%SZ").replace(tzinfo=timezone.utc)
    except (TypeError, ValueError):
        return False
    return 0 <= (now - then).total_seconds() < BREAKER_S


def write_row(row):
    """True only when the row is on disk."""
    try:
        path = ledger_path()
        os.makedirs(os.path.dirname(path), exist_ok=True)
        with open(path, "a", encoding="utf-8") as fh:
            fh.write(json.dumps(row, sort_keys=True) + "\n")
        return True
    except Exception as exc:
        sys.stderr.write("jev_route: ledger write failed: %s\n" % type(exc).__name__)
        return False


def output(decision, tool_name, p):
    if decision == "deny":
        reason = (
            "Jev (p=%.2f) reads this %s call as one a dedicated tool does better. "
            "Use Read, Grep, Glob, Edit or Write for this step. If none of them "
            "can do it, run the same call again: Jev denies an identical call "
            "only once per session." % (p, tool_name)
        )
    else:
        reason = (
            "Jev (p=%.2f) reads this %s call as changing something outside the "
            "repository or something that cannot be undone." % (p, tool_name)
        )
    return {
        "hookSpecificOutput": {
            "hookEventName": "PreToolUse",
            "permissionDecision": decision,
            "permissionDecisionReason": reason,
        }
    }


def stamp(now):
    return now.strftime("%Y-%m-%dT%H:%M:%SZ")


def run(payload, key=None, endpoint=None, now=None, timeout=None, started=None):
    """Returns the JSON object to print on stdout, or None to print nothing."""
    started = time.monotonic() if started is None else started
    now = now or datetime.now(timezone.utc)
    endpoint = endpoint or ENDPOINT
    key = (key or "").strip()
    if not isinstance(payload, dict) or not isinstance(payload.get("tool_name"), str) or not payload["tool_name"]:
        write_row({"ts": stamp(now), "enforced": ENFORCE, "decision": "none", "outcome": "bad_input"})
        return None
    name = payload["tool_name"]
    session = str(payload.get("session_id") or "")[:100]
    row = {"ts": stamp(now), "session": session, "tool": name[:200], "enforced": ENFORCE, "decision": "none"}

    if not key:
        row["outcome"] = "no_key"
        write_row(row)
        return None
    if not KEY_SHAPE.fullmatch(key):
        row.update(outcome="error", error="key has characters a header cannot carry, nothing sent")
        write_row(row)
        return None
    if not endpoint_ok(endpoint):
        row.update(outcome="error", error="endpoint refused")
        write_row(row)
        return None
    if not TOOL_NAME.fullmatch(name):
        row.update(outcome="bad_input", error="tool name outside the allowed characters, nothing sent")
        write_row(row)
        return None

    cwd = payload.get("cwd")
    cwd = cwd if isinstance(cwd, str) and os.path.isabs(cwd) else project_dir()
    tool_input = payload.get("tool_input")
    text = build_text(name, tool_input, cwd, home_dir())
    digest = input_digest(name, tool_input)
    row["input_sha"] = digest
    row["sent_chars"] = len(name) + len(text)

    rows = ledger_tail()
    if denied_before(rows, session, digest):
        row["outcome"] = "repeat_pass"
        write_row(row)
        return None
    if breaker_open(rows, now):
        row["outcome"] = "breaker_open"
        write_row(row)
        return None

    body = {
        "model": MODEL,
        "state": {"tool_name": name, "tool_input": text},
        "questions": QUESTIONS,
    }
    if timeout is None:
        timeout = HOOK_BUDGET_S - RESERVE_S - (time.monotonic() - started)
    timeout = max(0.1, timeout)
    began = time.monotonic()
    try:
        better_tool, needs_human, model = read_answers(ask_within(body, key, endpoint, timeout))
    except urllib.error.HTTPError as exc:
        row.update(outcome="error", error="HTTP %d" % exc.code)
    except Exception as exc:
        row.update(outcome="error", error=type(exc).__name__)
    else:
        row.update(outcome="answered", better_tool=better_tool, needs_human=needs_human, model=model)
        decision = decision_for(better_tool, needs_human)
        if decision:
            row["decision"] = decision
    row["latency_ms"] = int((time.monotonic() - began) * 1000)

    persisted = write_row(row)
    if row["decision"] == "none" or not ENFORCE:
        return None
    if row["decision"] == "deny" and not persisted:
        return None
    p = row["needs_human"] if row["decision"] == "ask" else row["better_tool"]
    return output(row["decision"], name, p)


def main():
    started = time.monotonic()
    try:
        raw = sys.stdin.read(MAX_STDIN + 1)
        payload = json.loads(raw) if len(raw) <= MAX_STDIN else None
    except Exception:
        payload = None
    try:
        out = run(payload, key=os.environ.get("TYPESAFE_API_KEY", ""), started=started)
    except Exception as exc:
        sys.stderr.write("jev_route: %s\n" % type(exc).__name__)
        write_row({"ts": stamp(datetime.now(timezone.utc)), "enforced": ENFORCE, "decision": "none",
                   "outcome": "crash", "error": type(exc).__name__})
        out = None
    if out is not None:
        sys.stdout.write(json.dumps(out))
    return 0


if __name__ == "__main__":
    sys.exit(main())
