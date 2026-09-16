/**
 * Does the Pulse tell the truth about the feeder?
 *
 *   node n8n/devon/heartbeat/compose_pulse.test.mjs
 *
 * The node body is plain JS that reads n8n's `$('Node').all()` and ends in a
 * `return`, so it runs here inside a Function with `$` stubbed. No n8n, no
 * network, no clock games beyond the rows themselves.
 *
 * WHY THESE FOUR CASES
 *
 * Two are real. On 2026-09-16 the 04:00:15Z beat reported `feeder_silent`
 * against the VPS cutover proof job while the Build 12 feeder was armed,
 * correct, and simply not due until 06:00Z; and at 06:00:53Z the feeder ran and
 * carried that job. Those are cases A and B, with the row shapes they actually
 * had. The other two are the faults the split is for: a feeder that ran and
 * skipped a job, and a job merely waiting for its slot.
 *
 * Case D is the one that matters most, because it is the false positive the old
 * rule produced on every beat for up to twenty three hours. The old rule is
 * reimplemented here, in eight lines, purely so the test can show it firing
 * where the new one is silent. A fix nobody measured against the behaviour it
 * replaces is a claim.
 */
import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const SOURCE = readFileSync(new URL("./compose_pulse.js", import.meta.url), "utf8");
const composePulse = new Function("$", SOURCE);

const HOUR = 3600000;
const ago = (hours) => new Date(Date.now() - hours * HOUR).toISOString();

/** Run the real node body over one set of table rows. */
function pulse({ jobs = [], feed = [], soul = [], beats = [] }) {
  const tables = { "Read Jobs": jobs, "Read Feed": feed, "Read Soul Log": soul, "Read Beats": beats };
  const $ = (name) => ({ all: () => (tables[name] || []).map((json) => ({ json })) });
  const out = composePulse($);
  const findings = {};
  for (const line of String(out[0].json.findings).split("\n")) {
    const cut = line.indexOf(" | ");
    if (cut > 0) findings[line.slice(0, cut)] = line.slice(cut + 3);
  }
  return { findings, keys: Object.keys(findings).sort(), body: out[0].json.body };
}

/** The rule this change replaces: any COMPLETED job unfed for 40 minutes. */
function oldRuleFires({ jobs, feed }) {
  const fed = new Set(feed.map((f) => String(f.intent_id)));
  return jobs.some(
    (j) =>
      String(j.state) === "COMPLETED" &&
      !fed.has(String(j.intent_id)) &&
      (Date.now() - Date.parse(j.updatedAt)) / 60000 > 40,
  );
}

let checks = 0;
const check = (name, run) => { run(); console.log(`ok ${++checks} ${name}`); };

/* A. The real 04:00:15Z beat. The proof job completed at 03:00:41Z; the feed log
 *    still held only the two 2026-08 smoke rows, because the feeder had never
 *    run on the VPS. The feeder really was down, and nothing had ever fed. */
const A = {
  jobs: [{ intent_id: "01M2KT8WM4RPZ90BCTZPVXH6HK", state: "COMPLETED", updatedAt: ago(1) }],
  feed: [
    { intent_id: "SMOKETEST0FEEDER0000000000", fed_at: "2026-08-25T06:35:28.967Z", gate_decision: "REQUIRES_HUMAN", webhook_status: 200 },
    { intent_id: "SMOKE-COMMITTER-V2-20260825", fed_at: "2026-08-25T18:45:00.000Z", gate_decision: "PROMOTE", webhook_status: 0 },
  ],
};
check("A, the real 04:00Z estate: feeder_down fires, and it is the finding that is true", () => {
  const { findings, keys } = pulse(A);
  assert.ok(keys.includes("feeder_down"), `expected feeder_down, got ${keys}`);
  assert.ok(!keys.includes("feeder_skipped"), "a job that no feeder run has passed over is not skipped");
  assert.match(findings.feeder_down, /has not run in \d+h/);
  assert.match(findings.feeder_down, /1 COMPLETED job\(s\)/);
});

/* B. The real estate after 06:00:53Z: the feeder ran and carried the job. */
const B = {
  jobs: [{ intent_id: "01M2KT8WM4RPZ90BCTZPVXH6HK", state: "COMPLETED", updatedAt: ago(7) }],
  feed: [
    ...A.feed,
    { intent_id: "01M2KT8WM4RPZ90BCTZPVXH6HK", fed_at: ago(4), gate_decision: "HOLD_SUBCONSCIOUS", webhook_status: 200 },
  ],
};
check("B, the real estate after the feeder ran: neither feeder finding fires", () => {
  const { keys } = pulse(B);
  assert.ok(!keys.includes("feeder_down"), `feeder ran 4h ago; got ${keys}`);
  assert.ok(!keys.includes("feeder_skipped"), `the job was carried; got ${keys}`);
});

/* C. The defect the old rule could not distinguish: the feeder RAN after this
 *    job completed, carried something else, and passed this one over. */
const C = {
  jobs: [
    { intent_id: "JOB-CARRIED", state: "COMPLETED", updatedAt: ago(9) },
    { intent_id: "JOB-PASSED-OVER", state: "COMPLETED", updatedAt: ago(9) },
  ],
  feed: [{ intent_id: "JOB-CARRIED", fed_at: ago(3), gate_decision: "HOLD_SUBCONSCIOUS", webhook_status: 200 }],
};
check("C, the feeder ran and passed a job over: feeder_skipped names that job and only that job", () => {
  const { findings, keys } = pulse(C);
  assert.ok(keys.includes("feeder_skipped"), `expected feeder_skipped, got ${keys}`);
  assert.ok(!keys.includes("feeder_down"), "the feeder ran 3h ago, it is not down");
  assert.match(findings.feeder_skipped, /JOB-PASSED-OVER/);
  assert.ok(!findings.feeder_skipped.includes("JOB-CARRIED"), "a carried job is not skipped");
});

/* D. The false positive. A job completed an hour ago; the feeder last ran three
 *    hours ago, BEFORE it, so the job is waiting for its slot, not late. This
 *    is the shape the old rule alerted on every beat until the slot came. */
const D = {
  jobs: [{ intent_id: "JOB-WAITING", state: "COMPLETED", updatedAt: ago(1) }],
  feed: [{ intent_id: "OLDER-JOB", fed_at: ago(3), gate_decision: "HOLD_SUBCONSCIOUS", webhook_status: 200 }],
};
check("D, a job waiting for its daily slot: the new rule is silent", () => {
  const { keys } = pulse(D);
  assert.ok(!keys.includes("feeder_down"), `feeder ran 3h ago; got ${keys}`);
  assert.ok(!keys.includes("feeder_skipped"), `the feeder has not run since it completed; got ${keys}`);
});
check("D, and the rule it replaces DID fire there, so this is a change and not a rename", () => {
  assert.equal(oldRuleFires(D), true, "the old 40 minute rule should fire on a job waiting for its slot");
  assert.equal(oldRuleFires(A), true, "the old rule fired on the real 04:00Z estate too, for the wrong reason");
  assert.equal(oldRuleFires(C), true, "the old rule did catch the genuine skip, slower and unnamed");
});

/* The dead feeder on a quiet week: the case the old rule could not see at all,
 * because it needed a COMPLETED job to be waiting before it would look. */
check("E, a feeder dead for days while every job is already carried: still caught", () => {
  const { findings, keys } = pulse({
    jobs: [{ intent_id: "JOB-CARRIED", state: "COMPLETED", updatedAt: ago(200) }],
    feed: [{ intent_id: "JOB-CARRIED", fed_at: ago(180), gate_decision: "PROMOTE", webhook_status: 200 }],
  });
  assert.ok(keys.includes("feeder_down"), `expected feeder_down, got ${keys}`);
  assert.ok(!keys.includes("feeder_skipped"), "nothing is unfed, so nothing is skipped");
  assert.match(findings.feeder_down, /180h/);
  assert.equal(
    oldRuleFires({ jobs: [{ intent_id: "JOB-CARRIED", state: "COMPLETED", updatedAt: ago(200) }], feed: [{ intent_id: "JOB-CARRIED" }] }),
    false,
    "the old rule was blind here: every job fed, so it never looked at the feeder at all",
  );
});

/* An empty estate must not alarm forever. */
check("F, an estate with no COMPLETED job yet: no feeder finding at all", () => {
  const { keys } = pulse({ jobs: [{ intent_id: "JOB-OPEN", state: "EXECUTING", updatedAt: ago(1) }], feed: [] });
  assert.ok(!keys.includes("feeder_down"), `nothing has ever completed; got ${keys}`);
  assert.ok(!keys.includes("feeder_skipped"), `nothing has ever completed; got ${keys}`);
});

/* The old rule must be gone from the CODE, not from the file. Both names still
 * appear in the comment that explains why they were retired, and that history is
 * the most useful thing in the file: delete it and the next reader re-derives
 * the forty minutes from scratch. So assert on the executable positions, which
 * is what actually decides what DEVON says. */
check("G, the retired rule is gone from the code while its history stays in the comment", () => {
  assert.ok(!/finding\(\s*'feeder_silent'/.test(SOURCE), "feeder_silent must no longer be raised as a finding");
  assert.ok(!/^\s*const UNFED_MIN/m.test(SOURCE), "the 40 minute threshold must no longer be declared");
  assert.ok(SOURCE.includes("feeder_silent"), "the comment explaining the retirement should survive");
  assert.ok(/finding\(\s*'feeder_down'/.test(SOURCE) && /finding\(\s*'feeder_skipped'/.test(SOURCE), "both replacements are raised");
});

const EXPECTED = 8;
assert.equal(checks, EXPECTED, `${checks} checks ran; this file makes exactly ${EXPECTED}`);
console.log(`compose_pulse: ${checks} checks passed`);
