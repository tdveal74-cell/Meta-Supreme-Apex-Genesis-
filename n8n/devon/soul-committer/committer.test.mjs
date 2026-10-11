/**
 * Does the Soul Committer put a lesson to Tee, and only a lesson, quoting
 * each member job's own ledger text, and write exactly what he approved?
 *
 *   node n8n/devon/soul-committer/committer.test.mjs
 *
 * Phase 2 of the grouping build, ruled by Tee 2026-10-11: one card per
 * lesson, rejection and expiry both close it for good, the committer reads
 * the ledger rows and the group log row itself, and the record says
 * status active. Each node body runs inside a Function with `$input` and `$`
 * stubbed, the house pattern. Nothing here reads approval_queue or reaches a
 * network: the queue rows below are hand made, and no test writes anywhere.
 *
 * ONE THING HERE IS REAL: the first member is the live ledger row of the
 * 2026-09-16 cutover job, n8n/devon/learning/fixtures_ledger_2026-09-16.json,
 * the one eligible job the ledger holds. The second member is that row with
 * its identity changed, because no second eligible job exists yet (Tee ruled
 * on 2026-10-11 that it comes from real work), and the card must be shown
 * quoting two different jobs.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const load = (path) => new Function("$input", "$", readFileSync(new URL(path, import.meta.url), "utf8"));
const select = load("./select_next_proposal.js");
const onlyPost = load("./only_post_item.js");
const onlyAdopt = load("./only_adopt_items.js");
const onlyRefused = load("./only_refused_items.js");
const refusalNotice = load("./refusal_notice.js");
const logOutcome = load("./log_proposal_outcome.js");
const explode = load("./explode_proposal_rows.js");
const resolveApproved = load("./resolve_approved.js");
const recordOutcome = load("./record_commit_outcome.js");
const resolveClosed = load("./resolve_closed.js");
const closedDigest = load("./closed_digest.js");
const RULES = readFileSync(new URL("../learning/lesson_evidence.js", import.meta.url), "utf8");
const rules = new Function(RULES + "; return { lessonCheckMember, lessonIdList };")();
const FIXTURE = JSON.parse(readFileSync(new URL("../learning/fixtures_ledger_2026-09-16.json", import.meta.url), "utf8"));
const SOUL_PY = readFileSync(new URL("../../../services/intelligence/soul.py", import.meta.url), "utf8");

let n = 0;
function check(name, fn) { fn(); n++; console.log("ok   " + name); }
const items = (rows) => rows.map((json) => ({ json }));
const input = (rows) => ({ all: () => items(rows), first: () => items(rows)[0] });
function refs(map) {
  return (name) => {
    if (!(name in map)) { throw new Error("unexpected node reference " + name); }
    const rows = map[name];
    return { all: () => items(rows), first: () => items(rows)[0], itemMatching: (i) => items(rows)[i] };
  };
}

const LEARN = "01M4GRP0A1B2C3D4E5F6G7H8J9";
const REAL = "01M2KT8WM4RPZ90BCTZPVXH6HK";
const SECOND = "01M4A0B1C2D3E4F5G6H7J8K9MN";
const THIRD = "01M4B0B1C2D3E4F5G6H7J8K9MN";
for (const id of [LEARN, REAL, SECOND, THIRD]) { assert.match(id, /^[0-9A-HJKMNP-TV-Z]{26}$/); }

/** A member's ledger row: the real one, or the real one with a new identity. */
function memberRow(id, overrides = {}) {
  const env = JSON.parse(JSON.stringify(FIXTURE.envelope));
  const row = JSON.parse(JSON.stringify(FIXTURE.row));
  if (id !== REAL) {
    env.intent_id = id;
    env.idempotency_key = "second-" + id;
    env.verification.verified_at = "2026-10-12T15:04:05Z";
    env.verification.evidence = ["verify_card REQ-20261012-Zx9Q2w", "verify_card REQ-20261012-Zx9Q2w approved by Tee"];
    env.receipt.summary = "Tee verified the second job and approved card REQ-20261012-Zx9Q2w. Job: a \"quoted\" real task";
    row.intent_id = id;
    row.idempotency_key = env.idempotency_key;
  }
  Object.assign(env, overrides.envelope || {});
  Object.assign(row, overrides.row || {});
  row.envelope = JSON.stringify(env);
  return row;
}

const CLAIM = "When a lane hands work to \"another\" lane, confirm the receiver read the record back  before calling it done; ünïcode stays.";
const feed = (over = {}) => ({ id: 13, intent_id: LEARN, fed_at: "2026-10-13T06:00:54Z", webhook_status: 200, gate_decision: "PROMOTE", claim: CLAIM, area: "Systems", ...over });
const group = (over = {}) => ({ group_key: "handoff-readback:" + [REAL, SECOND].sort().join(","), lesson_key: "handoff-readback", learning_intent_id: LEARN, source_intent_ids: JSON.stringify([REAL, SECOND]), state: "FED", gate_decision: "PROMOTE", conflict_status: "clear", receipt_id: "cr_01M4RECEIPT", top_match: "devon-2026-08-25-REQ-x 0.21", ...over });
const SMOKE_FEED = { id: 2, intent_id: "SMOKE-COMMITTER-V2-20260825", gate_decision: "PROMOTE", claim: "smoke claim. Area: smoke-test", area: "smoke-test", webhook_status: 0 };
const SMOKE_COMMIT = { id: 1, intent_id: "SMOKE-COMMITTER-V2-20260825", state: "REVERTED", request_id: "REQ-20260825-Jundef" };

/** Select Next Proposal over one poll's reads. Empty reads arrive as one {} item, as alwaysOutputData hands them over.
 * The group and ledger rows pass through the same filters the live Fetch Lesson Groups and Fetch Member Jobs apply,
 * unless raw is set, which tests the body's own defence in depth against rows live would never hand it. */
const LIVE_GROUP = (g) => g.gate_decision === "PROMOTE";
const LIVE_JOB = (r) => r.state === "COMPLETED" && r.verification_state === "passed" && r.verification_method === "human_watch";
function poll({ feeds = [feed()], commits = [SMOKE_COMMIT], queue = [{}], groups = [group()], jobs = [memberRow(REAL), memberRow(SECOND)], raw = false } = {}) {
  const or = (rows) => (rows.length ? rows : [{}]);
  if (!raw) { groups = groups.filter(LIVE_GROUP); jobs = jobs.filter(LIVE_JOB); }
  return select(input(or(jobs)), refs({
    "Fetch Promoted Jobs": feeds,
    "Fetch Commit Log": or(commits),
    "Fetch Open Requests": or(queue),
    "Fetch Lesson Groups": or(groups),
    "Fetch Member Jobs": or(jobs),
  })).map((i) => i.json);
}
const only = (mode, out) => out.filter((o) => o.mode === mode);
const reasonsOf = (out) => only("refuse", out).flatMap((o) => o.reasons).join(" | ");

// ---------------------------------------------------------------- the card

check("a sound lesson raises exactly one card, and nothing is refused", () => {
  const out = poll();
  assert.equal(out.length, 1);
  assert.equal(out[0].mode, "post");
  assert.equal(out[0].intent_id, LEARN);
  assert.equal(out[0].lesson_key, "handoff-readback");
  assert.deepEqual(JSON.parse(out[0].source_intent_ids), [REAL, SECOND]);
});

check("the card quotes the claim byte for byte, and names the key, the area and the intent", () => {
  const body = poll()[0].approval_body;
  assert.ok(body.what_happens.includes("\"" + CLAIM + "\""), "the claim, double spaces, quotes and accents intact");
  assert.ok(body.what_happens.includes("Lesson key: handoff-readback. Area: Systems. Learning intent: " + LEARN + "."));
  assert.equal(body.title, "Soul commit: " + CLAIM.slice(0, 90));
  assert.ok(body.what_happens.includes("never touches tee-soul-layer"));
});

check("the card quotes every member's own ledger text, uncut", () => {
  const what = poll()[0].approval_body.what_happens;
  const real = FIXTURE.envelope;
  assert.ok(what.includes("1. Job " + REAL + ", verify card REQ-20260916-J1ApUy, verified " + real.verification.verified_at + "."));
  assert.ok(what.includes("Receipt: \"" + real.receipt.summary + "\""), "the real receipt summary, verbatim");
  for (const e of real.verification.evidence) { assert.ok(what.includes("\"" + e + "\""), "evidence " + e); }
  const second = JSON.parse(memberRow(SECOND).envelope);
  assert.ok(what.includes("2. Job " + SECOND + ", verify card REQ-20261012-Zx9Q2w, verified 2026-10-12T15:04:05Z."));
  assert.ok(what.includes("Receipt: \"" + second.receipt.summary + "\""));
  assert.ok(what.includes("It stands on 2 completed jobs"));
});

check("the card carries the conflict receipt and the top match, and says what rejecting costs", () => {
  const what = poll()[0].approval_body.what_happens;
  assert.ok(what.includes("Conflict check: receipt cr_01M4RECEIPT, status clear, top match devon-2026-08-25-REQ-x 0.21."));
  assert.ok(what.includes("closes it for good: these 2 jobs can never back another lesson, and the lesson key stays open"));
});

check("the evidence starts intent <learning_intent_id>; so adoption still finds the card", () => {
  const body = poll()[0].approval_body;
  assert.ok(body.evidence.startsWith("intent " + LEARN + ";"));
  assert.deepEqual(Object.keys(body).sort(), ["action_type", "blast_radius", "evidence", "project", "requested_by", "reversible", "title", "what_happens"]);
  assert.equal(body.requested_by, "soul-committer");
});

check("a missing receipt summary is said, not invented", () => {
  const row = memberRow(SECOND, { envelope: { receipt: { outcome: "completed" } } });
  const what = poll({ jobs: [memberRow(REAL), row] })[0].approval_body.what_happens;
  assert.ok(what.includes("Receipt: none recorded"));
});

check("five members are all quoted; the group's order is the card's order", () => {
  const ids = [REAL, SECOND, THIRD, "01M4C0B1C2D3E4F5G6H7J8K9MN", "01M4D0B1C2D3E4F5G6H7J8K9MN"];
  const out = poll({ groups: [group({ source_intent_ids: JSON.stringify(ids) })], jobs: ids.map((id) => memberRow(id)) });
  assert.equal(out[0].mode, "post");
  const what = out[0].approval_body.what_happens;
  ids.forEach((id, i) => assert.ok(what.includes((i + 1) + ". Job " + id + ","), id));
});

// ------------------------------------------------------- refusals, for good

function refused(args, pattern) {
  const out = poll(args);
  assert.equal(only("post", out).length, 0, "no card");
  assert.equal(only("refuse", out).length, 1);
  assert.match(reasonsOf(out), pattern);
  return only("refuse", out)[0];
}

check("a member named by a rejected lesson's commit-log row is refused, with no card", () => {
  const rejected = { intent_id: "01M3OLDGRP000000000000000A".replace("O", "0"), state: "REJECTED", source_intent_ids: JSON.stringify([SECOND, THIRD]) };
  const r = refused({ commits: [SMOKE_COMMIT, rejected] }, /member 01M4A0B1C2D3E4F5G6H7J8K9MN already appears in the commit log under 01M3/);
  assert.deepEqual(JSON.parse(r.source_intent_ids), [REAL, SECOND]);
});

check("an expired lesson burns its members exactly as a rejected one does", () => {
  const expired = { intent_id: "01M3EXP0000000000000000000", state: "EXPIRED", source_intent_ids: [REAL] };
  refused({ commits: [expired] }, /member 01M2KT8WM4RPZ90BCTZPVXH6HK already appears in the commit log under 01M3EXP/);
});

check("a job once proposed alone, under the old single job path, is used too", () => {
  refused({ commits: [{ intent_id: REAL.toLowerCase(), state: "REVERTED" }] }, /member 01M2KT8WM4RPZ90BCTZPVXH6HK already appears/);
});

check("a PROMOTE row with no group log row is refused, and lists no members", () => {
  const r = refused({ groups: [] }, /no group log row recording PROMOTE names learning intent .*a lesson needs one, and a single job never promotes/);
  assert.equal(r.source_intent_ids, "[]");
  assert.equal(r.lesson_key, "");
});

check("every group log fault is named", () => {
  refused({ groups: [group({ state: "FAILED" })] }, /state FAILED, not FED/);
  refused({ groups: [group({ gate_decision: "REQUIRES_HUMAN" })], raw: true }, /records REQUIRES_HUMAN, not PROMOTE/);
  refused({ groups: [group({ conflict_status: "requires_human" })] }, /receipt reads requires_human, not clear/);
  refused({ groups: [group({ receipt_id: "" })] }, /no conflict receipt id/);
  refused({ groups: [group({ lesson_key: " " })] }, /names no lesson key/);
  refused({ groups: [group(), group()] }, /2 group log rows name learning intent/);
  refused({ groups: [group({ source_intent_ids: JSON.stringify([REAL]) })], jobs: [memberRow(REAL)] }, /lists 1 member job\(s\); a lesson needs 2 to 5/);
  const six = [REAL, SECOND, THIRD, "01M4C0B1C2D3E4F5G6H7J8K9MN", "01M4D0B1C2D3E4F5G6H7J8K9MN", "01M4E0B1C2D3E4F5G6H7J8K9MN"];
  refused({ groups: [group({ source_intent_ids: JSON.stringify(six) })], jobs: six.map((id) => memberRow(id)) }, /lists 6 member job/);
  refused({ groups: [group({ source_intent_ids: JSON.stringify([REAL, SECOND, REAL.toLowerCase()]) })] }, /one job more than once/);
});

check("the feed log and the group log must agree on the key and the members", () => {
  refused({ feeds: [feed({ lesson_key: "another-key" })] }, /feed log names lesson another-key and the group log names handoff-readback/);
  refused({ feeds: [feed({ source_intent_ids: JSON.stringify([REAL, THIRD]) })] }, /list different member jobs/);
  const out = poll({ feeds: [feed({ lesson_key: "handoff-readback", source_intent_ids: [SECOND.toLowerCase(), REAL] })] });
  assert.equal(out[0].mode, "post", "the same members in another order and case agree");
});

check("every member ledger fault is named", () => {
  refused({ jobs: [memberRow(REAL)] }, /member 01M4A0B1C2D3E4F5G6H7J8K9MN has no COMPLETED, passed, human watched ledger row/);
  refused({ jobs: [memberRow(REAL), memberRow(SECOND), memberRow(SECOND)] }, /has 2 ledger rows/);
  refused({ jobs: [memberRow(REAL), memberRow(SECOND, { row: { state: "CANCELLED" } })], raw: true }, /state is CANCELLED/);
  refused({ jobs: [memberRow(REAL), memberRow(SECOND, { row: { verification_method: "auto_no_artifact" } })], raw: true }, /not verified by a human watch/);
  refused({ jobs: [memberRow(REAL), memberRow(SECOND, { row: { verification_state: "pending" } })], raw: true }, /verification is pending/);
  refused({ jobs: [memberRow(REAL), memberRow(SECOND, { envelope: { verification: { evidence: ["xverify_card REQ-20261012-Zx9Q2w approved by Tee at noon"], verified_at: "2026-10-12T15:04:05Z" } } })] }, /no verify card approved by Tee/);
  refused({ jobs: [memberRow(REAL), memberRow(SECOND, { envelope: { verification: { evidence: ["xverify_card REQ-20261012-Zx9Q2w approved by Tee"], verified_at: "2026-10-12T15:04:05Z" } } })] }, /no verify card approved by Tee/);
  refused({ jobs: [memberRow(REAL), { ...memberRow(SECOND), envelope: "{not json" }] }, /envelope is unreadable/);
  refused({ jobs: [memberRow(REAL), memberRow(SECOND, { envelope: { intent_id: THIRD } })] }, /envelope names another job/);
  refused({ jobs: [memberRow(REAL), memberRow(SECOND, { envelope: { verification: { evidence: ["verify_card REQ-20261012-Zx9Q2w"], verified_at: "2026-10-12T15:04:05Z" } } })] }, /no verify card approved by Tee/);
  refused({ jobs: [memberRow(REAL), memberRow(SECOND, { envelope: { verification: { evidence: ["verify_card REQ-20261012-Zx9Q2w approved by Tee"], verified_at: "soon" } } })] }, /no readable verified_at/);
});

check("a PROMOTE row with no claim is refused, not skipped", () => {
  refused({ feeds: [feed({ claim: "   " })] }, /carries no claim/);
});

check("a refusal becomes one REFUSED commit-log row with every reason, and one email", () => {
  const out = poll({ groups: [group({ state: "FAILED", conflict_status: "" })] });
  const rows = onlyRefused(input(out), refs({})).map((i) => i.json);
  assert.equal(rows.length, 1);
  const r = rows[0];
  assert.equal(r.state, "REFUSED");
  assert.equal(r.request_id, "");
  assert.equal(r.intent_id, LEARN);
  assert.equal(r.resolved_at, r.proposed_at);
  assert.match(r.note, /^refused before a card, so no card was raised: .*state FAILED, not FED; its conflict receipt reads nothing/);
  assert.deepEqual(Object.keys(r).sort(), ["area", "claim", "intent_id", "lesson_key", "note", "proposed_at", "record_id", "request_id", "resolved_at", "source_intent_ids", "state"]);
  const mail = refusalNotice(input(rows), refs({}))[0].json;
  assert.equal(mail.subject, "Soul Committer: 1 lesson(s) refused before a card");
  assert.ok(mail.body.includes("REFUSED " + LEARN + " (lesson handoff-readback)"));
  assert.ok(mail.body.includes(CLAIM));
  assert.deepEqual(refusalNotice(input([]), refs({})), []);
  assert.deepEqual(onlyRefused(input(poll()), refs({})), [], "a sound poll refuses nothing");
});

check("the commit-log row a refusal or a rejection leaves is read by the feeder's own E6 rule", () => {
  const out = poll({ groups: [group({ state: "FAILED" })] });
  const row = onlyRefused(input(out), refs({}))[0].json;
  const ctx = { lessonKey: "handoff-readback", entry: { status: "active", evidence_ids: JSON.stringify([REAL, SECOND]) }, rowsById: { [REAL]: memberRow(REAL) }, groups: [], committedIds: [row.source_intent_ids] };
  const verdict = rules.lessonCheckMember(REAL, ctx);
  assert.ok(verdict.reasons.includes("E6 already named by a soul commit"), verdict.reasons.join("; "));
});

// --------------------------------------------- what the poll does not touch

check("the live tables as they stand today raise nothing and refuse nothing", () => {
  // Feed log: the smoke PROMOTE row, already closed in the commit log as REVERTED.
  assert.deepEqual(poll({ feeds: [SMOKE_FEED], commits: [SMOKE_COMMIT], groups: [], jobs: [memberRow(REAL)] }), []);
});

check("empty reads arrive as one {} item and change nothing", () => {
  assert.deepEqual(poll({ feeds: [{}], commits: [], groups: [], jobs: [] }), []);
  assert.equal(poll({ commits: [], queue: [] })[0].mode, "post");
});

check("one card per poll; the rest wait, and refusals go out beside it", () => {
  const LEARN2 = "01M4GRP1A1B2C3D4E5F6G7H8J9";
  const LEARN3 = "01M4GRP2A1B2C3D4E5F6G7H8J9";
  const out = poll({
    feeds: [feed(), feed({ intent_id: LEARN2 }), feed({ intent_id: LEARN3 })],
    groups: [group(), group({ learning_intent_id: LEARN2, source_intent_ids: JSON.stringify([THIRD, "01M4C0B1C2D3E4F5G6H7J8K9MN"]) })],
    jobs: [REAL, SECOND, THIRD, "01M4C0B1C2D3E4F5G6H7J8K9MN"].map((id) => memberRow(id)),
  });
  assert.equal(only("post", out).length, 1);
  assert.equal(only("post", out)[0].intent_id, LEARN);
  assert.equal(only("post", out)[0].deferred, 1);
  assert.deepEqual(only("refuse", out).map((o) => o.intent_id), [LEARN3]);
  assert.equal(onlyPost(input(out), refs({})).length, 1);
});

// ------------------------------------------------------------------ adoption

const QUEUED = { request_id: "REQ-20261013-AbC123", status: "pending", requested_by: "soul-committer", requested_at: "2026-10-13T07:00:01Z", expires_at: "2026-10-16T07:00:01Z", evidence: "intent " + LEARN + "; lesson handoff-readback; gate decision PROMOTE", what_happens: poll()[0].approval_body.what_happens };

check("a card already in the queue is adopted with its lesson, never raised twice", () => {
  const out = poll({ queue: [QUEUED] });
  assert.equal(out.length, 1);
  assert.equal(out[0].mode, "adopt");
  assert.equal(out[0].request_id, "REQ-20261013-AbC123");
  const rows = onlyAdopt(input(out), refs({})).map((i) => i.json);
  assert.equal(rows[0].state, "PROPOSED");
  assert.equal(rows[0].lesson_key, "handoff-readback");
  assert.deepEqual(JSON.parse(rows[0].source_intent_ids), [REAL, SECOND]);
});

check("an adoption holds back this poll's posts and refusals", () => {
  const LEARN2 = "01M4GRP1A1B2C3D4E5F6G7H8J9";
  const out = poll({ queue: [QUEUED], feeds: [feed(), feed({ intent_id: LEARN2 })] });
  assert.deepEqual(out.map((o) => o.mode), ["adopt"]);
});

check("a queued response becomes a PROPOSED row carrying the lesson", () => {
  const posted = onlyPost(input(poll()), refs({})).map((i) => i.json);
  const res = { statusCode: 200, body: { queued: true, request_id: "REQ-20261013-AbC123", expires_at: "2026-10-16T07:00:01Z" } };
  const summary = logOutcome(input([res]), refs({ "Only Post Item": posted }))[0].json;
  assert.equal(summary.failed_count, 0);
  const rows = explode(input([summary]), refs({})).map((i) => i.json);
  assert.equal(rows.length, 1);
  assert.equal(rows[0].state, "PROPOSED");
  assert.equal(rows[0].claim, CLAIM);
  assert.equal(rows[0].lesson_key, "handoff-readback");
  assert.deepEqual(JSON.parse(rows[0].source_intent_ids), [REAL, SECOND]);
  const failed = logOutcome(input([{ statusCode: 500, body: "down" }]), refs({ "Only Post Item": posted }))[0].json;
  assert.equal(failed.rows.length, 0);
  assert.equal(failed.failed_count, 1);
});

check("a queued card is adopted only for a sound lesson; for an unsound one it is refused with its request id", () => {
  const out = poll({ queue: [QUEUED], groups: [group({ conflict_status: "requires_human" })] });
  assert.equal(only("adopt", out).length, 0, "an adoption can never skip a lesson check");
  const r = only("refuse", out)[0];
  assert.equal(r.request_id, "REQ-20261013-AbC123");
  assert.match(r.reasons.join(" | "), /a queued card REQ-20261013-AbC123 names this intent and was not adopted, so approving it commits nothing/);
  const row = onlyRefused(input(out), refs({}))[0].json;
  assert.equal(row.state, "REFUSED");
  assert.equal(row.request_id, "REQ-20261013-AbC123", "REFUSED, never PROPOSED, so the commit lane cannot reach it");
  const mail = refusalNotice(input([row]), refs({}))[0].json;
  assert.ok(mail.body.includes("queued card REQ-20261013-AbC123 was not adopted"));
  const burned = { intent_id: "01M3EXP0000000000000000000", state: "REJECTED", source_intent_ids: JSON.stringify([REAL]) };
  assert.equal(only("adopt", poll({ queue: [QUEUED], commits: [burned] })).length, 0, "nor one with a burned member");
});

check("a queued text that does not quote the claim is never adopted; the committer raises its own card", () => {
  const forged = { ...QUEUED, what_happens: "DEVON writes one lesson: \"something else entirely\"." };
  const out = poll({ queue: [forged] });
  assert.deepEqual(out.map((o) => o.mode), ["post"]);
  const trimmed = { ...QUEUED, what_happens: "  " + QUEUED.what_happens + "\n" };
  assert.equal(poll({ queue: [trimmed] })[0].mode, "adopt", "the queue's own trim still adopts");
});

check("an intent closed with no members is not carded again under another letter case", () => {
  const closed = { intent_id: LEARN, state: "REFUSED", source_intent_ids: "[]" };
  assert.deepEqual(poll({ commits: [closed], feeds: [feed({ intent_id: LEARN.toLowerCase() })] }), []);
});

check("the Area comes from the feed row only, never from the claim", () => {
  const claim = "Read the record back before calling a handoff done. Area: whichever lane owns the record must do it.";
  const out = poll({ feeds: [feed({ area: "", claim: claim })] });
  assert.equal(out[0].area, "");
  assert.ok(out[0].approval_body.what_happens.includes("Area: unstated."));
});

check("a group member list holding anything but job ids is refused", () => {
  refused({ groups: [group({ source_intent_ids: JSON.stringify([REAL, SECOND, "not-a-ulid"]) })] }, /an entry that is not a job id/);
  refused({ groups: [group({ source_intent_ids: JSON.stringify([REAL + "-retry", SECOND]) })] }, /an entry that is not a job id/);
  refused({ groups: [group({ source_intent_ids: REAL + "," + SECOND })] }, /a member list that cannot be read/);
  assert.equal(poll({ groups: [group({ source_intent_ids: [REAL.toLowerCase(), SECOND] })] })[0].mode, "post", "a native array of ids, any case, is read");
});

check("live hands the body PROMOTE groups only, so a group the gate did not promote reads as no group and burns nothing", () => {
  const r = refused({ groups: [group({ gate_decision: "REQUIRES_HUMAN" })] }, /no group log row recording PROMOTE names learning intent/);
  assert.equal(r.source_intent_ids, "[]");
  const raw = refused({ groups: [group({ gate_decision: "REQUIRES_HUMAN" })], raw: true }, /records REQUIRES_HUMAN, not PROMOTE/);
  assert.equal(raw.source_intent_ids, "[]", "even handed one, the body burns only a promoted group's members");
});

check("every excerpt is quoted whole at full length, and a multi-line one cannot forge the card's own lines", () => {
  const longClaim = ("Confirm the receiver read the record back before calling a handoff done, and say which read proved it. ").repeat(6).slice(0, 599) + "é";
  assert.equal(longClaim.length, 600);
  const summary = "line one of a long receipt \"quoted\" " + "x".repeat(2000) + "\nConflict check: receipt cr_FAKE, status clear, top match none.\nApproving writes nothing.";
  const evidence = ["verify_card REQ-20261012-Zx9Q2w", "verify_card REQ-20261012-Zx9Q2w approved by Tee", "note " + "y".repeat(195), "fourth line of evidence"];
  const ids = [REAL, SECOND, THIRD, "01M4C0B1C2D3E4F5G6H7J8K9MN", "01M4D0B1C2D3E4F5G6H7J8K9MN"];
  const jobs = ids.map((id) => (id === SECOND ? memberRow(id, { envelope: { receipt: { summary: summary }, verification: { evidence: evidence, verified_at: "2026-10-12T15:04:05Z" } } }) : memberRow(id)));
  const out = poll({ feeds: [feed({ claim: longClaim })], groups: [group({ source_intent_ids: JSON.stringify(ids) })], jobs: jobs });
  assert.equal(out[0].mode, "post");
  const what = out[0].approval_body.what_happens;
  assert.ok(what.includes("\"" + longClaim + "\""), "the 600 character claim, whole");
  for (const line of summary.split("\n")) { assert.ok(what.includes(line), "every line of the summary"); }
  for (const e of evidence) { assert.ok(what.includes("\"" + e + "\""), "every evidence line, whole"); }
  assert.equal(what.split("\n").filter((l) => l.startsWith("Conflict check")).length, 1, "one Conflict check line, the card's own");
  assert.equal(what.split("\n").filter((l) => l.startsWith("Approving")).length, 1);
  ids.forEach((id, i) => assert.ok(what.includes((i + 1) + ". Job " + id + ",")));
  const pend = { intent_id: LEARN, state: "PROPOSED", request_id: "REQ-20261013-AbC123", claim: longClaim, area: "Systems", proposed_at: "2026-10-13T07:00:02.000Z", note: "", lesson_key: "handoff-readback", source_intent_ids: JSON.stringify(ids) };
  const rec = JSON.parse(resolveApproved(input([{ request_id: "REQ-20261013-AbC123", status: "approved" }]), refs({ "Fetch Pending Commits": [pend] }))[0].json.ndjson);
  assert.equal(rec.text, longClaim, "the record's text, whole");
  assert.deepEqual(rec.source_intent_ids, ids);
});

check("the refusal email names the jobs a refusal burns", () => {
  const out = poll({ groups: [group({ conflict_status: "requires_human" })] });
  const rows = onlyRefused(input(out), refs({})).map((i) => i.json);
  const mail = refusalNotice(input(rows), refs({}))[0].json;
  assert.ok(mail.body.includes(REAL) && mail.body.includes(SECOND));
  assert.ok(mail.body.includes("these jobs can never back another lesson"));
});

// ------------------------------------------------------------- the record

const APPROVED = { request_id: "REQ-20261013-AbC123", status: "approved", decided_at: "2026-10-13T09:00:00Z" };
const pending = (over = {}) => ({ intent_id: LEARN, state: "PROPOSED", request_id: "REQ-20261013-AbC123", record_id: "", claim: CLAIM, area: "Systems", proposed_at: "2026-10-13T07:00:02.000Z", resolved_at: "", note: "awaiting decision", lesson_key: "handoff-readback", source_intent_ids: JSON.stringify([REAL, SECOND]), ...over });

function commitFor(rows, decisions = [APPROVED]) {
  return resolveApproved(input(decisions), refs({ "Fetch Pending Commits": rows })).map((i) => i.json);
}

check("an approved lesson writes one record: the approved text, status active, its key, its intent and its jobs", () => {
  const out = commitFor([pending()]);
  assert.equal(out.length, 1);
  const record = JSON.parse(out[0].ndjson);
  assert.equal(record._id, "devon-2026-10-13-REQ-20261013-AbC123");
  assert.equal(record.text, CLAIM, "byte for byte what the card quoted");
  assert.equal(record.kind, "lesson");
  assert.equal(record.status, "active");
  assert.equal(record.lesson_key, "handoff-readback");
  assert.equal(record.learning_intent_id, LEARN);
  assert.deepEqual(record.source_intent_ids, [REAL, SECOND]);
  assert.ok(Array.isArray(record.source_intent_ids));
  assert.equal(record.author, "devon");
  assert.equal(record.approved, true);
  assert.ok(!out[0].ndjson.includes("\n"), "one NDJSON line");
});

check("the record's keys are to_record's keys for a lesson, in to_record's order", () => {
  const block = SOUL_PY.slice(SOUL_PY.indexOf("    def to_record(self)"));
  const body = block.slice(0, block.indexOf("\nclass "));
  const keys = [...body.matchAll(/^\s+"(\w+)":/gm)].map((m) => m[1]).concat([...body.matchAll(/record\["(\w+)"\] =/g)].map((m) => m[1]));
  assert.deepEqual(keys, ["_id", "text", "kind", "area", "observed_on", "source_note", "author", "approved", "status", "lesson_key", "learning_intent_id", "source_intent_ids"]);
  assert.deepEqual(Object.keys(JSON.parse(commitFor([pending()])[0].ndjson)), keys);
});

check("an approved row without its lesson fields writes nothing and stays PROPOSED", () => {
  assert.deepEqual(commitFor([pending({ lesson_key: "" })]), []);
  assert.deepEqual(commitFor([pending({ source_intent_ids: null })]), []);
  assert.deepEqual(commitFor([pending({ source_intent_ids: JSON.stringify([REAL]) })]), []);
  assert.deepEqual(commitFor([pending({ source_intent_ids: JSON.stringify([REAL, REAL]) })]), []);
  const six = [REAL, SECOND, THIRD, "01M4C0B1C2D3E4F5G6H7J8K9MN", "01M4D0B1C2D3E4F5G6H7J8K9MN", "01M4E0B1C2D3E4F5G6H7J8K9MN"];
  assert.deepEqual(commitFor([pending({ source_intent_ids: JSON.stringify(six) })]), []);
  const later = pending({ request_id: "REQ-20261014-ZZZ999", proposed_at: "2026-10-14T00:00:00Z" });
  const out = commitFor([pending({ lesson_key: "" }), later], [APPROVED, { request_id: "REQ-20261014-ZZZ999", status: "approved" }]);
  assert.equal(out.length, 1);
  assert.equal(out[0].request_id, "REQ-20261014-ZZZ999", "a sound row behind it still commits");
});

check("a pending or rejected card writes nothing; retries keep the record id and count attempts", () => {
  assert.deepEqual(commitFor([pending()], [{ ...APPROVED, status: "pending" }]), []);
  assert.deepEqual(commitFor([pending()], [{ ...APPROVED, status: "rejected" }]), []);
  const retry = commitFor([pending({ note: "commit FAILED HTTP 500 attempt 3 at x" })])[0];
  assert.equal(retry.attempt, 4);
  assert.equal(retry.record_id, "devon-2026-10-13-REQ-20261013-AbC123");
});

check("the commit email names the lesson and its jobs", () => {
  const src = commitFor([pending()]);
  const out = recordOutcome(input([{ statusCode: 200 }]), refs({ "Resolve Approved": src }))[0].json;
  assert.ok(out.body.includes("lesson handoff-readback, standing on " + REAL + ", " + SECOND));
  assert.equal(out.rows[0].state, "COMMITTED");
});

// ------------------------------------------------------------- closure

check("a rejected or expired lesson closes for good and the digest names the burned jobs", () => {
  const now = Date.now();
  const rejected = resolveClosed(input([{ ...APPROVED, status: "rejected" }]), refs({ "Fetch Pending Commits": [pending()] })).map((i) => i.json);
  assert.equal(rejected[0].state, "REJECTED");
  assert.equal(rejected[0].lesson_key, "handoff-readback");
  assert.deepEqual(JSON.parse(rejected[0].source_intent_ids), [REAL, SECOND]);
  const past = new Date(now - 3600000).toISOString();
  const expired = resolveClosed(input([{ request_id: "REQ-20261013-AbC123", status: "pending", expires_at: past }]), refs({ "Fetch Pending Commits": [pending()] })).map((i) => i.json);
  assert.equal(expired[0].state, "EXPIRED");
  assert.deepEqual(JSON.parse(expired[0].source_intent_ids), [REAL, SECOND]);
  const old = new Date(now - 100 * 3600000).toISOString();
  const absent = resolveClosed(input([{}]), refs({ "Fetch Pending Commits": [pending({ proposed_at: old })] })).map((i) => i.json);
  assert.equal(absent[0].state, "EXPIRED");
  assert.match(absent[0].note, /closed by absence/);
  assert.deepEqual(JSON.parse(absent[0].source_intent_ids), [REAL, SECOND]);
  const queueExpired = resolveClosed(input([{ request_id: "REQ-20261013-AbC123", status: "expired" }]), refs({ "Fetch Pending Commits": [pending()] })).map((i) => i.json);
  const noExpiry = resolveClosed(input([{ request_id: "REQ-20261013-AbC123", status: "pending", expires_at: "" }]), refs({ "Fetch Pending Commits": [pending({ proposed_at: old })] })).map((i) => i.json);
  const unknown = resolveClosed(input([{ request_id: "REQ-20261013-AbC123", status: "limbo" }]), refs({ "Fetch Pending Commits": [pending({ proposed_at: old })] })).map((i) => i.json);
  for (const c of [queueExpired, noExpiry, unknown]) {
    assert.equal(c.length, 1);
    assert.equal(c[0].lesson_key, "handoff-readback");
    assert.deepEqual(JSON.parse(c[0].source_intent_ids), [REAL, SECOND]);
  }
  const every = closedDigest(input([]), refs({ "Resolve Closed": absent.concat(queueExpired, noExpiry, unknown) }))[0].json;
  assert.equal(every.body.split("\n").filter((l) => l.includes("lesson handoff-readback; these jobs can never back another lesson")).length, 4);
  const mail = closedDigest(input([]), refs({ "Resolve Closed": rejected.concat(expired) }))[0].json;
  assert.ok(mail.body.includes("lesson handoff-readback; these jobs can never back another lesson: " + JSON.stringify([REAL, SECOND])));
  assert.ok(mail.body.includes("A closed lesson's key stays open for different jobs."));
});

console.log(n + " checks passed");
