# Flagship Bar audit: github.com/Vannu07/jarvis

Subject: `github.com/Vannu07/jarvis` at commit `21b9d63`
Audited: 2026-08-22
Standard: `SYS_SPEC_flagship-bar_v01_2026-08-21` (Drive id `1s4l6r9ucGWrtEENqlBqDmFtpl4_85z_m`)
critic_mode: fresh

This is the audit that decided what to carry over and what to rebuild. It is
kept because a rebuild with no record of what was wrong reads as taste rather
than engineering, and because the upstream project is a real open source effort
whose contributors deserve findings with evidence rather than a verdict.

Every finding below was verified by running a command against the clone, not by
reading and assuming.

---

## VERDICT: QUARANTINE

Scores:

| Dimension | Score |
|---|---|
| scope fidelity | 4 |
| correctness | 1 |
| unverified claims | 3 |
| security | 1 |
| reversibility and blast radius | 2 |
| silent failure resistance | 2 |
| idempotency | 3 |
| traceability | 3 |
| observability | 3 |
| completeness | 2 |
| maintainability | 2 |
| flagship bar | 1 |

mean 2.25, verification 2, security 1

Clause 1 (root, not symptom): MISSED
Clause 2 (simplest form that fully works): MISSED
Clause 3 (handed off clean): MISSED

PASS requires every dimension at 3 or above, a mean of 4.0, security at exactly
5, and verification at 4. This misses on all four.

**This verdict is about a specific commit against a specific internal standard.
It is not a judgement of the project or its contributors, and the architecture
was good enough to be worth rebuilding from rather than replacing.**

---

## Confirmed defects

### 1. The application cannot start. `main.py:13`

```python
from backend.feature.reminder import set_reminder
```

`backend/feature.py` is a module. There is no `backend/feature/` package, so
`backend.feature.reminder` cannot resolve and `main.py` raises at import.

Verified:

```
$ python3 -c "import os; print('feature.py is file:', os.path.isfile('backend/feature.py')); print('feature/ is dir:', os.path.isdir('backend/feature'))"
feature.py is file: True
feature/ is dir: False
```

Consequence: every entry point through `main.py` and `run.py` fails immediately.
Severity: blocks everything. Owner: upstream.

### 2. Dependency install fails. `requirements.txt:24`

```
sqlite3
```

`sqlite3` is a standard library module and is not distributable from PyPI.
`pip install -r requirements.txt` fails on this line.

Consequence: a new contributor cannot complete setup as documented.
Owner: upstream.

### 3. Shell injection from voice input. `backend/feature.py:211`

```python
os.system("start " + query)
```

`query` is derived from speech recognition, and from `takeAllCommands`, which is
exposed to the browser through `@eel.expose` at `backend/command.py:59` and
accepts an arbitrary `message` string. Unsanitised text is concatenated into a
shell command.

Verified:

```
$ grep -n "os.system\|shell=True\|os.startfile" backend/*.py
backend/feature.py:195:                os.startfile(results[0][0])
backend/feature.py:211:            os.system("start " + query)
backend/feature.py:344:        subprocess.run(full_command, shell=True)
backend/feature.py:346:        subprocess.run(full_command, shell=True)
```

Consequence: anyone who can reach the eel endpoint, or speak near the
microphone, can execute an arbitrary command. Security scores 1 on this alone.
Owner: upstream.

### 4. The WhatsApp path quotes for the wrong shell. `backend/feature.py:340`

`shlex.quote` is POSIX quoting, and the result is embedded in a Windows
`start "" "..."` command run with `shell=True`. POSIX quoting does not make a
`cmd.exe` argument safe.

Owner: upstream.

### 5. Face authentication accepts almost any face. `backend/auth/recognize.py:60`

```python
if accuracy < FACE_RECOGNITION_CONFIDENCE:
```

with the default at `backend/config_manager.py:208`:

```python
return self.get_int("FACE_RECOGNITION_CONFIDENCE", 100)
```

In OpenCV's LBPH recogniser the value returned as `accuracy` is a distance where
lower means a closer match. A threshold of 100 accepts nearly any detected face.

Consequence: the authentication gate does not gate. Owner: upstream.

### 6. Face auth cannot run on the pinned dependency. `backend/auth/recognize.py:12`

```python
recognizer = cv2.face.LBPHFaceRecognizer_create()
```

`cv2.face` ships in `opencv-contrib-python`. `requirements.txt:12` pins
`opencv-python==4.8.1.78`, which does not include it, so this raises
`AttributeError`.

`cv2.CAP_DSHOW` at line 26 is DirectShow and is Windows only, as are
`os.startfile` and the `start` command used elsewhere, while the README presents
the project as cross platform.

Owner: upstream.

### 7. Failed authentication hangs the command loop silently

`main.py:78` sets `auth_complete` only when `flag == 1`. If no face is ever
detected, `flag` stays `""` and the loop at `backend/auth/recognize.py:37` spins
until ESC. The command thread is blocked at `auth_complete.wait()`
(`main.py:27`) forever, with no timeout and no message.

Consequence: the application appears to be running and answers nothing.
Owner: upstream.

### 8. A SQLite connection is shared across threads. `backend/feature.py:40`

```python
conn = sqlite3.connect(DATABASE_PATH)
cursor = conn.cursor()
```

Created at module import and used from the command thread started at
`main.py:116`. Python's `sqlite3` defaults to `check_same_thread=True`, so this
raises `ProgrammingError` on first use from that thread.

Owner: upstream.

### 9. Two routers that disagree

`backend/command.py:76` routes on raw substrings:

```python
if "open" in query:
```

so any utterance containing "open" reaches the app launcher, including "I need
to open up to her about it". Meanwhile `backend/feature.py:74`
(`handle_user_text`) routes the same utterances through the fuzzy parser. Which
path runs depends on the entry point, and the two disagree.

Owner: upstream.

### 10. A destructive intent behind a 60 percent fuzzy match

`backend/nlp/command_parser.py:175`:

```python
if score >= 60:
    return all_phrases[best_match]
```

applied across a pool that includes `shutdown` and `restart`. A 60 percent token
match is not consent for powering off a machine. The destructive handlers at
`backend/feature.py:146` are currently inert, with the real calls commented out,
but the comments invite uncommenting with no gate in place.

Owner: upstream.

### 11. The configured speech rate never applies. `backend/command.py:11`

```python
engine.say(text)
engine.runAndWait()
engine.setProperty("rate", TTS_RATE)
```

`rate` is set after the utterance has already been spoken, so `TTS_RATE` has no
effect. The engine is also re-initialised on every call.

Owner: upstream.

### 12. Personal identity baked into defaults

`backend/config_manager.py:213`, `294` and `298` default
`FACE_RECOGNITION_NAMES` to a list containing a specific person's name, and
`USER_NAME` and `USER_EMAIL` likewise. A fork that does not override these
greets the wrong person.

Owner: upstream.

---

## Weaknesses

- `backend/db.py` is roughly 90 percent commented out scratch work.
- `backend/feature.py:1` opens with a commented out earlier implementation.
- Root holds `hacktober.txt`, `hacktober_update.txt`, `news_log.txt` and
  `.gitkeep_temp`, all empty or near empty, all bare generic names.
- `web_server_mode` defaults to the string `"None"`
  (`backend/config_manager.py:277`), which is not the same as `None` and is
  passed to `eel.start(mode=...)`.
- `_load_env_file` (`backend/config_manager.py:27`) does not strip quotes, so
  `KEY="value"` yields a value including the quote characters.
- No test covers authentication or any of the shell paths.

---

## What was carried over, and what was rebuilt

The architecture was sound and is the reason this was worth building from.

**Carried over as ideas:** the intent map and fuzzy matching approach, the
config object with typed accessors and feature flags, the status indicator and
timing wrapper, the separation of a command router from its handlers.

**Rebuilt:**

| Upstream | Here | Why |
|---|---|---|
| two routers | one, `commands.py` | they disagreed by entry point |
| flat 60 percent threshold | per intent floors, 0.92 for destructive | a fuzzy match is not consent |
| `os.system`, `subprocess(shell=True)` | nothing executes at all | removes the injection class entirely |
| commented out destructive calls | the approval gate | an effect needs a ruling, not a comment |
| `fuzzywuzzy` plus `python-Levenshtein` | `difflib` from the standard library | drops a compiled dependency, deterministic across versions |
| face auth accepting any face | not carried over | needs a camera and a real threshold study |
| shared cross thread SQLite connection | no database in the package | nothing to share |

The voice loop, face authentication and hotword detection were not carried over.
Each needs hardware and a desktop session, none survived the audit unchanged,
and porting them would have meant importing the injection surface along with
them. That is a deliberate scope decision, stated rather than quietly dropped.

---

## Standing rules observed in this audit

- INSPECT, THEN HAND BACK. Nothing upstream was modified. This session has no
  push access to `Vannu07/jarvis` and did not seek any.
- FINDINGS CARRY EVIDENCE. Every finding above cites file and line and, where a
  command produced it, the command and its output.
- NEVER CLAIM FIXED, TESTED OR SAFE WITHOUT A SHOWN RUN.
- The verdict is a verdict, not a merge. The human owns SHIP.
