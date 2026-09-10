"use client";

import { useState } from "react";
import Link from "next/link";
import { DecisionPackageView } from "@/components/council/DecisionPackageView";
import { generateMockPackage } from "@/lib/mock-deliberation";
import { API_BASE } from "@/lib/api-base";
import { readDevonToken } from "@/components/presence/usePresenceSocket";
import {
  describeWriteOutcome,
  isRecorded,
  parseDecisionRow,
  prepareCreate,
  prepareRuling,
  rulingFor,
  writeHeadline,
  type WriteOutcome,
} from "@/components/council/decision-record";
import type { DecisionPackage, HumanDecision } from "@/lib/council-types";

/**
 * WHAT CHANGED HERE, AND WHY IT IS THE POINT OF THE PAGE.
 *
 * handleDecision was a console.info. app/api/v1/decisions.py has been a
 * complete, registered, tested subsystem the whole time and nothing under
 * apps/web called it, so a visitor pressed "Record decision", read that their
 * call was held in this tab only, and a reload discarded it. The Council exists
 * to put a person at the end of it and the record of that person was a door
 * nobody could open.
 *
 * It now writes. Two requests, because the API takes them in that order:
 *
 *   POST  /decisions            creates the decision with the Council position
 *   PATCH /decisions/{id}       records the human final call on it
 *
 * DecisionCreate carries no chosen_option, so a ruling cannot be created in one
 * request. That makes "created but not ruled on" a real state and it is drawn
 * as its own thing rather than rounded to success or to failure. So is a
 * missing session token, which means no request was sent at all.
 *
 * NOTHING HERE RUNS AN EFFECT. Both requests touch the decision record only. No
 * tool is invoked, nothing is materialized and nothing is spawned, so the human
 * gate on WRITE and HIGH_IMPACT tools is untouched. Recording that a person
 * chose something is not the same as doing it, and the record says so.
 *
 * The run itself is still simulated and still labelled simulated, on screen and
 * in the recommendation that reaches the record. prepareCreate stamps the run id
 * and the mode into the stored text for exactly that reason: a record that did
 * not say the run was simulated would read later as nine agents having
 * deliberated.
 */
export default function DeliberatePage() {
  const [question, setQuestion] = useState("");
  const [pkg, setPkg] = useState<DecisionPackage | null>(null);
  const [outcome, setOutcome] = useState<WriteOutcome>({ kind: "idle" });

  function startDeliberation(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    const generated = generateMockPackage(question);
    setPkg(generated);
    setOutcome({ kind: "idle" });
  }

  async function handleDecision(decision: HumanDecision) {
    if (!pkg) return;

    const token = readDevonToken();
    if (!token) {
      setOutcome({ kind: "locked" });
      return;
    }

    const create = prepareCreate(pkg);
    if (!create.ok) {
      setOutcome({ kind: "refused", reason: create.reason });
      return;
    }
    const ruling = rulingFor(decision);
    const patch = prepareRuling(ruling);
    if (!patch.ok) {
      // Refused before the POST rather than after it, so a note that cannot be
      // stored never leaves a decision on the record with no call on it.
      setOutcome({ kind: "refused", reason: patch.reason });
      return;
    }

    setOutcome({ kind: "sending", step: "create" });
    let decisionId: string;
    try {
      const response = await fetch(`${API_BASE}/decisions`, {
        method: "POST",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(create.body),
      });
      if (!response.ok) {
        setOutcome({
          kind: "create-failed",
          detail: `the decisions route answered ${response.status}`,
        });
        return;
      }
      const created = parseDecisionRow(await response.json());
      if (created === null) {
        setOutcome({
          kind: "create-failed",
          detail: "the route answered with a body carrying no decision id, so nothing can be ruled on",
        });
        return;
      }
      decisionId = created.id;
    } catch (error) {
      setOutcome({
        kind: "create-failed",
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
      return;
    }

    setOutcome({ kind: "sending", step: "rule" });
    try {
      const response = await fetch(`${API_BASE}/decisions/${encodeURIComponent(decisionId)}`, {
        method: "PATCH",
        cache: "no-store",
        headers: { "Content-Type": "application/json", Authorization: `Bearer ${token}` },
        body: JSON.stringify(patch.body),
      });
      if (!response.ok) {
        setOutcome({
          kind: "rule-failed",
          decisionId,
          detail: `the decision route answered ${response.status}`,
        });
        return;
      }
      setOutcome({ kind: "recorded", decisionId, ruling });
    } catch (error) {
      setOutcome({
        kind: "rule-failed",
        decisionId,
        detail: error instanceof Error ? error.message : "the request did not complete",
      });
    }
  }

  function reset() {
    setPkg(null);
    setQuestion("");
    setOutcome({ kind: "idle" });
  }

  const sentence = describeWriteOutcome(outcome);
  const recorded = isRecorded(outcome);
  const halfWritten = outcome.kind === "rule-failed";
  // The headline is a switch over the union in decision-record.ts, not a chain
  // of booleans here. The chain it replaced omitted "locked", so a signed-out
  // visitor's terminal outcome read "Sending your call to the decision record"
  // forever over a request nothing sent.
  const headline = writeHeadline(outcome);

  return (
    <div className="min-h-screen bg-surface">
      {/* Minimal chrome */}
      <header className="border-b border-border/60 bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-2xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-navy">
              <span className="text-[11px] font-bold text-amber">MS</span>
            </div>
            <span className="text-sm font-medium text-navy">Meta Supreme</span>
          </Link>
          <div className="flex items-center gap-3">
            <Link
              href="/control/decisions"
              className="text-xs font-medium text-navy/60 underline decoration-navy/30 transition hover:text-navy"
            >
              Decision record
            </Link>
            <span className="text-xs text-navy/50">Council · Deliberate</span>
          </div>
        </div>
      </header>

      {!pkg ? (
        <main className="mx-auto max-w-2xl px-4 pb-20 pt-12 sm:px-6">
          <p className="text-[11px] font-medium uppercase tracking-widest text-amber">
            New deliberation
          </p>
          <h1 className="mt-2 text-2xl font-semibold tracking-tight text-navy">
            Pose a decision to the Council
          </h1>
          <p className="mt-3 max-w-lg text-sm leading-relaxed text-navy/65">
            The Council will return a structured Decision Package. You remain the
            final decision-maker. This path currently runs in fully labeled
            simulated mode, and the label travels with your ruling onto the{" "}
            <Link href="/control/decisions" className="underline decoration-navy/30">
              decision record
            </Link>
            .
          </p>

          <form onSubmit={startDeliberation} className="mt-10">
            <label htmlFor="question" className="block text-sm font-medium text-navy">
              Decision question
            </label>
            <textarea
              id="question"
              value={question}
              onChange={(e) => setQuestion(e.target.value)}
              placeholder="What decision do you need the Council to pressure-test?"
              rows={4}
              className="mt-2 w-full rounded-lg border border-border bg-surface-elevated px-4 py-3 text-sm text-navy placeholder:text-navy/50 shadow-soft focus:border-amber focus:outline-none focus:ring-2 focus:ring-amber/30"
              required
            />
            <button
              type="submit"
              className="mt-5 flex min-h-11 w-full items-center justify-center rounded-lg bg-navy text-sm font-medium text-surface shadow-soft transition hover:bg-navy-800 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2 sm:w-auto sm:px-8"
            >
              Run Council (simulated)
            </button>
          </form>
        </main>
      ) : (
        <>
          <DecisionPackageView
            pkg={pkg}
            onDecision={handleDecision}
            outcome={
              <div>
                <p
                  className={`text-sm font-medium ${
                    headline.tone === "bad" ? "text-red-700" : "text-navy"
                  }`}
                >
                  {headline.text}
                </p>
                <p className="mt-1.5 text-sm leading-relaxed text-navy/70">{sentence}</p>
                {recorded || halfWritten ? (
                  <Link
                    href="/control/decisions"
                    className="mt-2 inline-block text-sm font-medium text-navy underline decoration-navy/30"
                  >
                    Open the decision record
                  </Link>
                ) : null}
              </div>
            }
          />
          <div className="fixed bottom-0 left-0 right-0 border-t border-border/60 bg-surface/95 px-4 py-3 backdrop-blur sm:px-6">
            <div className="mx-auto flex max-w-2xl items-center justify-between gap-3">
              <button
                type="button"
                onClick={reset}
                className="text-sm font-medium text-navy/60 transition hover:text-navy"
              >
                New question
              </button>
              {outcome.kind !== "idle" ? (
                <span className="min-w-0 truncate text-xs text-navy/60">
                  {outcome.kind === "recorded"
                    ? `Recorded: ${outcome.decisionId}`
                    : outcome.kind === "sending"
                      ? "Writing to the record"
                      : "Not recorded"}
                </span>
              ) : null}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
