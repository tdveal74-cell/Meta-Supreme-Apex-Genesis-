#!/usr/bin/env bash
# Install OpenMontage at the pinned commit, outside this repository.
#
# Exit codes:
#   0  installed, every optional step included
#   1  a check after the fetch or after make setup failed: the checkout is not
#      at the pin, a resumed fetch left code the pin does not carry, make left
#      no .venv python, or the registry did not load or found no tools; the
#      FAILED line says which
#   3  refused before anything changed; the message says why
#   4  installed, but upstream skipped an optional step; the summary names it
#   any other non-zero code is the failing tool's own: git 128, make 2,
#   timeout 124 when the fetch or make setup runs past OPENMONTAGE_SETUP_TIMEOUT
#
# Idempotent: a checkout at the pin with no change to a tracked file, no
# untracked file under tools/ and no untracked .py at its top level is reused,
# and `make setup` runs again, which only fills in what is missing. A repository
# with OpenMontage's origin and no commit, which is what a fetch interrupted
# after git init leaves, is fetched into and then held to the same untracked
# check. Anything else at the target is refused and left alone, because it may
# hold someone's productions.
set -euo pipefail

PIN="195eab24478dc9363326aec437aefc3701635ddf"
REPO="https://github.com/calesthio/OpenMontage.git"
DEST="${OPENMONTAGE_HOME:-$HOME/OpenMontage}"
# Upstream's CI runs 3.11; its .python-version says 3.10. 3.11 is the one
# that is tested, and the one constraints.txt was measured on, so ask for it.
# uv can fetch it when the machine lacks it; that path was not exercised here,
# where python3.11 was already installed.
PY="${OPENMONTAGE_PYTHON:-3.11}"
MEASURED_PY="3.11"
SETUP_TIMEOUT="${OPENMONTAGE_SETUP_TIMEOUT:-900}"

refuse() {
  echo "REFUSED: $*" >&2
  exit 3
}

# GNU realpath -m is not on every machine; python3 is required anyway.
resolve() {
  python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

missing=""
for tool in git make python3 node npm npx; do
  command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
done
[ -z "$missing" ] || refuse "missing prerequisites:$missing"
case "$SETUP_TIMEOUT" in
  ''|*[!0-9]*|0*) refuse "OPENMONTAGE_SETUP_TIMEOUT must be a whole number of seconds above 0 with no leading zero, not '$SETUP_TIMEOUT'; timeout reads 0 and 00 alike as no limit at all." ;;
esac
at_least() {  # at_least <python> <major.minor>: does it run and meet the version?
  "$1" -c "import sys; raise SystemExit(0 if sys.version_info[:2] >= tuple(int(x) for x in '$2'.split('.')[:2]) else 1)" 2>/dev/null
}
# constraints.txt pins numpy 2.4.6, which needs Python 3.11 or newer.
python3 -c "import sys; raise SystemExit(0 if tuple(int(x) for x in '$PY'.split('.')[:2]) >= (3, 11) else 1)" 2>/dev/null \
  || refuse "OPENMONTAGE_PYTHON=$PY is below 3.11, and the pinned packages in constraints.txt need 3.11 or newer."
command -v ffmpeg >/dev/null 2>&1 \
  || echo "WARNING: ffmpeg is not on PATH, so rendering will not work." >&2
node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
[ "$node_major" -ge 22 ] 2>/dev/null \
  || echo "WARNING: Node $node_major found; HyperFrames needs 22 or newer and will be unavailable." >&2

# The first line a tool prints about its version, "none" when it is absent.
# sed reads to the end, so no pipe closes early under pipefail.
ver() {
  command -v "$1" >/dev/null 2>&1 || { echo "none"; return 0; }
  local out
  out="$("$@" 2>/dev/null | sed -n 1p)" || true
  echo "${out:-unknown}"
}
echo "==> Found node: $(ver node --version); uv: $(ver uv --version); ffmpeg: $(ver ffmpeg -version | cut -d' ' -f3)"

limit=""
if command -v timeout >/dev/null 2>&1; then
  limit="timeout $SETUP_TIMEOUT"
  cap="at most ${SETUP_TIMEOUT}s"
else
  cap="no time limit"
  echo "WARNING: timeout is not on PATH, so the fetch and make setup run with no time limit." >&2
fi

here="$(dirname "$(resolve "$0")")"
# Upstream pins no Python package. constraints.txt holds the versions measured
# in a working install, so every install on Python 3.11 resolves the same code.
constraints="$here/constraints.txt"
[ -f "$constraints" ] || refuse "$constraints is missing; it pins upstream's Python packages."
# pip splits PIP_CONSTRAINT on whitespace, so a path with a space in it would
# name two files that do not exist.
case "$constraints" in
  *[[:space:]]*) refuse "the script's path has whitespace in it ($constraints), which pip would split. Move the checkout to a path without spaces." ;;
esac
dest_abs="$(resolve "$DEST")"
# Upstream's make setup reuses an existing .venv before it looks at anything
# else. Failing that it makes one with uv when uv is on PATH, else with the
# first of python$PY, python3 and python, which must be $PY or newer.
existing="$dest_abs/.venv/bin/python"
if [ -x "$existing" ]; then
  at_least "$existing" "$PY" \
    || refuse "$existing is older than Python $PY or does not run, and make setup would reuse it. Remove $dest_abs/.venv so make setup makes a new one."
  venv_py="$("$existing" -c 'import sys; print("%d.%d" % sys.version_info[:2])'), the existing .venv"
elif command -v uv >/dev/null 2>&1; then
  venv_py="$PY, from uv"
else
  base=""
  for candidate in "python$PY" python3 python; do
    if command -v "$candidate" >/dev/null 2>&1; then base="$candidate"; break; fi
  done
  at_least "$base" "$PY" \
    || refuse "make setup needs uv, or a Python $PY or newer as python$PY, python3 or python; the first found, $base, is older. Install uv, or set OPENMONTAGE_PYTHON to the version you have, 3.11 or newer."
  venv_py="$("$base" -c 'import sys; print("%d.%d" % sys.version_info[:2])'), from $base"
fi
case "$venv_py" in
  "$MEASURED_PY",*) ;;
  *) echo "WARNING: the venv will use Python $venv_py; constraints.txt was measured on $MEASURED_PY, so its pins are untested there." >&2 ;;
esac
if repo_root="$(git -C "$here" rev-parse --show-toplevel 2>/dev/null)"; then
  repo_root="$(resolve "$repo_root")"
  case "$dest_abs/" in
    "$repo_root"/*)
      refuse "$dest_abs is inside $repo_root. Ruff and pytest would sweep OpenMontage's code into this repository's checks. Set OPENMONTAGE_HOME outside it."
      ;;
  esac
else
  echo "WARNING: could not find the repository this script lives in, so the inside-the-repository guard is off: $(git -C "$here" rev-parse --show-toplevel 2>&1 >/dev/null || true)" >&2
fi

# Untracked files that would load as code: anything under tools/ outside
# __pycache__, since the registry imports .py, .pyc and .so alike, and any .py
# at the top, where make runs python and a stray module shadows a real one.
untracked_code() {
  git -C "$dest_abs" ls-files --others -- tools ':(exclude,glob)tools/**/__pycache__/**' ':(glob)*.py'
}

fetch_pin() {
  echo "==> Fetching OpenMontage $PIN into $dest_abs"
  local status=0
  # shellcheck disable=SC2086
  $limit git -C "$dest_abs" fetch -q --depth 1 origin "$PIN" || status=$?
  if [ "$status" -ne 0 ]; then
    echo "FAILED: the fetch exited $status (124 means it ran past ${SETUP_TIMEOUT}s)." >&2
    exit "$status"
  fi
  git -C "$dest_abs" checkout -q --detach FETCH_HEAD
}

if [ -e "$dest_abs" ]; then
  [ -d "$dest_abs/.git" ] || refuse "$dest_abs exists and is not a git checkout."
  if ! git_err="$(git -C "$dest_abs" rev-parse --git-dir 2>&1 >/dev/null)"; then
    refuse "git cannot read $dest_abs: $git_err"
  fi
  # The configured URL, read raw: `git remote get-url` would apply any
  # url.*.insteadOf rewrite and refuse a checkout this script made itself.
  origin="$(git -C "$dest_abs" config --get remote.origin.url || true)"
  [ "$origin" = "$REPO" ] || refuse "$dest_abs has origin '${origin:-none}', not $REPO."
  have="$(git -C "$dest_abs" rev-parse -q --verify HEAD || true)"
  if [ -z "$have" ]; then
    # No commit yet: what a first run leaves when the fetch dies after
    # git init. The origin check above refuses any other origin; a repository
    # made by hand with this origin and no commit is resumed the same way.
    echo "==> Resuming an interrupted fetch"
    fetch_pin
    if ! extra="$(untracked_code)" || [ -n "$extra" ]; then
      echo "FAILED: $dest_abs held files the pin does not carry, which the tool registry or make setup would load: $extra" >&2
      exit 1
    fi
  elif [ "$have" != "$PIN" ]; then
    refuse "$dest_abs is at $have, not the pinned $PIN. Move it aside or set OPENMONTAGE_HOME."
  elif ! changes="$(git -C "$dest_abs" status --porcelain --untracked-files=no)"; then
    refuse "git status failed in $dest_abs, so its files cannot be checked; git's own message is above."
  elif [ -n "$changes" ]; then
    refuse "$dest_abs has local changes to tracked files, so make setup would not run the pinned code. See git -C $dest_abs status."
  elif ! extra="$(untracked_code)"; then
    refuse "git ls-files failed in $dest_abs, so its files cannot be checked; git's own message is above."
  elif [ -n "$extra" ]; then
    refuse "$dest_abs has files the pin does not carry, which the tool registry or make setup would load: $extra"
  else
    echo "==> $dest_abs is already at the pinned commit, with no change to a tracked file and nothing untracked that would load as code"
  fi
else
  git init -q "$dest_abs"
  git -C "$dest_abs" remote add origin "$REPO"
  fetch_pin
fi

have="$(git -C "$dest_abs" rev-parse HEAD)"
if [ "$have" != "$PIN" ]; then
  echo "FAILED: checkout is at $have, expected $PIN." >&2
  exit 1
fi

# Upstream's Makefile installs into an active virtualenv or conda env, and
# honours VENV_DIR from the environment, before it ever makes its own .venv.
# Clear all three for this one call so nothing lands in the caller's env.
log="$dest_abs/openmontage-setup.log"
echo "==> make setup with Python $PY, $cap; log: $log"
set +e
# shellcheck disable=SC2086
env -u VIRTUAL_ENV -u CONDA_PREFIX -u VENV_DIR PIP_CONSTRAINT="$constraints" $limit \
  make -C "$dest_abs" setup PYTHON_VERSION="$PY" VENV_DIR=.venv 2>&1 | tee "$log"
status=${PIPESTATUS[0]}
set -e
if [ "$status" -ne 0 ]; then
  echo "FAILED: make setup exited $status (124 means it ran past ${SETUP_TIMEOUT}s). See $log" >&2
  exit "$status"
fi

py="$dest_abs/.venv/bin/python"
if [ ! -x "$py" ]; then
  echo "FAILED: make setup finished but $py does not exist. See $log" >&2
  exit 1
fi

# make setup prints [skip] and carries on when an optional piece fails, so a
# zero exit does not prove the core works. Load the tool registry the way
# upstream's own preflight target does and count what it found.
"$py" - "$dest_abs" <<'PYEOF'
import os
import sys

os.chdir(sys.argv[1])
sys.path.insert(0, sys.argv[1])
try:
    from tools.tool_registry import registry

    registry.discover()
    menu = registry.provider_menu()
except Exception:
    import traceback

    traceback.print_exc()
    sys.exit("FAILED: the tool registry did not load; the traceback is above")
total = sum(group["total"] for group in menu.values())
configured = sum(group["configured"] for group in menu.values())
print(f"==> tool registry loaded: {total} tools in {len(menu)} capability groups, {configured} usable now")
if total == 0:
    sys.exit("FAILED: the registry discovered no tools")
PYEOF

# Only a line that starts with [skip] is a skip. make also echoes the recipe
# line `pip install piper-tts || echo "  [skip] ..."` before running it, and
# that echo carries the same text mid-line on every install.
skipped="$(grep -E '^[[:space:]]*\[skip\]|runtime_available=False' "$log" || true)"
if [ -n "$skipped" ]; then
  echo "DEGRADED: OpenMontage $PIN installed at $dest_abs, but upstream skipped optional steps:" >&2
  echo "$skipped" >&2
  exit 4
fi
echo "OK: OpenMontage $PIN installed at $dest_abs"
