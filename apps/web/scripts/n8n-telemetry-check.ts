/**
 * Proof for the n8n telemetry readers and for the panel over them. No test
 * framework: node:assert and a plain process exit code, the same shape as
 * scripts/presence-check.ts and scripts/control-check.ts. Run from apps/web:
 *
 *   node --experimental-strip-types scripts/n8n-telemetry-check.ts
 *
 * WHY THIS FILE EXISTS
 *
 * The panel it guards replaced an honest placeholder. The placeholder could not
 * lie, because it drew nothing; the replacement can, and the way it would is by
 * putting a DERIVED NUMBER on the screen with nothing under it.
 *
 * The law used to name a projected exhaustion date, because that was the only
 * derived date on the wire. Tee cut the projection on 2026-09-10, and the law
 * was retargeted rather than deleted with it. The burn against the plan cap is
 * still derived: an execution id gap added to a figure a human read off the
 * provider's usage page, against a ceiling nothing in this repository measured
 * (docs/devon/SYS_OPS_n8n-cloud-to-vps-cutover_v2_2026-09-06.md section 2). A
 * bare burn figure is a stronger claim than anything that was measured, exactly
 * as a bare date was.
 *
 * The behaviour half of this file exercises `readCap` refusing that figure. The
 * source half proves no web file can go around it.
 *
 * HOW THE SOURCE GUARD WAS BEATEN, THREE TIMES, AND WHAT IT DOES NOW
 *
 * Cycle one: it visited property access and string element access only, and
 * sixteen lines of DESTRUCTURING obtained every forbidden field while this file
 * printed "21 checks passed" with tsc exiting 0.
 *
 * Cycle two: it was a NAME allowlist over ONE FILE, and four bypasses walked
 * through it with 69 checks, tsc and control-check all green. A helper in a new
 * file, a computed key inside a binding element, an `Object.*` method outside
 * the five allowlisted names, and an escape through no `Object.*` route at all.
 *
 * Cycle three: it was stated by SHAPE and resolved through the checker, and an
 * adversary walked a bare burn figure past it three ways with 61 checks green,
 * because R1 resolves a derived field to the property SYMBOL on a payload type
 * and is blind to a read off a receiver that lost that type. R6 answers that,
 * and the block above `derivedName` says how and what it cost to measure.
 *
 * So the law is stated by SHAPE rather than by name, enforced over EVERY file
 * in the web workspace rather than over one, and resolved through the
 * TypeScript checker rather than by matching identifiers, with one deliberately
 * coarse NAME backstop under it. The six rules and the twenty two bypasses they
 * are proved against are in
 * `the retargeted law catches all four bypasses, thirteen more, and five R6 escapes`.
 * A guard that has never been shown to fire is a guard that has never been
 * shown to fire: each of those twenty two was run against the law with the rule
 * it exercises removed, and each went red.
 */

import assert from "node:assert/strict";
import { dirname, join } from "node:path";
import { readFileSync, readdirSync, statSync } from "node:fs";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import {
  formatDuration,
  isTelemetryPayload,
  orderInstances,
  readAssumptions,
  readCap,
  readInstance,
  readInstanceNotes,
  readProvenance,
  readRate,
  readRowDetail,
  readRowLabel,
  readVariables,
  readWindow,
  statusTone,
  type Rate,
  type TelemetryPayload,
  type Cap,
  type Counts,
  type ExecutionRow,
  type Instance,
  type Window,
} from "../components/control/n8n-telemetry.ts";

let checks = 0;
function check(name: string, run: () => void): void {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

const HERE = dirname(fileURLToPath(import.meta.url));
const WEB_ROOT = join(HERE, "..");
const PANEL = join(HERE, "..", "components", "control", "ExecutionHubPanel.tsx");
const READER = join(HERE, "..", "components", "control", "n8n-telemetry.ts");

function panelSource(): { text: string; file: ts.SourceFile } {
  const text = readFileSync(PANEL, "utf8");
  return {
    text,
    file: ts.createSourceFile(PANEL, text, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TSX),
  };
}

/**
 * The moment every fixture read is taken at, one hour after the newest fixture
 * execution.
 *
 * It is still pinned, and still matters after the projection was cut: the
 * configured cycle reset is compared with it, and the cap block records which
 * clock it was judged against. A test that cannot pin the read is a test whose
 * answer changes with the calendar.
 */
const READ_AT = "2026-09-10T13:00:00Z";

/* ------------------------------------------------------------------ */
/* fixtures                                                            */
/* ------------------------------------------------------------------ */

function capOf(over: Partial<Cap> = {}): Cap {
  return {
    state: "estimated",
    source: "stated_by_configuration",
    cap: 2500,
    resets_at: null,
    orphan_reset: null,
    reset_readable: null,
    reset_in_the_past: null,
    read_at: READ_AT,
    anchor: { id: 6265, spent: 1212, at: "2026-09-06T13:00:00Z", source: "stated_by_configuration" },
    spent_estimate: 1359,
    spent_basis: "anchor_plus_id_delta",
    remaining_estimate: 1141,
    used_fraction: 0.5436,
    counted_from_id: 6412,
    counted_from_moment: "2026-09-10T12:00:00Z",
    reason: null,
    assumptions: [
      "Execution ids on this instance are global and monotonic, so the gap between two ids is the " +
        "number of executions between them, saved or not.",
      "The cap and the anchor spend are stated by configuration, read off the provider's usage page " +
        "by a human.",
    ],
    problems: [],
    note: "stated",
    ...over,
  };
}

function windowOf(over: Partial<Window> = {}): Window {
  return {
    executions_read: 5,
    ids_read: 5,
    rows_without_id: 0,
    rows_without_started_at: 0,
    dated_ids_read: 5,
    newest_id: 6412,
    oldest_id: 6292,
    newest_id_started_at: "2026-09-10T12:00:00Z",
    oldest_id_started_at: "2026-09-09T12:00:00Z",
    newest_started_at: "2026-09-10T12:00:00Z",
    oldest_started_at: "2026-09-09T12:00:00Z",
    span_hours: 24,
    rate_from_id: 6292,
    rate_to_id: 6412,
    rate_from_moment: "2026-09-09T12:00:00Z",
    rate_to_moment: "2026-09-10T12:00:00Z",
    rate_span_hours: 24,
    rate_span_seconds: 86400,
    id_order_matches_time: true,
    id_order_inversions: 0,
    id_order_note: "id order matches startedAt order across the 5 executions carrying both",
    id_order_summary: null,
    ids_in_span: 121,
    not_saved_in_span: 116,
    span_coverage: 0.0413,
    truncated: false,
    ...over,
  };
}

/**
 * A window that satisfies every entry in `GOOD_REQUIRES`: complete, coherent,
 * id consistent and fully saved.
 *
 * `windowOf()` deliberately is NOT one. Its 5 saved rows across a 121 id span are
 * this estate's real shape, because a set of organs stopped saving successful
 * executions on 2026-09-05, and under the new rule that reads NEUTRAL rather than
 * good. That is the intended consequence and
 * `the estate's own measured shape reads neutral rather than good` below asserts
 * it, so nobody later reads the neutral tone as a regression and relaxes the rule
 * to get the green tick back.
 */
function wholeWindow(over: Partial<Window> = {}): Window {
  return windowOf({
    executions_read: 5,
    ids_read: 5,
    dated_ids_read: 5,
    newest_id: 6296,
    oldest_id: 6292,
    ids_in_span: 5,
    not_saved_in_span: 0,
    span_coverage: 1,
    truncated: false,
    id_order_matches_time: true,
    id_order_inversions: 0,
    ...over,
  });
}

const ZERO: Counts = {
  failed: 0,
  succeeded: 0,
  canceled: 0,
  running: 0,
  waiting: 0,
  other: 0,
  status_unreported: 0,
};

function instanceOf(over: Partial<Instance> = {}): Instance {
  return {
    role: "primary",
    state: "ok",
    reason: null,
    configured_host: "a.invalid",
    host: "a.invalid",
    status_code: 200,
    variables: { url: "N8N_API_URL", key: "N8N_API_KEY", cap: "N8N_EXECUTION_CAP" },
    window: windowOf(),
    counts: { ...ZERO, succeeded: 5 },
    status_counts: { success: 5 },
    recent: [],
    rate: { basis: "id_delta", per_day: 120, reason: null, assumptions: [] },
    cap: capOf(),
    read_problems: [],
    ...over,
  };
}

function rowOf(over: Partial<ExecutionRow> = {}): ExecutionRow {
  return {
    id: 6679,
    status: "success",
    workflow_id: "kQ2t",
    workflow_name: null,
    workflow_label: "workflow id kQ2t",
    workflow_label_kind: "id",
    mode: "trigger",
    started_at: "2026-09-10T12:00:00Z",
    stopped_at: "2026-09-10T12:00:03.500Z",
    duration_ms: 3500,
    ...over,
  };
}

/* ------------------------------------------------------------------ */
/* The law: a derived value never travels without its basis            */
/* ------------------------------------------------------------------ */

check("a measured burn returns the figure with every basis line", () => {
  const view = readCap(capOf());
  assert.equal(view.kind, "measured");
  if (view.kind !== "measured") return;
  // The burn is lines[0] and there is no field holding it alone. See the law
  // section below.
  assert.match(view.lines[0], /1359 of 2500 spent/);
  assert.match(view.lines[0], /1141 left/);
  assert.ok(view.lines.length >= 4, "a burn must arrive with the lines that explain it");
  assert.ok(
    view.lines.some((line) => line.includes("stated by configuration")),
    "the ceiling must never be presented as measured",
  );
  assert.ok(
    view.lines.some((line) => line.includes("execution id gap")),
    "the method under the spend is part of the claim",
  );
  assert.ok(
    view.lines.some((line) => line.includes("1212 spent at execution id 6265")),
    "the anchor is part of the claim",
  );
  assert.ok(
    view.lines.some((line) => line.includes("Carried forward to execution id 6412")),
    "the id the gap was carried to is part of the claim",
  );
  assert.ok(
    view.lines.some((line) => line.includes("monotonic")),
    "the id delta assumption is part of the claim",
  );
});

check("a burn whose numbers do not add up is refused, not shown thin", () => {
  const view = readCap(capOf({ remaining_estimate: -900 }));
  assert.equal(view.kind, "unusable");
  if (view.kind !== "unusable") return;
  assert.match(view.sentence, /does not add up/);
});

// F9's class, moved onto the value that survived the cut. Reproduced against a
// reader that presence checked: `spent_estimate` NaN and `used_fraction` as
// prose both drew a bar.
check("a burn field of the wrong type or an impossible value draws nothing", () => {
  const cases: Array<[string, Partial<Cap>]> = [
    ["spend NaN", { spent_estimate: Number.NaN }],
    ["spend as prose", { spent_estimate: "one thousand" as unknown as number }],
    ["spend Infinity", { spent_estimate: Number.POSITIVE_INFINITY }],
    ["spend negative", { spent_estimate: -1 }],
    ["remaining NaN", { remaining_estimate: Number.NaN }],
    ["remaining as prose", { remaining_estimate: "some" as unknown as number }],
  ];
  for (const [label, over] of cases) {
    const view = readCap(capOf(over));
    // `assert.ok` is an assertion function, so the kind is narrowed from here
    // and every surviving kind carries a `sentence`.
    assert.ok(view.kind !== "measured", `a bar survived ${label}`);
    assert.ok(!view.sentence.includes("NaN of"), `${label} rendered NaN as a spend`);
  }
});

check("a fraction the route did not clamp is clamped here, never by the caller", () => {
  const over = readCap(capOf({ used_fraction: 4.2, spent_estimate: 2500, remaining_estimate: 0 }));
  assert.equal(over.kind === "measured" && over.barPercent, 100);
  const under = readCap(capOf({ used_fraction: -3, spent_estimate: 0, remaining_estimate: 2500 }));
  assert.equal(under.kind === "measured" && under.barPercent, 0);
});

check("a spend at or past the cap says the usage page is the truth on it", () => {
  const view = readCap(capOf({ used_fraction: 1, spent_estimate: 2600, remaining_estimate: -100 }));
  assert.equal(view.kind, "measured");
  if (view.kind !== "measured") return;
  assert.equal(view.tone, "bad");
  assert.ok(
    view.lines.some((line) => line.includes("usage page is the truth")),
    "an estimate at the ceiling is still an estimate",
  );
});

check("a spend carried to an id with no clock of its own says so", () => {
  const view = readCap(capOf({ counted_from_moment: null }));
  assert.equal(view.kind, "measured");
  if (view.kind !== "measured") return;
  assert.ok(
    view.lines.some((line) => line.includes("carried no readable startedAt")),
    "a basis id with no moment is stated rather than left blank",
  );
});

check("no cap at all draws no burn and invents no ceiling", () => {
  const view = readCap(null);
  assert.equal(view.kind, "none");
  assert.ok(!JSON.stringify(view).includes("2500"), "no default cap may appear anywhere");
});

/* ------------------------------------------------------------------ */
/* THE PROJECTION IS GONE. Nothing may put it back by accident.        */
/* ------------------------------------------------------------------ */

/**
 * The wall was cut on 2026-09-10. These are the checks that make the cut a
 * property of the code rather than a fact about one afternoon.
 *
 * `exhausts_at` was the only DERIVED date on the wire. Every date that remains
 * is observed from an execution row (`started_at`, `stopped_at`,
 * `newest_id_started_at`) or stated by configuration (`resets_at`, `anchor.at`)
 * or is the moment of the read itself. So the check is not "no dates": it is
 * that no reader on this surface returns a date it computed.
 */
check("no reader exports a projection any more", () => {
  const readerText = readFileSync(READER, "utf8");
  for (const gone of [
    "readProjection",
    "ProjectionView",
    "exhausts_at",
    "exhausts_before_reset",
    "beyond_horizon",
    "days_left",
    "MAX_PROJECTION_DAYS",
  ]) {
    assert.ok(
      !readerText.includes(gone),
      `${gone} is projection scaffolding and the projection was cut`,
    );
  }
});

check("no web file names the cut projection", () => {
  for (const file of webFiles()) {
    const text = readFileSync(file, "utf8");
    for (const gone of ["exhausts_at", "exhausts_before_reset", "days_left"]) {
      assert.ok(
        !text.includes(gone),
        `${file.replace(WEB_ROOT, "")} still names ${gone}, which no payload carries`,
      );
    }
  }
});

/**
 * NF3'S OWN INPUT, THROUGH THE REAL READER.
 *
 * The finding, verbatim: "Projected exhaustion 2027-09-10 21:00:00 UTC, in
 * about 0.38 days, measured against a read at 2026-09-10 13:00:00 UTC" with
 * tone GOOD beside it, a date and a day count 365 days apart on one line. It
 * came from three rows an hour apart stamped a YEAR AHEAD of the read, with an
 * anchor one id behind the newest and 9 of a 2500 cap left, and it walked
 * through the staleness gate because that gate was one sided.
 *
 * This is the cap block the route now produces for exactly that input, fed to
 * the reader the panel actually renders through. There is no wall to be wrong
 * about, and the numbers the wall was derived from are all still here with
 * their basis attached.
 */
const NF3_FUTURE_CAP: Cap = capOf({
  cap: 2500,
  anchor: { id: 6411, spent: 2490, at: null, source: "stated_by_configuration" },
  spent_estimate: 2491,
  remaining_estimate: 9,
  used_fraction: 0.9964,
  counted_from_id: 6412,
  counted_from_moment: "2027-09-10T12:00:00Z",
  read_at: READ_AT,
});

check("NF3's own input reaches the reader with a burn and no wall", () => {
  const view = readCap(NF3_FUTURE_CAP);
  assert.equal(view.kind, "measured");
  if (view.kind !== "measured") return;
  assert.match(view.lines[0], /2491 of 2500 spent/);
  assert.match(view.lines[0], /9 left/);
  assert.equal(view.tone, "warn", "99.6 percent of the cap spent is not a calm figure");
  assert.equal(view.barPercent, 100);
  const rendered = view.lines.join(" | ");
  // The wall, its day count and its comparison sentence are all absent.
  for (const gone of ["2027-09-10 21:00", "2027-09-10T21:00", "0.38", "Projected exhaustion", "days"]) {
    assert.ok(!rendered.includes(gone), `${gone} survived the cut, in: ${rendered}`);
  }
  // The one 2027 date on the block is the OBSERVED start of execution 6412,
  // which is the basis of the spend, not a projection from it.
  assert.ok(
    rendered.includes("Carried forward to execution id 6412"),
    "the id the spend was carried to is named",
  );
  const dates = rendered.match(/\d{4}-\d{2}-\d{2}/g) || [];
  assert.deepEqual(dates, ["2027-09-10"], `only the observed basis date may appear: ${dates}`);
});

/* ------------------------------------------------------------------ */
/* The stated cycle reset, which is configured rather than derived     */
/* ------------------------------------------------------------------ */

check("the reset is exposed on the cap view whether or not a burn was measured", () => {
  const stated = readCap(
    capOf({
      state: "stated",
      spent_estimate: null,
      remaining_estimate: null,
      resets_at: "2026-10-01",
      reset_readable: true,
    }),
  );
  assert.equal(stated.resetsAt, "2026-10-01");
  const measured = readCap(capOf({ resets_at: "2026-10-01", reset_readable: true }));
  assert.equal(measured.resetsAt, "2026-10-01");
  const none = readCap(null);
  assert.equal(none.resetsAt, null);
});

// The guard that would have been lost with the projection. The only statement
// that a configured reset is not a date lived inside the projection's reset
// note, so cutting the wall without this would have printed an unreadable value
// on the panel verbatim as though it were a cycle boundary.
check("a configured reset that is not a date is not drawn at all", () => {
  const view = readCap(
    capOf({
      resets_at: "next tuesday-ish",
      reset_readable: false,
      problems: ["the configured cycle reset 'next tuesday-ish' could not be read as a date"],
    }),
  );
  assert.equal(view.resetsAt, null, "an unreadable reset must not reach the screen");
  const lines = readProvenance(
    payloadOf(),
    instanceOf({ cap: capOf({ resets_at: "next tuesday-ish", reset_readable: false }) }),
  );
  assert.ok(
    lines.some((line) => line.includes("could not be read as a date")),
    "and the reader must say why nothing is drawn",
  );
});

check("a reset already behind the read is reported as behind it", () => {
  const lines = readProvenance(
    payloadOf(),
    instanceOf({ cap: capOf({ resets_at: "2026-09-01", reset_readable: true, reset_in_the_past: true }) }),
  );
  assert.ok(lines.some((line) => line.includes("already behind this read")));
});

// The NF3 class, on the clock that survived the cut. It used to be checked on
// the projection's own `read_at`; the projection is gone and the class is not.
check("a cap block judged against a clock the reader is not shown warns", () => {
  const agreeing = readProvenance(payloadOf(), instanceOf());
  assert.ok(
    agreeing.some((line) => line.includes("the same read moment as this payload")),
    "the agreeing case must be stated rather than silent",
  );
  const skewed = readProvenance(
    payloadOf(),
    instanceOf({ cap: capOf({ read_at: "2026-09-09T13:00:00Z" }) }),
  );
  assert.ok(
    skewed.some((line) => line.startsWith("WARNING") && line.includes("different clocks")),
    "two clocks on one payload is the NF3 class arriving by another door",
  );
});

/* ------------------------------------------------------------------ */
/* The cap is never invented, and never drawn from junk                */
/* ------------------------------------------------------------------ */

check("an instance with no stated cap draws no cap and no bar", () => {
  const view = readCap(capOf({ state: "not_stated", cap: null, anchor: null, spent_estimate: null, remaining_estimate: null, used_fraction: null }));
  assert.equal(view.kind, "none");
  assert.ok(!JSON.stringify(view).includes("2500"), "no default cap may appear anywhere");
});

check("a stated cap with no spend refuses the burn and says why", () => {
  const view = readCap(
    capOf({
      state: "stated",
      spent_estimate: null,
      remaining_estimate: null,
      used_fraction: null,
      reason: "the cap is stated but the spend against it has no source",
    }),
  );
  assert.equal(view.kind, "stated");
  if (view.kind !== "stated") return;
  assert.match(view.sentence, /no source/);
  assert.ok(!("spent" in view), "a stated cap must carry no spend");
  assert.ok(!("cap" in view), "and no ceiling on its own either");
});

check("a cap past four fifths spent turns, and a spent one reads bad", () => {
  const warm = readCap(capOf({ used_fraction: 0.81, spent_estimate: 2025, remaining_estimate: 475 }));
  assert.equal(warm.kind === "measured" && warm.tone, "warn");
  const gone = readCap(capOf({ used_fraction: 1, spent_estimate: 2600, remaining_estimate: -100 }));
  assert.equal(gone.kind === "measured" && gone.tone, "bad");
});

// F9. Reproduced against the previous reader: cap 0 gave "1088 of 0 left" and
// cap -100 gave a 100 percent red bar reading "-110 left".
check("a cap that is not a ceiling draws nothing at all", () => {
  for (const [label, cap] of [
    ["zero", capOf({ cap: 0, spent_estimate: 1412, remaining_estimate: 1088, used_fraction: null })],
    ["negative", capOf({ cap: -100, spent_estimate: 0, remaining_estimate: -110, used_fraction: 1 })],
    ["NaN", capOf({ cap: Number.NaN })],
    ["prose", capOf({ cap: "two thousand five hundred" as unknown as number })],
  ] as [string, Cap][]) {
    const view = readCap(cap);
    assert.equal(view.kind, "unusable", `a ${label} cap was drawn`);
    if (view.kind !== "unusable") return;
    assert.match(view.sentence, /not a ceiling/);
    assert.ok(!view.sentence.includes(" left"), `a ${label} cap must not report a remaining count`);
  }
});

check("an inconsistent anchor is its own view, with no numbers", () => {
  const view = readCap(
    capOf({
      state: "inconsistent",
      spent_estimate: null,
      remaining_estimate: null,
      reason: "the anchor names a different instance",
    }),
  );
  assert.equal(view.kind, "inconsistent");
  if (view.kind !== "inconsistent") return;
  assert.match(view.sentence, /different instance/);
  assert.ok(!("cap" in view), "an inconsistent anchor draws no ceiling either");
});
/* ------------------------------------------------------------------ */
/* An instance that was not reached never reads well                   */
/* ------------------------------------------------------------------ */

check("only a reached instance with saved executions can read good", () => {
  for (const state of [
    "unconfigured",
    "misconfigured",
    "unreachable",
    "refused",
    "malformed",
    "errored",
  ] as const) {
    const verdict = readInstance(instanceOf({ state, window: null, counts: null, cap: null }));
    assert.notEqual(verdict.tone, "good", `${state} must never read as good`);
  }
  const good = readInstance(instanceOf({ window: wholeWindow(), counts: { ...ZERO, succeeded: 5 } }));
  assert.equal(good.tone, "good");
  assert.match(good.sentence, /none of them failed/);
});

// The other half of F4's class, and the half that makes the rule honest rather
// than merely strict: `good` is still REACHABLE, and it is reachable only from a
// window that supports it. A rule that could never grant good would be the same
// defect wearing the other face.
check("the estate's own measured shape reads neutral rather than good", () => {
  const verdict = readInstance(instanceOf());
  assert.equal(verdict.tone, "neutral");
  assert.equal(verdict.label, "SPAN NOT FULLY SAVED");
  assert.ok(!/none of them failed/.test(verdict.sentence));
  assert.match(verdict.sentence, /116 of the 121 ids in this span have no saved row/);
});

check("an instance that answered with nothing saved is neutral, not good", () => {
  // The cutover question is whether the target is carrying the load yet. A
  // green tick over an empty target answers it wrong.
  const verdict = readInstance(
    instanceOf({
      window: windowOf({ executions_read: 0, ids_read: 0, dated_ids_read: 0, not_saved_in_span: null }),
      counts: { ...ZERO },
      reason: "a.invalid answered with no saved executions.",
    }),
  );
  assert.equal(verdict.tone, "neutral");
  assert.equal(verdict.label, "NOTHING SAVED");
});

check("a failure in the window turns the instance", () => {
  const verdict = readInstance(
    instanceOf({ window: wholeWindow(), counts: { ...ZERO, failed: 2, succeeded: 3 } }),
  );
  assert.equal(verdict.tone, "warn");
  assert.match(verdict.sentence, /2 of 5/);
});

// F4. Every one of these rendered tone "good" and the sentence
// "100 saved executions read from h, none of them failed."
check("a degraded read never reads good and never claims nothing failed", () => {
  const cases: Array<[string, Instance, RegExp]> = [
    [
      "every row carried no status",
      instanceOf({ counts: { ...ZERO, status_unreported: 100 }, window: windowOf({ executions_read: 100 }) }),
      /no status at all/,
    ],
    [
      "every row was canceled",
      instanceOf({ counts: { ...ZERO, canceled: 100 }, window: windowOf({ executions_read: 100 }) }),
      /canceled/,
    ],
    [
      "every row carried a status the panel does not bucket",
      instanceOf({ counts: { ...ZERO, other: 100 }, window: windowOf({ executions_read: 100 }) }),
      /does not bucket/,
    ],
    [
      "the window was cut off at the row limit",
      instanceOf({
        counts: { ...ZERO, succeeded: 100 },
        window: windowOf({ executions_read: 100, truncated: true }),
      }),
      /cut off/,
    ],
    [
      "counts were absent altogether",
      instanceOf({ counts: null }),
      /no window or no status counts/,
    ],
    [
      "the window was absent altogether",
      instanceOf({ window: null }),
      /no window or no status counts/,
    ],
  ];
  for (const [label, instance, expected] of cases) {
    const verdict = readInstance(instance);
    assert.notEqual(verdict.tone, "good", `"${label}" read as good`);
    assert.ok(
      !/none of them failed/.test(verdict.sentence),
      `"${label}" claimed none of them failed: ${verdict.sentence}`,
    );
    assert.match(verdict.sentence, expected, `"${label}" did not say why`);
  }
});

check("in flight executions are never claimed as passes", () => {
  const verdict = readInstance(
    instanceOf({ window: wholeWindow(), counts: { ...ZERO, succeeded: 3, running: 2 } }),
  );
  // Neutral rather than good: a run that has not finished has not passed, and the
  // version of this scoped the sentence while leaving the tone green, which reads
  // as a settled window when it is not one.
  assert.equal(verdict.tone, "neutral");
  assert.notEqual(verdict.tone, "bad");
  assert.match(verdict.sentence, /had not finished/);
  assert.ok(!/none of them failed/.test(verdict.sentence));
});

/* ------------------------------------------------------------------ */
/* F1: the window a reader sees is never wider than its arithmetic     */
/* ------------------------------------------------------------------ */

check("rows carrying no usable id are named, not silently absorbed", () => {
  // One row whose id did not parse used to widen the rate's denominator
  // without touching its numerator: a measured 120 a day became 4.
  const view = readWindow(
    windowOf({ executions_read: 3, ids_read: 2, rows_without_id: 1, dated_ids_read: 2 }),
  );
  assert.ok(
    view.caveats.some((line) => line.includes("1 of the 3") && line.includes("no usable id")),
    `the divergence must be rendered, got: ${JSON.stringify(view.caveats)}`,
  );
  assert.ok(view.caveats.some((line) => line.includes("take no part in the rate")));
});

check("a clean complete window carries no caveats", () => {
  const view = readWindow(windowOf({ not_saved_in_span: 0 }));
  assert.deepEqual(view.caveats, []);
  assert.match(view.headline, /ids 6292 to 6412/);
});

check("a window whose ids contradict its clock says so, exactly once", () => {
  // The full 40 word note used to render three times per instance: under the
  // window, as the rate's refusal reason, and again in the panel level findings
  // block. Six copies on a two instance panel, diluting the one block an operator
  // scans first. It is now rendered by readInstanceNotes, once.
  const win = windowOf({
    id_order_matches_time: false,
    id_order_inversions: 1,
    id_order_note: "1 execution(s) carry a smaller id than one that started earlier",
    id_order_summary: "id order and startedAt order disagree over the window read",
    ids_in_span: null,
    not_saved_in_span: null,
  });
  const notes = readInstanceNotes(
    instanceOf({
      window: win,
      rate: {
        basis: "unavailable",
        per_day: null,
        reason: "id order and startedAt order disagree over the window read",
        assumptions: [],
      },
    }),
  );
  const carrying = notes.filter((line) => line.includes("smaller id"));
  assert.equal(carrying.length, 1, `the note must appear once, got ${carrying.length}: ${JSON.stringify(notes)}`);
  // And readWindow itself no longer repeats it.
  assert.ok(!readWindow(win).caveats.some((line) => line.includes("smaller id")));
});

check("no window at all renders no figures and says so", () => {
  const view = readWindow(null);
  assert.deepEqual(view.caveats, []);
  assert.match(view.headline, /No window was read/);
});

/* ------------------------------------------------------------------ */
/* small readers                                                       */
/* ------------------------------------------------------------------ */

check("durations format and a missing one says so", () => {
  assert.equal(formatDuration(null), "no duration");
  assert.equal(formatDuration(-1), "no duration");
  assert.equal(formatDuration(450), "450ms");
  assert.equal(formatDuration(3500), "3.5s");
  assert.equal(formatDuration(125_000), "2m 5s");
});

check("status tones never call an unknown status good", () => {
  assert.equal(statusTone("success"), "good");
  assert.equal(statusTone("error"), "bad");
  assert.equal(statusTone("crashed"), "bad");
  assert.equal(statusTone(null), "neutral");
  // MEASURED value set: canceled, crashed, error, new, running, success,
  // unknown, waiting. "unknown" is the instance saying it does not know.
  assert.equal(statusTone("unknown"), "neutral");
  assert.equal(statusTone("something-new"), "neutral");
});

// The shape correction of 2026-09-10: workflowData.name does not exist in the
// response, so the label falls back to the id and says which it is rather than
// leaving a blank where a name was promised.
check("a row with no workflow name shows the id and says it is an id", () => {
  const asId = readRowLabel(rowOf());
  assert.equal(asId.label, "workflow id kQ2t");
  assert.equal(asId.isName, false);
  assert.match(asId.suffix, /not a name/);
  assert.ok(asId.label.trim().length > 0, "a reader must never be shown a blank");

  const named = readRowLabel(rowOf({ workflow_name: "Driver Poll", workflow_label: "Driver Poll", workflow_label_kind: "name" }));
  assert.equal(named.label, "Driver Poll");
  assert.equal(named.isName, true);
  assert.equal(named.suffix, "");

  const nothing = readRowLabel(
    rowOf({ workflow_id: null, workflow_name: null, workflow_label: "no workflow identified", workflow_label_kind: "unidentified" }),
  );
  assert.ok(nothing.label.trim().length > 0);
  assert.equal(nothing.isName, false);
});

check("instances hold their order between refreshes", () => {
  const ordered = orderInstances([
    instanceOf({ role: "secondary" }),
    instanceOf({ role: "primary" }),
  ]);
  assert.deepEqual(ordered.map((i) => i.role), ["primary", "secondary"]);
});

check("a payload of the wrong shape is refused rather than read", () => {
  assert.equal(isTelemetryPayload(null), false);
  assert.equal(isTelemetryPayload({ instances: [] }), false);
  assert.equal(isTelemetryPayload({ instances: [], read_at: "x", findings: [] }), true);
});

/* ================================================================== */
/* THE LAW, RETARGETED. Its subject was the only derived DATE, and that */
/* date was cut. There is still a derived NUMBER, so the law now reads  */
/* "no derived value reaches the screen without its basis" and it       */
/* covers the burn.                                                     */
/* ================================================================== */

/**
 * WHY THE MECHANISM CHANGED AS WELL AS THE SUBJECT.
 *
 * The previous version was enforced over `panelSource()` alone, with a name
 * allowlist for the fields and a five entry allowlist of `Object.*` method
 * names for whole object escapes. FOUR bypasses shipped a bare wall past it
 * with 69 checks, tsc and control-check all green:
 *
 *   (i)   put the read in a NEW FILE and re-export the helper into the panel.
 *         The law read one file, so a second one was invisible to it.
 *   (ii)  a COMPUTED KEY IN A BINDING ELEMENT, `const { [k]: wall } = cap`.
 *         `forbiddenReads` only looked at a binding element's propertyName when
 *         it was an identifier or a string literal, and `dynamicPayloadReads`
 *         only visited ElementAccessExpression, so a computed key inside a
 *         destructuring pattern was seen by neither.
 *   (iii) a whole object escape through an `Object.*` method that was not one
 *         of the five allowlisted names, `Object.getOwnPropertyNames`.
 *   (iv)  a whole object escape through no `Object.*` route at all,
 *         `structuredClone`, `Reflect.ownKeys`, a template interpolation, or
 *         any external function handed the object whole.
 *
 * All four are the same mistake in three places: a rule stated as a list of
 * NAMES, over a list of ONE FILE. So this version is stated by SHAPE, over
 * EVERY file in the web workspace, and it is TYPE AWARE rather than textual:
 *
 *   R1 no file may read a DERIVED field off a payload type. Which fields are
 *      derived is resolved through the TypeScript checker to the property
 *      symbol declared on the payload type, so `per_day` on `Rate` and a
 *      `per_day` on anything else are different things here.
 *   R2 no file may reach into a payload object with a COMPUTED key, whatever
 *      the key is. The key is exactly what a name allowlist cannot see.
 *   R3 the same rule inside a destructuring pattern, which is bypass (ii).
 *   R4 no rest binding over a payload object and no spread of one. Neither
 *      names a field.
 *   R5 a payload object may only be handed to code THIS LAW ALSO READS. That
 *      is the shape rule that replaces the five method names: `Object.keys`,
 *      `Object.getOwnPropertyNames`, `Reflect.ownKeys`, `structuredClone`,
 *      `JSON.stringify`, `String`, `console.log` and any other function
 *      declared outside the scanned set are all one case, and so is a
 *      template interpolation and a `+` with a payload operand.
 *
 *   R6 THE NAME BACKSTOP, added 2026-09-10 after an adversary beat R1 through
 *      R5 three separate ways with 61 checks green. R1 resolves a derived field
 *      through the checker to the property SYMBOL declared on a payload type,
 *      which is precise and gives a good message, and is blind to any read off a
 *      receiver that no longer carries that symbol. All three bypasses were
 *      ordinary TypeScript, not obfuscation:
 *
 *        (A) an inline structural parameter type, which is how anyone would
 *            write a presentational component:
 *              function BurnBar({ data }: { data: { used_fraction: number|null } })
 *              ... <div>{data.used_fraction}</div>, with <BurnBar data={cap} />
 *        (B) an annotated assignment to a looser type:
 *              const loose: Loose = cap; <span>{loose.spent_estimate}</span>
 *        (D) `as any`:
 *              const loose = cap as any; <div>{loose.used_fraction}</div>
 *
 *      Probe A is the one that matters: it is idiomatic React and the panel
 *      holds `const cap: Cap | null = instance.cap` in scope throughout, so it
 *      was one ordinary refactor away rather than an attack.
 *
 *      (A2) and (A3) in the probe list are the same escape reached through the
 *      other two read sites, destructuring and a string key, because a rule
 *      added at one site and not the others is how cycle one happened. With R6
 *      removed the law misses exactly those five probes and no others, measured
 *      2026-09-10 rather than reasoned.
 *
 *      R6 therefore ignores the receiver entirely and refuses the NAME, at all
 *      three read sites, anywhere in the scanned set. It is deliberately coarser
 *      than R1: it cannot tell a payload's `per_day` from anybody else's. That
 *      is affordable here and was MEASURED before it was chosen, not assumed:
 *      across app, components and lib, the four derived names occur outside the
 *      reader exactly once, in a comment in the panel, so R6 has nothing to
 *      false positive on. If a future unrelated type needs one of these names,
 *      R6 will say so loudly and the answer is to rename that field or narrow
 *      this rule deliberately, not to widen the exemption quietly.
 *
 * WHAT R5 DOES NOT CATCH, stated rather than left to be discovered: a closure
 * that captures a payload object and is handed to external code,
 * `external(() => cap)`. `containsPayloadTyped` deliberately does not descend
 * into function bodies, because `payload.instances.map((instance) => ...)` is
 * how the panel is written and every such body is walked by the scan in its own
 * right. So a closure that READS a derived field is caught by R1 wherever it
 * is written, and a closure that DUMPS one is caught by R5 at the dump. A
 * closure that only returns the object to a foreign renderer is not caught
 * here.
 */

/**
 * The fields that are DERIVED, and WHERE THE LINE IS, because the line is a
 * judgement and it is the kind of judgement that gets quietly widened later.
 *
 * A field is derived here when it is an ESTIMATE of a quantity nothing in this
 * repository observed:
 *
 *   `spent_estimate`   an id gap added to a figure a human read off the
 *                      provider's usage page.
 *   `remaining_estimate`, `used_fraction`   the same estimate against a ceiling
 *                      nothing here measured.
 *   `per_day`          a short window extrapolated to a day.
 *
 * DELIBERATELY NOT IN THE SET, and this was measured before it was decided:
 * `ids_in_span`, `not_saved_in_span`, `span_coverage` and `executions_in_span`
 * are exact arithmetic over ids that were actually read, `newest - oldest + 1`
 * and differences from it. They estimate nothing. What the monotonic id
 * assumption buys is their INTERPRETATION, that an id with no row is an
 * execution that ran, and `readWindow` states that interpretation together with
 * the four causes an executions read cannot tell apart, every time it reports
 * one. Widening this set to cover them would be widening a rule on speculation
 * about intent, and the panel renders `not_saved_in_span` as a plain count in a
 * figure tile with that caveat on the same card.
 *
 * The names carry the line: `_estimate` and `per_day` are estimates, the rest
 * are counts.
 */
const DERIVED_FIELDS = new Set([
  "spent_estimate",
  "remaining_estimate",
  "used_fraction",
  "per_day",
]);

const PAYLOAD_TYPE_NAMES = [
  "ExecutionRow",
  "Window",
  "Counts",
  "Rate",
  "Cap",
  "Instance",
  "TelemetryPayload",
] as const;

/**
 * Every TypeScript file in the web workspace that could reach a payload object.
 *
 * `scripts/` is excluded because nothing there renders, and this file itself
 * builds payload fixtures by hand. The reader is IN the set for R5's purposes,
 * because handing a payload object to a reader is the sanctioned move, and OUT
 * of the set for R1 to R4, because the reader is where a derived field is
 * legitimately read and given its basis.
 */
function webFiles(): string[] {
  const out: string[] = [];
  const walk = (dir: string): void => {
    for (const entry of readdirSync(dir)) {
      const full = join(dir, entry);
      if (statSync(full).isDirectory()) {
        walk(full);
      } else if (/\.tsx?$/.test(entry) && !/\.d\.ts$/.test(entry)) {
        out.push(full);
      }
    }
  };
  for (const root of ["app", "components", "lib"]) walk(join(WEB_ROOT, root));
  return out.sort();
}

type Law = {
  program: ts.Program;
  checker: ts.TypeChecker;
  scanned: Set<string>;
  files: ts.SourceFile[];
};

function compilerOptions(): ts.CompilerOptions {
  const config = ts.readConfigFile(join(WEB_ROOT, "tsconfig.json"), ts.sys.readFile);
  const parsed = ts.parseJsonConfigFileContent(config.config, ts.sys, WEB_ROOT);
  return { ...parsed.options, noEmit: true };
}

/**
 * The program the law runs over. `overlay` adds in memory files, which is how
 * the negative controls below feed the law a bypass without writing anything to
 * disk: a probe is a real file in a real program with real types, and the law
 * sees it exactly as it would see a file somebody committed.
 */
function buildLaw(overlay: Map<string, string> = new Map()): Law {
  const roots = [...webFiles(), ...overlay.keys()];
  const options = compilerOptions();
  const base = ts.createCompilerHost(options, true);
  const host: ts.CompilerHost = {
    ...base,
    fileExists: (name) => overlay.has(name) || base.fileExists(name),
    readFile: (name) => (overlay.has(name) ? overlay.get(name) : base.readFile(name)),
    getSourceFile: (name, languageVersion, onError, shouldCreate) => {
      const text = overlay.get(name);
      if (text !== undefined) {
        return ts.createSourceFile(name, text, languageVersion, true, ts.ScriptKind.TSX);
      }
      return base.getSourceFile(name, languageVersion, onError, shouldCreate);
    },
  };
  const program = ts.createProgram(roots, options, host);
  const scanned = new Set(roots);
  const files = roots
    .map((name) => program.getSourceFile(name))
    .filter((file): file is ts.SourceFile => file !== undefined);
  return { program, checker: program.getTypeChecker(), scanned, files };
}

let SHIPPED: Law | null = null;
function shippedLaw(): Law {
  if (SHIPPED === null) SHIPPED = buildLaw();
  return SHIPPED;
}

/**
 * The payload type SYMBOLS, resolved from the reader's own declarations.
 *
 * By SYMBOL rather than by name, and this is not fussiness: the DOM declares an
 * interface called `Window` and the payload declares a type called `Window`, so
 * a name match flagged `typeof window !== "undefined"` in an unrelated chat
 * component as a reach into a payload object. Matching the symbol the reader
 * declared cannot collide with anything the platform declares.
 */
function payloadSymbols(law: Law): Set<ts.Symbol> {
  const found = new Set<ts.Symbol>();
  const reader = law.program.getSourceFile(READER);
  if (!reader) return found;
  ts.forEachChild(reader, (node) => {
    if (!ts.isTypeAliasDeclaration(node)) return;
    if (!(PAYLOAD_TYPE_NAMES as readonly string[]).includes(node.name.text)) return;
    const symbol = law.checker.getSymbolAtLocation(node.name);
    if (symbol) found.add(symbol);
  });
  return found;
}

const PAYLOAD_SYMBOLS = new WeakMap<ts.Program, Set<ts.Symbol>>();
function payloadSymbolsFor(law: Law): Set<ts.Symbol> {
  let found = PAYLOAD_SYMBOLS.get(law.program);
  if (!found) {
    found = payloadSymbols(law);
    PAYLOAD_SYMBOLS.set(law.program, found);
  }
  return found;
}

/** The payload type this expression's type is, or null. Unions and arrays too. */
function payloadTypeName(law: Law, type: ts.Type, depth = 0): string | null {
  if (depth > 3) return null;
  const symbols = payloadSymbolsFor(law);
  const parts = type.isUnion() ? type.types : [type];
  for (const part of parts) {
    if (part.flags & (ts.TypeFlags.Null | ts.TypeFlags.Undefined)) continue;
    for (const candidate of [part.aliasSymbol, part.getSymbol()]) {
      if (candidate && symbols.has(candidate)) return candidate.getName();
    }
    const element = law.checker.getIndexTypeOfType(part, ts.IndexKind.Number);
    if (element) {
      const inner = payloadTypeName(law, element, depth + 1);
      if (inner) return inner;
    }
  }
  return null;
}

function isPayloadExpression(law: Law, node: ts.Node): string | null {
  try {
    return payloadTypeName(law, law.checker.getTypeAtLocation(node));
  } catch {
    return null;
  }
}

/**
 * Does this expression carry a payload object into whatever consumes it?
 *
 * Two deliberate stopping rules, and both of them are what keeps this a rule
 * about ESCAPES rather than a rule about mentioning a payload anywhere:
 *
 * 1. Function bodies are not descended into. See the note on R5.
 * 2. A property access, an element access or a call whose OWN type is not a
 *    payload type stops the descent, because its value is not the payload
 *    object. `rendered.length` yields a number and `formatMoment(win.oldest)`
 *    yields a string; neither hands anything over. `JSON.stringify({ p: cap })`
 *    still descends, because an object literal is not a projection of the
 *    payload, it is a wrapper around it.
 */
function containsPayloadTyped(law: Law, node: ts.Node): boolean {
  let found = false;
  const visit = (n: ts.Node): void => {
    if (found) return;
    if (
      ts.isFunctionExpression(n) ||
      ts.isArrowFunction(n) ||
      ts.isFunctionDeclaration(n) ||
      ts.isClassDeclaration(n)
    ) {
      return;
    }
    if (isPayloadExpression(law, n) !== null) {
      found = true;
      return;
    }
    if (
      ts.isPropertyAccessExpression(n) ||
      ts.isElementAccessExpression(n) ||
      ts.isCallExpression(n)
    ) {
      return;
    }
    ts.forEachChild(n, visit);
  };
  visit(node);
  return found;
}

/** The property symbols of every DERIVED field declared on a payload type. */
function derivedPropertySymbols(law: Law): Map<ts.Symbol, string> {
  const declared = new Map<ts.Symbol, string>();
  const reader = law.program.getSourceFile(READER);
  assert.ok(reader, "the reader must be in the law's program");
  if (!reader) return declared;
  ts.forEachChild(reader, (node) => {
    if (!ts.isTypeAliasDeclaration(node)) return;
    const owner = node.name.text;
    if (!(PAYLOAD_TYPE_NAMES as readonly string[]).includes(owner)) return;
    const walk = (n: ts.Node): void => {
      if (ts.isPropertySignature(n) && n.name && ts.isIdentifier(n.name)) {
        if (DERIVED_FIELDS.has(n.name.text)) {
          const symbol = law.checker.getSymbolAtLocation(n.name);
          if (symbol) declared.set(symbol, `${owner}.${n.name.text}`);
        }
      }
      ts.forEachChild(n, walk);
    };
    walk(node.type);
  });
  return declared;
}

/** Is the thing this call reaches declared inside the set the law reads? */
function calleeIsScanned(law: Law, callee: ts.Node): boolean {
  let symbol = law.checker.getSymbolAtLocation(callee);
  if (symbol && symbol.flags & ts.SymbolFlags.Alias) {
    try {
      symbol = law.checker.getAliasedSymbol(symbol);
    } catch {
      /* an unresolvable alias is treated as external, which is the safe way */
    }
  }
  const declarations = symbol?.getDeclarations() || [];
  if (declarations.length === 0) return false;
  return declarations.every((declaration) =>
    law.scanned.has(declaration.getSourceFile().fileName),
  );
}

/** Every offence against the law in one file. */
function lawOffences(law: Law, file: ts.SourceFile): string[] {
  const offences: string[] = [];
  const derived = derivedPropertySymbols(law);
  const at = (node: ts.Node) => file.getLineAndCharacterOfPosition(node.pos).line + 1;
  const note = (rule: string, what: string, node: ts.Node) => {
    offences.push(`${rule}: ${what} at ${file.fileName.replace(WEB_ROOT, "")}:${at(node)}`);
  };
  const derivedName = (symbol: ts.Symbol | undefined): string | null => {
    if (!symbol) return null;
    const direct = derived.get(symbol);
    if (direct) return direct;
    for (const declaration of symbol.declarations || []) {
      if (
        ts.isPropertySignature(declaration) &&
        declaration.name &&
        ts.isIdentifier(declaration.name)
      ) {
        const original = law.checker.getSymbolAtLocation(declaration.name);
        const found = original ? derived.get(original) : undefined;
        if (found) return found;
      }
    }
    return null;
  };
  const escape = (node: ts.Node, why: string) => {
    if (containsPayloadTyped(law, node)) note("R5", `a payload object ${why}`, node);
  };

  const visit = (node: ts.Node): void => {
    // R1: a derived field read off a payload type, by any of the three forms
    // that reach a property.
    if (ts.isPropertyAccessExpression(node)) {
      const name = derivedName(law.checker.getSymbolAtLocation(node.name));
      if (name) note("R1", `${name} read directly`, node);
      else if (DERIVED_FIELDS.has(node.name.text)) {
        note("R6", `${node.name.text} read off a receiver that is not a payload type`, node);
      }
    }
    if (ts.isElementAccessExpression(node)) {
      const key = node.argumentExpression;
      if (ts.isStringLiteralLike(key)) {
        const objectType = law.checker.getTypeAtLocation(node.expression);
        const name = derivedName(objectType.getProperty(key.text));
        if (name) note("R1", `${name} read through a string key`, node);
        else if (DERIVED_FIELDS.has(key.text)) {
          note("R6", `${key.text} read through a string key off a non payload receiver`, node);
        }
      } else if (isPayloadExpression(law, node.expression) !== null) {
        // R2: a computed key into a payload object, whatever the key is.
        note("R2", "a computed reach into a payload object", node);
      }
    }
    if (ts.isBindingElement(node)) {
      const patternType = law.checker.getTypeAtLocation(node.parent);
      const overPayload = payloadTypeName(law, patternType) !== null;
      if (node.dotDotDotToken) {
        // R4: a rest element takes every property and names none.
        if (overPayload) note("R4", "a rest binding over a payload object", node);
      } else {
        const source = node.propertyName ?? node.name;
        if (ts.isComputedPropertyName(source)) {
          // R3, and this is bypass (ii). A computed key in a destructuring
          // pattern was seen by neither of the two previous detectors.
          if (overPayload) {
            note("R3", "a computed key in a destructuring pattern over a payload object", node);
          }
        } else if (ts.isIdentifier(source) || ts.isStringLiteralLike(source)) {
          const name = derivedName(patternType.getProperty(source.text));
          if (name) note("R1", `${name} read by destructuring`, node);
          else if (DERIVED_FIELDS.has(source.text)) {
            note("R6", `${source.text} destructured off a non payload receiver`, node);
          }
        }
      }
    }
    // R4: a spread of a payload object, in an object literal or an argument list.
    if (ts.isSpreadAssignment(node) && isPayloadExpression(law, node.expression) !== null) {
      note("R4", "a spread of a payload object", node);
    }
    if (ts.isSpreadElement(node) && isPayloadExpression(law, node.expression) !== null) {
      note("R4", "a spread of a payload object", node);
    }
    // R5: the object handed to code this law does not read.
    if (ts.isCallExpression(node) || ts.isNewExpression(node)) {
      if (!calleeIsScanned(law, node.expression)) {
        for (const argument of node.arguments || []) {
          escape(argument, `handed to ${node.expression.getText().slice(0, 40)}`);
        }
      }
    }
    if (ts.isTemplateSpan(node)) {
      escape(node.expression, "interpolated into a string");
    }
    if (ts.isBinaryExpression(node) && node.operatorToken.kind === ts.SyntaxKind.PlusToken) {
      escape(node.left, "concatenated into a string");
      escape(node.right, "concatenated into a string");
    }
    if (ts.isJsxExpression(node) && node.expression) {
      const parent = node.parent;
      if (ts.isJsxAttribute(parent)) {
        const tag = ts.isJsxOpeningElement(parent.parent.parent) || ts.isJsxSelfClosingElement(parent.parent.parent)
          ? parent.parent.parent.tagName
          : null;
        if (tag !== null && !calleeIsScanned(law, tag)) {
          escape(node.expression, `passed to <${tag.getText()}>`);
        }
      } else if (isPayloadExpression(law, node.expression) !== null) {
        note("R5", "a payload object rendered as a JSX child", node);
      }
    }
    ts.forEachChild(node, visit);
  };
  ts.forEachChild(file, visit);
  return offences;
}

/** Every offence across every scanned file except the reader itself. */
function shippedOffences(): string[] {
  const law = shippedLaw();
  const out: string[] = [];
  for (const file of law.files) {
    if (file.fileName === READER) continue;
    out.push(...lawOffences(law, file));
  }
  return out;
}

check("the law is enforced over every web file, not over one", () => {
  const law = shippedLaw();
  const names = law.files.map((f) => f.fileName);
  assert.ok(
    names.length >= 20,
    `the law must read the whole web workspace, it read ${names.length} files`,
  );
  assert.ok(names.includes(PANEL), "the panel must be in the scanned set");
  assert.ok(names.includes(READER), "the reader must be in the scanned set");
  const derived = derivedPropertySymbols(law);
  assert.equal(
    derived.size,
    DERIVED_FIELDS.size,
    "every derived field name must resolve to a real property symbol on a payload type, or the " +
      `rule is guarding a field that no longer exists: resolved ${[...derived.values()].join(", ")}`,
  );
});

check("no web file reaches a derived value without going through a reader", () => {
  const offences = shippedOffences();
  assert.deepEqual(
    offences,
    [],
    "a derived value must be obtained through readCap, readRate or readWindow, which return it " +
      `only with the basis beside it: ${offences.join(", ")}`,
  );
});

/**
 * THE NEGATIVE CONTROL. Every one of the four bypasses that shipped a bare wall,
 * plus every variant of them the adversary did not use, fed to the law as a real
 * file in a real program.
 *
 * The probes are in memory rather than on disk, so a failing run leaves nothing
 * behind, and they import the real reader so their types are the real types.
 */
const PROBE_DIR = join(WEB_ROOT, "components", "control");

const BYPASSES: Array<[string, string]> = [
  // The three that beat R1 through R5 on 2026-09-10 with 61 checks green. All
  // three are ordinary TypeScript and (A) is idiomatic React, not obfuscation.
  // R6 is what catches them: it refuses the NAME and ignores the receiver.
  [
    "(A) an inline structural parameter type, the shape any presentational component takes",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function BurnBar({ data }: { data: { used_fraction: number | null } }) {\n" +
      "  return <div>{data.used_fraction}</div>;\n" +
      "}\n" +
      "export function Host({ cap }: { cap: Cap }) { return <BurnBar data={cap} />; }\n",
  ],
  [
    "(B) an annotated assignment to a looser type",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "type Loose = { spent_estimate: number | null; used_fraction: number | null };\n" +
      "export function Burn({ cap }: { cap: Cap }) {\n" +
      "  const loose: Loose = cap;\n" +
      "  return <span>{loose.spent_estimate} spent, {loose.used_fraction} of cap</span>;\n" +
      "}\n",
  ],
  [
    "(D) as any",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function Burn({ cap }: { cap: Cap }) {\n" +
      "  const loose = cap as any;\n" +
      "  return <div>{loose.used_fraction}</div>;\n" +
      "}\n",
  ],
  [
    "(A2) the same escape reached by destructuring rather than a property read",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function Burn({ cap }: { cap: Cap }) {\n" +
      "  const loose = cap as { per_day: number | null };\n" +
      "  const { per_day } = loose;\n" +
      "  return <div>{per_day}</div>;\n" +
      "}\n",
  ],
  [
    "(A3) the same escape reached by a string key rather than a property read",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function Burn({ cap }: { cap: Cap }) {\n" +
      '  const loose = cap as Record<string, unknown>;\n' +
      '  return <div>{String(loose["remaining_estimate"])}</div>;\n' +
      "}\n",
  ],
  [
    "(i) the read moved into a NEW FILE and re-exported into the panel",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function Burn({ cap }: { cap: Cap }) { return cap.spent_estimate; }\n",
  ],
  [
    "(ii) a computed key in a BindingElement",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "declare const k: string;\n" +
      "export function Burn(cap: Cap) { const { [k]: value } = cap; return value; }\n",
  ],
  [
    "(iii) an Object.* route outside the five allowlisted names",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function Burn(cap: Cap) { return Object.getOwnPropertyNames(cap); }\n",
  ],
  [
    "(iv) an escape by no Object.* route at all",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function Burn(cap: Cap) { return structuredClone(cap); }\n",
  ],
  [
    "Reflect.ownKeys over a payload object",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function Burn(cap: Cap) { return Reflect.ownKeys(cap); }\n",
  ],
  [
    "the burn interpolated into a template",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function Burn(cap: Cap) { return `${cap}`; }\n",
  ],
  [
    "the burn concatenated into a string",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      'export function Burn(cap: Cap) { return "burn " + cap; }\n',
  ],
  [
    "an object rest then a raw dump, which is bypass (b) from cycle two",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function Burn(cap: Cap | null) { const { ...raw } = cap ?? ({} as Cap); return JSON.stringify(raw); }\n",
  ],
  [
    "a spread of a payload object into a new object",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function Burn(cap: Cap) { return { ...cap }; }\n",
  ],
  [
    "a key built by concatenation, which is bypass (a) from cycle two",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      'export function Burn(cap: Cap) { const k = "spent" + "_estimate"; return (cap as Cap)[k as keyof Cap]; }\n',
  ],
  [
    "a plain property read of the spend",
    'import type { Instance } from "./n8n-telemetry.ts";\n' +
      "export function Burn(instance: Instance) { return instance.cap?.remaining_estimate; }\n",
  ],
  [
    "a string element access of the fraction",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      'export function Burn(cap: Cap) { return cap["used_fraction"]; }\n',
  ],
  [
    "a renamed destructuring of the rate",
    'import type { Rate } from "./n8n-telemetry.ts";\n' +
      "export function Burn(rate: Rate) { const { per_day: n } = rate; return n; }\n",
  ],
  [
    "the whole window object handed to an external serialiser",
    'import type { Window } from "./n8n-telemetry.ts";\n' +
      "export function Burn(win: Window) { return JSON.stringify(win); }\n",
  ],
  [
    "the rate read off an instance rather than through readRate",
    'import type { Instance } from "./n8n-telemetry.ts";\n' +
      "export function Burn(instance: Instance) { return instance.rate?.per_day; }\n",
  ],
  [
    "the payload object logged out of the panel",
    'import type { TelemetryPayload } from "./n8n-telemetry.ts";\n' +
      "export function Burn(payload: TelemetryPayload) { console.log(payload); }\n",
  ],
  [
    "the cap object rendered as a JSX child",
    'import type { Cap } from "./n8n-telemetry.ts";\n' +
      "export function Burn({ cap }: { cap: Cap }) { return <div>{cap}</div>; }\n",
  ],
];

const CLEAN_PROBE =
  'import { readCap, readRate, type Cap, type Rate, type Tone, type Window } from "./n8n-telemetry.ts";\n' +
  "const DOT: Record<string, string> = { good: 'a', neutral: 'b' };\n" +
  "export function Fine({ cap, rate, win, tone }: { cap: Cap | null; rate: Rate | null; win: Window | null; tone: Tone }) {\n" +
  "  const view = readCap(cap);\n" +
  "  const rateView = readRate(rate, win);\n" +
  "  const dot = DOT[tone];\n" +
  "  const lines = view.kind === 'measured' ? view.lines : [view.sentence];\n" +
  "  return <ul className={dot}>{lines.map((line) => <li key={line}>{line}{rateView.sentence}</li>)}</ul>;\n" +
  "}\n";

check("the retargeted law catches all four bypasses, thirteen more, and five R6 escapes", () => {
  // The number in the name is asserted rather than remembered: a probe added
  // without renaming the check would otherwise leave the name quietly wrong,
  // which is a small version of the failure this whole file guards.
  assert.equal(BYPASSES.length, 22, "four named bypasses, thirteen more, and the five R6 escapes");
  const overlay = new Map<string, string>();
  BYPASSES.forEach(([, source], index) => {
    overlay.set(join(PROBE_DIR, `__probe-${index}.tsx`), source);
  });
  overlay.set(join(PROBE_DIR, "__probe-clean.tsx"), CLEAN_PROBE);
  const law = buildLaw(overlay);
  BYPASSES.forEach(([label], index) => {
    const name = join(PROBE_DIR, `__probe-${index}.tsx`);
    const file = law.program.getSourceFile(name);
    assert.ok(file, `the probe for ${label} must be in the program`);
    if (!file) return;
    const offences = lawOffences(law, file);
    assert.ok(
      offences.length > 0,
      `the law did not see ${label}, which is how a bare figure reaches the screen`,
    );
  });
  // And it must not fire on the shape the panel is actually written in: a
  // module level lookup table keyed by a tone, a reader called with a payload
  // object, and a view's own lines mapped into JSX.
  const clean = law.program.getSourceFile(join(PROBE_DIR, "__probe-clean.tsx"));
  assert.ok(clean, "the clean probe must be in the program");
  if (!clean) return;
  assert.deepEqual(
    lawOffences(law, clean),
    [],
    "the law must not fire on a reader call, a tone lookup table or a view's own lines",
  );
});

/**
 * The third layer, and the one that makes the other two belt rather than
 * braces: THERE IS NO BARE DERIVED NUMBER TO RENDER.
 *
 * `readCap`'s measured view carries `lines`, whose first entry states the burn
 * and whose remaining entries are the basis and the assumptions. It has no field
 * holding the spend, the remaining count, the ceiling or the fraction on its
 * own, so even a caller that got past all five rules has nothing to render
 * alone. This is the same shape the date view carried, moved onto the value
 * that survived the cut.
 */
check("no field on the burn view holds a derived number on its own", () => {
  const view = readCap(capOf());
  assert.equal(view.kind, "measured");
  if (view.kind !== "measured") return;
  const keys = Object.keys(view).sort();
  assert.deepEqual(keys, ["barPercent", "kind", "lines", "resetsAt", "tone"]);
  // The three accounting numbers appear in exactly one place on this view,
  // inside `lines`.
  const serialised = JSON.stringify({ ...view, lines: [] });
  for (const number of ["1359", "1141", "0.5436"]) {
    assert.ok(!serialised.includes(number), `the burn leaked outside lines: ${serialised}`);
  }
  assert.ok(view.lines.length >= 4, "a burn arrives with its basis or it does not arrive");
});

check("the panel renders the burn block whole and never indexes into it", () => {
  const { text } = panelSource();
  assert.ok(
    text.includes("capView.lines.map("),
    "the panel must render the burn block as one array",
  );
  assert.ok(
    !/capView\.lines\s*\[/.test(text),
    "indexing into the burn block is how the figure gets rendered without its basis",
  );
  // The measured branch alone, from its opening to the branch after it. The bar
  // is the fraction drawn as geometry, so it must sit inside the same block as
  // the lines rather than beside it with nothing to explain it, and the only
  // things the branch may read off the view are the bar, the tone and the lines.
  const opened = text.split('capView.kind === "measured" ? (')[1];
  assert.ok(opened, "the panel must have a measured branch");
  const block = (opened ?? "").split(") : capView.kind ===")[0];
  assert.ok(
    block.includes("capView.barPercent"),
    "the bar must be drawn inside the block that carries the basis lines",
  );
  assert.ok(
    block.includes("capView.lines.map("),
    "and the lines must be inside it too, not in a block of their own",
  );
  const reads = new Set((block.match(/capView\.[A-Za-z]+/g) || []).map((m) => m.slice(8)));
  assert.deepEqual(
    [...reads].sort(),
    ["barPercent", "lines", "tone"],
    "the measured branch may read the bar, the tone and the lines, and nothing else",
  );
});

check("the panel imports its readers rather than reaching past them", () => {
  const { file } = panelSource();
  const imported = new Set<string>();
  ts.forEachChild(file, (node) => {
    if (!ts.isImportDeclaration(node)) return;
    const clause = node.importClause;
    if (!clause || !clause.namedBindings || !ts.isNamedImports(clause.namedBindings)) return;
    for (const element of clause.namedBindings.elements) {
      imported.add(element.name.text);
    }
  });
  assert.ok(imported.has("readCap"), "the panel must get its cap view from readCap");
  assert.ok(imported.has("readRate"), "the panel must get its rate sentence from readRate");
  assert.ok(imported.has("readWindow"), "the panel must get its window caveats from readWindow");
  assert.ok(imported.has("readRowLabel"), "the panel must get a row's label from readRowLabel");
  assert.ok(
    !imported.has("readProjection"),
    "there is no projection: a panel importing one is reading a reader that does not exist",
  );
});

check("the panel hardcodes no instance address", () => {
  const { file } = panelSource();
  const live = /n8n\.cloud|editforge|\.app\.n8n\b/i;
  const offenders: string[] = [];
  const visit = (node: ts.Node): void => {
    if (ts.isStringLiteralLike(node) || ts.isTemplateLiteralToken(node)) {
      const text = (node as ts.LiteralLikeNode).text;
      const line = file.getLineAndCharacterOfPosition(node.pos).line + 1;
      if (text.includes("://")) offenders.push(`URL literal at line ${line}`);
      if (live.test(text)) offenders.push(`live n8n host at line ${line}`);
    }
    ts.forEachChild(node, visit);
  };
  ts.forEachChild(file, visit);
  assert.deepEqual(offenders, [], `the panel names an instance directly: ${offenders.join(", ")}`);
});
/* ================================================================== */
/* F8's CLASS: a field declared on the payload and read by nothing     */
/* ================================================================== */

/**
 * EVERY field on the payload types is read somewhere in the web layer.
 *
 * F8 was "read, carried, and rendered nowhere". Cycle one fixed `resets_at` and
 * left `Rate.assumptions` and `Instance.status_counts` in exactly that state, and
 * a sweep then found more. Fixing them one at a time is what produced this
 * pattern twice, so this is the rule instead.
 *
 * It is TYPE AWARE rather than a text grep, and it has to be: `Rate.assumptions`
 * and `Cap.assumptions` are different fields with the same name, and a text
 * count of "assumptions" cannot tell them apart. The TypeScript checker resolves
 * each access to the property symbol it actually reaches, so the two are
 * distinct here.
 *
 * It runs over the SAME program the law runs over, which is every file in the
 * web workspace rather than the reader and the panel. That is the F8 half of
 * the same correction: a field read only by a helper in a third file was
 * previously reported as unread.
 *
 * NF-C, CLOSED BY THE CUT. `Projection.from` was an untyped
 * `Record<string, unknown>` bag whose interior keys this sweep could not see,
 * so twenty odd values travelled inside it unchecked. The projection is gone
 * and the bag with it, and `no payload type carries an untyped bag` below
 * fails if another one appears. `Instance.status_counts` is a
 * `Record<string, number>` and is deliberately allowed: its keys are n8n's own
 * status strings, which are data rather than a field list, and `readProvenance`
 * enumerates them.
 */
const PAYLOAD_TYPES = PAYLOAD_TYPE_NAMES;

function payloadFieldCoverage(): { unread: string[]; declared: number } {
  const law = shippedLaw();
  const checker = law.checker;
  const readerFile = law.program.getSourceFile(READER);
  assert.ok(readerFile, "the reader must be in the program");
  if (!readerFile) return { unread: ["the reader is not in the program"], declared: 0 };

  // The declared property symbols, keyed by symbol identity.
  const declared = new Map<ts.Symbol, string>();
  ts.forEachChild(readerFile, (node) => {
    if (!ts.isTypeAliasDeclaration(node)) return;
    const name = node.name.text;
    if (!(PAYLOAD_TYPES as readonly string[]).includes(name)) return;
    const walk = (n: ts.Node): void => {
      if (ts.isPropertySignature(n) && n.name && ts.isIdentifier(n.name)) {
        const symbol = checker.getSymbolAtLocation(n.name);
        if (symbol) declared.set(symbol, `${name}.${n.name.text}`);
      }
      ts.forEachChild(n, walk);
    };
    walk(node.type);
  });

  const read = new Set<ts.Symbol>();
  const note = (symbol: ts.Symbol | undefined) => {
    if (!symbol) return;
    read.add(symbol);
    // A property reached through an optional or a union resolves to a synthetic
    // symbol whose declarations are the originals, so follow them.
    for (const declaration of symbol.declarations || []) {
      if (ts.isPropertySignature(declaration) && declaration.name && ts.isIdentifier(declaration.name)) {
        const original = checker.getSymbolAtLocation(declaration.name);
        if (original) read.add(original);
      }
    }
  };
  for (const file of law.files) {
    const visit = (node: ts.Node): void => {
      if (ts.isPropertyAccessExpression(node)) {
        note(checker.getSymbolAtLocation(node.name));
      }
      if (ts.isElementAccessExpression(node) && ts.isStringLiteralLike(node.argumentExpression)) {
        const objectType = checker.getTypeAtLocation(node.expression);
        note(objectType.getProperty(node.argumentExpression.text));
      }
      if (ts.isBindingElement(node)) {
        const source = node.propertyName ?? node.name;
        if (ts.isIdentifier(source)) {
          const patternType = checker.getTypeAtLocation(node.parent);
          note(patternType.getProperty(source.text));
        }
      }
      ts.forEachChild(node, visit);
    };
    ts.forEachChild(file, visit);
  }

  const unread: string[] = [];
  for (const [symbol, label] of declared) {
    if (!read.has(symbol)) unread.push(label);
  }
  return { unread: unread.sort(), declared: declared.size };
}

check("every field on the payload types is read somewhere in the web layer", () => {
  const { unread, declared } = payloadFieldCoverage();
  assert.ok(declared > 60, `the sweep must actually find the fields, found ${declared}`);
  assert.deepEqual(
    unread,
    [],
    "these are declared on the payload and read by nothing, which is F8 exactly. Either render " +
      `them or stop carrying them: ${unread.join(", ")}`,
  );
});

check("the field coverage sweep is not vacuous", () => {
  // A sweep that resolved nothing would report zero unread fields forever. This
  // proves it resolves real symbols and that it can tell two same named fields
  // apart, which a text grep cannot.
  const { declared } = payloadFieldCoverage();
  assert.ok(declared >= 70, `expected the full payload surface, got ${declared}`);
  const readerText = readFileSync(READER, "utf8");
  // Rate.assumptions and Cap.assumptions share a name. The sweep passing while
  // only one of them is read is the failure this note exists to prevent, so
  // assert both readers exist by name rather than by occurrence count.
  assert.ok(
    readerText.includes("instance.rate?.assumptions"),
    "the Rate assumptions must be read through readAssumptions",
  );
  assert.ok(
    readerText.includes("cap.assumptions"),
    "the Cap assumptions must be read into the burn block",
  );
});

// NF-C. The advisory was that a `Record<string, unknown>` bag hides its interior
// from the sweep above. `Projection.from` was the bag and it went with the
// projection; this fails if a new one appears on a surviving type.
check("no payload type carries an untyped bag the sweep cannot see into", () => {
  const law = shippedLaw();
  const reader = law.program.getSourceFile(READER);
  assert.ok(reader, "the reader must be in the program");
  if (!reader) return;
  const offenders: string[] = [];
  ts.forEachChild(reader, (node) => {
    if (!ts.isTypeAliasDeclaration(node)) return;
    const owner = node.name.text;
    if (!(PAYLOAD_TYPES as readonly string[]).includes(owner)) return;
    const walk = (n: ts.Node): void => {
      if (ts.isPropertySignature(n) && n.name && ts.isIdentifier(n.name) && n.type) {
        const text = n.type.getText().replace(/\s/g, "");
        // `Record<string, number>` is a real map of instance reported statuses.
        // `Record<string, unknown>` and `any` are a bag of named fields wearing
        // a map's clothes, and the field sweep is blind to every one of them.
        if (/Record<string,unknown>/.test(text) || /\bany\b/.test(text)) {
          offenders.push(`${owner}.${n.name.text}: ${n.type.getText()}`);
        }
      }
      ts.forEachChild(n, walk);
    };
    walk(node.type);
  });
  assert.deepEqual(
    offenders,
    [],
    `an untyped bag on a payload type hides its interior from the field sweep: ${offenders.join(", ")}`,
  );
});
/* ================================================================== */
/* NF4 and NF6: the rate sentence was presence checked only            */
/* ================================================================== */

function rateOf(over: Partial<Rate> = {}): Rate {
  return {
    basis: "id_delta",
    per_day: 120,
    executions_in_span: 120,
    span_hours: 24,
    span_seconds: 86400,
    from_id: 6292,
    to_id: 6412,
    from_moment: "2026-09-09T12:00:00Z",
    to_moment: "2026-09-10T12:00:00Z",
    rows_outside_the_rate: 0,
    reason: null,
    assumptions: ["a build session inside that window overstates a quiet day"],
    ...over,
  };
}

check("a rate arriving mistyped or impossible states no rate at all", () => {
  const cases: Array<[string, Partial<Rate>]> = [
    ["per_day NaN", { per_day: Number.NaN }],
    ["per_day as prose", { per_day: "one hundred and twenty" as unknown as number }],
    ["per_day Infinity", { per_day: Number.POSITIVE_INFINITY }],
    ["per_day zero", { per_day: 0 }],
    ["per_day negative", { per_day: -120 }],
    ["per_day null with an id_delta basis", { per_day: null }],
    ["span_hours as prose", { span_hours: "a day" as unknown as number }],
    ["span_hours NaN", { span_hours: Number.NaN }],
    ["span_hours negative", { span_hours: -24 }],
    ["span_seconds zero", { span_seconds: 0 }],
    ["span_seconds missing", { span_seconds: undefined }],
    ["executions_in_span zero", { executions_in_span: 0 }],
    ["executions_in_span as prose", { executions_in_span: "lots" as unknown as number }],
  ];
  for (const [label, over] of cases) {
    const view = readRate(rateOf(over), windowOf());
    assert.equal(view.kind, "unavailable", `${label} produced a rate`);
    // Naming the value it REJECTED is right; presenting it as the rate is the
    // defect. "a rate of Infinity a day ... which is not a number this panel will
    // state a rate from" is the correct sentence.
    assert.ok(!/NaN executions a day/.test(view.sentence), `${label} rendered NaN as a rate`);
    assert.ok(
      !/Infinity executions a day/.test(view.sentence),
      `${label} rendered Infinity as a rate`,
    );
    assert.ok(!/^\s*\d/.test(view.sentence), `${label} opened with a number as though it were a rate`);
    assert.match(view.sentence, /not a number this panel will state a rate from/);
  }
});

check("a usable rate is stated with its span and its two endpoints", () => {
  const view = readRate(rateOf(), windowOf());
  assert.equal(view.kind, "measured");
  assert.match(view.sentence, /120 executions a day/);
  assert.match(view.sentence, /120 ids across 24 hours/);
  assert.ok(view.caveats.some((line) => line.includes("execution 6292") && line.includes("execution 6412")));
});

check("a window shorter than an hour says how little the rate rests on", () => {
  // NF6. `rate_span_hours` was round(..., 3) AND the denominator, so a four second
  // window overstated by 11 percent and a one second window rounded to zero and
  // was refused. The route divides by the exact seconds now; this is the half a
  // reader sees.
  const view = readRate(rateOf({ span_seconds: 4, span_hours: 0.001, per_day: 21600 }), windowOf());
  assert.equal(view.kind, "measured");
  assert.ok(
    view.caveats.some((line) => line.includes("4 seconds of wall clock")),
    `a four second window must say so: ${JSON.stringify(view.caveats)}`,
  );
  assert.ok(view.caveats.some((line) => line.includes("21600 a day")));
  // And an hour long window does not carry that caveat, so it is not noise.
  const hour = readRate(rateOf({ span_seconds: 3600, span_hours: 1, per_day: 24 }), windowOf());
  assert.ok(!hour.caveats.some((line) => line.includes("wall clock")));
});

check("an unavailable rate carries the route's reason and no number", () => {
  const view = readRate(
    rateOf({ basis: "unavailable", per_day: null, reason: "the window holds one execution" }),
    windowOf(),
  );
  assert.equal(view.kind, "unavailable");
  assert.match(view.sentence, /one execution/);
  const missing = readRate(null, null);
  assert.equal(missing.kind, "unavailable");
  assert.match(missing.sentence, /No rate was reported/);
});

/* ================================================================== */
/* The rate's own assumptions, which lived nowhere reachable           */
/* ================================================================== */

check("the rate's assumptions are shown on an instance with no cap at all", () => {
  // The panel rendered assumptions only inside the projected date block, which
  // is unreachable with no cap, so a self hosted instance had a two hour window
  // extrapolated to a flat figure a day with no assumption anywhere. The block
  // that carries them now is the burn, and an instance with no cap has no burn
  // either, so the subtraction still has to be done rather than assumed.
  const assumptions = readAssumptions(instanceOf({ cap: null, rate: rateOf() }));
  assert.equal(assumptions.length, 1);
  assert.match(assumptions[0], /overstates a quiet day/);
});

check("the rate's assumptions are not shown twice when the burn already carries them", () => {
  const shared = "The rate is the rate over the window actually read, which is short.";
  const instance = instanceOf({
    rate: rateOf({ assumptions: [shared] }),
    cap: capOf({ assumptions: [shared] }),
  });
  const view = readCap(instance.cap);
  assert.equal(view.kind, "measured");
  if (view.kind !== "measured") return;
  assert.ok(view.lines.includes(shared), "the burn block carries it");
  assert.deepEqual(
    readAssumptions(instance),
    [],
    "and the card does not carry it a second time",
  );
});
/* ================================================================== */
/* An unconfigured instance is never silently dropped                  */
/* ================================================================== */

check("the panel renders every instance rather than filtering unconfigured ones out", () => {
  const { text } = panelSource();
  assert.ok(
    !/state\s*!==\s*"unconfigured"/.test(text),
    "filtering unconfigured instances out drops the secondary card and nothing on the page names it",
  );
  assert.ok(
    text.includes("orderInstances(payload.instances)"),
    "the panel renders the whole ordered list",
  );
  // And the NOT CONFIGURED branch is reachable for ONE instance rather than only
  // when every instance is unconfigured.
  const verdict = readInstance(
    instanceOf({ state: "unconfigured", window: null, counts: null, cap: null, host: null }),
  );
  assert.equal(verdict.label, "NOT CONFIGURED");
  assert.match(readVariables(instanceOf()), /N8N_API_URL/);
  assert.match(readVariables(instanceOf()), /never returned/);
});

/* ================================================================== */
/* The orphan reset, and the cause that was never measured             */
/* ================================================================== */

check("a reset stated with no cap is one sentence, not two contradictory ones", () => {
  const view = readCap(
    capOf({
      state: "not_stated",
      source: null,
      cap: null,
      resets_at: "2026-10-01",
      orphan_reset:
        "2026-10-01 is configured as the cycle reset for this instance while no cap is configured at all.",
      reset_readable: true,
      reset_in_the_past: false,
      anchor: null,
      spent_estimate: null,
      spent_basis: null,
      remaining_estimate: null,
      used_fraction: null,
      counted_from_id: null,
      counted_from_moment: null,
      reason: "no cap is stated for this instance",
      note: "No cap is configured for this instance.",
    }),
  );
  assert.equal(view.kind, "orphan-reset");
  assert.match(view.sentence, /no cap is configured at all/);
  // The generic reset paragraph must NOT also be drawn: that is the second of the
  // two contradictory sentences.
  assert.equal(view.resetsAt, null);
});

check("the unsaved id caveat names no cause it cannot distinguish", () => {
  const view = readWindow(windowOf({ not_saved_in_span: 19, ids_in_span: 21, ids_read: 2 }));
  const line = view.caveats.find((l) => l.includes("no saved row"));
  assert.ok(line, "the caveat must exist");
  if (!line) return;
  assert.match(line, /19 of the 21 ids/);
  assert.match(line, /cannot tell them apart/);
  assert.ok(
    !/is what the success data setting does/.test(line),
    "this read cannot distinguish that setting from age pruning, a deletion or a shared sequence",
  );
  assert.ok(line.includes("age pruning"), "the alternatives are named rather than one being asserted");
});

/* ================================================================== */
/* The degraded dot was the faintest mark on the card                  */
/* ================================================================== */

/** WCAG relative luminance of an sRGB triple. */
function luminance(r: number, g: number, b: number): number {
  const channel = (value: number) => {
    const c = value / 255;
    return c <= 0.04045 ? c / 12.92 : Math.pow((c + 0.055) / 1.055, 2.4);
  };
  return 0.2126 * channel(r) + 0.7152 * channel(g) + 0.0722 * channel(b);
}

function contrastAgainstVoid(alpha: number): number {
  // The control plane's ground, #04070d, from ControlPlane.tsx.
  const bg = [4, 7, 13];
  const composited = bg.map((c) => alpha * 255 + (1 - alpha) * c);
  const fg = luminance(composited[0], composited[1], composited[2]);
  const back = luminance(bg[0], bg[1], bg[2]);
  const [lighter, darker] = fg > back ? [fg, back] : [back, fg];
  return (lighter + 0.05) / (darker + 0.05);
}

check("every indicator dot on the card clears the 3:1 non-text floor", () => {
  // `neutral: "bg-white/30"` computed to 2.55:1, below the WCAG 3:1 floor for a
  // non-text indicator, and it is the dot for NOTHING SAVED, STATUS UNREPORTED,
  // STATUS UNRECOGNISED, WINDOW CUT OFF, SPAN NOT FULLY SAVED and NOT CONFIGURED:
  // the faintest mark on the card carried every degraded state. control-check.ts
  // bans only `text-` opacities, so a `bg-` one passed it.
  //
  // The maths is executed rather than asserted, and it is checked in both
  // directions so a future edit cannot dim the dot back.
  assert.ok(contrastAgainstVoid(0.3) < 3, "the reproduction: white/30 is below the floor");
  assert.ok(contrastAgainstVoid(0.5) >= 3, "white/50 clears it");

  const { text } = panelSource();
  const dotBlock = text.slice(text.indexOf("const TONE_DOT"), text.indexOf("const TONE_TEXT"));
  assert.ok(dotBlock.includes("neutral:"), "the dot table must be the thing being measured");
  const offences: string[] = [];
  for (const hit of dotBlock.matchAll(/bg-white\/(\d+)/g)) {
    const ratio = contrastAgainstVoid(Number(hit[1]) / 100);
    if (ratio < 3) offences.push(`${hit[0]} is ${ratio.toFixed(2)}:1 on #04070d`);
  }
  assert.deepEqual(offences, [], `an indicator dot below 3:1: ${offences.join(", ")}`);
});

/* ================================================================== */
/* F4's class: what tone good REQUIRES                                 */
/* ================================================================== */

check("the three states that survived F4's first fix all refuse a good tone", () => {
  const cases: Array<[string, Instance, RegExp]> = [
    [
      "(i) ids that contradict the clock",
      instanceOf({
        window: wholeWindow({
          id_order_matches_time: false,
          id_order_inversions: 2,
          id_order_summary: "id order and startedAt order disagree over the window read",
          ids_in_span: null,
          not_saved_in_span: null,
        }),
        counts: { ...ZERO, succeeded: 5 },
      }),
      /disagree/,
    ],
    [
      "(ii) 19 of a 21 id span never saved",
      instanceOf({
        window: wholeWindow({
          executions_read: 2,
          ids_read: 2,
          dated_ids_read: 2,
          newest_id: 6400,
          oldest_id: 6380,
          ids_in_span: 21,
          not_saved_in_span: 19,
          span_coverage: 0.0952,
        }),
        counts: { ...ZERO, succeeded: 2 },
      }),
      /19 of the 21 ids in this span have no saved row/,
    ],
    [
      "(iii) 100 read with every bucket zero",
      instanceOf({
        window: wholeWindow({ executions_read: 100, ids_read: 100, dated_ids_read: 100, ids_in_span: 100 }),
        counts: { ...ZERO },
      }),
      /add up to 0 for 100 executions read/,
    ],
  ];
  for (const [label, instance, expected] of cases) {
    const verdict = readInstance(instance);
    assert.notEqual(verdict.tone, "good", `${label} read as good`);
    assert.ok(
      !/none of them failed/.test(verdict.sentence),
      `${label} claimed nothing failed: ${verdict.sentence}`,
    );
    assert.match(verdict.sentence, expected, `${label} did not say why`);
  }
});

check("the good tone is gated on every row having passed, in the source", () => {
  // A SOURCE check rather than a behavioural one, and the reason is worth stating
  // plainly: `allPassed` and the requirement list are mutually redundant by
  // construction. No `Counts` shape can satisfy every requirement while
  // `succeeded !== read`, because a set that adds up with fewer passes than rows
  // must have a non empty bucket that some requirement names. So neutering
  // `allPassed` alone changes no behaviour any fixture can reach, and an
  // adversarial pass against this fix measured exactly that: the mutation
  // `const allPassed = true` survived every behavioural check.
  //
  // Two guards each catching the other's removal is defence in depth, not a
  // bypass, and the mutation that removes the OTHER one is caught behaviourally:
  // neutering `everyRowIsAccountedFor` leaves `allPassed` holding the tone on the
  // 100-read-zero-buckets case. But a line whose removal no test notices is a line
  // this file has to hold in place itself, so it does.
  const readerText = readFileSync(READER, "utf8");
  assert.ok(
    readerText.includes("const allPassed = counts.succeeded === read;"),
    "the completeness condition is `every row read landed in the bucket that says it passed`",
  );
  assert.ok(
    /if \(allPassed && tone === "good" && scope\.length === 0\)/.test(readerText),
    "the good return must be conjoined with allPassed, not merely near it",
  );
  assert.ok(
    !/const allPassed = true/.test(readerText),
    "a constant true is not a condition",
  );
});

check("every bucket on Counts is named by a good requirement", () => {
  // The structural half of F4's class. An exclusion list has to be complete to be
  // correct and never is, so the runtime rule is now `counts.succeeded === read`
  // plus a list that says WHICH. This is what stops a bucket being added to
  // `Counts` with no requirement written beside it: the new field's rows would be
  // rows not in `succeeded`, so the tone would already be right, but nothing
  // would SAY why, and a downgraded tone with no sentence is a tone nobody can
  // act on.
  const readerText = readFileSync(READER, "utf8");
  const file = ts.createSourceFile(READER, readerText, ts.ScriptTarget.ES2022, true, ts.ScriptKind.TS);
  const fields: string[] = [];
  ts.forEachChild(file, (node) => {
    if (!ts.isTypeAliasDeclaration(node) || node.name.text !== "Counts") return;
    const walk = (n: ts.Node): void => {
      if (ts.isPropertySignature(n) && n.name && ts.isIdentifier(n.name)) fields.push(n.name.text);
      ts.forEachChild(n, walk);
    };
    walk(node.type);
  });
  assert.ok(fields.length >= 7, `the sweep must find the buckets, found ${fields.join(", ")}`);

  // The whole decision region: the requirements list AND `readInstance` itself,
  // because `allPassed` is the condition that grants the claim and it lives in the
  // function rather than in the list.
  const start = readerText.indexOf("const GOOD_REQUIRES");
  const end = readerText.indexOf("export function readWindow");
  assert.ok(start > 0 && end > start, "the decision region must be locatable");
  const block = readerText.slice(start, end);
  // Every bucket must be named by a requirement OTHER than the arithmetic sum in
  // `everyRowIsAccountedFor`, because appearing only in the sum is what lets a new
  // bucket add up and still say nothing.
  const sumStart = block.indexOf('name: "everyRowIsAccountedFor"');
  const sumEnd = block.indexOf("},", block.indexOf("return total === read", sumStart));
  const outsideTheSum = block.slice(0, sumStart) + block.slice(sumEnd);
  const unnamed = fields.filter((field) => !outsideTheSum.includes(`counts.${field}`));
  assert.deepEqual(
    unnamed,
    [],
    "these buckets are counted in the sum and named by no requirement, so rows in them would " +
      `downgrade the tone and say nothing about why: ${unnamed.join(", ")}`,
  );
});

check("three more shapes against the good requirements", () => {
  // Shapes neither adversary used, against the list rather than against an
  // exclusion set.
  const cases: Array<[string, Instance]> = [
    [
      "counts that sum to MORE than the rows read",
      instanceOf({ window: wholeWindow(), counts: { ...ZERO, succeeded: 5, running: 3 } }),
    ],
    [
      "an id span that could not be measured at all",
      instanceOf({
        window: wholeWindow({ ids_in_span: null, not_saved_in_span: null }),
        counts: { ...ZERO, succeeded: 5 },
      }),
    ],
    [
      "every row waiting rather than finished",
      instanceOf({ window: wholeWindow(), counts: { ...ZERO, waiting: 5 } }),
    ],
  ];
  for (const [label, instance] of cases) {
    const verdict = readInstance(instance);
    assert.notEqual(verdict.tone, "good", `${label} read as good`);
    assert.ok(!/none of them failed/.test(verdict.sentence), `${label} claimed nothing failed`);
    assert.ok(verdict.sentence.length > 40, `${label} said nothing about why`);
  }
});

/* ================================================================== */
/* Provenance: every carried field has somewhere to be read            */
/* ================================================================== */

function payloadOf(over: Partial<TelemetryPayload> = {}): TelemetryPayload {
  return {
    read_only: true,
    read_at: READ_AT,
    limit: 100,
    instances: [instanceOf()],
    configured: 2,
    reachable: 1,
    findings: [],
    note: "Read only telemetry.",
    ...over,
  };
}

check("the provenance block says where every number came from", () => {
  const lines = readProvenance(payloadOf(), instanceOf());
  const all = lines.join(" | ");
  assert.match(all, /Read only/);
  assert.match(all, /1 of 2 configured instances answered/);
  assert.match(all, /answered HTTP 200/);
  assert.match(all, /5 distinct usable ids/);
  assert.match(all, /Newest usable id 6412/);
  assert.match(all, /121 ids lie in that span/);
  assert.match(all, /Raw statuses as the instance reported them: success 5/);
  assert.match(all, /anchor plus id delta/);
  assert.match(all, /rate window runs from id 6292/);
  assert.match(all, /exactly 86400 seconds/);
});

check("a status the panel does not bucket is still legible in the raw statuses", () => {
  const lines = readProvenance(
    payloadOf(),
    instanceOf({ status_counts: { "some-new-state": 4, success: 1 } }),
  );
  assert.ok(lines.some((line) => line.includes("some-new-state 4")));
});

check("a row's mode and whether it finished are both rendered", () => {
  const trigger = readRowDetail(rowOf());
  assert.equal(trigger.mode, "mode trigger");
  assert.match(trigger.finished, /finished/);
  // MEASURED: n8n uses "error" as a MODE for an error handler workflow, and it is
  // NOT a status. A reader shown only the string would call it a failure.
  const handler = readRowDetail(rowOf({ mode: "error", status: "success" }));
  assert.match(handler.mode, /not a failed run/);
  const unfinished = readRowDetail(rowOf({ stopped_at: null, duration_ms: null }));
  assert.match(unfinished.finished, /had not finished/);
  const clockless = readRowDetail(rowOf({ started_at: null, stopped_at: null }));
  assert.match(clockless.finished, /no clock on this row/);
  assert.equal(readRowDetail(rowOf({ mode: null })).mode, "mode unreported");
});

console.log(`\n${checks} checks passed`);
