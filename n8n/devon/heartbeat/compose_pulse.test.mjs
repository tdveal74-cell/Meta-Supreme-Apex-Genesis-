/**
 * Does the Pulse tell the truth about the feeder?
 *
 *   node n8n/devon/heartbeat/compose_pulse.test.mjs
 *
 * The node body is plain JS that reads n8n's `$('Node').all()` and ends in a
 * `return`, so it runs here inside a Function with `$` stubbed. No n8n, no
 * network, no clock games beyond the rows themselves.
 *
 * WHY THESE CASES
 *
 * Three are real. On 2026-09-16 the 04:00:15Z beat reported a feeder fault
 * against the VPS cutover proof job while the Build 12 feeder was armed,
 * correct, and simply not due until 06:00Z; at 06:00:53Z the feeder ran and
 * carried that job. Those are A and B. On 2026-09-17 the 10:00:15Z beat mailed
 * Tee "the feeder has not run in 28h" while VPS execution 350 shows it ran at
 * 06:00:53Z that morning and exited in 85ms having found nothing to carry.
 * That is H, and it is the reason this file changed.
 *
 * TWO RETIRED RULES ARE REIMPLEMENTED HERE, in a few lines each, purely so the
 * tests can show them firing where the current one is silent:
 *
 *   oldRuleFires       - any COMPLETED job unfed for 40 minutes (retired 09-16)
 *   writeTimeRuleFires - max(fed_at) treated as the last run    (retired 09-17)
 *
 * A fix nobody measured against the behaviour it replaces is a claim. Both
 * retired rules fire on cases the current rule correctly passes.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";

const SOURCE = readFileSync(new URL("./compose_pulse.js", import.meta.url), "utf8");
const composePulse = new Function("$", SOURCE);

const HOUR = 3600000;
const ago = (hours) => new Date(Date.now() - hours * HOUR).toISOString();
/** One run-log row. The feeder upserts exactly one of these on every run. */
const ranAt = (hours) => [{ feeder: "build12", ran_at: ago(hours) }];

/** Run the real node body over one set of table rows. */
function pulse({ jobs = [], feed = [], soul = [], beats = [], runs = [] }) {
  const tables = {
    "Read Jobs": jobs,
    "Read Feed": feed,
    "Read Soul Log": soul,
    "Read Beats": beats,
    "Read Feeder Runs": runs,
  };
  const $ = (name) => ({ all: () => (tables[name] || []).map((json) => ({ json })) });
  const out = composePulse($);
  const findings = {};
  for (const line of String(out[0].json.findings).split("\n")) {
    const cut = line.indexOf(" | ");
    if (cut > 0) findings[line.slice(0, cut)] = line.slice(cut + 3);
  }
  return { findings, keys: Object.keys(findings).sort(), body: out[0].json.body };
}

/** Retired 2026-09-16: any COMPLETED job unfed for 40 minutes. */
function oldRuleFires({ jobs, feed }) {
  const fed = new Set(feed.map((f) => String(f.intent_id)));
  return jobs.some(
    (j) =>
      String(j.state) === "COMPLETED" &&
      !fed.has(String(j.intent_id)) &&
      (Date.now() - Date.parse(j.updatedAt)) / 60000 > 40,
  );
}

/** Retired 2026-09-17: max(fed_at) read as the feeder's last RUN. */
function writeTimeRuleFires({ jobs, feed }) {
  const completed = jobs.filter((j) => String(j.state) === "COMPLETED");
  if (completed.length === 0) return false;
  let lastFed = null;
  for (const f of feed) {
    const t = Date.parse(String(f.fed_at || ""));
    if (Number.isNaN(t)) continue;
    if (lastFed === null || t > lastFed) lastFed = t;
  }
  if (lastFed === null) return true;
  return (Date.now() - lastFed) / HOUR > 26;
}

let checks = 0;
const check = (name, run) => { run(); console.log(`ok ${++checks} ${name}`); };

/* A. The real 04:00:15Z beat of 2026-09-16. The proof job completed at
 *    03:00:41Z; the feed log still held only the two 2026-08 smoke rows,
 *    because the feeder had never run on the VPS at all. With a run log, that
 *    reads as never stamped rather than as a missed slot, which is the more
 *    honest of the two: a feeder that has never stamped and one that missed
 *    yesterday need different looks. */
const A = {
  jobs: [{ intent_id: "01M2KT8WM4RPZ90BCTZPVXH6HK", state: "COMPLETED", updatedAt: ago(1) }],
  feed: [
    { intent_id: "SMOKETEST0FEEDER0000000000", fed_at: "2026-08-25T06:35:28.967Z", gate_decision: "REQUIRES_HUMAN", webhook_status: 200 },
    { intent_id: "SMOKE-COMMITTER-V2-20260825", fed_at: "2026-08-25T18:45:00.000Z", gate_decision: "PROMOTE", webhook_status: 0 },
  ],
  runs: [],
};
check("A, the real 04:00Z estate, feeder never stamped: named as that, never as silence", () => {
  const { findings, keys } = pulse(A);
  assert.ok(keys.includes("feeder_never_stamped"), `expected feeder_never_stamped, got ${keys}`);
  assert.ok(!keys.includes("feeder_down"), "a missing stamp is not a measured missed slot");
  assert.ok(!keys.includes("feeder_skipped"), "a job that no feeder run has passed over is not skipped");
  assert.match(findings.feeder_never_stamped, /never stamped/);
});

/* B. The real estate after 06:00:53Z: the feeder ran and carried the job. */
const B = {
  jobs: [{ intent_id: "01M2KT8WM4RPZ90BCTZPVXH6HK", state: "COMPLETED", updatedAt: ago(7) }],
  feed: [
    ...A.feed,
    { intent_id: "01M2KT8WM4RPZ90BCTZPVXH6HK", fed_at: ago(4), gate_decision: "HOLD_SUBCONSCIOUS", webhook_status: 200 },
  ],
  runs: ranAt(4),
};
check("B, the real estate after the feeder ran: no feeder finding at all", () => {
  const { keys } = pulse(B);
  assert.ok(!keys.includes("feeder_down"), `feeder ran 4h ago; got ${keys}`);
  assert.ok(!keys.includes("feeder_skipped"), `the job was carried; got ${keys}`);
  assert.ok(!keys.includes("feeder_never_stamped"), `it stamped 4h ago; got ${keys}`);
});

/* C. The defect the 40 minute rule could not distinguish: the feeder RAN after
 *    this job completed, carried something else, and passed this one over. */
const C = {
  jobs: [
    { intent_id: "JOB-CARRIED", state: "COMPLETED", updatedAt: ago(9) },
    { intent_id: "JOB-PASSED-OVER", state: "COMPLETED", updatedAt: ago(9) },
  ],
  feed: [{ intent_id: "JOB-CARRIED", fed_at: ago(3), gate_decision: "HOLD_SUBCONSCIOUS", webhook_status: 200 }],
  runs: ranAt(3),
};
check("C, the feeder ran and passed a job over: feeder_skipped names that job and only that job", () => {
  const { findings, keys } = pulse(C);
  assert.ok(keys.includes("feeder_skipped"), `expected feeder_skipped, got ${keys}`);
  assert.ok(!keys.includes("feeder_down"), "the feeder ran 3h ago, it is not down");
  assert.match(findings.feeder_skipped, /JOB-PASSED-OVER/);
  assert.ok(!findings.feeder_skipped.includes("JOB-CARRIED"), "a carried job is not skipped");
});

/* D. A job completed an hour ago; the feeder last ran three hours ago, BEFORE
 *    it, so the job is waiting for its slot rather than being late. */
const D = {
  jobs: [{ intent_id: "JOB-WAITING", state: "COMPLETED", updatedAt: ago(1) }],
  feed: [{ intent_id: "OLDER-JOB", fed_at: ago(3), gate_decision: "HOLD_SUBCONSCIOUS", webhook_status: 200 }],
  runs: ranAt(3),
};
check("D, a job waiting for its daily slot: silent", () => {
  const { keys } = pulse(D);
  assert.ok(!keys.includes("feeder_down"), `feeder ran 3h ago; got ${keys}`);
  assert.ok(!keys.includes("feeder_skipped"), `the feeder has not run since it completed; got ${keys}`);
});
check("D, and the 40 minute rule DID fire there, so that was a change and not a rename", () => {
  assert.equal(oldRuleFires(D), true, "the old 40 minute rule should fire on a job waiting for its slot");
  assert.equal(oldRuleFires(A), true, "the old rule fired on the real 04:00Z estate too, for the wrong reason");
  assert.equal(oldRuleFires(C), true, "the old rule did catch the genuine skip, slower and unnamed");
});

/* E. The dead feeder on a quiet week: the case the 40 minute rule could not see
 *    at all, because it needed a COMPLETED job to be waiting before it looked. */
check("E, a feeder dead for days while every job is already carried: still caught", () => {
  const { findings, keys } = pulse({
    jobs: [{ intent_id: "JOB-CARRIED", state: "COMPLETED", updatedAt: ago(200) }],
    feed: [{ intent_id: "JOB-CARRIED", fed_at: ago(180), gate_decision: "PROMOTE", webhook_status: 200 }],
    runs: ranAt(180),
  });
  assert.ok(keys.includes("feeder_down"), `expected feeder_down, got ${keys}`);
  assert.ok(!keys.includes("feeder_skipped"), "nothing is unfed, so nothing is skipped");
  assert.match(findings.feeder_down, /180h/);
  assert.match(findings.feeder_down, /by its own run log/);
  assert.equal(
    oldRuleFires({ jobs: [{ intent_id: "JOB-CARRIED", state: "COMPLETED", updatedAt: ago(200) }], feed: [{ intent_id: "JOB-CARRIED" }] }),
    false,
    "the 40 minute rule was blind here: every job fed, so it never looked at the feeder at all",
  );
});

/* F. An empty estate must not alarm forever, with or without a stamp. */
check("F, an estate with no COMPLETED job yet: no feeder finding at all", () => {
  const { keys } = pulse({ jobs: [{ intent_id: "JOB-OPEN", state: "EXECUTING", updatedAt: ago(1) }], feed: [], runs: [] });
  assert.ok(!keys.includes("feeder_down"), `nothing has ever completed; got ${keys}`);
  assert.ok(!keys.includes("feeder_skipped"), `nothing has ever completed; got ${keys}`);
  assert.ok(!keys.includes("feeder_never_stamped"), `nothing has ever completed; got ${keys}`);
});

/* H. THE CASE THIS CHANGE EXISTS FOR, and it is the real 2026-09-17 10:00:15Z
 *    beat. One COMPLETED job, carried 28h earlier. The feeder ran 4h ago
 *    (VPS execution 350, 06:00:53Z, 85ms) and wrote nothing, because there was
 *    nothing left to carry. The beat mailed Tee that the feeder had not run in
 *    28h. It had. */
const H = {
  jobs: [{ intent_id: "01M2KT8WM4RPZ90BCTZPVXH6HK", state: "COMPLETED", updatedAt: ago(31) }],
  feed: [{ intent_id: "01M2KT8WM4RPZ90BCTZPVXH6HK", fed_at: ago(28), gate_decision: "HOLD_SUBCONSCIOUS", webhook_status: 200 }],
  runs: ranAt(4),
};
check("H, the real 2026-09-17 false alarm: a quiet run is a run, and nothing fires", () => {
  const { keys } = pulse(H);
  assert.ok(!keys.includes("feeder_down"), `the feeder ran 4h ago and had nothing to carry; got ${keys}`);
  assert.ok(!keys.includes("feeder_skipped"), `the job was carried 28h ago; got ${keys}`);
  assert.ok(!keys.includes("feeder_never_stamped"), `it stamped 4h ago; got ${keys}`);

  // The negative control. Without this the case above would pass against the
  // very implementation it exists to reject.
  assert.equal(writeTimeRuleFires(H), true, "the retired write-time rule DID fire here; that was the 10:00Z email");
  assert.equal(writeTimeRuleFires(B), false, "and it was right whenever a feed row happened to be recent");
});

/* G. The retired rules must be gone from the CODE, not from the file. Their
 *    names still appear in the comments that explain why they were retired, and
 *    that history is the most useful thing in the file: delete it and the next
 *    reader re-derives the forty minutes from scratch. So assert on the
 *    executable positions, which is what actually decides what DEVON says. */
check("G, the retired rules are gone from the code while their history stays in the comments", () => {
  assert.ok(!/finding\(\s*'feeder_silent'/.test(SOURCE), "feeder_silent must no longer be raised as a finding");
  assert.ok(!/^\s*const UNFED_MIN/m.test(SOURCE), "the 40 minute threshold must no longer be declared");
  assert.ok(SOURCE.includes("feeder_silent"), "the comment explaining the retirement should survive");
  assert.ok(
    /finding\(\s*'feeder_down'/.test(SOURCE) && /finding\(\s*'feeder_skipped'/.test(SOURCE) && /finding\(\s*'feeder_never_stamped'/.test(SOURCE),
    "all three feeder findings are raised",
  );
  assert.ok(/rowsOf\('Read Feeder Runs', 'ran_at'\)/.test(SOURCE), "the run log must be read");
  assert.ok(
    /const feederDown = [^;]*feederRanTs/.test(SOURCE) && !/const feederDown = [^;]*lastFedTs/.test(SOURCE),
    "feeder_down must decide on the run stamp, never on max(fed_at) again",
  );
});

const EXPECTED = 9;
assert.equal(checks, EXPECTED, `${checks} checks ran; this file makes exactly ${EXPECTED}`);
console.log(`compose_pulse: ${checks} checks passed`);
