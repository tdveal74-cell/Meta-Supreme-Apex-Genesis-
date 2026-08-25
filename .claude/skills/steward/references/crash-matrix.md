# Crash-matrix methodology: proving concurrency invariants

How the lease, fencing, and durable-intent invariants were proven in
`test_devon_lease_loss_crash_matrix.py`, generalized so the next invariant
gets the same treatment. A claim about behavior under crashes or races is
unproven until it survives this checklist.

## 1. State the invariant as a falsifiable sentence

Not "leases work" but "only the live lease owner can commit receipts" or "a
worker crash after an external effect leaves a durable intent that forces
refusal". If the sentence names no observable row, file, or status code, it
cannot be tested.

## 2. Race it with real concurrency

Use `asyncio.gather` with one `AsyncSessionLocal()` session per simulated
worker. Do not share a session between workers; the point is separate
transactions contending on the same rows. Keep worker count at or below the
connection pool (six worked here). Assert the exact cardinality the invariant
promises: exactly one lease claim wins, the generation moves exactly once,
the external effect (a marker file) runs exactly once, one intent row and one
receipt row exist.

Make assertions interleaving-robust: when a race can legitimately resolve two
ways (loser gets TaskExecutionBusy, or arrives after completion and no-ops),
assert the invariant that holds in BOTH orderings, not one lucky schedule.

## 3. Simulate the crash with a rollback

A worker crash is: commit the claim, perform the pre-effect writes, run the
"effect", then `rollback()` the session instead of committing, and release
the lease the way expiry would (force `lease_expires_at` into the past).
Whatever survives that rollback is what survives a real crash. In the Hermes
case this exposed that intents did NOT survive, which meant orphan refusal
could never fire outside hand-seeded tests.

## 4. Fence checks are attempted, not assumed

For every stale-writer path, actually attempt the write with the dead token
and generation and assert the typed refusal, then query that no row carries
the dead token. A fence that is never attacked in tests is decoration.

## 5. The negative control is mandatory

Before trusting the fix, demonstrate the test FAILS on the old behavior:
run the pre-fix code path (here: recorder without a session factory) and show
the protective row does not survive. A test that passes on both old and new
code proves nothing. Record the control's result in the PR body.

## 6. Hold it under repetition and load

Run the matrix module several consecutive times (five here) before calling it
stable; interleaving bugs are shy. Add one scenario that hammers the refusal
path concurrently (N workers against one orphan intent, all must refuse, no
lease left claimed) so load cannot open a retry hole.

## 7. Semantics worth copying

- Durable-marker pattern: the record that forces human inspection commits in
  its own short transaction BEFORE the irreversible action; the happy-path
  record commits atomically with the fenced result. Crash between them fails
  toward refusal, never toward silent retry.
- Refusal must be a typed exception mapped to a stable status code (409
  ambiguous_external_effect), not a bare RuntimeError leaking as a 500.
- After any refusal, assert cleanup: no lease held, task state and
  failure_reason set, so the system parks instead of wedging.
