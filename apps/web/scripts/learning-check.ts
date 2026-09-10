/**
 * Proof for the learning panel's verdict ladder. No test framework:
 * node:assert and a plain process exit code, the same shape as
 * scripts/control-check.ts. Run from apps/web:
 *
 *   node --experimental-strip-types scripts/learning-check.ts
 *
 * WHY THIS FILE EXISTS
 *
 * The learning panel is the first surface over DEVON's learning store, and the
 * one claim it exists to make is whether that store is empty. It has exactly
 * one way to be wrong: rendering a FAILED read as an EMPTY store. That is the
 * same inversion a critic used against the control plane on 2026-09-09, when
 * `pnpm typecheck` and `pnpm build` both exited 0 over a reversed safeguard, so
 * neither of those is a guard on this.
 *
 * readLearningVerdict is a pure function with no DOM and no network, so there is
 * no reason for it to be unguarded.
 */

import assert from "node:assert/strict";
import {
  readLearningVerdict,
  type LearningRead,
  type LearningVerdict,
} from "../components/mind/learning-honesty.ts";

let checks = 0;
function check(name: string, run: () => void): void {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

const OK_EMPTY: LearningRead = { state: "ok", count: 0 };
const OK_FULL: LearningRead = { state: "ok", count: 4 };
const FAILED: LearningRead = { state: "failed", detail: "the memories route answered 500" };
const LOCKED: LearningRead = { state: "locked" };

/* ------------------------------------------------------------------ */
/* The load bearing law                                                 */
/* ------------------------------------------------------------------ */

function refuseEmptyAndGood(verdict: LearningVerdict, why: string): void {
  assert.equal(verdict.code, "unreadable", why);
  assert.notEqual(verdict.code, "empty", "a failed read must never read as an empty store");
  assert.notEqual(verdict.tone, "good", "a failed read must never take a good tone");
  assert.match(verdict.sentence, /failed read, not an empty store/);
}

check("a failed memories read is never reported as an empty store", () => {
  refuseEmptyAndGood(
    readLearningVerdict(FAILED, OK_EMPTY),
    "memories failed, so no claim about emptiness is available",
  );
});

check("a failed skills read is never reported as an empty store", () => {
  // The asymmetric case: memories read fine and returned nothing, which on its
  // own would be the empty verdict. One broken half is enough to withhold it.
  refuseEmptyAndGood(
    readLearningVerdict(OK_EMPTY, FAILED),
    "skills failed, so the pair supports no emptiness claim",
  );
});

check("a failed read outranks rows that did come back", () => {
  // The flattering half must not win: 4 memories arrived, but the skills read
  // failed, so the store was not fully read and cannot read as present.
  const verdict = readLearningVerdict(OK_FULL, FAILED);
  assert.equal(verdict.code, "unreadable");
  assert.notEqual(verdict.tone, "good");
});

check("the failing detail reaches the operator", () => {
  const verdict = readLearningVerdict(FAILED, OK_EMPTY);
  assert.match(verdict.sentence, /answered 500/, "the operator needs the actual failure");
});

/* ------------------------------------------------------------------ */
/* Locked outranks unreadable                                           */
/* ------------------------------------------------------------------ */

check("no session token is locked, not a failed read", () => {
  // No request was sent, so calling this a failure would invent one.
  const verdict = readLearningVerdict(LOCKED, LOCKED);
  assert.equal(verdict.code, "locked");
  assert.notEqual(verdict.code, "unreadable");
  assert.notEqual(verdict.code, "empty");
});

check("locked wins even when the other half failed", () => {
  assert.equal(readLearningVerdict(LOCKED, FAILED).code, "locked");
  assert.equal(readLearningVerdict(FAILED, LOCKED).code, "locked");
});

/* ------------------------------------------------------------------ */
/* The honest ends of the ladder                                        */
/* ------------------------------------------------------------------ */

check("two successful reads with no rows are an empty store, and say so", () => {
  const verdict = readLearningVerdict(OK_EMPTY, OK_EMPTY);
  assert.equal(verdict.code, "empty");
  assert.notEqual(verdict.tone, "good", "an empty store is a finding, not a pass");
  assert.match(verdict.sentence, /returned no rows/);
  assert.match(verdict.sentence, /no memories and no skills/);
});

check("skills alone are enough to be populated", () => {
  const verdict = readLearningVerdict(OK_EMPTY, OK_FULL);
  assert.equal(verdict.code, "populated");
  assert.equal(verdict.tone, "good");
});

check("a populated store still refuses to promise recall", () => {
  // Search is token overlap only, so stored is not the same as recalled. The
  // panel must not imply otherwise.
  const verdict = readLearningVerdict(OK_FULL, OK_FULL);
  assert.equal(verdict.code, "populated");
  assert.match(verdict.sentence, /not a guarantee of recall/);
});

check("counts are pluralised without inventing any", () => {
  const one = readLearningVerdict({ state: "ok", count: 1 }, { state: "ok", count: 1 });
  assert.match(one.sentence, /1 memory and 1 skill stored/);
  const many = readLearningVerdict({ state: "ok", count: 2 }, { state: "ok", count: 3 });
  assert.match(many.sentence, /2 memories and 3 skills stored/);
});

check("every verdict code is reachable", () => {
  const codes = new Set([
    readLearningVerdict(LOCKED, LOCKED).code,
    readLearningVerdict(FAILED, OK_EMPTY).code,
    readLearningVerdict(OK_EMPTY, OK_EMPTY).code,
    readLearningVerdict(OK_FULL, OK_FULL).code,
  ]);
  assert.equal(codes.size, 4, "a code nothing can reach is a branch nobody guards");
});

console.log(`\n${checks} learning honesty checks passed`);
