"use client";

import { useState } from "react";
import Link from "next/link";
import { DecisionPackageView } from "@/components/council/DecisionPackageView";
import { generateMockPackage } from "@/lib/mock-deliberation";
import type { DecisionPackage, HumanDecision } from "@/lib/council-types";

export default function DeliberatePage() {
  const [question, setQuestion] = useState("");
  const [pkg, setPkg] = useState<DecisionPackage | null>(null);
  const [lastDecision, setLastDecision] = useState<HumanDecision | null>(null);

  function startDeliberation(e: React.FormEvent) {
    e.preventDefault();
    if (!question.trim()) return;
    const generated = generateMockPackage(question);
    setPkg(generated);
    setLastDecision(null);
  }

  function handleDecision(decision: HumanDecision) {
    setLastDecision(decision);
    // In a later slice this will persist the official decision record.
    console.info("Human decision recorded:", decision);
  }

  function reset() {
    setPkg(null);
    setQuestion("");
    setLastDecision(null);
  }

  return (
    <div className="min-h-screen bg-surface">
      {/* Minimal chrome */}
      <header className="border-b border-border/60 bg-surface/95 backdrop-blur">
        <div className="mx-auto flex h-14 max-w-2xl items-center justify-between px-4 sm:px-6">
          <Link href="/" className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-navy">
              <span className="text-[10px] font-bold text-amber">MS</span>
            </div>
            <span className="text-sm font-medium text-navy">Meta Supreme</span>
          </Link>
          <span className="text-xs text-navy/45">Council · Deliberate</span>
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
            simulated mode.
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
              className="mt-2 w-full rounded-lg border border-border bg-surface-elevated px-4 py-3 text-sm text-navy placeholder:text-navy/40 shadow-soft focus:border-amber focus:outline-none focus:ring-2 focus:ring-amber/30"
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
          <DecisionPackageView pkg={pkg} onDecision={handleDecision} />
          <div className="fixed bottom-0 left-0 right-0 border-t border-border/60 bg-surface/95 px-4 py-3 backdrop-blur sm:px-6">
            <div className="mx-auto flex max-w-2xl items-center justify-between">
              <button
                type="button"
                onClick={reset}
                className="text-sm font-medium text-navy/60 transition hover:text-navy"
              >
                New question
              </button>
              {lastDecision && (
                <span className="text-xs text-navy/50">
                  Decision locked · {lastDecision.choice}
                </span>
              )}
            </div>
          </div>
        </>
      )}
    </div>
  );
}
