#!/usr/bin/env bash
# Install OpenMontage at the pinned commit, outside this repository.
#
# Idempotent: a checkout already at the pin is reused and `make setup` runs
# again, which only fills in what is missing. A checkout at any other commit
# is refused rather than moved, because it may hold someone's productions.
set -euo pipefail

PIN="195eab24478dc9363326aec437aefc3701635ddf"
REPO="https://github.com/calesthio/OpenMontage.git"
DEST="${OPENMONTAGE_HOME:-$HOME/OpenMontage}"
# Upstream's CI runs 3.11; its .python-version says 3.10. 3.11 is the one
# that is tested, so ask for it. uv fetches it when the machine lacks it.
PY="${OPENMONTAGE_PYTHON:-3.11}"

here="$(cd "$(dirname "$0")" && pwd)"
repo_root="$(git -C "$here" rev-parse --show-toplevel 2>/dev/null || true)"
dest_abs="$(realpath -m "$DEST")"
if [ -n "$repo_root" ]; then
  case "$dest_abs/" in
    "$repo_root"/*)
      echo "REFUSED: $dest_abs is inside $repo_root. Ruff and pytest would sweep OpenMontage's code into this repository's checks. Set OPENMONTAGE_HOME outside it." >&2
      exit 2
      ;;
  esac
fi

fetch_pin() {
  echo "==> Fetching OpenMontage $PIN into $dest_abs"
  git -C "$dest_abs" fetch -q --depth 1 origin "$PIN"
  git -C "$dest_abs" checkout -q --detach FETCH_HEAD
}

if [ -e "$dest_abs" ]; then
  if [ ! -d "$dest_abs/.git" ]; then
    echo "REFUSED: $dest_abs exists and is not a git checkout." >&2
    exit 2
  fi
  have="$(git -C "$dest_abs" rev-parse -q --verify HEAD || true)"
  if [ -z "$have" ]; then
    # No commit yet. That is what a first run leaves when the fetch dies
    # after git init, so resume it, but only for a repository this script
    # made: one whose origin is OpenMontage.
    origin="$(git -C "$dest_abs" remote get-url origin 2>/dev/null || true)"
    if [ "$origin" != "$REPO" ]; then
      echo "REFUSED: $dest_abs is an empty git repository whose origin is not $REPO." >&2
      exit 2
    fi
    echo "==> Resuming an interrupted fetch"
    fetch_pin
  elif [ "$have" != "$PIN" ]; then
    echo "REFUSED: $dest_abs is at $have, not the pinned $PIN. Move it aside or set OPENMONTAGE_HOME." >&2
    exit 2
  else
    echo "==> $dest_abs is already at the pinned commit"
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

make -C "$dest_abs" setup PYTHON_VERSION="$PY"

# make setup prints [skip] and carries on when an optional piece fails, so a
# zero exit does not prove the core works. Load the tool registry the way
# upstream's own preflight target does and count what it found.
"$dest_abs/.venv/bin/python" - "$dest_abs" <<'PYEOF'
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

echo "OK: OpenMontage $PIN installed at $dest_abs"
