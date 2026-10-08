/**
 * Does the Learning Gate refuse before it searches, and promote only what it
 * verified itself?
 *
 *   node n8n/devon/learning-gate/gate.test.mjs
 *
 * Phase 1 of the grouping build, ruled by Tee 2026-10-08. Each node body runs
 * inside a Function with `$input` and `$` stubbed, the house pattern.
 *
 * TWO THINGS HERE ARE REAL. The twelve claims are the live feed log
 * U0PqQWiq4nadKFlm as read on 2026-10-08, every POST the feeder has ever
 * made, so the preflight is measured against the traffic it will actually
 * see. And the answer is fed to the feeder's own Log Or Alert node from
 * n8n/devon/ledger-feeder/, so the decision the feeder records is read by the
 * feeder's code, not by a re-implementation of it.
 *
 * The twelve claims are posted in a hand built body. The ledger object the
 * live feeder also sends is covered by one check that builds the POST with
 * the feeder's own Select Unfed Jobs over the real ledger row in
 * n8n/devon/learning/fixtures_ledger_2026-09-16.json.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const load = (path) => new Function("$input", "$", readFileSync(new URL(path, import.meta.url), "utf8"));
const preflight = load("./candidate_former.js");
const refuse = load("./refuse_before_search.js");
const assemble = load("./assemble_result.js");
const gate = load("./learning_gate.js");
const build = load("./build_record.js");
const write = load("./write_result.js");
const logOrAlert = load("../ledger-feeder/log_or_alert.js");
const selectUnfed = load("../ledger-feeder/select_unfed_jobs.js");
const FIXTURE = JSON.parse(readFileSync(new URL("../learning/fixtures_ledger_2026-09-16.json", import.meta.url), "utf8"));

let n = 0;
function check(name, fn) { fn(); n++; console.log("ok   " + name); }
const one = (json) => ({ first: () => ({ json }), all: () => [{ json }] });
const noRefs = () => { throw new Error("this node should not read another node"); };

/** The preflight's verdict for one webhook body. */
function pre(body) { return preflight(one({ headers: {}, body }), noRefs)[0].json; }
/** The full no-search branch: preflight, then the answer the webhook returns. */
function answer(body) { return refuse(one(pre(body)), noRefs)[0].json; }
/** What the feeder's own code records for an HTTP 200 carrying that answer. */
function recorded(body, intentId = "01M2KT8WM4RPZ90BCTZPVXH6HK") {
  const res = { statusCode: 200, body: answer(body) };
  const $ = (name) => {
    assert.equal(name, "Select Unfed Jobs");
    return { all: () => [{ json: { intent_id: intentId, claim: String(body && body.claim) } }] };
  };
  const out = logOrAlert({ all: () => [{ json: res }] }, $)[0].json;
  return out.logs[0];
}

const REAL = "01M2KT8WM4RPZ90BCTZPVXH6HK";
const CANCELLED = ["01M0RMKF6ZGZE2TX6XT1QSHEKA", "01M0RMKF6ZGC169DYZZG1XSC7G"];
const MADE_UP = ["01M3ZZZZZZZZZZZZZZZZZZZZZZ", "01M3YYYYYYYYYYYYYYYYYYYYYY"];
const GROUP = "01M3GRP0000000000000000000";
const feederPost = (id, claim) => ({ claim, source_intent_ids: [id], proposed_scope: "Systems", confidence: 0.6, source: "ledger-feeder" });

// The live feed log, all twelve rows, read 2026-10-08: [intent_id, gate_decision then, claim].
const FEED_LOG = [
  ["SMOKETEST0FEEDER0000000000", "REQUIRES_HUMAN", "Completed job experience: Build 12 feeder smoke test: ledger to webhook wiring. Area: Systems. Executor: n8n. Outcome: success."],
  ["SMOKE-COMMITTER-V2-20260825", "PROMOTE", "SMOKE TEST from the Build 12 close-out session. REJECT this card. It proves the live propose path of the rebuilt Soul Committer end to end; a devon-soul write must never result from it. Area: smoke-test. Executor: claude-session. Outcome: reject."],
  ["01M1KAEBPXJZMZSWC6MM02E2HA", "HOLD_SUBCONSCIOUS", "Completed job experience: Migrate n8n Data Tables export (9 tables, 38 rows) from n8n cloud instance to self-hosted n8n.editforge.online via the public REST API, per user-supplied API key.. Area: Systems. Executor: claude-cowork-session. Outcome: PASS. Target n8n.editforge.online. Scope: 9 tables, 38 rows. Verification: field-by-field comparison, zero mismatches. Cloud source: untouched. Limitations: the field-by-field verification pass ran inline and was not saved as a rerunnable artifact/log; the create_table 409-collision idempotency branch was never exercised since every create succeeded fresh, so it remains unproven.."],
  ["01M1S81K3WDD0JSKY6KPAY43K1", "HOLD_SUBCONSCIOUS", "Completed job experience: Build 14 lane proof: level 0 job with no blast radius, auto verified, through every organ. Area: Systems. Executor: n8n. Outcome: completed."],
  ["01M1SAK59GF0511GR7B78Y06A9", "HOLD_SUBCONSCIOUS", "Completed job experience: Brief proof: draft a one page outline for TQO episode 12 on automating a weekly report with Claude Code and file it as a Drive draft. Area: TQO. Executor: n8n. Outcome: completed."],
  ["01M1SC1BAA6ST4716GZ2N0DYS7", "HOLD_SUBCONSCIOUS", "Completed job experience: Dedupe proof: level 0 note filed twice under one idempotency key, second post must return the first job. Area: Systems. Executor: n8n. Outcome: completed."],
  ["01M1SEBXAXR48STXRVRHDAMG6T", "HOLD_SUBCONSCIOUS", "Completed job experience: Build 05 refusal repair: prove the accepted path through spine.echo after the Refused gate. Area: Systems. Executor: n8n. Outcome: completed."],
  ["01M1SN5X4ETKEPPCC4JT61TE5V", "HOLD_SUBCONSCIOUS", "Completed job experience: Draft the TQO episode 13 outline on reading an AI tool's receipts before trusting it. Area: TQO. Executor: n8n. Outcome: completed."],
  ["01M1TB5RAJHF0FJEN91QMKYYK7", "REQUIRES_HUMAN", "Completed job experience: Key rotation probe: confirm every organ still reaches the Event Bus after the shared x-devon-key was rotated on 2026-09-06. Area: Systems. Executor: n8n. Outcome: completed."],
  ["01M1V6M3XG0RQR191QFF7W74WJ", "REQUIRES_HUMAN", "Completed job experience: Write one Inbox Captures row recording that the Build 17 Airtable Row Writer is live. Area: Systems. Executor: n8n. Outcome: completed."],
  ["01M2BP853KS5PN4D2CK7PQ8234", "REQUIRES_HUMAN", "Completed job experience: Record in Inbox Captures that the Build 14 approval to action path completed end to end.. Area: Systems. Executor: n8n. Outcome: completed."],
  ["01M2KT8WM4RPZ90BCTZPVXH6HK", "HOLD_SUBCONSCIOUS", "Completed job experience: VPS cutover verification: one real job driven end to end on the VPS. Area: Systems. Executor: n8n. Outcome: completed."],
];

// ---- the preflight, over the traffic the feeder actually sends ---------------

check("every real feed with a ULID id answers HOLD, and none spends a search or trips the secret scan", () => {
  const real = FEED_LOG.filter(([id]) => /^[0-9A-HJKMNP-TV-Z]{26}$/.test(id));
  assert.equal(real.length, 10);
  for (const [id, , claim] of real) {
    const p = pre(feederPost(id, claim));
    assert.equal(p.preflight.decision, "HOLD_SUBCONSCIOUS", id + " " + p.preflight.reason);
    assert.equal(p.preflight.search_needed, false);
    assert.equal(p.candidate, null);
  }
});

check("the two smoke rows, whose ids are not ULIDs, are refused as malformed", () => {
  for (const [id, , claim] of FEED_LOG.slice(0, 2)) {
    assert.equal(pre(feederPost(id, claim)).preflight.decision, "REJECT_MALFORMED", id);
  }
});

check("the feeder records each answer through its own Log Or Alert code", () => {
  const [, , claim] = FEED_LOG[11];
  assert.equal(recorded(feederPost(REAL, claim)).gate_decision, "HOLD_SUBCONSCIOUS");
  assert.equal(recorded({ kind: "lesson", source_intent_ids: MADE_UP, learning_intent_id: GROUP, lesson_key: "a-lesson" }).gate_decision, "REJECT_UNREGISTERED");
  assert.equal(recorded({ source_intent_ids: MADE_UP, claim }).gate_decision, "REJECT_MALFORMED");
  assert.equal(recorded(feederPost(REAL, "short")).gate_decision, "REJECT_WEAK_EVIDENCE");
});

check("the answer carries the decision at gate.decision only, so nothing can shadow it", () => {
  const a = answer(feederPost(REAL, FEED_LOG[11][2]));
  assert.equal(a.gate.decision, "HOLD_SUBCONSCIOUS");
  assert.equal("decision" in a, false);
  assert.equal("gate_decision" in a, false);
  assert.equal(a.receipt, null);
  assert.equal(a.gate.search_spent, false);
  assert.equal(a.subconscious_write.skipped, true);
});

// ---- the spec's T8 cases, which Phase 1 also runs against the live gate ------

check("T8: two made-up ULIDs as one job are malformed, and as a lesson are unregistered", () => {
  assert.equal(pre({ source_intent_ids: MADE_UP, claim: "Completed job experience: made up." }).preflight.decision, "REJECT_MALFORMED");
  assert.equal(pre({ kind: "lesson", source_intent_ids: MADE_UP, learning_intent_id: GROUP, lesson_key: "made-up" }).preflight.decision, "REJECT_UNREGISTERED");
});

check("T8: two CANCELLED ids are malformed as a job and unregistered as a lesson", () => {
  assert.equal(pre({ source_intent_ids: CANCELLED, claim: "Completed job experience: cancelled." }).preflight.decision, "REJECT_MALFORMED");
  assert.equal(pre({ kind: "lesson", source_intent_ids: CANCELLED, learning_intent_id: GROUP, lesson_key: "cancelled-pair" }).preflight.decision, "REJECT_UNREGISTERED");
});

check("T8: the real id twice in two letter cases is one job, refused as a repeat", () => {
  for (const kind of ["job", "lesson"]) {
    const p = pre({ kind, source_intent_ids: [REAL, REAL.toLowerCase()], learning_intent_id: GROUP, lesson_key: "same-job", claim: kind === "job" ? "Completed job experience: twice." : undefined });
    assert.equal(p.preflight.decision, "REJECT_MALFORMED", kind);
    assert.match(p.preflight.reason, /repeats/);
  }
});

// ---- every refusal, one rule at a time ---------------------------------------

check("a body that is not an object, an unknown kind, and ids that are not a list of strings are malformed", () => {
  for (const body of [null, "text", [REAL]]) { assert.equal(pre(body).preflight.decision, "REJECT_MALFORMED"); }
  assert.equal(pre({ kind: "insight", source_intent_ids: [REAL], claim: "x".repeat(20) }).preflight.decision, "REJECT_MALFORMED");
  assert.equal(pre({ source_intent_ids: REAL, claim: "x".repeat(20) }).preflight.decision, "REJECT_MALFORMED");
  assert.equal(pre({ source_intent_ids: [7], claim: "x".repeat(20) }).preflight.decision, "REJECT_MALFORMED");
  assert.equal(pre({ claim: "x".repeat(20) }).preflight.decision, "REJECT_MALFORMED");
});

check("a lesson that carries a claim, a bad group id, a bad key, one member or six is malformed", () => {
  const ok = { kind: "lesson", source_intent_ids: MADE_UP, learning_intent_id: GROUP, lesson_key: "a-lesson" };
  assert.equal(pre({ ...ok, claim: "A claim the caller made up for itself." }).preflight.decision, "REJECT_MALFORMED");
  assert.equal(pre({ ...ok, learning_intent_id: "group-1" }).preflight.decision, "REJECT_MALFORMED");
  assert.equal(pre({ ...ok, lesson_key: "Not A Slug" }).preflight.decision, "REJECT_MALFORMED");
  assert.equal(pre({ ...ok, source_intent_ids: [MADE_UP[0]] }).preflight.decision, "REJECT_MALFORMED");
  const six = ["01M4A", "01M4B", "01M4C", "01M4D", "01M4E", "01M4F"].map((p) => (p + "0".repeat(26)).slice(0, 26));
  assert.equal(pre({ ...ok, source_intent_ids: six }).preflight.decision, "REJECT_MALFORMED");
});

check("a secret anywhere in the body is refused by its shape, and never echoed back", () => {
  const secret = "pc" + "sk_" + "Ab3".repeat(12);
  for (const body of [
    feederPost(REAL, "Completed job experience: pasted " + secret + " into the summary."),
    { ...feederPost(REAL, "Completed job experience: clean claim."), note: { nested: [secret] } },
  ]) {
    const a = answer(body);
    assert.equal(a.gate.decision, "REJECT_SECRET");
    assert.match(a.gate.reason, /a Pinecone key/);
    assert.equal(JSON.stringify(a).includes(secret), false);
  }
});

check("a field named like a credential is refused whatever it holds, and an empty one is not", () => {
  const base = feederPost(REAL, "Completed job experience: clean claim.");
  for (const extra of [{ password: "x" }, { Authorization: "y" }, { meta: { "X-Devon-Key": "z" } }, { list: [{ api_key: 1 }] }, { token: false }]) {
    const a = answer({ ...base, ...extra });
    assert.equal(a.gate.decision, "REJECT_SECRET", JSON.stringify(extra));
    assert.match(a.gate.reason, /named like a credential/);
  }
  for (const extra of [{ token: "" }, { password: null }, { secret: [] }, { access_token_count: 3 }]) {
    assert.equal(answer({ ...base, ...extra }).gate.decision, "HOLD_SUBCONSCIOUS", JSON.stringify(extra));
  }
});

check("the bearer and x-devon-key shapes ignore letter case", () => {
  for (const claim of ["Completed job experience: sent bear" + "er abcDEF123456ghiJKL789 by hand.", "Completed job experience: X-DEVON-" + "KEY: s3cr3tV4lue was pasted."]) {
    assert.equal(answer(feederPost(REAL, claim)).gate.decision, "REJECT_SECRET", claim);
  }
});

check("a job with a missing or short claim is weak evidence", () => {
  assert.equal(pre({ source_intent_ids: [REAL] }).preflight.decision, "REJECT_WEAK_EVIDENCE");
  assert.equal(pre({ source_intent_ids: [REAL], claim: "  too short " }).preflight.decision, "REJECT_WEAK_EVIDENCE");
});

check("nothing a caller sends as evidence, counts or a receipt makes a job anything but HOLD", () => {
  const p = pre({
    ...feederPost(REAL, "Completed job experience: dressed up as evidence."),
    independent_evidence_count: 5,
    evidence: [{ intent_id: MADE_UP[0], state: "COMPLETED" }],
    receipt: { complete: true, conflict_status: "clear" },
    verified_count: 9,
  });
  assert.equal(p.preflight.decision, "HOLD_SUBCONSCIOUS");
  assert.equal(p.preflight.search_needed, false);
});

check("the POST the feeder's own code builds from a real ledger row answers HOLD", () => {
  const $ = (name) => { assert.equal(name, "Fetch Completed Jobs"); return { all: () => [{ json: FIXTURE.row }] }; };
  const posts = selectUnfed({ all: () => [{ json: {} }] }, $);
  assert.equal(posts.length, 1);
  const body = posts[0].json.payload;
  assert.equal(typeof body.ledger, "object");
  assert.equal(body.ledger.intent_id, REAL);
  assert.equal(answer(body).gate.decision, "HOLD_SUBCONSCIOUS");
  assert.equal(recorded(body).gate_decision, "HOLD_SUBCONSCIOUS");
});

// ---- a body too big or too deep to scan is refused as data, quickly ------------

check("a body too large or too deep to scan whole is refused as data, never thrown and never slow", () => {
  const deep = (levels, leaf) => { let o = leaf; for (let i = 0; i < levels; i++) { o = { n: o }; } return o; };
  const secret = "pc" + "sk_" + "Ab3".repeat(12);
  const hostile = [
    ["a 6 MB run after a key prefix", feederPost(REAL, "Completed job experience: x pc" + "sk_" + "a".repeat(6000000))],
    ["200 KB of a token prefix repeated", feederPost(REAL, "Completed job experience: " + "eyJ-".repeat(50000))],
    ["a secret nested ten objects down", { ...feederPost(REAL, "Completed job experience: clean claim."), x: deep(10, secret) }],
    ["a secret after 2001 other strings", { source_intent_ids: [REAL], pad: Array(2001).fill("a"), claim: "Completed job experience: x " + secret }],
  ];
  for (const [name, body] of hostile) {
    const started = Date.now();
    const a = answer(body);
    assert.ok(Date.now() - started < 2000, name + " took " + (Date.now() - started) + " ms");
    assert.equal(a.gate.decision, "REJECT_MALFORMED", name);
    assert.match(a.gate.reason, /too large or too deeply nested/, name);
    assert.equal(recorded(body).gate_decision, "REJECT_MALFORMED", name);
  }
});

check("inside the bound the scan still reaches a secret eight objects down and one held in a key", () => {
  const secret = "pc" + "sk_" + "Ab3".repeat(12);
  const deep = (levels, leaf) => { let o = leaf; for (let i = 0; i < levels; i++) { o = { n: o }; } return o; };
  const base = feederPost(REAL, "Completed job experience: clean claim.");
  assert.equal(answer({ ...base, x: deep(7, secret) }).gate.decision, "REJECT_SECRET");
  assert.equal(answer({ ...base, x: { [secret]: 1 } }).gate.decision, "REJECT_SECRET");
  const named = answer({ ...base, x: deep(6, { password: "x" }) });
  assert.equal(named.gate.decision, "REJECT_SECRET");
  assert.match(named.gate.reason, /named like a credential/);
});

check("every secret shape the gate declares is refused by its own label", () => {
  // Assembled the same way test_devon_lesson_registry.py assembles them, so
  // no sample is written whole in the repo.
  const tail = "Ab3".repeat(12);
  const samples = {
    "a Pinecone key": "pc" + "sk_" + tail,
    "a console token": "ds" + "t_" + "0123456789abcdef".repeat(3),
    "a capture token": "dc" + "p_" + "claude_" + "f1".repeat(10),
    "an Anthropic key": "s" + "k-" + "ant-" + "api03-" + tail,
    "an OpenAI style key": "s" + "k-" + "proj" + tail,
    "a Cerebras key": "cs" + "k-" + tail,
    "an AWS access key id": "AK" + "IA" + "ABCDEFGHIJKLMNOP",
    "a private key block": "-----BEG" + "IN RSA PRIVATE KEY-----",
    "a Slack token": "xo" + "xb-" + "1234567890-abcdef",
    "a GitHub token": "gh" + "p_" + tail,
    "a Google API key": "AI" + "za" + tail,
    "an Airtable token": "pa" + "t" + "Ab3Cd4Ef5Gh6Ij" + "." + "0123456789abcdef".repeat(4),
    "a JSON web token": "ey" + "JhbGciOiJIUzI1NiJ9" + "." + "ey" + "JzdWIiOiJ0ZWUifQ" + "." + "sig",
    "a bearer credential": "sent as bear" + "er " + "abcDEF123456ghiJKL789",
    "an x-devon-key value": "x-devon-" + "key: " + "s3cr3tV4lue",
  };
  const declared = [...readFileSync(new URL("./candidate_former.js", import.meta.url), "utf8").matchAll(/^ {2}\["([^"]+)", String\.raw`/gm)].map((m) => m[1]);
  assert.deepEqual([...declared].sort(), Object.keys(samples).sort());
  for (const label of declared) {
    const a = answer(feederPost(REAL, "Completed job experience: before this step " + samples[label] + " was pasted."));
    assert.equal(a.gate.decision, "REJECT_SECRET", label);
    assert.equal(a.gate.reason, "the request carries something shaped like " + label);
  }
});

check("the preflight's boundaries: id length, slug length, claim floor, kind, case and spaces", () => {
  const claim = "Completed job experience: clean claim.";
  assert.equal(pre({ source_intent_ids: [REAL + "X"], claim }).preflight.decision, "REJECT_MALFORMED");
  assert.equal(pre({ kind: null, source_intent_ids: [REAL], claim }).preflight.decision, "REJECT_MALFORMED");
  const spaced = pre({ source_intent_ids: ["  " + REAL.toLowerCase() + " "], claim });
  assert.equal(spaced.preflight.decision, "HOLD_SUBCONSCIOUS");
  assert.deepEqual(spaced.preflight.source_intent_ids, [REAL]);
  assert.equal(pre({ source_intent_ids: [REAL], claim: "x".repeat(11) }).preflight.decision, "REJECT_WEAK_EVIDENCE");
  assert.equal(pre({ source_intent_ids: [REAL], claim: "x".repeat(12) }).preflight.decision, "HOLD_SUBCONSCIOUS");
  const ok = { kind: "lesson", source_intent_ids: MADE_UP, learning_intent_id: GROUP };
  assert.equal(pre({ ...ok, lesson_key: "a".repeat(60) }).preflight.decision, "REJECT_UNREGISTERED");
  assert.equal(pre({ ...ok, lesson_key: "a".repeat(61) }).preflight.decision, "REJECT_MALFORMED");
  assert.match(pre({ ...ok, lesson_key: "a-lesson" }).preflight.reason, /not enabled yet/);
  for (const extra of [{ tokenizer: "bpe" }, { next_page_token: "abc" }, { refresh_token_used: true }]) {
    assert.equal(answer({ ...feederPost(REAL, claim), ...extra }).gate.decision, "HOLD_SUBCONSCIOUS", JSON.stringify(extra));
  }
});

check("Refuse Before Search falls back to REJECT_MALFORMED rather than an empty decision", () => {
  for (const json of [{}, { preflight: {} }, { preflight: { decision: "" } }]) {
    const a = refuse(one(json), noRefs)[0].json;
    assert.equal(a.gate.decision, "REJECT_MALFORMED");
    assert.ok(a.gate.reason.length > 0);
  }
});

// ---- the search branch, which Phase 1 never reaches ----------------------------

const lessonCandidate = (over = {}) => ({
  kind: "lesson", claim: "Read the executor's own receipt back before reporting a job as done.",
  learning_intent_id: GROUP, lesson_key: "read-receipts", area: "Systems", proposed_scope: "system",
  verified_ids: [REAL, MADE_UP[0]], verified_count: 2, min_sources: 2, ...over,
});
const clear = { receipt_id: "01M3RECEIPT000000000000000", complete: true, conflict_status: "clear", matched_records: [{ id: "rec-1", score: 0.21 }] };
const decide = (candidate, receipt) => gate(one({ candidate, receipt }), noRefs)[0].json.gate;

check("the gate promotes only a lesson whose members it verified, never a job or a caller's count", () => {
  assert.equal(decide(lessonCandidate(), clear).decision, "PROMOTE");
  assert.equal(decide({ claim: "Completed job experience: one job.", source_intent_ids: [REAL], independent_evidence_count: 2 }, clear).decision, "HOLD_SUBCONSCIOUS");
  assert.equal(decide(lessonCandidate({ verified_count: undefined, independent_evidence_count: 5 }), clear).decision, "HOLD_SUBCONSCIOUS");
  assert.equal(decide(lessonCandidate({ min_sources: 3 }), clear).decision, "HOLD_SUBCONSCIOUS");
  assert.equal(decide(lessonCandidate({ verified_ids: [REAL] }), clear).decision, "HOLD_SUBCONSCIOUS");
  assert.equal(decide(lessonCandidate({ verified_ids: undefined }), clear).decision, "HOLD_SUBCONSCIOUS");
});

check("conflict and requires_human still outrank everything", () => {
  assert.equal(decide(lessonCandidate(), { ...clear, conflict_status: "conflict" }).decision, "REJECT_CONFLICT");
  assert.equal(decide(lessonCandidate(), { ...clear, conflict_status: "requires_human" }).decision, "REQUIRES_HUMAN");
  assert.equal(decide(lessonCandidate(), { ...clear, complete: false }).decision, "REQUIRES_HUMAN");
});

check("the record's id is the learning intent id, so a retry rewrites the same record", () => {
  const out = build(one({ candidate: lessonCandidate(), receipt: clear }), noRefs)[0].json.record;
  assert.equal(out._id, GROUP);
  assert.equal(out.kind, "lesson");
  assert.equal(out.status, "active");
  assert.equal(out.conflict_check_receipt_id, clear.receipt_id);
  assert.deepEqual(out.source_intent_ids, [REAL, MADE_UP[0]]);
  assert.equal(out.independent_evidence_count, 2);
  assert.equal(out.top_match_score, 0.21);
});

check("Build Record refuses to write without a learning intent id or a verified member list", () => {
  assert.throws(() => build(one({ candidate: lessonCandidate({ learning_intent_id: "" }), receipt: clear }), noRefs), /without a learning intent id/);
  assert.throws(() => build(one({ candidate: lessonCandidate({ verified_ids: [REAL] }), receipt: clear }), noRefs), /without a verified list of distinct members/);
});

const ctx = { record: { _id: GROUP, text: "t" }, candidate: lessonCandidate(), gate: { decision: "PROMOTE" } };
const fromBuild = (name) => { assert.equal(name, "Build Record"); return { first: () => ({ json: ctx }) }; };

check("a failed subconscious write throws instead of answering 200 PROMOTE", () => {
  for (const res of [{ statusCode: 500, body: { error: "upstream: down" } }, { statusCode: 401, body: "no" }, {}]) {
    let message = "";
    try { write(one(res), fromBuild); } catch (e) { message = e.message; }
    assert.match(message, /^Subconscious write failed with HTTP/);
    assert.equal(message.includes(":"), false, "a colon would be cut by n8n: " + message);
    assert.equal(/[\r\n]/.test(message), false);
  }
});

check("a written record still answers PROMOTE with the record id", () => {
  const out = write(one({ statusCode: 200, body: { upsertedCount: 1 } }), fromBuild)[0].json;
  assert.equal(out.gate.decision, "PROMOTE");
  assert.equal(out.subconscious_write.ok, true);
  assert.equal(out.subconscious_write.record_id, GROUP);
});

check("Assemble Result names the lesson group in a failed search", () => {
  const refs = (name) => { assert.equal(name, "Search Needed"); return { first: () => ({ json: { candidate: lessonCandidate() } }) }; };
  assert.throws(() => assemble(one({ statusCode: 503, body: "down" }), refs), /for lesson group 01M3GRP/);
});

check("a member list that repeats one job or carries junk counts as none", () => {
  assert.equal(decide(lessonCandidate({ verified_ids: [REAL, REAL.toLowerCase()] }), clear).decision, "HOLD_SUBCONSCIOUS");
  assert.equal(decide(lessonCandidate({ verified_ids: ["x", "y"] }), clear).decision, "HOLD_SUBCONSCIOUS");
  assert.equal(decide(lessonCandidate({ verified_ids: [REAL, 7] }), clear).decision, "HOLD_SUBCONSCIOUS");
  assert.equal(decide(lessonCandidate({ claim: 1234567890123 }), clear).decision, "REJECT_WEAK_EVIDENCE");
  assert.equal(decide(lessonCandidate({ verified_ids: [" " + REAL.toLowerCase(), MADE_UP[0]] }), clear).decision, "PROMOTE");
});

check("the gate's own rules hold without help: a job never promotes, PROMOTE needs clear, the floor is two", () => {
  const asJob = lessonCandidate({ kind: "job" });
  assert.equal(decide(asJob, clear).decision, "HOLD_SUBCONSCIOUS");
  assert.equal(decide(lessonCandidate({ kind: undefined }), clear).decision, "HOLD_SUBCONSCIOUS");
  assert.equal(decide(lessonCandidate(), { ...clear, conflict_status: "weak" }).decision, "REQUIRES_HUMAN");
  assert.equal(decide(lessonCandidate({ min_sources: 1, verified_ids: [REAL], verified_count: 1 }), clear).decision, "HOLD_SUBCONSCIOUS");
});

check("Build Record refuses a repeated member, a lone member, and a group id that is not a ULID", () => {
  const b = (over) => () => build(one({ candidate: lessonCandidate(over), receipt: clear }), noRefs);
  assert.throws(b({ verified_ids: [REAL, REAL.toLowerCase()] }), /distinct members/);
  assert.throws(b({ verified_ids: [REAL], verified_count: 1 }), /distinct members/);
  assert.throws(b({ verified_ids: [REAL, "x"] }), /distinct members/);
  assert.throws(b({ learning_intent_id: "group-1" }), /without a learning intent id/);
  const out = build(one({ candidate: lessonCandidate({ verified_ids: [" " + REAL.toLowerCase(), MADE_UP[0]] }), receipt: clear }), noRefs)[0].json.record;
  assert.deepEqual(out.source_intent_ids, [REAL, MADE_UP[0]]);
});

check("only a 2xx counts as a write or a search, and an incomplete receipt is never a decision", () => {
  assert.throws(() => write(one({ statusCode: 300, body: {} }), fromBuild), /HTTP 300/);
  const refs = (name) => { assert.equal(name, "Search Needed"); return { first: () => ({ json: { candidate: lessonCandidate() } }) }; };
  assert.throws(() => assemble(one({ statusCode: 300, body: clear }), refs), /HTTP 300/);
  assert.throws(() => assemble(one({ statusCode: 200, body: { ...clear, complete: false } }), refs), /did not complete/);
  const colonId = { ...ctx, record: { _id: "a:b", text: "t" } };
  let message = "";
  try { write(one({ statusCode: 500, body: "x" }), () => ({ first: () => ({ json: colonId }) })); } catch (e) { message = e.message; }
  assert.equal(message.includes(":"), false, message);
});

console.log(n + " checks passed");
