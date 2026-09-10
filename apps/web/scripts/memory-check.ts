/**
 * Proof for the long term memory panel. No test framework: node:assert and a
 * plain process exit code, the same shape as scripts/learning-check.ts and
 * scripts/control-check.ts. Run from apps/web:
 *
 *   node --experimental-strip-types scripts/memory-check.ts
 *
 * WHY THIS FILE EXISTS
 *
 * The memory panel is the first surface over app/api/v1/memory.py, and it makes
 * two kinds of claim that nothing else in the estate can check for it:
 *
 *   1. Whether the store is empty. Rendering a FAILED read as an EMPTY store is
 *      the defect this estate has shipped most often, and neither `tsc --noEmit`
 *      nor `next build` has ever caught it: on 2026-09-09 a critic inverted the
 *      control plane's verdict ladder and both exited 0 over a green badge on a
 *      broken chain. So type checks are not a guard on this and this file is.
 *
 *   2. Whether a delete was ruled on. DELETE /memory/{id} is a hard delete with
 *      no archive and no undo. The two step gate is the only thing between a
 *      stray tap and a row that cannot be recovered, and a gate is exactly the
 *      kind of code that keeps working while quietly letting everything through.
 *
 * Both live in components/mind/memory-honesty.ts as pure functions with no DOM
 * and no network, so there is no reason for either to be unguarded. And because
 * a correct ladder wired up wrong renders the lie anyway (the hole a critic found
 * in LearningPanel's `asRead` on 2026-09-10), the last section reads the panel's
 * own source and binds the component to the functions below it.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import {
  armDelete,
  confirmDelete,
  DELETE_DISARMED,
  deleteIsArmedFor,
  describeDeletion,
  describeFilter,
  describeRecall,
  disarmDelete,
  filterMemories,
  importanceLabel,
  originLabel,
  parseMemoryPayload,
  readMemoryVerdict,
  summarizeMemories,
  type MemoryRead,
  type MemoryTally,
  type MemoryVerdict,
  type ParsedMemory,
} from "../components/mind/memory-honesty.ts";

const HERE = dirname(fileURLToPath(import.meta.url));

let checks = 0;
function check(name: string, run: () => void): void {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

function tally(over: Partial<MemoryTally> = {}): MemoryTally {
  return { total: 0, active: 0, paused: 0, unknownActivity: 0, malformed: 0, ...over };
}

const PENDING: MemoryRead = { state: "pending" };
const LOCKED: MemoryRead = { state: "locked" };
const FAILED: MemoryRead = { state: "failed", detail: "the memory route answered 500" };
const OK_EMPTY: MemoryRead = { state: "ok", tally: tally() };
const OK_FULL: MemoryRead = {
  state: "ok",
  tally: tally({ total: 3, active: 2, paused: 1 }),
};

function row(over: Partial<ParsedMemory> = {}): ParsedMemory {
  return {
    id: "11111111-1111-1111-1111-111111111111",
    content: "Prefers concise answers with explicit tradeoffs.",
    memoryType: "preference",
    importance: 8,
    isActive: true,
    origin: "user",
    conversationId: null,
    projectId: null,
    createdAt: "2026-09-09T04:00:00+00:00",
    updatedAt: "2026-09-09T04:00:00+00:00",
    ...over,
  };
}

/* ------------------------------------------------------------------ */
/* The load bearing law: a failed read is not an empty store           */
/* ------------------------------------------------------------------ */

function refuseEmptyAndGood(verdict: MemoryVerdict, why: string): void {
  assert.equal(verdict.code, "unreadable", why);
  assert.notEqual(verdict.code, "empty", "a failed read must never read as an empty store");
  assert.notEqual(verdict.tone, "good", "a failed read must never take a good tone");
  assert.equal(
    verdict.rowsAreTheStore,
    false,
    "a failed read must never license the panel to render its rows as the whole store",
  );
  assert.match(verdict.sentence, /failed read, not an empty store/);
}

check("a failed read is never reported as an empty store", () => {
  refuseEmptyAndGood(
    readMemoryVerdict(FAILED),
    "the route did not answer, so no claim about emptiness is available",
  );
});

check("the failing detail reaches the operator", () => {
  assert.match(
    readMemoryVerdict(FAILED).sentence,
    /answered 500/,
    "the operator needs the actual failure, not a generic apology",
  );
});

check("a body that is not a list is a failed read, not an empty store", () => {
  // A 200 carrying {"detail": "..."} is the realistic shape here: FastAPI error
  // envelopes, a proxy's JSON, a route that starts paginating. Falling through
  // to [] renders "nothing is stored" over a store nobody counted.
  for (const body of [{ detail: "nope" }, null, "[]", 7] as unknown[]) {
    const parsed = parseMemoryPayload(body);
    assert.equal(parsed.shape, "not-a-list", `${JSON.stringify(body)} parsed as a list`);
    assert.equal(
      summarizeMemories(parsed),
      null,
      "a body that was not a list produced a tally, which is a count over nothing",
    );
  }
});

check("every non-ok read refuses both contents claims", () => {
  // Sampling one state is how the (FAILED, FAILED) hole got into learning-check.
  // Every state is walked and the invariant stated over all of them.
  const states: Array<[string, MemoryRead]> = [
    ["pending", PENDING],
    ["locked", LOCKED],
    ["failed", FAILED],
    ["ok-empty", OK_EMPTY],
    ["ok-full", OK_FULL],
  ];
  let walked = 0;
  for (const [name, read] of states) {
    walked += 1;
    const verdict = readMemoryVerdict(read);
    assert.ok(verdict.code, `${name} produced no verdict code`);
    if (read.state !== "ok") {
      assert.notEqual(
        verdict.code,
        "empty",
        `${name} reads as an EMPTY store without a completed read. An unread store is not an empty one`,
      );
      assert.notEqual(
        verdict.code,
        "populated",
        `${name} reads as a POPULATED store without a completed read, claiming rows nobody counted`,
      );
      assert.notEqual(verdict.tone, "good", `${name} reads in the good tone with no read`);
      assert.equal(
        verdict.rowsAreTheStore,
        false,
        `${name} licenses the row list, so a partial or absent read would render as the store`,
      );
    }
    if (verdict.code === "empty") {
      assert.ok(
        read.state === "ok" && read.tally.total === 0,
        `${name} reads as an empty store, but only a completed read of zero rows supports that`,
      );
    }
  }
  assert.equal(walked, 5, `expected all five read states walked, walked ${walked}`);
});

/* ------------------------------------------------------------------ */
/* pending and locked are their own facts                              */
/* ------------------------------------------------------------------ */

check("a read in flight is reading, not locked and not failed", () => {
  const verdict = readMemoryVerdict(PENDING);
  assert.equal(verdict.code, "reading");
  assert.notEqual(verdict.code, "locked");
  assert.notEqual(verdict.code, "unreadable");
});

check("no session token is locked, not a failed read", () => {
  // No request was sent, so calling this a failure would invent one.
  const verdict = readMemoryVerdict(LOCKED);
  assert.equal(verdict.code, "locked");
  assert.notEqual(verdict.code, "unreadable");
  assert.notEqual(verdict.code, "empty");
  assert.match(verdict.sentence, /no request was sent/);
});

check("every verdict code is reachable", () => {
  const codes = new Set(
    [PENDING, LOCKED, FAILED, OK_EMPTY, OK_FULL].map((read) => readMemoryVerdict(read).code),
  );
  assert.equal(codes.size, 5, "a code nothing can reach is a branch nobody guards");
});

/* ------------------------------------------------------------------ */
/* The honest ends of the ladder                                       */
/* ------------------------------------------------------------------ */

check("a completed read of no rows is an empty store, and says which", () => {
  const verdict = readMemoryVerdict(OK_EMPTY);
  assert.equal(verdict.code, "empty");
  assert.equal(verdict.rowsAreTheStore, true);
  assert.notEqual(verdict.tone, "good", "an empty store is a finding, not a pass");
  assert.match(verdict.sentence, /answered and returned no rows/);
});

check("a populated store reports the counts it was given and no others", () => {
  const verdict = readMemoryVerdict(OK_FULL);
  assert.equal(verdict.code, "populated");
  assert.equal(verdict.tone, "good");
  assert.match(verdict.sentence, /3 memories: 2 active, 1 paused/);
  assert.ok(
    !/flag the route did not send/.test(verdict.sentence),
    "no row had an absent flag, so the panel must not mention one",
  );
});

check("rows whose active flag is absent are named, never counted as active", () => {
  const verdict = readMemoryVerdict({
    state: "ok",
    tally: tally({ total: 2, active: 1, unknownActivity: 1 }),
  });
  assert.match(verdict.sentence, /2 memories: 1 active, 0 paused/);
  assert.match(verdict.sentence, /1 whose active flag the route did not send/);
});

check("a populated store still refuses to promise recall", () => {
  assert.match(readMemoryVerdict(OK_FULL).sentence, /not a guarantee of recall/);
});

/* ------------------------------------------------------------------ */
/* Parsing never fills a gap                                           */
/* ------------------------------------------------------------------ */

check("absent fields stay absent instead of taking the server's defaults", () => {
  // importance defaults to 5 and is_active to True in app/api/v1/memory.py and
  // app/models/memory.py. Reproducing those defaults on the client puts a number
  // on the screen that no route sent for this row.
  const parsed = parseMemoryPayload([{ id: "a", content: "text only" }]);
  assert.equal(parsed.shape, "list");
  if (parsed.shape !== "list") return;
  const only = parsed.rows[0];
  assert.equal(only.importance, null, "importance was defaulted");
  assert.equal(only.isActive, null, "is_active was defaulted");
  assert.equal(only.memoryType, null, "memory_type was defaulted");
  assert.equal(only.origin, null, "origin was invented from an absent metadata dict");
  assert.equal(only.createdAt, null);
  assert.match(importanceLabel(null), /did not send an importance/);
  assert.match(originLabel(null), /did not say where this came from/);
});

check("a row with no usable id is counted, not rendered with an invented one", () => {
  const parsed = parseMemoryPayload([{ id: "a" }, { content: "no id" }, "nonsense", null]);
  assert.equal(parsed.shape, "list");
  if (parsed.shape !== "list") return;
  assert.equal(parsed.rows.length, 1);
  assert.equal(parsed.malformed, 3);
  const summary = summarizeMemories(parsed);
  assert.equal(summary?.malformed, 3, "the tally dropped the malformed rows silently");
});

check("the tally keeps unknown activity out of both buckets", () => {
  const parsed = parseMemoryPayload([
    { id: "a", is_active: true },
    { id: "b", is_active: false },
    { id: "c" },
  ]);
  const summary = summarizeMemories(parsed);
  assert.deepEqual(summary, {
    total: 3,
    active: 1,
    paused: 1,
    unknownActivity: 1,
    malformed: 0,
  });
});

check("a paused row is never described as reachable by recall", () => {
  assert.match(describeRecall(row({ isActive: false })), /can never reach a Council answer/);
  assert.match(describeRecall(row({ isActive: null })), /not something this panel can state/);
  assert.match(describeRecall(row({ isActive: true })), /^Active\./);
});

/* ------------------------------------------------------------------ */
/* A filter is the fifth way to draw an empty store                    */
/* ------------------------------------------------------------------ */

check("a filter that matched nothing is a filter, not an empty store", () => {
  const rows = [row({ id: "a" }), row({ id: "b", content: "Ships on Fridays." })];
  const outcome = filterMemories(rows, "zzz");
  assert.equal(outcome.shown.length, 0);
  assert.equal(outcome.hiddenByFilter, 2);
  const sentence = describeFilter(outcome, tally({ total: 2, active: 2 }));
  assert.ok(sentence, "a filter that hid everything owes the reader a sentence");
  assert.match(sentence!, /2 memories are stored/);
  assert.match(sentence!, /rather than a store that holds nothing/);
  assert.ok(
    !/\bempty\b/i.test(sentence!),
    "the filter sentence uses the empty verdict's word, which is the confusion it exists to prevent",
  );
});

check("no filter means no sentence, so nothing is claimed about hidden rows", () => {
  const rows = [row()];
  const outcome = filterMemories(rows, "   ");
  assert.equal(outcome.applied, "");
  assert.equal(outcome.shown.length, 1);
  assert.equal(describeFilter(outcome, tally({ total: 1, active: 1 })), null);
});

check("a row with no content cannot be matched, so it counts as hidden", () => {
  const outcome = filterMemories([row({ content: null })], "anything");
  assert.equal(outcome.shown.length, 0);
  assert.equal(outcome.hiddenByFilter, 1);
});

/* ------------------------------------------------------------------ */
/* The delete gate                                                     */
/* ------------------------------------------------------------------ */

check("a disarmed gate refuses every delete", () => {
  const ruling = confirmDelete(DELETE_DISARMED, "a");
  assert.equal(ruling.proceed, false);
  if (ruling.proceed) return;
  assert.match(ruling.reason, /one tap destructive action/);
});

check("arming one row does not delete it", () => {
  const gate = armDelete("a");
  assert.equal(deleteIsArmedFor(gate, "a"), true);
  assert.equal(deleteIsArmedFor(gate, "b"), false);
  // Arming is a state change and nothing else. The only function that may say a
  // request leaves is confirmDelete, and it has not been called.
  assert.equal(gate.armedId, "a");
});

check("only the armed id may be deleted", () => {
  const gate = armDelete("a");
  assert.equal(confirmDelete(gate, "a").proceed, true);
  const wrong = confirmDelete(gate, "b");
  assert.equal(wrong.proceed, false, "a delete for an id nobody armed was allowed through");
  if (!wrong.proceed) assert.match(wrong.reason, /the armed row is a and this request named b/);
});

check("arming a second row disarms the first", () => {
  // Two rows one tap from deletion is the state this shape exists to make
  // unrepresentable: the gate holds one id, not a set.
  const gate = armDelete("b");
  assert.equal(confirmDelete(armDelete("a"), "a").proceed, true);
  assert.equal(confirmDelete(gate, "a").proceed, false);
  assert.equal(confirmDelete(gate, "b").proceed, true);
});

check("keeping it disarms, so the next tap sends nothing", () => {
  assert.equal(confirmDelete(disarmDelete(), "a").proceed, false);
});

check("the notice says exactly what is lost, and refuses when it does not know", () => {
  const notice = describeDeletion(row());
  assert.equal(notice.losing, "Prefers concise answers with explicit tradeoffs.");
  assert.match(notice.irreversible, /hard delete/);
  assert.match(notice.irreversible, /no undo/);
  assert.match(notice.alternative, /Pausing keeps the row/);
  assert.ok(
    notice.facts.some((fact) => fact.includes("11111111-1111-1111-1111-111111111111")),
    "the notice does not name the row it would destroy",
  );

  const blind = describeDeletion(row({ content: null, importance: null, createdAt: null }));
  assert.match(blind.losing, /cannot show you what you would be deleting/);
  assert.ok(
    blind.facts.some((fact) => /did not send an importance/.test(fact)),
    "the notice invented an importance for a row that carried none",
  );
  assert.ok(
    !/\b5 of 10\b/.test(blind.facts.join(" ")),
    "the notice fell back to the server default importance",
  );
});

/* ------------------------------------------------------------------ */
/* The wire from the panel into all of the above                       */
/* ------------------------------------------------------------------ */

/*
 * Everything above exercises pure functions in isolation, which is right and is
 * not enough. A critic proved that on LearningPanel on 2026-09-10: the ladder was
 * never wrong, one line inside the adapter feeding it was, every check passed and
 * the panel rendered "EMPTY" over a store it had failed to read. So the panel's
 * own source is read here and bound to the functions it is meant to use.
 *
 * Read from source rather than executed, because this runner imports no React.
 */
const PANEL_PATH = join(HERE, "..", "components/mind/MemoryPanel.tsx");
const PANEL = readFileSync(PANEL_PATH, "utf8");

function tsx(name: string, source: string): ts.SourceFile {
  return ts.createSourceFile(name, source, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
}

function collect(root: ts.Node, keep: (n: ts.Node) => boolean): ts.Node[] {
  const out: ts.Node[] = [];
  const walk = (n: ts.Node) => {
    if (keep(n)) out.push(n);
    ts.forEachChild(n, walk);
  };
  walk(root);
  return out;
}

function findFunction(file: ts.SourceFile, name: string): ts.FunctionDeclaration {
  const found = collect(
    file,
    (n) => ts.isFunctionDeclaration(n) && n.name !== undefined && n.name.text === name,
  ) as ts.FunctionDeclaration[];
  assert.equal(
    found.length,
    1,
    `MemoryPanel must declare ${name} exactly once; found ${found.length}. Without it this check cannot find the wire`,
  );
  return found[0];
}

check("the panel's asRead maps a failed read to failed, never to a tally", () => {
  const asRead = findFunction(tsx("MemoryPanel.tsx", PANEL), "asRead");
  const text = asRead.getText();

  const returns = collect(asRead, ts.isReturnStatement) as ts.ReturnStatement[];
  const failedBranch = returns.find((r) => {
    let at: ts.Node | undefined = r.parent;
    while (at && at !== asRead) {
      if (ts.isIfStatement(at) && at.expression.getText().includes('"failed"')) return true;
      at = at.parent;
    }
    return false;
  });
  assert.ok(
    failedBranch,
    'asRead has no branch keyed on a "failed" read, so a failure falls through to whatever the last return says',
  );
  const failedText = failedBranch!.getText();
  assert.match(
    failedText,
    /state:\s*"failed"/,
    `asRead's failed branch returns ${failedText}, which does not carry state "failed"`,
  );
  assert.ok(
    !/tally:/.test(failedText),
    `asRead's failed branch carries a tally (${failedText}). A tally is a claim about the store, and a read that failed supports no such claim`,
  );

  // The unreadable body case has to land on failed too, or a 200 with the wrong
  // shape becomes an empty store.
  assert.match(
    text,
    /if\s*\(tally === null\)[\s\S]{0,400}state:\s*"failed"/,
    "asRead does not send a null tally to the failed state, so a body that was not a list reads as an empty store",
  );

  assert.match(
    PANEL,
    /readMemoryVerdict\(asMemoryRead\)/,
    "the panel no longer feeds asRead's output into readMemoryVerdict, so the ladder this file guards is not the one it renders",
  );
  assert.match(
    PANEL,
    /const asMemoryRead = asRead\(read\)/,
    "the panel no longer builds its verdict input through asRead",
  );
});

check("the panel renders its row list only when the rows are the store", () => {
  assert.match(
    PANEL,
    /\{verdict\.rowsAreTheStore && tally !== null \? \(/,
    "the row list is not gated on rowsAreTheStore, so a partial or failed read can render rows that read as the whole store",
  );
});

check("the panel's only delete asks the gate first and obeys a refusal", () => {
  const destroy = findFunction(tsx("MemoryPanel.tsx", PANEL), "destroy");
  const text = destroy.getText();
  const asked = text.indexOf("confirmDelete(gate, row.id)");
  assert.ok(asked >= 0, "destroy does not consult confirmDelete, so the gate is decorative");
  assert.match(
    text,
    /if \(!ruling\.proceed\) \{[\s\S]{0,400}return;/,
    "destroy does not return on a refusal, so a refused ruling falls through to the request",
  );
  const sent = text.indexOf("fetch(");
  assert.ok(sent >= 0, "destroy sends no request, so this check is guarding nothing");
  assert.ok(
    asked < sent,
    "destroy calls fetch before it consults the gate, so the ruling cannot stop the request",
  );

  // And there is exactly one DELETE in the whole panel, inside that function.
  const deletes = [...PANEL.matchAll(/method:\s*"DELETE"/g)];
  assert.equal(
    deletes.length,
    1,
    `the panel carries ${deletes.length} DELETE requests; every destructive path has to go through the one gated function`,
  );
  assert.ok(
    text.includes('method: "DELETE"'),
    "the panel's DELETE is not inside destroy, so it is not behind the gate",
  );

  // The arm button must not be able to delete. armDelete appears only as a state
  // setter, never next to a fetch.
  // \b keeps this off disarmDelete, which contains the same letters.
  const arms = [...PANEL.matchAll(/\barmDelete\(/g)];
  assert.equal(arms.length, 1, "armDelete is called more than once; there is one arming path");
  assert.match(
    PANEL,
    /onClick=\{\(\) => setGate\(armDelete\(row\.id\)\)\}/,
    "the Delete button does something other than arm the gate",
  );
});

check("the panel writes nothing on load", () => {
  // A panel that seeds a row to make the store non-empty is the same lie as an
  // empty state over a failed read, told in the other direction. The load path
  // must be a GET and nothing else.
  const load = collect(
    tsx("MemoryPanel.tsx", PANEL),
    (n) =>
      ts.isVariableDeclaration(n) &&
      ts.isIdentifier(n.name) &&
      n.name.text === "load" &&
      n.initializer !== undefined,
  ) as ts.VariableDeclaration[];
  assert.equal(load.length, 1, "MemoryPanel must declare exactly one load callback");
  const text = load[0].getText();
  for (const verb of ["POST", "PATCH", "DELETE", "PUT"]) {
    assert.ok(
      !text.includes(`"${verb}"`),
      `the load path issues a ${verb}, so opening the panel mutates the store`,
    );
  }
  assert.match(text, /\/memory\?include_inactive=true/, "the load path does not read the route");
  assert.match(
    text,
    /setGate\(disarmDelete\(\)\)/,
    "a reload leaves a row armed, so a ruling made against the old list survives into a new one",
  );
});

check("the panel is mounted where a person can reach it", () => {
  const page = readFileSync(join(HERE, "..", "app/control/memory/page.tsx"), "utf8");
  assert.match(
    page,
    /<MemoryPanel \/>/,
    "/control/memory no longer renders MemoryPanel, so the door is open in the file tree and shut to a person",
  );
  assert.match(page, /from "@\/components\/mind\/MemoryPanel"/);
});

/* ------------------------------------------------------------------ */
/* The legibility floor, on this door's own files                      */
/* ------------------------------------------------------------------ */

/*
 * scripts/control-check.ts holds this floor over a NAMED list of files, so a new
 * file is outside it until somebody adds it. These three are named here so the
 * floor applies from the commit that introduces them rather than from the commit
 * that remembers to. Thresholds are control-check's, computed against #04070d:
 * white at 45% is 4.48:1 and fails AA for body text, white at 50% is 5.35:1.
 */
const MEMORY_TREE = [
  "components/mind/MemoryPanel.tsx",
  "components/mind/memory-honesty.ts",
  "app/control/memory/page.tsx",
];

const BELOW_AA: Array<{ pattern: RegExp; why: string }> = [
  { pattern: /text-\[(?:[0-9]|10)px\]/g, why: "under 11px is unreadable on a phone" },
  {
    pattern: /text-white\/(?:[0-9]|[1-3][0-9]|4[0-5])\b/g,
    why: "white at 45% or less is below 4.5:1 on the ACX void",
  },
  { pattern: /text-\[#526979\]/g, why: "#526979 is 3.49:1 on the ACX void" },
];

check("no text in this door renders below the AA floor", () => {
  const offences: string[] = [];
  for (const relative of MEMORY_TREE) {
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
  // A list that silently matches nothing passes forever.
  assert.equal(MEMORY_TREE.length, 3);
  for (const relative of MEMORY_TREE) {
    const source = readFileSync(join(HERE, "..", relative), "utf8");
    assert.ok(source.length > 200, `${relative} is too small to be the real file`);
  }
  assert.match(PANEL, /className=/, "the panel carries no classes to check");
});

/** The text of an id= or htmlFor= attribute, literal or template. */
function attrText(element: ts.JsxOpeningLikeElement, name: string): string | null {
  for (const attribute of element.attributes.properties) {
    if (!ts.isJsxAttribute(attribute)) continue;
    if (attribute.name.getText() !== name) continue;
    const value = attribute.initializer;
    if (value === undefined) return null;
    if (ts.isStringLiteral(value)) return value.text;
    if (ts.isJsxExpression(value) && value.expression) return value.expression.getText();
    return null;
  }
  return null;
}

check("every control on this door carries a label", () => {
  // A placeholder is not a label: it disappears the moment anything is typed and
  // a screen reader is not required to announce it. Selects and textareas are
  // included, not just inputs, because the same is true of both.
  const file = tsx("MemoryPanel.tsx", PANEL);
  const opens = collect(
    file,
    (n) => ts.isJsxOpeningElement(n) || ts.isJsxSelfClosingElement(n),
  ) as ts.JsxOpeningLikeElement[];

  const labelledIds = new Set<string>();
  for (const element of opens) {
    if (element.tagName.getText() !== "label") continue;
    const target = attrText(element, "htmlFor");
    if (target !== null) labelledIds.add(target);
  }

  let controls = 0;
  for (const element of opens) {
    const tag = element.tagName.getText();
    if (tag !== "input" && tag !== "textarea" && tag !== "select") continue;
    controls += 1;
    const id = attrText(element, "id");
    const aria = attrText(element, "aria-label") ?? attrText(element, "aria-labelledby");
    assert.ok(
      (id !== null && labelledIds.has(id)) || aria !== null,
      `${tag} with id ${String(id)} has no label; the labelled ids are ${[...labelledIds].join(", ")}`,
    );
  }
  assert.equal(
    controls,
    7,
    `expected 7 controls on this panel, found ${controls}. The count moved, so re-check that each one is labelled`,
  );
  assert.equal(labelledIds.size, 7, "a label lost its htmlFor, or one was added without a control");
});

/* ------------------------------------------------------------------ */
/* Added 2026-09-10, after an adversary beat all 32 checks above.       */
/* ------------------------------------------------------------------ */

check("rows that arrived and could not be used are not a claim that nothing is stored", () => {
  // THE HOLE: GET /memory answering 200 with [{content:"a"},{content:"b"},
  // {content:"c"}] parsed to zero rows with malformed 3, and the empty rung
  // stated "Nothing is stored for this account" while the amber line two lines
  // above the header said three rows had come back. The surface rendered both
  // halves of a contradiction and every check here was green over it.
  const verdict = readMemoryVerdict({ state: "ok", tally: tally({ total: 0, malformed: 3 }) });
  assert.equal(verdict.code, "unusable", `three unusable rows read as ${verdict.code}`);
  assert.notEqual(verdict.tone, "good");
  assert.equal(
    verdict.rowsAreTheStore,
    false,
    "an unusable read must not license the panel to render its rows as the whole store",
  );
  assert.ok(
    !/Nothing is stored/.test(verdict.sentence),
    `rows arrived and the sentence still says nothing is stored: "${verdict.sentence}"`,
  );
  assert.match(verdict.sentence, /3 rows/, verdict.sentence);

  // and a genuinely empty read is still empty, so this rung did not eat it
  const empty = readMemoryVerdict({ state: "ok", tally: tally() });
  assert.equal(empty.code, "empty");
  assert.equal(empty.rowsAreTheStore, true);

  // a partial read, some usable and some not, is still populated: the rows in
  // hand are the store, and the amber line reports the shortfall
  const partial = readMemoryVerdict({ state: "ok", tally: tally({ total: 2, active: 2, malformed: 1 }) });
  assert.equal(partial.code, "populated");
});

check("the verdict the ladder returns is the verdict the screen shows", () => {
  // THE HOLE, and it is the third time this shape has been found in this repo.
  // Every check above binds the LADDER and the ADAPTER. None bound the render.
  // A six line change to the JSX painted "MEMORY EMPTY / Nothing is stored for
  // this account yet" for the unreadable code, with all 32 checks, control-check
  // and tsc exiting 0. So the two JSX expressions inside the verdict block are
  // asserted to be exactly the ladder's own fields, with no conditional.
  const file = ts.createSourceFile("MemoryPanel.tsx", PANEL, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
  const rendered: string[] = [];
  const walk = (node: ts.Node) => {
    if (ts.isJsxExpression(node) && node.expression) {
      const text = node.expression.getText().replace(/\s+/g, " ");
      if (/\bverdict\b/.test(text)) rendered.push(text);
    }
    ts.forEachChild(node, walk);
  };
  walk(file);
  assert.ok(
    rendered.includes("verdict.label"),
    `no JSX expression renders verdict.label bare. Found: ${JSON.stringify(rendered)}`,
  );
  assert.ok(
    rendered.includes("verdict.sentence"),
    `no JSX expression renders verdict.sentence bare. Found: ${JSON.stringify(rendered)}`,
  );
  for (const expression of rendered) {
    // A conditional over verdict.code inside a rendered expression is a second
    // source of truth about what the read found. Gating a control on the code is
    // fine, and those expressions do not render label or sentence.
    if (!/verdict\.(label|sentence)/.test(expression)) continue;
    assert.ok(
      !/\?/.test(expression),
      `the verdict block renders "${expression}", a conditional over the ladder's own answer. That is how MEMORY UNREADABLE became MEMORY EMPTY with every check green`,
    );
  }
  // and no label the ladder owns may appear as a literal in the panel
  for (const owned of ["MEMORY EMPTY", "MEMORY UNREADABLE", "MEMORY PRESENT", "MEMORY LOCKED", "MEMORY UNUSABLE"]) {
    assert.ok(
      !PANEL.includes(`"${owned}"`),
      `the panel carries the literal "${owned}". Labels belong to the ladder; a copy in the component can disagree with it`,
    );
  }
});

check("an active row names every gate recall actually applies", () => {
  // THE HOLE: the sentence named ONE gate, the word overlap. app/services/
  // memory.py has three, and an adversary measured the two that were missing
  // against the real service: the project scope at memory.py:88-93 and the 200
  // row candidate window at memory.py:95. The Council writes one to five rows
  // per exchange, so an owner crosses 200 in roughly 40 to 200 exchanges and
  // from then on this panel was promising recall for rows that can never be
  // candidates.
  const global = describeRecall(row({ isActive: true, projectId: null }));
  assert.match(global, /^Active\./);
  assert.match(global, /200 most recently created/, `the candidate window is not named: "${global}"`);
  assert.match(global, /no project/, `project scope is not named: "${global}"`);
  assert.match(global, /shares a word/, `the word overlap is not named: "${global}"`);
  assert.match(global, /top 5/, `the top k cut is not named: "${global}"`);

  const scoped = describeRecall(row({ isActive: true, projectId: "22222222-2222-4222-8222-222222222222" }));
  assert.match(scoped, /200 most recently created/, scoped);
  assert.match(
    scoped,
    /different project can never recall it/,
    `a project scoped row does not say a conversation elsewhere cannot reach it: "${scoped}"`,
  );
  assert.notEqual(global, scoped, "a scoped row and a global row read identically, so the scope is not stated");

  // the two non-active branches are untouched and still distinct
  assert.match(describeRecall(row({ isActive: false })), /^Paused\./);
  assert.match(describeRecall(row({ isActive: null })), /did not send an active flag/);

  // the store level sentence carries the same three gates rather than one
  const populated = readMemoryVerdict({ state: "ok", tally: tally({ total: 3, active: 2, paused: 1 }) });
  assert.match(populated.sentence, /200 most recently created/, populated.sentence);
  assert.match(populated.sentence, /project/, populated.sentence);
});

check("a read that yielded no store does not stamp a successful read time", () => {
  // A 200 carrying {"detail":"Not authenticated"} maps to a failed read through
  // asRead, and setCheckedAt was called on the line after regardless, so the
  // header said the store could not be read while the footer said "Store read
  // <now>." Found by an adversary on 2026-09-10.
  const at = PANEL.indexOf("setCheckedAt(new Date())");
  assert.ok(at > 0, "the panel no longer stamps a read time, so this check has nothing to guard");
  const line = PANEL.slice(PANEL.lastIndexOf("\n", at) + 1, PANEL.indexOf("\n", at));
  assert.match(
    line,
    /shape === "list"/,
    `the read time is stamped unconditionally (${line.trim()}), so a body that was not a list stamps a successful read`,
  );
});

console.log(`\n${checks} memory honesty checks passed`);
