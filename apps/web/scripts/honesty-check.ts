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
 *   3. Added 2026-09-15. The Soul tile rendered a failed read of
 *      GET /soul/status as "recall off", the same words the route uses when
 *      it answers enabled: false, and threw away the route's own detail,
 *      which names the two variables that turn recall on. Nothing on the
 *      panel said which host it reads. A diagnostic went to the devon-soul
 *      Vercel project on that basis while the dock reads API_BASE on
 *      Railway, whose environment carried none of the variables. The first
 *      guard for this was itself beaten eleven times in one afternoon by a
 *      critic; section 1b records what replaced it.
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
/* 1b. Everything the dock says about soul derives from one value       */
/* ------------------------------------------------------------------ */

/**
 * Added 2026-09-15 and rewritten the same day. The first version pinned the
 * shape of one ternary in the Soul tile and the presence of three identifiers,
 * and a critic got eleven of twelve lying edits past it while it stayed green:
 * the on and off arms swapped, the failure branch of the status read storing
 * { enabled: false } instead of null so a 401 rendered as "recall off", API_BASE
 * read in a dead branch of apiHost, the route's detail read and then
 * overwritten, the note rendered under a hidden attribute, the light keyed on
 * tee_host_configured. Every one of those left the pinned ternary intact.
 *
 * So the dock now derives every Soul statement from ONE value, soulState, and
 * the checks below pin that value's expression exactly, pin that the status
 * object is read in exactly two places, pin what is allowed to feed it, and
 * pin the words as data rather than as a ternary anyone can reorder. The DOM
 * level check is scripts/dock-smoke.mjs, which reads the rendered words off a
 * real page with a real token and with a refused one, and cannot be edited
 * around; these are the fast checks that name the edit.
 */

const DOCK = "components/command-center/CapabilityDock.tsx";

function unparen(node: ts.Node): ts.Node {
  while (ts.isParenthesizedExpression(node)) node = node.expression;
  return node;
}

function isIdent(node: ts.Node, name: string): boolean {
  return ts.isIdentifier(node) && node.text === name;
}

function isStr(node: ts.Node, text: string): boolean {
  return ts.isStringLiteral(node) && node.text === text;
}

/** `object.name` or `object?.name`, with `object` a bare identifier. */
function isPropOf(node: ts.Node, object: string, name: string): boolean {
  return (
    ts.isPropertyAccessExpression(node) && isIdent(node.expression, object) && node.name.text === name
  );
}

/** `left === "text"` */
function isEqualsString(node: ts.Node, left: string, text: string): boolean {
  const n = unparen(node);
  return (
    ts.isBinaryExpression(n) &&
    n.operatorToken.kind === ts.SyntaxKind.EqualsEqualsEqualsToken &&
    isIdent(unparen(n.left), left) &&
    isStr(unparen(n.right), text)
  );
}

function within(node: ts.Node, root: ts.Node): boolean {
  return node.pos >= root.pos && node.end <= root.end;
}

/** Every way a name can be bound: a const, a parameter, a destructuring, a function, a catch, an import. */
function bindingsNamed(root: ts.Node, name: string): ts.Node[] {
  return collect(
    root,
    (n) =>
      ((ts.isVariableDeclaration(n) || ts.isParameter(n) || ts.isBindingElement(n) || ts.isFunctionDeclaration(n) || ts.isImportSpecifier(n)) &&
        !!n.name &&
        ts.isIdentifier(n.name) &&
        n.name.text === name) ||
      (ts.isCatchClause(n) && !!n.variableDeclaration && ts.isIdentifier(n.variableDeclaration.name) && n.variableDeclaration.name.text === name),
  );
}

function onlyDeclaration(file: ts.SourceFile, name: string): ts.VariableDeclaration {
  // Bound once in the whole file, in any form. The second critic shadowed
  // soulState with an arrow parameter around the tile grid and the first
  // version of this helper, which counted const declarations only, never saw it.
  const bindings = bindingsNamed(file, name);
  assert.equal(
    bindings.length,
    1,
    `${name} is bound ${bindings.length} time(s) in the dock, counting parameters, destructurings, functions, catches and imports. It may be bound once, as a const, and this check pins it by name on purpose: renaming it means updating this check`,
  );
  const decl = bindings[0];
  assert.ok(ts.isVariableDeclaration(decl), `${name} is bound as something other than a const declaration`);
  assert.ok(decl.initializer, `${name} has no initialiser`);
  return decl;
}

check("the status object is bound once and read in exactly two places: enabled for the state, detail for the note", () => {
  const file = parse(DOCK);

  // One binding, the useState pair, so nothing can shadow `soul` with a
  // literal and feed the state from it.
  const bindings = bindingsNamed(file, "soul");
  assert.equal(bindings.length, 1, `the name soul is bound ${bindings.length} time(s); it may be bound once, by useState`);
  assert.ok(ts.isBindingElement(bindings[0]) && ts.isArrayBindingPattern(bindings[0].parent), "soul is not bound by an array destructuring of useState");

  const reads = collect(
    file,
    (n) => ts.isPropertyAccessExpression(n) && isIdent(n.expression, "soul"),
  ) as ts.PropertyAccessExpression[];
  const names = reads.map((r) => r.name.text);
  assert.deepEqual(
    [...names].sort(),
    ["detail", "enabled"],
    `the dock reads ${JSON.stringify(names)} off the status object. It may read enabled once, in soulState, and detail once, in soulNote, and nothing else: a light keyed on tee_host_configured lit green while recall was off and the first version of this check passed it`,
  );
  const soulState = onlyDeclaration(file, "soulState");
  const soulNote = onlyDeclaration(file, "soulNote");
  const enabledRead = reads.find((r) => r.name.text === "enabled") as ts.PropertyAccessExpression;
  const detailRead = reads.find((r) => r.name.text === "detail") as ts.PropertyAccessExpression;
  assert.ok(within(enabledRead, soulState.initializer as ts.Node), "enabled is read somewhere other than soulState's initialiser");
  assert.ok(within(detailRead, soulNote.initializer as ts.Node), "detail is read somewhere other than soulNote's initialiser");
});

check("soulState is one three way read: unread when the route did not answer, then on or off by enabled", () => {
  const file = parse(DOCK);
  const decl = onlyDeclaration(file, "soulState");
  const outer = unparen(decl.initializer as ts.Node);
  assert.ok(ts.isConditionalExpression(outer), "soulState is not a conditional expression");
  const cond = unparen(outer.condition);
  assert.ok(
    ts.isPrefixUnaryExpression(cond) &&
      cond.operator === ts.SyntaxKind.ExclamationToken &&
      isIdent(unparen(cond.operand), "soul"),
    "soulState does not test !soul first, so a status the dock never read is not a state of its own and a 401 renders as off",
  );
  assert.ok(isStr(unparen(outer.whenTrue), "unread"), 'soulState\'s null arm is not "unread"');
  const inner = unparen(outer.whenFalse);
  assert.ok(ts.isConditionalExpression(inner), "soulState's read arm is not itself a conditional on enabled");
  assert.ok(
    isPropOf(unparen(inner.condition), "soul", "enabled"),
    "soulState's read arm does not test soul.enabled, unnegated and alone",
  );
  assert.ok(
    isStr(unparen(inner.whenTrue), "on") && isStr(unparen(inner.whenFalse), "off"),
    'soulState\'s arms are not "on" for enabled and "off" otherwise, in that order',
  );
});

check("the light, the tile, the mesh count and the panel header all derive from soulState", () => {
  const file = parse(DOCK);

  const tile = dockTiles(file).find((t) => ts.isStringLiteral(t.elements[0]) && t.elements[0].text === "Soul");
  assert.ok(tile, 'no tile is labelled "Soul"; this check has nothing to inspect');
  assert.ok(isEqualsString(tile.elements[1], "soulState", "on"), 'the Soul light is not soulState === "on"');
  const detail = unparen(tile.elements[2]);
  assert.ok(
    ts.isElementAccessExpression(detail) &&
      isIdent(detail.expression, "SOUL_TILE_DETAIL") &&
      isIdent(unparen(detail.argumentExpression), "soulState"),
    "the Soul tile detail is not SOUL_TILE_DETAIL[soulState]",
  );

  // The words, pinned as data. A ternary can be reordered and still carry
  // every word; a map with three fixed keys cannot say "recall on" for off.
  const map = onlyDeclaration(file, "SOUL_TILE_DETAIL");
  const obj = unparen(map.initializer as ts.Node);
  assert.ok(ts.isObjectLiteralExpression(obj), "SOUL_TILE_DETAIL is not an object literal");
  const entries: Record<string, string> = {};
  for (const prop of obj.properties) {
    assert.ok(ts.isPropertyAssignment(prop), "SOUL_TILE_DETAIL carries something other than key: value");
    const key = ts.isIdentifier(prop.name) || ts.isStringLiteral(prop.name) ? prop.name.text : "?";
    entries[key] = ts.isStringLiteral(prop.initializer) ? prop.initializer.text : "?";
  }
  assert.deepEqual(
    entries,
    { on: "recall on", off: "recall off", unread: "status unread" },
    "SOUL_TILE_DETAIL no longer maps the three states to their three words",
  );
  const writes = collect(
    file,
    (n) =>
      ts.isBinaryExpression(n) &&
      n.operatorToken.kind === ts.SyntaxKind.EqualsToken &&
      collect(n.left, (m) => isIdent(m, "SOUL_TILE_DETAIL")).length > 0,
  );
  assert.equal(writes.length, 0, "SOUL_TILE_DETAIL is written to after its declaration");

  // The mesh count reads the derived state exactly once inside its callback,
  // the object never, and names soulState in its dependency list, or the
  // count would sit stale while the tile moved.
  const count = onlyDeclaration(file, "activeCount");
  const memo = unparen(count.initializer as ts.Node);
  assert.ok(
    ts.isCallExpression(memo) && isIdent(memo.expression, "useMemo") && memo.arguments.length === 2,
    "activeCount is not a useMemo(callback, deps)",
  );
  const [countBody, countDeps] = memo.arguments;
  assert.equal(
    collect(countBody, (n) => isEqualsString(n, "soulState", "on")).length,
    1,
    'activeCount does not count soulState === "on" exactly once',
  );
  assert.equal(collect(countBody, (n) => isIdent(n, "soulState")).length, 1, "activeCount reads soulState more than once inside its callback");
  assert.equal(collect(countBody, (n) => isIdent(n, "soul")).length, 0, "activeCount reads the status object directly instead of soulState");
  assert.ok(
    ts.isArrayLiteralExpression(countDeps) && countDeps.elements.some((e) => isIdent(e, "soulState")),
    "activeCount's dependency list does not name soulState, so the count would not move when the tile does",
  );

  // The panel header, found from its own label. JsxText -> span -> the row.
  const labels = collect(file, (n) => ts.isJsxText(n) && n.text.trim() === "Soul recall");
  assert.equal(labels.length, 1, 'the "Soul recall" panel label is not rendered exactly once');
  const row = labels[0].parent.parent;
  const exprs = collect(row, (n) => ts.isJsxExpression(n) && !!n.expression) as ts.JsxExpression[];
  assert.equal(exprs.length, 1, "the Soul recall header row carries more than one expression");
  const call = unparen(exprs[0].expression as ts.Node);
  assert.ok(
    ts.isCallExpression(call) && isPropOf(call.expression, "soulState", "toUpperCase"),
    "the Soul recall header is not soulState.toUpperCase(), so it can say OFF over a note that says unread",
  );
});

check("what feeds soulState: the status slot starts null and only ever holds the route's parsed answer or null", () => {
  const file = parse(DOCK);
  const slot = collect(
    file,
    (n) =>
      ts.isVariableDeclaration(n) &&
      ts.isArrayBindingPattern(n.name) &&
      n.name.elements.some((e) => ts.isBindingElement(e) && isIdent(e.name, "setSoul")),
  ) as ts.VariableDeclaration[];
  assert.equal(slot.length, 1, "the [soul, setSoul] state is not declared exactly once");
  const init = unparen(slot[0].initializer as ts.Node);
  assert.ok(
    ts.isCallExpression(init) &&
      isIdent(init.expression, "useState") &&
      init.arguments.length === 1 &&
      init.arguments[0].kind === ts.SyntaxKind.NullKeyword,
    "the soul state does not start as useState(null)",
  );

  const calls = collect(file, (n) => ts.isCallExpression(n) && isIdent(n.expression, "setSoul")) as ts.CallExpression[];
  let nulls = 0;
  let answers: ts.CallExpression[] = [];
  for (const call of calls) {
    assert.equal(call.arguments.length, 1, "setSoul is called with other than one argument");
    let arg = unparen(call.arguments[0]);
    if (arg.kind === ts.SyntaxKind.NullKeyword) {
      nulls += 1;
      continue;
    }
    // (await soulResult.value.json()) as SoulStatus, and nothing looser: a
    // failure branch storing { enabled: false } renders a 401 as "recall off",
    // which is the lie this tile existed to remove, and `soulResult && FALLBACK`
    // mentions the result while storing something else.
    if (ts.isAsExpression(arg)) arg = unparen(arg.expression);
    assert.ok(ts.isAwaitExpression(arg), `setSoul is handed ${call.arguments[0].getText().slice(0, 60)}, which is neither null nor the awaited answer`);
    const parsed = unparen(arg.expression);
    assert.ok(
      ts.isCallExpression(parsed) &&
        parsed.arguments.length === 0 &&
        ts.isPropertyAccessExpression(parsed.expression) &&
        parsed.expression.name.text === "json" &&
        isPropOf(unparen(parsed.expression.expression), "soulResult", "value"),
      `setSoul is handed ${call.arguments[0].getText().slice(0, 60)}, not soulResult.value.json()`,
    );
    answers.push(call);
  }
  assert.ok(nulls >= 1, "setSoul never stores null, so a failed read has no state of its own");
  assert.equal(answers.length, 1, `setSoul stores the route's answer ${answers.length} time(s); expected exactly one`);

  // And the answer is stored only when the response was ok. Storing a 401's
  // body parses {"detail": "Not authenticated"} into a status with no enabled,
  // which soulState would read as off.
  let node: ts.Node = answers[0];
  let guard: ts.IfStatement | null = null;
  while (node.parent) {
    node = node.parent;
    if (ts.isIfStatement(node)) {
      guard = node;
      break;
    }
  }
  assert.ok(guard, "the answer is stored outside any if statement");
  // Exact shape: `soulResult.status === "fulfilled" && soulResult.value.ok`
  // and no other operand. A count of parts was satisfied by `|| status === 401`.
  const condition = unparen(guard.expression);
  const okRead = (n: ts.Node) =>
    ts.isPropertyAccessExpression(n) && n.name.text === "ok" && isPropOf(unparen(n.expression), "soulResult", "value");
  const fulfilled = (n: ts.Node) => {
    const b = unparen(n);
    return (
      ts.isBinaryExpression(b) &&
      b.operatorToken.kind === ts.SyntaxKind.EqualsEqualsEqualsToken &&
      isPropOf(unparen(b.left), "soulResult", "status") &&
      isStr(unparen(b.right), "fulfilled")
    );
  };
  assert.ok(
    ts.isBinaryExpression(condition) &&
      condition.operatorToken.kind === ts.SyntaxKind.AmpersandAmpersandToken &&
      fulfilled(condition.left) &&
      okRead(unparen(condition.right)),
    'the answer is stored under a condition other than exactly `soulResult.status === "fulfilled" && soulResult.value.ok`',
  );
  assert.ok(within(answers[0], guard.thenStatement), "the answer is stored in the else branch of the ok test");
  assert.ok(
    guard.elseStatement && collect(guard.elseStatement, (n) => ts.isCallExpression(n) && isIdent(n.expression, "setSoul") && n.arguments[0]?.kind === ts.SyntaxKind.NullKeyword).length === 1,
    "the failure branch of the status read does not store null",
  );
});

check("soulNote reads the route's detail, names the host it read in the off branch, and is rendered in plain sight", () => {
  const file = parse(DOCK);
  const note = onlyDeclaration(file, "soulNote");
  const body = note.initializer as ts.Node;

  // detail is `soul?.detail || <fallback>`. Read then discarded was one of the
  // critic's passes.
  const detailDecls = declarationsNamed(body, "detail");
  assert.equal(detailDecls.length, 1, "soulNote does not declare detail exactly once");
  const dinit = unparen(detailDecls[0].initializer as ts.Node);
  assert.ok(
    ts.isBinaryExpression(dinit) &&
      dinit.operatorToken.kind === ts.SyntaxKind.BarBarToken &&
      isPropOf(unparen(dinit.left), "soul", "detail"),
    "detail is not `soul?.detail || <fallback>`, so the sentence under the tiles is the dock's own words rather than the route's",
  );

  // Each branch keyed on soulState, each returning a template that carries
  // what that branch owes the reader.
  const spans = (node: ts.Node) =>
    new Set(collect(node, (n) => ts.isTemplateSpan(n)).map((s) => unparen((s as ts.TemplateSpan).expression).getText()));
  const branch = (test: (c: ts.Node) => boolean, what: string) => {
    const ifs = collect(body, (n) => ts.isIfStatement(n) && test(unparen(n.expression))) as ts.IfStatement[];
    assert.equal(ifs.length, 1, `soulNote's ${what} branch is missing or duplicated`);
    const returns = collect(ifs[0].thenStatement, (n) => ts.isReturnStatement(n)) as ts.ReturnStatement[];
    assert.equal(returns.length, 1, `soulNote's ${what} branch does not return exactly once`);
    return returns[0];
  };
  const unread = branch((c) => isEqualsString(c, "soulState", "unread"), "unread");
  assert.ok(spans(unread).has("apiHost") && /unread/.test(unread.getText()), "the unread branch does not say unread and name apiHost");
  const on = branch((c) => isEqualsString(c, "soulState", "on"), "on");
  assert.ok(spans(on).has("detail"), "the on branch does not carry the route's detail");
  const returns = collect(body, (n) => ts.isReturnStatement(n)) as ts.ReturnStatement[];
  const off = returns[returns.length - 1];
  assert.ok(
    spans(off).has("detail") && spans(off).has("apiHost"),
    "the off branch, the final return, does not carry both the route's detail and apiHost, so a reader is not told which host's environment the variables belong to",
  );
  assert.equal(
    collect(body, (n) => (ts.isStringLiteral(n) || ts.isTemplateLiteralToken(n)) && /vercel/i.test(n.text)).length,
    0,
    "soulNote names a Vercel host; the dock reads API_BASE and nothing else",
  );

  // Rendered exactly once, under a plain className, inside the Soul recall
  // panel. innerText in dock-smoke.mjs is the check a hidden element cannot
  // pass either way; this names the edit.
  const rendered = collect(
    file,
    (n) => ts.isJsxExpression(n) && !!n.expression && isIdent(n.expression, "soulNote"),
  ) as ts.JsxExpression[];
  assert.equal(rendered.length, 1, "soulNote is not rendered exactly once");
  const element = rendered[0].parent;
  assert.ok(ts.isJsxElement(element), "soulNote is not the child of a JSX element");
  const attrs = element.openingElement.attributes.properties;
  assert.equal(attrs.length, 2, "the element rendering soulNote carries attributes besides its marker and className");
  const marker = attrs.find((a) => ts.isJsxAttribute(a) && a.name.getText() === "data-soul-note") as ts.JsxAttribute | undefined;
  assert.ok(marker && !!marker.initializer && ts.isStringLiteral(marker.initializer) && marker.initializer.text === "text", 'the note element is not marked data-soul-note="text"');
  const attr = attrs.find((a) => ts.isJsxAttribute(a) && a.name.getText() === "className") as ts.JsxAttribute | undefined;
  assert.ok(
    !!attr && !!attr.initializer && ts.isStringLiteral(attr.initializer),
    "the element rendering soulNote does not carry a literal className",
  );
  const classes = (attr.initializer as ts.StringLiteral).text.split(/\s+/);
  for (const hidden of ["hidden", "sr-only", "invisible", "opacity-0", "h-0", "w-0", "text-[0", "collapse"]) {
    assert.ok(!classes.some((c) => c === hidden || c.startsWith(`${hidden}`)), `soulNote is rendered under a ${hidden} class`);
  }
  const label = collect(file, (n) => ts.isJsxText(n) && n.text.trim() === "Soul recall")[0];
  const panel = label.parent.parent.parent;
  assert.ok(within(rendered[0], panel), "soulNote is not rendered inside the Soul recall panel");
});

check("apiHost is the host of API_BASE and nothing else", () => {
  const file = parse(DOCK);
  const host = onlyDeclaration(file, "apiHost");
  const init = host.initializer as ts.Node;
  assert.equal(
    collect(init, (n) => ts.isStringLiteral(n) || ts.isNoSubstitutionTemplateLiteral(n) || ts.isTemplateExpression(n)).length,
    0,
    "apiHost's initialiser carries a string literal, so the note can name a host the dock never reads",
  );
  const urls = collect(init, (n) => ts.isNewExpression(n) && isIdent(n.expression, "URL")) as ts.NewExpression[];
  assert.equal(urls.length, 1, "apiHost does not construct exactly one URL");
  assert.ok(
    urls[0].arguments?.length === 1 && isIdent(unparen(urls[0].arguments[0]), "API_BASE"),
    "the URL apiHost constructs is not new URL(API_BASE)",
  );
  const hostRead = urls[0].parent;
  assert.ok(
    ts.isPropertyAccessExpression(hostRead) && hostRead.name.text === "host",
    "apiHost does not read .host off new URL(API_BASE)",
  );
  const returns = collect(init, (n) => ts.isReturnStatement(n)) as ts.ReturnStatement[];
  assert.equal(returns.length, 2, "apiHost does not return in exactly two places, the URL host and the fallback");
  assert.ok(
    returns.some((r) => !!r.expression && unparen(r.expression) === hostRead),
    "new URL(API_BASE).host is constructed but not what apiHost returns",
  );
  assert.ok(
    returns.some((r) => !!r.expression && isIdent(unparen(r.expression), "API_BASE")),
    "apiHost's fallback is not API_BASE itself",
  );
  const tries = collect(init, (n) => ts.isTryStatement(n)) as ts.TryStatement[];
  assert.equal(tries.length, 1, "apiHost is not a single try/catch");
  assert.ok(within(hostRead, tries[0].tryBlock), "the URL host is not returned from the try block");
  assert.ok(
    collect(init, (n) => ts.isIfStatement(n) || ts.isConditionalExpression(n)).length === 0,
    "apiHost branches on something; the only branch it may have is the catch",
  );
});

check("the soul request is GET API_BASE/soul/status with the bearer header, and nothing else feeds soulResult", () => {
  const file = parse(DOCK);
  const settled = collect(
    file,
    (n) =>
      ts.isVariableDeclaration(n) &&
      ts.isArrayBindingPattern(n.name) &&
      n.name.elements.some((e) => ts.isBindingElement(e) && isIdent(e.name, "soulResult")),
  ) as ts.VariableDeclaration[];
  assert.equal(settled.length, 1, "soulResult is not bound exactly once by the allSettled destructuring");
  const pattern = settled[0].name as ts.ArrayBindingPattern;
  const position = pattern.elements.findIndex((e) => ts.isBindingElement(e) && isIdent(e.name, "soulResult"));
  let init = unparen(settled[0].initializer as ts.Node);
  if (ts.isAwaitExpression(init)) init = unparen(init.expression);
  assert.ok(
    ts.isCallExpression(init) && isPropOf(init.expression, "Promise", "allSettled") && init.arguments.length === 1,
    "soulResult does not come from Promise.allSettled([...])",
  );
  const list = unparen(init.arguments[0]);
  assert.ok(ts.isArrayLiteralExpression(list), "Promise.allSettled is not handed an array literal");
  const call = unparen(list.elements[position]);
  assert.ok(ts.isCallExpression(call) && isIdent(call.expression, "fetch") && call.arguments.length === 2, "the soul read is not a two argument fetch");
  const url = unparen(call.arguments[0]);
  assert.ok(
    ts.isTemplateExpression(url) &&
      url.head.text === "" &&
      url.templateSpans.length === 1 &&
      isIdent(unparen(url.templateSpans[0].expression), "API_BASE") &&
      url.templateSpans[0].literal.text === "/soul/status",
    "the soul read is not aimed at `${API_BASE}/soul/status`; the second critic aimed it at /agent-tasks/tools and every word on the panel stayed plausible",
  );
  const opts = unparen(call.arguments[1]);
  assert.ok(ts.isObjectLiteralExpression(opts) && opts.properties.length === 2, "the soul read's options are not exactly { cache, headers }");
  const cache = opts.properties.find((p) => ts.isPropertyAssignment(p) && ts.isIdentifier(p.name) && p.name.text === "cache") as ts.PropertyAssignment | undefined;
  assert.ok(cache && isStr(unparen(cache.initializer), "no-store"), 'the soul read is not cache: "no-store"');
  assert.ok(
    opts.properties.some((p) => ts.isShorthandPropertyAssignment(p) && p.name.text === "headers"),
    "the soul read does not pass the shared headers, so it is sent without the bearer token and every read is a 401",
  );
  const headers = declarationsNamed(file, "headers");
  assert.equal(headers.length, 1, "headers is not declared exactly once");
  const h = unparen(headers[0].initializer as ts.Node);
  assert.ok(
    ts.isObjectLiteralExpression(h) &&
      h.properties.length === 1 &&
      ts.isPropertyAssignment(h.properties[0]) &&
      ts.isIdentifier(h.properties[0].name) &&
      h.properties[0].name.text === "Authorization" &&
      ts.isTemplateExpression(unparen(h.properties[0].initializer)) &&
      (unparen(h.properties[0].initializer) as ts.TemplateExpression).head.text === "Bearer " &&
      isIdent(unparen((unparen(h.properties[0].initializer) as ts.TemplateExpression).templateSpans[0].expression), "token"),
    "headers is not exactly { Authorization: `Bearer ${token}` }",
  );
});

check("the render path from soulState to the pixels is pinned: the light's body, the tile callback, the header row, the section", () => {
  const file = parse(DOCK);

  // Indicator: one span, data-indicator="light", a className whose only
  // expression is a conditional on `ok` between the two pinned class strings.
  const indicator = collect(file, (n) => ts.isFunctionDeclaration(n) && !!n.name && n.name.text === "Indicator") as ts.FunctionDeclaration[];
  assert.equal(indicator.length, 1, "Indicator is not declared exactly once");
  const returns = collect(indicator[0], (n) => ts.isReturnStatement(n)) as ts.ReturnStatement[];
  assert.equal(returns.length, 1, "Indicator does not return exactly once");
  const span = unparen(returns[0].expression as ts.Node);
  assert.ok(ts.isJsxSelfClosingElement(span) && span.tagName.getText() === "span", "Indicator does not return one self closing span");
  const attrs = span.attributes.properties;
  assert.equal(attrs.length, 2, "Indicator's span carries attributes besides data-indicator and className");
  const marker = attrs.find((a) => ts.isJsxAttribute(a) && a.name.getText() === "data-indicator") as ts.JsxAttribute | undefined;
  assert.ok(marker && marker.initializer && ts.isStringLiteral(marker.initializer) && marker.initializer.text === "light", 'Indicator\'s span is not marked data-indicator="light"');
  const cls = attrs.find((a) => ts.isJsxAttribute(a) && a.name.getText() === "className") as ts.JsxAttribute | undefined;
  assert.ok(cls && cls.initializer && ts.isJsxExpression(cls.initializer) && cls.initializer.expression, "Indicator's className is not an expression");
  const tpl = unparen(cls.initializer.expression as ts.Node);
  assert.ok(ts.isTemplateExpression(tpl) && tpl.head.text === "h-1.5 w-1.5 rounded-full " && tpl.templateSpans.length === 1 && tpl.templateSpans[0].literal.text === "", "Indicator's class template is not `h-1.5 w-1.5 rounded-full ${...}`");
  const cond = unparen(tpl.templateSpans[0].expression);
  assert.ok(
    ts.isConditionalExpression(cond) &&
      isIdent(unparen(cond.condition), "ok") &&
      isStr(unparen(cond.whenTrue), "bg-emerald-400 shadow-[0_0_10px_rgba(52,211,153,.7)]") &&
      isStr(unparen(cond.whenFalse), "bg-[#526979]"),
    "Indicator does not choose exactly the emerald class on ok and the grey class otherwise",
  );

  // The tile callback: [label, ok, detail] => a div with two rows and nothing else.
  const indicators = collect(file, (n) => (ts.isJsxSelfClosingElement(n) || ts.isJsxOpeningElement(n)) && n.tagName.getText() === "Indicator");
  assert.equal(indicators.length, 1, "expected exactly one <Indicator> in the dock");
  let node: ts.Node = indicators[0];
  let arrow: ts.ArrowFunction | null = null;
  while (node.parent) {
    node = node.parent;
    if (ts.isArrowFunction(node)) {
      arrow = node;
      break;
    }
  }
  assert.ok(arrow, "the <Indicator> is not rendered inside an arrow function");
  assert.ok(
    arrow.parameters.length === 1 && ts.isArrayBindingPattern(arrow.parameters[0].name) && arrow.parameters[0].name.elements.map((e) => (ts.isBindingElement(e) && ts.isIdentifier(e.name) ? e.name.text : "?")).join(",") === "label,ok,detail",
    "the tile callback does not destructure [label, ok, detail]",
  );
  const tile = unparen(arrow.body);
  assert.ok(ts.isJsxElement(tile) && tile.openingElement.tagName.getText() === "div", "the tile callback does not return a div");
  const tileChildren = tile.children.filter((c) => !(ts.isJsxText(c) && c.text.trim() === ""));
  assert.equal(tileChildren.length, 2, "the tile div does not have exactly two children (the row and the paragraph); the second critic painted a second light inside it");
  const [row, para] = tileChildren;
  assert.ok(ts.isJsxElement(row) && row.openingElement.tagName.getText() === "div", "the tile's first child is not the row div");
  const rowChildren = row.children.filter((c) => !(ts.isJsxText(c) && c.text.trim() === ""));
  assert.equal(rowChildren.length, 2, "the tile row does not have exactly two children (the light and the label)");
  const light = rowChildren[0];
  assert.ok(ts.isJsxSelfClosingElement(light) && light.tagName.getText() === "Indicator", "the row's first child is not <Indicator>");
  const okAttr = light.attributes.properties.find((a) => ts.isJsxAttribute(a) && a.name.getText() === "ok") as ts.JsxAttribute | undefined;
  assert.ok(okAttr && okAttr.initializer && ts.isJsxExpression(okAttr.initializer) && okAttr.initializer.expression, "Indicator has no ok expression");
  const okExpr = unparen(okAttr.initializer.expression as ts.Node);
  assert.ok(
    ts.isCallExpression(okExpr) && isIdent(okExpr.expression, "Boolean") && okExpr.arguments.length === 1 && isIdent(unparen(okExpr.arguments[0]), "ok"),
    "the light is not lit by exactly Boolean(ok); the second critic lit it with `|| label === \"Soul\"`",
  );
  assert.equal(light.attributes.properties.length, 1, "the <Indicator> carries attributes besides ok");
  assert.ok(ts.isJsxElement(para) && para.openingElement.tagName.getText() === "p", "the tile's second child is not the paragraph");
  const paraExprs = collect(para, (n) => ts.isJsxExpression(n) && !!n.expression) as ts.JsxExpression[];
  assert.equal(paraExprs.length, 1, "the tile paragraph does not carry exactly one expression");
  const pe = unparen(paraExprs[0].expression as ts.Node);
  assert.ok(ts.isCallExpression(pe) && isIdent(pe.expression, "String") && pe.arguments.length === 1 && isIdent(unparen(pe.arguments[0]), "detail"), "the tile paragraph is not exactly String(detail); the second critic rewrote unread as off here");
  const tileAttrs = tile.openingElement.attributes.properties.map((a) => (ts.isJsxAttribute(a) ? a.name.getText() : "?"));
  assert.deepEqual(tileAttrs, ["key", "data-tile", "className"], "the tile div's attributes are not exactly key, data-tile, className");

  // The Soul recall header row: exactly two spans, the value span pinned.
  const rows = collect(file, (n) => ts.isJsxOpeningElement(n) && n.attributes.properties.some((a) => ts.isJsxAttribute(a) && a.name.getText() === "data-soul-header" && !!a.initializer && ts.isStringLiteral(a.initializer) && a.initializer.text === "row"));
  assert.equal(rows.length, 1, 'no element is marked data-soul-header="row"');
  const rowEl = rows[0].parent as ts.JsxElement;
  const headerChildren = rowEl.children.filter((c) => !(ts.isJsxText(c) && c.text.trim() === ""));
  assert.equal(headerChildren.length, 2, "the Soul recall header row does not have exactly two children; the second critic added a static ON beside a hidden OFF");
  const [labelSpan, valueSpan] = headerChildren;
  assert.ok(ts.isJsxElement(labelSpan) && labelSpan.children.length === 1 && ts.isJsxText(labelSpan.children[0]) && labelSpan.children[0].text.trim() === "Soul recall", 'the header label is not the text "Soul recall"');
  assert.ok(ts.isJsxElement(valueSpan), "the header value is not an element");
  const valueAttrs = (valueSpan as ts.JsxElement).openingElement.attributes.properties;
  const valueMarker = valueAttrs.find((a) => ts.isJsxAttribute(a) && a.name.getText() === "data-soul-header") as ts.JsxAttribute | undefined;
  assert.ok(valueMarker && valueMarker.initializer && ts.isStringLiteral(valueMarker.initializer) && valueMarker.initializer.text === "value", 'the header value span is not marked data-soul-header="value"');
  const valueCls = valueAttrs.find((a) => ts.isJsxAttribute(a) && a.name.getText() === "className") as ts.JsxAttribute | undefined;
  assert.ok(valueCls && valueCls.initializer && ts.isStringLiteral(valueCls.initializer) && valueCls.initializer.text === "font-mono text-[9px] text-[#d4a017]", "the header value span's className is not the pinned amber literal; the second critic painted it in the background colour");
  assert.equal(valueAttrs.length, 2, "the header value span carries attributes besides its marker and className");
  const valueKids = (valueSpan as ts.JsxElement).children.filter((c) => !(ts.isJsxText(c) && c.text.trim() === ""));
  assert.ok(valueKids.length === 1 && ts.isJsxExpression(valueKids[0]) && !!valueKids[0].expression, "the header value span does not carry exactly one expression");
  const call = unparen(valueKids[0].expression as ts.Node);
  assert.ok(ts.isCallExpression(call) && isPropOf(call.expression, "soulState", "toUpperCase") && call.arguments.length === 0, "the header value is not soulState.toUpperCase()");

  // The note paragraph is marked, and the section carries the derived state.
  const noteEls = collect(file, (n) => ts.isJsxOpeningElement(n) && n.attributes.properties.some((a) => ts.isJsxAttribute(a) && a.name.getText() === "data-soul-note"));
  assert.equal(noteEls.length, 1, "the note paragraph is not marked data-soul-note exactly once");
  const noteKids = (noteEls[0].parent as ts.JsxElement).children.filter((c) => !(ts.isJsxText(c) && c.text.trim() === ""));
  assert.ok(noteKids.length === 1 && ts.isJsxExpression(noteKids[0]) && !!noteKids[0].expression && isIdent(noteKids[0].expression, "soulNote"), "the marked note paragraph does not render exactly {soulNote}");
  const sections = collect(file, (n) => ts.isJsxOpeningElement(n) && n.tagName.getText() === "section") as ts.JsxOpeningElement[];
  assert.equal(sections.length, 1, "the dock does not render exactly one section");
  const dockAttr = sections[0].attributes.properties.find((a) => ts.isJsxAttribute(a) && a.name.getText() === "data-dock") as ts.JsxAttribute | undefined;
  assert.ok(dockAttr && dockAttr.initializer && ts.isStringLiteral(dockAttr.initializer) && dockAttr.initializer.text === "capability-mesh", 'the section is not marked data-dock="capability-mesh"');
  const stateAttr = sections[0].attributes.properties.find((a) => ts.isJsxAttribute(a) && a.name.getText() === "data-soul-state") as ts.JsxAttribute | undefined;
  assert.ok(stateAttr && stateAttr.initializer && ts.isJsxExpression(stateAttr.initializer) && !!stateAttr.initializer.expression && isIdent(stateAttr.initializer.expression, "soulState"), "the section does not carry data-soul-state={soulState}");
});

check("the three note sentences are the pinned ones, and the fallbacks name themselves", () => {
  const file = parse(DOCK);
  const note = onlyDeclaration(file, "soulNote");
  const body = note.initializer as ts.Node;
  const templates = collect(body, (n) => ts.isTemplateExpression(n)) as ts.TemplateExpression[];
  const texts = templates.map((t) => t.head.text + t.templateSpans.map((sp) => "${" + unparen(sp.expression).getText() + "}" + sp.literal.text).join(""));
  assert.deepEqual(
    texts,
    [
      "Checking. GET /soul/status on ${apiHost} has not answered yet.",
      "Soul status unread. GET /soul/status on ${apiHost} did not answer, so whether recall is on is unknown here.",
      "${detail} Configured rather than probed: the status route never calls Pinecone, so only a recall proves the connection.",
      "${detail} Those variables belong to the environment of ${apiHost}, the only host this readout asks.",
    ],
    "soulNote's four sentences are not the pinned ones, in order. The second critic made the on branch claim Pinecone had been probed; change these words as a decision, here and in dock-smoke.mjs together",
  );
  const literals = collect(body, (n) => ts.isStringLiteral(n)).map((n) => (n as ts.StringLiteral).text);
  for (const fallback of literals.filter((t) => /Soul recall is/.test(t))) {
    assert.ok(/gave no detail/.test(fallback), `the fallback ${JSON.stringify(fallback)} could pass for the route's own detail; a fallback names itself as one`);
  }
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
