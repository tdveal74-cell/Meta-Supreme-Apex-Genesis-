# Dedicated DEVON browser candidate

Status: disabled source candidate. No production browser or computer is enabled.
The API's real agent-tool builder registers this capability only when
`DEVON_PRIVATE_BROWSER_ENABLED=1` plus explicit owner, service key, hosts and
network policy are configured. Defaults register no private-browser tool.
No service key or owner is supplied by the repository.

Supported actions are `browser.session.open`, `navigate`, `snapshot` and
`close`. Snapshot returns an artifact receipt and bounded untrusted page text
in proxy mode. Every action is WRITE and spends its own exact runtime approval;
owner, task, step, arguments and receipt identities remain bound. There is no
implicit retry after an ambiguous result. This does not implement click, type,
file upload/download, shell access, desktop applications or a full computer.

The default worker executable is deny-all and requires a network-none
container. The optional proxy launcher additionally requires a root-owned,
nonwritable isolation receipt mounted read-only at
`/run/devon-network/isolation.json`. It must match the current Linux network
namespace, exact proxy/hosts and a recent verified OUTPUT policy. An operator
must install and verify namespace rules permitting only TCP3128 to the
RFC1918 proxy IP and dropping all other IPv4 plus all IPv6 OUTPUT before issuing
that receipt. The namespace rules are not host-global firewall changes.
`integration-proof.py` demonstrates this sequence only in disposable fixtures;
there is no production network initializer or automatic rollout in this patch.
Never start proxy mode with an ordinary unrestricted bridge or host network.

The dedicated proxy accepts only exact configured DNS hosts on HTTPS443.
Every connection resolves in a bounded subprocess, rejects mixed/private,
mapped/transition addresses and pins a checked numeric IP. Redirects and
subresources meet the same CDP URL allowlist and fresh CONNECT checks.
Scripts are disabled, service-worker bypass is enabled and nonproxied WebRTC
and QUIC are disabled. The namespace firewall provides the actual egress
boundary. The proxy has16 concurrent slots, an8KiB header bound,32MiB tunnel
bound and a30-second request deadline. No arbitrary HTTP forwarding exists.

Profiles, SQLite claims and PNG artifacts live on dedicated persistent data
storage. They never mount or reuse Tee's Browser Desk profile. A request claim
commits before action; an interrupted claim stays unknown and is never replayed.
A completed historical receipt can be retrieved after restart, but that does
not restore the old Chromium process. Old session UUIDs never reopen profiles.
The current conservative quota counts two distinct sessions over the storage
lifetime, including closed sessions, plus10000 requests and20 PNGs per session.
This is a rollout limit requiring an explicit retention/reconciliation design
before sustained use. It is not general session continuity.

Close returns completed only after Chromium's process group exits. An unproven
close stays unknown and quarantined. After SIGKILL, a stale Unix socket blocks
restart. With the worker stopped, an operator must verify exact socket type,
UID10001 and absence of a live peer before removing only that owned stale socket.
Never automatically unlink files, symlinks or live sockets.

`validate.sh` builds the pinned image and runs all18 real nonroot Chromium
sandbox tests with zero skips, plus proxy policy tests in pinned Python3.12.
The path-filtered CI job runs that same command and fails if the hosted sandbox
is unsupported. A green contract suite alone proves no production activation.
The broader backend suite covers the owner/approval adapter and real registry.

A local acceptance fixture proved approved adapter -> Unix socket -> sandboxed
Chromium -> restricted proxy -> public HTTPS page, text and PNG receipt, clean
close and direct-IP refusals for metadata, gateway and public bypass targets.
It used fixture-only approvals, keys and temporary networks/volumes, all removed.
The API production host currently has no private route/mount to this VPS socket.
A reviewed private transport topology, production initializer, host acceptance,
receipt/artifact viewer, retention and explicit activation remain open.


## Review corrections

Each browser action starts a fresh30-second monotonic budget shared by all its
CDP commands and event waits. It does not reset per command or persist across
idle sessions. Expiry prevents a completed receipt and triggers separately
bounded2-second process cleanup before the worker becomes available. Unproven
cleanup remains quarantined. The adapter allows35seconds for the receipt and
bounds its whole streaming operation at40seconds, with no retries. Existing
runtime lease renewal and fenced commits remain unchanged.

CDP output uses a streaming UTF-8 decoder, preserving multilingual page text
when characters cross pipe chunks. The regression emits every response byte
through the actual production parser callback in real sandboxed Chromium.
