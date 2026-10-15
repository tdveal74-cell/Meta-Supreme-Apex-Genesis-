# The gate learns gh and wget, and the ledger becomes a receipt

Follow up to `SYS_OPS_outward-gate-ledger-and-paste-loop_v1_2026-10-14-2352.md`.
On 2026-10-14 Tee ruled on three cards: build the ledger into DEVON, add gh
writes and wget to the gate with merges staying ledger only, and file the thread
log. The thread log is filed in Notion (Conversations, Thread Log). The other two
are built here.

## What changed

- `.claude/hooks/gate_ledger.py` now gates `gh workflow run`, `gh api` writes
  and GraphQL mutations, `gh release`, `gh repo`, `gh secret`, `gh variable`
  and `gh run rerun`, and a wget that posts to a non-local host. `gh pr merge`
  is ledger only, like the merge tool. The daily `gh pr` and `gh issue` flow is
  not gated. A GraphQL call whose query cannot be read inline is treated as a
  write.
- `scripts/ledger_receipt.py` renders the ledger as a DEVON RECEIPT in the
  standing format and validates it with `services/devon/receipts.py`. It prints
  and writes nothing.
- `test_gate_ledger.py` is at 318 tests together with `test_ledger_receipt.py`,
  both in the standalone job.

## What "built into DEVON" means, and what it does not

The ledger reaches DEVON the way every other thread does, as a receipt filed
once. Nothing files it automatically. The capture door `devon-capture` needs an
`x-devon-key` header, and that key is not in this repository and not set in the
cloud environment (an env scan for DEVON secrets returned zero). The n8n host
answered a health check with HTTP 200 from the container, so the network is not
the blocker; the key is. Setting it as an environment secret is Tee's, and a curl
to that webhook is itself a gated call.

## How it was checked

Two more fresh critics, base ac322339, each in its own worktree. They found a
receipt that counted merges and local deletes as gated outward calls, ledger text
that could inject lines into a receipt, GraphQL mutations read from a file or a
variable that the gate could not see, a read query gated because a repo was named
`mutation-tests`, and wget targets without a scheme. Each is fixed and pinned
by a named test. Full suite 4409 passed, standalone list and lint clean.

## Left alone on purpose

`gh pr merge --admin` is ledger only, so it skips the "every check passed"
condition of the standing grant and nothing here can see that. A gh alias, an
extension and `gh gist`, `gh label create` and `gh codespace` writes are not
gated. Both were weighed and left as documented.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_gate-gh-wget-and-ledger-receipt_v1_2026-10-15-0111.md
DATE: 2026-10-15
DECISIONS: Tee ruled yes on building the ledger into DEVON, yes on gating gh writes and wget only with merges staying ledger only, and yes on filing the thread log now.
FINDINGS: The ledger cannot reach devon-capture on its own because the x-devon-key header is not in the repository or the environment. A first receipt counted ledger only calls as gated and outward; two critics caught it.
OPEN: Tee sets the capture key as an environment secret if he wants automatic posting. The hook's live behaviour, the wrapper exit 1 and the subagent path are still unmeasured. Five secret groups still need rotating.
STATUS: Built, full suite 4409 passed, two critic rounds applied, awaiting merge.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
