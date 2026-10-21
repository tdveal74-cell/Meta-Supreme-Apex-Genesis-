# ARF shadow request-budget implementation

Supersedes the missing request-protection item for the local candidate only.
Production activation and authenticated production readback remain separate.

Tee approved the scoped shared PostgreSQL limiter: 30/minute refill and five
immediate requests, charged by authenticated account before evidence reads.
A conditional database upsert prevents workers from claiming the same
allowance. Accounting commits independently of later request failures.

The predecessor reproduced the failure: the sixth immediate request returned
404 instead of the expected 429. The candidate passes 124 focused tests and
six existing parameterized subtests, including actual PostgreSQL admission,
account isolation, two fresh Python processes and database-failure refusal.
These measurements use isolated fixture accounts, not production user tasks.

Full local validation, migration parity and independent review remain required
before this candidate is released. No production flag was changed.

## DEVON RECEIPT

```text
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_arf-shadow-request-budget_v1_2026-10-20-1324.md
DATE: 2026-10-20
DECISIONS: Add only shared ARF request accounting; preserve 30/minute refill and burst five; keep activation disabled pending authenticated production acceptance.
FINDINGS: Sixth-request regression reproduced on predecessor and passed after guard insertion; focused PostgreSQL and existing reliability tests passed, including fresh-worker persistence and generic refusal on missing table or lock timeout.
OPEN: Full candidate tests, migration parity, independent review and release verification; authenticated production readback before activation.
STATUS: Local review candidate, not deployed or activated.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
