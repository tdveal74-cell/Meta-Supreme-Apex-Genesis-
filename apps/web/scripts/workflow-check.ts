/**
 * Proof for the workflow door's verdict ladders and its approval gate. No test
 * framework: node:assert and a plain process exit code, the same shape as
 * scripts/control-check.ts and scripts/learning-check.ts. Run from apps/web:
 *
 *   node --experimental-strip-types scripts/workflow-check.ts
 *
 * WHY THIS FILE EXISTS
 *
 * The workflow door is the only surface in the estate that can answer a
 * workflow's approval gate, so it is the only one that can answer it WRONGLY.
 * Two things here are worth more than everything else on the panel:
 *
 *  1. A failed read must never render as an empty list. That inversion has now
 *     been demonstrated twice against this repository by critics who left tsc
 *     and next build both exiting 0 (see the headers of scripts/control-check.ts
 *     and scripts/learning-check.ts), so neither of those is a guard on it.
 *
 *  2. An approve control must never exist over a gate the API marked diverged.
 *     app/services/workflows.py seals the rendered payload when a run pauses and
 *     refuses an approval that no longer renders that seal. A door that offers
 *     the button anyway is asking a person to rule on a payload while showing
 *     them a different one, and the fact that the server would refuse it is not
 *     the point: the ruling would have been given.
 *
 * Both live in pure functions with no DOM and no network, and the last two
 * checks bind those functions to the component that renders them, because a
 * ladder nobody is standing on holds no weight.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import {
  approvalBody,
  availableReferences,
  buildDefinition,
  describeStart,
  parseCatalog,
  readCatalogVerdict,
  readGateRuling,
  readListVerdict,
  readSummary,
  reportedLabel,
  reportedNumber,
  type PendingGate,
  type StepDraft,
  type WorkflowRead,
} from "../components/control/workflow-honesty.ts";

const HERE = dirname(fileURLToPath(import.meta.url));

let checks = 0;
function check(name: string, run: () => void): void {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

const LOCKED: WorkflowRead = { state: "locked" };
const FAILED: WorkflowRead = { state: "failed", detail: "the workflow list route answered 500" };
const OK_EMPTY: WorkflowRead = { state: "ok", count: 0 };
const OK_FULL: WorkflowRead = { state: "ok", count: 3 };

const SEALED = "a".repeat(64);

function gate(over: Partial<PendingGate> = {}): PendingGate {
  return {
    step_id: "remember",
    step_type: "memory_write",
    preview: { content: "Tee rules that the estate never merges without his word." },
    project_id: null,
    payload_sha256: SEALED,
    diverged: false,
    ...over,
  };
}

/* ------------------------------------------------------------------ */
/* Law one: a failed read is never an empty list                        */
/* ------------------------------------------------------------------ */

check("a failed workflow list read is never reported as an empty list", () => {
  const verdict = readListVerdict(FAILED);
  assert.equal(verdict.code, "unreadable");
  assert.notEqual(verdict.code, "empty", "a failed read must never read as an empty list");
  assert.notEqual(verdict.tone, "good", "a failed read must never take a good tone");
  assert.match(verdict.sentence, /failed read, not an empty list/);
  assert.match(verdict.sentence, /answered 500/, "the operator needs the actual failure");
});

check("no session token is locked, which is neither a failed read nor an empty list", () => {
  const verdict = readListVerdict(LOCKED);
  assert.equal(verdict.code, "locked");
  assert.notEqual(verdict.code, "unreadable", "no request was sent, so no failure happened");
  assert.notEqual(verdict.code, "empty");
  assert.notEqual(verdict.tone, "good");
});

check("only a successful read with no rows is an empty list, and it is not a pass", () => {
  const verdict = readListVerdict(OK_EMPTY);
  assert.equal(verdict.code, "empty");
  assert.notEqual(verdict.tone, "good", "an empty list is a finding, not a success");
  assert.match(verdict.sentence, /answered and returned no rows/);
});

check("every list read state resolves and only one of them may say empty", () => {
  const states: Array<[string, WorkflowRead]> = [
    ["locked", LOCKED],
    ["failed", FAILED],
    ["ok-empty", OK_EMPTY],
    ["ok-full", OK_FULL],
  ];
  let seen = 0;
  for (const [label, read] of states) {
    seen += 1;
    const verdict = readListVerdict(read);
    assert.ok(verdict.code, `${label} produced no verdict code`);
    if (label !== "ok-empty") {
      assert.notEqual(
        verdict.code,
        "empty",
        `${label} reads as an EMPTY list, and only a successful read of zero rows supports that claim`,
      );
    }
    if (label !== "ok-full") {
      assert.notEqual(
        verdict.code,
        "populated",
        `${label} reads as a POPULATED list, which claims rows nobody counted`,
      );
      assert.notEqual(verdict.tone, "good", `${label} reads in the good tone`);
    }
  }
  assert.equal(seen, 4);
});

/* ------------------------------------------------------------------ */
/* The catalog decides whether approval semantics may be stated         */
/* ------------------------------------------------------------------ */

check("an unreadable catalog never claims to know which steps are gated", () => {
  for (const read of [LOCKED, FAILED, OK_EMPTY]) {
    const verdict = readCatalogVerdict(read);
    assert.equal(
      verdict.semanticsKnown,
      false,
      `${verdict.code} claims to know approval semantics it did not read. Which steps stop for a human comes from the step-type route and from nothing else`,
    );
  }
  assert.equal(readCatalogVerdict(OK_FULL).semanticsKnown, true);
});

check("a failed catalog read does not suppress the list verdict, and the reverse", () => {
  // The two ladders answer different questions on purpose. Merging them would
  // withhold a fact the door is holding: how many workflows the list returned
  // does not depend on whether the catalog answered.
  const list = readListVerdict(OK_FULL);
  const catalog = readCatalogVerdict(FAILED);
  assert.equal(list.code, "populated");
  assert.equal(catalog.code, "unreadable");
  assert.equal(catalog.semanticsKnown, false);
});

/* ------------------------------------------------------------------ */
/* Law two: the gate                                                    */
/* ------------------------------------------------------------------ */

check("a diverged gate is never approvable", () => {
  // THE ONE THAT MATTERS MOST. The preview rendered for a diverged gate is the
  // LIVE definition, not the sealed payload the run paused on, so an approve
  // control here asks for a ruling on something other than what is displayed.
  const ruling = readGateRuling("awaiting_approval", gate({ diverged: true }));
  assert.equal(ruling.code, "diverged");
  assert.equal(ruling.approvable, false, "a diverged gate must never offer an approval");
  assert.equal(ruling.rejectable, true, "an owner must always be able to close a diverged run");
  assert.match(ruling.sentence, /LIVE rendering/);
});

check("a gate with no seal is never approvable", () => {
  for (const seal of ["", "not-a-hash", "A".repeat(64), "a".repeat(63)]) {
    const ruling = readGateRuling("awaiting_approval", gate({ payload_sha256: seal }));
    assert.equal(
      ruling.approvable,
      false,
      `a gate sealed with ${JSON.stringify(seal)} was called approvable; there is nothing to bind the ruling to`,
    );
  }
});

check("a run that is not awaiting approval offers no ruling at all", () => {
  for (const status of ["running", "completed", "halted", "failed", ""]) {
    const ruling = readGateRuling(status, gate());
    assert.equal(ruling.code, "no_gate");
    assert.equal(ruling.approvable, false, `${status || "an empty status"} offered an approval`);
    assert.equal(ruling.rejectable, false);
  }
});

check("awaiting approval with no pending block is unreadable, never approvable", () => {
  for (const pending of [null, undefined, { ...gate(), step_id: "" }]) {
    const ruling = readGateRuling("awaiting_approval", pending as PendingGate | null);
    assert.equal(ruling.approvable, false);
    assert.equal(ruling.code, "malformed");
  }
});

check("exactly one shape is approvable", () => {
  // A future branch that quietly adds a second approvable outcome is the same
  // failure the control plane critic demonstrated, so the count is pinned.
  const cases: Array<[string, ReturnType<typeof readGateRuling>]> = [
    ["not waiting", readGateRuling("completed", gate())],
    ["no pending", readGateRuling("awaiting_approval", null)],
    ["diverged", readGateRuling("awaiting_approval", gate({ diverged: true }))],
    ["unsealed", readGateRuling("awaiting_approval", gate({ payload_sha256: "" }))],
    ["open", readGateRuling("awaiting_approval", gate())],
  ];
  const approvable = cases.filter(([, ruling]) => ruling.approvable);
  assert.equal(
    approvable.length,
    1,
    `expected exactly one approvable shape, got ${approvable.map(([name]) => name).join(", ")}`,
  );
  assert.equal(approvable[0][0], "open");
});

/* ------------------------------------------------------------------ */
/* The body that is actually sent                                       */
/* ------------------------------------------------------------------ */

check("an approval carries the seal that was displayed, and exactly one decision", () => {
  const pending = gate();
  const ruling = readGateRuling("awaiting_approval", pending);
  const body = approvalBody(ruling, pending, "approved");
  assert.deepEqual(body.decisions, { remember: "approved" });
  assert.equal(Object.keys(body.decisions).length, 1, "a ruling decides one step, the pending one");
  assert.equal(
    body.expected_payload_sha256,
    SEALED,
    "the approval must name the payload the person was shown, so the server can refuse it if the run has moved",
  );
});

check("a rejection carries no seal, so a moved run can always be closed", () => {
  const pending = gate({ diverged: true });
  const ruling = readGateRuling("awaiting_approval", pending);
  const body = approvalBody(ruling, pending, "rejected");
  assert.deepEqual(body.decisions, { remember: "rejected" });
  assert.equal(
    body.expected_payload_sha256,
    undefined,
    "a rejection executes nothing and must not be blocked by a seal that has already moved",
  );
});

check("no approval body can be built for a gate that is not approvable", () => {
  for (const pending of [gate({ diverged: true }), gate({ payload_sha256: "" })]) {
    const ruling = readGateRuling("awaiting_approval", pending);
    assert.throws(
      () => approvalBody(ruling, pending, "approved"),
      /refuses to build an approval/,
      "approvalBody handed back a body for a gate nothing may approve",
    );
  }
  const closed = readGateRuling("completed", gate());
  assert.throws(() => approvalBody(closed, gate(), "approved"), /refuses to build an approval/);
  assert.throws(() => approvalBody(closed, gate(), "rejected"), /refuses to build a rejection/);
});

/* ------------------------------------------------------------------ */
/* Law three: no number is invented from an absence                     */
/* ------------------------------------------------------------------ */

check("a number the route did not send is absent, never zero", () => {
  for (const absent of [undefined, null, "4", NaN, Infinity, {}]) {
    assert.equal(reportedNumber(absent).known, false, `${String(absent)} was read as a number`);
    assert.equal(reportedLabel(absent), "not reported");
  }
  assert.deepEqual(reportedNumber(0), { known: true, value: 0 });
  assert.equal(reportedLabel(0), "0", "a real zero is a measurement and must be shown");
});

check("a definition that does not parse reports no step count", () => {
  // describe_definition sends step_count 0 for an unparseable definition. That
  // zero is a default, not a measurement, and rendering it as "0 steps" states
  // a fact about a workflow nobody could read.
  const facts = readSummary({
    valid: false,
    error: "Step 'draft': unknown type 'nonsense'",
    step_count: 0,
    approval_steps: [],
    trigger_type: null,
    awaiting_dispatcher: false,
  });
  assert.equal(facts.parses, false);
  assert.equal(facts.stepCount, null, "an unparseable definition must not report a step count");
  assert.equal(
    facts.awaitingDispatcher,
    null,
    "awaiting_dispatcher is a default for an unparseable definition, not a report",
  );
  assert.match(facts.sentence, /does not parse/);
  assert.match(facts.sentence, /unknown type/);
  assert.ok(!/0 steps/.test(facts.sentence), "the default zero leaked into the sentence");
});

check("a parsed definition reports what the route sent and nothing more", () => {
  const facts = readSummary({
    valid: true,
    error: null,
    step_count: 3,
    approval_steps: ["remember"],
    trigger_type: "manual",
    awaiting_dispatcher: false,
  });
  assert.equal(facts.stepCount, 3);
  assert.deepEqual(facts.gatedSteps, ["remember"]);
  assert.equal(facts.trigger, "manual");
  assert.equal(facts.awaitingDispatcher, false);
  assert.match(facts.sentence, /3 steps/);
  assert.match(facts.sentence, /1 of them stops for a ruling \(remember\)/);
});

check("a summary missing its step_count says so rather than showing a number", () => {
  const facts = readSummary({ valid: true, approval_steps: [], trigger_type: "manual" });
  assert.equal(facts.stepCount, null);
  assert.match(facts.sentence, /a step count the route did not send/);
});

/* ------------------------------------------------------------------ */
/* Starting a run says what a run would do                              */
/* ------------------------------------------------------------------ */

check("starting a run names the steps that will stop for a ruling", () => {
  const facts = readSummary({
    valid: true,
    error: null,
    step_count: 2,
    approval_steps: ["remember", "draft"],
    trigger_type: "manual",
    awaiting_dispatcher: false,
  });
  const sentence = describeStart(facts, "draft");
  assert.match(sentence, /STOPS in front of remember, draft/);
  assert.match(sentence, /Nothing is written until you rule/);
});

check("a workflow with no effect steps is not described as gated", () => {
  const facts = readSummary({
    valid: true,
    error: null,
    step_count: 2,
    approval_steps: [],
    trigger_type: "manual",
    awaiting_dispatcher: false,
  });
  assert.match(describeStart(facts, "active"), /No step in this workflow writes anything/);
});

/* ------------------------------------------------------------------ */
/* The catalog parser refuses a shape it does not recognise             */
/* ------------------------------------------------------------------ */

check("the catalog parser returns null rather than a partial guess", () => {
  assert.equal(parseCatalog(null), null);
  assert.equal(parseCatalog({}), null);
  assert.equal(parseCatalog({ step_types: "council" }), null);
  assert.equal(parseCatalog({ step_types: [{ type: "council" }] }), null, "requires_approval missing");
  assert.equal(
    parseCatalog({ step_types: [{ type: "council", requires_approval: "yes" }] }),
    null,
    "requires_approval must be a boolean, not a truthy string",
  );
  const parsed = parseCatalog({
    step_types: [
      { type: "council", requires_approval: false, description: "A full Council run." },
      { type: "memory_write", requires_approval: true, description: "" },
    ],
    approval_required: true,
    dispatchable_triggers: ["manual"],
  });
  assert.equal(parsed?.length, 2);
  assert.equal(parsed?.[1].requires_approval, true);
});

/* ------------------------------------------------------------------ */
/* The composer sends what it shows                                     */
/* ------------------------------------------------------------------ */

function draft(over: Partial<StepDraft> = {}): StepDraft {
  return { key: "k1", id: "recall", type: "knowledge_search", body: "{{ input }}", rawConfig: "{}", ...over };
}

check("the composer refuses a malformed step rather than sending it", () => {
  assert.equal(buildDefinition([]).ok, false, "a workflow with no steps must not be sent");
  const badId = buildDefinition([draft({ id: "Recall" })]);
  assert.equal(badId.ok, false);
  const duplicate = buildDefinition([draft(), draft({ key: "k2" })]);
  assert.equal(duplicate.ok, false);
  const empty = buildDefinition([draft({ body: "   " })]);
  assert.equal(empty.ok, false);
});

check("the composer builds exactly the definition the parser expects", () => {
  const built = buildDefinition([
    draft(),
    draft({ key: "k2", id: "remember", type: "memory_write", body: "{{ recall }}" }),
  ]);
  assert.equal(built.ok, true);
  if (!built.ok) return;
  assert.deepEqual(built.definition, {
    version: 1,
    trigger: { type: "manual", config: {} },
    steps: [
      { id: "recall", type: "knowledge_search", config: { query: "{{ input }}" } },
      { id: "remember", type: "memory_write", config: { content: "{{ recall }}" } },
    ],
  });
});

check("an unknown step type gets a raw config editor, never a guessed field", () => {
  const built = buildDefinition([
    draft({ id: "novel", type: "something_new", rawConfig: '{"whatever": 1}' }),
  ]);
  assert.equal(built.ok, true);
  if (!built.ok) return;
  assert.deepEqual(built.definition.steps[0], {
    id: "novel",
    type: "something_new",
    config: { whatever: 1 },
  });
  const broken = buildDefinition([draft({ id: "novel", type: "something_new", rawConfig: "{oops" })]);
  assert.equal(broken.ok, false);
});

check("only earlier steps are offered as references", () => {
  const drafts = [draft(), draft({ key: "k2", id: "council" }), draft({ key: "k3", id: "remember" })];
  assert.deepEqual(availableReferences(drafts, 0), ["input"]);
  assert.deepEqual(availableReferences(drafts, 2), ["input", "recall", "council"]);
});

/* ------------------------------------------------------------------ */
/* The wire from the panel into the ladders                             */
/*                                                                     */
/* Everything above exercises pure functions, which is right and is not */
/* enough. A critic beat the learning panel on 2026-09-10 by leaving    */
/* its ladder untouched and changing the one adapter that feeds it, and */
/* every ladder check still passed. So the adapter is read from source  */
/* here, the same way scripts/learning-check.ts reads asRead.           */
/* ------------------------------------------------------------------ */

const PANEL = readFileSync(join(HERE, "..", "components/control/WorkflowDoor.tsx"), "utf8");

check("the panel's asRead maps a failed read to failed, never to a count", () => {
  const file = ts.createSourceFile(
    "WorkflowDoor.tsx",
    PANEL,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const decls: ts.FunctionDeclaration[] = [];
  const walk = (node: ts.Node) => {
    if (ts.isFunctionDeclaration(node) && node.name && node.name.text === "asRead") {
      decls.push(node);
    }
    ts.forEachChild(node, walk);
  };
  walk(file);
  assert.equal(
    decls.length,
    1,
    `WorkflowDoor must declare asRead exactly once; found ${decls.length}. Without it this check cannot find the wire into the ladders`,
  );

  const text = decls[0].getText();
  const failed = /if\s*\(load\.state === "failed"\)\s*return\s*\{[^}]*\}/.exec(text);
  assert.ok(failed, 'asRead has no branch returning on a "failed" read');
  assert.match(
    failed[0],
    /state:\s*"failed"/,
    `asRead's failed branch is ${failed[0]}, which does not carry state "failed". A failed read presented as a count is the one way this panel can lie`,
  );
  assert.ok(
    !/count:/.test(failed[0]),
    `asRead's failed branch carries a count (${failed[0]}). A count is a claim about the list, and a read that failed supports no such claim`,
  );
  assert.match(
    text,
    /state:\s*"ok",\s*count:\s*load\.value\.length/,
    "asRead's ok branch does not report the actual row count, so the number on the panel is not the number the route returned",
  );
  assert.match(
    PANEL,
    /readListVerdict\(asRead\(list\)\)/,
    "the panel no longer feeds asRead into readListVerdict, so the ladder this file guards is not the one it renders",
  );
  assert.match(
    PANEL,
    /readCatalogVerdict\(asRead\(catalog\)\)/,
    "the panel no longer feeds asRead into readCatalogVerdict",
  );
});

check("the panel renders an approve control only under gate.approvable", () => {
  // The button is guarded by the ladder rather than by a status string read in
  // the component, which is how a diverged gate would sprout an approve button
  // without any ladder check noticing.
  const approve = /\{gate\.approvable && pending \? \(/.exec(PANEL);
  assert.ok(
    approve,
    "the approve control is no longer gated on gate.approvable. Any other condition is a second source of truth about when a payload may be executed",
  );
  assert.ok(
    !/decisions:\s*\{/.test(PANEL),
    "the panel builds an approval body inline instead of through approvalBody, which is where the one-key and seal rules are proved",
  );
  assert.match(
    PANEL,
    /approvalBody\(gate, pending, decision\)/,
    "the panel no longer routes its ruling through approvalBody",
  );
});

check("the panel offers no bulk or automatic ruling", () => {
  // CLAUDE.md: WRITE and HIGH_IMPACT tools require human approval, and
  // materialize and spawn never auto run effects. A control that decides more
  // than the one gate a person is looking at is the same defect in a new place.
  for (const banned of [
    /approveAll/i,
    /autoApprove/i,
    /\bapprove_all\b/i,
    /setInterval\([^)]*approve/i,
  ]) {
    assert.ok(
      !banned.test(PANEL),
      `the panel carries ${banned}, which would rule on a gate without a person looking at it`,
    );
  }
});

check("the door is mounted where a person can reach it", () => {
  const page = readFileSync(join(HERE, "..", "app/control/workflows/page.tsx"), "utf8");
  assert.match(
    page,
    /<WorkflowDoor \/>/,
    "/control/workflows no longer renders WorkflowDoor, so the engine is unreachable again",
  );
  assert.match(
    PANEL,
    /\/workflows\/step-types/,
    "the panel no longer reads the step catalog, so its approval semantics would be a local guess",
  );
});

check("the legibility floor holds in this door's own files", () => {
  // The same thresholds scripts/control-check.ts computes against #04070d:
  // under 11px is unreadable on a phone, and white at 45% or less is below
  // 4.5:1. This door is not in that file's CONTROL_TREE until it is mounted in
  // the shell, so the floor is asserted here too rather than assumed.
  const files = [
    "components/control/WorkflowDoor.tsx",
    "components/control/workflow-honesty.ts",
    "app/control/workflows/page.tsx",
  ];
  const below: Array<{ pattern: RegExp; why: string }> = [
    { pattern: /text-\[(?:[0-9]|10)px\]/g, why: "under 11px is unreadable on a phone" },
    {
      pattern: /text-white\/(?:[0-9]|[1-3][0-9]|4[0-5])\b/g,
      why: "white at 45% or less is below 4.5:1 on the ACX void",
    },
    { pattern: /text-\[#526979\]/g, why: "#526979 is 3.49:1 on the ACX void" },
  ];
  const offences: string[] = [];
  for (const relative of files) {
    const source = readFileSync(join(HERE, "..", relative), "utf8");
    assert.ok(source.length > 200, `${relative} is too small to be the real file`);
    source.split("\n").forEach((line, index) => {
      for (const { pattern, why } of below) {
        for (const hit of line.matchAll(pattern)) {
          offences.push(`${relative}:${index + 1} ${hit[0]} (${why})`);
        }
      }
    });
  }
  assert.deepEqual(offences, [], `\n${offences.join("\n")}`);
});

check("every text input and textarea in the door carries a label", () => {
  // A placeholder is not a label: it disappears the moment anything is typed
  // and a screen reader is not required to announce it.
  // Three ways a label can name its field on this panel, and all three are
  // real: a literal id, a template literal built from a row key, and a bare
  // identifier holding one. Only the first was recognised when this check was
  // first written, and it correctly failed on the third, which is what a guard
  // that reads real files is for.
  const literals = new Set([...PANEL.matchAll(/htmlFor="([^"]+)"/g)].map((m) => m[1]));
  const templates = new Set([...PANEL.matchAll(/htmlFor=\{`([^`]+)`\}/g)].map((m) => m[1]));
  const identifiers = new Set(
    [...PANEL.matchAll(/htmlFor=\{([A-Za-z_$][\w$]*)\}/g)].map((m) => m[1]),
  );
  let fields = 0;
  const unlabelled: string[] = [];
  const tags = [
    ...PANEL.matchAll(/<input\b[\s\S]*?\/>/g),
    ...PANEL.matchAll(/<textarea\b[\s\S]*?\/>/g),
    ...PANEL.matchAll(/<select\b[\s\S]*?>/g),
  ];
  for (const tag of tags) {
    fields += 1;
    const element = tag[0];
    const literal = /\bid="([^"]+)"/.exec(element)?.[1];
    const template = /\bid=\{`([^`]+)`\}/.exec(element)?.[1];
    const identifier = /\bid=\{([A-Za-z_$][\w$]*)\}/.exec(element)?.[1];
    const labelled =
      /\baria-label(?:ledby)?=/.test(element) ||
      (literal !== undefined && literals.has(literal)) ||
      (template !== undefined && templates.has(template)) ||
      (identifier !== undefined && identifiers.has(identifier));
    if (!labelled) unlabelled.push(element.slice(0, 100));
  }
  assert.deepEqual(unlabelled, [], `\n${unlabelled.join("\n")}`);
  assert.ok(fields >= 6, `only ${fields} fields found; the scan cannot be trusted`);
});

/* ------------------------------------------------------------------ */
/* Added 2026-09-10, after an adversary beat all 31 checks above.       */
/*                                                                     */
/* Two holes, both in coverage rather than in the shipped code. The     */
/* pattern is the same one that produced check 26: a ladder can be      */
/* perfect and a single line in the component can still hand it a lie,  */
/* so every branch that classifies a read now has an assertion on it.  */
/* ------------------------------------------------------------------ */

check("a list payload that is not an array is a failed read, never a count", () => {
  // THE HOLE: deleting the `!Array.isArray(listed.data)` branch from loadTop
  // left all 31 checks, tsc and control-check exiting 0, while a 200 carrying a
  // paginated envelope rendered "WORKFLOWS PRESENT" in a good tone with an
  // undefined count. Measured, not argued.
  const load = /const loadTop = useCallback\([\s\S]*?\n  \}, \[\]\);/.exec(PANEL);
  assert.ok(load, "WorkflowDoor no longer declares loadTop, so this check cannot find the list read");
  const branch = /else if \(!Array\.isArray\(listed\.data\)\) \{[\s\S]*?\n    \}/.exec(load[0]);
  assert.ok(
    branch,
    "loadTop no longer refuses a list payload that is not an array. A 200 whose body is an object would then be counted, and an object has no length",
  );
  assert.match(
    branch[0],
    /setList\(\{ state: "failed"/,
    `loadTop's non-array branch is ${branch[0]}, which does not set a failed read. A body that is not a list is an unreadable answer, not an empty list`,
  );
  assert.ok(
    !/state: "ok"/.test(branch[0]),
    `loadTop's non-array branch carries an ok state (${branch[0]})`,
  );
});

check("a count that is not a whole number is unreadable, never populated", () => {
  // The second half of the same hole: the ladder itself let any non-finite
  // count fall through to `populated`, so it depended on its one caller being
  // correct. Now it refuses on its own.
  for (const bad of [null, undefined, Number.NaN, 1.5, -1, Number.POSITIVE_INFINITY, "3"]) {
    const verdict = readListVerdict({ state: "ok", count: bad } as unknown as WorkflowRead);
    assert.equal(
      verdict.code,
      "unreadable",
      `a count of ${String(bad)} produced ${verdict.code}: "${verdict.sentence}"`,
    );
    assert.notEqual(verdict.tone, "good", `a count of ${String(bad)} was drawn in a good tone`);
  }
  // and a real zero is still a measurement rather than an absence
  assert.equal(readListVerdict({ state: "ok", count: 0 }).code, "empty");
  assert.equal(readListVerdict({ state: "ok", count: 2 }).code, "populated");
});

check("run history is only ever rendered for the workflow it was read for", () => {
  // THE HOLE: one `runs` state is shared by every row and was not bound to the
  // workflow it came from, so opening workflow B while A was open rendered A's
  // runs, A's gate and A's approve button inside B's card for one commit. The
  // server 404s a ruling sent that way, so nothing was written, but the ruling
  // was still given over a payload belonging to something else.
  assert.match(
    PANEL,
    /const \[runsFor, setRunsFor\] = useState<string \| null>\(null\)/,
    "the panel no longer tracks which workflow `runs` was read for",
  );
  assert.match(
    PANEL,
    /runs=\{runsFor === row\.id \? runs : \{ state: "loading" \}\}/,
    "RunHistory is handed `runs` without checking it was read for this row. That is how one workflow's gate renders inside another's card",
  );
  assert.match(
    PANEL,
    /setRunsFor\(workflowId\);/,
    "loadRuns no longer records which workflow it is reading, so the binding above can never match",
  );
  // and no selection must not fabricate a successful read of zero runs
  const none = /if \(!selectedId\) \{[\s\S]*?\n      return;\n    \}/.exec(PANEL);
  assert.ok(none, "the panel no longer has a no-selection branch for the run history");
  assert.ok(
    !/setRuns\(\{ state: "ok"/.test(none[0]),
    `with nothing selected the panel sets ${none[0]}, an ok read of a route it never called. RunHistory renders that as "This workflow has never run"`,
  );
});

console.log(`\n${checks} workflow door checks passed`);
