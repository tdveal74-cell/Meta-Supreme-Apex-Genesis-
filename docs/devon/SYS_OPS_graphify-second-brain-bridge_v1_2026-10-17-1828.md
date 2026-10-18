---
title: DEVON Graphify Second Brain Read-Only Bridge
type: SYS_OPS
version: 1
date: 2026-10-17
area: Systems
status: draft-not-deployed
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
---

# DEVON Graphify Second Brain Read-Only Bridge

## Scope and evidence

Graphify is already declared in `.mcp.json`, and the hosted repository index was
queried successfully by an external ChatGPT Graphify connection at commit
`747df79`. This **does not authenticate DEVON's runtime**.

The Second Brain in `services/devon` must stay network/effect-free. The runtime
tool registry in `app/services/agent_tasks.py` is the application seam. This
branch adds `graphify.query_graph(question)` as an explicit READ capability to
that registry; it does not introduce Graphify as a writable soul, a new Tee
ruling, or an automatic memory-ingest source.

Graphify's external evidence enters a tool observation as a JSON object
labelled `untrusted_external_code_evidence`. It is scoped to
`tdveal74-cell/Meta-Supreme-Apex-Genesis-` in the code. Only the remote MCP
method `query_graph` is reachable. The remote `remember`, workspace selection
and explicit write tools are deliberately unavailable. The query itself requires
remote no-capture assurances, as explained in the review correction below. This scope is not a blanket
claim that arbitrary retrieved source instructions cannot confuse a model.

## Authentication and deployment

Graphify hosted MCP uses Streamable HTTP and a browser OAuth flow. **Do not**
reuse or extract ChatGPT's Graphify credentials. The DEVON host needs its own
service-managed authorization, including token refresh/rotation. Whether the
hosted service accepts a noninteractive, read-scoped credential for MCP must be
confirmed with Graphify; the site advertises read-scoped keys for its HTTP API,
which is not proof they work with MCP.

The bridge has these explicit configuration keys:

- `DEVON_GRAPHIFY_ENABLED=true` to opt into remote reads.
- `DEVON_GRAPHIFY_ACCESS_TOKEN` containing the service-owned OAuth bearer
  access token, supplied via the host's secret manager, never committed.
  A renewable credentials process is required before production enablement.

Without both values, the tool reports "not connected", rather than inventing
results. Expired credentials and transport failures also refuse. Do not put
tokens in the goal, tool arguments, tasks, logs, status documents, or PR.

## Verification gates (not yet completed)

1. CI: `pytest -q test_devon_graphify_bridge.py test_devon_hermes_surface.py
   test_devon_tool_arguments.py test_devon_agent_runtime.py`.
2. Independent security review: verify fixed repository scope, source-only
   trust label, no Graphify write paths, no credential or untrusted body leakage,
   and protocol handshake/SSE correctness.
3. DEVON service-owned OAuth: authorize through a trusted client on the actual
   host and verify refresh behavior. Avoid manually copying bearer tokens
   between apps.
4. Live DEVON readback: request `graphify.query_graph` for the approval queue;
   confirm source path, indexed commit, non-authority label, and no effects.
5. Negative: remove credentials and confirm fail-closed, simulate expired OAuth
   and confirm no cached-success claim. Verify ledger and Tee Soul unchanged.
6. Production status: only after successful authenticated live readback and
   review, amend this document from `draft-not-deployed` with a dated receipt.

No tests are claimed to have run on the real DEVON deployment, and no
production service or memory store has been modified in this draft.

## Review correction on 2026-10-18

Renamed with 1828 from the original PR creation timestamp (2026-10-17T18:28:11Z).
The original exact document writing minute was not recorded; 1828 is the earliest
verified publication time, not a claim about when the author typed it.

The remote query is conditional: Graphify documents that trail capture can
persist query intent. The corrected client discovers tools in the same session
and refuses unless query_graph explicitly advertises readOnlyHint=true. This
advisory declaration alone is not a security boundary. Before any live read,
verify capture is disabled and the service grant cannot write memory.

## DEVON RECEIPT
AREA: Systems
TYPE: draft-implementation
ARTIFACT: PR #372 Graphify runtime bridge
DATE: 2026-10-17
DECISIONS: No merge, deployment, enablement or credential reuse authorized by this record.
FINDINGS: Original implementation requires protocol and side-effect validation.
OPEN: Service-owned OAuth renewal, capture-disabled assurance, independent review and DEVON readback.
STATUS: draft-not-deployed
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
