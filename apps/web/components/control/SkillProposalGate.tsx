"use client";

import { useCallback, useEffect, useMemo, useState } from "react";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";

/**
 * The door on the skill proposal gate.
 *
 * WHAT WAS BROKEN. Every agent task that reaches COMPLETED drafts a skill
 * proposal and saves it against the owner (app/services/agent_tasks.py:513,
 * with DEVON_AUTO_SKILL_PROPOSE defaulting ON at app/services/agent_tasks.py:174),
 * and that path is reachable from the chat surface. CLAUDE.md's invariant reads
 * "Skill promotion is human gated". It was gated with no door: the two routes
 * that would let a person see and rule on a proposal,
 * GET /agent-expansion/skill-proposals (app/api/v1/agent_expansion.py:161) and
 * POST /agent-expansion/skill-proposals/{id}/decide
 * (app/api/v1/agent_expansion.py:173), had no caller anywhere in apps/web.
 * Measured on this commit with a grep across apps/web and packages/ui: the only
 * hit for agent-expansion was CapabilityDock.tsx:111 reading /schedules. So
 * proposals accumulated where nobody could read them, and nothing failed.
 *
 * WHY PROMOTE IS ALWAYS SENT EXPLICITLY. SkillDecideBody declares
 * `promote: bool = True` (app/api/v1/agent_expansion.py:35-37). A decide body
 * that omits the key therefore promotes. Approving a draft and activating a
 * skill are two different rulings, so every request from here carries promote
 * as its own value read off the button the human pressed. Nothing here defaults
 * it, and nothing here infers it from approve.
 *
 * WHY THE THREE BUTTONS LOOK THE SAME. A gate where refusing costs more than
 * accepting is not a gate, it is a nudge. Reject sits first and carries the same
 * border, padding and type weight as the two approve buttons, so no styling here
 * makes declining feel like the dangerous choice.
 *
 * WHY THE INSTRUCTIONS ARE NEVER COLLAPSED. The instructions are the thing being
 * approved. A title is not the artifact, so the body is rendered in full with no
 * clamp and no expander to forget to open.
 */

type SkillProposal = {
  proposal_id: string;
  name: string;
  description: string;
  instructions: string;
  source_task_id: string;
  state: string;
  created_at: string;
};

type Load =
  | { state: "loading" }
  | { state: "ready"; proposals: SkillProposal[] }
  | { state: "signed-out" }
  | { state: "error"; detail: string };

/**
 * The two halves of the ruling, kept apart all the way to the request body.
 * approve records the human decision on the draft. promote activates a skill
 * from it. There is no shape here that carries one without the other.
 */
type Decision = { approve: boolean; promote: boolean };

type Outcome =
  | { kind: "sending" }
  | { kind: "failed"; detail: string }
  | { kind: "done"; sentence: string };

const PROPOSED = "proposed";

function whenLabel(iso: string): string {
  const at = new Date(iso);
  if (Number.isNaN(at.getTime())) return iso;
  return at.toLocaleString();
}

export function SkillProposalGate() {
  const [load, setLoad] = useState<Load>({ state: "loading" });
  const [outcomes, setOutcomes] = useState<Record<string, Outcome>>({});
  const [checkedAt, setCheckedAt] = useState<Date | null>(null);

  const read = useCallback(async () => {
    const token = readDevonToken();
    if (!token) {
      setLoad({ state: "signed-out" });
      return;
    }
    setLoad({ state: "loading" });
    try {
      // Read unfiltered rather than with ?state=proposed. One request then
      // answers both questions on the panel: what is waiting on a ruling, and
      // how many rulings have already been made. The route is scoped to the
      // caller, so this is the caller's own queue either way.
      const response = await fetch(`${API_BASE}/agent-expansion/skill-proposals`, {
        cache: "no-store",
        headers: { Authorization: `Bearer ${token}` },
      });
      if (!response.ok) {
        setLoad({
          state: "error",
          detail: `the skill proposal route answered ${response.status}`,
        });
        return;
      }
      const payload = await response.json();
      if (!Array.isArray(payload)) {
        // An unreadable payload is a failed read. Falling through to an empty
        // list here would render "nothing is waiting" over an unknown queue.
        setLoad({ state: "error", detail: "the route did not return a list of proposals" });
        return;
      }
      setLoad({ state: "ready", proposals: payload as SkillProposal[] });
      setCheckedAt(new Date());
    } catch (error) {
      setLoad({
        state: "error",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }, []);

  useEffect(() => {
    void read();
    // Same cadence and the same storage wake as MissionAdvisor, the estate's
    // other human decision surface, so signing in through Talk to DEVON in
    // another tab brings this panel up without a reload.
    const timer = window.setInterval(() => void read(), 30000);
    const onStorage = () => void read();
    window.addEventListener("storage", onStorage);
    return () => {
      window.clearInterval(timer);
      window.removeEventListener("storage", onStorage);
    };
  }, [read]);

  const decide = useCallback(
    async (proposal: SkillProposal, decision: Decision) => {
      const token = readDevonToken();
      if (!token) {
        setOutcomes((current) => ({
          ...current,
          [proposal.proposal_id]: {
            kind: "failed",
            detail: "the session token is no longer in this browser, so nothing was sent",
          },
        }));
        return;
      }
      setOutcomes((current) => ({
        ...current,
        [proposal.proposal_id]: { kind: "sending" },
      }));
      try {
        const response = await fetch(
          `${API_BASE}/agent-expansion/skill-proposals/${encodeURIComponent(proposal.proposal_id)}/decide`,
          {
            method: "POST",
            cache: "no-store",
            headers: {
              "Content-Type": "application/json",
              Authorization: `Bearer ${token}`,
            },
            // Both keys, always. See the promote note at the top of this file:
            // the server defaults promote to true when the key is absent.
            body: JSON.stringify({ approve: decision.approve, promote: decision.promote }),
          },
        );
        if (!response.ok) {
          setOutcomes((current) => ({
            ...current,
            [proposal.proposal_id]: {
              kind: "failed",
              detail:
                response.status === 409
                  ? "this proposal was already decided, so nothing changed"
                  : `the decide route answered ${response.status}`,
            },
          }));
          return;
        }
        const result = await response.json();
        const skillName =
          result && typeof result === "object" && result.skill && typeof result.skill === "object"
            ? String((result.skill as { name?: unknown }).name ?? "")
            : "";
        const sentence = !decision.approve
          ? "Rejected. No skill was created and the draft is closed."
          : skillName
            ? `Approved and activated as the skill ${skillName}.`
            : "Approved. No skill was activated, so DEVON cannot use it yet.";
        setOutcomes((current) => ({
          ...current,
          [proposal.proposal_id]: { kind: "done", sentence },
        }));
        await read();
      } catch (error) {
        setOutcomes((current) => ({
          ...current,
          [proposal.proposal_id]: {
            kind: "failed",
            detail: error instanceof Error ? error.message : "the request did not complete",
          },
        }));
      }
    },
    [read],
  );

  const split = useMemo(() => {
    if (load.state !== "ready") return { pending: [] as SkillProposal[], decided: 0 };
    const pending = load.proposals.filter(
      (item) => String(item.state || "").toLowerCase() === PROPOSED,
    );
    return { pending, decided: load.proposals.length - pending.length };
  }, [load]);

  if (load.state === "loading") {
    return <p className="text-xs text-white/50">Reading the skill proposal queue.</p>;
  }

  if (load.state === "signed-out") {
    return (
      <p className="text-xs leading-relaxed text-white/50">
        No session token in this browser, so the proposal queue cannot be read. Proposals are
        scoped to one account and this panel will not guess at the queue. Sign in through Talk
        to DEVON.
      </p>
    );
  }

  if (load.state === "error") {
    return (
      <div className="space-y-2">
        <p className="text-xs text-red-300">
          The skill proposal queue could not be read: {load.detail}.
        </p>
        <p className="text-xs leading-relaxed text-white/50">
          This is a failed read, not an empty queue. Proposals may be waiting on a ruling and
          this panel cannot see them.
        </p>
        <button
          type="button"
          onClick={() => void read()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Try again
        </button>
      </div>
    );
  }

  return (
    <div className="space-y-4">
      <p className="text-xs leading-relaxed text-white/50">
        Completed agent tasks draft these on their own. Nothing here is active until a person
        approves it, and approving a draft is a separate ruling from activating a skill.
      </p>

      {split.pending.length === 0 ? (
        <p className="text-xs leading-relaxed text-white/70">
          No proposal is waiting on a ruling. The queue was read successfully and it holds
          nothing undecided.
          {split.decided > 0
            ? ` ${split.decided} ${split.decided === 1 ? "proposal has" : "proposals have"} already been decided.`
            : " Nothing has been decided yet either, so no task has drafted one."}
        </p>
      ) : (
        <ul className="space-y-3">
          {split.pending.map((proposal) => {
            const outcome = outcomes[proposal.proposal_id];
            const sending = outcome?.kind === "sending";
            return (
              <li
                key={proposal.proposal_id}
                className="min-w-0 rounded-xl border border-white/10 bg-black/25 px-3 py-3"
              >
                <div className="flex flex-wrap items-baseline justify-between gap-2">
                  <p className="text-sm font-semibold tracking-tight text-white">
                    {proposal.name || proposal.proposal_id}
                  </p>
                  <span className="rounded-full border border-white/15 bg-white/5 px-2 py-0.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/55">
                    Awaiting ruling
                  </span>
                </div>

                {proposal.description ? (
                  <p className="mt-1.5 text-xs leading-relaxed text-white/60">
                    {proposal.description}
                  </p>
                ) : (
                  <p className="mt-1.5 text-xs leading-relaxed text-white/40">
                    The draft carries no description.
                  </p>
                )}

                <p className="mt-2.5 text-[11px] font-semibold uppercase tracking-[0.14em] text-white/45">
                  Instructions DEVON would follow
                </p>
                {proposal.instructions ? (
                  <pre className="mt-1 max-w-full overflow-x-auto whitespace-pre-wrap break-words rounded-lg border border-white/10 bg-black/40 px-2.5 py-2 text-[11px] leading-relaxed text-white/75">
                    {proposal.instructions}
                  </pre>
                ) : (
                  <p className="mt-1 text-xs leading-relaxed text-red-300">
                    The draft carries no instructions, so there is nothing here to approve.
                  </p>
                )}

                <dl className="mt-2.5 grid gap-1 text-[11px] text-white/50 sm:grid-cols-2">
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Drafted from task</dt>
                    <dd className="min-w-0 break-all font-mono text-white/70">
                      {proposal.source_task_id || "not recorded"}
                    </dd>
                  </div>
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Proposal</dt>
                    <dd className="min-w-0 break-all font-mono text-white/70">
                      {proposal.proposal_id}
                    </dd>
                  </div>
                  <div className="flex min-w-0 items-baseline gap-1.5">
                    <dt className="shrink-0">Drafted</dt>
                    <dd className="min-w-0 text-white/70">{whenLabel(proposal.created_at)}</dd>
                  </div>
                </dl>

                {/* Equal weight on all three, reject first. See the note at the
                    top of this file on why refusing is not the styled-scary
                    option here. */}
                <div className="mt-3 flex flex-wrap gap-2">
                  <button
                    type="button"
                    disabled={sending}
                    onClick={() => void decide(proposal, { approve: false, promote: false })}
                    className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white disabled:opacity-40"
                  >
                    Reject
                  </button>
                  <button
                    type="button"
                    disabled={sending}
                    onClick={() => void decide(proposal, { approve: true, promote: false })}
                    className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white disabled:opacity-40"
                  >
                    Approve only
                  </button>
                  <button
                    type="button"
                    disabled={sending}
                    onClick={() => void decide(proposal, { approve: true, promote: true })}
                    className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/30 hover:text-white disabled:opacity-40"
                  >
                    Approve and activate
                  </button>
                </div>
                <p className="mt-1.5 text-[11px] leading-relaxed text-white/45">
                  Approve only records the ruling and leaves the skill inactive. Approve and
                  activate writes it into the skill set DEVON can use.
                </p>

                {outcome?.kind === "sending" ? (
                  <p className="mt-2 text-[11px] text-white/60">Sending the ruling.</p>
                ) : null}
                {outcome?.kind === "failed" ? (
                  <p className="mt-2 text-[11px] text-red-300">
                    The ruling was not recorded: {outcome.detail}.
                  </p>
                ) : null}
                {outcome?.kind === "done" ? (
                  <p className="mt-2 text-[11px] text-white/70">{outcome.sentence}</p>
                ) : null}
              </li>
            );
          })}
        </ul>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <button
          type="button"
          onClick={() => void read()}
          className="rounded-lg border border-white/15 px-3 py-1.5 text-xs font-medium text-white/70 transition hover:border-white/25 hover:text-white"
        >
          Refresh
        </button>
        <p className="text-[11px] text-white/40">
          {split.decided > 0 && split.pending.length > 0
            ? `${split.decided} already decided and not shown. `
            : ""}
          {checkedAt ? `Queue read ${checkedAt.toLocaleTimeString()}.` : ""}
        </p>
      </div>
    </div>
  );
}
