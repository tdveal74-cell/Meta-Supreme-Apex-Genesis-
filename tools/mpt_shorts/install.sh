#!/usr/bin/env bash
# Install MoneyPrinterTurbo at the audited commit, locked for render_short.py.
#
# Everything is pinned: the commit, uv, the project's own uv.lock (hashed, and
# carrying the patched Pillow override the plain pip route misses), and the
# caption model by revision and sha256. Nothing is piped into a shell, no
# provider key is asked for or written, and nothing is started. Re-running it
# keeps a config.toml that still passes the audit and refuses one that does not.
#
#   tools/mpt_shorts/install.sh /opt/mpt-shorts
#
# Needs git, curl, sha256sum, ffmpeg, ffprobe and python3 3.11 to 3.14 on the host.
set -euo pipefail

DEST="${1:?usage: install.sh DEST}"
HERE="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
COMMIT=27843a994bfa29c43c02150861d51490a6ca4bd2
UV_VERSION=0.11.32
MODEL=Systran/faster-whisper-base.en
MODEL_REV=3d3d5dee26484f91867d81cb899cfcf72b96be6c
MODEL_SUMS="f3bc3821e9fc76a27bae538e11ae5b677dcdd352b4600429ce7951d398569aeb  config.json
2a166925539a16005f14ff328359f9b9adb9dc4fb631bb3b227526862e93e2ef  model.bin
929c5252409436dce1b38a75d1abbcb5e132d170d8e324e4e04ed915fa2d22df  tokenizer.json
ff77588746d3a2595d32ab5b69ffd7b95ce2441ac57533cb66fc3eb575a115cf  vocabulary.txt"

for tool in git curl sha256sum ffmpeg ffprobe python3; do
  command -v "$tool" >/dev/null || { echo "missing on PATH: $tool" >&2; exit 2; }
done
# The python3 first on PATH, by absolute path, so uv cannot swap in another.
# Asked for a bare "python3", uv 0.11.32 picked the uv-managed CPython 3.15 on
# srv1936199 over /usr/bin/python3, and ctranslate2 4.7.1 (the caption model)
# ships no 3.15 wheel.
PY="$(python3 -c 'import os, sys; print(os.path.abspath(sys.executable))')"
[ -x "$PY" ] || { echo "python3 did not report an absolute path to itself" >&2; exit 2; }
"$PY" -c 'import sys; sys.exit(not (3, 11) <= sys.version_info[:2] <= (3, 14))' \
  || { echo "python3 must be 3.11 to 3.14; ctranslate2 4.7.1 has wheels for those only" >&2; exit 2; }

mkdir -p "$DEST/ledger"
DEST="$(cd "$DEST" && pwd)"  # absolute, because later steps cd into the checkout
MPT="$DEST/mpt"
if [ ! -d "$MPT/.git" ]; then
  git clone --quiet --filter=blob:none https://github.com/harry0703/MoneyPrinterTurbo.git "$MPT"
fi
git -C "$MPT" -c advice.detachedHead=false checkout --quiet --detach "$COMMIT"
[ "$(git -C "$MPT" rev-parse HEAD)" = "$COMMIT" ] || { echo "checkout is not $COMMIT" >&2; exit 2; }

if [ ! -x "$DEST/uv-env/bin/uv" ]; then
  "$PY" -m venv "$DEST/uv-env"
  "$DEST/uv-env/bin/pip" install --quiet --progress-bar off "uv==$UV_VERSION"
fi
(cd "$MPT" && UV_PYTHON_PREFERENCE=only-system UV_PYTHON_DOWNLOADS=never \
  "$DEST/uv-env/bin/uv" sync --quiet --frozen --no-dev --python "$PY")

WHISPER="$MPT/models/whisper-base.en"
mkdir -p "$WHISPER"
if ! (cd "$WHISPER" && printf '%s\n' "$MODEL_SUMS" | sha256sum --quiet -c - >/dev/null 2>&1); then
  for f in config.json model.bin tokenizer.json vocabulary.txt; do
    curl -fsSL --retry 3 -o "$WHISPER/$f" "https://huggingface.co/$MODEL/resolve/$MODEL_REV/$f"
  done
  (cd "$WHISPER" && printf '%s\n' "$MODEL_SUMS" | sha256sum --quiet -c -)
fi

if [ -f "$MPT/config.toml" ]; then
  python3 "$HERE/render_short.py" audit --mpt-root "$MPT"
else
  python3 "$HERE/render_short.py" lock-config --mpt-root "$MPT"
fi
echo "installed: $MPT at $COMMIT; render with --mpt-python $MPT/.venv/bin/python --ledger $DEST/ledger"
