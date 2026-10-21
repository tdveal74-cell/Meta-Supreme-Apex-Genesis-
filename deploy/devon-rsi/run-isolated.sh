#!/usr/bin/env bash
# Trusted operator invocation, never exposed to candidate code or text.
set -euo pipefail
umask 077
ROOT="${1:?absolute release directory required}"
TRUST="${2:?operator-pinned release manifest SHA-256 required}"
IMAGE="${3:?local Python image ID required}"
RUN="${4:?new absolute run directory required}"
[[ "$ROOT" =~ ^/opt/devon/rsi/releases/[a-f0-9]{40}$ ]]
[[ "$RUN" =~ ^/opt/devon/rsi/runs/[A-Za-z0-9_-]+$ ]]
[[ "$TRUST" =~ ^[a-f0-9]{64}$ && "$IMAGE" =~ ^sha256:[a-f0-9]{64}$ ]]
[[ ! -e "$RUN" && ! -L "$RUN" && ! -L "$ROOT" ]]
[[ -f "$ROOT/tools/devon_rsi/release.json" ]]
python3 - "$ROOT" "$RUN" <<'PY'
import sys
from pathlib import Path
for arg in sys.argv[1:]:
    path = Path(arg)
    if path.resolve() != path or any(p.is_symlink() for p in [path, *path.parents]):
        raise SystemExit('REJECT_PATH')
PY
install -d -m 700 "$RUN"
chown 65534:65534 "$RUN"
# No secrets, no Docker socket, no live vault, no host root and no network.
# All descendants are killed by Docker when timeout terminates the invocation.
NAME="devon-rsi-$(date -u +%Y%m%d%H%M%S)-$$"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
timeout --signal=TERM --kill-after=5 75 docker run --rm --name "$NAME" \
  --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --user 65534:65534 --pids-limit 64 --memory 128m --cpus 1 \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  --mount "type=bind,src=$ROOT/tools,dst=/app/tools,readonly" \
  --mount "type=bind,src=$RUN,dst=/reports" \
  --workdir /app --env PYTHONDONTWRITEBYTECODE=1 \
  --entrypoint python3 "$IMAGE" -B -X pycache_prefix=/tmp/devon-rsi-bytecode -m tools.devon_rsi.runner \
  --output /reports/evaluation --trust-sha256 "$TRUST"
