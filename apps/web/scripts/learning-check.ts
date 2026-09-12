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
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import {
  readLearningVerdict,
  type LearningRead,
  type LearningVerdict,
} from "../components/mind/learning-honesty.ts";

const HERE = dirname(fileURLToPath(import.meta.url));

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

check("every pair of read states resolves, and the double outage never reads empty", () => {
  // THE COMBINATION AN ADVERSARY FOUND MISSING, AND WHY IT IS THE IMPORTANT ONE.
  //
  // This file fed (FAILED, OK_EMPTY), (OK_EMPTY, FAILED) and (OK_FULL, FAILED),
  // and never (FAILED, FAILED). LearningPanel reads both routes through one
  // Promise.allSettled with one token, so an expired token or an API outage fails
  // BOTH halves at once: the untested pair is the likeliest one in production. An
  // adversary added a branch returning code "empty" for it and all 11 checks here
  // passed while the panel rendered "LEARNING EMPTY / DEVON is planning with no
  // memories and no skills" over a store it had not read.
  //
  // The mirror gap was the same shape: (OK_EMPTY, OK_FULL) was fed and
  // (OK_FULL, OK_EMPTY) was not, so keying the empty branch on the wrong half
  // rendered four stored memories as an empty store.
  //
  // So every one of the sixteen pairs is walked, and the invariant is stated over
  // all of them rather than sampled: if EITHER half failed, the verdict may never
  // say the store is empty or populated, because neither is a fact you hold.
  const states: Array<[string, LearningRead]> = [
    ["locked", LOCKED],
    ["failed", FAILED],
    ["ok-empty", OK_EMPTY],
    ["ok-full", OK_FULL],
  ];
  let pairs = 0;
  for (const [memoryName, memories] of states) {
    for (const [skillName, skills] of states) {
      pairs += 1;
      const verdict = readLearningVerdict(memories, skills);
      const where = `(${memoryName}, ${skillName})`;
      assert.ok(verdict.code, `${where} produced no verdict code`);

      const anyFailed = memoryName === "failed" || skillName === "failed";
      if (anyFailed) {
        assert.notEqual(
          verdict.code,
          "empty",
          `${where} reads as an EMPTY store while a read failed. An unread store is not an empty one, and this is the only way this panel can lie`,
        );
        assert.notEqual(
          verdict.code,
          "populated",
          `${where} reads as a POPULATED store while a read failed, which claims rows nobody counted`,
        );
        assert.notEqual(
          verdict.tone,
          "good",
          `${where} reads in the good tone while a read failed`,
        );
      }

      const bothOkEmpty = memoryName === "ok-empty" && skillName === "ok-empty";
      if (verdict.code === "empty") {
        assert.ok(
          bothOkEmpty,
          `${where} reads as an empty store, but only a pair of successful empty reads supports that claim`,
        );
      }
    }
  }
  assert.equal(pairs, 16, `expected all sixteen pairs walked, walked ${pairs}`);
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

/* the panel's own adapter, not just the pure function */

/*
 * WHY THESE LAST CHECKS EXIST, AND WHY THEIR ABSENCE WAS THE HOLE.
 *
 * Everything above exercises readLearningVerdict in isolation, which is right and
 * was not enough. A critic found the gap on 2026-09-10: `asRead` in
 * LearningPanel.tsx is the adapter that turns a fetch result into the ladder's
 * input, and nothing bound the two. One line changed inside it:
 *
 *   if (rows.state === "failed") return { state: "ok", count: 0 };
 *
 * and the panel rendered "LEARNING EMPTY / Both routes answered and returned no
 * rows. DEVON is planning with no memories and no skills" over a store it had
 * failed to read. With `count: 7` it rendered "LEARNING PRESENT" in the good tone.
 * All 11 checks here passed, check:control passed, tsc and next build exited 0.
 *
 * The ladder was never wrong. The wire into it was unguarded, and a ladder nobody
 * is standing on holds no weight. control-check already binds its six graph
 * refusals to the panel that renders them; this file had no equivalent.
 *
 * Read from source rather than executed, because asRead is module private and
 * this runner imports no React.
 */
const PANEL = readFileSync(
  join(HERE, "..", "components/mind/LearningPanel.tsx"),
  "utf8",
);

check("the panel's asRead maps a failed read to failed, never to a count", () => {
  const file = ts.createSourceFile(
    "LearningPanel.tsx",
    PANEL,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );

  const decls: ts.FunctionDeclaration[] = [];
  const walk = (n: ts.Node) => {
    if (ts.isFunctionDeclaration(n) && n.name && n.name.text === "asRead") {
      decls.push(n);
    }
    ts.forEachChild(n, walk);
  };
  walk(file);
  assert.equal(
    decls.length,
    1,
    `LearningPanel must declare asRead exactly once; found ${decls.length}. Without it this check cannot find the wire into the ladder`,
  );

  // Every `return` in the adapter, paired with the branch test above it.
  const returns: ts.ReturnStatement[] = [];
  const collectReturns = (n: ts.Node) => {
    if (ts.isReturnStatement(n)) returns.push(n);
    ts.forEachChild(n, collectReturns);
  };
  collectReturns(decls[0]);
  const text = decls[0].getText();

  // The load bearing one. A failed read must produce state "failed", and must
  // never produce a count, because a count is a claim about the store.
  const failedBranch = returns.find((r) => {
    let at: ts.Node | undefined = r.parent;
    while (at && at !== decls[0]) {
      if (ts.isIfStatement(at) && at.expression.getText().includes('"failed"')) return true;
      at = at.parent;
    }
    return false;
  });
  assert.ok(
    failedBranch,
    'asRead has no branch keyed on a "failed" read, so a failed read falls through to whatever the last return says',
  );
  const failedText = failedBranch!.getText();
  assert.match(
    failedText,
    /state:\s*"failed"/,
    `asRead's failed branch returns ${failedText}, which does not carry state "failed". A failed read presented as a count is the one way this panel can lie`,
  );
  assert.ok(
    !/count:/.test(failedText),
    `asRead's failed branch carries a count (${failedText}). A count is a claim about the store, and a read that failed supports no such claim`,
  );

  // And the ok branch must carry the real row count rather than a constant.
  assert.match(
    text,
    /state:\s*"ok",\s*count:\s*rows\.rows\.length/,
    "asRead's ok branch does not report the actual row count, so the number on the panel is not the number the route returned",
  );

  // The adapter must actually feed the ladder.
  assert.match(
    PANEL,
    /readLearningVerdict\(\s*asRead\(/,
    "LearningPanel no longer feeds asRead into readLearningVerdict, so the ladder this file guards is not the one the panel renders",
  );
});

check("the learning panel is mounted where a person can reach it", () => {
  // /control/learning is its own route, and it is also folded into Tier 2. Both
  // are reachable surfaces and neither is asserted anywhere else.
  const page = readFileSync(join(HERE, "..", "app/control/page.tsx"), "utf8");
  assert.match(
    page,
    /learning=\{<LearningPanel \/>\}/,
    "the control plane no longer mounts LearningPanel, so Tier 2 reads 'not mounted on this build' and the panel is only reachable by typing a URL",
  );
  const route = readFileSync(
    join(HERE, "..", "app/control/learning/page.tsx"),
    "utf8",
  );
  assert.match(
    route,
    /LearningPanel/,
    "/control/learning no longer renders LearningPanel",
  );
});

console.log(`\n${checks} learning honesty checks passed`);
