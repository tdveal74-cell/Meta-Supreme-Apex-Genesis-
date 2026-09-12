"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";
import {
  formatDuration,
  formatMoment,
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
  type Cap,
  type Instance,
  type TelemetryPayload,
  type Tone,
} from "@/components/control/n8n-telemetry";

/**
 * Tier 3, the execution side.
 *
 * This panel said, for as long as it was true, that no route in this repository
 * read the n8n instance and that a chart here would be invented rather than
 * measured. `GET /n8n/executions` is that route now, so the placeholder is
 * gone and the numbers below come from it.
 *
 * What is still not built, and is therefore still not drawn: the retry and
 * queue viewer, and version sync against GitHub. Retries are not drawn for a
 * second reason as well. The route behind this panel cannot trigger, retry,
 * delete or resume anything, by construction, so a retry control here would
 * have nothing to call.
 *
 * WHAT THIS PANEL NO LONGER DRAWS AT ALL. The projected exhaustion date was
 * cut on 2026-09-10 on Tee's ruling. It was the least valuable figure here and
 * the most expensive one to be right about, and the two things an operator
 * actually asks of this tier, what ran and what failed, and how much of the cap
 * is burned, are both still answered below. Nothing here projects forward from
 * the read: every date on this card is observed from an execution row or stated
 * by configuration.
 *
 * Five things this panel refuses to do, each one a way the old placeholder was
 * more honest than a filled in version would have been:
 *
 * 1. It never shows a burn figure on its own. The spend, the remaining count
 *    and the bar come from `readCap`, which returns them only together with the
 *    lines that explain them, and withholds them entirely when the numbers are
 *    thin, mistyped, or disagree with each other.
 * 2. It never shows a cap for an instance that has none. A self hosted target
 *    has no plan cap, and the space where the burn bar would be says so.
 * 3. It never merges the two instances. During a cutover the question is
 *    whether the target is doing what the source is doing yet, and an average
 *    of the two answers nothing.
 * 4. It never shows a window wider than the numbers under it. The rows that
 *    carried no usable id widen the window a reader sees and take no part in
 *    the rate, so `readWindow` says how many, every time there are any.
 * 5. It never draws a burn out of an id gap the window itself has called
 *    unusable. The route refuses the spend in that case and this panel prints
 *    the refusal where the bar would have been.
 */

type Load =
  | { state: "loading" }
  | { state: "ready"; payload: TelemetryPayload }
  | { state: "signed-out" }
  | { state: "error"; detail: string };

// The neutral dot was `bg-white/30`, which computes to 2.55:1 against this
// page's #04070d ground and is below the WCAG 3:1 floor for a non-text
// indicator. It is not a decoration: it is the dot for NOTHING SAVED, STATUS
// UNREPORTED, STATUS UNRECOGNISED, WINDOW CUT OFF, SPAN NOT FULLY SAVED and NOT
// CONFIGURED, so the faintest mark on the card was the one carrying every
// degraded state. `bg-white/50` computes to 5.31:1. `control-check.ts` bans only
// `text-` opacities so a `bg-` one passed it; the contrast is computed from the
// class name and checked in scripts/n8n-telemetry-check.ts instead, which is the
// file this piece owns.
const TONE_DOT: Record<Tone, string> = {
  good: "bg-cyan-400 shadow-[0_0_10px_rgba(34,211,238,.7)]",
  warn: "bg-amber-300",
  bad: "bg-red-400",
  neutral: "bg-white/50",
};

const TONE_TEXT: Record<Tone, string> = {
  good: "text-cyan-200",
  warn: "text-amber-200",
  bad: "text-red-300",
  neutral: "text-white/60",
};

function integer(value: number): string {
  return new Intl.NumberFormat("en-US").format(Math.round(value));
}

export function ExecutionHubPanel() {
  const [load, setLoad] = useState<Load>({ state: "loading" });

  const read = useCallback(async () => {
    const token = readDevonToken();
    if (!token) {
      setLoad({ state: "signed-out" });
      return;
    }
    setLoad({ state: "loading" });
    try {
      const response = await fetch(`${API_BASE}/n8n/executions`, {
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setLoad({ state: "error", detail: `the executions route answered ${response.status}` });
        return;
      }
      const body: unknown = await response.json();
      if (!isTelemetryPayload(body)) {
        setLoad({ state: "error", detail: "the route answered in a shape this panel cannot read" });
        return;
      }
      setLoad({ state: "ready", payload: body });
    } catch (error) {
      setLoad({
        state: "error",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }, []);

  useEffect(() => {
    void read();
  }, [read]);

  if (load.state === "loading") {
    return <p className="text-xs text-white/50">Reading the configured n8n instances.</p>;
  }

  if (load.state === "signed-out") {
    return (
      <p className="text-xs leading-relaxed text-white/50">
        No session token in this browser, so the executions route cannot be called. The panel
        will not show a cached or example instance in its place.
      </p>
    );
  }

  if (load.state === "error") {
    return (
      <div className="space-y-2">
        <p className="text-xs text-red-300">Execution telemetry could not be read: {load.detail}.</p>
        <p className="text-xs leading-relaxed text-white/50">
          This is a failed read of the DEVON API, which is not the same as an n8n instance being
          down. Nothing below is being shown as a measurement.
        </p>
        <Retry onClick={() => void read()} />
      </div>
    );
  }

  const { payload } = load;
  // EVERY instance, including the unconfigured ones.
  //
  // This filtered them out and fell back to the whole list only when the filter
  // emptied it, so with the primary configured and the secondary not, the
  // secondary card was DROPPED and nothing on the page named it. The whole NOT
  // CONFIGURED branch was reachable only when every instance was unconfigured.
  // The service docstring calls unconfigured and "answered with nothing saved"
  // the pair most worth keeping apart, and a panel that hides one of them cannot
  // keep them apart at all: during a cutover "the target is not configured" and
  // "the target is quiet" are different answers to the only question being asked.
  const rendered = orderInstances(payload.instances);

  return (
    <div className="space-y-4">
      <div className="flex flex-wrap items-center justify-between gap-2">
        <p className="text-[11px] uppercase tracking-[0.14em] text-white/50">
          Read only, {formatMoment(payload.read_at)}, newest {payload.limit} per instance
        </p>
        <Retry onClick={() => void read()} />
      </div>

      {payload.findings.length > 0 ? (
        <ul className="space-y-1.5 rounded-xl border border-red-400/30 bg-red-500/10 px-3 py-2.5">
          {payload.findings.map((finding) => (
            <li key={finding} className="text-xs leading-relaxed text-red-200">
              {finding}
            </li>
          ))}
        </ul>
      ) : null}

      <div
        className={`grid gap-3 ${rendered.length > 1 ? "lg:grid-cols-2" : "grid-cols-1"}`}
      >
        {rendered.map((instance) => (
          <InstanceCard key={instance.role} instance={instance} payload={payload} />
        ))}
      </div>

      {/* The route's own statement of what it is, rendered rather than carried. */}
      <p className="text-xs leading-relaxed text-white/50">{payload.note}</p>

      <p className="text-xs leading-relaxed text-white/50">
        The retry and queue viewer and version sync against GitHub are still not built, so they
        are not drawn. This route reads and only reads: it cannot trigger, retry, delete or
        resume an execution, so a retry control here would have nothing to call.
      </p>
    </div>
  );
}

function Retry({ onClick }: { onClick: () => void }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
    >
      Read again
    </button>
  );
}

function InstanceCard({ instance, payload }: { instance: Instance; payload: TelemetryPayload }) {
  const verdict = readInstance(instance);
  // Named `win` rather than `window`: shadowing the DOM global inside a client
  // component is how a later edit reaches for the wrong one.
  const win = instance.window;
  const counts = instance.counts;
  const windowView = readWindow(win);
  // One collected, deduped set of caveat lines for this card. The 40 word id
  // order note used to arrive here three separate ways.
  const notes = readInstanceNotes(instance);

  return (
    <div className="min-w-0 space-y-3 rounded-xl border border-white/10 bg-black/25 px-3 py-3">
      <div className="space-y-1">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50">
            {instance.role}
          </p>
          <span className={`text-[11px] font-semibold uppercase tracking-[0.14em] ${TONE_TEXT[verdict.tone]}`}>
            {verdict.label}
          </span>
        </div>
        {/* The host that answered, never the one configuration hoped for. A
            secondary left pointing at the source is the quietest cutover
            failure there is, so the label is the evidence. */}
        <p className="flex items-center gap-2 break-all text-sm text-white/80">
          <span className={`h-2 w-2 shrink-0 rounded-full ${TONE_DOT[verdict.tone]}`} />
          {instance.host || instance.configured_host || "no host configured"}
        </p>
        {instance.host && instance.configured_host && instance.host !== instance.configured_host ? (
          <p className="text-xs leading-relaxed text-amber-200">
            Configured as {instance.configured_host} and answered by {instance.host}.
          </p>
        ) : null}
        <p className="text-xs leading-relaxed text-white/50">{verdict.sentence}</p>
        {/* Which variables configure this instance, by NAME. The repair for an
            unconfigured or half configured one is otherwise a thing a reader has
            to already know, and the card that most needs it is the one that was
            being dropped from the page altogether. */}
        <p className="text-xs leading-relaxed text-white/50">{readVariables(instance)}</p>
      </div>

      {instance.read_problems && instance.read_problems.length > 0 ? (
        <ul className="space-y-0.5 rounded-lg border border-amber-400/25 bg-amber-400/5 px-2.5 py-2">
          {instance.read_problems.map((problem) => (
            <li key={problem} className="text-xs leading-relaxed text-amber-200">
              {problem}
            </li>
          ))}
        </ul>
      ) : null}

      {counts && win ? (
        <>
          <div className="grid grid-cols-4 gap-2">
            <Figure label="Saved read" value={integer(win.executions_read)} />
            {/* The divergence F1 hid: what the arithmetic actually ran on. */}
            <Figure
              label="Usable ids"
              value={integer(win.ids_read)}
              tone={win.ids_read < win.executions_read ? "warn" : "neutral"}
            />
            <Figure label="Failed" value={integer(counts.failed)} tone={counts.failed > 0 ? "bad" : "neutral"} />
            <Figure
              label="Not saved"
              value={win.not_saved_in_span === null ? "unknown" : integer(win.not_saved_in_span)}
              tone={
                win.not_saved_in_span === null || win.not_saved_in_span > 0 ? "warn" : "neutral"
              }
            />
          </div>

          <p className="text-xs leading-relaxed text-white/50">{windowView.headline}</p>
          {/* One block, deduped, rather than the window's caveats here and the
              rate's further down with the same paragraph in both. */}
          {notes.length > 0 ? (
            <ul className="space-y-0.5">
              {notes.map((line) => (
                <li key={line} className="text-xs leading-relaxed text-white/50">
                  {line}
                </li>
              ))}
            </ul>
          ) : null}

          {counts.status_unreported > 0 ? (
            <p className="text-xs leading-relaxed text-white/50">
              {integer(counts.status_unreported)} rows carried no status. They are counted as
              neither passed nor failed rather than guessed at.
            </p>
          ) : null}

          <RateAndCap instance={instance} />
          <Recent instance={instance} />
          <Provenance instance={instance} payload={payload} />
        </>
      ) : null}
    </div>
  );
}

function RateAndCap({ instance }: { instance: Instance }) {
  const cap: Cap | null = instance.cap;
  const capView = readCap(cap);
  const rateView = readRate(instance.rate, instance.window);
  const assumptions = readAssumptions(instance);

  return (
    <div className="space-y-2 border-t border-white/10 pt-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50">
        Burn
      </p>

      {/* The rate sentence comes from readRate, which gates per_day and both
          spans the way readCap gates the numbers under the burn. The panel used
          to check `rate.per_day !== null` and interpolate it, so NaN would have
          rendered "NaN executions a day" and span_hours was never gated at all. */}
      <p className="text-xs leading-relaxed text-white/60">{rateView.sentence}</p>

      {/* THE BURN AND ITS BASIS ARE ONE ARRAY, and this maps it.
          `readCap` no longer has a field holding the spend, the remaining count
          or the fraction on its own, so there is nothing here to render alone:
          the first line states the burn and every line after it qualifies it.
          That is the structural answer to a name allowlist being walked around
          four times. The bar is inside this block deliberately: a bar is the
          fraction drawn as geometry, and a fraction with no basis beside it is
          the same claim the number would have been. */}
      {capView.kind === "measured" ? (
        <div className="space-y-1.5 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-2">
          <div className="h-1.5 w-full overflow-hidden rounded-full bg-white/10">
            <div
              className={`h-full rounded-full ${capView.tone === "bad" ? "bg-red-400" : capView.tone === "warn" ? "bg-amber-300" : "bg-cyan-400"}`}
              style={{ width: `${capView.barPercent}%` }}
            />
          </div>
          <ul className="space-y-0.5">
            {capView.lines.map((line, index) => (
              <li
                key={line}
                className={
                  index === 0
                    ? `text-sm ${TONE_TEXT[capView.tone]}`
                    : "text-xs leading-relaxed text-white/50"
                }
              >
                {line}
              </li>
            ))}
          </ul>
        </div>
      ) : capView.kind === "unusable" || capView.kind === "orphan-reset" ? (
        <p className="text-xs leading-relaxed text-red-300">{capView.sentence}</p>
      ) : (
        <p className="text-xs leading-relaxed text-white/50">{capView.sentence}</p>
      )}

      {/* The stated cycle reset. Read from configuration, and drawn whether or
          not a burn was measured, because a reader judging a burn needs to know
          when the counter goes back to zero. `readCap` returns null here when
          the configured value is not a date at all, so an unreadable one is
          reported in `problems` below rather than printed as a boundary. */}
      {capView.resetsAt ? (
        <p className="text-xs leading-relaxed text-white/50">
          The plan cycle is stated by configuration to reset {capView.resetsAt}. That statement is
          not measured either, and the provider&apos;s usage page stays the truth on it.
        </p>
      ) : null}

      {/* The assumptions under the RATE, which lived only inside the projected
          date block and were therefore unreachable on an instance with no cap: a
          two hour window was extrapolated to a flat figure a day and the
          assumption saying why that is not a day's work appeared nowhere.
          `readAssumptions` subtracts the ones already inside the burn block, so
          they are on the card exactly once whether or not a burn was drawn. */}
      {assumptions.length > 0 ? (
        <ul className="space-y-0.5">
          {assumptions.map((line) => (
            <li key={line} className="text-xs leading-relaxed text-white/50">
              {line}
            </li>
          ))}
        </ul>
      ) : null}

      {cap?.problems.length ? (
        <ul className="space-y-0.5">
          {cap.problems.map((problem) => (
            <li key={problem} className="text-xs leading-relaxed text-red-300">
              {problem}
            </li>
          ))}
        </ul>
      ) : null}
    </div>
  );
}

function Recent({ instance }: { instance: Instance }) {
  if (instance.recent.length === 0) return null;
  return (
    <div className="space-y-1.5 border-t border-white/10 pt-3">
      <p className="text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50">
        Recent executions
      </p>
      <ul className="space-y-1">
        {instance.recent.map((row) => {
          // MEASURED 2026-09-10: the API returns no workflow name, only
          // workflowId. The label falls back to the id and says so, rather
          // than leaving a blank where a name was promised.
          const named = readRowLabel(row);
          // MEASURED: `mode` takes "error" for an error handler workflow and is
          // NOT a status, and a row with no stoppedAt had not finished. Both
          // fields were declared on ExecutionRow and rendered nowhere.
          const detail = readRowDetail(row);
          return (
            <li
              key={`${row.id ?? "no-id"}-${row.started_at ?? ""}`}
              className="flex flex-wrap items-baseline gap-x-2 gap-y-0.5 text-xs"
            >
              <span className={`h-1.5 w-1.5 shrink-0 rounded-full ${TONE_DOT[statusTone(row.status)]}`} />
              <span className="text-white/70">{named.label}</span>
              {named.suffix ? <span className="text-white/50">({named.suffix})</span> : null}
              <span className={TONE_TEXT[statusTone(row.status)]}>{row.status || "no status"}</span>
              <span className="text-white/50">{detail.mode}</span>
              <span className="text-white/50">{formatDuration(row.duration_ms)}</span>
              <span className="text-white/50">{formatMoment(row.started_at)}</span>
              <span className="text-white/50">{detail.finished}</span>
              <span className="text-white/50">#{row.id ?? "no id"}</span>
            </li>
          );
        })}
      </ul>
    </div>
  );
}

/**
 * Where every number on this card came from.
 *
 * The lines here are the payload fields that were carried across the wire and
 * rendered nowhere: the raw status strings, the id span, the exact rate window,
 * the HTTP status, the moment every date was compared against. A panel that
 * projects a wall has to be able to answer "where did this come from", and a
 * field declared in the type and read by nothing is a promise the panel is not
 * keeping. `every field on the payload types is read somewhere` in
 * scripts/n8n-telemetry-check.ts fails the build when a new one appears.
 */
function Provenance({ instance, payload }: { instance: Instance; payload: TelemetryPayload }) {
  const lines = readProvenance(payload, instance);
  if (lines.length === 0) return null;
  return (
    <details className="border-t border-white/10 pt-3">
      <summary className="cursor-pointer text-[11px] font-semibold uppercase tracking-[0.14em] text-white/50">
        Where these numbers came from
      </summary>
      <ul className="mt-1.5 space-y-0.5">
        {lines.map((line) => (
          <li key={line} className="text-xs leading-relaxed text-white/50">
            {line}
          </li>
        ))}
      </ul>
    </details>
  );
}

function Figure({ label, value, tone = "neutral" }: { label: string; value: string; tone?: Tone }) {
  return (
    <div className="min-w-0 rounded-lg border border-white/10 bg-white/[0.03] px-2.5 py-2">
      <p className="text-[11px] uppercase tracking-[0.14em] text-white/50">{label}</p>
      <p className={`mt-0.5 truncate text-sm font-medium ${tone === "neutral" ? "text-white/85" : TONE_TEXT[tone]}`}>
        {value}
      </p>
    </div>
  );
}
