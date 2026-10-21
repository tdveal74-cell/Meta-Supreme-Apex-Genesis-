#!/usr/bin/env bash
# Authorized isolated DEVON quality-90 staging installation only.
# No model calls, private keys, n8n updates, network listeners or release actions.
set -euo pipefail
umask 077

EXPECTED="/opt/devon/quality90-isolated"
TARGET="${DEVON_Q90_STAGE_ROOT:-$EXPECTED}"
SOURCE="${1:-}"

if [[ "$TARGET" != "$EXPECTED" ]]; then
  echo "HOLD: refused unreviewed staging destination" >&2
  exit 2
fi
if [[ -z "$SOURCE" || ! -d "$SOURCE" ]]; then
  echo "HOLD: explicit checked-out plugin source directory required" >&2
  exit 2
fi
if [[ -e "$TARGET" ]]; then
  echo "HOLD: isolated staging destination already exists; do not overwrite" >&2
  exit 2
fi
if [[ "$(id -u)" != 0 ]]; then
  echo "HOLD: isolated stage must be provisioned by the authorized host owner" >&2
  exit 2
fi
for mod in ecosystem_review_gate.mjs public_key_review_verifier.mjs secure_review_intake.mjs devon_isolated_verifier.mjs; do
  test -f "$SOURCE/$mod" || { echo "HOLD: missing reviewed module $mod" >&2; exit 2; }
done

install -d -m 700 "$TARGET" "$TARGET/code" "$TARGET/trust" "$TARGET/reviews"
for mod in ecosystem_review_gate.mjs public_key_review_verifier.mjs secure_review_intake.mjs devon_isolated_verifier.mjs; do
  install -m 600 "$SOURCE/$mod" "$TARGET/code/$mod"
done
# Explicitly empty allowlist: no verifier can pass without an independently
# provisioned trust registry and valid detached review. Never install a signer.
printf '%s\n' '{"schemaVersion":"quality90-trust-v1","registryRevision":"unprovisioned-hold-v1","keys":{}}' > "$TARGET/trust/registry.json"
chmod 600 "$TARGET/trust/registry.json"

echo "STAGING_INSTALLED_NO_SIGNER_NO_ACTIVE_WORKFLOW"
echo "Directory: $TARGET"
echo "Run manual checks only. No service, route or publisher was started."
