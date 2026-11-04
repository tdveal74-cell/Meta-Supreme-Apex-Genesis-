# Gemini provider compatibility candidate

Status: validated isolated code candidate; provider activation is held.
Supersedes: no historical record. Qualifies the staged-provider update notices.

## Verified blocker

At main 9752eb08f8c9e08ab859567c4008df789dcc3be8, factory selection of gemini
raises ProviderConfigError; Presence primary and fallback settings reject it.
An independent verifier reproduced both without keys or inference.
API provider construction is lazy, so healthy startup would not prove readiness.
Presence settings validate during app construction and would prevent startup.
The staged Railway patch must not be committed before compatible code deploys.

The separate repository /opt/devon/gemini-migration-20261102 held three unmerged
commits: eb8a80d, 165af69 and 50f054f. This candidate adopts the first two on
current main and excludes 50f054f's provider-policy status changes. A local
branch is not production evidence.

## Candidate behavior

Gemini uses Google's OpenAI-compatible chat completions endpoint, its own key,
max_tokens, configured model gemini-3.8-flash and low reasoning for 3.8.
Deprecated 3.8 sampling parameters are omitted. Other configured Gemini model
families retain their sampling contract. Model defaults for existing providers,
mock defaults, tenant metering, effect approvals and embeddings stay intact.
Malformed success payloads refuse with ProviderResponseError, including missing
or non-string content and missing, negative, boolean or non-integer token counts.
An empty filtered string remains a typed result with measured usage.
The bootstrap reads Gemini input silently and passes it to its Python child by
private environment, not argv. Its Pinecone input block remains independent.
New installs configure Gemini; this script was not run against a live .env.

Originals read November 4, 2026:
https://aistudio.google.com/docs/openai
https://aistudio.google.com/docs/models/gemini-3.8-flash
https://aistudio.google.com/docs/whats-new-gemini-3.8
No upstream Hermes package, new SDK or dependency is installed.

## Network evidence and limits

Public Google DNS matches both VPS resolutions: API 69.46.46.24 and Presence
69.46.46.26. No matching local hosts override was found. TCP 80 and 443 timed
out from srv1936199, and both health hosts also timed out from srv1936193.
Railway's homepage timed out from the VPS as well; self-hosted n8n returned 200.
Railway reports API and Presence online, each one running replica, zero recent
failures, and scheduler's last execution succeeded. This does not prove public
reachability or inference. Device policy rejected firewall inspection; no policy
was changed. The failing network boundary remains unverified and no restart or
route change was made on speculation.

## Activation plan, held for review

Existing Railway patch: 0b5a7869-182d-49d0-b24d-6643ec8f0cda. It contains nine
variable fields across three services; the generic status also counts three
service-update entries, so it reports twelve changes. Values are redacted and
were not inferred. No key was recreated or replaced.

Proposed exact non-secret values after compatible code deploys:

| Service | Variable | Value |
|---|---|---|
| API and scheduler | DEFAULT_AI_PROVIDER | gemini |
| API and scheduler | ENRICHMENT_PROVIDER | gemini |
| API and scheduler | GEMINI_MODEL | gemini-3.8-flash |
| Presence | PRESENCE_INFERENCE | gemini |
| Presence | PRESENCE_FALLBACK_INFERENCE | empty, fail closed |
| Presence | GEMINI_MODEL | gemini-3.8-flash |

Use the existing GEMINI_API_KEY variables. A listed key name proves neither a
value nor a valid credential. Activation and a synthetic inference test are
separate from code preparation; no paid call or private record transfer occurred.
Authenticated self-hosted n8n workflows and Data Tables were not inspected.

## Validation and rollback

Offline targeted provider, Presence and billing tests: 93 passed.
Before repairs: seven request/shape cases failed, then nine content/usage cases
failed, then the isolated Pinecone bootstrap test failed. Each failure has a
regression; fixture keys are synthetic and no live provider was called.
First full run: 9735 passed and one failure in the unchanged MPT process-test
helper. An independent verifier reproduced an uncaught ProcessLookupError on
both base and candidate when a procfs read races a process exit. The narrow
helper repair handles that exited-process result and retains permission errors.
Its deterministic regression failed before the repair while the permission
control passed. Repaired executable commit 18a658ae4ee79114e6ec661213153b9977676769:
9738 full tests passed, 3 skipped and 56 subtests passed; 5836 standalone tests
passed, 1 skipped; 25 engine tests passed. Full lint, migration upgrade/downgrade/
upgrade to head 030_arf_shadow_rate_limit, and app imports passed. Both production
Dockerfiles built; Presence imported, refused production without SECRET_KEY and
answered local health configured for Gemini with a synthetic key. The API image
passed canonical imports, policy/dispatcher presence and Gemini selection without
inference. Both strict Python audits and the locked pnpm audit found no known
vulnerabilities. Runtime payloads are unchanged from image-tested commit 1ae8dc4.
The fresh critic verified provider and process-error negative controls, retained
permission/I/O errors, and found no remaining blocker. No live provider call ran.
Rollback code to main 9752eb0; current provider-variable values remain unchanged.
Before any future activation, preserve the old non-secret values for a precise
configuration rollback and verify the new deployment IDs and health afterward.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_gemini-provider-compatibility_v1_2026-11-04-2051.md
DATE: 2026-11-04
DECISIONS: Continue compatible provider preparation without spending or changing credentials.
FINDINGS: Staged Gemini selection is incompatible with current main; code candidate prepared.
OPEN: CI, code rollout, exact provider activation and external network diagnosis.
STATUS: candidate only; no provider configuration applied and no live inference performed
