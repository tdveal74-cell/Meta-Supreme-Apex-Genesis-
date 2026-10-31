#!/usr/bin/env bash
# Install OpenMontage at the pinned commit, outside this repository.
#
# Exit codes:
#   0  installed, every optional step included
#   3  refused before anything changed; the message says why
#   4  installed, but upstream skipped an optional step; the summary names it
#   any other non-zero code is the failing tool's own: git 128, make 2,
#   timeout 124 when the fetch or make setup runs past OPENMONTAGE_SETUP_TIMEOUT
#
# Idempotent: a clean checkout at the pin is reused and `make setup` runs
# again, which only fills in what is missing. Anything else at the target is
# refused and left alone, because it may hold someone's productions.
set -euo pipefail

PIN="195eab24478dc9363326aec437aefc3701635ddf"
REPO="https://github.com/calesthio/OpenMontage.git"
DEST="${OPENMONTAGE_HOME:-$HOME/OpenMontage}"
# Upstream's CI runs 3.11; its .python-version says 3.10. 3.11 is the one
# that is tested, so ask for it. uv can fetch it when the machine lacks it;
# that path was not exercised here, where python3.11 was already installed.
PY="${OPENMONTAGE_PYTHON:-3.11}"
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
for tool in git make python3 npm npx; do
  command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
done
[ -z "$missing" ] || refuse "missing prerequisites:$missing"
if ! command -v uv >/dev/null 2>&1 && ! command -v "python$PY" >/dev/null 2>&1; then
  refuse "neither uv nor python$PY is on PATH, and upstream's make setup needs one of them. Install uv, or set OPENMONTAGE_PYTHON to a version whose python3.X is on PATH; upstream's README asks for 3.10 or newer."
fi
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
command -v timeout >/dev/null 2>&1 && limit="timeout $SETUP_TIMEOUT"

here="$(dirname "$(resolve "$0")")"
# Upstream pins no Python package. constraints.txt holds the versions measured
# in a working install, so every install resolves the same Python code.
constraints="$here/constraints.txt"
[ -f "$constraints" ] || refuse "$constraints is missing; it pins upstream's Python packages."
dest_abs="$(resolve "$DEST")"
if repo_root="$(git -C "$here" rev-parse --show-toplevel 2>&1)"; then
  repo_root="$(resolve "$repo_root")"
  case "$dest_abs/" in
    "$repo_root"/*)
      refuse "$dest_abs is inside $repo_root. Ruff and pytest would sweep OpenMontage's code into this repository's checks. Set OPENMONTAGE_HOME outside it."
      ;;
  esac
else
  echo "WARNING: could not find the repository this script lives in, so the inside-the-repository guard is off: $repo_root" >&2
fi

fetch_pin() {
  echo "==> Fetching OpenMontage $PIN into $dest_abs"
  # shellcheck disable=SC2086
  $limit git -C "$dest_abs" fetch -q --depth 1 origin "$PIN"
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
    # git init. The origin check above makes sure this script made it.
    echo "==> Resuming an interrupted fetch"
    fetch_pin
  elif [ "$have" != "$PIN" ]; then
    refuse "$dest_abs is at $have, not the pinned $PIN. Move it aside or set OPENMONTAGE_HOME."
  elif [ -n "$(git -C "$dest_abs" status --porcelain --untracked-files=no)" ]; then
    refuse "$dest_abs has local changes to tracked files, so make setup would not run the pinned code. See git -C $dest_abs status."
  else
    echo "==> $dest_abs is already at the pinned commit, with no local changes"
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
echo "==> make setup with Python $PY, at most ${SETUP_TIMEOUT}s; log: $log"
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
from tools.tool_registry import registry

registry.discover()
menu = registry.provider_menu()
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
