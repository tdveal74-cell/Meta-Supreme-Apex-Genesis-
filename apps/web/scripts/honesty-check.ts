/**
 * Proof that two surfaces cannot go back to claiming what they do not do. No
 * test framework: node:assert and a plain process exit code, the same shape as
 * scripts/control-check.ts and scripts/presence-check.ts. Run from apps/web:
 *
 *   node --experimental-strip-types scripts/honesty-check.ts
 *
 * WHY THIS FILE EXISTS
 *
 * Two lies shipped on a control plane whose whole job is honesty, and neither
 * had anything guarding it. Both passed typecheck and build, because neither is
 * a type error.
 *
 *   1. CapabilityDock lit a green Scheduler light from a hardcoded
 *      `expansion.scheduler: true` in app/services/agent_tasks.py. Directly
 *      under that light it listed the schedule rows with a run_at and no
 *      task_id and called them the next scheduled goal. Those are the rows
 *      nothing will ever run: materialize_due_schedules has one caller, the
 *      manual route at app/api/v1/agent_expansion.py:87, and the cron the API
 *      image ships drives the workflow dispatcher, which never reads
 *      agent_schedules.
 *   2. The landing page advertised "Workflows with gates" and "gated
 *      workflows". The engine behind that is real, about 2470 lines and ten
 *      routes, and nothing can create a workflow: no page under
 *      apps/web/app, no component calling /workflows, no agent tool. It also
 *      offered document upload and memory you can edit or delete, over a
 *      knowledge panel that only reads and searches.
 *
 * WHY THIS PARSES RATHER THAN GREPS
 *
 * control-check.ts records three text guards beaten in one evening on this
 * repo, and the landing page is the worst case for text: its prose lives in
 * JsxText split across source lines, so any pattern with a space in it misses,
 * and every capability word also appears in the comments that explain the ban.
 * TypeScript is already a dependency because tsc runs in this same job, so
 * these checks ask the real parser. A word in a comment is trivia, not a
 * JsxText node, and no rewrapping changes that.
 *
 * Each check carries its own anti-vacuity assertion. A guard whose extractor
 * silently returns nothing passes everything, which is how a guard ends up
 * failing for reasons entirely its own.
 */

import assert from "node:assert/strict";
import { readdirSync, readFileSync } from "node:fs";
import { dirname, join, relative, sep } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB = join(HERE, "..");

let checks = 0;
function check(name: string, run: () => void): void {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

function parse(relativePath: string): ts.SourceFile {
  const path = join(WEB, relativePath);
  return ts.createSourceFile(
    path,
    readFileSync(path, "utf8"),
    ts.ScriptTarget.Latest,
    true,
    relativePath.endsWith(".tsx") ? ts.ScriptKind.TSX : ts.ScriptKind.TS,
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

/** Every `const <name> = ...` in a subtree. */
function declarationsNamed(root: ts.Node, name: string): ts.VariableDeclaration[] {
  return collect(
    root,
    (n) => ts.isVariableDeclaration(n) && ts.isIdentifier(n.name) && n.name.text === name,
  ) as ts.VariableDeclaration[];
}

/** The property names read anywhere in a subtree, `a?.b.c` included. */
function propertyNames(root: ts.Node): Set<string> {
  const names = new Set<string>();
  for (const node of collect(root, (n) => ts.isPropertyAccessExpression(n))) {
    names.add((node as ts.PropertyAccessExpression).name.text);
  }
  return names;
}

/* ------------------------------------------------------------------ */
/* 1. No capability tile may be lit by a literal                        */
/* ------------------------------------------------------------------ */

/**
 * The dock's grid is an array of [label, lit, detail] tuples mapped to an
 * <Indicator>. The array is found through that <Indicator>, not by name, so a
 * renamed constant or a second decoy array cannot shift what is inspected.
 */
function dockTiles(file: ts.SourceFile): ts.ArrayLiteralExpression[] {
  const indicators = collect(
    file,
    (n) =>
      (ts.isJsxSelfClosingElement(n) || ts.isJsxOpeningElement(n)) &&
      n.tagName.getText() === "Indicator",
  );
  assert.equal(
    indicators.length,
    1,
    `expected exactly one <Indicator> in the dock, found ${indicators.length}; more than one means this check cannot tell which grid it is reading`,
  );

  // Walk out to the .map(...) whose callback renders that Indicator, then take
  // the array it maps over.
  let node: ts.Node = indicators[0];
  let mapCall: ts.CallExpression | null = null;
  while (node.parent) {
    node = node.parent;
    if (
      ts.isCallExpression(node) &&
      ts.isPropertyAccessExpression(node.expression) &&
      node.expression.name.text === "map"
    ) {
      mapCall = node;
      break;
    }
  }
  assert.ok(mapCall, "the <Indicator> is not rendered inside a .map(...) this check can read");
  const source = (mapCall.expression as ts.PropertyAccessExpression).expression;
  assert.ok(
    ts.isArrayLiteralExpression(source),
    "the tile grid is no longer a literal array of tuples, so this check cannot read the tiles one by one",
  );
  const tiles = source.elements.filter((e) => ts.isArrayLiteralExpression(e)) as ts.ArrayLiteralExpression[];
  assert.equal(
    tiles.length,
    source.elements.length,
    "at least one tile is not an array literal, so its lit value cannot be inspected",
  );
  return tiles;
}

check("no capability tile in the dock is lit by a hardcoded true", () => {
  const file = parse("components/command-center/CapabilityDock.tsx");
  const tiles = dockTiles(file);

  // Anti-vacuity: the grid is eight tiles today and every tile is a triple. A
  // grid this check read as empty would pass every assertion below it.
  assert.ok(tiles.length >= 6, `only ${tiles.length} tiles found; the grid cannot have shrunk that far`);

  for (const tile of tiles) {
    assert.equal(tile.elements.length, 3, "a tile is not a [label, lit, detail] triple");
    const label = tile.elements[0];
    const lit = tile.elements[1];
    const name = ts.isStringLiteral(label) ? label.text : label.getText();
    assert.notEqual(
      lit.kind,
      ts.SyntaxKind.TrueKeyword,
      `the ${name} tile is lit by the literal true. A control plane indicator has to read state; a literal is a green light nothing can turn off, which is exactly how the Scheduler light stood over goals that never run`,
    );
  }
});

check("the Scheduler tile is lit by whether goals run, not by whether they are recorded", () => {
  const file = parse("components/command-center/CapabilityDock.tsx");
  const scheduler = dockTiles(file).find((tile) => {
    const label = tile.elements[0];
    return ts.isStringLiteral(label) && label.text === "Scheduler";
  });
  assert.ok(scheduler, 'no tile is labelled "Scheduler"; this check has nothing to inspect');

  // The lit value may be an expression or an identifier standing for one.
  // Resolve an identifier to its single declaration so the real expression is
  // what gets read.
  let lit: ts.Node = scheduler.elements[1];
  if (ts.isIdentifier(lit)) {
    const decls = declarationsNamed(file, lit.text);
    assert.equal(
      decls.length,
      1,
      `${lit.text} is declared ${decls.length} times; a second declaration means this check may be reading the wrong one`,
    );
    assert.ok(decls[0].initializer, `${lit.text} has no initialiser to read`);
    lit = decls[0].initializer;
  }

  const names = propertyNames(lit);
  assert.ok(
    names.has("runs_goals"),
    "the Scheduler light does not read scheduler_status.runs_goals. Recording a goal and running one are separate capabilities in GET /agent-tasks/tools, and lighting this from the recorder is the original lie",
  );
  assert.ok(
    !names.has("scheduler"),
    "the Scheduler light reads expansion.scheduler again. That key is a plain flag kept false so a stale reader fails safe; reading it back here reintroduces a light that cannot distinguish recorded from running",
  );
});

check("the recorded goal panel carries the runner reason from the matrix", () => {
  const file = parse("components/command-center/CapabilityDock.tsx");

  // Renaming this constant means updating this check. That is deliberate: the
  // note is the one sentence telling Tee the queued goals are inert.
  const decls = declarationsNamed(file, "schedulerNote");
  assert.equal(decls.length, 1, "schedulerNote is not declared exactly once");
  assert.ok(decls[0].initializer, "schedulerNote has no initialiser");
  assert.ok(
    propertyNames(decls[0].initializer).has("scheduler_status"),
    "schedulerNote does not read scheduler_status, so the reason shown under the queued goals is not the runner's own answer",
  );

  const rendered = collect(
    file,
    (n) => ts.isJsxExpression(n) && !!n.expression && ts.isIdentifier(n.expression) && n.expression.text === "schedulerNote",
  );
  assert.ok(
    rendered.length >= 1,
    "schedulerNote is computed and never rendered, so the panel states the goals are queued and says nothing about whether anything runs them",
  );
});

/* ------------------------------------------------------------------ */
/* 2. The landing page may only name what a visitor can reach           */
/* ------------------------------------------------------------------ */

/**
 * Every string a visitor could read: string literals, template literal pieces,
 * and JSX text. Comments are trivia and are deliberately excluded, because the
 * comments on the landing page name the banned capabilities in order to explain
 * the ban.
 */
function visibleText(root: ts.Node): string[] {
  const nodes = collect(
    root,
    (n) =>
      ts.isStringLiteral(n) ||
      ts.isNoSubstitutionTemplateLiteral(n) ||
      ts.isTemplateHead(n) ||
      ts.isTemplateMiddle(n) ||
      ts.isTemplateTail(n) ||
      ts.isJsxText(n),
  );
  return nodes.map((n) => (n as ts.LiteralLikeNode).text ?? "");
}

/**
 * The files that can constitute a surface a visitor reaches: routes, the
 * components they mount, and the helpers those call. Build config and the
 * scripts directory are excluded, and that exclusion is load bearing rather
 * than tidiness.
 *
 * Measured on 2026-09-10 while proving this check could fail: with scripts/ in
 * scope, the CLAIMS table below put the literals "/workflows" and "/memory" in
 * scope as string literals of this very file, every claim read as reachable,
 * and the check passed with "gated workflows" restored to the hero. A guard
 * that reads its own needles certifies itself. The negative control caught it;
 * review had not.
 */
function webSources(): string[] {
  const roots = ["app", "components", "lib"];
  const skip = new Set(["node_modules", ".next", "out", "dist"]);
  const found: string[] = [];
  for (const entry of readdirSync(WEB, { recursive: true, withFileTypes: true })) {
    const parentPath = (entry as unknown as { parentPath?: string; path?: string }).parentPath ??
      (entry as unknown as { path: string }).path;
    const rel = relative(WEB, join(parentPath, entry.name));
    const parts = rel.split(sep);
    if (parts.some((part) => skip.has(part))) continue;
    if (!roots.includes(parts[0])) continue;
    if (!entry.isFile()) continue;
    if (!rel.endsWith(".ts") && !rel.endsWith(".tsx")) continue;
    found.push(rel);
  }
  return found;
}

/**
 * A capability the landing page may name only while some component under
 * apps/web actually calls the path behind it.
 *
 * The surface side is deliberately strict: a path assembled by concatenation
 * reads as absent, which forbids the claim. Erring that way costs a sentence on
 * a landing page; erring the other way is how "Workflows with gates" sat over
 * an engine nothing can reach.
 */
const CLAIMS = [
  {
    word: /workflow/i,
    needs: "/workflows",
    why: "components/control/WorkflowDoor.tsx is the caller: it composes through POST /workflows, starts runs, reads run history and rules on the approval gate, mounted at /control and /control/workflows. If this fires again, that panel was removed and the engine has no way to be reached",
  },
  {
    word: /\bmemor(y|ies)\b/i,
    needs: "/memory",
    why: "components/mind/MemoryPanel.tsx is the caller: GET /memory to read, POST to write, PATCH to edit and pause, DELETE to destroy, mounted at /control and /control/memory. If this fires again, that panel was removed and the Council is storing memories nobody can read",
  },
  {
    // Added 2026-09-10. The Decision Intelligence pillar claimed the site would
    // "record the human final call so future decisions stay accountable", and the
    // three checks above all passed over it: this list held only workflow and
    // memory. The claim is the same shape as the other two and was missed for the
    // same reason, so the list grows rather than the instance being patched.
    //
    // Unlike the other two, the API side EXISTS: app/api/v1/decisions.py is
    // registered at app/api/v1/router.py:50. What is missing is any caller. The
    // only handler on the surface, handleDecision in
    // app/council/deliberate/page.tsx, is a console.info, so a visitor's ruling
    // lives in React state until they reload.
    // Narrowed on first run, and the reason is worth keeping. The first version
    // also matched keep|keeps|log|logs|store|stores, and it fired on the hero
    // line "Keep the final call human." That sentence is TRUE and it is the
    // estate's whole posture: the human decides. Banning it would have been the
    // guard forcing a lie of omission. So the verbs here are only the ones that
    // unambiguously mean "this is written down somewhere it can be read back".
    word: /\b(record|records|recorded|recording|persist|persists|persisted|save|saves|saved)\b[^.]{0,80}\b(decision|decisions|final call)\b/i,
    needs: "/decisions",
    why: "components/council/DecisionRecordPanel.tsx is the caller: GET /decisions, GET and PATCH /decisions/{id}, POST /decisions/from-message, mounted at /control and /control/decisions, and the deliberate page POSTs a decision then PATCHes the ruling onto it. If this fires again, a ruling made on this site lives in one browser tab",
  },
];

/**
 * The page is allowed to say a capability has no surface here. A word ban
 * cannot tell a claim from a disclaimer, so the disclaimers are named, exactly,
 * one sentence each, and removed from the prose before the ban applies.
 *
 * The shape is borrowed from test_devon_receipt_shape.py: an exemption list of
 * exact text, not a rule with a clever exception, so adding one is a decision
 * somebody made in this file rather than a pattern that quietly widened. The
 * second assertion below keeps it from rotting: an exemption the page no longer
 * carries has to come out.
 */
const DISCLAIMERS: string[] = [
  // EMPTY ON PURPOSE, since 2026-09-10, and empty is the healthy state.
  //
  // Two sentences lived here for part of that day. Both were the page saying
  // "we do not do this" about a real subsystem with no caller, and both were
  // deleted from the page when the caller shipped:
  //
  //   "Ingestion and long-term memory are API side and have no page here yet."
  //   -> MemoryPanel.tsx now reads GET /memory and writes, edits, pauses and
  //      hard deletes through the other three routes. The pillar names that,
  //      and it still disclaims INGESTION, which is still true and which no
  //      CLAIMS entry bans, so it needs no exemption.
  //
  //   "Recording the final call is an API route with no page here yet, so
  //    nothing on this site persists a decision."
  //   -> DecisionRecordPanel.tsx and the deliberate page now call the decision
  //      routes, so the pillar makes the claim instead of disclaiming it.
  //
  // The loop below is a no-op while this list is empty, which is correct: a
  // page that disclaims nothing needs no exemption. The CLAIMS entries above
  // are what hold the line now, and they pass by being SATISFIED rather than
  // by being exempted, which is the stronger of the two.
];

check("the landing page names no capability a visitor cannot reach", () => {
  const LANDING = join("app", "page.tsx");
  const raw = visibleText(parse(LANDING)).join(" ").replace(/\s+/g, " ");

  // Anti-vacuity. If the extractor ever returns nothing, every claim below
  // passes and this file would certify a page it never read.
  assert.ok(
    raw.includes("Amplify judgment"),
    "the landing page prose could not be read: the extractor did not find the headline, so nothing below it proves anything",
  );

  let prose = raw;
  for (const sentence of DISCLAIMERS) {
    assert.ok(
      raw.includes(sentence),
      `the disclaimer "${sentence}" is exempted here and the page no longer carries it. Drop it from DISCLAIMERS; a stale exemption is a hole nobody is watching`,
    );
    prose = prose.split(sentence).join(" ");
  }

  const sources = webSources().filter((rel) => rel !== LANDING);
  assert.ok(sources.length > 20, `only ${sources.length} web sources found; the surface scan cannot be trusted`);
  const surfaceText = sources.flatMap((rel) => visibleText(parse(rel)));

  for (const claim of CLAIMS) {
    const reachable = surfaceText.some((text) => text.includes(claim.needs));
    if (reachable) continue;
    const hit = claim.word.exec(prose);
    assert.equal(
      hit,
      null,
      `the landing page says "${hit?.[0]}" while nothing under apps/web calls ${claim.needs}: ${claim.why}. Either ship the surface or drop the claim`,
    );
  }
});

console.log(`\n${checks} honesty checks passed`);
