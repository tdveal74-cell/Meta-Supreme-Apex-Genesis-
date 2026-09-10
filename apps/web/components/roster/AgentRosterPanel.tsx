"use client";

import { useCallback, useEffect, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";
import {
  activeClaim,
  countLabel,
  declaredCount,
  describeDetail,
  detailReadForStatus,
  listReadForStatus,
  parseAgentDetail,
  parseRosterPayload,
  readRosterVerdict,
  type DetailRead,
  type RosterRead,
  type RosterRow,
} from "./agent-roster-honesty.ts";

/**
 * The agent roster: the AI Council as the registry actually declares it.
 *
 * WHY THIS PANEL EXISTS
 *
 * app/api/v1/agents.py serves two complete read routes over
 * services/agents/registry.py, and until this panel nothing under apps/web called
 * either. The estate's own front page (apps/web/app/page.tsx:33) types the nine
 * names into a marketing sentence by hand, and CapabilityDock renders the LENGTH
 * of `council.agents` from a different route's tool catalog as "9 agents". So a
 * person could read the number nine and could not read one agent's purpose,
 * mission, capabilities, limitations, declared output shape or evaluation
 * criteria. That is the door: the capability was real, complete and unreachable,
 * and nothing failed.
 *
 * WHAT IT READS
 *
 *   GET /api/v1/agents          the roster. Six fields per agent: slug, name,
 *                               purpose, mission, version, is_active. Filtered
 *                               to active agents by list_active_agents().
 *   GET /api/v1/agents/{slug}   one agent's full definition, on demand. Adds
 *                               capabilities, limitations, output_format and
 *                               evaluation_criteria. NOT filtered by is_active.
 *
 * WHAT IT DOES NOT DO
 *
 * Nothing here writes and nothing here runs. The registry is Python module level
 * code, not a table, so there is no edit for this panel to offer even if one were
 * wanted; and every WRITE or HIGH_IMPACT tool in this estate is human gated, so a
 * roster is not the place to put a shortcut past that. The one interaction is
 * expanding a row, which issues the second GET.
 *
 * THE HONESTY, all of it in agent-roster-honesty.ts and proved in
 * scripts/roster-check.ts
 *
 *  - A failed roster read is drawn as unreadable, never as an estate with no
 *    agents, and a 401 or 403 is a third state again.
 *  - No pre-flight token gate. The routes declare no dependency and answer 200
 *    with no Authorization header (measured 2026-09-10 against a TestClient), so
 *    refusing to read without a token would invent a lock. The token is sent when
 *    the device has one, and a deployment that does gate the read reports as
 *    gated.
 *  - Capability, limitation and criteria counts read "not read" until the detail
 *    route has answered for that slug, because the list route does not send them.
 *    They are never 0 by default.
 *  - The `is_active` badge is only called a measurement on the detail route. On
 *    the list it is the filter, not the agent.
 *  - A 404 from the detail route on a slug the list just returned is reported as
 *    the two routes disagreeing, not as an agent that declares nothing.
 */

export type AgentRosterPanelProps = {
  /**
   * Bearer token to send. When omitted the component reads the same
   * devon-chat-token the rest of the workspace stores on the device, and reads
   * the roster with no Authorization header when there is none, because these two
   * routes do not require one.
   */
  token?: string;
  /** Extra classes on the outer container. */
  className?: string;
};

type RosterState =
  | { state: "loading" }
  | { state: "ok"; rows: RosterRow[]; dropped: number }
  | { state: "unauthorized"; status: number }
  | { state: "failed"; detail: string };

function asRead(roster: RosterState): RosterRead {
  if (roster.state === "ok") {
    return {
      state: "ok",
      count: roster.rows.length,
      dropped: roster.dropped,
      // Counted from the rows themselves rather than assumed to be zero. The
      // list route filters on is_active, so this is 0 in every healthy read,
      // and a non-zero value is a finding about the route rather than a state
      // of the registry.
      contradicted: roster.rows.filter((row) => row.isActive === false).length,
    };
  }
  if (roster.state === "unauthorized") {
    return { state: "unauthorized", status: roster.status };
  }
  if (roster.state === "failed") return { state: "failed", detail: roster.detail };
  return { state: "loading" };
}

function authHeaders(token: string): Record<string, string> {
  return token ? { Authorization: `Bearer ${token}` } : {};
}

const TONE_CLASS: Record<"neutral" | "warn" | "good", string> = {
  good: "border-emerald-400/30 text-emerald-200",
  warn: "border-amber-400/35 text-amber-200",
  neutral: "border-white/15 text-white/70",
};

export function AgentRosterPanel({ token, className }: AgentRosterPanelProps) {
  const [roster, setRoster] = useState<RosterState>({ state: "loading" });
  const [open, setOpen] = useState<string | null>(null);
  const [details, setDetails] = useState<Record<string, DetailRead>>({});

  const load = useCallback(async () => {
    setRoster({ state: "loading" });
    const bearer = token ?? readDevonToken();
    let response: Response;
    try {
      response = await fetch(`${API_BASE}/agents`, {
        cache: "no-store",
        headers: authHeaders(bearer),
      });
    } catch (error) {
      setRoster({
        state: "failed",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
      return;
    }
    if (!response.ok) {
      const mapped = listReadForStatus(response.status, response.statusText);
      setRoster(
        mapped.state === "unauthorized"
          ? { state: "unauthorized", status: mapped.status }
          : { state: "failed", detail: (mapped as { detail: string }).detail },
      );
      return;
    }
    let payload: unknown;
    try {
      payload = await response.json();
    } catch {
      setRoster({
        state: "failed",
        detail: `the roster route answered ${response.status} with a body that was not JSON`,
      });
      return;
    }
    const parsed = parseRosterPayload(payload);
    if (!parsed.wasArray) {
      setRoster({
        state: "failed",
        detail: `the roster route answered ${response.status} with a body that was not a list`,
      });
      return;
    }
    setRoster({ state: "ok", rows: parsed.rows, dropped: parsed.dropped });
  }, [token]);

  useEffect(() => {
    void load();
  }, [load]);

  const loadDetail = useCallback(
    async (slug: string) => {
      setDetails((prior) => ({ ...prior, [slug]: { state: "loading" } }));
      const bearer = token ?? readDevonToken();
      let response: Response;
      try {
        response = await fetch(`${API_BASE}/agents/${encodeURIComponent(slug)}`, {
          cache: "no-store",
          headers: authHeaders(bearer),
        });
      } catch (error) {
        setDetails((prior) => ({
          ...prior,
          [slug]: {
            state: "failed",
            detail: error instanceof Error ? error.message : "the request did not complete",
          },
        }));
        return;
      }
      if (!response.ok) {
        const mapped = detailReadForStatus(response.status, response.statusText);
        setDetails((prior) => ({ ...prior, [slug]: mapped }));
        return;
      }
      let payload: unknown;
      try {
        payload = await response.json();
      } catch {
        setDetails((prior) => ({
          ...prior,
          [slug]: { state: "malformed", detail: "the body was not JSON" },
        }));
        return;
      }
      const detail = parseAgentDetail(payload);
      setDetails((prior) => ({
        ...prior,
        [slug]:
          detail === null
            ? {
                state: "malformed",
                detail: "the body did not carry the ten fields AgentDetail declares",
              }
            : { state: "ok", detail },
      }));
    },
    [token],
  );

  function toggle(slug: string) {
    if (open === slug) {
      setOpen(null);
      return;
    }
    setOpen(slug);
    const known = details[slug];
    // Re-read on a failed or gated attempt, keep a good read.
    if (!known || (known.state !== "ok" && known.state !== "loading")) {
      void loadDetail(slug);
    }
  }

  const verdict = readRosterVerdict(asRead(roster));

  return (
    <div className={`space-y-4 ${className ?? ""}`}>
      <div className={`rounded-xl border bg-black/25 px-3 py-2.5 ${TONE_CLASS[verdict.tone]}`}>
        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.16em]">
          {verdict.label}
        </p>
        <p className="mt-1.5 text-xs leading-relaxed">{verdict.sentence}</p>
      </div>

      {roster.state === "failed" || roster.state === "unauthorized" ? (
        <button
          type="button"
          onClick={() => void load()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Read the roster again
        </button>
      ) : null}

      {roster.state === "ok" && roster.rows.length > 0 ? (
        <ul className="space-y-2">
          {roster.rows.map((row) => {
            const detail = details[row.slug] ?? ({ state: "idle" } as DetailRead);
            const note = describeDetail(detail);
            const expanded = open === row.slug;
            const listClaim = activeClaim("list", row.isActive);
            return (
              <li
                key={row.slug}
                className="overflow-hidden rounded-xl border border-white/10 bg-black/20"
              >
                <button
                  type="button"
                  onClick={() => toggle(row.slug)}
                  aria-expanded={expanded}
                  aria-controls={`roster-detail-${row.slug}`}
                  className="flex w-full flex-col gap-1.5 px-3 py-2.5 text-left transition hover:bg-white/[0.03]"
                >
                  <span className="flex flex-wrap items-baseline gap-x-2 gap-y-1">
                    <span className="text-sm font-semibold text-white/90">{row.name}</span>
                    <span className="font-mono text-[11px] text-white/55">{row.slug}</span>
                    <span className="font-mono text-[11px] tabular-nums text-white/55">
                      v{row.version}
                    </span>
                    <span className="ml-auto font-mono text-[11px] uppercase tracking-[0.12em] text-white/55">
                      {expanded ? "close" : "open"}
                    </span>
                  </span>
                  <span className="text-xs leading-relaxed text-white/70">{row.purpose}</span>
                  <span className="text-xs leading-relaxed text-white/55">{row.mission}</span>
                  <span className="flex flex-wrap gap-1.5 pt-0.5">
                    <Chip
                      label="capabilities"
                      value={countLabel(declaredCount(detail, "capabilities"))}
                    />
                    <Chip
                      label="limitations"
                      value={countLabel(declaredCount(detail, "limitations"))}
                    />
                    <Chip
                      label="criteria"
                      value={countLabel(declaredCount(detail, "evaluationCriteria"))}
                    />
                  </span>
                </button>

                <div
                  id={`roster-detail-${row.slug}`}
                  hidden={!expanded}
                  className="border-t border-white/10 px-3 py-2.5"
                >
                  <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
                    {note.label}
                  </p>
                  <p
                    className={`mt-1 text-xs leading-relaxed ${
                      note.tone === "warn" ? "text-amber-200" : "text-white/60"
                    }`}
                  >
                    {note.sentence}
                  </p>

                  {detail.state !== "ok" && detail.state !== "idle" && detail.state !== "loading" ? (
                    <button
                      type="button"
                      onClick={() => void loadDetail(row.slug)}
                      className="mt-2 rounded-lg border border-white/15 px-2.5 py-1 text-[11px] font-medium text-white/70 transition hover:border-white/25 hover:text-white"
                    >
                      Read {row.slug} again
                    </button>
                  ) : null}

                  {detail.state === "ok" ? (
                    <div className="mt-3 space-y-3">
                      <p className="text-xs leading-relaxed text-white/60">
                        Registry says: {activeClaim("detail", detail.detail.isActive).text}. The
                        row above only says it was {listClaim.text}.
                      </p>
                      <Bullets title="Capabilities" items={detail.detail.capabilities} />
                      <Bullets title="Limitations" items={detail.detail.limitations} />
                      <Bullets
                        title="Evaluation criteria"
                        items={detail.detail.evaluationCriteria}
                      />
                      <div>
                        <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
                          Declared output format
                        </p>
                        {!detail.detail.outputFormatWasObject ? (
                          <p className="mt-1 text-xs leading-relaxed text-amber-200">
                            output_format was absent or was not an object on this read, so no
                            output shape is shown. The field is typed Dict[str, Any], so this is
                            allowed by the contract.
                          </p>
                        ) : detail.detail.outputFormat.length === 0 ? (
                          <p className="mt-1 text-xs leading-relaxed text-white/60">
                            The route sent an empty object. This agent declares no output shape.
                          </p>
                        ) : (
                          <dl className="mt-1 space-y-1">
                            {detail.detail.outputFormat.map((line) => (
                              <div key={line.key} className="flex flex-wrap gap-x-2">
                                <dt className="font-mono text-[11px] text-white/55">
                                  {line.key}
                                </dt>
                                <dd className="min-w-0 flex-1 text-xs leading-relaxed text-white/70">
                                  {line.value}
                                </dd>
                              </div>
                            ))}
                          </dl>
                        )}
                      </div>
                    </div>
                  ) : null}
                </div>
              </li>
            );
          })}
        </ul>
      ) : null}

      {roster.state === "ok" && roster.dropped > 0 ? (
        <p className="text-[11px] leading-relaxed text-amber-200">
          {roster.dropped} of the entries the route returned did not carry the six fields
          AgentSummary declares and are not listed above.
        </p>
      ) : null}

      <p className="text-xs leading-relaxed text-white/55">
        Read only, by construction. The registry is Python module level code in
        services/agents/registry.py rather than a table, so there is nothing on this surface to
        edit and no effect for it to run. Expanding a row issues GET /agents/{"{slug}"}; nothing
        else is sent.
      </p>
    </div>
  );
}

function Chip({ label, value }: { label: string; value: string }) {
  const unread = value === "not read";
  return (
    <span
      className={`rounded-full border px-2 py-0.5 font-mono text-[11px] ${
        unread
          ? "border-white/10 text-white/50"
          : "border-white/15 tabular-nums text-white/70"
      }`}
    >
      {label} {value}
    </span>
  );
}

function Bullets({ title, items }: { title: string; items: string[] }) {
  return (
    <div>
      <p className="font-mono text-[11px] font-semibold uppercase tracking-[0.14em] text-white/60">
        {title}
      </p>
      {items.length === 0 ? (
        <p className="mt-1 text-xs leading-relaxed text-white/60">
          The route sent an empty list, so this agent declares none.
        </p>
      ) : (
        <ul className="mt-1 space-y-0.5">
          {items.map((item) => (
            <li key={item} className="text-xs leading-relaxed text-white/70">
              {item}
            </li>
          ))}
        </ul>
      )}
    </div>
  );
}
