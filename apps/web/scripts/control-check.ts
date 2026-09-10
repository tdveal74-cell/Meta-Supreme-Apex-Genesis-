/**
 * Proof for the control plane's honesty helpers. No test framework:
 * node:assert and a plain process exit code, the same shape as
 * scripts/presence-check.ts. Run from apps/web:
 *
 *   node --experimental-strip-types scripts/control-check.ts
 *
 * WHY THIS FILE EXISTS
 *
 * A fresh critic attacked the control plane on 2026-09-09 and found that the
 * one claim the arc is built to make had nothing guarding it. It inverted
 * `readVerdict` so an intact but incomplete chain returned a good tone,
 * `pnpm typecheck` exited 0, `pnpm build` exited 0, and a browser rendered a
 * green VERIFIED badge over a payload whose five events were all unhashed.
 * The whole web CI gate passed with the safeguard reversed.
 *
 * These are pure functions with no DOM and no network, so there was never a
 * reason for them to be unguarded. The verdict ladder is the load bearing one:
 * an intact chain that is not complete is receipted on trust, not on proof,
 * and must never reach a good tone however sound the receipt looks.
 */

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import {
  isProvenancePayload,
  readVerdict,
  shortHash,
  type ProvenancePayload,
} from "../components/ledger/provenance-payload.ts";
import {
  ageLabel,
  buildCatalogIndex,
  resolveTool,
  riskRank,
  summarizeTaskRisk,
} from "../components/readiness/risk-resolution.ts";
import {
  classifyProvider,
  compareNodes,
  describeGaps,
  edgeCloseness,
  layoutNodes,
  parseGraphPayload,
  radiusEncodesDegree,
  readGraphVerdict,
  sourceOrder,
} from "../components/mind/knowledge-graph.ts";
import type {
  AgentTaskView,
  ToolCatalogEntry,
} from "../components/readiness/readiness-types.ts";

let checks = 0;
function check(name: string, run: () => void): void {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

/* ------------------------------------------------------------------ */
/* The verdict ladder                                                   */
/* ------------------------------------------------------------------ */

function payload(over: {
  verified?: boolean;
  receipted?: boolean;
  chain?: Partial<ProvenancePayload["chain"]>;
  receipt?: Partial<ProvenancePayload["receipt"]>;
}): ProvenancePayload {
  return {
    intent_id: "3f6c1e2a-0000-4000-8000-000000000000",
    verified: over.verified ?? false,
    receipted: over.receipted ?? false,
    verified_at: "2026-09-09T04:00:00+00:00",
    chain: {
      intact: true,
      complete: true,
      length: 5,
      hashed: 5,
      unhashed: 0,
      head_hash: "a".repeat(64),
      findings: [],
      ...(over.chain || {}),
    },
    receipt: {
      present: false,
      verified: false,
      findings: [],
      ...(over.receipt || {}),
    },
  } as ProvenancePayload;
}

check("an intact but incomplete chain with a receipt is never good", () => {
  // This is the exact payload the critic's inverted build rendered green.
  const verdict = readVerdict(
    payload({
      chain: { complete: false, hashed: 0, unhashed: 5 },
      receipted: true,
      receipt: { present: true, verified: true },
    }),
  );
  assert.equal(verdict.code, "receipted_on_trust");
  assert.equal(verdict.label, "RECEIPTED ON TRUST");
  assert.notEqual(verdict.tone, "good", "a trust only chain must never read as good");
  assert.match(verdict.sentence, /not a verified intent/);
  assert.match(verdict.sentence, /on trust, not on proof/);
});

check("a receipt that verifies cannot lift an incomplete chain to verified", () => {
  // Belt and braces on the same law: even with the payload's own `verified`
  // set true, completeness decides. The writer never emits this, so if it ever
  // arrives the card must not take the flattering half.
  const verdict = readVerdict(
    payload({
      verified: true,
      receipted: true,
      chain: { complete: false, hashed: 4, unhashed: 1 },
      receipt: { present: true, verified: true },
    }),
  );
  assert.equal(verdict.code, "receipted_on_trust");
  assert.notEqual(verdict.tone, "good");
});

check("a broken chain outranks everything, including a sound receipt", () => {
  const verdict = readVerdict(
    payload({
      verified: true,
      receipted: true,
      chain: { intact: false, findings: ["event 3 does not link to event 2"] },
      receipt: { present: true, verified: true },
    }),
  );
  assert.equal(verdict.code, "chain_broken");
  assert.equal(verdict.tone, "bad");
});

check("an empty chain is bad, never an empty success", () => {
  const verdict = readVerdict(
    payload({ chain: { length: 0, hashed: 0, unhashed: 0, head_hash: "" } }),
  );
  assert.equal(verdict.code, "no_chain");
  assert.equal(verdict.tone, "bad");
});

check("a complete chain with no receipt is warned, not verified", () => {
  const verdict = readVerdict(payload({ receipted: false }));
  assert.equal(verdict.code, "unreceipted");
  assert.notEqual(verdict.tone, "good");
});

check("a complete chain with an unsound receipt is bad", () => {
  const verdict = readVerdict(
    payload({
      receipted: true,
      receipt: { present: true, verified: false, findings: ["signature verifies under no key"] },
    }),
  );
  assert.equal(verdict.code, "receipt_unsound");
  assert.equal(verdict.tone, "bad");
});

check("only a complete chain with a sound receipt reads verified", () => {
  const verdict = readVerdict(
    payload({
      verified: true,
      receipted: true,
      receipt: { present: true, verified: true },
    }),
  );
  assert.equal(verdict.code, "verified");
  assert.equal(verdict.tone, "good");
});

check("a payload that disagrees with itself is reported, not resolved", () => {
  const verdict = readVerdict(
    payload({
      verified: false,
      receipted: true,
      receipt: { present: true, verified: true },
    }),
  );
  assert.equal(verdict.code, "payload_disagrees");
  assert.equal(verdict.tone, "bad");
});

check("exactly one verdict code carries a good tone", () => {
  // A future branch that quietly adds a second good outcome is the same
  // failure the critic demonstrated, so the count itself is pinned.
  const cases: ProvenancePayload[] = [
    payload({ chain: { intact: false } }),
    payload({ chain: { length: 0 } }),
    payload({ chain: { complete: false }, receipted: true, receipt: { present: true } }),
    payload({ chain: { complete: false } }),
    payload({ receipted: false }),
    payload({ receipted: true, receipt: { present: true, verified: false } }),
    payload({ verified: true, receipted: true, receipt: { present: true, verified: true } }),
    payload({ verified: false, receipted: true, receipt: { present: true, verified: true } }),
  ];
  const good = cases.map(readVerdict).filter((v) => v.tone === "good");
  assert.equal(good.length, 1, "more than one path reaches a good tone");
  assert.equal(good[0].code, "verified");
});

/* ------------------------------------------------------------------ */
/* The payload guard                                                    */
/* ------------------------------------------------------------------ */

check("a well formed payload is accepted", () => {
  assert.ok(isProvenancePayload(payload({})));
});

check("a partial body is refused rather than read with holes", () => {
  const full = payload({}) as unknown as Record<string, unknown>;
  assert.ok(!isProvenancePayload(null));
  assert.ok(!isProvenancePayload(undefined));
  assert.ok(!isProvenancePayload("verified"));
  assert.ok(!isProvenancePayload(42));
  assert.ok(!isProvenancePayload([]));
  assert.ok(!isProvenancePayload({}));
  for (const key of ["intent_id", "verified", "receipted", "verified_at", "chain", "receipt"]) {
    const missing = { ...full };
    delete missing[key];
    assert.ok(!isProvenancePayload(missing), `a body missing ${key} was accepted`);
  }
});

check("a chain or receipt with a wrong field type is refused", () => {
  const base = payload({}) as unknown as Record<string, unknown>;
  const chain = base.chain as Record<string, unknown>;
  assert.ok(!isProvenancePayload({ ...base, chain: { ...chain, intact: "yes" } }));
  assert.ok(!isProvenancePayload({ ...base, chain: { ...chain, length: "5" } }));
  assert.ok(!isProvenancePayload({ ...base, chain: { ...chain, findings: "none" } }));
  assert.ok(!isProvenancePayload({ ...base, chain: null }));
  assert.ok(!isProvenancePayload({ ...base, receipt: null }));
  assert.ok(
    !isProvenancePayload({
      ...base,
      receipt: { present: true, verified: true, findings: "none" },
    }),
  );
});

check("shortHash truncates visibly and never silently", () => {
  // The ellipsis is the point: a reader must be able to tell a shortened hash
  // from a short one, so a truncated value is never mistaken for the whole.
  assert.equal(shortHash("b".repeat(64)), `${"b".repeat(12)}...`);
  assert.equal(shortHash("abc"), "abc", "a value shorter than the cut is untouched");
  assert.equal(shortHash("c".repeat(12)), "c".repeat(12), "exactly the cut is untouched");
  assert.equal(shortHash(""), "", "an absent head hash stays absent, not an ellipsis");
});

/* ------------------------------------------------------------------ */
/* Tool risk                                                            */
/* ------------------------------------------------------------------ */

function task(tools: string[]): AgentTaskView {
  return {
    task_id: "t-1",
    goal: "probe",
    context: {},
    plan: { steps: tools.map((name) => ({ tool_call: { name } })) },
    state: "planned",
    current_step: 0,
    observations: [],
    checkpoints: [],
    final_summary: "",
    failure_reason: "",
    created_at: "2026-09-09T03:00:00+00:00",
    updated_at: "2026-09-09T03:00:00+00:00",
  } as unknown as AgentTaskView;
}

check("an unknown tool resolves to unknown, never defaulted to read", () => {
  const resolved = resolveTool("no.such.tool", new Map());
  assert.equal(resolved.risk, null);
  assert.equal(resolved.source, "unknown");
  assert.equal(resolved.approvalRequired, null);
  assert.equal(riskRank(resolved.risk), 0, "an unknown tool must not outrank a read");
});

check("summarizeTaskRisk names an unknown tool instead of hiding it", () => {
  const summary = summarizeTaskRisk(task(["no.such.tool"]), new Map());
  assert.deepEqual(summary.toolNames, ["no.such.tool"]);
  assert.deepEqual(summary.unresolved, ["no.such.tool"]);
  assert.equal(summary.peak, null, "an unresolved tool must not become a peak risk");
  assert.equal(summary.approvalRequired, false);
});

check("the live catalog outranks the pinned manifest", () => {
  const catalog = buildCatalogIndex([
    {
      name: "browser.fetch",
      risk: "high_impact",
      approval_required: true,
      reversible: false,
      blast_radius: "changed since the manifest was pinned",
    } as ToolCatalogEntry,
  ]);
  const resolved = resolveTool("browser.fetch", catalog);
  assert.equal(resolved.source, "catalog");
  assert.equal(resolved.risk, "high_impact");
  assert.equal(resolved.approvalRequired, true);
});

check("peak risk is the highest across a plan, and approval carries", () => {
  const catalog = buildCatalogIndex([
    { name: "a.read", risk: "read", approval_required: false } as ToolCatalogEntry,
    { name: "b.write", risk: "write", approval_required: true } as ToolCatalogEntry,
  ]);
  const summary = summarizeTaskRisk(task(["a.read", "b.write", "a.read"]), catalog);
  assert.deepEqual(summary.toolNames, ["a.read", "b.write"], "duplicates collapse in plan order");
  assert.equal(summary.peak?.risk, "write");
  assert.equal(summary.approvalRequired, true);
});

check("a plan with no steps summarizes to nothing rather than a zero risk", () => {
  const summary = summarizeTaskRisk(task([]), new Map());
  assert.equal(summary.peak, null);
  assert.deepEqual(summary.toolNames, []);
  assert.equal(summary.approvalRequired, false);
});

/* ------------------------------------------------------------------ */
/* Age                                                                  */
/* ------------------------------------------------------------------ */

check("ageLabel returns null for anything it cannot parse", () => {
  const now = Date.parse("2026-09-09T04:00:00+00:00");
  assert.equal(ageLabel(null, now), null);
  assert.equal(ageLabel(undefined, now), null);
  assert.equal(ageLabel("", now), null);
  assert.equal(ageLabel("not a date", now), null);
});

check("ageLabel reads the clock rather than inventing a number", () => {
  const now = Date.parse("2026-09-09T04:00:00+00:00");
  assert.equal(ageLabel("2026-09-09T03:59:31+00:00", now), "29s");
  assert.equal(ageLabel("2026-09-09T03:58:00+00:00", now), "2m 0s");
  assert.equal(ageLabel("2026-09-09T01:30:00+00:00", now), "2h 30m");
  assert.equal(ageLabel("2026-09-07T02:00:00+00:00", now), "2d 2h");
  assert.equal(ageLabel("2026-09-09T04:00:30+00:00", now), "in the future");
});

/* ------------------------------------------------------------------ */
/* The legibility floor.                                              */
/*                                                                    */
/* The honesty text is the load bearing part of this surface: every    */
/* badge that says "partial" is only worth anything if the sentence    */
/* under it explaining why can actually be read. The same critic run   */
/* measured that sentence at 3.11:1 against the page and found 101     */
/* text nodes under 11px, six of them at 8px, on a surface whose       */
/* primary device is a phone. A sweep fixes it once; this check is     */
/* what stops it coming back, in the same spirit as the dash ban in    */
/* test_devon_integrity.py.                                           */
/*                                                                    */
/* The thresholds are computed, not taste. Against the page background */
/* #04070d, white at 45% opacity is 4.48:1 and fails WCAG AA for body  */
/* text by a hair, white at 50% is 5.35:1, and #526979 is 3.49:1 while */
/* #718898 is 5.42:1. So the ban is on the classes below AA, not on a  */
/* preference about how dim is too dim.                               */
/* ------------------------------------------------------------------ */

const HERE = dirname(fileURLToPath(import.meta.url));

/** Every file mounted under /control, directly or through a slot. */
const CONTROL_TREE = [
  "components/control/ControlPlane.tsx",
  "components/control/TierPanel.tsx",
  "components/control/CostPanel.tsx",
  "components/control/ExecutionHubPanel.tsx",
  "components/control/SecurityPanel.tsx",
  "components/control/SessionDoor.tsx",
  "components/control/ProvenanceSlot.tsx",
  "components/mind/KnowledgePanel.tsx",
  "components/readiness/AgentReadinessMatrix.tsx",
  "components/ledger/ProvenanceCard.tsx",
  "components/presence/PresenceStage.tsx",
  "components/presence/PresenceStageLoader.tsx",
];

/** Class patterns that render below WCAG AA on this background. */
const BELOW_AA: Array<{ pattern: RegExp; why: string }> = [
  { pattern: /text-\[(?:[0-9]|10)px\]/g, why: "under 11px is unreadable on a phone" },
  { pattern: /text-white\/(?:[0-9]|[1-3][0-9]|4[0-5])\b/g, why: "white at 45% or less is below 4.5:1 on the ACX void" },
  { pattern: /text-\[#526979\]/g, why: "#526979 is 3.49:1 on the ACX void" },
];

check("no text in the control tree renders below the AA floor", () => {
  const offences: string[] = [];
  for (const relative of CONTROL_TREE) {
    const source = readFileSync(join(HERE, "..", relative), "utf8");
    const lines = source.split("\n");
    for (const { pattern, why } of BELOW_AA) {
      lines.forEach((line, index) => {
        for (const hit of line.matchAll(pattern)) {
          offences.push(`${relative}:${index + 1} ${hit[0]} (${why})`);
        }
      });
    }
  }
  assert.deepEqual(offences, [], `\n${offences.join("\n")}`);
});

check("the legibility check is reading real files rather than an empty list", () => {
  // A glob that silently matches nothing passes forever. This asserts the
  // files are on disk and carry the classes the check is written against, so a
  // rename cannot turn the guard above into a no-op.
  assert.ok(CONTROL_TREE.length >= 12, "the control tree lost files");
  for (const relative of CONTROL_TREE) {
    const source = readFileSync(join(HERE, "..", relative), "utf8");
    assert.ok(source.length > 200, `${relative} is too small to be the real file`);
    assert.match(source, /className=/, `${relative} carries no classes to check`);
  }
});

check("every text input on the surface carries a label", () => {
  // A placeholder is not a label: it disappears the moment anything is typed,
  // and a screen reader is not required to announce it. Found by the same
  // critic run on the two inputs in PresenceStage.
  const withInputs = [
    "components/control/ProvenanceSlot.tsx",
    "components/mind/KnowledgePanel.tsx",
      "components/presence/PresenceStage.tsx",
  ];
  let inputs = 0;
  for (const relative of withInputs) {
    const source = readFileSync(join(HERE, "..", relative), "utf8");
    const ids = new Set([...source.matchAll(/htmlFor="([^"]+)"/g)].map((m) => m[1]));
    for (const tag of source.matchAll(/<input\b[\s\S]*?\/>/g)) {
      inputs += 1;
      const element = tag[0];
      const id = /\bid="([^"]+)"/.exec(element)?.[1];
      const labelled =
        (id !== undefined && ids.has(id)) ||
        /\baria-label(?:ledby)?=/.test(element);
      assert.ok(labelled, `${relative} has an input with no label: ${element.slice(0, 90)}`);
    }
  }
  assert.equal(inputs, 4, "the input count moved; re-check that each one is labelled");
});

/* the capture lane's only reachable surface */

/*
 * WHAT THIS GUARDS, AND WHY IT IS NOT A STYLE CHECK
 *
 * POST /api/v1/soul/propose is the only caller of knowledge_loop.propose in the
 * estate, and propose is the only thing that runs the Cerebras enrichment lane.
 * Until 2026-09-09 the only human surface reaching it was the platform console,
 * which wants a CurrentUser JWT pasted into a field by hand, so the lane wired
 * in PR #186 had never run once in production. Nothing failed. No test went
 * red. The capability existed and no person could trigger it.
 *
 * HOW THE FIRST VERSION OF THIS CHECK WAS BEATEN
 *
 * It sliced the handler by name and then asserted that each token was PRESENT
 * somewhere in the slice. A fresh critic beat that four ways on 2026-09-09,
 * each with the capture path genuinely broken and this check reporting ok:
 *
 *   1. A no-op early return above the fetch. Every token untouched.
 *   2. The whole body replaced by one string literal carrying all four tokens.
 *   3. A dead rememberLegacy neighbour inside the widened slice.
 *   4. A decoy `const remember` declared earlier, so indexOf found it first.
 *
 * So presence is no longer enough. Strings are blanked before the structural
 * pass, so a token inside a string literal cannot stand in for code. The
 * declaration must be unique, so a decoy fails rather than shadows. And the
 * handler must reach its fetch without returning first, so a no-op guard above
 * it fails rather than passes.
 */

/*
 * WHY THIS CHECK PARSES INSTEAD OF GREPPING
 *
 * Three text-based versions of this guard were beaten in one evening, each by
 * a critic, each shipping the capture lane dead at 26 checks passed and tsc 0:
 *
 *   1. presence assertions inside a name-sliced region: a no-op early return,
 *      a body replaced by one string carrying every token, a decoy declaration
 *      earlier in the file, and a dead neighbour inside the slice
 *   2. a uniqueness count on one exact declaration string: beaten by a
 *      neighbour under ANY other name, still inside the slice
 *   3. a hand written string blanker: three independent quote regexes mis-pair
 *      on apostrophes in JSX prose, and the replacement scanner mis-parsed a
 *      template literal containing a nested expression. Measured: the handler
 *      declaration this check exists to find dropped to zero occurrences. A
 *      guard that erases its own subject fails for reasons that are entirely
 *      its own.
 *
 * Text analysis cannot tell code from a string without parsing, and every
 * attempt to fake it added a new way to be wrong. TypeScript is already a
 * dependency because tsc runs in this same job, so the guard now asks the real
 * parser. A token inside a string literal is a StringLiteral node, not a
 * CallExpression, and no amount of clever quoting changes that.
 */

import ts from "typescript";

function parse(relative: string): ts.SourceFile {
  const path = join(HERE, "..", relative);
  return ts.createSourceFile(
    path,
    readFileSync(path, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    relative.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
  );
}

function collect(node: ts.Node, hit: (n: ts.Node) => boolean): ts.Node[] {
  const found: ts.Node[] = [];
  const walk = (n: ts.Node) => {
    if (hit(n)) found.push(n);
    ts.forEachChild(n, walk);
  };
  walk(node);
  return found;
}

/** Every `foo(...)` call in a subtree whose callee is exactly `name`. */
function callsTo(root: ts.Node, name: string): ts.CallExpression[] {
  return collect(
    root,
    (n) => ts.isCallExpression(n) && ts.isIdentifier(n.expression) && n.expression.text === name,
  ) as ts.CallExpression[];
}

/*
 * `const <name> = ...` or `function <name>() {}`. Both forms, because a handler
 * written as a function declaration is a refactor somebody will make and the
 * first version of this helper read only the const form. It failed closed, which
 * is right, and then explained itself as "declared 0 times; a second declaration
 * means this check may be reading the wrong one", which is a sentence about the
 * opposite problem. A guard that fails for a reason it cannot name costs the
 * next reader an hour.
 */
function declarationsNamed(root: ts.Node, name: string): ts.Node[] {
  return collect(root, (n) => {
    if (ts.isVariableDeclaration(n)) return ts.isIdentifier(n.name) && n.name.text === name;
    if (ts.isFunctionDeclaration(n)) return Boolean(n.name && n.name.text === name);
    return false;
  });
}

/*
 * REACHABILITY, NOT PRESENCE.
 *
 * The fourth critic (2026-09-09) got past the AST rewrite three ways without
 * touching a single token it asserts on, each one shipping the capture lane
 * dead at 26 checks passed and tsc exit 0:
 *
 *   A. the propose call wrapped in a condition that is never satisfied,
 *      `if (!utterance)`, which send() already guarantees is false
 *   B. the mode list filtered before it renders, so the keep button that the
 *      guard reads out of the array literal never reaches the page
 *   C. real dispatch moved to a switch, with the `=== "keep"` the guard reads
 *      left behind in a useCallback nothing calls
 *
 * A and B are the arc's ORIGINAL defect restated: a capability that exists and
 * that no person can reach. Proving a node exists in a subtree proves nothing
 * about whether control ever arrives there. The three helpers below are what
 * the guard was missing.
 */

/** Conditional ancestors between `node` and `stop`, exclusive of `stop`. */
function conditionalAncestors(node: ts.Node, stop: ts.Node): ts.Node[] {
  const gates: ts.Node[] = [];
  let at: ts.Node | undefined = node.parent;
  let reached = false;
  while (at) {
    if (at === stop) {
      reached = true;
      break;
    }
    if (
      ts.isIfStatement(at) ||
      ts.isConditionalExpression(at) ||
      ts.isSwitchStatement(at) ||
      ts.isCaseClause(at)
    ) {
      gates.push(at);
    }
    at = at.parent;
  }
  // THE VACUITY GUARD, and it is here because it was exploited.
  //
  // The original loop condition was `while (at && at !== stop)`, so a `node` that
  // is NOT inside `stop` walked all the way to the source file root, collected no
  // conditionals from an unrelated subtree, and returned []. Every caller then
  // read that empty array as "no gates, all good".
  //
  // A critic used exactly that on 2026-09-10: it moved the skill gate's decide
  // fetch into a module level `async function neverCalledSend()` that nothing
  // calls, replaced the real one with `new Response("{}")`, and control-check
  // reported 36 checks passed with tsc and next build both clean. Tee would have
  // pressed Approve, seen the panel confirm the ruling, and the row would never
  // have changed. That is worse than the no-door state this arc set out to fix,
  // because the no-door state was at least visibly absent.
  //
  // So an unreachable `stop` is now a hard error rather than a pass. A caller
  // that hands two unrelated nodes has a bug in the check, and a check with a bug
  // must fail loudly instead of approving.
  assert.ok(
    reached,
    "conditionalAncestors was given a node that is not inside `stop`, so it can prove nothing about whether that node is gated. The caller is resolving the two out of different subtrees",
  );
  return gates;
}

/** Strips `as const`/parentheses upward so the real method call is visible. */
function throughWrappers(node: ts.Node): ts.Node {
  let at = node;
  while (
    at.parent &&
    (ts.isAsExpression(at.parent) ||
      ts.isParenthesizedExpression(at.parent) ||
      ts.isSatisfiesExpression(at.parent))
  ) {
    at = at.parent;
  }
  return at;
}

/** The name of the `const <name> = ...` that encloses `node`, or null. */
function enclosingDeclarationName(node: ts.Node): string | null {
  let at: ts.Node | undefined = node.parent;
  while (at) {
    if (ts.isVariableDeclaration(at) && ts.isIdentifier(at.name)) return at.name.text;
    if (ts.isFunctionDeclaration(at) && at.name) return at.name.text;
    at = at.parent;
  }
  return null;
}

check("DEVON chat can still reach the capture endpoint", () => {
  const file = parse("components/devon/DevonChat.tsx");

  // 1. Find the handler the keep mode actually dispatches to, from the AST
  //    rather than by assuming a name. A guard checking a name nothing
  //    dispatches to is checking nothing.
  //
  //    Counted over BOTH dispatch forms. The fourth critic moved real dispatch
  //    into `switch (mode) { case "keep": ... }` and left the `=== "keep"` this
  //    check reads in a useCallback nothing calls, so keep answered
  //    conversationally and captured nothing at 26 checks passed. A guard that
  //    knows only one of the two ways to branch on a string is a guard that
  //    tells you which way to write the bug.
  const keepBranches = collect(file, (n) => {
    if (ts.isCaseClause(n)) {
      return ts.isStringLiteral(n.expression) && n.expression.text === "keep";
    }
    if (!ts.isBinaryExpression(n)) return false;
    if (n.operatorToken.kind !== ts.SyntaxKind.EqualsEqualsEqualsToken) return false;
    return ts.isStringLiteral(n.right) && n.right.text === "keep";
  });
  assert.equal(
    keepBranches.length,
    1,
    `expected exactly one keep dispatch site, counting \`=== "keep"\` and \`case "keep":\` alike; found ${keepBranches.length}, so a live branch and a dead one could both exist and this check cannot tell which one runs`,
  );

  // 1b. And whatever encloses that dispatch has to be called. A `case "keep"`
  //     inside a handler nothing invokes is unreachable however well formed it
  //     is, which is bypass C stated exactly.
  const dispatchOwner = enclosingDeclarationName(keepBranches[0]);
  assert.ok(
    dispatchOwner,
    "the keep dispatch is not inside a named declaration, so this check cannot prove anything reaches it",
  );
  assert.ok(
    callsTo(file, dispatchOwner as string).length > 0,
    `the keep dispatch lives in ${dispatchOwner}, and nothing in this file calls ${dispatchOwner}, so no keystroke can reach it`,
  );

  // The enclosing if/else block, and the handler awaited inside it.
  let branch: ts.Node = keepBranches[0];
  while (branch.parent && !ts.isIfStatement(branch.parent)) branch = branch.parent;
  assert.ok(branch.parent && ts.isIfStatement(branch.parent), "the keep comparison is not the test of an if statement");
  const thenBlock = (branch.parent as ts.IfStatement).thenStatement;
  const awaited = collect(thenBlock, (n) => ts.isAwaitExpression(n)) as ts.AwaitExpression[];
  assert.equal(awaited.length, 1, "the keep branch does not await exactly one call");
  const awaitedCall = awaited[0].expression;
  assert.ok(ts.isCallExpression(awaitedCall) && ts.isIdentifier(awaitedCall.expression),
    "the keep branch awaits something this check cannot resolve to a named handler");
  const handlerName = (awaitedCall.expression as ts.Identifier).text;

  // 2. That handler must be declared exactly once, so a decoy or a dead
  //    neighbour under any name cannot stand in for it.
  const decls = declarationsNamed(file, handlerName);
  assert.equal(
    decls.length,
    1,
    decls.length === 0
      ? `the keep branch dispatches to ${handlerName} and no \`const ${handlerName} =\` or \`function ${handlerName}\` declaration exists in this file. A destructured or imported handler is out of this check's reach: declare it here`
      : `${handlerName} is declared ${decls.length} times, and a second declaration means this check cannot tell which one the keep branch reaches`,
  );
  const handler = decls[0];

  // 3. Inside THAT declaration's own subtree, an authedFetch call whose first
  //    argument is the literal path. A string containing this text is a
  //    StringLiteral, not a CallExpression, so a body replaced by one string
  //    fails here by construction rather than by regex.
  const fetches = callsTo(handler, "authedFetch");
  const proposeCalls = fetches.filter(
    (c) => c.arguments.length > 0 && ts.isStringLiteral(c.arguments[0]) &&
      (c.arguments[0] as ts.StringLiteral).text === "/soul/propose",
  );
  assert.equal(
    proposeCalls.length,
    1,
    `${handlerName} must call authedFetch("/soul/propose") exactly once as real code. This check parses the file, so a token inside a string or a comment cannot satisfy it, and an extracted path constant fails here even though the code would work`,
  );
  const call = proposeCalls[0];

  // 4. Nothing may return before that call, and nothing may gate it. The
  //    return walk closes an early exit above the fetch; the gate walk closes
  //    the same defect written as a condition, which is what the fourth critic
  //    used: `if (!utterance)` around the whole body, dead for every real input
  //    because send() already refuses empty text. Both are the capture lane
  //    shipping dead with every other assertion here still green.
  //
  //    A try/catch is not a gate and passes, which is the refactor that matters.
  const returnsBefore = collect(handler, (n) => ts.isReturnStatement(n)).filter(
    (n) => n.getStart() < call.getStart(),
  );
  assert.equal(
    returnsBefore.length,
    0,
    `${handlerName} can return before it reaches authedFetch("/soul/propose"), so for some input it files nothing while every other assertion here still passes. A plain \`return\` in a nested callback trips this too: hoist it or restructure, this check reads statements and not control flow`,
  );
  const gates = conditionalAncestors(call, handler);
  assert.equal(
    gates.length,
    0,
    `authedFetch("/soul/propose") sits inside ${gates.length} condition(s) in ${handlerName}, so whether anything is ever captured depends on a test this check cannot evaluate. The call has to be on the handler's unconditional path`,
  );

  // 5. The request has to be a POST that leaves the Area unset, or the
  //    enrichment gate never opens: suggest_area only runs when area is None.
  const init = call.arguments[1];
  assert.ok(init && ts.isObjectLiteralExpression(init), "the authedFetch options are not an object literal this check can read");
  const options = init as ts.ObjectLiteralExpression;
  const method = options.properties.find(
    (pr) => ts.isPropertyAssignment(pr) && pr.name.getText() === "method",
  ) as ts.PropertyAssignment | undefined;
  assert.ok(
    method && ts.isStringLiteral(method.initializer) && method.initializer.text === "POST",
    `${handlerName} no longer POSTs, so propose would never be reached`,
  );
  const bodyText = options.getText();
  assert.ok(
    /area:\s*null/.test(bodyText),
    `${handlerName} now supplies an area, which closes the enrichment gate: suggest_area only runs when area is None`,
  );
  assert.ok(
    handler.getText().includes("what_happens"),
    `${handlerName} no longer renders what_happens, which is where the model's labelled gloss is shown`,
  );

  // 6. And a person has to be able to select it. One mode list, containing
  //    keep, with buttons that actually call setMode.
  const modeLists = collect(file, (n) => {
    if (!ts.isArrayLiteralExpression(n)) return false;
    return n.elements.some((e) => ts.isStringLiteral(e) && e.text === "auto") &&
      n.elements.some((e) => ts.isStringLiteral(e) && e.text === "ask");
  }) as ts.ArrayLiteralExpression[];
  assert.equal(
    modeLists.length,
    1,
    `expected exactly one mode list; ${modeLists.length} means a decoy could be read while another one renders`,
  );
  assert.ok(
    modeLists[0].elements.some((e) => ts.isStringLiteral(e) && e.text === "keep"),
    "the keep mode is not offered as a button, so no person can select it",
  );
  assert.ok(
    callsTo(file, "setMode").length > 0,
    "nothing calls setMode, so every mode button is inert and keep can never be selected",
  );

  // 6b. And every element of that list has to reach a button. The fourth critic
  //     put `.filter((option) => option !== "keep")` between the literal and the
  //     map: the array still contained keep, this check still read it out of the
  //     literal, and the button was gone from the page. Reading a literal is not
  //     reading a rendering.
  //
  //     Traced through a binding as well as inline, because hoisting the list to
  //     `const MODES = [...]` and mapping that is a refactor somebody will make.
  //     The first version of this clause failed on exactly that and was caught
  //     by its own control, which is the only reason it is not shipping.
  const methodsOn = (subject: ts.Node): string[] =>
    collect(file, (n) => {
      if (!ts.isPropertyAccessExpression(n)) return false;
      if (subject === n.expression) return true;
      // `const MODES = [...]` then `MODES.map(...)` elsewhere in the file.
      return (
        ts.isIdentifier(subject) &&
        ts.isIdentifier(n.expression) &&
        n.expression.text === (subject as ts.Identifier).text
      );
    }).map((n) => (n as ts.PropertyAccessExpression).name.text);

  const rendered = throughWrappers(modeLists[0]);
  const bound =
    rendered.parent && ts.isVariableDeclaration(rendered.parent) && ts.isIdentifier(rendered.parent.name)
      ? rendered.parent.name
      : rendered;
  const methods = methodsOn(bound);
  const dropping = methods.filter((m) =>
    ["filter", "slice", "reduce", "flatMap", "splice", "find", "pop", "shift"].includes(m),
  );
  assert.deepEqual(
    dropping,
    [],
    `the mode list has .${dropping[0]}() applied to it, which can drop an element, so the literal this check reads is not what a person sees. That is how the keep button disappeared while every assertion here still passed`,
  );
  assert.ok(
    methods.includes("map"),
    "nothing maps the mode list into buttons, so this check cannot prove the keep button reaches the page",
  );
});

/* the voice is owned, on every surface */

/*
 * WHAT THIS GUARDS. Tee opened /devon on 2026-09-09 and DEVON answered in a
 * stock female browser voice. DevonChat was calling window.speechSynthesis,
 * preferring an en-GB voice named daniel or arthur, and otherwise taking ANY
 * installed English voice. So the estate had two surfaces speaking as DEVON in
 * two different voices, and only /presence used the clone.
 *
 * The standing rule is voice and identity owned, never rented, and it carries
 * no exception path. A browser stock voice is a rented persona by definition:
 * it is whatever that machine happens to have installed, chosen by a vendor,
 * and it changes between devices. That is the thing this refuses to let back
 * in, on any surface, however convenient the API is.
 *
 * Comments are stripped first so the history above cannot satisfy the check,
 * and the speak handler is read by name so a match somewhere else in the file
 * cannot stand in for it.
 */

/*
 * Counted from the ESTATE, not from the lane.
 *
 * The first version of this list held three files under apps/web, and the
 * check it printed claimed "no surface". A critic found deploy/soul/console.html
 * still running the identical rented-voice implementation, served in production
 * by deploy/soul/main.py and by app.main GET /console. It titles itself DEVON
 * and labels its output lines DEVON, so it is a DEVON surface by any reading.
 *
 * That was the third count taken from a lane rather than the estate in one
 * evening, which is the miss CLAUDE.md's first law is written about. The list
 * is now every served surface that could speak, and the paths are relative to
 * apps/web so the two roots sit side by side rather than one being forgotten.
 *
 * docs/devon/assets/SYS_OPS_devon-console_v*.html is the same file: app.main
 * serves the newest of them and test_deploy_soul.py holds it byte identical to
 * deploy/soul/console.html, so guarding one guards both. The SUPERSEDED_ copies
 * are archives and are not served.
 */
/*
 * A FIXED LIST IS A LIST THAT THE NEXT FILE ESCAPES.
 *
 * The fourth critic (2026-09-09) did not attack the ban. It added
 * components/devon/DevonVoiceFallback.tsx with window.speechSynthesis,
 * synth.getVoices() and voices[0], the exact unfloored implementation this arc
 * was opened to remove, and the check reported ok 25 at 26 checks passed.
 *
 * Four hardcoded paths guard four files. They cannot guard a fifth that does
 * not exist yet, and the rule is about the estate rather than about those four.
 * test_devon_integrity.py:24-40 already had the answer: glob, then assert a
 * FLOOR on what the glob found, so a glob that silently matches nothing fails
 * loudly instead of passing vacuously.
 */
function walk(dir: string, keep: (name: string) => boolean): string[] {
  const out: string[] = [];
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const full = join(dir, entry.name);
    if (entry.isDirectory()) {
      if (entry.name === "node_modules" || entry.name === ".next") continue;
      out.push(...walk(full, keep));
    } else if (keep(entry.name)) {
      out.push(full);
    }
  }
  return out;
}

function voiceSurfaces(): string[] {
  // Named rather than globbed one level up, so a new top level directory is a
  // deliberate addition here. walk() throws ENOENT on a missing one, which is
  // the loud failure a silent skip would not be.
  const web = ["components", "app", "lib"].flatMap((sub) =>
    walk(join(HERE, "..", sub), (n) => n.endsWith(".ts") || n.endsWith(".tsx")),
  );
  assert.ok(
    web.length >= 50,
    `the web glob found ${web.length} source files and the estate has more than fifty, so this glob is wrong and the ban would pass over an unscanned tree`,
  );

  // The served HTML consoles. SUPERSEDED_ copies are archives that app.main's
  // version picker excludes, so they keep their history; everything else under
  // these two roots is servable and is held to the rule.
  const html = [
    join(HERE, "..", "..", "..", "deploy", "soul"),
    join(HERE, "..", "..", "..", "docs", "devon", "assets"),
  ].flatMap((dir) =>
    walk(dir, (n) => n.endsWith(".html") && !n.startsWith("SUPERSEDED_")),
  );
  assert.ok(
    html.length >= 3,
    `the served-console glob found ${html.length} files and there are at least three, so this glob is wrong`,
  );
  for (const required of ["deploy/soul/console.html", "SYS_OPS_devon-console_v10_2026-09-01.html"]) {
    assert.ok(
      html.some((f) => f.replace(/\\/g, "/").endsWith(required)),
      `${required} is a served DEVON surface and the glob did not reach it`,
    );
  }
  return [...web, ...html];
}

check("no surface speaks as DEVON in a rented browser voice", () => {
  for (const absolute of voiceSurfaces()) {
    const relative = absolute.slice(absolute.indexOf("Meta-Supreme-Apex-Genesis-") + 27);
    const source = readFileSync(absolute, "utf8");
    const code = source
      .replace(/\/\*[\s\S]*?\*\//g, "")
      .split("\n")
      .filter((line) => !line.trim().startsWith("//"))
      .join("\n");
    assert.ok(
      !/speechSynthesis|SpeechSynthesisUtterance/.test(code),
      `${relative} reaches for the browser's speech synthesis, which is a rented voice`,
    );
    // getVoices is the tell for picking a voice off the machine even without
    // naming speechSynthesis directly.
    assert.ok(
      !/\.getVoices\s*\(/.test(code),
      `${relative} selects a voice from the machine's installed set`,
    );
  }
});

/*
 * WHY THIS ONE PARSES TOO.
 *
 * It used to slice the file between indexOf("const speak = useCallback(") and
 * the next indexOf("useEffect("). That is bypass shape 4 from the commit one
 * check above, which the capture guard was rewritten to close and this one was
 * left carrying: the fourth critic added an unmounted VoicePreview component
 * earlier in the file with its own `const speak = useCallback(`, a
 * `${PRESENCE_BASE}/tts` fetch and an Authorization header, then a `useEffect(`
 * to close the slice. indexOf found the decoy, every assertion here passed at
 * ok 26, and the real speak in DevonChat was a no-op. DEVON was silent on
 * /devon with the whole gate green.
 *
 * Fixing one check and leaving its neighbour on the beaten mechanism is how a
 * guard file ends up with a soft edge nobody remembers. Same treatment: resolve
 * the declaration through the parser, require it unique so a decoy fails rather
 * than shadows, and require something to call it so it cannot be a correct
 * handler nothing reaches.
 */
check("DEVON chat speaks through the presence service's clone", () => {
  const file = parse("components/devon/DevonChat.tsx");
  const decls = declarationsNamed(file, "speak");
  assert.equal(
    decls.length,
    1,
    decls.length === 0
      ? "DevonChat has no `const speak =` or `function speak` declaration, so this check cannot find the handler. A destructured or imported one is out of its reach: declare it here"
      : `DevonChat declares speak ${decls.length} times, and a second declaration is a decoy this check could read while the real handler stays silent`,
  );
  assert.ok(
    callsTo(file, "speak").length > 0,
    "nothing calls speak, so the handler is correct and unreachable and DEVON says nothing",
  );
  const handler = decls[0].getText();

  assert.ok(
    /\$\{PRESENCE_BASE\}\/tts/.test(handler),
    "speak no longer streams from the presence service, so the chat is not using Tee's clone",
  );
  assert.ok(
    /Authorization/.test(handler),
    "speak calls the voice endpoint unauthenticated, which would 401 and go silent",
  );
  // The voice belongs to the service, never to the caller. A voice id sent from
  // the browser would let this surface speak as anyone.
  assert.ok(
    !/voice_id|voiceId|CARTESIA_VOICE/.test(handler),
    "speak names a voice, but the voice is the presence service's to choose and never the caller's",
  );
});

/*
 * WHAT THIS GUARDS. Every agent task that reaches COMPLETED drafts a skill
 * proposal and saves it, and DEVON_AUTO_SKILL_PROPOSE defaults ON
 * (app/services/agent_tasks.py:174, saved at :513). CLAUDE.md's invariant reads
 * "Skill promotion is human gated". Until 2026-09-09 it was gated with no door:
 * GET /agent-expansion/skill-proposals (app/api/v1/agent_expansion.py:161) and
 * POST /agent-expansion/skill-proposals/{id}/decide (:173) had no caller
 * anywhere in apps/web, so proposals piled up where no person could read them.
 * Nothing failed. No test went red. The same shape as the capture endpoint
 * above: a capability that existed and nobody could trigger.
 *
 * So the panel existing is not the thing worth guarding. Three things are, and
 * each of them can break silently:
 *
 *   1. the panel still calls both routes, as real code
 *   2. the panel is still mounted on a page a person opens
 *   3. approve and promote stay two separate rulings in the request body
 *
 * Point 3 is the sharp one. SkillDecideBody declares `promote: bool = True`
 * (app/api/v1/agent_expansion.py:35-37), so a decide body that omits the key
 * promotes. A refactor that drops promote from the payload turns every approval
 * into an activation and the UI would look identical.
 *
 * WHY THIS PARSES INSTEAD OF GREPPING. Same reason as the capture check: three
 * text based guards were beaten in this repository in one evening. A route path
 * pasted into a comment or a JSX sentence is a comment or a StringLiteral, not a
 * CallExpression with a TemplateExpression argument, and no quoting changes that.
 *
 * WHAT THIS DELIBERATELY DOES NOT ASSERT. The capture check forbids any return
 * before its fetch. That would be wrong here: the decide handler legitimately
 * returns early when the session token has gone, and a guard demanding it press
 * on regardless would be demanding an unauthenticated request that 401s.
 */

/**
 * The literal halves of a template expression with every interpolation
 * collapsed to "{}", so `${API_BASE}/a/${id}/b` reads as "{}/a/{}/b".
 * Returns null for anything that is not a template expression, which is how a
 * path sitting inside a plain string fails to match rather than passing.
 */
function templatePath(node: ts.Node): string | null {
  if (!ts.isTemplateExpression(node)) return null;
  let out = node.head.text;
  for (const span of node.templateSpans) out += `{}${span.literal.text}`;
  return out;
}

/** The property assignment named `key` on an object literal, or undefined. */
function propNamed(
  object: ts.ObjectLiteralExpression,
  key: string,
): ts.PropertyAssignment | undefined {
  return object.properties.find(
    (pr) => ts.isPropertyAssignment(pr) && pr.name.getText() === key,
  ) as ts.PropertyAssignment | undefined;
}

function isBooleanLiteral(node: ts.Node): boolean {
  return node.kind === ts.SyntaxKind.TrueKeyword || node.kind === ts.SyntaxKind.FalseKeyword;
}

const GATE = "components/control/SkillProposalGate.tsx";
const GATE_COMPONENT = "SkillProposalGate";

check("the skill proposal gate still reads the queue and rules on it", () => {
  const panel = parse(GATE);
  const fetches = callsTo(panel, "fetch");
  // NOTE for whoever edits below: `fetches` is file wide on purpose, for the
  // COUNTING assertions ("exactly once in this file"). Every assertion about
  // where a call sits must re-resolve it from inside the handler's own subtree,
  // as the decide block does. Resolving the call and the handler independently is
  // what let a critic orphan the ruling fetch and still report 36 passed.

  // 1. The read. Without it there is no queue on the page, and a door onto
  //    nothing is the state this whole check exists to end.
  const listCalls = fetches.filter(
    (c) =>
      c.arguments.length > 0 &&
      templatePath(c.arguments[0]) === "{}/agent-expansion/skill-proposals",
  );
  assert.equal(
    listCalls.length,
    1,
    `${GATE} must fetch \`\${API_BASE}/agent-expansion/skill-proposals\` exactly once as real code; found ${listCalls.length}`,
  );

  // 2. The decide call, as a POST. A GET here would read as success and rule
  //    on nothing.
  const decideCalls = fetches.filter(
    (c) =>
      c.arguments.length > 0 &&
      templatePath(c.arguments[0]) === "{}/agent-expansion/skill-proposals/{}/decide",
  );
  assert.equal(
    decideCalls.length,
    1,
    `${GATE} must fetch the decide route exactly once as real code; found ${decideCalls.length}. Without it the panel shows proposals nobody can rule on`,
  );
  // And the ruling call must sit on its handler's unconditional path. This is
  // the one assertion the panel's own author could not write: the reachability
  // helpers arrived in the same commit that closed the capture guard's three
  // bypasses, and a gate whose decide fetch hides behind a never-satisfied
  // condition is that defect wearing this arc's name. A try/catch is not a gate.
  // declarationsNamed, not a const only predicate. The first version of this line
  // matched `ts.isVariableDeclaration` alone, so rewriting the handler as
  // `async function decide()` went red on correct code with the message "declared 0
  // times". That is the exact misfire the comment above declarationsNamed was
  // written about, reintroduced one screenful below it by someone who did not read
  // his own helper. An adversary caught it on 2026-09-10.
  const decideOwner = declarationsNamed(panel, "decide");
  assert.equal(
    decideOwner.length,
    1,
    decideOwner.length === 0
      ? `${GATE} has no \`const decide =\` or \`function decide\` declaration, so this check cannot find the ruling handler`
      : `${GATE} declares decide ${decideOwner.length} times, and a second declaration is a decoy this check could read while the real handler never sends`,
  );
  // THE RULING FETCH MUST BE INSIDE THE HANDLER, not merely somewhere in the file.
  //
  // `decideCalls` above is filtered out of a FILE WIDE search, which is right for
  // asserting "exactly once in this file" and useless for asserting where it sits.
  // A critic moved the ruling fetch into a module level function nothing calls and
  // left `new Response("{}")` in its place: the count still said one, the gate walk
  // walked an unrelated subtree and found nothing, and this check reported 36
  // passed while every button reported success and no ruling reached the API.
  //
  // Re-resolved from the handler's own subtree, the same direction the DevonChat
  // capture guard resolves in. `conditionalAncestors` now also refuses a node that
  // is not inside its stop node, so the two halves cover each other.
  const inHandler = callsTo(decideOwner[0], "fetch").filter(
    (c) =>
      c.arguments.length > 0 &&
      templatePath(c.arguments[0]) ===
        "{}/agent-expansion/skill-proposals/{}/decide",
  );
  assert.equal(
    inHandler.length,
    1,
    `the decide route is fetched ${inHandler.length} times INSIDE the decide handler. It has to be exactly one: a call that lives elsewhere in the file is a ruling no button can send, however real it looks`,
  );
  assert.ok(
    inHandler[0] === decideCalls[0],
    "the decide fetch this check counted is not the one inside the handler, so one of them is a decoy",
  );

  const decideGates = conditionalAncestors(decideCalls[0], decideOwner[0]);
  assert.equal(
    decideGates.length,
    0,
    `the decide fetch sits inside ${decideGates.length} condition(s), so whether a ruling ever reaches the API depends on a test this check cannot evaluate. It has to be on the handler's unconditional path`,
  );

  // WHERE THIS CLAUSE STOPS, MEASURED RATHER THAN ASSUMED.
  //
  // The capture guard one screenful up also walks for a `return` before its call,
  // and copying that here was tried and reverted, because the handler does return
  // early: on a missing session token, which is a real condition and not a decoy.
  //
  // CORRECTION, 2026-09-10. This comment previously said the early return was an
  // already-sent guard. That was false, and an adversary measured it: the only
  // `return` before the fetch tests `!token`, and re-entry is prevented by
  // `disabled={sending}` on all three buttons, which is an attribute rather than a
  // return. The block comment above this check always gave the right reason; this
  // one invented a second one. Two reasons for the same decision, one of them
  // fabricated, is exactly what the first law is written about, so it is corrected
  // here rather than quietly deleted.
  //
  // The bypass it would have closed is `if (proposal.proposal_id === "") return;`
  // above the fetch, dead for every real proposal. It stays open and graded low,
  // and the same adversary gave the better reason why: the containment assertion
  // above reaches the identical outcome with no contrived condition at all, so
  // fortifying this window while that door stood open bought nothing. The door is
  // now shut. What is left needs a guard clause whose test is never true, which is
  // a deliberate act rather than a regression or a copy paste.

  const init = decideCalls[0].arguments[1];
  assert.ok(
    init && ts.isObjectLiteralExpression(init),
    "the decide fetch options are not an object literal this check can read",
  );
  const options = init as ts.ObjectLiteralExpression;
  const method = propNamed(options, "method");
  assert.ok(
    method && ts.isStringLiteral(method.initializer) && method.initializer.text === "POST",
    "the decide fetch no longer POSTs, so no ruling is ever recorded",
  );

  // 3. Both halves of the ruling in the body, and neither one hardcoded.
  //    A literal promote:true here promotes every approval; a literal
  //    approve:true makes the reject button approve.
  const body = propNamed(options, "body");
  assert.ok(body, "the decide fetch sends no body, so approve and promote never reach the API");
  const payloads = (
    collect(body as ts.Node, (n) => ts.isObjectLiteralExpression(n)) as ts.ObjectLiteralExpression[]
  ).filter((o) => propNamed(o, "approve") && propNamed(o, "promote"));
  assert.equal(
    payloads.length,
    1,
    `the decide body must carry exactly one object with both approve and promote; found ${payloads.length}. SkillDecideBody defaults promote to true, so a body missing the key promotes every approval`,
  );
  for (const key of ["approve", "promote"] as const) {
    const assigned = propNamed(payloads[0], key) as ts.PropertyAssignment;
    assert.ok(
      !isBooleanLiteral(assigned.initializer),
      `the decide body hardcodes ${key}, so the button the human pressed no longer decides it`,
    );

    // Each key must read the handler's OWN ruling parameter, and must read the
    // key of the same name. Three shapes got past the literal check alone, all
    // found by an adversary on 2026-09-10, all with the panel unchanged to a
    // reader and "Approve only" silently activating a skill:
    //
    //   promote: true as boolean      an AsExpression, not a TrueKeyword
    //   promote: decision.approve     the exact inference the docs promise never
    //                                 happens, which is the invariant itself
    //   promote: decision.promote,    a SpreadAssignment is invisible to
    //   ...RULING_DEFAULTS            propNamed, and the spread wins
    //
    // The second is the one that matters most: CLAUDE.md's rule is that skill
    // promotion is human gated, and inferring promote from approve is precisely
    // ungating it. The third is the most plausible accident, because a defaults
    // object looks like tidying.
    assert.ok(
      ts.isPropertyAccessExpression(assigned.initializer) &&
        ts.isIdentifier(assigned.initializer.name) &&
        assigned.initializer.name.text === key,
      `the decide body's ${key} is not a plain read of the ruling's own ${key}. It has to be exactly \`${key}: <ruling>.${key}\`: a cast, a widened type, or a read of the OTHER key is how approve silently starts promoting`,
    );
  }

  // And nothing may be spread into that payload. A spread is invisible to the
  // per key assertions above and overrides whatever they approved.
  for (const payload of payloads) {
    const spreads = payload.properties.filter((pr) => ts.isSpreadAssignment(pr));
    assert.equal(
      spreads.length,
      0,
      `the decide body spreads ${spreads.length} object(s) into the ruling. A spread can set approve or promote to anything after this check has read them, so the payload must be written out key by key`,
    );
  }

  // 4. All three rulings have to be reachable from the rendered buttons, and
  //    every call site has to name promote. Read off the call sites of the
  //    panel's own handler, so a button wired to nothing fails here.
  // decideOwner is already resolved and already asserted unique above. The first
  // version of this block re-ran the identical predicate and asserted the identical
  // thing, which can never fail once the first has passed: it read as extra
  // coverage and was none. Removed rather than left as decoration.
  const rulings = new Set<string>();

  // EVERY RULING MUST COME OFF A RENDERED BUTTON, not merely exist in the file.
  //
  // This read `callsTo(panel, "decide")` file wide. An adversary put all three call
  // sites in an unreferenced useCallback and rewrote every button to
  // `onClick={() => undefined}` on 2026-09-10: three rulings still resolved, the
  // set still held false/false, true/false and true/true, and this check reported
  // ok while no button on the page did anything at all.
  //
  // So the sites are now collected from inside JSX onClick attributes. A call in
  // dead code is not a button, and this check is about what a person can press.
  const onClickHandlers = collect(panel, (n) => {
    if (!ts.isJsxAttribute(n)) return false;
    return ts.isIdentifier(n.name) && n.name.text === "onClick";
  }) as ts.JsxAttribute[];
  const sites = onClickHandlers.flatMap((attr) =>
    attr.initializer ? callsTo(attr.initializer, "decide") : [],
  );
  assert.ok(
    sites.length > 0,
    "no rendered button's onClick calls decide, so every ruling in this file is dead code and the gate is a picture of a gate",
  );
  assert.equal(
    sites.length,
    callsTo(panel, "decide").length,
    `${callsTo(panel, "decide").length} call(s) to decide exist in the file but only ${sites.length} are wired to a button's onClick. A ruling nothing can press is dead code that makes this check read as coverage`,
  );
  for (const site of sites) {
    const arg = site.arguments[1];
    assert.ok(
      arg && ts.isObjectLiteralExpression(arg),
      "a decide call site does not pass a literal ruling this check can read",
    );
    const ruling = arg as ts.ObjectLiteralExpression;
    const approve = propNamed(ruling, "approve");
    const promote = propNamed(ruling, "promote");
    assert.equal(
      ruling.properties.filter((pr) => ts.isSpreadAssignment(pr)).length,
      0,
      "a decide call site spreads an object into its ruling, which can overwrite approve or promote after this check has read them",
    );
    assert.ok(
      approve && isBooleanLiteral(approve.initializer),
      "a decide call site does not state approve as a literal, so what it rules cannot be read here",
    );
    assert.ok(
      promote && isBooleanLiteral(promote.initializer),
      "a decide call site omits promote. The API defaults it to true, so that button would activate a skill the human only approved",
    );
    rulings.add(
      `${approve.initializer.kind === ts.SyntaxKind.TrueKeyword}/${promote.initializer.kind === ts.SyntaxKind.TrueKeyword}`,
    );
  }
  assert.ok(
    rulings.has("false/false"),
    "no button rejects a proposal. A gate where refusing is unavailable is not a gate",
  );
  assert.ok(
    rulings.has("true/false"),
    "no button approves without activating, so approving a draft and activating a skill have collapsed into one ruling",
  );
  assert.ok(
    rulings.has("true/true"),
    "no button activates an approved proposal, so nothing can ever be promoted from this surface",
  );

  // 5. The instructions are the artifact being approved, so the JSX has to
  //    render the whole property and nothing derived from it. Asserting only
  //    that the property is READ somewhere was measured green against
  //    `{proposal.instructions.slice(0, 80)}` on 2026-09-09, which is a ruling
  //    made on the first eighty characters. Requiring the interpolation to be
  //    the bare property access turns a truncation into a CallExpression and
  //    fails it. This still cannot catch a CSS line clamp, which is a style and
  //    not a node: that boundary is real and is not claimed to be closed here.
  const isField = (n: ts.Node, field: string) =>
    ts.isPropertyAccessExpression(n) &&
    n.name.text === field &&
    ts.isIdentifier(n.expression) &&
    n.expression.text === "proposal";
  assert.ok(
    collect(
      panel,
      (n) => ts.isJsxExpression(n) && n.expression !== undefined && isField(n.expression, "instructions"),
    ).length > 0,
    `${GATE} does not render proposal.instructions whole, so a ruling would be made on a title or an excerpt`,
  );
  // source_task_id is only a trace, so a fallback around it is legitimate and
  // only the read is required here.
  assert.ok(
    collect(panel, (n) => isField(n, "source_task_id")).length > 0,
    `${GATE} never reads proposal.source_task_id, so what produced the draft cannot be traced`,
  );
});

check("the skill proposal gate is mounted on the control plane", () => {
  const shell = parse("components/control/ControlPlane.tsx");

  const imported = collect(shell, (n) => {
    if (!ts.isImportSpecifier(n)) return false;
    return n.name.text === GATE_COMPONENT;
  });
  assert.equal(
    imported.length,
    1,
    `ControlPlane.tsx must import ${GATE_COMPONENT} exactly once; found ${imported.length}`,
  );

  const rendered = collect(shell, (n) => {
    if (!ts.isJsxSelfClosingElement(n) && !ts.isJsxOpeningElement(n)) return false;
    const tag = (n as ts.JsxSelfClosingElement | ts.JsxOpeningElement).tagName;
    return ts.isIdentifier(tag) && tag.text === GATE_COMPONENT;
  });
  assert.equal(
    rendered.length,
    1,
    `ControlPlane.tsx must render <${GATE_COMPONENT} /> exactly once; found ${rendered.length}. An imported but unrendered panel is the unreachable route this arc closed`,
  );

  // AND NOT BEHIND A CONDITION. Counting the JSX node proved the element exists in
  // the file, which is not the same as it reaching the page. An adversary wrote
  // `{process.env.NEXT_PUBLIC_SKILL_GATE === "on" ? <SkillProposalGate /> : null}`
  // on 2026-09-10: exactly one import, exactly one element, this check reported ok,
  // and the panel never rendered. Measured effect on the build: /control fell from
  // 27.7 kB to 26.2 kB and the route string vanished from every static chunk.
  //
  // The message above claimed to catch exactly that, which made it worse than
  // silent. conditionalAncestors was already in this file, one screenful up, being
  // used for the ruling fetch. It is now used here too.
  const mountGates = conditionalAncestors(rendered[0], shell);
  assert.equal(
    mountGates.length,
    0,
    `<${GATE_COMPONENT} /> is mounted inside ${mountGates.length} condition(s), so whether a person can see the gate at all depends on a test this check cannot evaluate. The mount has to be unconditional`,
  );
});

/* ------------------------------------------------------------------ */
/* Rendered copy may not point at a panel that is not there            */
/* ------------------------------------------------------------------ */

/*
 * The defect this catches was mine, found on 2026-09-10 while writing the very
 * status doc about it, and it was live on main for one commit.
 *
 * The graph panel was pulled in 8707362 for stating a measurement that had not
 * run. KnowledgePanel.tsx's file docstring was rewritten to say so, and
 * ControlPlane.tsx's tier note was rewritten to say so, and the paragraph at the
 * bottom of KnowledgePanel.tsx's own render was not. It went on telling every
 * reader that "the edges between these items are drawn in the knowledge graph
 * panel below", pointing at a component that no longer existed in the tree.
 *
 * Twenty eight checks in this file passed over it, and so did 61 Python tests
 * and a production build, because every one of them reads a literal, a symbol or
 * an import. This arc's own method note was "a guard that reads a literal is not
 * reading a rendering", written before the miss and not applied to it.
 *
 * So this check reads the rendering. It resolves prose out of the AST rather than
 * out of the file text, because a source comment is allowed to name a pulled
 * panel and this file's docstrings do: a reader of the source is not a reader of
 * the page. TierPanel.tsx has "while the panel below it had no session" in a
 * line comment, correct there and a false positive for any regex over raw text.
 *
 * WHAT IT CANNOT DO. It only resolves a NAMED panel, matching a determiner then
 * one to four words then "panel" then a direction. Bare copy like "the panel
 * below" names nothing this check can look up, and is left alone rather than
 * guessed at. Widening it to unnamed references would mean speculating about
 * which component was meant, which the first law here forbids.
 */

/** True when the node's ancestor chain reaches JSX, so its text reaches a browser. */
function insideJsx(node: ts.Node): boolean {
  let at: ts.Node | undefined = node.parent;
  while (at) {
    if (
      ts.isJsxElement(at) ||
      ts.isJsxFragment(at) ||
      ts.isJsxSelfClosingElement(at) ||
      ts.isJsxAttribute(at) ||
      ts.isJsxExpression(at)
    ) {
      return true;
    }
    at = at.parent;
  }
  return false;
}

/**
 * Every string a browser renders from this file, whitespace normalised so a
 * phrase that wraps across two source lines still reads as one phrase.
 *
 * JsxText is the prose between tags. A string or template literal counts too once
 * its ancestor chain reaches JSX, which is how ControlPlane.tsx carries its tier
 * notes: they live in a ternary inside an expression container, not in JsxText,
 * and a check that read only JsxText would pass over the longest prose on the
 * control plane.
 */
function renderedProse(file: ts.SourceFile): string[] {
  const out: string[] = [];
  const visit = (n: ts.Node): void => {
    if (ts.isJsxText(n)) {
      const text = n.text.replace(/\s+/g, " ").trim();
      if (text) out.push(text);
    } else if (
      (ts.isStringLiteral(n) ||
        ts.isNoSubstitutionTemplateLiteral(n) ||
        ts.isTemplateExpression(n)) &&
      insideJsx(n)
    ) {
      const text = n.getText(file).replace(/\s+/g, " ").trim();
      if (text) out.push(text);
    }
    ts.forEachChild(n, visit);
  };
  ts.forEachChild(file, visit);
  return out;
}

/** Every identifier declared anywhere under apps/web, so a name can be resolved. */
function webDeclaredNames(files: string[]): Set<string> {
  const names = new Set<string>();
  for (const absolute of files) {
    const file = ts.createSourceFile(
      absolute,
      readFileSync(absolute, "utf8"),
      ts.ScriptTarget.Latest,
      true,
      absolute.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
    );
    const visit = (n: ts.Node): void => {
      if ((ts.isFunctionDeclaration(n) || ts.isClassDeclaration(n)) && n.name) {
        names.add(n.name.text);
      }
      if (ts.isVariableDeclaration(n) && ts.isIdentifier(n.name)) names.add(n.name.text);
      if (ts.isImportSpecifier(n)) names.add(n.name.text);
      ts.forEachChild(n, visit);
    };
    ts.forEachChild(file, visit);
  }
  return names;
}

const NAMED_PANEL_NEARBY =
  /\b(?:the|a|an)\s+((?:[a-z][a-z0-9]*\s+){1,4})panel\s+(below|above|to the (?:left|right)|on the (?:left|right))\b/gi;

// Words that are grammar rather than a component's name. "Knowledge graph panel"
// keeps both of its words; "the current numbers panel below" would keep both of
// its own and fail, which is the right direction: an unresolvable name is a
// finding, not a pass.
const GRAMMAR = new Set([
  "the", "a", "an", "this", "that", "its", "their", "in", "on", "at", "of", "and", "or",
  "while", "same", "one", "each", "every", "other", "first", "second", "next", "last",
]);

check("no rendered copy points at a named panel the tree does not have", () => {
  const files = ["components", "app", "lib"].flatMap((sub) =>
    walk(join(HERE, "..", sub), (n) => n.endsWith(".ts") || n.endsWith(".tsx")),
  );
  assert.ok(
    files.length >= 50,
    `the web glob found ${files.length} source files and the estate has more than fifty, so this glob is wrong and the check would pass over an unscanned tree`,
  );

  const declared = webDeclaredNames(files);
  // A floor on the resolver itself. An empty or tiny set would make every lookup
  // below fail, and a resolver that silently returned nothing would make every
  // lookup pass if the assertion were inverted. Name the shape it must have.
  assert.ok(
    declared.size >= 200,
    `the declaration index holds ${declared.size} names and apps/web declares far more, so the resolver is broken and its answers mean nothing`,
  );
  assert.ok(
    declared.has("KnowledgePanel") && declared.has("ControlPlane"),
    "the declaration index cannot see KnowledgePanel or ControlPlane, so it is not reading the components tree",
  );

  let examined = 0;
  for (const absolute of files) {
    if (!absolute.endsWith(".tsx")) continue;
    const relative = absolute.slice(absolute.indexOf("apps/web"));
    const file = ts.createSourceFile(
      absolute,
      readFileSync(absolute, "utf8"),
      ts.ScriptTarget.Latest,
      true,
      ts.ScriptKind.TSX,
    );
    for (const prose of renderedProse(file)) {
      for (const hit of prose.matchAll(NAMED_PANEL_NEARBY)) {
        const words = hit[1].trim().split(/\s+/).filter((w) => !GRAMMAR.has(w.toLowerCase()));
        if (words.length === 0) continue;
        examined += 1;
        const pascal = words.map((w) => w[0].toUpperCase() + w.slice(1)).join("");
        const candidates = [`${pascal}Panel`, pascal, `${pascal}Card`];
        assert.ok(
          candidates.some((c) => declared.has(c)),
          `${relative} renders "${hit[0]}", which sends the reader to a panel named ${candidates.join(" or ")}, and apps/web declares none of them. Either the panel was removed and this copy was not, or the copy names it wrongly. A pulled panel that copy still points at is the 2026-09-10 miss this check exists for`,
        );
      }
    }
  }

  // Zero examined would make the loop above vacuous, the same shape as the
  // pgvector assertion that ran zero times and let an L2 operator pass. There is
  // no positional cross reference left in the estate after the 2026-09-10 fix, so
  // zero is the correct answer today and the assertion is on the mechanism
  // instead: prove the matcher fires on the exact sentence that was live.
  const wasLive =
    "The edges between these items are drawn in the knowledge graph panel below, read from GET /knowledge/graph.";
  const proof = [...wasLive.matchAll(NAMED_PANEL_NEARBY)];
  assert.equal(
    proof.length,
    1,
    `the matcher no longer fires on the sentence this check was written for, so it is guarding nothing. Examined ${examined} live cross reference(s)`,
  );
  const proven = proof[0][1]
    .trim()
    .split(/\s+/)
    .filter((w) => !GRAMMAR.has(w.toLowerCase()))
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join("");
  assert.equal(
    proven,
    "KnowledgeGraph",
    `the matcher resolved "${proven}" out of the sentence that was live, and it has to resolve KnowledgeGraph for the lookup to mean anything`,
  );
  // The lookup must be able to FAIL, or the assertion in the loop above is
  // satisfied by a resolver that says yes to everything. Proving that needs a
  // name the tree genuinely lacks, and the original proof used KnowledgeGraph,
  // which the tree now has: the graph panel shipped on 2026-09-10, this
  // assertion went red, and its message said to give the proof an absent name.
  // That is the check catching its own staleness rather than a person noticing.
  const absent = "the phlogiston panel below, read from GET /nowhere.";
  const absentHit = [...absent.matchAll(NAMED_PANEL_NEARBY)];
  assert.equal(absentHit.length, 1, "the matcher no longer fires on a plain named positional reference");
  const absentName = absentHit[0][1]
    .trim()
    .split(/\s+/)
    .filter((w) => !GRAMMAR.has(w.toLowerCase()))
    .map((w) => w[0].toUpperCase() + w.slice(1))
    .join("");
  assert.equal(absentName, "Phlogiston", `expected Phlogiston, resolved ${absentName}`);
  for (const candidate of [`${absentName}Panel`, absentName, `${absentName}Card`]) {
    assert.ok(
      !declared.has(candidate),
      `apps/web declares ${candidate}, so this proof case can no longer fail and the check above proves nothing. Pick a name the tree does not have`,
    );
  }

  // And the real case now resolves to something that DOES exist, which is the
  // other half: a guard that can only ever fail is as useless as one that can
  // only ever pass.
  assert.ok(
    declared.has("KnowledgeGraphPanel"),
    "KnowledgeGraphPanel is not declared, so the knowledge panel's cross reference to it points at nothing again",
  );
});

/* ------------------------------------------------------------------ */
/* The knowledge graph, against fixtures the ROUTE generated            */
/* ------------------------------------------------------------------ */

/*
 * WHY THESE FIXTURES ARE NOT WRITTEN HERE
 *
 * The graph panel was pulled on 2026-09-10 with both suites green. The route
 * sends ONE FLAT payload; the panel read `raw.counts` as a nested member, so
 * every real response produced `counts: null`. test_knowledge_graph.py was green
 * because it pinned the flat shape the route sends. The graph checks in THIS file
 * were green because their fixtures were written BY HAND in the nested shape. Two
 * suites, each internally consistent, agreeing with each other about nothing, and
 * the panel shipped a headline about a comparison that never ran.
 *
 * So the fixtures are now GENERATED, by scripts/gen_knowledge_graph_fixtures.py
 * calling the real `assemble_graph`, and read from disk here.
 * test_knowledge_graph_fixtures.py regenerates and compares on every Python run,
 * so the committed file cannot drift back into being hand written.
 *
 * A fixture is committed rather than generated at check time because web-ci.yml
 * runs this script in a Node only job: there is no Python interpreter there.
 */

type Fixtures = {
  scenarios: Record<string, { why: string; payload: unknown }>;
};

const GRAPH_FIXTURES: Fixtures = JSON.parse(
  readFileSync(join(HERE, "..", "components", "mind", "knowledge-graph-fixtures.json"), "utf8"),
) as Fixtures;

function scenario(name: string): unknown {
  const entry = GRAPH_FIXTURES.scenarios[name];
  assert.ok(
    entry,
    `the generated fixture has no scenario named ${name}. Regenerate with python3 scripts/gen_knowledge_graph_fixtures.py, and if it is genuinely gone, delete the check that reads it rather than inventing a payload here`,
  );
  return entry.payload;
}

check("the graph fixtures are the route's own output, not a hand written shape", () => {
  const names = Object.keys(GRAPH_FIXTURES.scenarios);
  assert.ok(
    names.length >= 8,
    `the fixture carries ${names.length} scenarios and the generator defines at least eight, so this file is stale`,
  );
  for (const name of names) {
    const payload = scenario(name) as Record<string, unknown>;
    // The defect itself, pinned from this side too. A nested counts object is
    // the shape the pulled panel read and the route has never sent.
    assert.ok(
      !("counts" in payload),
      `${name} carries a nested counts object. The route sends a flat payload; reading a nested one is what got the panel pulled`,
    );
    assert.ok(
      "items_total" in payload,
      `${name} has no top level items_total, so it is not the route's payload`,
    );
    // And every scenario must survive the parser, or a check below is asserting
    // over a null it never noticed.
    const parsed = parseGraphPayload(payload);
    assert.notEqual(parsed, null, `${name} did not parse at all`);
    assert.notEqual(
      parsed!.counts,
      null,
      `${name} parsed with counts null. That is the original defect: the reader looking in the wrong place and the panel reporting "the route did not say" over counts that were right there`,
    );
    assert.deepEqual(
      parsed!.missingFields,
      [],
      `${name} parsed with missing fields ${JSON.stringify(parsed!.missingFields)}, so the reader and the route disagree about the payload's own keys`,
    );
  }
});

check("a failed embedding provider is never read as a real one", () => {
  // THE FIX OF 2026-09-10. classifyProvider took only the provider NAME and
  // returned "real" for anything it did not recognise as fake. The route reports
  // `embedding_provider: "unavailable"` with the simulated flag RAISED when it
  // cannot build a provider at all, "unavailable" matched no fake substring, and
  // a hard provider failure rendered as verified semantic distance. It is not an
  // exotic path: start-devon.sh writes DEFAULT_AI_PROVIDER=cerebras, and only
  // mock and openai embed, so a default launch produces exactly this payload.
  const unavailable = parseGraphPayload(scenario("provider_unavailable"))!;
  assert.equal(unavailable.provider, "unavailable", "the fixture is not the unavailable case");
  assert.equal(
    unavailable.counts!.embedding_provider_simulated,
    true,
    "the unavailable payload must arrive with the simulated flag raised",
  );
  assert.equal(
    classifyProvider(unavailable.provider, unavailable.counts!.embedding_provider_simulated),
    "simulated",
    "a provider the route could not build must never read as real",
  );
  // Reading the name alone is the bug, so prove the name alone is not enough.
  assert.notEqual(
    classifyProvider(unavailable.provider, undefined),
    "real",
    "with the flag withheld, an unrecognised provider name must read unknown, never real",
  );

  const real = parseGraphPayload(scenario("provider_real"))!;
  assert.equal(
    classifyProvider(real.provider, real.counts!.embedding_provider_simulated),
    "real",
    "openai with the flag lowered is the one shape allowed to read real",
  );

  const mock = parseGraphPayload(scenario("embedded_no_edges"))!;
  assert.equal(
    classifyProvider(mock.provider, mock.counts!.embedding_provider_simulated),
    "simulated",
    "the mock provider's distances are a real measurement of a fake quantity",
  );

  // The flag outranks the name in BOTH directions, and an unknown name fails
  // closed rather than open.
  assert.equal(classifyProvider("openai", true), "simulated", "the raised flag wins over a real name");
  assert.equal(classifyProvider("fixture-embedder", false), "unknown", "an unrecognised name must not read real");
  assert.equal(classifyProvider("openai", null), "unknown", "a withheld flag cannot certify distances");
  assert.equal(classifyProvider("simulated-v2", false), "simulated", "a name that says fake wins over a lowered flag");
  assert.equal(classifyProvider(null, undefined), "unknown");
});

check("the three cap notices are reachable, not merely parsed", () => {
  // nodes_capped, chunks_truncated and the per edge distance_is_upper_bound were
  // all PARSED into the types and read by nothing, while the type comments
  // claimed they were authoritative. A field with a reader and no renderer is a
  // sentence nobody ever sees.
  const capped = parseGraphPayload(scenario("capped_and_truncated"))!;
  assert.equal(capped.counts!.nodes_capped, true, "the fixture must have node_cap actually biting");
  assert.equal(capped.counts!.chunks_truncated, true, "the fixture must have chunk_cap actually biting");
  assert.ok(
    capped.edges.some((edge) => edge.distanceIsUpperBound === true),
    "no drawn edge carries distanceIsUpperBound, so the per edge ceiling notice cannot fire",
  );

  const notes = describeGaps(capped, sourceOrder(capped.nodes));
  const joined = notes.join(" ");
  for (const required of [
    "capped the node list",
    "capped the edge list",
    "ceilings",
    "upper bound",
  ]) {
    assert.ok(
      joined.includes(required),
      `describeGaps said nothing about ${JSON.stringify(required)} over a payload where it is true. Notes were: ${JSON.stringify(notes)}`,
    );
  }
});

check("the layout claim and the layout move together", () => {
  // The screen reader description said "most connected items pulled inward"
  // unconditionally. The layout DOES do that, through radius = outer * (1 - 0.3 *
  // share), but share is degree over max degree, so it collapses whenever every
  // degree is equal. The commonest such payload is a new corpus with no edges at
  // all, where every mark lands on one ring. For anyone using a screen reader the
  // description IS the picture, so it described a shape that was not there.
  const varying = parseGraphPayload(scenario("drawable_varying_degree"))!;
  assert.ok(varying.edges.length >= 2, "the varying fixture needs at least two edges");
  assert.equal(
    radiusEncodesDegree(varying.nodes),
    true,
    "degrees differ in this payload, so the radius does encode degree and the claim is allowed",
  );

  const flat = parseGraphPayload(scenario("drawable_flat_degree"))!;
  assert.equal(
    radiusEncodesDegree(flat.nodes),
    false,
    "every node has the same degree, so the radius encodes nothing and the claim must be withheld",
  );

  const unembedded = parseGraphPayload(scenario("items_none_embedded"))!;
  assert.equal(
    radiusEncodesDegree(unembedded.nodes),
    false,
    "with no edges every degree is 0, which is the payload the false claim was measured over",
  );
  assert.equal(radiusEncodesDegree([]), false, "nothing is encoded when nothing is placed");

  // And the measurement the WHY note recorded: over a no edge payload the marks
  // really do land on one radius, so the claim would have been false.
  const placed = layoutNodes(unembedded.nodes);
  const radii = new Set(
    placed.map((entry) => Math.round(Math.hypot(entry.x - 160, entry.y - 160) * 100) / 100),
  );
  assert.ok(
    radii.size <= 2,
    `a no edge payload should place every mark on one ring plus the parity stagger, so at most two radii; got ${radii.size}`,
  );

  // AND THE PANEL HAS TO ACTUALLY BRANCH ON IT. Everything above proves the
  // helper is right, which is not the same as the description using it: a correct
  // helper beside an unconditional sentence is the exact shape of the defect this
  // whole arc keeps finding. So read the rendering. Both the screen reader <desc>
  // and the visible paragraph must reference radialDegree, or the claim is fixed
  // in place again.
  const panel = parse("components/mind/KnowledgeGraphPanel.tsx");
  const descs = collect(
    panel,
    (n) =>
      ts.isJsxElement(n) &&
      ts.isIdentifier(n.openingElement.tagName) &&
      n.openingElement.tagName.text === "desc",
  );
  assert.equal(descs.length, 1, `the panel has ${descs.length} <desc> elements; expected exactly one`);
  assert.ok(
    descs[0].getText(panel).includes("radialDegree"),
    "the SVG <desc> does not branch on radialDegree, so it states one layout claim whatever the payload does. For a screen reader that description IS the picture",
  );

  const claims = collect(
    panel,
    (n) => ts.isIdentifier(n) && n.text === "radialDegree",
  );
  assert.ok(
    claims.length >= 3,
    `radialDegree is referenced ${claims.length} times in the panel. It must be computed once and read by BOTH the <desc> and the visible layout paragraph, so a reader and a listener are told the same thing`,
  );
});

check("four kinds of nothing still produce four different messages", () => {
  const seen = new Map<string, string>();
  for (const name of ["empty_corpus", "items_none_embedded", "embedded_no_edges", "drawable_varying_degree"]) {
    const parsed = parseGraphPayload(scenario(name))!;
    const verdict = readGraphVerdict(parsed);
    seen.set(name, verdict.kind);
  }
  assert.equal(seen.get("empty_corpus"), "no-items");
  assert.equal(
    seen.get("items_none_embedded"),
    "no-embeddings",
    "items exist and none carry a vector, so the panel must say nothing is embedded rather than that no pair was close enough. Claiming a comparison over an edge query the route SKIPPED is exactly what got this panel pulled",
  );
  assert.equal(seen.get("embedded_no_edges"), "no-edges");
  assert.equal(seen.get("drawable_varying_degree"), "drawable");
  assert.equal(new Set(seen.values()).size, 4, "two of the four states collapsed onto one verdict");

  // And the headline over the pulled payload must not mention a threshold, since
  // no pair was ever compared against one.
  const unembedded = readGraphVerdict(parseGraphPayload(scenario("items_none_embedded"))!);
  const words = `${(unembedded as { headline?: string }).headline ?? ""} ${(unembedded as { detail?: string }).detail ?? ""}`;
  assert.ok(
    !/threshold|further apart|close enough/i.test(words),
    `the no-embeddings message claims a distance comparison that never ran: ${JSON.stringify(words)}`,
  );
});

check("edge thickness still refuses a scale the route did not supply", () => {
  assert.equal(edgeCloseness(0.3, null), null, "no threshold means no scale");
  assert.equal(edgeCloseness(0.3, 0), null);
  assert.equal(edgeCloseness(0.3, -1), null);
  assert.equal(edgeCloseness(Number.NaN, 0.65), null);
  assert.equal(edgeCloseness(0, 0.65), 1, "touching is 1");
  assert.equal(edgeCloseness(0.65, 0.65), 0, "on the threshold is 0");
  assert.ok((edgeCloseness(1.3, 0.65) ?? -1) === 0, "beyond the threshold clamps rather than going negative");
});

check("the graph layout does not move between two readings of one payload", () => {
  const payload = scenario("drawable_varying_degree");
  const first = layoutNodes(parseGraphPayload(payload)!.nodes);
  const second = layoutNodes(parseGraphPayload(payload)!.nodes);
  assert.deepEqual(first, second, "the same payload drew two different pictures, so two readings cannot be compared");

  // Order independence: the same nodes sent in another order must place the same.
  const parsed = parseGraphPayload(payload)!;
  const reversed = layoutNodes([...parsed.nodes].reverse());
  const byId = new Map(first.map((entry) => [entry.node.id, entry]));
  for (const entry of reversed) {
    const original = byId.get(entry.node.id)!;
    assert.equal(entry.x, original.x, `node ${entry.node.id} moved when the send order changed`);
    assert.equal(entry.y, original.y, `node ${entry.node.id} moved when the send order changed`);
  }
  assert.ok(compareNodes(parsed.nodes[0], parsed.nodes[0]) === 0, "compareNodes is not reflexive");
});

check("only the filtered edge list can draw a line", () => {
  // The adversary's finding of 2026-09-10: it drew a <line> between every pair of
  // placed nodes and NO check noticed, because nothing inspected the SVG at all.
  // An edge with no entry in edges[] is a relationship nobody measured, rendered
  // as though it were one.
  //
  // This runs no browser, so it guards the structure rather than the pixels: every
  // <line> in the panel must be produced by mapping over `shownEdges`, and
  // `shownEdges` must be a FILTER of the parsed edge list. An all pairs mutation
  // has to either add a line outside that map or change how shownEdges is built,
  // and both go red here.
  const panel = parse("components/mind/KnowledgeGraphPanel.tsx");

  const lines = collect(
    panel,
    (n) =>
      (ts.isJsxSelfClosingElement(n) || ts.isJsxOpeningElement(n)) &&
      ts.isIdentifier((n as ts.JsxSelfClosingElement | ts.JsxOpeningElement).tagName) &&
      ((n as ts.JsxSelfClosingElement | ts.JsxOpeningElement).tagName as ts.Identifier).text === "line",
  );
  assert.ok(lines.length > 0, "the panel draws no <line> at all, so it is not drawing edges");

  for (const line of lines) {
    // Walk out to the nearest enclosing .map() call and check what it maps over.
    let at: ts.Node | undefined = line.parent;
    let mapped: string | null = null;
    while (at) {
      if (
        ts.isCallExpression(at) &&
        ts.isPropertyAccessExpression(at.expression) &&
        at.expression.name.text === "map"
      ) {
        mapped = at.expression.expression.getText(panel);
        break;
      }
      at = at.parent;
    }
    const where = panel.getLineAndCharacterOfPosition(line.getStart(panel)).line + 1;
    assert.equal(
      mapped,
      "shownEdges",
      `the <line> at KnowledgeGraphPanel.tsx:${where} is drawn from ${mapped ?? "no map at all"} rather than from shownEdges. A line that does not come from the route's edge list is a relationship nobody measured`,
    );
  }

  // And shownEdges must narrow the edge list, never generate pairs.
  const decls = declarationsNamed(panel, "shownEdges");
  assert.equal(decls.length, 1, `shownEdges is declared ${decls.length} times`);
  const body = decls[0].getText(panel);
  assert.ok(
    body.includes("view.edges"),
    "shownEdges is not derived from view.edges, so what it draws is not what the route returned",
  );
  for (const forbidden of ["flatMap", "for (", "while (", "concat", "push("]) {
    assert.ok(
      !body.includes(forbidden),
      `shownEdges uses ${forbidden}, which can produce pairs the route never sent. It must only narrow view.edges`,
    );
  }
});

check("the knowledge graph panel still reads the graph route", () => {
  const panel = parse("components/mind/KnowledgeGraphPanel.tsx");
  const fetches = callsTo(panel, "fetch");
  assert.ok(fetches.length >= 1, "the graph panel makes no fetch at all, so it draws nothing real");

  const targets = fetches.map((call) => (call.arguments[0] ? call.arguments[0].getText(panel) : ""));
  assert.ok(
    targets.some((text) => text.includes("/knowledge/graph")),
    `the graph panel does not fetch /knowledge/graph. It requests ${JSON.stringify(targets)}, so whatever it draws did not come from the route that measures the edges`,
  );

  // And the read must not be behind a condition this check cannot evaluate: a
  // panel that fetches only when some flag is set draws nothing by default, which
  // is the stranded-surface failure this whole arc closed.
  const graphFetch = fetches.find((call) =>
    call.arguments[0] ? call.arguments[0].getText(panel).includes("/knowledge/graph") : false,
  )!;
  const owner = enclosingDeclarationName(graphFetch);
  assert.ok(owner !== null, "the graph fetch sits in no named declaration, so nothing can be said about who calls it");
});

check("the knowledge graph panel is mounted where a person can reach it", () => {
  // Same shape as the skill gate's mount check, and for the same reason: an
  // imported but unrendered panel is a route nobody can open, and a panel behind
  // an environment flag is worse, because the flag reads as a feature.
  const page = parse("app/control/page.tsx");
  const COMPONENT = "KnowledgeGraphPanel";

  const imported = collect(page, (n) => ts.isImportSpecifier(n) && n.name.text === COMPONENT);
  assert.equal(imported.length, 1, `control/page.tsx must import ${COMPONENT} exactly once; found ${imported.length}`);

  const rendered = collect(page, (n) => {
    if (!ts.isJsxSelfClosingElement(n) && !ts.isJsxOpeningElement(n)) return false;
    const tag = (n as ts.JsxSelfClosingElement | ts.JsxOpeningElement).tagName;
    return ts.isIdentifier(tag) && tag.text === COMPONENT;
  });
  assert.equal(
    rendered.length,
    1,
    `control/page.tsx must render <${COMPONENT} /> exactly once; found ${rendered.length}. An imported but unrendered panel is a measurement nobody can see`,
  );

  const gates = conditionalAncestors(rendered[0], page);
  assert.equal(
    gates.length,
    0,
    `<${COMPONENT} /> is mounted inside ${gates.length} condition(s), so whether the graph is drawn at all depends on a test this check cannot evaluate. The mount has to be unconditional`,
  );
});

console.log(`control-check: ${checks} checks passed`);
