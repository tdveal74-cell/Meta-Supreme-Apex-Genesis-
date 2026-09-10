/**
 * Proof for the decision record's verdict ladder, its refusals, and the two
 * surfaces that write to it. No test framework: node:assert and a plain process
 * exit code, the same shape as scripts/learning-check.ts and
 * scripts/control-check.ts. Run from apps/web:
 *
 *   node --experimental-strip-types scripts/decisions-check.ts
 *
 * WHY THIS FILE EXISTS
 *
 * The decision record is the Council's whole point: a person rules, and the
 * ruling can be read back. app/api/v1/decisions.py has carried that since it
 * was written and, measured on commit 32883cf, no component under apps/web
 * called any of its five operations. handleDecision on the deliberate page was
 * a console.info.
 *
 * A panel over those routes can lie in four ways, and typecheck catches none of
 * them because none of them is a type error:
 *
 *   1. A FAILED read drawn as an EMPTY record. This is the estate's single most
 *      repeated defect and the one a critic used against the control plane on
 *      2026-09-09 and against the learning panel on 2026-09-10.
 *   2. An UNKNOWN drawn as a NEGATIVE. "this exchange is not on the record" is
 *      a claim, and it is unavailable whenever the record could not be read.
 *   3. A field TRUNCATED to fit the route's cap and stored under the human's
 *      name as though they wrote it.
 *   4. A request for another Council round FILED AS A DECISION, because
 *      update_decision advances an open decision to "decided" by itself when
 *      chosen_option arrives with no status.
 *
 * Every one of those is decided by a pure function in
 * components/council/decision-record.ts, and the checks below feed those
 * functions directly. The last group binds the pure functions to the two
 * surfaces that actually call them, because the learning arc proved a ladder
 * nobody is standing on holds no weight: that panel's ladder was never wrong
 * and one line in the adapter feeding it rendered an unread store as empty
 * while every check passed.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import {
  COUNCIL_OPTIONS,
  LONG_TEXT_MAX,
  QUESTION_MAX,
  describeWriteOutcome,
  isRecorded,
  parseDecisionList,
  parseDecisionRow,
  prepareCreate,
  prepareRuling,
  readDecisionsVerdict,
  rulingFor,
  rulingForOption,
  summarizeStatuses,
  trackedState,
  writeHeadline,
  type DecisionRow,
  type DecisionsRead,
  type DecisionVerdict,
  type WriteOutcome,
} from "../components/council/decision-record.ts";
import type { DecisionPackage } from "../lib/council-types.ts";

const HERE = dirname(fileURLToPath(import.meta.url));

let checks = 0;
function check(name: string, run: () => void): void {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

function row(overrides: Partial<DecisionRow> = {}): DecisionRow {
  return {
    id: "d1",
    question: "Which provider?",
    options: ["AWS", "GCP"],
    recommendation: "GCP.",
    chosenOption: null,
    outcome: null,
    outcomeNotes: null,
    status: "open",
    projectId: null,
    origin: "manual",
    messageId: null,
    conversationId: null,
    agentsConsulted: null,
    createdAt: "2026-09-10T00:00:00+00:00",
    updatedAt: "2026-09-10T00:00:00+00:00",
    ...overrides,
  };
}

const LOCKED: DecisionsRead = { state: "locked" };
const FAILED: DecisionsRead = {
  state: "failed",
  detail: "the decisions route answered 500",
};
const OK_EMPTY: DecisionsRead = { state: "ok", rows: [], malformed: 0 };
const OK_FULL: DecisionsRead = {
  state: "ok",
  rows: [row({ id: "a", status: "decided" }), row({ id: "b", status: "open" })],
  malformed: 0,
};

/* ------------------------------------------------------------------ */
/* 1. The load bearing law: a failed read is never an empty record      */
/* ------------------------------------------------------------------ */

function refuseEmptyAndGood(verdict: DecisionVerdict, why: string): void {
  assert.equal(verdict.code, "unreadable", why);
  assert.notEqual(verdict.code, "empty", "a failed read must never read as an empty record");
  assert.notEqual(verdict.tone, "good", "a failed read must never take a good tone");
  assert.match(verdict.sentence, /failed read, not an empty record/);
}

check("a failed list read is never reported as an empty record", () => {
  refuseEmptyAndGood(
    readDecisionsVerdict(FAILED),
    "the read failed, so no claim about emptiness is available",
  );
});

check("the failing detail reaches the operator", () => {
  assert.match(
    readDecisionsVerdict(FAILED).sentence,
    /answered 500/,
    "the operator needs the actual failure, not a shrug",
  );
});

check("no session token is locked, not a failed read and not an empty record", () => {
  // No request was sent, so calling this a failure would invent one and calling
  // it empty would invent a record.
  const verdict = readDecisionsVerdict(LOCKED);
  assert.equal(verdict.code, "locked");
  assert.notEqual(verdict.code, "unreadable");
  assert.notEqual(verdict.code, "empty");
  assert.notEqual(verdict.tone, "good");
});

check("every read state resolves and only a successful read may claim empty or present", () => {
  // The whole ladder walked rather than sampled, so a branch keyed on the wrong
  // state cannot hide between two checks that each pass on their own.
  const states: Array<[string, DecisionsRead]> = [
    ["locked", LOCKED],
    ["failed", FAILED],
    ["ok-empty", OK_EMPTY],
    ["ok-full", OK_FULL],
  ];
  const seen = new Set<string>();
  for (const [name, read] of states) {
    const verdict = readDecisionsVerdict(read);
    seen.add(verdict.code);
    assert.ok(verdict.label.length > 0, `${name} produced no label`);
    assert.ok(verdict.sentence.length > 0, `${name} produced no sentence`);
    if (read.state !== "ok") {
      assert.notEqual(
        verdict.code,
        "empty",
        `${name} reads as an EMPTY record while the record was not read. An unread record is not an empty one, and this is the only way this panel can lie about what has been decided`,
      );
      assert.notEqual(
        verdict.code,
        "present",
        `${name} reads as a POPULATED record while the record was not read, which claims rows nobody counted`,
      );
      assert.notEqual(verdict.tone, "good", `${name} reads in the good tone without a read`);
    }
    if (verdict.code === "empty") {
      assert.ok(
        read.state === "ok" && read.rows.length === 0,
        `${name} reads as an empty record, and only a successful read with no rows supports that`,
      );
    }
  }
  assert.equal(seen.size, 4, "a verdict code nothing can reach is a branch nobody guards");
});

check("a present record counts only the statuses it actually read", () => {
  const verdict = readDecisionsVerdict(OK_FULL);
  assert.equal(verdict.code, "present");
  assert.equal(verdict.tone, "good");
  assert.match(verdict.sentence, /1 decided/);
  assert.match(verdict.sentence, /1 still open/);
  assert.match(
    verdict.sentence,
    /not a claim that anything acted on it/,
    "a record of a ruling is not a record of an effect, and the panel has to say so",
  );
});

check("a status the route did not send is never folded into open", () => {
  const tally = summarizeStatuses([
    row({ id: "a", status: null }),
    row({ id: "b", status: "open" }),
    row({ id: "c", status: "something-new" }),
  ]);
  assert.equal(tally.unstated, 1, "an absent status must be counted as absent");
  assert.equal(tally.open, 1, "an absent status was counted as open, which invents a fact");
  assert.equal(tally.other, 1);
  const verdict = readDecisionsVerdict({
    state: "ok",
    rows: [row({ id: "a", status: null })],
    malformed: 0,
  });
  assert.match(verdict.sentence, /status the route did not send/);
});

check("refused entries are reported rather than dropped in silence", () => {
  const verdict = readDecisionsVerdict({ state: "ok", rows: [], malformed: 2 });
  assert.equal(verdict.code, "empty");
  assert.match(verdict.sentence, /2 entries came back without a usable id/);
});

/* ------------------------------------------------------------------ */
/* 2. The parser refuses rather than inventing                          */
/* ------------------------------------------------------------------ */

check("a payload that is not a list is a failed read, not an empty record", () => {
  // Returning {rows: []} here is the exact collapse this module exists to stop:
  // the caller would have no way to tell "no decisions" from "not a list".
  assert.equal(parseDecisionList({ detail: "Not authenticated" }), null);
  assert.equal(parseDecisionList(null), null);
  assert.equal(parseDecisionList("[]"), null);
  const parsed = parseDecisionList([]);
  assert.ok(parsed, "an actual empty array is a real empty record and must parse");
  assert.equal(parsed.rows.length, 0);
});

check("a field the route did not send stays absent and is never defaulted", () => {
  const parsed = parseDecisionRow({ id: "d9" });
  assert.ok(parsed);
  assert.equal(parsed.options, null, "an absent option list must not become an empty list");
  assert.equal(parsed.status, null, "an absent status must not become open");
  assert.equal(parsed.question, null);
  assert.equal(parsed.chosenOption, null);
  assert.equal(parsed.origin, null);
});

check("a row with no usable id is refused and counted", () => {
  const parsed = parseDecisionList([{ id: "ok" }, { question: "no id" }, 7, null]);
  assert.ok(parsed);
  assert.equal(parsed.rows.length, 1);
  assert.equal(parsed.malformed, 3);
});

check("council metadata is read from metadata, not guessed", () => {
  const parsed = parseDecisionRow({
    id: "d1",
    metadata: {
      origin: "council",
      message_id: "m1",
      conversation_id: "c1",
      agents_consulted: ["Oracle", "Skeptic"],
    },
  });
  assert.ok(parsed);
  assert.equal(parsed.origin, "council");
  assert.equal(parsed.messageId, "m1");
  assert.deepEqual(parsed.agentsConsulted, ["Oracle", "Skeptic"]);
  const mixed = parseDecisionRow({ id: "d2", metadata: { agents_consulted: ["a", 3] } });
  assert.ok(mixed);
  assert.equal(
    mixed.agentsConsulted,
    null,
    "a list that lost entries to a filter is not the list the route sent",
  );
});

/* ------------------------------------------------------------------ */
/* 3. Unknown is never drawn as a negative                              */
/* ------------------------------------------------------------------ */

check("whether an exchange is on the record is unknown unless the record was read", () => {
  for (const read of [LOCKED, FAILED]) {
    assert.equal(
      trackedState("m1", read),
      "unknown",
      'a record that was not read cannot say an exchange is "not on the record"; that invites a duplicate',
    );
  }
  assert.equal(trackedState("m1", OK_EMPTY), "untracked");
  assert.equal(
    trackedState("m1", {
      state: "ok",
      rows: [row({ id: "d1", origin: "council", messageId: "m1" })],
      malformed: 0,
    }),
    "tracked",
  );
});

/* ------------------------------------------------------------------ */
/* 4. Nothing is reshaped to fit the route                              */
/* ------------------------------------------------------------------ */

function pkg(overrides: Partial<DecisionPackage> = {}): DecisionPackage {
  return {
    run_id: "sim_abc",
    timestamp: "2026-09-10T00:00:00+00:00",
    mode: "simulated",
    question: "Should we ship the pilot?",
    plurality_view: "Ship a narrow pilot.",
    key_reasons: [],
    strongest_dissent: [],
    confidence_range: "62 to 74",
    unresolved_unknowns: [],
    open_questions: [],
    ...overrides,
  };
}

check("an over-length question is refused, never trimmed to fit", () => {
  const long = "x".repeat(QUESTION_MAX + 1);
  const prepared = prepareCreate(pkg({ question: long }));
  assert.equal(prepared.ok, false);
  assert.ok(!prepared.ok);
  assert.match(prepared.reason, /2001 characters/);
  assert.match(prepared.reason, /Nothing was sent and nothing was shortened/);
});

check("an over-length note is refused, never trimmed to fit", () => {
  const prepared = prepareRuling(rulingForOption("A", "y".repeat(LONG_TEXT_MAX + 1), "decided"));
  assert.equal(prepared.ok, false);
  assert.ok(!prepared.ok);
  assert.match(prepared.reason, /Nothing was sent and nothing was shortened/);
});

check("the record carries the run mode, so a simulated run cannot read as a real one", () => {
  const prepared = prepareCreate(pkg());
  assert.ok(prepared.ok);
  assert.match(
    prepared.body.recommendation,
    /mode simulated/,
    "a record that does not say the run was simulated reads later as nine agents having deliberated",
  );
  assert.match(prepared.body.recommendation, /sim_abc/, "the run id has to survive too");
  assert.match(prepared.body.recommendation, /Ship a narrow pilot\./);
  assert.deepEqual(prepared.body.options, [...COUNCIL_OPTIONS]);
  assert.equal(prepared.body.question, "Should we ship the pilot?");
});

check("a package with no question is refused rather than recorded as untitled", () => {
  const prepared = prepareCreate(pkg({ question: "   " }));
  assert.ok(!prepared.ok);
  assert.match(prepared.reason, /no question/);
});

/* ------------------------------------------------------------------ */
/* 5. Asking for another round is not a decision                        */
/* ------------------------------------------------------------------ */

check("every ruling carries an explicit status, because the route defaults one", () => {
  // update_decision advances an open decision to "decided" whenever
  // chosen_option arrives with no status, so an omitted key is a decision the
  // human did not make.
  const rulings = [
    rulingFor({ choice: "A" }),
    rulingFor({ choice: "B", modification: "trim scope" }),
    rulingFor({ choice: "C", alternative: "do nothing" }),
    rulingFor({ choice: "D", focus: "the cost line" }),
  ];
  for (const ruling of rulings) {
    const prepared = prepareRuling(ruling);
    assert.ok(prepared.ok);
    assert.ok(
      Object.prototype.hasOwnProperty.call(prepared.body, "status"),
      `${ruling.chosenOption} sends no status, so the route decides for the human`,
    );
  }
});

check("choice D is recorded as still open, not as a final call", () => {
  const ruling = rulingFor({ choice: "D", focus: "the cost line" });
  assert.equal(
    ruling.status,
    "open",
    "asking the Council to look again is the opposite of a final call, and filing it as decided closes a decision nobody made",
  );
  assert.match(ruling.statusReason, /not a final call/);
  const prepared = prepareRuling(ruling);
  assert.ok(prepared.ok);
  assert.equal(prepared.body.status, "open");
});

check("choices A, B and C are recorded as decided", () => {
  assert.equal(rulingFor({ choice: "A" }).status, "decided");
  assert.equal(rulingFor({ choice: "B", modification: "x" }).status, "decided");
  assert.equal(rulingFor({ choice: "C", alternative: "x" }).status, "decided");
});

check("a blank note is absent from the body rather than stored as an empty note", () => {
  const blank = rulingFor({ choice: "B", modification: "   " });
  assert.equal(blank.note, null);
  const prepared = prepareRuling(blank);
  assert.ok(prepared.ok);
  assert.ok(
    !Object.prototype.hasOwnProperty.call(prepared.body, "outcome_notes"),
    "an empty string sent as outcome_notes is a note the human did not write",
  );

  const written = rulingFor({ choice: "B", modification: "  keep the gate  " });
  const preparedWritten = prepareRuling(written);
  assert.ok(preparedWritten.ok);
  assert.equal(preparedWritten.body.outcome_notes, "keep the gate");
});

/* ------------------------------------------------------------------ */
/* 6. A half written ruling is never described as recorded              */
/* ------------------------------------------------------------------ */

check("only the recorded outcome counts as recorded", () => {
  const ruling = rulingFor({ choice: "A" });
  const outcomes = [
    { kind: "idle" } as const,
    { kind: "locked" } as const,
    { kind: "refused", reason: "too long" } as const,
    { kind: "sending", step: "create" } as const,
    { kind: "create-failed", detail: "the route answered 500" } as const,
    { kind: "rule-failed", decisionId: "d1", detail: "the route answered 500" } as const,
    { kind: "recorded", decisionId: "d1", ruling } as const,
  ];
  let recorded = 0;
  for (const outcome of outcomes) {
    if (isRecorded(outcome)) recorded += 1;
    else {
      assert.ok(
        !/^Recorded as decision/.test(describeWriteOutcome(outcome)),
        `${outcome.kind} describes itself as recorded and it is not`,
      );
    }
  }
  assert.equal(recorded, 1, "exactly one outcome means the ruling reached the record");
});

check("a POST that landed and a PATCH that did not is drawn as half written", () => {
  const sentence = describeWriteOutcome({
    kind: "rule-failed",
    decisionId: "d1",
    detail: "the decision route answered 500",
  });
  assert.match(sentence, /Half recorded/);
  assert.match(sentence, /was NOT written/);
  assert.match(sentence, /answered 500/);
});

check("a locked write says no request was sent at all", () => {
  const sentence = describeWriteOutcome({ kind: "locked" });
  assert.match(sentence, /nothing was sent/);
  assert.match(sentence, /not recorded anywhere/);
});

/* ------------------------------------------------------------------ */
/* 7. The wire from the surfaces into the pure functions                */
/* ------------------------------------------------------------------ */

/*
 * WHY THESE LAST CHECKS EXIST.
 *
 * Everything above exercises the pure module in isolation, which is right and is
 * not enough. scripts/learning-check.ts records exactly this hole being found on
 * 2026-09-10: the ladder was never wrong, and one line in the adapter feeding it
 * rendered a store it had failed to read as empty, in the good tone, with every
 * check passing and tsc and next build exiting 0.
 *
 * Read from source rather than executed, because these live inside React
 * components and this runner imports no React.
 */

const PANEL_PATH = join(HERE, "..", "components/council/DecisionRecordPanel.tsx");
const DELIBERATE_PATH = join(HERE, "..", "app/council/deliberate/page.tsx");
const PANEL = readFileSync(PANEL_PATH, "utf8");
const DELIBERATE = readFileSync(DELIBERATE_PATH, "utf8");

function sourceFile(path: string, text: string): ts.SourceFile {
  return ts.createSourceFile(path, text, ts.ScriptTarget.Latest, true, ts.ScriptKind.TSX);
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

/**
 * The names of everything CALLED inside a subtree, as call expressions rather
 * than as text. control-check.ts records four ways a text slice was beaten in
 * one evening, one of them a single string literal carrying every token the
 * check looked for. A string is not a CallExpression, so none of that works
 * here.
 */
function callNames(root: ts.Node): Set<string> {
  const names = new Set<string>();
  for (const node of collect(root, (n) => ts.isCallExpression(n))) {
    const call = node as ts.CallExpression;
    if (ts.isIdentifier(call.expression)) names.add(call.expression.text);
    else if (ts.isPropertyAccessExpression(call.expression)) {
      names.add(call.expression.name.text);
    }
  }
  return names;
}

/** Every literal string a subtree contains, template pieces included. */
function literals(root: ts.Node): string[] {
  return collect(
    root,
    (n) =>
      ts.isStringLiteral(n) ||
      ts.isNoSubstitutionTemplateLiteral(n) ||
      ts.isTemplateHead(n) ||
      ts.isTemplateMiddle(n) ||
      ts.isTemplateTail(n),
  ).map((n) => (n as ts.LiteralLikeNode).text ?? "");
}

function functionNamed(file: ts.SourceFile, name: string): ts.Node {
  const found = collect(
    file,
    (n) =>
      (ts.isFunctionDeclaration(n) && !!n.name && n.name.text === name) ||
      (ts.isVariableDeclaration(n) &&
        ts.isIdentifier(n.name) &&
        n.name.text === name &&
        !!n.initializer),
  );
  assert.equal(
    found.length,
    1,
    `expected exactly one declaration of ${name}, found ${found.length}. A second one means this check cannot tell which it is reading`,
  );
  return found[0];
}

check("the panel adapter maps a failed read to failed, never to rows", () => {
  const file = sourceFile(PANEL_PATH, PANEL);
  const adapter = functionNamed(file, "asRead");

  const returns = collect(adapter, (n) => ts.isReturnStatement(n)) as ts.ReturnStatement[];
  assert.ok(returns.length >= 3, "asRead no longer has a branch per read state");

  const failedBranch = returns.find((statement) => {
    let at: ts.Node | undefined = statement.parent;
    while (at && at !== adapter) {
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
    `asRead's failed branch returns ${failedText}, which does not carry state "failed". A failed read presented as rows is the one way this panel can lie`,
  );
  assert.ok(
    !/rows:/.test(failedText),
    `asRead's failed branch carries rows (${failedText}). Rows are a claim about the record, and a read that failed supports no such claim`,
  );

  const okBranch = returns.find((statement) => /state:\s*"ok"/.test(statement.getText()));
  assert.ok(okBranch, "asRead has no ok branch");
  assert.match(
    okBranch!.getText(),
    /rows:\s*load\.rows/,
    "asRead's ok branch does not report the rows the route returned, so what is drawn is not what was read",
  );

  assert.match(
    PANEL,
    /readDecisionsVerdict\(\s*asRead\(/,
    "the panel no longer feeds asRead into readDecisionsVerdict, so the ladder this file guards is not the one the panel renders",
  );
  assert.match(
    PANEL,
    /trackedState\(/,
    "the panel no longer asks trackedState whether an exchange is on the record",
  );
});

check("the panel refuses a list payload it cannot read instead of drawing an empty record", () => {
  const file = sourceFile(PANEL_PATH, PANEL);
  const read = functionNamed(file, "read");
  const names = callNames(read);
  assert.ok(
    names.has("parseDecisionList"),
    "the panel parses the list payload itself, so a non-list body could be read as no decisions",
  );
  assert.match(
    read.getText(),
    /parsed === null[\s\S]{0,400}state:\s*"failed"/,
    "an unparseable payload does not set a failed state, so the panel would draw an empty record over an unknown one",
  );
});

check("the panel reaches every operation on the decision record", () => {
  const file = sourceFile(PANEL_PATH, PANEL);
  const found = literals(file);
  for (const needle of ["/decisions", "/decisions/", "/decisions/from-message"]) {
    assert.ok(
      found.some((text) => text.includes(needle)),
      `the panel no longer names ${needle}, so that route has no caller again`,
    );
  }
  for (const method of ["PATCH"]) {
    assert.ok(found.includes(method), `the panel no longer sends ${method}`);
  }
  // The picker exists so nobody has to paste an assistant message id by hand.
  assert.ok(
    found.some((text) => text.includes("/conversations")),
    "the exchange picker no longer reads conversations, so from-message is back to wanting a pasted id",
  );
});

check("the deliberate page writes the ruling instead of logging it", () => {
  const file = sourceFile(DELIBERATE_PATH, DELIBERATE);
  const handler = functionNamed(file, "handleDecision");
  const names = callNames(handler);

  assert.ok(names.has("fetch"), "handleDecision sends no request, so no ruling reaches the record");
  assert.ok(
    !names.has("info") && !names.has("log"),
    "handleDecision is back to writing the ruling to the console, which is where this door started",
  );
  for (const required of ["prepareCreate", "rulingFor", "prepareRuling"]) {
    assert.ok(
      names.has(required),
      `handleDecision does not call ${required}, so a body is being assembled somewhere this file cannot check`,
    );
  }

  const found = literals(handler);
  assert.ok(found.includes("POST"), "handleDecision no longer creates the decision");
  assert.ok(found.includes("PATCH"), "handleDecision no longer records the call on it");
  assert.ok(
    found.some((text) => text.includes("/decisions")),
    "handleDecision no longer names the decisions route",
  );
  assert.match(
    handler.getText(),
    /JSON\.stringify\(\s*patch\.body\s*\)/,
    "the PATCH body is not the one prepareRuling built, so the explicit status it exists to carry may not be sent",
  );
  assert.match(
    handler.getText(),
    /kind:\s*"rule-failed"/,
    "a POST that landed with a PATCH that did not is no longer its own outcome, so a half written ruling would round to success or to failure",
  );
  assert.match(
    handler.getText(),
    /kind:\s*"locked"/,
    "a missing session token is no longer its own outcome, so no request sent would read like a request that failed",
  );
});

check("the decision record is mounted where a person can reach it", () => {
  const page = readFileSync(join(HERE, "..", "app/control/decisions/page.tsx"), "utf8");
  assert.match(
    page,
    /<DecisionRecordPanel \/>/,
    "/control/decisions no longer renders DecisionRecordPanel, so the panel is a component nothing mounts",
  );
  assert.match(
    DELIBERATE,
    /href="\/control\/decisions"/,
    "the deliberate page no longer links to the record, so a person who rules has no way to look at it",
  );
});

check("this file is reading the real sources rather than an empty string", () => {
  // A guard whose extractor silently returns nothing passes everything.
  assert.ok(PANEL.length > 4000, `the panel source read as ${PANEL.length} characters`);
  assert.ok(DELIBERATE.length > 2000, `the deliberate page read as ${DELIBERATE.length} characters`);
  assert.match(PANEL, /DecisionRecordPanel/);
  assert.match(DELIBERATE, /handleDecision/);
});

/* ------------------------------------------------------------------ */
/* Added 2026-09-10, after an adversary beat every check above.         */
/* ------------------------------------------------------------------ */

check("the HTTP status branch of the read is a failed read, never an empty record", () => {
  // THE HOLE: every assertion above guarded `asRead` and the ladder, and the
  // line that classifies the HTTP status sits ONE LINE ABOVE the guarded
  // adapter. Replacing the !response.ok body with an ok read of zero rows left
  // this file at exit 0 with 29 ok lines, tsc at 0 and control-check at 0, while
  // a route answering 500 rendered "DECISION RECORD EMPTY / Nothing has been
  // recorded on this account". Measured by the adversary, not argued.
  const fn = /const read = useCallback\([\s\S]*?\n  \}, \[\]\);/.exec(PANEL);
  assert.ok(fn, "DecisionRecordPanel no longer declares `read`, so this check cannot find the list read");
  const branch = /if \(!response\.ok\) \{[\s\S]*?\n      \}/.exec(fn[0]);
  assert.ok(
    branch,
    "the read no longer classifies a non-2xx status. Without it a 500 body falls into the parser and an error envelope reads as no rows",
  );
  assert.match(
    branch[0],
    /setLoad\(\{\s*state: "failed"/,
    `the read's !response.ok branch is ${branch[0]}, which does not set a failed read`,
  );
  assert.ok(
    !/state: "ok"/.test(branch[0]),
    `the read's !response.ok branch carries an ok state (${branch[0]})`,
  );
  assert.match(
    branch[0],
    /response\.status/,
    "the failing status is not carried into the detail, so the operator is told the read failed and not what answered",
  );
  // and the timestamp may not be stamped before the body has been classified
  const stamp = fn[0].indexOf("setCheckedAt");
  const parsedAt = fn[0].indexOf("parseDecisionList");
  assert.ok(stamp > parsedAt, "setCheckedAt runs before the payload is parsed, so a failed read stamps a fresh successful-read time");
});

check("every write outcome has a headline, and only an in-flight one may say it is sending", () => {
  // THE DEFECT THIS REPLACED WAS LIVE. app/council/deliberate/page.tsx built the
  // bold line from a `failed` flag listing create-failed and refused and NOT
  // locked, so a signed-out visitor pressing Record decision read "Sending your
  // call to the decision record" over a request that was never sent, forever.
  const outcomes: WriteOutcome[] = [
    { kind: "idle" },
    { kind: "locked" },
    { kind: "refused", reason: "no option was chosen" },
    { kind: "sending", step: "create" },
    { kind: "sending", step: "rule" },
    { kind: "create-failed", detail: "the route answered 500" },
    { kind: "rule-failed", decisionId: "d1", detail: "the route answered 409" },
    { kind: "recorded", decisionId: "d1", ruling: rulingForOption(COUNCIL_OPTIONS[0], undefined, "decided") },
  ];
  const kinds = new Set(outcomes.map((o) => o.kind));
  assert.equal(kinds.size, 7, "the WriteOutcome union changed; this check no longer covers every kind");
  for (const outcome of outcomes) {
    const headline = writeHeadline(outcome);
    assert.ok(headline.text.length > 0, `${outcome.kind} has no headline`);
    const claimsInFlight = /\bsending\b/i.test(headline.text);
    const inFlight = outcome.kind === "idle" || outcome.kind === "sending";
    assert.equal(
      claimsInFlight,
      inFlight,
      `${outcome.kind} renders "${headline.text}". Only an outcome with a request actually in flight may claim one is`,
    );
    if (outcome.kind === "locked" || outcome.kind === "refused") {
      assert.equal(headline.tone, "bad", `${outcome.kind} is terminal and nothing was sent, so it is not neutral`);
      assert.match(headline.text, /NOT/, `${outcome.kind} does not say the call was not sent`);
    }
  }
  assert.equal(writeHeadline({ kind: "recorded", decisionId: "d1", ruling: rulingForOption(COUNCIL_OPTIONS[0], undefined, "decided") }).tone, "good");
  // and the page must render that function rather than rebuilding the chain
  assert.match(
    DELIBERATE,
    /const headline = writeHeadline\(outcome\)/,
    "the deliberate page no longer derives its headline from writeHeadline, so this check guards a function nothing renders",
  );
  assert.match(DELIBERATE, /\{headline\.text\}/, "the deliberate page does not render headline.text");
  assert.ok(
    !/Sending your call to the decision record\./.test(DELIBERATE),
    "the deliberate page carries the in-flight sentence as a literal again, which is the ternary chain coming back",
  );
});

console.log(`\n${checks} decision record checks passed`);
