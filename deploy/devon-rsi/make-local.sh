#!/usr/bin/env bash
# One bounded request to Tee's already installed local model. No paid endpoint.
# Called by the operator, outside the evaluator. No suite is sent to the maker.
set -euo pipefail
umask 077
ROOT="${1:?release directory required}"
OUT="${2:?new maker output directory required}"
[[ "$ROOT" =~ ^/opt/devon/rsi/releases/[a-f0-9]{40}$ ]]
[[ "$OUT" =~ ^/opt/devon/rsi/maker/[A-Za-z0-9_-]+$ ]]
[[ ! -e "$OUT" && ! -L "$OUT" && ! -L "$ROOT" ]]
python3 - "$ROOT" "$OUT" <<'PY'
import sys
from pathlib import Path
for arg in sys.argv[1:]:
    path = Path(arg)
    if path.resolve() != path or any(p.is_symlink() for p in [path, *path.parents]):
        raise SystemExit('REJECT_PATH')
PY
install -d -m 700 "$OUT"
PYTHONPATH="$ROOT" python3 -B -X "pycache_prefix=$OUT/bytecode" -m tools.devon_rsi.maker > "$OUT/request.json"
NAME="devon-rsi-maker-$(date -u +%Y%m%d%H%M%S)-$$"
trap 'docker rm -f "$NAME" >/dev/null 2>&1 || true' EXIT
timeout --signal=TERM --kill-after=5 50 docker run --rm -i --name "$NAME" \
  --network container:rakazo-local-model --read-only --cap-drop ALL \
  --security-opt no-new-privileges --pids-limit 32 --memory 32m --cpus 0.5 \
  --entrypoint curl curlimages/curl:latest \
  --fail --silent --show-error --max-time 45 --max-filesize 65536 \
  --header 'Content-Type: application/json' --data-binary @- \
  http://127.0.0.1:11434/api/generate < "$OUT/request.json" > "$OUT/response.json"
PYTHONPATH="$ROOT" python3 -B -X "pycache_prefix=$OUT/bytecode" - "$OUT" <<'PY'
import json
import sys
from pathlib import Path
from tools.devon_rsi.kernel import candidate, canonical, read_json, strict_load
out = Path(sys.argv[1])
try:
    response = read_json(out / 'response.json')
    if response.get('done') is not True:
        raise ValueError('incomplete')
    proposal = candidate(strict_load(response['response'].encode()))
    (out / 'candidate.json').write_bytes(canonical(proposal) + b'\n')
    (out / 'receipt.json').write_text(json.dumps({
        'status': 'CANDIDATE_ONLY', 'model': response.get('model'),
        'eval_count': response.get('eval_count'), 'paid_api_calls': 0,
        'promoted': False, 'gain_claim': False,
    }, indent=2))
    print('CANDIDATE_ONLY_NO_PROMOTION')
except (ValueError, KeyError, TypeError, OSError):
    print('REJECT_MAKER_RESPONSE')
    raise SystemExit(2)
PY
