/**
 * Do the grouping rules count only genuinely independent, human verified jobs?
 *
 *   node n8n/devon/learning/lesson_evidence.test.mjs
 *
 * lesson_evidence.js defines functions and runs nothing, so it loads here
 * inside a Function that hands them back. No n8n, no network, no clock.
 *
 * THE BASE FIXTURE IS REAL. fixtures_ledger_2026-09-16.json holds the live
 * ledger row of 01M2KT8WM4RPZ90BCTZPVXH6HK, the VPS cutover proof and the only
 * COMPLETED job on the instance, read on 2026-10-08, with its trace cut to two
 * entries, and one of the eight CANCELLED test jobs. Every other job below is
 * that real row with one or two fields changed, so each case isolates exactly
 * one rule. The case list follows the spec's T1 list, rule by rule, with two
 * departures. The drive.draft case is synthetic, not a real envelope: the
 * Drive Draft Writer reads no structural payload beyond refusing editforge
 * (drive-draft-writer/validate_and_plan.js lines 75 and 76), so an action and
 * a note is what one carries. And T1's byte for byte pin of the two pasted
 * copies lands in Phase 3, when the copies exist.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const SOURCE = readFileSync(new URL("./lesson_evidence.js", import.meta.url), "utf8");
const R = new Function(SOURCE + "\nreturn { lessonCheckMember, lessonCheckPair, lessonVerifyGroup, lessonPickMembers, lessonActFingerprint, lessonIdList, LESSON_ULID, LESSON_PREFLIGHT_REFUSALS };")();
const FX = JSON.parse(readFileSync(new URL("./fixtures_ledger_2026-09-16.json", import.meta.url), "utf8"));
const REAL_ID = "01M2KT8WM4RPZ90BCTZPVXH6HK";
const KEY = "read-receipts-before-trust";

let n = 0;
function check(name, fn) { fn(); n++; console.log("ok   " + name); }
const clone = (x) => JSON.parse(JSON.stringify(x));
/** The real 2026-09-16 row, columns and envelope together, as the data table returns it. */
const realRow = () => Object.assign(clone(FX.row), { envelope: JSON.stringify(FX.envelope) });

/** A ledger row built from the real one. `edit` changes the envelope, `cols` the columns. */
function job(id, { edit = () => {}, cols = {} } = {}) {
  const env = clone(FX.envelope);
  env.intent_id = id;
  env.idempotency_key = "job-" + id;
  env.execution.execution_id = "exec-" + id;
  env.artifacts = [{ kind: "airtable_record", uri: "https://airtable.com/app/tbl/rec" + id, name: "row" }];
  env.intent.payload.airtable.fields.Title = "Title for " + id;
  edit(env);
  const row = clone(FX.row);
  Object.assign(row, {
    intent_id: id,
    idempotency_key: env.idempotency_key,
    parent_intent_id: env.parent_intent_id || "",
    workflow_id: env.execution.workflow_id,
    execution_id: env.execution.execution_id,
  }, cols);
  row.envelope = JSON.stringify(env);
  return row;
}
const verifiedOn = (day) => (env) => { env.verification.verified_at = day + "T03:00:41Z"; };
const A = "01M3AAAAAAAAAAAAAAAAAAAAAA";
const B = "01M3BBBBBBBBBBBBBBBBBBBBBB";
const C = "01M3CCCCCCCCCCCCCCCCCCCCCC";

function ctxFor(rows, extra = {}) {
  const rowsById = {};
  for (const r of rows) { rowsById[r.intent_id.toUpperCase()] = r; }
  return Object.assign({
    lessonKey: KEY,
    entry: { lesson_key: KEY, status: "active", evidence_ids: rows.map((r) => r.intent_id) },
    rowsById,
    groups: [],
    selfGroupId: "01M3GROUP0000000000000000Z",
    committedIds: [],
  }, extra);
}
const reasons = (m) => m.reasons.join(" | ");

// ---- E1 to E6, one member at a time -------------------------------------------

check("the real 2026-09-16 job passes E1 to E6 once it is declared", () => {
  const real = realRow();
  const m = R.lessonCheckMember(REAL_ID, ctxFor([real]));
  assert.equal(m.ok, true, reasons(m));
});

check("E1 refuses both live smoke ids and the 2026-10-07 probe id", () => {
  for (const id of ["SMOKETEST0FEEDER0000000000", "SMOKE-COMMITTER-V2-20260825", "01PR0BEGATEFINAL0000000003"]) {
    const m = R.lessonCheckMember(id, ctxFor([]));
    assert.equal(m.ok, false, id);
    assert.match(reasons(m), /^E1/);
  }
});

check("E1 accepts the real id in lower case, because ULIDs are case insensitive", () => {
  const m = R.lessonCheckMember(" " + REAL_ID.toLowerCase() + " ", ctxFor([realRow()]));
  assert.equal(m.id, REAL_ID);
  assert.equal(m.ok, true, reasons(m));
});

check("E2 refuses an id the ledger does not hold, such as a Cloud-era feed row", () => {
  const m = R.lessonCheckMember("01M1SAK59GF0511GR7B78Y06A9", ctxFor([]));
  assert.match(reasons(m), /E2 no ledger row/);
});

check("E2 refuses a CANCELLED test job", () => {
  const c = FX.cancelled_row;
  const m = R.lessonCheckMember(c.intent_id, ctxFor([c]));
  assert.equal(m.ok, false);
  assert.match(reasons(m), /E2 state is CANCELLED/);
});

check("E2 refuses a row whose envelope names another job", () => {
  const r = job(A, { edit: (e) => { e.intent_id = B; } });
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r]))), /E2 envelope intent_id does not match/);
});

check("E3 refuses a job completed as auto_no_artifact", () => {
  const r = job(A, { cols: { verification_method: "auto_no_artifact", human_watched: false } });
  const m = R.lessonCheckMember(A, ctxFor([r]));
  assert.match(reasons(m), /E3 not verified by a human watch/);
  assert.match(reasons(m), /E3 human_watched is not true/);
});

check("E3 refuses human_watch without Tee's approved verify card in the evidence", () => {
  const r = job(A, { edit: (e) => { e.verification.evidence = ["verify_card REQ-20260916-J1ApUy"]; } });
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r]))), /E3 no verify card approved by Tee/);
});

check("E4 refuses a job nobody declared for this lesson, whatever else it shares", () => {
  const r = job(A);
  const m = R.lessonCheckMember(A, ctxFor([r], { entry: { lesson_key: KEY, status: "active", evidence_ids: [] } }));
  assert.match(reasons(m), /E4 not declared/);
});

check("E4 accepts a job filed forward with intent.payload.lesson_key", () => {
  const r = job(A, { edit: (e) => { e.intent.payload.lesson_key = KEY; } });
  const m = R.lessonCheckMember(A, ctxFor([r], { entry: { lesson_key: KEY, status: "active", evidence_ids: [] } }));
  assert.equal(m.ok, true, reasons(m));
});

check("E5 refuses a retired lesson and an unknown one", () => {
  const r = job(A);
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r], { entry: { lesson_key: KEY, status: "retired", evidence_ids: [A] } }))), /E5 lesson .* is not active/);
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r], { entry: null }))), /E5 lesson .* is not active/);
});

check("E5 refuses a job filed with auto_verify", () => {
  const r = job(A, { edit: (e) => { e.intent.payload.auto_verify = true; } });
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r]))), /E5 filed with auto_verify/);
});

check("E6 holds a member that backed a group which reached the search, and frees one refused at preflight", () => {
  const r = job(A);
  const searched = { learning_intent_id: "01M3OTHERGROUP000000000000", source_intent_ids: JSON.stringify([A, B]), gate_decision: "REQUIRES_HUMAN", state: "FED" };
  const inFlight = { learning_intent_id: "01M3INFLIGHT00000000000000", source_intent_ids: [A, C], gate_decision: "", state: "FORMED" };
  const refused = { learning_intent_id: "01M3REFUSED000000000000000", source_intent_ids: [A, B], gate_decision: "REJECT_UNVERIFIED_SOURCE", state: "FED" };
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r], { groups: [searched] }))), /E6 already backs group 01M3OTHERGROUP/);
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r], { groups: [inFlight] }))), /E6 already backs group 01M3INFLIGHT/);
  assert.equal(R.lessonCheckMember(A, ctxFor([r], { groups: [refused] })).ok, true);
});

check("E6 does not count the group being checked against itself", () => {
  const r = job(A);
  const self = { learning_intent_id: "01M3GROUP0000000000000000Z", source_intent_ids: [A, B], gate_decision: "", state: "FORMED" };
  assert.equal(R.lessonCheckMember(A, ctxFor([r], { groups: [self] })).ok, true);
});

check("E6 holds a member a soul commit already names", () => {
  const r = job(A);
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r], { committedIds: [A.toLowerCase()] }))), /E6 already named by a soul commit/);
});

// ---- I1 to I7, one pair at a time ---------------------------------------------

const a = job(A, { edit: verifiedOn("2026-09-16") });
const b = job(B, { edit: verifiedOn("2026-09-18") });

check("two valid members on different days are independent", () => {
  const p = R.lessonCheckPair(A, B, ctxFor([a, b]));
  assert.equal(p.ok, true, p.reasons.join(" | "));
});

check("I1 the same id in two letter cases is one job", () => {
  assert.match(R.lessonCheckPair(A, A.toLowerCase(), ctxFor([a])).reasons.join(), /I1 the same job/);
});

check("I2 the same idempotency key is one job retried", () => {
  const b2 = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.idempotency_key = a.idempotency_key; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, b2])).reasons.join(), /I2 the same idempotency key/);
});

check("I3 a parent and its child, and two siblings, are not independent", () => {
  const child = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.parent_intent_id = A; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, child])).reasons.join(), /I3 one is the other's ancestor/);
  const s1 = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.parent_intent_id = C; } });
  const s2 = job(A, { edit: (e) => { verifiedOn("2026-09-16")(e); e.parent_intent_id = C; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([s1, s2, job(C)])).reasons.join(), /I3 they share a parent/);
});

check("I4 two jobs that wrote the same row are one observation", () => {
  const b2 = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.artifacts = clone(JSON.parse(a.envelope).artifacts); } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, b2])).reasons.join(), /I4 they share an artifact/);
});

check("I5 the same act with a different brief, summary and note counts once", () => {
  const b2 = job(B, { edit: (e) => {
    verifiedOn("2026-09-18")(e);
    e.intent.payload.airtable = clone(JSON.parse(a.envelope).intent.payload.airtable);
    e.intent.summary = "A completely reworded summary";
    e.intent.payload.brief = { plan: ["other"], by: "another model" };
    e.intent.payload.note = "a different note";
  } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, b2])).reasons.join(), /I5 the same structural act/);
});

check("I5 ignores case and spacing in the act, so retyping cannot split it", () => {
  const b2 = job(B, { edit: (e) => {
    verifiedOn("2026-09-18")(e);
    e.intent.payload.airtable = clone(JSON.parse(a.envelope).intent.payload.airtable);
    e.intent.payload.airtable.fields.Title = "  " + e.intent.payload.airtable.fields.Title.toUpperCase().replace(/ /g, "   ") + " ";
  } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, b2])).reasons.join(), /I5 the same structural act/);
});

check("I5 two jobs of an action with no structural object always count once", () => {
  const e1 = job(A, { edit: (e) => { verifiedOn("2026-09-16")(e); e.intent.payload = { action: "drive.draft", note: "draft one" }; } });
  const e2 = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.intent.payload = { action: "drive.draft", note: "draft two" }; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([e1, e2])).reasons.join(), /I5 the same structural act/);
});

check("I6 refuses two jobs verified on the same UTC day, and allows them with I6 off", () => {
  const b2 = job(B, { edit: verifiedOn("2026-09-16") });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, b2])).reasons.join(), /I6 verified on the same UTC day 2026-09-16/);
  assert.equal(R.lessonCheckPair(A, B, ctxFor([a, b2], { distinctDays: false })).ok, true);
});

check("I7 the same workflow execution is one observation", () => {
  const b2 = job(B, { edit: verifiedOn("2026-09-18"), cols: { workflow_id: a.workflow_id, execution_id: a.execution_id } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, b2])).reasons.join(), /I7 the same workflow execution/);
});

// ---- the gate and the feeder --------------------------------------------------

check("the gate counts two valid members as 2, from the rows and never from the caller", () => {
  const v = R.lessonVerifyGroup([A, B], ctxFor([a, b]));
  assert.equal(v.ok, true);
  assert.equal(v.verified_count, 2);
});

check("the gate refuses mixed-case duplicates of one id rather than counting them", () => {
  const v = R.lessonVerifyGroup([A, A.toLowerCase()], ctxFor([a]));
  assert.equal(v.ok, false);
  assert.equal(v.verified_count, 0);
});

check("the gate refuses a WHOLE group of three when one member is dependent, and never trims it", () => {
  const dependent = job(C, { edit: (e) => { verifiedOn("2026-09-20")(e); e.parent_intent_id = A; } });
  const v = R.lessonVerifyGroup([A, B, C], ctxFor([a, b, dependent]));
  assert.equal(v.ok, false);
  assert.equal(v.verified_count, 0);
  assert.equal(v.members.every((m) => m.ok), true);
  assert.equal(v.pairs.filter((p) => !p.ok).length, 1);
});

check("the gate refuses two made-up ULIDs, a single member and six members", () => {
  assert.equal(R.lessonVerifyGroup(["01M3ZZZZZZZZZZZZZZZZZZZZZZ", "01M3YYYYYYYYYYYYYYYYYYYYYY"], ctxFor([])).ok, false);
  assert.equal(R.lessonVerifyGroup([A], ctxFor([a])).ok, false);
  const six = ["01M4A", "01M4B", "01M4C", "01M4D", "01M4E", "01M4F"].map((p) => (p + "0000000000000000000000").slice(0, 26));
  const rows = six.map((id, i) => job(id, { edit: verifiedOn("2026-09-1" + i) }));
  assert.equal(R.lessonVerifyGroup(six, ctxFor(rows)).ok, false);
});

check("the feeder picks oldest verified first and leaves the dependent job out, with a reason", () => {
  const dependent = job(C, { edit: (e) => { verifiedOn("2026-09-10")(e); e.parent_intent_id = A; } });
  const picked = R.lessonPickMembers([B, C, A], ctxFor([a, b, dependent]));
  assert.deepEqual(picked.members, [C, B]);
  const out = picked.excluded.find((x) => x.id === A);
  assert.ok(out, "A must be excluded");
  assert.match(out.reasons.join(), /I3/);
});

check("the feeder collapses case duplicates and reports every excluded id", () => {
  const c = FX.cancelled_row;
  const picked = R.lessonPickMembers([A, A.toLowerCase(), c.intent_id, "SMOKETEST0FEEDER0000000000"], ctxFor([a, c]));
  assert.deepEqual(picked.members, [A]);
  assert.equal(picked.excluded.length, 3);
  assert.match(picked.excluded.find((x) => x.id === A).reasons.join(), /a repeat/);
});

check("today's pool cannot form a group: one real job, a cancelled one, three Cloud-era orphans", () => {
  const pool = [realRow(), FX.cancelled_row];
  const orphans = ["01M1KAEBPXJZMZSWC6MM02E2HA", "01M1S81K3WDD0JSKY6KPAY43K1", "01M1SAK59GF0511GR7B78Y06A9"];
  const ids = [REAL_ID, FX.cancelled_row.intent_id].concat(orphans);
  const picked = R.lessonPickMembers(ids, ctxFor(pool, { entry: { lesson_key: KEY, status: "active", evidence_ids: ids } }));
  assert.deepEqual(picked.members, [REAL_ID]);
  assert.equal(picked.members.length < 2, true);
});

// ---- the critic's cases, 2026-10-08 -------------------------------------------

check("the gate refuses a whole group whose pairs are all independent when one member fails a member rule", () => {
  const bad = [
    ["never watched by Tee", job(B, { edit: verifiedOn("2026-09-18"), cols: { verification_method: "auto_no_artifact", human_watched: false } }), {}],
    ["already backing a promoted group", b, { groups: [{ learning_intent_id: "01M3PR0M0TED00000000000000", source_intent_ids: [B, C], gate_decision: "PROMOTE" }] }],
    ["under a retired lesson", b, { entry: { lesson_key: KEY, status: "retired", evidence_ids: [A, B] } }],
    ["never declared", b, { entry: { lesson_key: KEY, status: "active", evidence_ids: [A] } }],
  ];
  for (const [name, row, extra] of bad) {
    const v = R.lessonVerifyGroup([A, B], ctxFor([a, row], extra));
    assert.equal(v.pairs.every((p) => p.ok), true, name + ": " + v.pairs.map((p) => p.reasons.join()).join());
    assert.equal(v.members[1].ok, false, name);
    assert.equal(v.ok, false, name);
    assert.equal(v.verified_count, 0, name);
  }
});

check("E6 holds a member for every decision that reached the search or is unknown, and frees it for the four preflight refusals only", () => {
  const r = job(A);
  const g = (decision) => ({ groups: [{ learning_intent_id: "01M3OTHERGR0P000000000000", source_intent_ids: [A, B], gate_decision: decision }] });
  for (const d of ["PROMOTE", "REJECT_CONFLICT", "REQUIRES_HUMAN", "HOLD_SUBCONSCIOUS", "REJECT_WEAK_EVIDENCE", "", "SOMETHING_NEW"]) {
    assert.match(reasons(R.lessonCheckMember(A, ctxFor([r], g(d)))), /E6 already backs group/, d);
  }
  assert.deepEqual([...R.LESSON_PREFLIGHT_REFUSALS].sort(), ["REJECT_MALFORMED", "REJECT_SECRET", "REJECT_UNREGISTERED", "REJECT_UNVERIFIED_SOURCE"]);
  for (const d of R.LESSON_PREFLIGHT_REFUSALS) {
    assert.equal(R.lessonCheckMember(A, ctxFor([r], g(d))).ok, true, d);
  }
});

check("I3 refuses a grandparent and a cousin whose linking rows are not in hand, and a blank parent column cannot hide the envelope's", () => {
  const grandchild = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.parent_intent_id = C; } });
  const p1 = R.lessonCheckPair(A, B, ctxFor([a, grandchild]));
  assert.equal(p1.ok, false);
  assert.match(p1.reasons.join(), /I3 a parent chain leaves the rows in hand/);
  const D = "01M3DDDDDDDDDDDDDDDDDDDDDD";
  const cousin = job(A, { edit: (e) => { verifiedOn("2026-09-16")(e); e.parent_intent_id = D; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([cousin, grandchild])).reasons.join(), /I3 a parent chain leaves/);
  const blank = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.parent_intent_id = A; }, cols: { parent_intent_id: " " } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, blank])).reasons.join(), /I3 one is the other's ancestor/);
  const viaC = job(C, { edit: (e) => { verifiedOn("2026-09-20")(e); e.parent_intent_id = A; } });
  const twoHops = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.parent_intent_id = C; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, twoHops, viaC])).reasons.join(), /I3 one is the other's ancestor/);
});

check("every id list is read whatever shape the table hands it back in, and an unread list refuses", () => {
  for (const shape of [JSON.stringify([A, B]), A + "," + B, A + ", " + B, A + " " + B, A + ";" + B, "['" + A + "', '" + B + "']", JSON.stringify(JSON.stringify([A, B])), { [A]: 1, [B]: 1 }, [A.toLowerCase(), B]]) {
    assert.deepEqual(R.lessonIdList(shape), [A, B], JSON.stringify(shape));
  }
  assert.deepEqual(R.lessonIdList(A + "X"), []);
  const r = job(A);
  assert.equal(R.lessonCheckMember(A, ctxFor([r], { entry: { lesson_key: KEY, status: "active", evidence_ids: JSON.stringify([A.toLowerCase()]) } })).ok, true);
  for (const shape of [A + " " + B, A + ";" + B, JSON.stringify(JSON.stringify([A, B]))]) {
    const g = { groups: [{ learning_intent_id: "01M3OTHERGR0P000000000000", source_intent_ids: shape, gate_decision: "REQUIRES_HUMAN" }] };
    assert.match(reasons(R.lessonCheckMember(A, ctxFor([r], g))), /E6 already backs group/, shape);
  }
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r], { committedIds: JSON.stringify([A]) }))), /E6 already named by a soul commit/);
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r], { groups: "[]" }))), /E6 the group log was not read/);
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r], { committedIds: undefined }))), /E6 the soul commit list was not read/);
});

check("E6 excludes the group under check by its normalised id, and only when there is one", () => {
  const r = job(A);
  const ownLower = { learning_intent_id: "01M3GR0UPSELF0000000000000".toLowerCase(), source_intent_ids: [A, B], gate_decision: "" };
  assert.equal(R.lessonCheckMember(A, ctxFor([r], { selfGroupId: "01M3GR0UPSELF0000000000000", groups: [ownLower] })).ok, true);
  const anon = { source_intent_ids: [A, B], gate_decision: "PROMOTE" };
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([r], { selfGroupId: undefined, groups: [anon] }))), /E6 already backs group unknown/);
  assert.deepEqual(R.lessonPickMembers([A], ctxFor([r], { selfGroupId: undefined, groups: [anon] })).members, []);
});

check("I5 is not split by invisible characters, number versus string, or a key that holds nothing", () => {
  const act = (fields, extra = {}) => R.lessonActFingerprint({ intent: { payload: { action: "airtable.row", airtable: { table: "Inbox Captures", fields }, ...extra } } });
  assert.equal(act({ Title: "Same" }), act({ Title: "Same​" }));
  assert.equal(act({ Title: "Same" }), act({ Title: "﻿Same⁠" }));
  assert.equal(act({ Title: "ＳＡＭＥ" }), act({ Title: "same" }));
  assert.equal(act({ Count: 1 }), act({ Count: "1" }));
  assert.equal(act({ Title: "Same" }), act({ Title: "Same", Notes: "" }));
  assert.equal(act({ Title: "Same", Body: "B" }), act({ Body: "B", Title: "Same" }));
  const z = (args) => R.lessonActFingerprint({ intent: { payload: { action: "zapier.mcp", zapier: { tool: "t", arguments: args } } } });
  assert.equal(z({ a: 1, b: null }), z({ a: "1" }));
  assert.notEqual(z({ a: 1 }), z({ a: 2 }));
  assert.notEqual(act({ Title: "Same" }), act({ Title: "Other" }));
});

check("the E-rule belts each refuse on their own", () => {
  const one = (name, row, re, extra = {}) => assert.match(reasons(R.lessonCheckMember(row.intent_id, ctxFor([row], extra))), re, name);
  one("not terminal", job(A, { cols: { terminal: false } }), /E2 not terminal/);
  one("receipt failed", job(A, { cols: { receipt_outcome: "failed" } }), /E2 receipt outcome is failed/);
  one("envelope unreadable", job(A, { cols: {} }), /E2 envelope unreadable/, { rowsById: { [A]: Object.assign(job(A), { envelope: "not json" }) } });
  one("array envelope", job(A), /E2 envelope unreadable/, { rowsById: { [A]: Object.assign(job(A), { envelope: "[1]" }) } });
  one("verification failed", job(A, { cols: { verification_state: "failed" } }), /E3 verification is failed/);
  one("no verified_at", job(A, { edit: (e) => { delete e.verification.verified_at; } }), /E3 no readable verified_at/);
  one("evidence with a prefix", job(A, { edit: (e) => { e.verification.evidence = ["x verify_card REQ-20260916-J1ApUy approved by Tee"]; } }), /E3 no verify card/);
  one("evidence that only says approved", job(A, { edit: (e) => { e.verification.evidence = ["approved"]; } }), /E3 no verify card/);
  one("human_watched as a string", job(A, { cols: { human_watched: "yes" } }), /E3 human_watched is not true/);
  one("auto_verify as a string", job(A, { edit: (e) => { e.intent.payload.auto_verify = "true"; } }), /E5 filed with auto_verify/);
  const long = A + "Z";
  assert.match(reasons(R.lessonCheckMember(long, ctxFor([]))), /^E1/);
  const r = job(A);
  assert.equal(R.lessonCheckMember(A, ctxFor([r], { entry: { lesson_key: KEY, status: "active", evidence_ids: [A.toLowerCase()] } })).ok, true);
  const prefix = job(A, { edit: (e) => { e.intent.payload.lesson_key = "read"; } });
  assert.match(reasons(R.lessonCheckMember(A, ctxFor([prefix], { entry: { lesson_key: KEY, status: "active", evidence_ids: [] } }))), /E4 not declared/);
  const obj = Object.assign(job(A), { envelope: JSON.parse(job(A).envelope) });
  assert.equal(R.lessonCheckMember(A, ctxFor([obj])).ok, true);
});

check("each I rule reads its column, falls back to the envelope, and refuses when both are empty", () => {
  const noKeyCol = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.idempotency_key = a.idempotency_key; }, cols: { idempotency_key: "" } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, noKeyCol])).reasons.join(), /I2 the same idempotency key/);
  const colKey = job(B, { edit: verifiedOn("2026-09-18"), cols: { idempotency_key: a.idempotency_key } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, colKey])).reasons.join(), /I2 the same idempotency key/);
  const noKey = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.idempotency_key = ""; }, cols: { idempotency_key: "" } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, noKey])).reasons.join(), /I2 an idempotency key is missing/);
  const colParent = job(B, { edit: verifiedOn("2026-09-18"), cols: { parent_intent_id: A.toLowerCase() } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, colParent])).reasons.join(), /I3 one is the other's ancestor/);
  const exEnv = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.execution.workflow_id = a.workflow_id; e.execution.execution_id = a.execution_id; }, cols: { workflow_id: "", execution_id: "" } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, exEnv])).reasons.join(), /I7 the same workflow execution/);
  const noEx = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.execution.execution_id = ""; }, cols: { execution_id: "" } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, noEx])).reasons.join(), /I7 a workflow and execution id pair is missing/);
  const noDay = job(B, { edit: (e) => { delete e.verification.verified_at; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, noDay])).reasons.join(), /I6 a verified date is missing/);
  const offset = job(B, { edit: (e) => { e.verification.verified_at = "2026-09-15T23:30:00-05:00"; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, offset])).reasons.join(), /I6 verified on the same UTC day 2026-09-16/);
  const recOnly = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.artifacts = [{ kind: "airtable_record", uri: "https://elsewhere/x", record_id: "recSHARED" }]; } });
  const recA = job(A, { edit: (e) => { verifiedOn("2026-09-16")(e); e.artifacts = [{ kind: "airtable_record", uri: "https://airtable.com/y", record_id: "recSHARED" }]; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([recA, recOnly])).reasons.join(), /I4 they share an artifact/);
  const uriCase = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.artifacts = [{ uri: JSON.parse(a.envelope).artifacts[0].uri.toUpperCase() }]; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([a, uriCase])).reasons.join(), /I4 they share an artifact/);
  const driveA = job(A, { edit: (e) => { verifiedOn("2026-09-16")(e); e.artifacts = [{ kind: "drive_file", uri: "https://docs.google.com/document/d/F1/edit", drive_file_id: "F1" }]; } });
  const driveB = job(B, { edit: (e) => { verifiedOn("2026-09-18")(e); e.artifacts = [{ kind: "drive_file", uri: "https://docs.google.com/document/d/F1/", drive_file_id: "F1" }]; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([driveA, driveB])).reasons.join(), /I4 they share an artifact/);
});

check("I5 reads the zapier and editforge objects, and leaves labels and lesson keys out", () => {
  const zap = (id, day, args, extra = {}) => job(id, { edit: (e) => { verifiedOn(day)(e); e.intent.payload = { action: "zapier.mcp", zapier: { tool: "gmail_send", arguments: args }, ...extra }; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([zap(A, "2026-09-16", { to: "x" }), zap(B, "2026-09-18", { to: "x" }, { lesson_key: "other-lesson" })])).reasons.join(), /I5 the same structural act/);
  assert.equal(R.lessonCheckPair(A, B, ctxFor([zap(A, "2026-09-16", { to: "x" }), zap(B, "2026-09-18", { to: "y" })])).ok, true);
  const ef = (id, day, prompt, label) => job(id, { edit: (e) => { verifiedOn(day)(e); e.intent.payload = { action: "editforge.job", editforge: { kind: "voice", prompt, provider: "mock", label } }; } });
  assert.match(R.lessonCheckPair(A, B, ctxFor([ef(A, "2026-09-16", "p", "one"), ef(B, "2026-09-18", "p", "two")])).reasons.join(), /I5 the same structural act/);
  assert.equal(R.lessonCheckPair(A, B, ctxFor([ef(A, "2026-09-16", "p", "one"), ef(B, "2026-09-18", "q", "one")])).ok, true);
});

check("the feeder caps a group at five, oldest first by instant rather than by string", () => {
  const ids = ["01M5A", "01M5B", "01M5C", "01M5D", "01M5E", "01M5F"].map((p) => (p + "0".repeat(26)).slice(0, 26));
  const days = ["2026-09-21", "2026-09-11", "2026-09-12", "2026-09-13", "2026-09-14", "2026-09-15"];
  const rows = ids.map((id, i) => job(id, { edit: verifiedOn(days[i]) }));
  const picked = R.lessonPickMembers(ids, ctxFor(rows));
  assert.equal(picked.members.length, 5);
  assert.deepEqual(picked.members, ids.slice(1));
  assert.match(picked.excluded.find((x) => x.id === ids[0]).reasons.join(), /already holds 5/);
  // 01:00 at +05:00 is 20:00Z, an hour BEFORE 21:00Z, though it sorts after it as a string.
  const earlierInstant = job(A, { edit: (e) => { e.verification.verified_at = "2026-09-16T01:00:00+05:00"; } });
  const laterInstant = job(B, { edit: (e) => { e.verification.verified_at = "2026-09-15T21:00:00Z"; } });
  assert.deepEqual(R.lessonPickMembers([B, A], ctxFor([earlierInstant, laterInstant], { distinctDays: false })).members, [A, B]);
});

console.log(n + " checks passed");
