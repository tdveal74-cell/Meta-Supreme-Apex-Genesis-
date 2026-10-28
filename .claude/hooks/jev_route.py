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
https://api.typesafe.ai/v1/systemone. This file holds no key. Each call asks two
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

The input fields are the keys of the input object itself and no others. A key
below the top is the caller's data: a map keyed by ids, names or tokens, a
header, an environment variable. The character class cannot tell one from a
field name, so none of them leaves. Ruled by Tee 2026-10-28 on a card: Top-level
only.

A program name leaves only when it is a command on this machine. Ruled by Tee
2026-10-28 on a card: Known commands only. Four verify rounds against the shell
reader each found a new way for a value to leave as a "program name", and the
reader cannot be made to model the shell perfectly. So a word the reader takes
for a program is handed out only when it is a bash builtin or reserved word from
BASH_WORDS, or a name the hook process's PATH resolves to an executable file, or,
for a word with a / in it, an existing executable file. Any other word is
dropped, and so is every flag of the same simple command, because a word the
reader wrongly took for a program carries its neighbours with it. A reader
mistake that takes data for a program then costs a word and does not leak one.
The gate does not reach a redirect target, which is a path by syntax and is sent
untested, so there the only defence is the reader itself stopping at what it
cannot model. This is a gate on what the reader hands out and replaces none of
its defences. Nothing is executed to find
out: a lookup is a stat on a path, BASH_WORDS is a list pinned in this file, and
bash is never run. A word over MAX_WORD characters is not looked up, a name is
looked up once per call, and a call stops looking after MAX_LOOKUPS distinct
names, so the names after the cap are dropped. The cost is fidelity: Jev sees
less of a script or a tool that is not installed where the hook runs. The edge is
a secret that is itself the name of an installed command, which still leaves.

A piece outside the character class [A-Za-z0-9._/~-] is dropped, not escaped.
A path over MAX_PATH characters is dropped. /dev/tcp/HOST/PORT and
/dev/udp/HOST/PORT are sockets and not paths, and are dropped. The home directory
is written as ~.
The whole text, tool name included, stops at MAX_OUT characters at a piece
boundary. Nothing is ever cut out of a longer string, because no longer string
is ever sent.

In a Bash command a word is read only as one of: the program (first word of a
command, or the word after sudo, env and the like), a flag, the target of a
redirect, or a path. NAME=value before the program is skipped only after env,
sudo, watch and the reserved word time. After nohup, exec, command, builtin,
xargs, doas, and time typed after an assignment, a redirect or a quote (then it
is /usr/bin/time), NAME=value is the name of the program to run, and the word
after it is an argument. A word that is none of those, a quoted string, a heredoc
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
longer string. A word the read stopped inside is a piece of a word and is never
judged: that covers a quote that never closes, an escape the text ends on and
the cut at MAX_SCAN. An assignment is one only when its name and its = are typed
bare, and a reserved word only when it is typed bare and nothing was read ahead
of it on its command, so "FOO=bar", \\if, FOO=bar if and > f if are each a command
name and the word after is its argument. &> and &>> are one redirect. A carriage
return is part of a word, as it is in bash. A line continuation is not there:
bash removes it before it reads a token, so the reader steps over it between
words, joins what is on both sides of it inside a word and counts it as no quote,
and a program, a keyword or an assignment split or preceded by one is still that.
A $ followed by one inside double quotes ends the read, because whether the $
opens an expansion depends on the character bash sees after the pair is gone.
A bare case ends the read wherever it stands, because the words after a case
pattern are data that look like commands, and so does a bare [[ that does not
begin a command or follow the reserved word time: read there it is an argument
(echo [[), or the reader has lost its place, and the text after it is not an
expression. A [[ that does begin a command is read to its ]] without looking in,
except that a $( ) or a pair of backticks is read as the command list it is, and
a # that begins a word is a comment, which runs nothing. The ]] is the first one
that is a word by itself, as bash has it: after a blank or a newline and before a
blank, a newline, ; & | ) or a < or > that does not open <( or >(, and a line
continuation counts as nothing, so ] then a continuation then ] is the word and a
continuation neither ends the blank before a ]] or a # nor hides a comment. A ]]
glued to a parenthesis ends the read, because it is the end of a group or the end
of a regular expression ([[ a =~ (b)]] never closes there), and so does one before
a ( or a <( or a >(. A reader that closed on fewer of these than bash does would go
on to a later ]] that is data, a here-document body or a quoted string, and read
code there. $$ is the process id: a
( or a { after the pair is text. A $( ), a <( ) and a pair of backticks are parsed
apart from the command around them, so a here-document the outer command waits
for does not take its body from a newline inside one, and one the list leaves
pending when it closes ends the read. Inside one, bash finds where the
substitution ends before it parses what is in it, and a here-document body does
not hide the end: a body line that begins with the delimiter and goes on, E) or
E ) or E) # c, ends the here-document and the substitution together, and inside
backticks any closing backtick in a body cuts it. This reader ends a body only at
a line that is the delimiter, so it would go on to a later line that is the
delimiter in other data and read what follows as code. A body line inside a
substitution that begins with the delimiter and is not it, and any body line with
a backtick in it inside backticks, ends the read. A plain subshell does neither.
A subshell is part of the outer parse. A
here-document delimiter is literal text: it is not resolved, and one with an
expansion in it ends the read. When it is typed bare the body is expanded, so a
body line that ends in an odd number of backslashes is joined to the next one
before it is compared with the delimiter, as bash does. A delimiter that runs
into <( or >( ends the read as well: bash reads those two characters into the
word, nothing in a delimiter is run, and this reader would run what is inside.
Bash reads a backtick body in two steps, cutting it at the closing backtick and
undoing its backslashes, and only then reading words. The reader does neither, so
inside backticks a comment, a backslash in an ANSI-C string and a here-document
line that ends in a backslash end the read: where the comment ends, where the
string closes and which lines continue are not what the text shows. Where a
command begins, NAME[ is the head of an array assignment and bash takes the word
up to the matching ], blanks and operators included, so m[k >f ]=1 is one word
and runs nothing. The reader reads such a word only when the ] comes before a
blank, an operator, a quote, an escape or an expansion other than $NAME, and
otherwise ends the read. The name and the [ are found with line continuations
taken out, so a, a continuation and [k >f ]=1 is that word too. A line
continuation inside an operator, a function
definition, a coprocess, the legacy $[ ] arithmetic and a subshell after an
assignment or a redirect are not modelled and end the read.

Bash reads aliases at parse time, so after shopt -s expand_aliases and alias
foo='cat <<EOF' the lines after a line that holds only foo are data to bash, and
this reader reads text and not the state the shell has built by running the lines
before. What an alias is cannot be known statically, so the read ends at a word
that names expand_aliases or BASH_ALIASES, at the word alias wherever it is typed,
as a program, as an argument (eval alias f=g, command -p alias) or inside a string
(eval "x=1; alias f=g"), and at an expansion handed to shopt, which may be that
option name. unalias, aliases, alias.co and --alias are other words. The edge: an
alias that a profile or a file the command sources defines, one the command writes
with a here-document and then sources included, is not in the text, and nothing
here sees it.

Building the text is linear. Only the first MAX_SCAN characters of a command
are read, no regex has a nested or adjacent unbounded quantifier, and the
whole hook, request included, stays inside HOOK_BUDGET_S of its 5 second
timeout whatever the input. The request itself gets what is left of that
budget once RESERVE_S is set aside for start up and the ledger write.

It fails open. With SEND false, a refused host, a redirect, the deadline
passing, an HTTP error or a malformed answer, it prints nothing and the call
runs exactly as it would without this file. So a quiet hook proves nothing. Each
call it sees gets one row in .claude/ledger/jev-route.jsonl, which is the only
evidence that Jev decided anything. A deny is printed only after its ledger row
is written, because that row is what lets the identical call through the second
time. After BREAKER_ERRORS failed requests in a row it stops asking for
BREAKER_S seconds, so a dead vendor costs three deadlines and not one per call.

SEND gates every request. While it is False the hook makes no request, opens no
socket and writes an off row for each call it sees. Turning it on is Tee's
ruling and a one line commit, as ENFORCE is.

The hook holds no key. It reads none from any environment variable and sends no
Authorization header of its own. The TypeSafe key is a network secret of the
cloud environment, and the agent proxy adds it to requests for api.typesafe.ai,
so the container never holds it. That means the request has to go through the
proxy the environment sets and not around it: the opener is built for each
request with ProxyHandler(), which reads HTTPS_PROXY and NO_PROXY from the
environment, the TLS context is the default one, which trusts SSL_CERT_FILE, and
the one thing the opener changes is that a redirect is refused. A proxy that does
not add the header gets HTTP 401 from the API. That is an error row, the call
runs as it would without this file, and three in a row open the breaker. An error
row holds the exception's class name and never its text. The ledger holds a hash
of the raw call, so "the identical call" means identical input, and no copy of
the input.

CONFIDENCE is a starting guess, to be set from the ledger once real answers
exist. The request and answer shapes were taken from the first version, which
recorded checking them against TypeSafe's OpenAPI spec (version 0.2.0) and the
official typesafe-sdk 0.7.5 on 2026-10-16. This rebuild did not re-read the
spec, and no authenticated request has been made.
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
MAX_WORD = 64
MAX_LOOKUPS = 128
MAX_FIELDS = 60
MAX_FIELD_LEN = 30
MAX_DIGITS = 4
MAX_FANOUT = 200
MAX_NEST = 8
TAIL_BYTES = 256 * 1024
BREAKER_ERRORS = 3
BREAKER_S = 600
ENFORCE = False
SEND = False

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
WORD_RUN = re.compile(r"[^ \t\n'\"\\$`;&|<>()]+")
DQ_SPECIAL = re.compile(r"[\"\\$`]")
# One character each, so no quantifier at all. They find the next character that
# ends or changes the reading of a region the reader skips without looking in.
ARITH_STOP = re.compile(r"[()'\"`\\]")
BRACE_STOP = re.compile(r"[}$'\"`\\{\n]")
ANSI_STOP = re.compile(r"[\\']")
# The next character in an array subscript that ends or changes the reading of the
# word, and the characters of a NAME. See Shell.subscript_closes() and
# Shell.array_head().
SUBSCRIPT_STOP = re.compile(r"[\[\]\t \n;&|<>()'\"\\$`]")
NAME_START = frozenset("ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz_")
NAME_CHARS = NAME_START | frozenset("0123456789")
# The word alias on its own, in a word or in a string a word holds (eval "x=1; alias
# f=g"). A letter, a digit, _, . or - on either side makes it part of another name:
# unalias, aliases, alias.co and --alias are not it. No quantifier at all.
ALIAS_WORD = re.compile(r"(?<![\w.-])alias(?![\w.-])")
# Bash reads these two as the start of a process substitution wherever a word is
# being read, a here-document delimiter included. See Shell.redirect().
PROCESS_OPENERS = ("<(", ">(")

# Bash splits words at a space or a tab and at a metacharacter. A carriage
# return, a form feed and a vertical tab are ordinary characters inside a word.
WS = " \t"
SEPARATORS = "\n;&|<>()"
# The only words a command may start with that are not themselves the program.
# A case statement is not here: its patterns are words that look like commands,
# so the reader stops at it instead.
OPENERS = frozenset(("if", "then", "else", "elif", "do", "while", "until", "!", "{"))
CLOSERS = frozenset(("fi", "done", "esac", "}"))
HEADERS = frozenset(("for", "select"))
# A function definition and a coprocess hold a command list the reader does not
# open, so it stops at either one typed at the start of a command.
UNMODELLED = frozenset(("function", "coproc"))
# Programs whose next word is a program too. timeout and nice are left out on
# purpose: their next word is a number.
WRAPPERS = frozenset(("sudo", "doas", "env", "time", "nohup", "exec", "command", "builtin", "xargs", "watch"))
# Of those, the ones that take NAME=value words before the program: sudo, env and
# watch do, and so does the reserved word time. For nohup, exec, command, builtin,
# xargs, doas and the program /usr/bin/time, NAME=value is the program's name, it
# fails, and the word after it is only an argument.
ASSIGNING = frozenset(("sudo", "env", "watch"))
# Bash opens a socket for a redirect to these two, so what follows is a host and a
# port, never a file.
SOCKET_PATHS = ("dev/tcp/", "dev/udp/")
FIND_FLAGS = frozenset((
    "-name", "-iname", "-type", "-exec", "-execdir", "-ok", "-delete", "-maxdepth", "-mindepth",
    "-print", "-print0", "-mtime", "-mmin", "-size", "-path", "-regex", "-newer", "-perm", "-user",
    "-group", "-prune", "-empty",
))
PATH_FIELDS = {"Edit": ("file_path",), "Write": ("file_path",), "NotebookEdit": ("notebook_path",)}

# The words bash itself runs, taken from this container's
#     bash -c 'compgen -b; compgen -k'
# which is bash 5.2.21(1)-release, on 2026-10-28: 61 builtins, then 22 reserved
# words. Bash is never run at hook time, so the list is pinned here and a test
# compares it with the local bash when that is the same version. A name outside
# this list is a command only if PATH resolves it or it is an existing file.
BASH_VERSION_PINNED = "5.2.21(1)-release"
BASH_WORDS_TAKEN = "2026-10-28"
BASH_BUILTINS = tuple((
    ". : [ alias bg bind break builtin caller cd command compgen complete compopt continue declare dirs "
    "disown echo enable eval exec exit export false fc fg getopts hash help history jobs kill let local "
    "logout mapfile popd printf pushd pwd read readarray readonly return set shift shopt source suspend "
    "test times trap true type typeset ulimit umask unalias unset wait"
).split())
BASH_RESERVED = tuple((
    "if then else elif fi case esac for select while until do done in function time { } ! [[ ]] coproc"
).split())
BASH_WORDS = frozenset(BASH_BUILTINS + BASH_RESERVED)


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
    """A path piece with the home directory as ~, or None. /dev/tcp/HOST/PORT and
    /dev/udp/HOST/PORT are not paths: bash connects to the host, and the text
    after the prefix is a destination, which the character class cannot tell
    from a file name."""
    if not isinstance(raw, str) or not 0 < len(raw) <= MAX_PATH:
        return None
    if raw.startswith("/") and raw.lstrip("/").startswith(SOCKET_PATHS):
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


def assignment(word, quoted_at):
    """is_assignment, with the name and the = typed bare. "A=1", \\A=1 and A"="1
    are command names in bash, and the word after one is its argument. So is a
    name with a quote or an expansion in its subscript, which costs a program name
    shown to Jev and no secrecy. quoted_at is where the word's first quote, escape
    or expansion begins, as Shell.word() reports it."""
    return is_assignment(word) and (quoted_at is None or quoted_at > word.index("="))


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


def is_executable(path):
    """An existing executable file. It is looked at and never run."""
    return os.path.isfile(path) and os.access(path, os.X_OK)


def search_path():
    """The directories of this process's PATH, in order, without the empty entries
    that bash reads as the current directory. An unset PATH is the platform's
    default, as it is for shutil.which."""
    raw = os.environ.get("PATH")
    return [d for d in (os.defpath if raw is None else raw).split(os.pathsep) if d]


def wrapper_kind(name, keyword=False):
    """How the word after a program is read. False when the program runs nothing
    else. "plain" when the next word that is not a flag is a program. "assigns"
    when NAME=value words may come first: env, sudo and watch. "time" for the
    reserved word time, which takes them too and after which a command begins
    again, so a [[ there is a test. keyword is True only for time typed bare as
    the first word of a command: /usr/bin/time, which it is after an assignment,
    a redirect or a quote, is a plain wrapper whose NAME=value is the program."""
    if keyword:
        return "time"
    if name in ASSIGNING:
        return "assigns"
    return "plain" if name in WRAPPERS else False


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
    <( ), redirects including &> and &>>, heredocs and here-strings, and it
    reads past $(( )), (( )), [[ ]], ${ }, $' ' and the literal of an array
    assignment without looking inside. A case statement, a [[ that does not
    begin a command, a function definition, a coprocess, an extglob group, the
    legacy $[ ] arithmetic, a line continuation inside an operator, a
    here-document delimiter with an expansion in it or one that runs into <( or
    >(, a here-document left pending by a $( ), a here-document body line inside
    a substitution that begins with the delimiter and is not it (E) ends both)
    or, inside backticks, has a backtick in it, a subshell after an assignment
    or a redirect, inside backticks a comment, a backslash in an ANSI-C string
    or a here-document line that ends in a backslash, an array subscript at the
    start of a command that does not close before a blank or an operator, an
    element of an array literal that holds a [ the same way, text glued to the )
    that ends an array literal, a ]] that is glued to a parenthesis or sits before
    a ( , a $ followed by a line continuation inside double quotes, the word alias, a word that names
    expand_aliases or BASH_ALIASES, an expansion handed to shopt, a quote nested in a way it
    cannot follow, or a quote or an escape the text ends inside, ends the read. A
    line continuation between or inside words is stepped over, and so is one
    inside the name or before the [ of an array subscript and one inside a ]].

    What it takes for a program is then checked against the machine by known():
    a word that is not a command here is dropped with the flags of its command, so
    a word it misreads as a program costs a word and does not send one. A
    redirect target is not checked, so it is the stops above that keep data out
    of one."""

    def __init__(self, text, out, cwd, home):
        self.t, self.n, self.i = text, len(text), 0
        self.out, self.cwd, self.home = out, cwd, home
        self.stats = 0
        # What the lookups of this call found, by word, so a name is looked up once.
        self.path, self.found = search_path(), {}
        self.heredocs = []
        self.frames = []
        self.halted = False
        self.quoted_at = None
        # A here-document delimiter is read as literal text. See redirect().
        self.literal = False
        self.reset()

    def reset(self):
        self.program = None
        self.wrapper = False
        self.skip = False
        self.ddash = False
        # An assignment or a redirect has been read ahead of the program. Bash
        # recognises a reserved word only as the first word of a command, so after
        # either one if, then, { and the rest are ordinary command names.
        self.prefixed = False
        # The word read as the program is not a known command, so no flag of this
        # command is sent. See known().
        self.dropped = False
        # The program of this command is shopt, so a word that is an expansion is
        # an option name this reader cannot read. See note_program().
        self.shopt = False

    def saved(self):
        return self.program, self.wrapper, self.skip, self.ddash, self.prefixed, self.dropped, self.shopt

    def restore(self, state):
        self.program, self.wrapper, self.skip, self.ddash, self.prefixed, self.dropped, self.shopt = state

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
                self.i = self.comment_end(i)
            elif c == "&" and t.startswith(">", self.past_continuations(i + 1)):
                # &>file and &>>file are one redirect, and the word after the
                # target is an argument. They are not a separator and a command.
                self.redirect()
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
            elif c == "\\" and self.continuation(i):
                # Bash removes a line continuation before it reads a token, so
                # between two words it is not there. It is not a word, and the
                # word after it is the first word of the command.
                self.i += 2
            else:
                if self.program in (None, "time") and not self.subscript_closes(i):
                    self.halt()
                    return False
                word = self.word()
                if self.halted:
                    # The read stopped inside this word, so what is in hand is a
                    # piece of it. A half read word is never judged.
                    return False
                if self.i == i:
                    self.i += 1
                elif not (word.isdigit() and self.i < n and t[self.i] in "<>"):
                    self.take(word, self.quoted_at)
            if self.halted:
                return False
        return False

    def continuation(self, i):
        """True when a backslash-newline pair that bash removes starts at i. Inside
        backticks a backslash is not modelled at all, so there it is not one."""
        return self.t.startswith("\\\n", i) and "`" not in self.frames

    def past_continuations(self, i):
        """The index after any backslash-newline pairs that start at i."""
        while self.continuation(i):
            i += 2
        return i

    def comment_end(self, i):
        """The index of the newline that ends the comment starting at i, or the end
        of the text. Inside backticks it is not known where a comment ends, and the
        read stops. Bash cuts a backtick body at the closing backtick first, with
        no regard for a comment, and removes a backslash-newline pair from what it
        cut. So the backtick that closes the body can sit inside what looks like a
        comment, and a comment that ends in a backslash goes on to the next line.
        The reader sees neither, ends the comment at the newline, pairs the
        backticks differently from bash and reads data as commands."""
        if "`" in self.frames:
            return self.halt()
        j = self.t.find("\n", i)
        return self.n if j < 0 else j

    def subscript_closes(self, i):
        """False when the word at i is NAME[ and its subscript is not one this
        reader sees whole, and the caller stops. Where bash expects a command it
        reads NAME[ as the head of an array assignment and takes everything up to
        the matching ] into the same word: spaces, ; | & < > and newlines included.
        m[k >f ]=1 is one word, whose key is "k >f ", and it runs nothing. This
        reader ends a word at the first of those characters and would read >f as a
        redirect. So the subscript has to close before one of them, and before a
        quote, an escape, a backtick or an expansion, which bash reads as pairs
        inside the subscript and this reader reads as pieces of a word. $NAME is the
        one expansion that is plain. True also when the word does not start that
        way. The subscript is bash's own matching: a [ inside it opens another.
        The head is found with line continuations taken out, because bash removes
        them before it reads a token: a\\ then [k >f ]=1 is the one word a[k >f ]=1."""
        start = self.array_head(i)
        return start < 0 or self.subscript_end(start) >= 0

    def subscript_end(self, i):
        """From just after a [ to just after the ] that matches it, or -1 when
        something that splits the word, or that bash reads as a pair inside the
        subscript, comes first. See subscript_closes(). A ) is one of those: in the
        subscript of an array element bash takes it into the word, and this reader
        would close the array literal there."""
        t = self.t
        depth, j = 1, i
        while True:
            stop = SUBSCRIPT_STOP.search(t, j)
            if stop is None:
                return -1
            c, j = stop.group(), stop.end()
            if c == "[":
                depth += 1
            elif c == "]":
                depth -= 1
                if depth == 0:
                    return j
            elif not (c == "$" and t[j:j + 1] in NAME_START):
                return -1

    def array_head(self, i):
        """The index after NAME[ when a NAME starts at i, or -1. A line continuation
        between two characters of the name, or between the name and the [, is
        stepped over: bash removes it before it reads a token, so ab, a\\ then b[ and
        a\\ then [ are each the head of an array assignment, and a reader that
        matched the raw text would read the word as a name and its subscript as a
        redirect. Nothing is backtracked, so the scan is linear."""
        t, n = self.t, self.n
        j = self.past_continuations(i)
        if j >= n or t[j] not in NAME_START:
            return -1
        j = self.past_continuations(j + 1)
        while j < n and t[j] in NAME_CHARS:
            j = self.past_continuations(j + 1)
        return j + 1 if t.startswith("[", j) else -1

    def skip_blanks(self):
        """Step over spaces, tabs and line continuations."""
        t, n = self.t, self.n
        while self.i < n:
            if t[self.i] in WS:
                self.i += 1
            elif self.continuation(self.i):
                self.i += 2
            else:
                break

    def substitution(self, closer, subshell=False):
        """A command list inside $( ), ( ), <( ) or backticks, read with its own
        quote state. The command around it is put back afterwards. One that cannot
        be read to its closer sends nothing: a list that never closes is not known
        to be a list.

        A $( ), a <( ) and a pair of backticks are parsed apart from the command
        around them, so a here-document the outer command is waiting for does not
        take its body from a newline inside one: the body starts at the newline
        after the whole line, and a delimiter-only line inside is only a command
        named after it. The list gets a here-document list of its own, and one it
        leaves pending when it closes ends the read, because where bash then
        takes the body from is not something this reader models. A subshell, which
        is subshell=True, is part of the outer parse and shares the list."""
        if len(self.frames) >= MAX_NEST:
            self.halt()
            return
        outer = self.saved()
        waiting = self.heredocs
        if not subshell:
            self.heredocs = []
        mark = self.out.mark()
        self.reset()
        # What kind of frame this is: ( for a subshell, which is part of the outer
        # parse, and the closer for the rest. See skip_heredocs().
        self.frames.append("(" if subshell else closer)
        found = self.commands(closer)
        self.frames.pop()
        self.out.newline()
        self.restore(outer)
        left = [] if subshell else self.heredocs
        if not subshell:
            self.heredocs = waiting
        if not found:
            self.out.rewind(mark)
            self.halt()
        elif left:
            self.halt()

    def paren(self):
        """A ( where a word does not start. Only a subshell at the start of a
        command, with nothing read ahead of it, is read; an array literal, an
        arithmetic command and a bare group are read past; anything else, a
        subshell after an assignment or a redirect included, is syntax this reader
        does not model."""
        t, i = self.t, self.i
        prev = t[i - 1] if i else "\n"
        if prev == "=":
            self.i = self.skip_array(i + 1)
            # Whatever is glued to the ) is part of the same word in bash: a=()$(>f)
            # is one word and a=()W is one. Here it would start a new command, so
            # only a blank, a separator, a closer or the end of the text may follow.
            # A line continuation is removed before bash reads a token.
            after = self.past_continuations(self.i)
            follower = t[after:after + 1]
            if follower and follower not in WS + SEPARATORS and not (follower == "`" and "`" in self.frames):
                self.halt()
        elif prev not in WS and prev not in SEPARATORS:
            self.halt()
        elif t.startswith("(", self.past_continuations(i + 1)):
            # (( with or without a continuation between the two: bash joins them.
            j = self.skip_arith(self.past_continuations(i + 1) + 1)
            if j < 0:
                self.halt()
            else:
                self.i = j
                self.skip = True
        elif self.program is None and not self.skip and not self.prefixed:
            self.i = i + 1
            self.substitution(")", subshell=True)
            self.skip = True
        else:
            self.halt()

    def word(self):
        """The next word with its quotes and escapes resolved. An expansion is
        left as a literal $, which no piece rule accepts. self.quoted_at is the
        length of the plain text before the first quote, escape or expansion in the
        word, or None when the word has none. A line continuation is neither: bash
        removes it before it reads a token, so it joins what is on both sides and
        quotes nothing."""
        t, n, i = self.t, self.n, self.i
        buf = []
        plain = 0
        quoted_at = None
        while i < n:
            c = t[i]
            if c in WS or c in SEPARATORS or (c == "`" and "`" in self.frames):
                break
            if c == "\\" and self.continuation(i):
                i += 2
                continue
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
            # A backslash with nothing after it is the text cut off, and the word
            # it ends is a piece of a longer one.
            if "`" in self.frames or i + 1 >= n:
                return self.halt()
            if t[i + 1] != "\n":
                buf.append(t[i + 1])
            return i + 2
        if c == "'":
            j = t.find("'", i + 1)
            if j < 0:
                return self.halt()
            buf.append(t[i + 1:j])
            return j + 1
        if c == '"':
            return self.double(i + 1, buf)
        if c == "`":
            if "`" in self.frames or self.literal:
                return self.halt()
            self.i = i + 1
            self.substitution("`")
            buf.append("$")
            return self.i
        if c != "$":
            return None
        if self.literal:
            # A here-document delimiter is taken as typed: bash expands nothing
            # in it, runs nothing in it and reads $'EOF' as EOF, so this reader
            # cannot say what the delimiter is, and it does not run the text.
            return self.halt()
        buf.append("$")
        if t.startswith("$", i + 1):
            # $$ is the process id, one parameter. Bash does not look for a ( or a
            # { after the pair: "$$(x y)" is the number and the text (x y), and
            # nothing in it runs. Pairs are taken left to right, so "$$$(x)" is the
            # number and then a substitution, as it is in bash.
            if t.startswith("\\\n", i + 2):
                return self.halt()
            return i + 2
        if t.startswith("\\\n", i + 1):
            # $\ then ( or { is an expansion once bash joins the lines.
            return self.halt()
        nxt = t[i + 1:i + 2]
        if nxt == "(":
            second = self.past_continuations(i + 2)
            if t.startswith("(", second):
                j = self.skip_arith(second + 1)
                return self.halt() if j < 0 else j
            self.i = i + 2
            self.substitution(")")
            return self.i
        if nxt == "{":
            return self.skip_brace(i)
        if nxt == "'":
            return self.skip_ansi(i)
        if nxt == "[":
            # The legacy $[ ] arithmetic. Its body is not a command list and may
            # hold a ; or a newline, and this reader does not read arithmetic.
            return self.halt()
        return i + 1

    def double(self, i, buf):
        """The inside of a double quoted string, from after the opening quote to
        after the closing one. A $( ) or pair of backticks inside it is a command
        list with its own quotes, so it is read as one and not as text."""
        t, n = self.t, self.n
        while i < n:
            m = DQ_SPECIAL.search(t, i)
            if m is None:
                return self.halt()
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
            elif c == "$" and t.startswith("\\\n", j + 1):
                # $ then a line continuation then ( or { is an expansion once bash
                # removes the pair, and what is inside it is code or a pid and
                # literal text, which this reader cannot tell from the characters.
                # special() stops at the same place outside a string.
                return self.halt()
            elif c == "$" and t.startswith("$", j + 1):
                # The process id: the pair is one parameter and a ( after it is
                # text. Without this the second $ is read as the start of $( ).
                if t.startswith("\\\n", j + 2):
                    return self.halt()
                buf.append("$")
                i = j + 2
            elif c == "`" or t.startswith(("$(", "${", "$["), j):
                i = self.special(j, buf)
                if self.halted:
                    return n
            else:
                buf.append(c)
                i = j + 1
        return self.halt()

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
        """From the $ of $' to after the closing quote, a \\' inside not closing it.
        Inside backticks a backslash ends the read: bash turns \\\\ into \\ before
        it reads the string, so $'a\\\\' is $'a\\' there, the quote is escaped and
        the string goes on, where this reader would close it."""
        t = self.t
        j = i + 2
        while True:
            m = ANSI_STOP.search(t, j)
            if m is None:
                return self.halt()
            if m.group() == "'":
                return m.end()
            if "`" in self.frames:
                return self.halt()
            j = m.end() + 1

    def skip_array(self, i):
        """From after the ( of NAME=( to after its ). Quotes and expansions inside
        are read as they are in a word, so a ) in one does not close it. A [ is the
        start of a subscript, and bash keeps all of it in the element: [a)]=1 is one
        word, and so is [b>f ]=2 with its blank and its operator. It is stepped over
        when it closes with a ] before anything that splits the word, a ) included,
        and otherwise the read ends, because the rest of the literal would be read
        here as commands."""
        t, n = self.t, self.n
        while i < n:
            c = t[i]
            if c == ")":
                return i + 1
            if c == "(" or (c == "#" and t[i - 1] in WS + "\n("):
                return self.halt()
            if c == "[":
                j = self.subscript_end(i + 1)
                if j < 0:
                    return self.halt()
                i = j
                continue
            j = self.special(i, [])
            if self.halted:
                return n
            i = i + 1 if j is None else j
        return self.halt()

    def skip_test(self, i):
        """From after [[ to after the ]] that closes it. Operators and a regular
        expression can hold ( ) | & < >, so only the closing ]] word ends it. A
        # that begins a word is a comment to the end of the line, as it is in
        bash, and a $( ) or backticks in it run nothing, so it is read past
        without looking in. One after an operator or a parenthesis may be a
        comment or the middle of a regular expression, and ends the read, and so
        does any comment inside backticks. See comment_end().

        ]] is a word, and bash closes the test at the first one. It is one after a
        blank or a newline, and before a blank, a newline, ; & | ) or a < or > that
        does not open a <( or a >(. Bash removes a line continuation before it reads
        a token, so one is nothing here: it does not end the blank before a ] or a #,
        and a ] then a continuation then a ] is the word. A reader that closed on
        fewer of these than bash does goes on to a later ]] that is data, a
        here-document body or a quoted string, and reads code there. A ]] glued to a
        parenthesis is either the end of a group or the end of a regular expression
        ([[ a =~ (b)]] never closes), a ]] after any other operator is not valid
        syntax, and a ]] before a ( or a <( or a >( is a longer word or not valid
        either; none of them is guessed at and each ends the read."""
        t, n = self.t, self.n
        # The last character bash sees before i, a line continuation not counted
        # as one. "[" stands for the [[ just read.
        prev = "["
        while i < n:
            if self.continuation(i):
                i += 2
                continue
            if t[i] == "]":
                end = self.double_bracket(i)
                if end >= 0 and prev in WS + "\n":
                    after = self.past_continuations(end)
                    follower = t[after:after + 1]
                    if follower in ("", " ", "\t", "\n", ";", "&", "|", ")"):
                        return end
                    if follower in ("<", ">") and not t.startswith("(", self.past_continuations(after + 1)):
                        return end
                    if follower in ("<", ">", "("):
                        return self.halt()
                elif end >= 0 and prev in "()&|<>;":
                    return self.halt()
            if t[i] == "#":
                if prev in WS + "\n":
                    i = self.comment_end(i)
                    if self.halted:
                        return n
                    prev = "#"
                    continue
                if prev in "()&|<>;":
                    return self.halt()
            j = self.special(i, [])
            if self.halted:
                return n
            if j is None:
                prev = t[i]
                i += 1
            else:
                prev = "w"
                i = j
        return self.halt()

    def double_bracket(self, i):
        """The index after a ]] that starts at i, or -1. A line continuation between
        the two brackets is stepped over, as bash removes it before it reads a token."""
        t = self.t
        if not t.startswith("]", i):
            return -1
        j = self.past_continuations(i + 1)
        return j + 1 if t.startswith("]", j) else -1

    def redirect(self):
        t, n, i = self.t, self.n, self.i
        two = t[i:i + 2]
        if t[i] == "&":
            # &>file and &>>file send both streams to one file. Only reached when
            # a > follows, and a line continuation between them is stopped at below.
            kind, width = "path", 3 if t.startswith("&>>", i) else 2 if two == "&>" else 1
        elif t.startswith("<<<", i):
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
        self.prefixed = True
        if t.startswith("\\\n", self.i):
            # Bash joins the lines before it reads tokens, so this may be a longer
            # operator than the characters show: <\ then <EOF is a heredoc. A line
            # continuation inside an operator is not modelled.
            self.halt()
            return
        self.skip_blanks()
        heredoc = kind in ("heredoc", "heredoc-")
        if heredoc and t.startswith(PROCESS_OPENERS, self.i):
            # <<EOF<(x) and << >(x) are one delimiter, text and parentheses
            # included: bash reads <( and >( into the word being read, and expands
            # nothing in a delimiter. See below for the same after the word.
            self.halt()
            return
        if self.i >= n or t[self.i] in SEPARATORS:
            return
        start = self.i
        # The delimiter of a here-document is literal text, never a word to resolve.
        self.literal = heredoc
        operand = self.word()
        self.literal = False
        if self.halted:
            return
        if heredoc and t.startswith(PROCESS_OPENERS, self.i):
            # The word ended at a < or a > that bash takes into the delimiter.
            self.halt()
            return
        if self.i == start:
            self.i += 1
        elif kind == "path":
            piece = vet_path(operand, self.home)
            if piece:
                self.out.add(piece)
        elif kind != "operand":
            self.heredocs.append((operand, kind == "heredoc-", self.quoted_at is None))

    def skip_heredocs(self):
        """Read past the bodies of the here-documents a line left pending. Inside a
        $( ), a <( ) or a pair of backticks bash finds where the substitution ends
        before it parses what is in it, and a here-document body does not hide the
        end: a body line that begins with the delimiter and goes on, E) or E ) or
        E) # c, ends the here-document and the substitution together, and so does
        a closing backtick anywhere in a body inside backticks. A plain subshell does
        not do either. This reader ends a body only at a line that is the delimiter,
        so it would go on to a later line that is the delimiter in other data and
        read what follows as code. A line like that inside a substitution ends the
        read. See heredoc_line() for the backtick."""
        pending, self.heredocs = self.heredocs, []
        cut = ")" in self.frames or "`" in self.frames
        for delimiter, tabs, bare in pending:
            while self.i < self.n:
                line = self.heredoc_line(bare)
                if self.halted:
                    return
                shown = line.lstrip("\t") if tabs else line
                if shown == delimiter:
                    break
                if cut and shown.startswith(delimiter):
                    self.halt()
                    return

    def heredoc_line(self, joined):
        """The next line of a here-document body. When the delimiter was typed
        bare the body is expanded, and bash removes a backslash-newline from it
        before it compares the line with the delimiter: foo\\ then EOF is the line
        fooEOF, and the body goes on. A quoted delimiter expands nothing and the
        lines are the lines. A line that ends in an odd number of backslashes
        continues, the last of a run of an even number is an escaped backslash.
        Inside backticks a line that ends in a backslash ends the read, whatever
        the delimiter: bash unescapes the body and removes a backslash-newline pair
        before it reads the here-document, so which lines continue is not what the
        text shows, and the body can end where this reader does not end it. So does
        a line with a backtick in it: bash cuts the body of a pair of backticks at
        the closing one with no regard for a here-document, so a body line that is
        the delimiter and a closing backtick ends the substitution there, and the
        text after it is code that this reader would still be reading as data."""
        t, n = self.t, self.n
        parts, run = [], 0
        while True:
            j = t.find("\n", self.i)
            end = n if j < 0 else j
            line = t[self.i:end]
            self.i = n if j < 0 else end + 1
            if "`" in self.frames and (line.endswith("\\") or "`" in line):
                self.halt()
                return line
            head = line.rstrip("\\")
            run = len(line) - len(head) + (run if not head else 0)
            if not (joined and j >= 0 and self.i < n and run % 2):
                parts.append(line)
                return "".join(parts)
            parts.append(line[:-1])
            run -= 1

    def test_expression(self):
        """A [[ just read: read past the expression to its ]] and past whatever
        follows it on the command."""
        j = self.skip_test(self.i)
        if not self.halted:
            self.i = j
            self.skip = True

    def known(self, word):
        """True when a word is a command here: a bash builtin or reserved word, a
        name PATH resolves to an executable file, or, with a / in it, an existing
        executable file. Nothing is run. A word over MAX_WORD characters is not
        looked up. A word is looked up once per call, and once MAX_LOOKUPS words
        have been, a word not seen yet is not a command: the cost of the cap is a
        name dropped, never one let through."""
        if len(word) > MAX_WORD:
            return False
        if word in BASH_WORDS:
            return True
        hit = self.found.get(word)
        if hit is not None:
            return hit
        if len(self.found) >= MAX_LOOKUPS:
            return False
        if "/" not in word:
            hit = any(is_executable(os.path.join(directory, word)) for directory in self.path)
        elif word.startswith("~/"):
            hit = bool(self.home) and is_executable(self.home + word[1:])
        else:
            hit = is_executable(os.path.join(self.cwd, word))
        self.found[word] = hit
        return hit

    def command_name(self, word):
        """The name to send for a word the reader took as a program, or None. A
        word that is not a known command is not sent, and the flags of its command
        are not sent either: the reader may have taken a word of the caller's data
        for a program, and the words beside it are the caller's data too."""
        name = program_name(word)
        if name and self.known(word):
            return name
        self.dropped = True
        return None

    def note_program(self, word):
        """A word has been taken as a program, a wrapper's included, so that take()
        knows when the arguments are those of shopt. Bash reads aliases at parse
        time, and an alias can expand to the start of a here-document or of anything
        else that changes where a command ends: after shopt -s expand_aliases and
        alias foo='cat <<EOF', the lines after a line that holds only foo are data
        to bash, and this reader, which reads the text and not the state the shell
        has built by running it, would read them as commands. What an alias is
        cannot be known without running the lines before it, so the read ends at
        the command that makes one or allows one, which take() sees in its words."""
        self.shopt = word == "shopt"

    def take(self, word, quoted_at=None):
        """One resolved word. quoted_at is where its first quote, escape or
        expansion begins, as word() reports it."""
        if (("alias" in word and ALIAS_WORD.search(word)) or "expand_aliases" in word or "BASH_ALIASES" in word
                or (self.shopt and "$" in word)):
            # Wherever it is typed, as a program, a wrapper's program, an argument
            # such as eval's or inside a string: the word alias, the shell option and
            # the variable that turn aliases on or define one, and an option of shopt
            # that is an expansion and so may be that name. See note_program().
            self.halt()
            return
        if quoted_at is None:
            # These two are acted on wherever they are typed bare, whatever the
            # reader makes of the command around them: a case pattern and an
            # operand of [[ ]] are data that look like commands, and a reader that
            # has lost its place (after time -p, in a function body or a
            # coprocess) would send them. A case ends the read. A [[ begins a test
            # only where a command begins, and after the reserved word time. Read
            # anywhere else it is an argument (echo [[, type [[) or something the
            # reader does not follow, and the text after it is not an expression:
            # skipping to a ]] would read a comment or a here-document body as
            # commands. It ends the read as a case does, which costs the commands
            # after it, fidelity and not secrecy.
            if word == "case":
                self.halt()
                return
            if word == "[[":
                if (self.program is None and not self.prefixed and not self.skip) or self.wrapper == "time":
                    self.test_expression()
                else:
                    self.halt()
                return
        if self.skip:
            return
        if self.program is None:
            # A reserved word is one only when it is typed bare and nothing has
            # been read ahead of it in this command: "if", \if, FOO=bar if and
            # > f if are each a command name, and the word after is its argument.
            if quoted_at is None and not self.prefixed:
                if word in OPENERS or word in CLOSERS:
                    return
                if word in HEADERS:
                    self.skip = True
                    return
                if word in UNMODELLED:
                    self.halt()
                    return
            if assignment(word, quoted_at):
                self.prefixed = True
                return
            self.program = word
            name = self.command_name(word)
            if name:
                self.out.add(name)
            self.wrapper = wrapper_kind(name, word == "time" and quoted_at is None and not self.prefixed)
            self.note_program(word)
            return
        if self.wrapper:
            # Only some wrappers take NAME=value: after the others it is the name
            # of the program to run, which fails, and the word after it is an
            # argument and not a program.
            if self.wrapper != "plain" and assignment(word, quoted_at):
                if self.wrapper == "time":
                    # After an assignment a [[ is a command name and not a test.
                    self.wrapper = "assigns"
                return
            if not word.startswith("-"):
                name = self.command_name(word)
                if name:
                    self.out.add(name)
                self.wrapper = wrapper_kind(name)
                self.note_program(word)
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
                if name and not self.dropped:
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
    """The keys of the tool's input object that are plain names, in order. Never a
    value, and never a key below the top: the top level is the tool's own
    parameters, and a key under one is the caller's data (a map keyed by ids,
    names or tokens, a header, an environment variable, a JSON body), which the
    character class cannot tell from a name. A key that is long, or carries more
    than MAX_DIGITS digits, or leaves the character class, is dropped as well."""
    names = []
    if isinstance(value, dict):
        for key in itertools.islice(value, MAX_FANOUT):
            if isinstance(key, str) and len(key) <= MAX_FIELD_LEN and FIELD.fullmatch(key) and few_digits(key):
                names.append(key)
                if len(names) >= MAX_FIELDS:
                    break
    return names


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


def opener():
    """The opener for one request. It is built here and not at import so that the
    proxy is read from the environment when the request is made. ProxyHandler()
    with no argument is the environment's proxy: HTTPS_PROXY for an https URL and
    NO_PROXY for the hosts that skip it. The request reaches api.typesafe.ai as a
    CONNECT through that proxy, which is what adds the key, and the TLS context is
    the default one, which trusts SSL_CERT_FILE. _NoRedirect replaces the default
    redirect handler and is the only thing this changes."""
    return urllib.request.build_opener(urllib.request.ProxyHandler(), _NoRedirect)


def ask_jev(body, endpoint, timeout):
    """The request. It carries no credential header: the proxy adds the key."""
    req = urllib.request.Request(
        endpoint,
        data=json.dumps(body).encode("utf-8"),
        headers={"Content-Type": "application/json"},
        method="POST",
    )
    with opener().open(req, timeout=timeout) as resp:
        return json.loads(resp.read(1 << 20).decode("utf-8"))


def ask_within(body, endpoint, deadline):
    """The request, DNS and every read included, inside one deadline."""
    box = {}

    def work():
        try:
            box["response"] = ask_jev(body, endpoint, deadline)
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


def run(payload, endpoint=None, now=None, timeout=None, started=None):
    """Returns the JSON object to print on stdout, or None to print nothing."""
    started = time.monotonic() if started is None else started
    now = now or datetime.now(timezone.utc)
    endpoint = endpoint or ENDPOINT
    if not isinstance(payload, dict) or not isinstance(payload.get("tool_name"), str) or not payload["tool_name"]:
        write_row({"ts": stamp(now), "enforced": ENFORCE, "decision": "none", "outcome": "bad_input"})
        return None
    name = payload["tool_name"]
    session = str(payload.get("session_id") or "")[:100]
    row = {"ts": stamp(now), "session": session, "tool": name[:200], "enforced": ENFORCE, "decision": "none"}

    if not SEND:
        row["outcome"] = "off"
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
        better_tool, needs_human, model = read_answers(ask_within(body, endpoint, timeout))
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
        out = run(payload, started=started)
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
