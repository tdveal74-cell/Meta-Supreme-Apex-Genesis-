#!/usr/bin/env bash
# Contract/sandbox validation only. No production worker, network or secrets.
set -euo pipefail
cd "$(dirname "$0")"
image="devon-browser-validation:${GITHUB_RUN_ID:-local}"
worker_log="$(mktemp)"
trap 'rm -f "$worker_log"' EXIT
docker build -t "$image" .
if ! docker run --rm --init --network none --user 10001:10001 --read-only \
  --cap-drop ALL --security-opt no-new-privileges:true \
  --security-opt "seccomp=$PWD/seccomp-browser.json" --pids-limit 128 \
  --memory 768m --cpus 1 --shm-size 128m \
  --tmpfs /tmp:rw,noexec,nosuid,size=128m,uid=10001,gid=10001,mode=700 \
  -e DEVON_TEST_CHROMIUM=/usr/bin/chromium -e DEVON_TEST_UDS=1 \
  "$image" node --test --test-reporter=tap /app/worker.test.mjs > "$worker_log" 2>&1; then
  cat "$worker_log"
  exit 1
fi
python3 - "$worker_log" <<'PY'
import re
import sys
from pathlib import Path
text = Path(sys.argv[1]).read_text()
for key, test in (("tests", lambda n: n >= 13), ("fail", lambda n: n == 0), ("skipped", lambda n: n == 0)):
    value = re.search(rf"^# {key} (\d+)$", text, re.M)
    if value is None or not test(int(value.group(1))):
        raise SystemExit("Real browser validation missing, failed or skipped: " + key)
print("Sandboxed Chromium worker: all tests executed, zero failures/skips")
PY
docker run --rm --network none --read-only --cap-drop ALL \
  --security-opt no-new-privileges:true --user 10001:10001 \
  --memory 128m --pids-limit 64 --cpus 1 \
  --mount "type=bind,src=$PWD,dst=/app,readonly" -w /app \
  python:3.12-slim@sha256:2259debdc6af85626058a15a7bf44ad6a68b8c98c9ae82a02cf5cdb92f096d47 \
  python -B -m unittest -v test_egress_proxy.py test_critic_boundaries.py
