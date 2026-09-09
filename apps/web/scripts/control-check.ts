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
  while (at && at !== stop) {
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

console.log(`control-check: ${checks} checks passed`);
