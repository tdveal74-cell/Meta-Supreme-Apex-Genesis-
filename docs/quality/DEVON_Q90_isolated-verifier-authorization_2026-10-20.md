# DEVON Universal Quality-90: Authorized Isolated Verifier Stage

**Date:** 2026-10-20. **Owner:** Tee. **Authorization:** isolated/no-spend DEVON-owned verifier setup and staging integration on `srv1936199` only. **Not authorized:** production publication, paid generation, active n8n workflow mutation, live merge/release, or any real independent evidence signoff.

## Verified constraints

- At authorization check, Desktop Commander reported `srv1936199` **offline**, while `srv1936193` was online. The authorized target could not be accessed for installation. Do not claim anything is installed or running on the DEVON host.
- GitHub PR #377 was open and draft. Issue #380 was open. All previously completed CI suites were green at the earlier head; new stage files have their own CI checks, which must be checked on the latest head.
- The earlier direct read of `devon-soul` on `srv1936199` showed runtime `QUALITY_THRESHOLD = 99`. The 90 source is staged, not deployed.

## New isolated staged source

| Artifact | Purpose |
|---|---|
| `n8n/tqo-v5/slop-curator/devon_isolated_verifier.mjs` | Host-file-based local verifier. Reads only protected trust, exact final artifact, packet and detached review. Fails closed and **never** returns a production release authorization |
| `n8n/tqo-v5/slop-curator/devon_isolated_verifier.test.mjs` | Negative tests: absent independent signature, changed content, permissive permissions, symlink input, path traversal and invalid data must HOLD |
| `deploy/quality90/install-isolated-stage.sh` | Root-owned one-time installer for an isolated directory on the authorized DEVON host. Creates only module files and an **empty, disabled** trust registry. Does not launch a service or integrate n8n |
| `.github/workflows/ci.yml` | Adds isolated-verifier tests and a nonexecuting installer syntax check |

### Stage-only semantics

- Required stage directory: `/opt/devon/quality90-isolated`.
- Required host controls: directories owner-only 0700; trust, packet, final artifact and review files owner-only 0600; reject symlinks, invalid owner, disallowed paths or malformed data.
- Review packet is bound to the **exact final bytes** and policy/rubric/brand/canon/source references.
- Receipt must be detached Ed25519-signed, issuer-authorized, and valid under a protected public-key registry. The **private key and evidence-checking signer are intentionally not installed**.
- With an empty registry or missing independent review the result is **`HOLD`**.
- Even a valid independent receipt returns only **`VERIFIED_STAGING_ONLY`**, never release, paid generation, merge or publication.
- Never allow n8n or a draft author to create or change the trusted registry, issue the review signature, or substitute a `verified=true` model output for evidence.

## Authorized host setup (NOT executed as of this document)

After Desktop Commander and the host owner's control are verified:

```sh
# In a reviewed PR checkout on srv1936199. Do not run on an active n8n host.
sudo bash deploy/quality90/install-isolated-stage.sh \
  "${PWD}/n8n/tqo-v5/slop-curator"

# Without a real independently issued packet and trusted signing key,
# the stage deliberately returns HOLD, not an approval:
sudo DEVON_Q90_STAGE_ROOT=/opt/devon/quality90-isolated \
  node /opt/devon/quality90-isolated/code/devon_isolated_verifier.mjs sample-review-id
```

The second command uses no network, signer, providers, media generation, or live n8n data. No sample stage review should be fabricated to make it pass.

## Actual closure dependencies

1. Restore the authorized connection to `srv1936199`, verify identity/permissions and deploy the **isolated stage only**, then read back installed module hashes and a missing-signature `HOLD`.
2. Select an independently authorized editorial reviewer and evidence/canon verifier. Design source-snapshot and user-authenticated approval intake; provision public trust key under a separate human-controlled process. Do not put the private key in repo, ChatGPT, n8n, Docker container images, or logs.
3. Verify final-artifact SHA-256 **after** all script expansions and alterations and independently read the immutable final artifact. Verify 89 fails, 90 only meets the numeric floor, and hard evidence/canon failures remain HOLD.
4. Create a distinct inactive n8n staging route without paid/publishing credentials, run no-spend transport/readback tests and prevent manual status/WAIVED bypass.
5. Only with a **separate explicit** deployment authorization and approved rollback, update live workflows; confirm actual DEVON runtime floor and all affected brand routes.
6. Close issue #380 only with date-stamped independent production readback receipts per active lane.

**Honest current status:** Authorized setup, staged code, runtime target offline, real independent signer absent, no active-workflow change, no production release.
