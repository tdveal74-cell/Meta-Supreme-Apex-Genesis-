#!/usr/bin/env bash
# Trusted continuous observer. Candidate makers never receive this interface.
set -euo pipefail
umask 077
ROOT="${1:?absolute release directory required}"
TRUST="${2:?operator-pinned manifest SHA-256 required}"
IMAGE="${3:?local Python image ID required}"
STATE="${4:?operator state directory required}"
INBOX="${5:?read-only fixture inbox required}"
[[ "$ROOT" =~ ^/opt/devon/rsi/releases/[a-f0-9]{40}$ ]]
[[ "$TRUST" =~ ^[a-f0-9]{64}$ && "$IMAGE" =~ ^sha256:[a-f0-9]{64}$ ]]
[[ "$STATE" == /opt/devon/rsi/operator-state && "$INBOX" == /opt/devon/rsi/runs ]]
python3 - "$ROOT" "$STATE" "$INBOX" <<'PY'
import sys
from pathlib import Path
for arg in sys.argv[1:]:
    path = Path(arg)
    if path.resolve() != path or any(p.is_symlink() for p in [path, *path.parents]):
        raise SystemExit('REJECT_PATH')
PY
[[ -f "$ROOT/tools/devon_rsi_ops/service.py" && -d "$INBOX" ]]
install -d -m 700 "$STATE"
chown 65534:65534 "$STATE"
# A single named worker and durable state survive host restarts. Failures exit
# and are NOT restarted automatically; the operator must inspect a HOLD.
exec docker run --rm --name devon-rsi-observer \
  --network none --read-only --cap-drop ALL --security-opt no-new-privileges \
  --user 65534:65534 --pids-limit 64 --memory 192m --cpus 0.5 \
  --tmpfs /tmp:rw,noexec,nosuid,size=32m \
  --mount "type=bind,src=$ROOT/tools,dst=/app/tools,readonly" \
  --mount "type=bind,src=$STATE,dst=/state" \
  --mount "type=bind,src=$INBOX,dst=/inbox,readonly" \
  --workdir /app --env PYTHONDONTWRITEBYTECODE=1 \
  --log-driver local --log-opt max-size=5m --log-opt max-file=3 \
  --entrypoint python3 "$IMAGE" -B -X pycache_prefix=/tmp/devon-rsi-bytecode \
  -m tools.devon_rsi_ops.service --state /state --inbox /inbox \
  --trust-sha256 "$TRUST" --watch
