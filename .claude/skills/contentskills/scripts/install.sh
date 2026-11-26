#!/usr/bin/env bash
# Install ContentSkills by Blotato at the pinned commit, outside this repository.
#
# Exit codes:
#   0  installed: checkout at the pin, upstream's `npm run setup` finished, the
#      three Python environments import, the voice model files match their
#      checksums, the headless browser is present, and every media file is the
#      real file
#   1  a check after the fetch or after `npm run setup` failed; FAILED says which
#   3  refused before anything changed; the message says why
#   4  installed, but some example or gallery media is still an LFS pointer
#   any other non-zero code is the failing tool's own (git 128, npm 1, timeout 124)
#
# Idempotent: a checkout at the pin with no change to a tracked file and no
# untracked file that would load as code is reused, and `npm run setup` runs
# again, which only fills in what is missing. Anything else at the target is
# refused and left alone, because it may hold someone's projects.
set -euo pipefail

PIN="d137fbf17e4a8614d41185535c32b284e4845e4b"
REPO="https://github.com/blotato/contentskills.git"
DEST="${CONTENTSKILLS_HOME:-$HOME/contentskills}"
SETUP_TIMEOUT="${CONTENTSKILLS_SETUP_TIMEOUT:-1800}"
# upstream's setup.mjs installs `chrome-headless-shell@stable` through an
# unpinned `npx --yes @puppeteer/browsers`. When CONTENTSKILLS_HEADLESS_SHELL_VERSION
# is set, this script installs exactly that build first, and setup.mjs then
# skips its own download.
PUPPETEER_BROWSERS_VERSION="${CONTENTSKILLS_PUPPETEER_BROWSERS_VERSION-3.3.0}"
HEADLESS_SHELL_VERSION="${CONTENTSKILLS_HEADLESS_SHELL_VERSION-158.0.8127.88}"

refuse() {
  echo "REFUSED: $*" >&2
  exit 3
}

resolve() {
  python3 -c 'import os, sys; print(os.path.realpath(sys.argv[1]))' "$1"
}

missing=""
for tool in git node npm npx uv ffmpeg ffprobe python3; do
  command -v "$tool" >/dev/null 2>&1 || missing="$missing $tool"
done
[ -z "$missing" ] || refuse "missing prerequisites:$missing. Upstream's setup needs uv and ffmpeg on PATH, and node 22 or newer."
case "$SETUP_TIMEOUT" in
  ''|*[!0-9]*|0*) refuse "CONTENTSKILLS_SETUP_TIMEOUT must be a whole number of seconds above 0 with no leading zero, not '$SETUP_TIMEOUT'; timeout reads 0 and 00 alike as no limit at all." ;;
esac
node_major="$(node -p 'process.versions.node.split(".")[0]' 2>/dev/null || echo 0)"
[ "$node_major" -ge 22 ] 2>/dev/null \
  || refuse "Node $node_major found; upstream's package.json says 22 or newer and pipeline/watch.mjs uses import.meta.dirname."

ver() {
  command -v "$1" >/dev/null 2>&1 || { echo "none"; return 0; }
  local out
  out="$("$@" 2>/dev/null | sed -n 1p)" || true
  echo "${out:-unknown}"
}
echo "==> Found node: $(ver node --version); npm: $(ver npm --version); uv: $(ver uv --version); ffmpeg: $(ver ffmpeg -version | cut -d' ' -f3)"

limit=""
if command -v timeout >/dev/null 2>&1; then
  limit="timeout $SETUP_TIMEOUT"
  cap="at most ${SETUP_TIMEOUT}s"
else
  cap="no time limit"
  echo "WARNING: timeout is not on PATH, so the fetch and npm run setup run with no time limit." >&2
fi

here="$(dirname "$(resolve "$0")")"
dest_abs="$(resolve "$DEST")"
if repo_root="$(git -C "$here" rev-parse --show-toplevel 2>/dev/null)"; then
  repo_root="$(resolve "$repo_root")"
  case "$dest_abs/" in
    "$repo_root"/*)
      refuse "$dest_abs is inside $repo_root. Its AGPL-3.0 code does not belong in this tree, and ruff and pytest would sweep it into this repository's checks. Set CONTENTSKILLS_HOME outside it."
      ;;
  esac
else
  echo "WARNING: could not find the repository this script lives in, so the inside-the-repository guard is off." >&2
fi
case "$dest_abs" in
  *[[:space:]]*) refuse "$dest_abs has whitespace in it; upstream's npm scripts hand paths to shells and Python. Choose a path without spaces." ;;
esac

# Untracked files that would load as code: .py/.pyc/.so/.js/.mjs/.cjs anywhere
# under pipeline, library, dashboard or templates, or at the top level.
# --others without --exclude-standard, on purpose: upstream's .gitignore
# ignores *.py[cod], and an ignored .pyc still imports.
untracked_code() {
  git -C "$dest_abs" ls-files --others -- \
    ':(glob)pipeline/**' ':(glob)library/**' ':(glob)dashboard/**' ':(glob)templates/**' \
    ':(glob)*.py' ':(glob)*.pyc' ':(glob)*.so' ':(glob)*.js' ':(glob)*.mjs' ':(glob)*.cjs' \
    | grep -E '\.(py|pyc|so|js|mjs|cjs)$' | grep -v '/__pycache__/' || true
}

# Every media file tracked through LFS must be either its untouched pointer or
# a file whose SHA-256 is the one the pointer names.
# Prints "real=<n> pointer=<n> bad=<n>"; lists anything bad; exits 1 if any.
media_check() {
  python3 - "$dest_abs" <<'PYEOF'
import hashlib, re, subprocess, sys
root = sys.argv[1]
media = re.compile(r"\.(mov|mp4|webm|m4v|mkv|mp3)$", re.I)
listed = subprocess.run(["git", "-C", root, "ls-files", "-s", "-z"], capture_output=True, check=True).stdout
rows = []
for entry in listed.split(b"\0"):
    if not entry:
        continue
    meta, path = entry.split(b"\t", 1)
    path = path.decode()
    if media.search(path):
        rows.append((meta.split(b" ")[1].decode(), path))
pointers = {}
if rows:
    out = subprocess.run(["git", "-C", root, "cat-file", "--batch"], input="\n".join(b for b, _ in rows).encode() + b"\n", capture_output=True, check=True).stdout
    pos = 0
    for blob, path in rows:
        header_end = out.index(b"\n", pos)
        size = int(out[pos:header_end].decode().split()[2])
        body = out[header_end + 1:header_end + 1 + size]
        pos = header_end + 1 + size + 1
        m = re.search(rb"oid sha256:([0-9a-f]{64})", body)
        pointers[path] = (body, m.group(1).decode() if m else None)
real = pointer = 0
bad = []
for _, path in rows:
    body, oid = pointers[path]
    try:
        with open(f"{root}/{path}", "rb") as f:
            data = f.read()
    except OSError as e:
        bad.append(f"{path}: {e.strerror}")
        continue
    if data == body:
        pointer += 1
    elif oid and hashlib.sha256(data).hexdigest() == oid:
        real += 1
    else:
        bad.append(f"{path}: neither the LFS pointer nor a file with its SHA-256")
print(f"real={real} pointer={pointer} bad={len(bad)}")
for line in bad:
    print("  " + line)
sys.exit(1 if bad else 0)
PYEOF
}

fetch_pin() {
  echo "==> Fetching ContentSkills $PIN into $dest_abs"
  local status=0
  # LFS objects are not fetched here: this cloud session's git proxy serves
  # none, and upstream's setup.mjs fetches each over HTTPS and checks its hash.
  # shellcheck disable=SC2086
  GIT_LFS_SKIP_SMUDGE=1 $limit git -C "$dest_abs" fetch -q --depth 1 origin "$PIN" || status=$?
  if [ "$status" -ne 0 ]; then
    echo "FAILED: the fetch exited $status (124 means it ran past ${SETUP_TIMEOUT}s)." >&2
    exit "$status"
  fi
  GIT_LFS_SKIP_SMUDGE=1 git -C "$dest_abs" checkout -q --detach FETCH_HEAD
}

if [ -e "$dest_abs" ]; then
  [ -d "$dest_abs/.git" ] || refuse "$dest_abs exists and is not a git checkout."
  if ! git_err="$(git -C "$dest_abs" rev-parse --git-dir 2>&1 >/dev/null)"; then
    refuse "git cannot read $dest_abs: $git_err"
  fi
  origin="$(git -C "$dest_abs" config --get remote.origin.url || true)"
  [ "$origin" = "$REPO" ] || refuse "$dest_abs has origin '${origin:-none}', not $REPO."
  have="$(git -C "$dest_abs" rev-parse -q --verify HEAD || true)"
  if [ -z "$have" ]; then
    echo "==> Resuming an interrupted fetch"
    fetch_pin
    if ! extra="$(untracked_code)" || [ -n "$extra" ]; then
      echo "FAILED: $dest_abs held files the pin does not carry, which the pipeline would load: $extra" >&2
      exit 1
    fi
  elif [ "$have" != "$PIN" ]; then
    refuse "$dest_abs is at $have, not the pinned $PIN. Move it aside or set CONTENTSKILLS_HOME."
  elif ! changes="$(GIT_LFS_SKIP_SMUDGE=1 git -C "$dest_abs" status --porcelain --untracked-files=no)"; then
    refuse "git status failed in $dest_abs, so its files cannot be checked."
  elif [ -n "$changes" ]; then
    refuse "$dest_abs has local changes to tracked files, so the pipeline would not run the pinned code. See git -C $dest_abs status."
  elif ! extra="$(untracked_code)"; then
    refuse "git ls-files failed in $dest_abs, so its files cannot be checked."
  elif [ -n "$extra" ]; then
    refuse "$dest_abs has files the pin does not carry, which the pipeline would load: $extra"
  elif ! media_report="$(media_check)"; then
    refuse "$dest_abs has a media file that is neither its LFS pointer nor the file that pointer names: $media_report"
  else
    echo "==> $dest_abs is already at the pinned commit, nothing changed or untracked that would load as code, media intact ($media_report)"
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

log="$dest_abs/contentskills-setup.log"
: > "$log"

have_browser() {
  (cd "$dest_abs" && node -e 'import("./pipeline/tools.mjs").then(m => { const f = m.findFile(m.paths.browser, m.browserName); if (!f) process.exit(1); console.log(f); })' 2>/dev/null)
}
if ! have_browser >/dev/null; then
  if [ -n "$HEADLESS_SHELL_VERSION" ]; then
    echo "==> Installing chrome-headless-shell $HEADLESS_SHELL_VERSION through @puppeteer/browsers $PUPPETEER_BROWSERS_VERSION, $cap"
    mkdir -p "$dest_abs/.tools/browser"
    set +e
    # shellcheck disable=SC2086
    (cd "$dest_abs" && $limit npx --yes "@puppeteer/browsers@$PUPPETEER_BROWSERS_VERSION" install "chrome-headless-shell@$HEADLESS_SHELL_VERSION" --path "$dest_abs/.tools/browser") 2>&1 | tee -a "$log"
    status=${PIPESTATUS[0]}
    set -e
    if [ "$status" -ne 0 ]; then
      echo "FAILED: the pinned browser install exited $status. See $log" >&2
      exit "$status"
    fi
  else
    echo "WARNING: CONTENTSKILLS_HEADLESS_SHELL_VERSION is empty, so upstream's setup.mjs fetches chrome-headless-shell@stable, whatever that is today. The build it chose is printed below." >&2
  fi
fi

# upstream's setup.mjs: media over HTTPS, three uv environments on Python 3.13,
# the Kokoro model files (SHA-256 checked by upstream), the browser.
# VIRTUAL_ENV and CONDA_PREFIX are cleared so uv builds into .tools/.
echo "==> npm run setup, $cap; log: $log"
set +e
# shellcheck disable=SC2086
(cd "$dest_abs" && env -u VIRTUAL_ENV -u CONDA_PREFIX GIT_LFS_SKIP_SMUDGE=1 $limit npm run --silent setup) 2>&1 | tee -a "$log"
status=${PIPESTATUS[0]}
set -e
if [ "$status" -ne 0 ]; then
  echo "FAILED: npm run setup exited $status (124 means it ran past ${SETUP_TIMEOUT}s). See $log" >&2
  exit "$status"
fi

# setup.mjs prints a check mark and carries on, so re-measure what it claims.
failed=""
for env_name in voice effects transcribe; do
  py="$dest_abs/.tools/venv-$env_name/bin/python"
  case "$env_name" in
    voice) probe='import kokoro_onnx, phonemizer, soundfile, onnxruntime' ;;
    effects) probe='import cv2, numpy, moderngl' ;;
    transcribe) probe='import faster_whisper, av' ;;
  esac
  if [ -x "$py" ] && "$py" -c "$probe" 2>/dev/null; then
    echo "==> $env_name environment imports ($("$py" -c 'import sys; print("Python %d.%d.%d" % sys.version_info[:3])'))"
  else
    failed="$failed $env_name-environment"
  fi
done
if browser_bin="$(have_browser)"; then
  echo "==> headless browser: $browser_bin"
else
  browser_bin=""
  failed="$failed headless-browser"
fi
voice_ok="$(cd "$dest_abs" && node -e '
import("./pipeline/tools.mjs").then(async m => {
  const {createHash} = await import("node:crypto"); const {readFileSync, existsSync} = await import("node:fs"); const {join} = await import("node:path");
  let ok = 0;
  for (const f of m.voiceModelFiles) { const p = join(m.paths.voiceModels, f.name); if (existsSync(p) && createHash("sha256").update(readFileSync(p)).digest("hex") === f.sha256) ok++; }
  console.log(`${ok}/${m.voiceModelFiles.length}`);
})' 2>/dev/null || echo "0/?")"
echo "==> voice model files matching their checksums: $voice_ok"
case "$voice_ok" in
  3/3) ;;
  *) failed="$failed voice-model-files($voice_ok)" ;;
esac
if ! media_report="$(media_check)"; then
  echo "FAILED: a media file is neither its LFS pointer nor the file that pointer names: $media_report" >&2
  exit 1
fi
echo "==> media: $media_report"
if [ -n "$failed" ]; then
  echo "FAILED: npm run setup exited 0 but these did not check out:$failed. See $log" >&2
  exit 1
fi

if [ -n "$HEADLESS_SHELL_VERSION" ]; then
  case "$browser_bin" in
    *"$HEADLESS_SHELL_VERSION"*) ;;
    *) echo "WARNING: the browser in use is not the pinned build $HEADLESS_SHELL_VERSION: $browser_bin" >&2 ;;
  esac
fi

echo "==> Resolved package counts (uv pip freeze --python <env>/bin/python for the list):"
for env_name in voice effects transcribe; do
  count="$(uv pip freeze --python "$dest_abs/.tools/venv-$env_name/bin/python" 2>/dev/null | wc -l | tr -d ' ')"
  echo "    $env_name: $count packages"
done

case "$media_report" in
  *"pointer=0 "*) ;;
  *)
    echo "DEGRADED: ContentSkills $PIN installed at $dest_abs, but some example or gallery media is still a pointer ($media_report). Run the installer again to retry the download." >&2
    exit 4
    ;;
esac
echo "OK: ContentSkills $PIN installed at $dest_abs"
