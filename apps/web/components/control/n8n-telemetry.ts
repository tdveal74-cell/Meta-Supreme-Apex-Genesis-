// Pure readers over the payload of GET /n8n/executions. No fetch, no React,
// so the rules below can be exercised on their own by
// scripts/n8n-telemetry-check.ts.
//
// The one law in this file: A DERIVED VALUE IS NEVER RETURNED WITHOUT THE BASIS
// IT WAS DERIVED FROM.
//
// The law used to name a projected exhaustion date, because that was the only
// derived date on the wire. The projection was cut on 2026-09-10, and the law
// was retargeted rather than deleted with it: the burn against the plan cap is
// still derived, and a bare burn figure with no basis is the same defect the
// bare wall was. `readCap` is now the only way the panel can obtain a spend, a
// remaining count or a fraction of a cap, and it returns them only inside
// `lines`, whose first entry states the figure and whose rest is the basis and
// the assumptions. There is no field on that view holding a number on its own.
// A bare number on a control plane reads as a measurement, and on this estate
// the burn is an id gap added to a figure a human read off a usage page,
// against a ceiling nothing here measured.
//
// The second law: nothing here supplies a fallback. A cap the route did not
// state stays absent, an unreached instance renders no figures, and an instance
// that answered with nothing saved is never dressed up as a healthy one.
//
// The third law, added after a read that knew nothing rendered a green tick:
// a TONE is a claim too. `good` is reserved for a read that actually supports
// it, and every way a read can be degraded and still answer 200 downgrades it
// and says which way.
//
// The fourth law, added after `per_day` arrived as NaN and as the string
// "one hundred and twenty" and both produced a confident date: presence is not
// validation. Every number these readers cite is checked for being a finite
// number in the range the sentence assumes, and the set of them is checked for
// adding up, before any of it is rendered.

export type InstanceState =
  | "unconfigured"
  | "misconfigured"
  | "unreachable"
  | "refused"
  | "malformed"
  | "errored"
  | "ok";

export type ExecutionRow = {
  id: number | null;
  status: string | null;
  workflow_id: string | null;
  // MEASURED 2026-09-10: the executions API returns workflowId and NO
  // workflowData.name, so this is null on a live row and `workflow_label`
  // below is what a reader is actually shown.
  workflow_name: string | null;
  workflow_label: string | null;
  workflow_label_kind: "name" | "id" | "unidentified" | null;
  mode: string | null;
  started_at: string | null;
  stopped_at: string | null;
  duration_ms: number | null;
};

export type Window = {
  executions_read: number;
  ids_read: number;
  rows_without_id: number;
  rows_without_started_at: number;
  dated_ids_read: number;
  newest_id: number | null;
  oldest_id: number | null;
  newest_id_started_at: string | null;
  oldest_id_started_at: string | null;
  newest_started_at: string | null;
  oldest_started_at: string | null;
  span_hours: number | null;
  rate_from_id: number | null;
  rate_to_id: number | null;
  rate_from_moment: string | null;
  rate_to_moment: string | null;
  rate_span_hours: number | null;
  // The EXACT span the rate divides by. `rate_span_hours` is rounded to three
  // places and is for display; rounding before dividing overstated a four
  // second window by 11 percent and refused a one second one outright.
  rate_span_seconds: number | null;
  id_order_matches_time: boolean | null;
  id_order_inversions: number;
  id_order_note: string;
  // The short form of `id_order_note`, for the places that must SAY it rather
  // than explain it. The full note is rendered once, on the instance card.
  id_order_summary: string | null;
  ids_in_span: number | null;
  not_saved_in_span: number | null;
  // What fraction of the id span has a saved row of its own. This is what tells
  // a reader whether "none of them failed" is about the instance or about a
  // sliver of it: a two row read of a twenty one id span is 0.0952.
  span_coverage: number | null;
  truncated: boolean;
};

export type Counts = {
  failed: number;
  succeeded: number;
  canceled: number;
  running: number;
  waiting: number;
  other: number;
  status_unreported: number;
};

export type Rate = {
  basis: "id_delta" | "unavailable";
  per_day: number | null;
  executions_in_span?: number;
  span_hours?: number;
  span_seconds?: number;
  from_id?: number | null;
  to_id?: number | null;
  from_moment?: string | null;
  to_moment?: string | null;
  rows_outside_the_rate?: number;
  reason: string | null;
  assumptions: string[];
};

export type Cap = {
  state: "not_stated" | "stated" | "estimated" | "inconsistent" | "unusable";
  source: string | null;
  cap: number | null;
  resets_at: string | null;
  // A reset stated for an instance with no cap. Its own field so the panel can
  // render ONE coherent sentence instead of two contradictory adjacent ones.
  orphan_reset: string | null;
  // Whether the configured reset is a date at all. `null` when none is
  // configured. `false` used to be reported only inside the projection's reset
  // note, so the cut would have taken the only statement of it with it and the
  // panel would have printed an unreadable value verbatim.
  reset_readable: boolean | null;
  reset_in_the_past: boolean | null;
  read_at: string | null;
  anchor: { id: number; spent: number; at: string | null; source: string } | null;
  spent_estimate: number | null;
  spent_basis: string | null;
  remaining_estimate: number | null;
  used_fraction: number | null;
  // The id the spend was carried forward to, and the moment that id's own
  // execution started. The basis of the burn, so they travel with it.
  counted_from_id: number | null;
  counted_from_moment: string | null;
  // Why no spend was derived, and null exactly when one was.
  reason: string | null;
  // What a derived spend rests on. The burn is derived, so it carries its
  // assumptions the way the projected date used to carry its own.
  assumptions: string[];
  problems: string[];
  note: string;
};

export type Instance = {
  role: string;
  state: InstanceState;
  reason: string | null;
  configured_host: string | null;
  host: string | null;
  status_code: number | null;
  variables: { url: string; key: string; cap: string };
  window: Window | null;
  counts: Counts | null;
  status_counts: Record<string, number> | null;
  recent: ExecutionRow[];
  rate: Rate | null;
  cap: Cap | null;
  read_problems?: string[];
};

export type TelemetryPayload = {
  read_only: boolean;
  read_at: string;
  limit: number;
  instances: Instance[];
  configured: number;
  reachable: number;
  findings: string[];
  note: string;
};

export type Tone = "good" | "warn" | "bad" | "neutral";

export function isTelemetryPayload(value: unknown): value is TelemetryPayload {
  if (!value || typeof value !== "object") return false;
  const candidate = value as Partial<TelemetryPayload>;
  return (
    Array.isArray(candidate.instances) &&
    typeof candidate.read_at === "string" &&
    Array.isArray(candidate.findings)
  );
}

/* ------------------------------------------------------------------ */
/* type and sanity gates, applied before anything is cited             */
/* ------------------------------------------------------------------ */

function finite(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function positive(value: unknown): number | null {
  const read = finite(value);
  return read !== null && read > 0 ? read : null;
}

function nonNegative(value: unknown): number | null {
  const read = finite(value);
  return read !== null && read >= 0 ? read : null;
}

function instant(value: unknown): string | null {
  if (typeof value !== "string" || !value.trim()) return null;
  return Number.isNaN(new Date(value).getTime()) ? null : value;
}

/** How a rejected value is named in the reason. Short, and never a date. */
function describe(value: unknown): string {
  if (typeof value === "number") return Number.isNaN(value) ? "NaN" : String(value);
  if (typeof value === "string") return JSON.stringify(value.slice(0, 32));
  if (value === null) return "null";
  return typeof value;
}

/* ------------------------------------------------------------------ */
/* One instance's headline                                             */
/* ------------------------------------------------------------------ */

export type InstanceVerdict = { tone: Tone; label: string; sentence: string };

const TONE_RANK: Record<Tone, number> = { good: 0, neutral: 1, warn: 2, bad: 3 };

/**
 * WHAT `good` REQUIRES. Not what forbids it.
 *
 * The version of `readInstance` this replaces listed the ways a read could be
 * bad and defaulted to `good` for everything else, so every state nobody had
 * thought of arrived green. Three more were then found by a second adversary
 * after six had already been fixed, which is what an exclusion list does: it
 * has to be complete to be correct, and it never is.
 *
 * This list is the other direction. `good` is granted only when every entry
 * here is satisfied; anything else is a downgrade with a sentence naming the
 * entry that failed. A state nobody enumerated fails `everyRowIsAccountedFor`
 * or `everyRowPassed` and lands neutral, because a row that is not in a
 * definite passing bucket cannot make a passing claim true.
 *
 * The three that survived cycle one, each now an entry:
 *
 * (i)   ids that CONTRADICT the clock. `id_order_matches_time` false with two
 *       inversions and the rate refused rendered tone `good` and "3 saved
 *       executions read, and none of them failed": F7's whole subject as a
 *       clean bill of health.
 * (ii)  19 of a 21 id span never saved. A row missing a STATUS downgraded the
 *       tone; 19 executions missing a ROW ENTIRELY did not, because
 *       `readInstance` never read `not_saved_in_span` at all.
 * (iii) `executions_read` 100 with every bucket 0. `readCap` enforced
 *       spent + remaining === ceiling and this enforced nothing, while the file
 *       header's fourth law claimed the set "is checked for adding up, before
 *       any of it is rendered".
 */
const GOOD_REQUIRES: Array<{
  name: string;
  tone: Tone;
  label: string;
  /** The caveat when the requirement is NOT met, or null when it is. */
  unmet: (win: Window, counts: Counts, read: number) => string | null;
}> = [
  {
    name: "everyRowIsAccountedFor",
    tone: "bad",
    label: "COUNTS DO NOT ADD UP",
    // (iii). The buckets are exhaustive by construction on the route, so a set
    // that does not sum to the row count is a payload this panel cannot
    // account for, not a quiet instance.
    unmet: (_win, counts, read) => {
      const total =
        counts.failed +
        counts.succeeded +
        counts.canceled +
        counts.running +
        counts.waiting +
        counts.other +
        counts.status_unreported;
      return total === read
        ? null
        : `the status counts add up to ${total} for ${read} executions read, so this panel cannot ` +
            "account for what ran and states nothing about it";
    },
  },
  {
    name: "noRowFailed",
    tone: "warn",
    label: "FAILURES IN WINDOW",
    unmet: (_win, counts, read) =>
      counts.failed > 0 ? `${counts.failed} of ${read} failed` : null,
  },
  {
    name: "noRowWasCanceled",
    tone: "warn",
    label: "CANCELED IN WINDOW",
    unmet: (_win, counts) =>
      counts.canceled > 0 ? `${counts.canceled} were canceled` : null,
  },
  {
    name: "everyRowReportedAStatus",
    tone: "neutral",
    label: "STATUS UNREPORTED",
    unmet: (_win, counts) =>
      counts.status_unreported > 0
        ? `${counts.status_unreported} carried no status at all, so whether they failed is unknown`
        : null,
  },
  {
    name: "everyStatusWasRecognised",
    tone: "neutral",
    label: "STATUS UNRECOGNISED",
    unmet: (_win, counts) =>
      counts.other > 0
        ? `${counts.other} carried a status this panel does not bucket, so whether they failed is unknown`
        : null,
  },
  {
    name: "noRowIsStillInFlight",
    tone: "neutral",
    label: "STILL RUNNING",
    // A run that has not finished has not passed. The version of this scoped the
    // sentence and left the tone `good`, which reads as a settled window when it
    // is not one.
    unmet: (_win, counts) => {
      const inFlight = counts.running + counts.waiting;
      return inFlight > 0
        ? `${inFlight} had not finished when the window was read, so whether they pass is not yet known`
        : null;
    },
  },
  {
    name: "theWindowIsWhole",
    tone: "neutral",
    label: "WINDOW CUT OFF",
    unmet: (win) =>
      win.truncated
        ? "the window is cut off at the row limit, so older runs are outside it"
        : null,
  },
  {
    name: "theIdsAgreeWithTheClock",
    tone: "warn",
    label: "IDS CONTRADICT THE CLOCK",
    // (i). Warn rather than neutral: this is not missing information, it is
    // information that disagrees with itself, and it invalidates the rate and
    // the burn beside it.
    unmet: (win) =>
      win.id_order_matches_time === false
        ? win.id_order_summary ||
          "id order and startedAt order disagree over this window, so no id gap is used as a count"
        : null,
  },
  {
    name: "theIdSpanIsFullySaved",
    tone: "neutral",
    label: "SPAN NOT FULLY SAVED",
    // (ii). The rule is `not_saved_in_span === 0`, and the consequence is
    // deliberate: on this estate a set of organs stopped saving successful
    // executions on 2026-09-05, so the live primary will read NEUTRAL with this
    // sentence until that setting changes. That is the honest answer. With 19 of
    // a 21 id span unsaved, "none of them failed" is a statement about 2
    // executions being presented as a statement about 21.
    //
    // A null count is not a pass either: it means the span could not be
    // measured, which is less information rather than more.
    unmet: (win) => {
      if (win.not_saved_in_span === null) {
        return "the id span of this window could not be measured, so how much of it went unsaved is unknown";
      }
      if (win.not_saved_in_span <= 0) return null;
      const span = win.ids_in_span;
      return (
        `${win.not_saved_in_span} of the ${span ?? "unknown"} ids in this span have no saved row, so ` +
        `whether those executions failed is unknown. This window accounts for ${win.ids_read} of them`
      );
    },
  },
];

/**
 * How one instance reads at a glance.
 *
 * Only a reached instance that actually accounts for what it read can be
 * `good`. The cases that must never be `good` are the ones a collapsing panel
 * gets wrong, and every one of them was reproduced against the version of this
 * function that computed `failed = counts?.failed ?? 0` and then
 * `tone = failed > 0 ? "warn" : "good"`:
 *
 * * an instance nobody configured, and an instance that answered with an
 *   empty list. During a cutover the second is the whole question, so it gets
 *   a neutral tone and a sentence that says the read succeeded and found
 *   nothing, rather than a green tick that reads as a target already carrying
 *   the load.
 * * 100 executions read, every one of them `status_unreported`: a read that
 *   knows nothing about whether anything failed, which rendered green and the
 *   sentence "100 saved executions read, none of them failed".
 * * 100 canceled, and 100 carrying a status this panel does not bucket. Both
 *   rendered the same green sentence.
 * * `counts` absent altogether, where `?? 0` turned "no information" into
 *   "zero failures".
 * * a window cut off at the row limit, where "none of them failed" is a
 *   statement about the window and was rendered as a statement about the
 *   instance.
 */
export function readInstance(instance: Instance): InstanceVerdict {
  const host = instance.host || instance.configured_host;
  switch (instance.state) {
    case "unconfigured":
      return {
        tone: "neutral",
        label: "NOT CONFIGURED",
        sentence:
          instance.reason ||
          `Set ${instance.variables.url} and ${instance.variables.key} to read this instance.`,
      };
    case "misconfigured":
      return {
        tone: "bad",
        label: "HALF CONFIGURED",
        sentence: instance.reason || "The configuration for this instance is incomplete.",
      };
    case "unreachable":
      return {
        tone: "bad",
        label: "NOT REACHED",
        sentence:
          instance.reason ||
          `${host || "the instance"} was not reached. Nothing below is a measurement.`,
      };
    case "refused":
      return {
        tone: "bad",
        label: "READ REFUSED",
        sentence:
          instance.reason ||
          `${host || "the instance"} is up and declined the read. Check the API key.`,
      };
    case "malformed":
      return {
        tone: "bad",
        label: "WRONG SHAPE",
        sentence:
          instance.reason ||
          `${host || "the instance"} answered, but not with an executions list.`,
      };
    case "errored":
      return {
        tone: "bad",
        label: "READ FAILED",
        sentence:
          instance.reason ||
          `Reading ${host || "this instance"} raised. Nothing below it is a measurement.`,
      };
    case "ok": {
      const win = instance.window;
      const counts = instance.counts;
      if (!win || !counts) {
        // A 200 with no window or no counts is not a quiet instance. It is a
        // payload this panel cannot account for, and `?? 0` used to turn it
        // into a clean bill of health.
        return {
          tone: "bad",
          label: "NOTHING TO COUNT",
          sentence:
            `${host || "the instance"} answered, but the read carried no window or no status ` +
            "counts, so nothing here is a measurement of what ran.",
        };
      }
      const read = win.executions_read;
      if (read === 0) {
        return {
          tone: "neutral",
          label: "NOTHING SAVED",
          sentence:
            instance.reason ||
            `${host} answered with no saved executions. The read worked; this is not a claim that nothing ran.`,
        };
      }

      let tone: Tone = "good";
      let label = "READ";
      const scope: string[] = [];
      const worsen = (next: Tone, nextLabel: string) => {
        if (TONE_RANK[next] > TONE_RANK[tone]) {
          tone = next;
          label = nextLabel;
        }
      };

      // THE ONE CONDITION for "and none of them failed": every row read landed in
      // the bucket that says it passed. Nothing below can grant that claim and
      // this alone can deny it, which is what makes the rule complete rather than
      // merely long. A bucket added to `Counts` tomorrow with no requirement
      // written beside it still cannot produce a green tick, because rows in it
      // are rows not in `succeeded`.
      const allPassed = counts.succeeded === read;

      // THE REQUIREMENTS. These say WHICH, and they set the tone. `good` needs
      // this list satisfied AND `allPassed`, so a state nobody enumerated is
      // neutral by construction rather than good by omission.
      for (const requirement of GOOD_REQUIRES) {
        const failure = requirement.unmet(win, counts, read);
        if (failure === null) continue;
        worsen(requirement.tone, requirement.label);
        scope.push(failure);
      }

      if (!allPassed && scope.length === 0) {
        // Unreachable by any `Counts` shape today: a set that adds up with fewer
        // passes than rows must have a non empty bucket one of the requirements
        // above names. It is kept, and stated to be unreachable rather than
        // described as a guard I have watched fire, because the shape that reaches
        // it is a bucket added to `Counts` and folded into the sum with no
        // requirement beside it. `every bucket on Counts is named by a requirement`
        // in scripts/n8n-telemetry-check.ts is the guard with a control behind it;
        // this is the runtime floor under it.
        worsen("neutral", "UNACCOUNTED");
        scope.push(
          `only ${counts.succeeded} of the ${read} executions read landed in a bucket that says it ` +
            "passed, and this panel cannot say what the rest did",
        );
      }

      if (allPassed && tone === "good" && scope.length === 0) {
        return {
          tone: "good",
          label: "READ",
          sentence: `${read} saved executions read from ${host}, and none of them failed.`,
        };
      }
      const opening =
        counts.failed > 0
          ? `${read} saved executions read from ${host}`
          : `${read} saved executions read from ${host}, none of the rows read recorded as failed`;
      return { tone, label, sentence: `${opening}: ${scope.join("; ")}.` };
    }
    default:
      return {
        tone: "neutral",
        label: "UNKNOWN",
        sentence: "The route reported a state this panel does not know.",
      };
  }
}

/* ------------------------------------------------------------------ */
/* What the window covered, and what it does not support               */
/* ------------------------------------------------------------------ */

export type WindowView = { headline: string; caveats: string[] };

/**
 * The window sentence, and every reason the numbers beside it are narrower
 * than the window looks.
 *
 * `rows_without_id` is the one this exists for. The rate is an id gap over a
 * time span; a row whose id does not parse still carries a startedAt, so it
 * used to widen the span while contributing nothing to the gap, and a single
 * thirty day old row of that kind turned a measured 120 a day into 4. The
 * route now takes both halves from the same rows, and the count of rows that
 * took no part travels here so a reader can see the window they are shown is
 * wider than the window that was measured.
 */
export function readWindow(win: Window | null): WindowView {
  if (!win) {
    return { headline: "No window was read for this instance.", caveats: [] };
  }
  const headline =
    win.span_hours === null
      ? "The window carries no readable timestamps, so it has no span."
      : `Window ${win.oldest_started_at ?? "unknown"} to ${win.newest_started_at ?? "unknown"}, ` +
        `${win.span_hours} hours, ids ${win.oldest_id ?? "none"} to ${win.newest_id ?? "none"}.`;

  const caveats: string[] = [];
  const withoutId = nonNegative(win.rows_without_id) ?? 0;
  if (withoutId > 0) {
    caveats.push(
      `${withoutId} of the ${win.executions_read} executions read carried no usable id. They widen ` +
        `the window shown above and take no part in the rate or the burn, which are measured over ` +
        `the ${win.ids_read} that did.`,
    );
  }
  const withoutMoment = nonNegative(win.rows_without_started_at) ?? 0;
  if (withoutMoment > 0) {
    caveats.push(
      `${withoutMoment} carried no readable startedAt, so they are outside the span the rate is measured over.`,
    );
  }
  if (win.truncated) {
    caveats.push("The window is cut off at the row limit, so older runs are outside it.");
  }
  const notSaved = win.not_saved_in_span;
  if (typeof notSaved === "number" && Number.isFinite(notSaved) && notSaved > 0) {
    // A CAUSE THIS READ CANNOT DISTINGUISH IS NOT ASSERTED.
    //
    // This sentence used to end "which is what the success data setting does
    // rather than a fault". Nothing in an executions read can tell that setting
    // apart from n8n's own age pruning (EXECUTIONS_DATA_MAX_AGE, on by default),
    // from executions deleted by hand, or from an id sequence shared with
    // something else. The service docstring hedged; the sentence a reader saw
    // did not, and a reader who trusts it stops looking for the fault.
    const coverage = finite(win.span_coverage);
    caveats.push(
      `${notSaved} of the ${win.ids_in_span ?? "unknown"} ids in the span have no saved row` +
        (coverage === null ? "" : `, so this window accounts for ${Math.round(coverage * 100)}% of it`) +
        ". On this estate a success data setting, n8n's own age pruning, a deleted execution and a " +
        "shared id sequence all produce exactly this, and an executions read cannot tell them apart.",
    );
  }
  // The full 40 word id order note is NOT repeated here. It is rendered once,
  // by readInstanceNotes, which is the one place an instance's caveats are
  // collected and deduped. Putting it under the window as well as under the rate
  // and again in the findings block meant a two instance panel carried the same
  // paragraph six times and the red findings block stopped reading as findings.
  return { headline, caveats };
}

/* ------------------------------------------------------------------ */
/* The rate, gated the same way every other number is                  */
/* ------------------------------------------------------------------ */

export type RateView = {
  kind: "measured" | "unavailable";
  sentence: string;
  caveats: string[];
};

/**
 * The rate sentence, and the reason there is none.
 *
 * This exists because the panel rendered the rate itself:
 * `rate.basis === "id_delta" && rate.per_day !== null` is a PRESENCE check, and
 * `per_day` then went straight into the sentence. `per_day` as NaN, as Infinity
 * or as the string "one hundred and twenty" would each have rendered
 * "NaN executions a day", and `span_hours` was never gated at all. That is the
 * same defect the projected date was rewritten for in cycle one, still live one
 * function along, and the file header's fourth law claimed otherwise.
 *
 * Unreachable from the current route, which gates the rate before it reports
 * one. That is an argument for gating here, not against it: the route's gate is
 * a different file's promise, and this reader is the only thing between a
 * payload and a sentence.
 */
export function readRate(rate: Rate | null, win: Window | null): RateView {
  const caveats: string[] = [];
  if (!rate) {
    return {
      kind: "unavailable",
      sentence: "No rate was reported for this instance, so none is shown.",
      caveats,
    };
  }
  if (rate.basis !== "id_delta") {
    return {
      kind: "unavailable",
      sentence: `No rate could be measured: ${rate.reason || "the window carried nothing to measure"}.`,
      caveats,
    };
  }
  const perDay = positive(rate.per_day);
  const spanHours = nonNegative(rate.span_hours);
  const spanSeconds = positive(rate.span_seconds);
  const inSpan = positive(rate.executions_in_span);
  if (perDay === null || spanHours === null || spanSeconds === null || inSpan === null) {
    const rejected: string[] = [];
    if (perDay === null) rejected.push(`a rate of ${describe(rate.per_day)} a day`);
    if (spanHours === null) rejected.push(`a span of ${describe(rate.span_hours)} hours`);
    if (spanSeconds === null) {
      rejected.push(`an exact span of ${describe(rate.span_seconds)} seconds`);
    }
    if (inSpan === null) rejected.push(`an id delta of ${describe(rate.executions_in_span)}`);
    return {
      kind: "unavailable",
      sentence:
        `A rate arrived carrying ${rejected.join(" and ")}, which is not a number this panel will ` +
        "state a rate from, so none is shown.",
      caveats,
    };
  }

  const outside = nonNegative(rate.rows_outside_the_rate) ?? 0;
  if (outside > 0) {
    caveats.push(
      `${outside} executions in the window took no part in that rate, because they carried no ` +
        "usable id or no readable startedAt.",
    );
  }
  // The exact span, in words, when it is short enough for the rate to be an
  // extrapolation rather than a measurement. Under an hour a single execution
  // moves the day figure by more than a whole day's worth of work.
  if (spanSeconds < 3600) {
    caveats.push(
      `That rate is measured over ${spanSeconds} seconds of wall clock. A window that short says ` +
        "almost nothing about a day, and one extra execution inside it moves the figure by " +
        `${Math.round(86400 / spanSeconds)} a day.`,
    );
  }
  const fromId = rate.from_id;
  const toId = rate.to_id;
  const fromMoment = instant(rate.from_moment);
  const toMoment = instant(rate.to_moment);
  if (
    typeof fromId === "number" &&
    typeof toId === "number" &&
    fromMoment !== null &&
    toMoment !== null
  ) {
    caveats.push(
      `Measured between execution ${fromId} at ${formatMoment(fromMoment)} and execution ${toId} ` +
        `at ${formatMoment(toMoment)}, which are the two rows carrying both an id and a clock.`,
    );
  }
  const dated = win ? nonNegative(win.dated_ids_read) : null;
  if (dated !== null && win && dated < win.executions_read) {
    caveats.push(
      `${dated} of the ${win.executions_read} executions read carried both, so the rate is measured ` +
        "over those and the window shown above is wider than it.",
    );
  }
  return {
    kind: "measured",
    sentence: `${perDay} executions a day, from ${inSpan} ids across ${spanHours} hours.`,
    caveats,
  };
}

/* ------------------------------------------------------------------ */
/* One instance's caveat block, collected once and deduped            */
/* ------------------------------------------------------------------ */

/**
 * Every line an instance's card has to say, in order, with no line said twice.
 *
 * The 40 word `id_order_note` was rendered three times per instance: under the
 * window, as the rate's refusal reason, and again in the panel level findings
 * block. Six copies on a two instance panel, and the findings block it was
 * diluting is the one an operator scans first.
 *
 * The route now emits a SHORT form for the places that must say it and keeps the
 * full note on the window. This collects the card's lines and drops any exact
 * duplicate, so the full note lands once and a future reader that repeats a line
 * cannot put it on the screen twice.
 */
export function readInstanceNotes(instance: Instance): string[] {
  const lines: string[] = [];
  const win = instance.window;
  if (win) {
    lines.push(...readWindow(win).caveats);
    // The full note, once, here. The findings block carries the short form.
    if (win.id_order_matches_time === false && win.id_order_note) {
      lines.push(win.id_order_note);
    }
  }
  lines.push(...readRate(instance.rate, win).caveats);
  const seen = new Set<string>();
  const deduped: string[] = [];
  for (const line of lines) {
    const key = line.trim();
    if (!key || seen.has(key)) continue;
    seen.add(key);
    deduped.push(line);
  }
  return deduped;
}

/* ------------------------------------------------------------------ */
/* The cap, and the burn against it                                    */
/* ------------------------------------------------------------------ */

export type CapView =
  | { kind: "none"; sentence: string; resetsAt: string | null }
  | { kind: "unusable"; sentence: string; resetsAt: string | null }
  | { kind: "stated"; sentence: string; resetsAt: string | null }
  | { kind: "orphan-reset"; sentence: string; resetsAt: string | null }
  | {
      /**
       * THE BURN AND ITS BASIS, AS ONE INDIVISIBLE BLOCK.
       *
       * `lines[0]` states the burn and every line after it is the basis and the
       * assumptions. There is NO field on this view holding the spend, the
       * remaining count, the ceiling or the fraction on its own, and that is
       * the point.
       *
       * The projected exhaustion date was cut from this surface on 2026-09-10,
       * and the law that guarded it was not: a bare burn figure with no basis
       * is the same defect the bare wall was, wearing different clothes. So the
       * law is now "no DERIVED VALUE reaches the screen without its basis", and
       * the burn is a derived value. It is an id gap added to a number a human
       * read off a usage page, against a ceiling nothing here measured.
       *
       * `barPercent` and `tone` are here because a bar has to be drawn with
       * something, and the panel is checked for drawing the bar only inside the
       * same block as these lines.
       */
      kind: "measured";
      lines: string[];
      barPercent: number;
      tone: Tone;
      resetsAt: string | null;
    }
  | { kind: "inconsistent"; sentence: string; resetsAt: string | null };

/**
 * What may be drawn for the cap. `none` is the answer for a self hosted
 * instance and there is no branch here that invents a number for it.
 *
 * Four things it refuses that presence checking alone let through, each one
 * reproduced against the previous version:
 *
 * * a cap of 0 rendered "1088 of 0 left".
 * * a cap of -100 drew a 100 percent red bar reading "-110 left".
 * * a negative remaining count beside a positive cap and a positive spend
 *   rendered as though the three agreed. They do not add up, and numbers that
 *   disagree with each other are not drawn at all.
 * * a cycle reset the route could not read as a date was printed verbatim as
 *   though it were a cycle boundary. `reset_readable` is false for those and
 *   `resetsAt` is null, so the panel draws nothing and the repair is in
 *   `problems`.
 *
 * `barPercent` exists so the panel cannot compute a width from a fraction this
 * function has not clamped.
 */
export function readCap(cap: Cap | null): CapView {
  // A configured reset that is not a date is not shown. It is still reported,
  // in `problems`, as the configuration error it is. This gate used to live
  // inside the projection's reset note, which is exactly the kind of guard that
  // would have been lost with the thing it sat under.
  const resetsAt =
    cap &&
    typeof cap.resets_at === "string" &&
    cap.resets_at.trim() &&
    cap.reset_readable !== false
      ? cap.resets_at
      : null;

  if (!cap || cap.state === "not_stated" || cap.cap === null || cap.cap === undefined) {
    // A RESET STATED FOR A CAP NOBODY STATED gets one sentence, not two.
    //
    // With RESETS_AT set and no cap the panel drew "No cap is configured for this
    // instance" and then, in the very next paragraph, "The plan cycle is stated
    // by configuration to reset 2026-10-01". A panel that contradicts itself in
    // two adjacent sentences is worse than one that says nothing, and this is a
    // configuration error rather than a caveat: a cycle with no ceiling states
    // nothing.
    const orphan = cap && typeof cap.orphan_reset === "string" ? cap.orphan_reset.trim() : "";
    if (orphan) {
      return {
        kind: "orphan-reset",
        // Deliberately null: the panel must not go on to draw the generic reset
        // paragraph beside this one, which is the whole defect.
        resetsAt: null,
        sentence:
          "No plan cap is configured for this instance, so no burn is shown. " + orphan,
      };
    }
    return {
      kind: "none",
      resetsAt,
      sentence:
        cap?.note ||
        "No plan cap is configured for this instance, so none is shown. A self hosted instance has none.",
    };
  }

  const ceiling = positive(cap.cap);
  if (ceiling === null) {
    return {
      kind: "unusable",
      resetsAt,
      sentence:
        `The stated cap is ${describe(cap.cap)}, which is not a ceiling. No spend and no bar are ` +
        "drawn against it, and the configuration is what needs the repair.",
    };
  }

  if (cap.state === "inconsistent") {
    return {
      kind: "inconsistent",
      resetsAt,
      sentence: cap.reason || "The configured anchor does not match this instance.",
    };
  }

  const spent = nonNegative(cap.spent_estimate);
  const remaining = finite(cap.remaining_estimate);
  if (cap.state === "stated" || spent === null || remaining === null) {
    const rejected: string[] = [];
    if (cap.state !== "stated" && cap.spent_estimate !== null && spent === null) {
      rejected.push(`a spend of ${describe(cap.spent_estimate)}`);
    }
    if (cap.state !== "stated" && cap.remaining_estimate !== null && remaining === null) {
      rejected.push(`a remaining count of ${describe(cap.remaining_estimate)}`);
    }
    return {
      kind: "stated",
      resetsAt,
      sentence: rejected.length
        ? `The cap is stated by configuration. ${rejected.join(" and ")} arrived, which is not a ` +
          "number this panel will draw a burn from, so none is drawn."
        : cap.reason ||
          "The cap is stated by configuration. The spend against it has no source, so no burn is drawn.",
    };
  }

  if (spent + remaining !== ceiling) {
    return {
      kind: "unusable",
      resetsAt,
      sentence:
        `The cap block does not add up: an estimated ${spent} spent plus ${remaining} left is not ` +
        `the stated ${ceiling}. Nothing is drawn from three numbers that disagree with each other.`,
    };
  }

  // THE FRACTION IS CROSS CHECKED, NOT TRUSTED, and this is the one number in
  // the set that was not. The block immediately above refuses when spent plus
  // remaining does not equal the ceiling, so the reader's fourth law ("the set
  // of them is checked for adding up") already held for three of the four
  // numbers. used_fraction drove BOTH the bar width and the tone off nothing.
  //
  // Measured by an adversary on 2026-09-10: a cap of 2500 with spent 1359 and
  // remaining 1141 but a wire fraction of 0.01 rendered "Estimated 1359 of 2500
  // spent, 1141 left." beside a bar drawn at 1 percent. The words said 54 and
  // the bar, which is the most glanceable thing on the tier, said 1. The
  // converse would raise a WARN tone off a number nothing measured.
  //
  // The shipped service always emits round(min(1, max(0, spent / cap)), 4), so
  // there is no divergence path from it today. This refuses one anyway, because
  // a fraction that disagrees with the spend it claims to summarise is a fact
  // about a payload we did not write.
  const stated = cap.used_fraction;
  const computed = Math.min(1, Math.max(0, spent / ceiling));
  const statedIsUsable =
    typeof stated === "number" && Number.isFinite(stated) && stated >= 0 && stated <= 1;
  // One percentage point of tolerance, which is wider than the service's own
  // four decimal rounding and narrower than anything a reader could see.
  const statedAgrees = statedIsUsable && Math.abs((stated as number) - computed) <= 0.01;
  const used = statedAgrees ? (stated as number) : computed;

  // THE BURN AND EVERYTHING IT RESTS ON, IN ONE ARRAY. The headline is first and
  // nothing after it is optional decoration: the ceiling is stated rather than
  // measured, the spend is an id gap forward from a human's reading, and the id
  // that gap was carried to is named so a reader can check it against the window
  // above rather than believe it.
  const lines: string[] = [
    `Estimated ${spent} of ${ceiling} spent, ${remaining} left.`,
    "The ceiling is stated by configuration and is not measured by this route. The spend against " +
      "it is estimated from the execution id gap, never counted.",
  ];
  const anchor = cap.anchor;
  if (anchor) {
    lines.push(
      `Carried forward from ${anchor.spent} spent at execution id ${anchor.id}` +
        (anchor.at ? `, read ${formatMoment(anchor.at)}.` : ", with no date recorded for the reading."),
    );
  }
  const countedFromId = cap.counted_from_id;
  const countedFromMoment = instant(cap.counted_from_moment);
  if (typeof countedFromId === "number" && Number.isFinite(countedFromId)) {
    lines.push(
      `Carried forward to execution id ${countedFromId}` +
        (countedFromMoment === null
          ? ", which carried no readable startedAt of its own."
          : `, which started ${formatMoment(countedFromMoment)}.`),
    );
  }
  if (remaining <= 0) {
    lines.push(
      "The estimated spend is at or past the stated cap. The provider's usage page is the truth " +
        "on whether the plan has actually stopped.",
    );
  }
  lines.push(...(cap.assumptions || []));

  return {
    kind: "measured",
    lines,
    barPercent: Math.max(0, Math.min(100, Math.round(used * 100))),
    resetsAt,
    // 0.8 is where the cost panel already turns, so the two tiers agree.
    tone: remaining <= 0 ? "bad" : used >= 0.8 ? "warn" : "neutral",
  };
}

/* ------------------------------------------------------------------ */
/* Provenance: the fields that were carried and rendered nowhere        */
/* ------------------------------------------------------------------ */

/**
 * What the read actually was, in words, from the payload fields nothing rendered.
 *
 * F8 was "a field is read, carried across the wire, and rendered nowhere". Cycle
 * one fixed `resets_at` and left `Rate.assumptions` and `Instance.status_counts`
 * in exactly that state; a type aware sweep of every payload field then found
 * more. Rather than fix them one at a time again, every payload field either
 * reaches a reader or is not declared, and
 * `every field on the payload types is read somewhere` in
 * scripts/n8n-telemetry-check.ts fails the build when a new one is not.
 *
 * These are the diagnostic lines. They are the answer to "where did this number
 * come from", which is the question a panel that projects a wall has to be able
 * to answer.
 */
export function readProvenance(payload: TelemetryPayload, instance: Instance): string[] {
  const lines: string[] = [];
  const win = instance.window;
  lines.push(
    `${payload.read_only ? "Read only" : "NOT read only, which this surface does not support"}. ` +
      `${payload.reachable} of ${payload.configured} configured instances answered, newest ` +
      `${payload.limit} per instance, at ${formatMoment(payload.read_at)}.`,
  );
  if (instance.status_code !== null) {
    lines.push(`${instance.host || instance.configured_host} answered HTTP ${instance.status_code}.`);
  }
  if (win) {
    const dated = nonNegative(win.dated_ids_read);
    lines.push(
      `${win.executions_read} rows read, ${win.ids_read} distinct usable ids, ` +
        `${dated ?? "unknown"} carrying both an id and a clock.`,
    );
    if (win.newest_id !== null && win.newest_id_started_at) {
      lines.push(
        `Newest usable id ${win.newest_id} started ${formatMoment(win.newest_id_started_at)}` +
          (win.oldest_id !== null && win.oldest_id_started_at
            ? `; oldest ${win.oldest_id} started ${formatMoment(win.oldest_id_started_at)}.`
            : "."),
      );
    }
    if (win.ids_in_span !== null) {
      lines.push(
        `${win.ids_in_span} ids lie in that span and ${win.ids_read} of them have a saved row.`,
      );
    }
    if (win.id_order_matches_time === true) {
      lines.push(
        `Id order and startedAt order agree across the window, with ${win.id_order_inversions} ` +
          "inversions, so the id gap is usable as a count here.",
      );
    } else if (win.id_order_matches_time === false) {
      lines.push(`${win.id_order_inversions} inversions between id order and startedAt order.`);
    } else {
      lines.push(win.id_order_note);
    }
    const exact = finite(win.rate_span_seconds);
    const shown = finite(win.rate_span_hours);
    if (
      win.rate_from_id !== null &&
      win.rate_to_id !== null &&
      win.rate_from_moment &&
      win.rate_to_moment
    ) {
      lines.push(
        `The rate window runs from id ${win.rate_from_id} at ${formatMoment(win.rate_from_moment)} to ` +
          `id ${win.rate_to_id} at ${formatMoment(win.rate_to_moment)}` +
          (exact === null ? "." : `, exactly ${exact} seconds`) +
          // Both forms, and which is which. The rounded one used to be the
          // denominator as well as the label, so a four second window was
          // overstated by 11 percent and a one second one was refused outright.
          (shown === null
            ? "."
            : ` (shown as ${shown} hours; the exact seconds are what the rate divides by).`),
      );
    }
  }
  const counts = instance.status_counts;
  if (counts) {
    const entries = Object.keys(counts)
      .sort()
      .map((status) => `${status} ${counts[status]}`);
    lines.push(
      entries.length > 0
        ? `Raw statuses as the instance reported them: ${entries.join(", ")}. These are the strings ` +
          "themselves, so a status this panel does not bucket is still legible here."
        : "The instance reported no status string on any row read.",
    );
  }
  const spentBasis = instance.cap?.spent_basis;
  if (typeof spentBasis === "string" && spentBasis.trim()) {
    lines.push(`The spend against the cap is derived by ${spentBasis.replace(/_/g, " ")}.`);
  }
  // Where the cap number itself came from, in the route's own words. It is never
  // measured here and the label says so on every payload that carries one.
  const capSource = instance.cap?.source;
  if (typeof capSource === "string" && capSource.trim()) {
    lines.push(`The cap ceiling is ${capSource.replace(/_/g, " ")}, not measured by this route.`);
  }
  // The anchor, which is the human's reading off the provider's usage page and
  // therefore the one number on this card with a person behind it.
  const anchor = instance.cap?.anchor;
  if (anchor) {
    lines.push(
      `The anchor is ${anchor.spent} spent at execution id ${anchor.id}` +
        (anchor.at ? `, read ${formatMoment(anchor.at)}` : ", with no date recorded for the reading") +
        `, ${anchor.source.replace(/_/g, " ")}. Everything since is the id gap forward from it.`,
    );
  }
  // The cap block's own record of the moment it compared against, checked
  // against the payload's. Two different instants here would mean the cycle
  // reset was judged against a clock the reader is not being shown, which is the
  // NF3 class arriving by a different door. The check used to sit on the
  // projection's `read_at`; the projection is gone and the class is not, so it
  // moved down onto the clock that survives rather than leaving with it.
  const capReadAt = instance.cap?.read_at;
  if (typeof capReadAt === "string" && capReadAt.trim()) {
    lines.push(
      capReadAt === payload.read_at
        ? `Every date on this cap block was compared with ${formatMoment(capReadAt)}, the same read ` +
          "moment as this payload."
        : `WARNING: this cap block was judged against ${formatMoment(capReadAt)} while this payload ` +
          `reports ${formatMoment(payload.read_at)}. Those are different clocks and the cycle reset ` +
          "above rests on the first of them.",
    );
  }
  if (instance.cap?.reset_readable === false) {
    lines.push(
      "The configured cycle reset could not be read as a date, so it is not shown at all.",
    );
  }
  if (instance.cap?.reset_in_the_past === true) {
    lines.push("The stated cycle reset is already behind this read.");
  }
  return lines;
}

/**
 * The assumptions this card must show that are not already inside the wall block.
 *
 * `Rate.assumptions` had exactly one occurrence in the whole web layer: its own
 * type declaration. The route ships two of them on every measured rate, and the
 * panel rendered assumptions ONLY inside `projection.kind === "date"`, which is
 * unreachable with no cap. So on a self hosted instance a two hour window was
 * extrapolated to a flat figure a day and WINDOW_ASSUMPTION, which says exactly
 * why that figure is not a day's work, appeared nowhere on the page.
 *
 * The subtraction is done here rather than assumed by the panel. A measured burn
 * already carries its own assumptions inside `lines`, and rendering the rate's
 * beside them would put the same paragraph on the card twice, which is the defect
 * one row up in this file. It used to be subtracted against the projected wall's
 * lines; the burn block is what carries assumptions now, so it is subtracted
 * against that instead.
 *
 * `readAt` is gone from the signature. It was here only to hand the projection
 * the moment to judge a wall against, and there is no wall.
 */
export function readAssumptions(instance: Instance): string[] {
  const capView = readCap(instance.cap);
  const already = new Set(capView.kind === "measured" ? capView.lines.map((l) => l.trim()) : []);
  const out: string[] = [];
  const seen = new Set<string>();
  for (const line of instance.rate?.assumptions || []) {
    const key = line.trim();
    if (!key || already.has(key) || seen.has(key)) continue;
    seen.add(key);
    out.push(line);
  }
  return out;
}

/* ------------------------------------------------------------------ */
/* small formatters                                                    */
/* ------------------------------------------------------------------ */

export function formatDuration(ms: number | null): string {
  if (ms === null || !Number.isFinite(ms) || ms < 0) return "no duration";
  if (ms < 1000) return `${Math.round(ms)}ms`;
  if (ms < 60_000) return `${(ms / 1000).toFixed(1)}s`;
  const minutes = Math.floor(ms / 60_000);
  const seconds = Math.round((ms % 60_000) / 1000);
  return `${minutes}m ${seconds}s`;
}

export function formatMoment(value: string | null): string {
  if (!value) return "no timestamp";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toISOString().replace("T", " ").replace(".000Z", "Z").replace("Z", " UTC");
}

export function statusTone(status: string | null): Tone {
  if (!status) return "neutral";
  if (status === "error" || status === "crashed") return "bad";
  if (status === "success") return "good";
  if (status === "canceled" || status === "cancelled") return "warn";
  // MEASURED: "unknown" is a status the instance itself reports, and it means
  // the instance does not know. It is not a pass.
  return "neutral";
}

/**
 * What a row is called, and whether that is a name or an id.
 *
 * MEASURED 2026-09-10: the executions API returns no workflow name, only
 * `workflowId`. The panel promised a name and would have rendered a blank, so
 * the label falls back to the id and this reader says which one a viewer is
 * looking at rather than letting an id pass as a name.
 */
export function readRowLabel(row: ExecutionRow): { label: string; isName: boolean; suffix: string } {
  if (row.workflow_label_kind === "name" && row.workflow_label) {
    return { label: row.workflow_label, isName: true, suffix: "" };
  }
  if (row.workflow_label && row.workflow_label_kind === "id") {
    return { label: row.workflow_label, isName: false, suffix: "id, not a name" };
  }
  if (row.workflow_name) return { label: row.workflow_name, isName: true, suffix: "" };
  if (row.workflow_id) {
    return { label: `workflow id ${row.workflow_id}`, isName: false, suffix: "id, not a name" };
  }
  return { label: "no workflow identified", isName: false, suffix: "" };
}

/**
 * The rest of what a row says, in words: its mode, and whether it finished.
 *
 * `mode` and `stopped_at` were both declared on `ExecutionRow` and read by
 * nothing. `mode` matters for one measured reason: n8n uses `"error"` as a MODE,
 * naming an error handler workflow, and it is NOT a status. A row reading
 * `mode: "error"` beside `status: "success"` is a successful run of an error
 * handler, and a reader shown only the mode string would call it a failure.
 * `stopped_at` is how a reader tells a run still going from one whose duration
 * simply was not reported.
 */
export function readRowDetail(row: ExecutionRow): { mode: string; finished: string } {
  const mode =
    typeof row.mode === "string" && row.mode.trim()
      ? row.mode === "error"
        ? "mode error (an error handler workflow, not a failed run)"
        : `mode ${row.mode}`
      : "mode unreported";
  const finished = row.stopped_at
    ? `finished ${formatMoment(row.stopped_at)}`
    : row.started_at
      ? "no stoppedAt, so this run had not finished when the window was read"
      : "no clock on this row at all";
  return { mode, finished };
}

/**
 * Where this instance's configuration lives, by variable NAME, never value.
 *
 * `Instance.variables` and the `url`/`key` names inside it were carried and
 * rendered nowhere, which made the repair for an unconfigured or half configured
 * instance a thing a reader had to already know.
 */
export function readVariables(instance: Instance): string {
  return (
    `Configured by ${instance.variables.url} and ${instance.variables.key}` +
    `, with any plan cap by ${instance.variables.cap}. Values are never returned by the route.`
  );
}

/**
 * Order for rendering: primary first, then secondary, then anything a later
 * route adds. Side by side during a cutover only helps if the columns hold
 * still between refreshes.
 */
export function orderInstances(instances: Instance[]): Instance[] {
  const rank = (role: string) => (role === "primary" ? 0 : role === "secondary" ? 1 : 2);
  return [...instances].sort((a, b) => rank(a.role) - rank(b.role) || a.role.localeCompare(b.role));
}
