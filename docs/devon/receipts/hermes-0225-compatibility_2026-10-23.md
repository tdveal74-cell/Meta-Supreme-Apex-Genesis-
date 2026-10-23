DEVON RECEIPT
platform: ChatGPT
date: 2026-10-23
area: Systems
files_opened: AGENTS.md; CLAUDE.md; services/browser/http_fetcher.py; services/browser/agent_adapter.py; services/agent_runtime/runtime.py; services/agent_runtime/tools.py; test_devon_browser_fetch_boundary.py; test_devon_hermes_expansion.py; deploy/browser-worker/worker.test.mjs; .github/workflows/ci.yml; .github/workflows/browser-worker-ci.yml
summary: Adapted Hermes v0.22.5 read-throttling evidence to DEVON's custom runtime. Added regression coverage for missing delegation writers and failed browser launches. No upstream installation, browser activation or external effects.
decisions: Tee requested the update. Preserve effect-free core, tenant ownership, approvals, durable intents and canon; no automatic retries.
open_threads: Publish and deployment receipts belong in the PR. This is a prepared thread-log receipt; authenticated external capture was not performed.
artifacts: docs/devon/SYS_OPS_hermes-0225-compatibility_v1_2026-10-23-0806.md
unverified: Production update until exact merge deployment read-back; authenticated external thread-log capture; private browser activation and topology are outside this patch.
