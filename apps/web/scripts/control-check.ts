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
  "components/mind/KnowledgeGraphPanel.tsx",
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
    "components/mind/KnowledgeGraphPanel.tsx",
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
  assert.equal(inputs, 5, "the input count moved; re-check that each one is labelled");
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
  const decideOwner = collect(
    panel,
    (n) =>
      ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === "decide",
  );
  assert.equal(
    decideOwner.length,
    1,
    `${GATE} must declare the decide handler exactly once; found ${decideOwner.length}`,
  );
  const decideGates = conditionalAncestors(decideCalls[0], decideOwner[0]);
  assert.equal(
    decideGates.length,
    0,
    `the decide fetch sits inside ${decideGates.length} condition(s), so whether a ruling ever reaches the API depends on a test this check cannot evaluate. It has to be on the handler's unconditional path`,
  );

  // WHERE THIS CLAUSE STOPS, MEASURED RATHER THAN ASSUMED.
  //
  // The capture guard one screenful up also walks for a `return` before its
  // call, and copying that here was tried and reverted. This handler legitimately
  // returns early when a ruling has already been sent for the same proposal, so
  // the blanket walk went red on correct code at once.
  //
  // The bypass it would have closed is `if (proposal.proposal_id === "") return;`
  // above the fetch, dead for every real proposal. That is structurally IDENTICAL
  // to the already-sent guard the panel needs: both are a conditional return
  // before the call, and telling them apart means evaluating the condition, which
  // a source check cannot do. So it stays open, deliberately, and graded low:
  // exploiting it means writing a guard clause whose test is never true, which is
  // a deliberate act rather than a regression or a copy paste.
  //
  // The reason that is the right call and not laziness: a guard that fails on
  // correct code costs every future contributor an hour and teaches them to
  // distrust the file, and this one would have failed on the panel as shipped.
  // The condition walk above still closes the wrapping form, which is the shape
  // a refactor actually produces.

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
  }

  // 4. All three rulings have to be reachable from the rendered buttons, and
  //    every call site has to name promote. Read off the call sites of the
  //    panel's own handler, so a button wired to nothing fails here.
  const handler = collect(
    panel,
    (n) => ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === "decide",
  );
  assert.equal(
    handler.length,
    1,
    `${GATE} declares the decide handler ${handler.length} times; a second declaration means this check may be reading the wrong one`,
  );
  const rulings = new Set<string>();
  const sites = callsTo(panel, "decide");
  assert.ok(sites.length > 0, "nothing calls the decide handler, so every button is inert");
  for (const site of sites) {
    const arg = site.arguments[1];
    assert.ok(
      arg && ts.isObjectLiteralExpression(arg),
      "a decide call site does not pass a literal ruling this check can read",
    );
    const ruling = arg as ts.ObjectLiteralExpression;
    const approve = propNamed(ruling, "approve");
    const promote = propNamed(ruling, "promote");
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
});

/* the knowledge graph draws measured edges, or names which nothing it is */

/*
 * WHAT THIS GUARDS
 *
 * components/mind/KnowledgePanel.tsx refused to draw a graph until 2026-09-09
 * because no route measured the edges, and its reason was the right one: a graph
 * would have been "a picture of something nobody measured". GET /knowledge/graph
 * measures them now, so the picture is allowed. The obligation is not lifted,
 * and a graph is the worst surface in this estate to lose it on, because a wrong
 * graph still looks like a diagram of something real. A reader cannot tell a
 * cluster of meaning from a cluster of shared vocabulary by looking.
 *
 * So this holds the panel to four things it must keep doing:
 *
 *   1. Read the route. A panel that renders a layout of nothing is the failure
 *      that started this, one step further along.
 *   2. Refuse mock distances. app/core/config.py:239 defaults EMBEDDING_PROVIDER
 *      to mock, and services/intelligence/providers/embeddings.py:11 documents
 *      that provider as hashed bag-of-words, which clusters on shared words and
 *      nothing else. That is the default in every dev and test environment, so
 *      the failure mode is not exotic: it is what the panel shows unless someone
 *      set a key.
 *   3. Count what is absent. An item with no embedding has no vector and cannot
 *      be placed, and a capped edge list is a truncated picture. Both must reach
 *      the reader as a number.
 *   4. Tell four kinds of nothing apart. No items, items with no embeddings,
 *      embeddings with no pair inside the threshold, and a failed request are
 *      four different facts. One blank box for all four is the lie.
 *
 * WHY THE HONEST PARTS ARE PURE FUNCTIONS
 *
 * The same reason readVerdict is one. A critic can mutate a pure function and
 * re-measure it in a second; JSX needs a browser and a payload. So every refusal
 * above lives in components/mind/knowledge-graph.ts and is called here directly,
 * and the last assertion in the route check is the link that matters: the panel
 * must actually CALL each of them, or these tests are guarding dead code while
 * the rendered surface does whatever it likes. That is the shape of the four
 * beaten guards catalogued above this block, and it is the one thing the AST is
 * needed for.
 *
 * WHAT THE AST CANNOT DO HERE
 *
 * The DevonChat guard asserts zero returns before its fetch. This panel needs a
 * signed out early return, so the same assertion would be wrong. This one asserts
 * no return at the TOP LEVEL of the loader body before the fetch, which catches
 * the no-op guard that was used to beat the earlier version while leaving a
 * branch return alone. An attacker willing to write `if (true) return;` beats it,
 * and no static check of an unexecuted file closes that. Stated plainly here
 * rather than implied by silence.
 */

import {
  GRAPH_BOX,
  classifyProvider,
  describeGaps,
  edgeCloseness,
  layoutNodes,
  parseGraphPayload,
  readGraphVerdict,
  sourceOrder,
  type GraphCounts,
  type GraphNode,
  type ParsedGraph,
} from "../components/mind/knowledge-graph.ts";

/** The literal text of a string or a template, or null for anything else. */
function pathText(node: ts.Node): string | null {
  if (ts.isStringLiteral(node) || ts.isNoSubstitutionTemplateLiteral(node)) return node.text;
  if (!ts.isTemplateExpression(node)) return null;
  return node.head.text + node.templateSpans.map((span) => span.literal.text).join("");
}

/**
 * The OUTERMOST `const <name> = ...` a node sits in. Outermost, because the
 * nearest one to a fetch call is the `const response = await fetch(...)` holding
 * its own result, and checking that would tell us nothing about the handler.
 */
function outermostDeclaration(node: ts.Node): ts.VariableDeclaration | null {
  let found: ts.VariableDeclaration | null = null;
  let cursor: ts.Node | undefined = node;
  while (cursor) {
    if (ts.isVariableDeclaration(cursor)) found = cursor;
    cursor = cursor.parent;
  }
  return found;
}

function jsxElementsNamed(root: ts.Node, name: string): ts.Node[] {
  return collect(
    root,
    (n) =>
      (ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n)) &&
      ts.isIdentifier(n.tagName) &&
      n.tagName.text === name,
  );
}

const NO_COUNTS: GraphCounts = {
  items_total: null,
  items_ready: null,
  items_embedded: null,
  items_unembedded: null,
  edges_returned: null,
  edges_capped: null,
};

function countsOf(over: Partial<GraphCounts>): GraphCounts {
  return { ...NO_COUNTS, ...over };
}

function graphOf(over: Partial<ParsedGraph>): ParsedGraph {
  return {
    nodes: [],
    edges: [],
    counts: null,
    maxDistance: 0.6,
    provider: "openai",
    malformedNodes: 0,
    malformedEdges: 0,
    unresolvedEdges: 0,
    selfEdges: 0,
    nodesWithoutDegree: 0,
    missingFields: [],
    ...over,
  };
}

function nodeOf(id: string, over: Partial<GraphNode> = {}): GraphNode {
  return {
    id,
    title: `item ${id}`,
    source: "drive",
    created_at: "2026-09-01T00:00:00+00:00",
    degree: 1,
    ...over,
  };
}

check("the graph panel refuses to present a mock embedding's distances as real", () => {
  // The default in every environment that has not set a key, so this is the
  // common case rather than the edge case.
  for (const name of ["mock", "MOCK", "  mock  ", "mock-v2", "fake", "stub", "simulated", "dummy"]) {
    assert.equal(
      classifyProvider(name),
      "simulated",
      `${name} must be read as simulated, or the panel presents hashed bag-of-words clusters as measured meaning`,
    );
  }
  assert.equal(classifyProvider("openai"), "real");
  // A provider the route did not name is not a provider this panel may vouch for.
  assert.equal(classifyProvider("unknown"), "unknown");
  assert.equal(classifyProvider(""), "unknown");
  assert.equal(classifyProvider(null), "unknown");
  assert.equal(classifyProvider(undefined), "unknown");
});

check("four kinds of nothing produce four different messages", () => {
  const noItems = readGraphVerdict(
    graphOf({ counts: countsOf({ items_total: 0, items_embedded: 0, items_unembedded: 0 }) }),
  );
  const noEmbeddings = readGraphVerdict(
    graphOf({ counts: countsOf({ items_total: 12, items_embedded: 0, items_unembedded: 12 }) }),
  );
  const noEdges = readGraphVerdict(
    graphOf({
      nodes: [nodeOf("a"), nodeOf("b")],
      counts: countsOf({ items_total: 2, items_embedded: 2, items_unembedded: 0 }),
    }),
  );
  const drawable = readGraphVerdict(
    graphOf({
      nodes: [nodeOf("a"), nodeOf("b")],
      edges: [{ source: "a", target: "b", distance: 0.2 }],
      counts: countsOf({ items_total: 2, items_embedded: 2, items_unembedded: 0 }),
    }),
  );

  assert.equal(noItems.kind, "no-items");
  assert.equal(noEmbeddings.kind, "no-embeddings");
  assert.equal(noEdges.kind, "no-edges");
  assert.equal(drawable.kind, "drawable");

  const spoken = [noItems, noEmbeddings, noEdges].map((verdict) =>
    "headline" in verdict ? `${verdict.headline} ${verdict.detail}` : "",
  );
  assert.equal(
    new Set(spoken).size,
    3,
    "two of the empty states print the same words, so a reader cannot tell an empty corpus from an unembedded one",
  );
  for (const message of spoken) {
    assert.ok(
      message.length > 60,
      `an empty state explained in ${message.length} characters is the blank box this check exists to prevent`,
    );
  }
  // Headlines on their own too. A reader scans those and stops, so two states
  // sharing a headline are indistinguishable in practice even when the small
  // print differs. Measured on 2026-09-10: duplicating one headline beat the
  // combined comparison above.
  const headlines = [noItems, noEmbeddings, noEdges].map((verdict) =>
    "headline" in verdict ? verdict.headline : "",
  );
  assert.equal(
    new Set(headlines).size,
    3,
    "two of the empty states share a headline, which is the line a reader actually reads",
  );
  // The fourth is the component's, because only it knows the request failed.
  const panel = parse("components/mind/KnowledgeGraphPanel.tsx");
  const failure = collect(
    panel,
    (n) => ts.isFunctionDeclaration(n) && n.name?.text === "failureDetail",
  );
  assert.equal(failure.length, 1, "the panel has no failureDetail, so a failed read has no message of its own");
  assert.ok(
    callsTo(panel, "failureDetail").length > 0,
    "failureDetail is declared and never called, so a failed read falls through to whatever the empty states say",
  );
});

check("a degraded graph payload is never filled in with invented numbers", () => {
  assert.equal(parseGraphPayload(null), null);
  assert.equal(parseGraphPayload("nodes"), null);
  assert.equal(parseGraphPayload([]), null);

  const bare = parseGraphPayload({});
  assert.ok(bare !== null);
  assert.equal(
    bare.counts,
    null,
    "an absent counts object became a counts object, which puts numbers on screen the route never sent",
  );
  assert.equal(bare.maxDistance, null);
  assert.equal(bare.provider, null);
  assert.deepEqual(bare.missingFields, [
    "nodes",
    "edges",
    "counts",
    "max_distance",
    "embedding_provider",
  ]);

  const partial = parseGraphPayload({ counts: { items_total: 4 } });
  assert.equal(partial?.counts?.items_total, 4);
  assert.equal(
    partial?.counts?.items_embedded,
    null,
    "a missing count read as zero would tell the reader nothing is embedded when the route never said so",
  );

  const dirty = parseGraphPayload({
    nodes: [{ id: "a" }, { id: "a" }, { title: "no id at all" }, { id: "b", degree: 2 }],
    edges: [
      { source: "a", target: "b", distance: 0.1 },
      { source: "a", target: "ghost", distance: 0.2 },
      { source: "a", target: "a", distance: 0 },
      { source: "a", target: "b" },
    ],
  });
  assert.equal(dirty?.nodes.length, 2, "a duplicate or id-less node row was placed anyway");
  assert.equal(dirty?.malformedNodes, 2);
  assert.equal(dirty?.edges.length, 1);
  assert.equal(dirty?.unresolvedEdges, 1, "an edge to a node the route did not send was drawn to somewhere");
  assert.equal(dirty?.selfEdges, 1);
  assert.equal(dirty?.malformedEdges, 1, "an edge with no distance was drawn at a guessed thickness");
  assert.equal(dirty?.nodesWithoutDegree, 1);
});

check("edge thickness refuses a scale the route did not supply", () => {
  assert.equal(
    edgeCloseness(0.2, null),
    null,
    "with no threshold there is nothing to normalise against, and a made up scale makes thickness carry a comparison nobody supplied",
  );
  assert.equal(edgeCloseness(0.2, 0), null);
  assert.equal(edgeCloseness(Number.NaN, 0.5), null);
  assert.equal(edgeCloseness(0, 0.5), 1);
  assert.equal(edgeCloseness(0.5, 0.5), 0);
  assert.equal(edgeCloseness(0.25, 0.5), 0.5);
  assert.equal(edgeCloseness(9, 0.5), 0, "a distance past the threshold must clamp, not go negative");
});

check("the graph layout does not move between two readings of one payload", () => {
  const nodes = [
    nodeOf("c", { degree: 5 }),
    nodeOf("a", { degree: 1, source: "notion" }),
    nodeOf("b", { degree: 3 }),
    nodeOf("d", { degree: null, source: null }),
    nodeOf("e", { degree: 3, created_at: null }),
    // b and f tie on source, degree and created_at, so only the id tiebreak
    // separates them. Without a pair like this the comparator can lose that
    // tiebreak and this check stays green: measured on 2026-09-10, the earlier
    // input had no tie and the mutation survived.
    nodeOf("f", { degree: 3 }),
  ];
  const first = layoutNodes(nodes, GRAPH_BOX);
  const shuffled = layoutNodes([...nodes].reverse(), GRAPH_BOX);
  assert.deepEqual(
    shuffled,
    first,
    "the same nodes in another order drew a different picture, so two readings of one corpus cannot be compared and a screenshot proves nothing",
  );
  assert.deepEqual(layoutNodes(nodes, GRAPH_BOX), first, "two calls on one input disagree");
  assert.equal(first.length, nodes.length, "the layout dropped or duplicated a node");
  for (const placed of first) {
    assert.ok(
      placed.x >= 0 && placed.x <= GRAPH_BOX.width,
      `${placed.node.id} is placed outside the viewBox at x ${placed.x}`,
    );
    assert.ok(
      placed.y >= 0 && placed.y <= GRAPH_BOX.height,
      `${placed.node.id} is placed outside the viewBox at y ${placed.y}`,
    );
    assert.ok(placed.radius > 0 && Number.isFinite(placed.radius), `${placed.node.id} has no drawable radius`);
  }
  // A node whose source the route did not name must not be folded into one that
  // was named, or the legend would count it under a source it never claimed.
  const unsourced = first.find((placed) => placed.node.id === "d");
  assert.ok(unsourced && unsourced.sourceKey !== "drive" && unsourced.sourceKey !== "notion");
});

check("an unembedded item and a capped edge list always reach the reader", () => {
  const partial = graphOf({
    nodes: [nodeOf("a"), nodeOf("b")],
    edges: [{ source: "a", target: "b", distance: 0.1 }],
    counts: countsOf({
      items_total: 10,
      items_embedded: 2,
      items_unembedded: 8,
      edges_returned: 1,
      edges_capped: true,
    }),
  });
  const notes = describeGaps(partial, sourceOrder(partial.nodes));
  assert.ok(
    notes.some((note) => note.includes("8")),
    "eight items with no embedding are absent from the picture and no sentence says so",
  );
  assert.ok(
    notes.some((note) => /truncated/i.test(note)),
    "the route capped the edge list and nothing tells the reader the graph is truncated",
  );

  // The other half of the same guard: a complete payload must not manufacture a
  // warning, or every warning stops being read.
  const clean = graphOf({
    nodes: [nodeOf("a"), nodeOf("b")],
    edges: [{ source: "a", target: "b", distance: 0.1 }],
    counts: countsOf({
      items_total: 2,
      items_ready: 2,
      items_embedded: 2,
      items_unembedded: 0,
      edges_returned: 1,
      edges_capped: false,
    }),
  });
  assert.deepEqual(
    describeGaps(clean, sourceOrder(clean.nodes)),
    [],
    "a complete payload produced a warning, which teaches the reader to ignore the real ones",
  );

  // A route that says nothing must be reported as saying nothing, never as zero.
  const silent = describeGaps(graphOf({ nodes: [nodeOf("a")] }), ["drive"]);
  assert.ok(
    silent.some((note) => /no counts/i.test(note)),
    "a payload with no counts did not say that how much is missing is unknown",
  );
});

check("the knowledge graph panel still reads the graph route", () => {
  const file = parse("components/mind/KnowledgeGraphPanel.tsx");

  const graphFetches = callsTo(file, "fetch").filter((call) => {
    const first = call.arguments[0];
    const text = first ? pathText(first) : null;
    return text !== null && text.endsWith("/knowledge/graph");
  });
  assert.equal(
    graphFetches.length,
    1,
    "the panel must call fetch on a path ending /knowledge/graph exactly once as real code. This check parses the file, so the path inside a comment or a string cannot satisfy it, and an extracted path constant fails here even though the code would work",
  );
  const call = graphFetches[0];

  const declaration = outermostDeclaration(call);
  assert.ok(
    declaration && ts.isIdentifier(declaration.name),
    "the graph fetch is not inside a named declaration this check can resolve",
  );
  const loaderName = (declaration!.name as ts.Identifier).text;
  assert.equal(
    declarationsNamed(file, loaderName).length,
    1,
    `${loaderName} is declared more than once, so a decoy could be read while another one runs`,
  );

  // No unconditional return above the fetch. A signed out branch return is
  // correct and is left alone; a no-op guard at the top of the body is not.
  const arrows = collect(declaration!, (n) => ts.isArrowFunction(n)) as ts.ArrowFunction[];
  const holder = arrows.find((fn) => fn.getStart() <= call.getStart() && fn.getEnd() >= call.getEnd());
  assert.ok(holder && ts.isBlock(holder.body), "the graph fetch is not inside a block bodied function");
  const body = holder!.body as ts.Block;
  const unconditional = collect(body, (n) => ts.isReturnStatement(n)).filter(
    (n) => n.parent === body && n.getStart() < call.getStart(),
  );
  assert.equal(
    unconditional.length,
    0,
    `${loaderName} returns unconditionally before it reaches the graph route, so the panel renders without ever asking for data while every other assertion here still passes`,
  );

  // And something has to run it.
  const wired = callsTo(file, "useEffect").filter((effect) => {
    const first = effect.arguments[0];
    if (!first) return false;
    return collect(first, (n) => ts.isIdentifier(n) && n.text === loaderName).length > 0;
  });
  assert.ok(
    wired.length >= 1,
    `no useEffect references ${loaderName}, so the panel never asks the route for anything and draws whatever its initial state holds`,
  );

  // The link that makes every assertion above matter. A tested refusal the panel
  // does not call is a tested refusal that never runs.
  for (const refusal of [
    "parseGraphPayload",
    "classifyProvider",
    "readGraphVerdict",
    "describeGaps",
    "layoutNodes",
    "edgeCloseness",
  ]) {
    assert.ok(
      callsTo(file, refusal).length > 0,
      `${refusal} is proved above and the panel never calls it, so those assertions guard dead code while the surface does as it likes`,
    );
  }
});

check("the knowledge graph panel is mounted where a person can reach it", () => {
  const page = parse("app/control/page.tsx");

  const shells = jsxElementsNamed(page, "ControlPlane") as Array<
    ts.JsxOpeningElement | ts.JsxSelfClosingElement
  >;
  assert.equal(shells.length, 1, "the control page no longer renders exactly one ControlPlane");

  const carrying = shells[0].attributes.properties
    .filter(ts.isJsxAttribute)
    .filter((attribute) => jsxElementsNamed(attribute, "KnowledgeGraphPanel").length > 0);
  assert.equal(
    carrying.length,
    1,
    "the control page does not hand KnowledgeGraphPanel to ControlPlane in exactly one slot, so the graph renders nowhere a person can see it",
  );
  assert.equal(
    jsxElementsNamed(page, "KnowledgeGraphPanel").length,
    1,
    "there is more than one KnowledgeGraphPanel on the page, so this check cannot tell which one is mounted",
  );
  const slot = carrying[0].name.getText();

  const shell = parse("components/control/ControlPlane.tsx");
  const rendered = collect(
    shell,
    (n) =>
      ts.isJsxExpression(n) &&
      n.expression !== undefined &&
      ts.isIdentifier(n.expression) &&
      n.expression.text === slot,
  );
  assert.ok(
    rendered.length >= 1,
    `ControlPlane takes the ${slot} slot and never renders it, so the graph is mounted into a hole`,
  );

  // The sentence next to it has to stop contradicting it. ControlPlane told the
  // reader that no route exposes vector activations or edges between the
  // indexes, which was true until GET /knowledge/graph landed. A surface with a
  // graph on it and that sentence under it is worse than either alone.
  const stale = collect(
    shell,
    (n) =>
      (ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isJsxText(n)) &&
      /no route exposes vector activations/i.test(n.getText()),
  );
  assert.equal(
    stale.length,
    0,
    "ControlPlane still tells the reader no route exposes vector activations or edges while a graph of them is mounted beside that sentence",
  );
});

console.log(`control-check: ${checks} checks passed`);
