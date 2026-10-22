# Dedicated DEVON browser candidate

Date: 2026-10-22. This records a disabled source candidate and isolated test evidence.
It does not establish a deployed browser or full computer. It supersedes the
informal offline-worker progress descriptions from this build; no previous
production browser installation is replaced.

## Result and boundaries

The actual agent-task tool builder can register four private-browser tools:
`browser.session.open`, `navigate`, `snapshot` and `close`. Registration is
absent by default and requires explicit `DEVON_PRIVATE_BROWSER_ENABLED=1`,
owner UUID, service key, allowed hosts and network policy. No production setting
was changed. Browser actions are WRITE operations with individual human rulings.
The adapter verifies the authoritative final approval marker, owner and exact
task/step/tool/arguments before single-use consumption. Approved nested values
are copied before the first asynchronous transport boundary. A mismatched owner,
argument substitution or reused approval sends no worker request.

The only API transport is a private local Unix socket. It does not expose a
worker URL, public port, arbitrary CDP command, generic shell or credentials.
The response is bound to owner, request, session, action and isolation policy.
Ambiguous transport never retries automatically and spends its approval. The
existing leased effect-intent framework remains necessary around runtime use.
Page text is bounded and explicitly untrusted observation data.

The optional public-proxy candidate allows exact configured DNS hosts on HTTPS443.
Its proxy resolves through a bounded subprocess, rejects private/mixed, mapped
and transition addresses, then connects a checked numeric address. CDP checks
every resource request and redirects against the same host allowlist. Scripts
are disabled; service-worker bypass, nonproxied WebRTC restriction and QUIC
restriction remain enabled. The actual egress boundary is the separate browser
network namespace: OUTPUT allows only TCP3128 to the dedicated RFC1918 proxy
address; other IPv4 and all IPv6 OUTPUT are dropped. No host-wide firewall rule
was edited. The proxy has16 concurrent slots, bounded headers, bounded tunnel
bytes, a30-second soft deadline and bounded socket timeouts. A blocked send can
finish after the nominal deadline; this is not an exact30-second hard cutoff.

The default executable remains deny-all. The optional proxy launcher refuses
without a recent root-owned, nonwritable, read-only-mounted isolation receipt
matching its network namespace, proxy, hosts and verified OUTPUT policy. The
included network initializer is a disposable acceptance fixture, not a production
launcher. No external worker endpoint or Railway-to-VPS route was installed.

## Independent and executed evidence

Final source is frozen under `/opt/devon/browser-egress-20261022`. Its23-file
SHA-256 manifest is `/opt/devon/browser-egress-20261022-browser-source-manifest.json`.
It is based on tree `5fbc4f510e074a9681adfe021f6a143d0d5e1b31`, the source published
in telemetry PR399, subsequently merged. A byte comparison found all1368 baseline
tracked paths present; the only changed existing file is the intended registry
registration in `app/services/agent_tasks.py`. The final PR398 approval-marker
implementation and its tests are retained exactly.

Independent verifier results on the frozen files:

- 25 adapter tests pass, including owner isolation, authoritative approval binding,
 single-use consumption, receipt substitution, lost response, nested argument
 mutation, default-off registry and explicit owner configuration.
- 8 proxy tests pass, including mixed/private DNS, strict private bind, seventeenth
 concurrent request refusal and absolute header-deadline refusal before DNS.
- 13 adversarial private-proxy configuration cases pass.
- 10 launcher receipt cases pass; wrong policy, namespace, hosts, proxy, time,
 ownership/writability or absent receipt refuses before worker creation.
- Negative controls removing owner, approval, receipt, SSRF or isolation gates fail.

The same proxy tests passed in the actual pinned Python3.12 image, including
explicit mapped/6to4/Teredo refusal. The independent review confirmed numeric
address normalization after the subprocess JSON boundary preserves IP pinning.
Ruff passes after formatting; focused tests were rerun after formatting.

The bounded `validate.sh` builds the pinned worker image and executed all13
real nonroot sandboxed Chromium worker tests, zero failures and zero skips.
The renderer had a different user-namespace mapping and two seccomp filters,
compared with one container filter. The test opens a blank page, captures a
valid PNG, exercises real Unix-socket authentication/duplicate suppression,
refuses navigation in offline mode and closes. Close completion waits for the
process group to exit. A separate process-count proof measured10 Chromium
processes before close and zero after. Restoring the earlier missing-await
implementation makes both close regressions fail.

The real public acceptance fixture used the actual Python approval adapter,
Unix socket, sandboxed Chromium, namespace OUTPUT restrictions and restricted
proxy to load `https://example.org/`, return bounded page text containing
`documentation examples`, and return a PNG artifact receipt. It then closed
successfully. Three nonallowed navigation targets were refused. Three direct
IP bypass targets covering metadata, gateway and public IP were unreachable.
This used fixture-only identities, keys and approvals, with temporary networks,
containers and volumes removed. The public acceptance ran before Ruff-only
formatting; final focused tests and independent source review followed.

A persistent-volume crash fixture retained SQLite claims, receipts and PNGs.
After SIGKILL, restart failed closed on the stale socket. An operator fixture
verified exact socket type, UID10001 and ECONNREFUSED before removing only that
owned stale socket. Restart returned a byte-identical historical receipt,
refused reuse of the old session/profile and opened/closed a new Chromium process.
No Tee Browser Desk profile, production cookies or credentials were mounted.

Exact logs remain under the candidate root (`browser-tests.log`,
`browser-validation.log`, `browser-integration.log`, `browser-node-tests.log`,
`proxy-python-image-tests.log`). Independent negative controls and receipt checks
are under `/tmp/devon-browser-security-critic-20261022`; persistent crash and close
proofs are preserved under `/opt/devon/browser-offline-evidence-20261022`.
These are internal evidence locations, not published artifacts.

The path-filtered `browser-worker-ci.yml` runs the same image build and all13
real sandbox tests plus proxy tests on Ubuntu24.04. Any skipped worker test,
missing Chromium or unsupported sandbox is red. Hosted execution must still
pass before merge; no sandbox relaxation is authorized to make it green.
The broader backend suite on this frozen candidate is being run by the parent
session and is not asserted complete by this record.

## Still open

This is not a complete computer workspace. Click, type, authenticated sign-in,
file upload/download, shell commands, desktop applications, artifact viewing
and arbitrary existing-session resume are not implemented. Production API
currently lacks the private topology/mount needed to reach the VPS Unix socket.
A production network initializer, host acceptance, deployment and explicit
activation remain unverified.

Dedicated profiles, SQLite and artifacts persist independently of Tee's profile,
but old session UUIDs never reopen historical profiles after restart. Historical
completed receipts are history, not restored live processes. The current
conservative lifetime quota is two distinct sessions including closed ones,
10000 request records and20 PNGs per session. A retention/quota and manual
reconciliation design is required before sustained use; general continuity is
not claimed. A stale socket or unproven close remains quarantined.

## Manifest hygiene and rollback

All23 manifest entries were inspected for generated logs, images, SQLite data,
environment files, fixture secrets and token-shaped credentials. None were found.
Configuration uses environment lookups only. Tests use generated or conspicuously
fixture-only credentials. Runtime logs, data and original offline proof scripts
are outside the publishable file list. No live secret is committed.

Rollback keeps or restores `DEVON_PRIVATE_BROWSER_ENABLED=0`, stops only the
separately installed dedicated worker if one is later authorized, and preserves
its data pending reconciliation. Reverting this source removes registry support.
Do not delete profiles, unlink sockets automatically, or touch Browser Desk.

## DEVON RECEIPT

TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_private-browser-candidate_v1_2026-10-22-0955.md
DATE: 2026-10-22
DECISIONS: Keep private browser default off; preserve exact approvals, owner isolation, dedicated state and fail-closed egress.
FINDINGS: Independent source review and isolated real-browser acceptance pass within the stated candidate scope; no production computer is established.
OPEN: Full backend and hosted CI, private production topology and initializer, deployment and activation, click/type/files/shell, artifact viewing, retention and sustained-session design.
STATUS: independently reviewed disabled source candidate; isolated browser acceptance verified; production unverified