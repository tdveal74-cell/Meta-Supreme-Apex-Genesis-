"use client";

import { useState } from "react";
import type { DecisionPackage, HumanDecision } from "@/lib/council-types";
import { ModeBadge } from "./ModeBadge";

interface Props {
  pkg: DecisionPackage;
  onDecision?: (decision: HumanDecision) => void;
}

export function DecisionPackageView({ pkg, onDecision }: Props) {
  const [selected, setSelected] = useState<"A" | "B" | "C" | "D" | null>(null);
  const [modification, setModification] = useState("");
  const [alternative, setAlternative] = useState("");
  const [focus, setFocus] = useState("");
  const [submitted, setSubmitted] = useState(false);
  const [showTranscript, setShowTranscript] = useState(false);

  function submit() {
    if (!selected || !onDecision) return;

    let decision: HumanDecision;
    if (selected === "A") decision = { choice: "A" };
    else if (selected === "B") decision = { choice: "B", modification };
    else if (selected === "C") decision = { choice: "C", alternative };
    else decision = { choice: "D", focus };

    onDecision(decision);
    setSubmitted(true);
  }

  return (
    <div className="mx-auto w-full max-w-2xl px-4 pb-32 pt-8 sm:px-6">
      {/* Header */}
      <header className="mb-8 flex flex-wrap items-center justify-between gap-3">
        <div>
          <p className="text-[11px] font-medium uppercase tracking-widest text-navy/45">
            Council Decision Package
          </p>
          <p className="mt-0.5 font-mono text-xs text-navy/40">{pkg.run_id}</p>
        </div>
        <ModeBadge mode={pkg.mode} />
      </header>

      {/* Question */}
      <section className="mb-8 border-y border-border-strong py-5">
        <p className="text-[11px] font-medium uppercase tracking-widest text-amber">
          Question
        </p>
        <h1 className="mt-2 text-balance text-xl font-semibold leading-snug tracking-tight text-navy sm:text-2xl">
          {pkg.question}
        </h1>
      </section>

      {/* Plurality */}
      <section className="mb-8 rounded-lg bg-surface-elevated p-5 shadow-soft">
        <p className="text-[11px] font-medium uppercase tracking-widest text-amber">
          Plurality position
        </p>
        <p className="mt-2 text-base font-medium leading-relaxed text-navy">
          {pkg.plurality_view}
        </p>
      </section>

      {/* Key Reasons */}
      <section className="mb-8">
        <p className="mb-3 text-[11px] font-medium uppercase tracking-widest text-navy/50">
          Key reasons
        </p>
        <ul className="space-y-3">
          {pkg.key_reasons.map((reason, i) => (
            <li key={i} className="flex gap-3 text-sm leading-relaxed text-navy/80">
              <span className="mt-1.5 h-1.5 w-1.5 shrink-0 rounded-full bg-navy/30" />
              <span>{reason}</span>
            </li>
          ))}
        </ul>
      </section>

      {/* Strongest Dissent — protected */}
      <section className="mb-8 rounded-lg border-l-[3px] border-border-strong bg-surface-muted p-5">
        <p className="mb-4 text-[11px] font-medium uppercase tracking-widest text-amber">
          Strongest dissent
        </p>
        <div className="space-y-5">
          {pkg.strongest_dissent.map((d, i) => (
            <div key={i}>
              <p className="font-mono text-xs text-navy/50">{d.seat}</p>
              <p className="mt-1 text-sm font-medium text-navy">{d.position}</p>
              <p className="mt-1 text-sm leading-relaxed text-navy/70">{d.argument}</p>
            </div>
          ))}
        </div>
      </section>

      {/* Confidence */}
      <section className="mb-8">
        <p className="mb-2 text-[11px] font-medium uppercase tracking-widest text-navy/50">
          Confidence & uncertainty
        </p>
        <p className="text-sm font-medium text-navy">
          Range: <span className="font-mono">{pkg.confidence_range}</span>
        </p>
        {pkg.unresolved_unknowns.length > 0 && (
          <ul className="mt-3 space-y-1.5">
            {pkg.unresolved_unknowns.map((u, i) => (
              <li key={i} className="text-sm text-navy/65">
                • {u}
              </li>
            ))}
          </ul>
        )}
      </section>

      {/* Open Questions */}
      <section className="mb-10">
        <p className="mb-3 text-[11px] font-medium uppercase tracking-widest text-navy/50">
          Open questions for you
        </p>
        <ol className="list-decimal space-y-2 pl-5">
          {pkg.open_questions.map((q, i) => (
            <li key={i} className="text-sm leading-relaxed text-navy">
              {q}
            </li>
          ))}
        </ol>
      </section>

      {/* Actions */}
      {!submitted ? (
        <section className="rounded-lg bg-surface-elevated p-5 shadow-elevated">
          <p className="mb-4 text-[11px] font-medium uppercase tracking-widest text-navy/50">
            Your decision
          </p>
          <div className="space-y-3">
            <ActionButton
              active={selected === "A"}
              primary
              onClick={() => setSelected("A")}
              label="A. Accept plurality view"
            />
            <ActionButton
              active={selected === "B"}
              onClick={() => setSelected("B")}
              label="B. Accept with modifications"
            />
            {selected === "B" && (
              <textarea
                value={modification}
                onChange={(e) => setModification(e.target.value)}
                placeholder="Describe the modifications…"
                className="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm text-navy placeholder:text-navy/40 focus:border-amber focus:outline-none focus:ring-2 focus:ring-amber/30"
                rows={3}
              />
            )}
            <ActionButton
              active={selected === "C"}
              onClick={() => setSelected("C")}
              label="C. Override with alternative"
            />
            {selected === "C" && (
              <textarea
                value={alternative}
                onChange={(e) => setAlternative(e.target.value)}
                placeholder="State your alternative…"
                className="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm text-navy placeholder:text-navy/40 focus:border-amber focus:outline-none focus:ring-2 focus:ring-amber/30"
                rows={3}
              />
            )}
            <ActionButton
              active={selected === "D"}
              onClick={() => setSelected("D")}
              label="D. Request another round on a specific point"
            />
            {selected === "D" && (
              <textarea
                value={focus}
                onChange={(e) => setFocus(e.target.value)}
                placeholder="What should be re-examined?"
                className="w-full rounded-md border border-border bg-surface px-3 py-2.5 text-sm text-navy placeholder:text-navy/40 focus:border-amber focus:outline-none focus:ring-2 focus:ring-amber/30"
                rows={3}
              />
            )}
          </div>

          <button
            type="button"
            disabled={!selected}
            onClick={submit}
            className="mt-5 flex min-h-11 w-full items-center justify-center rounded-md bg-navy text-sm font-medium text-surface transition hover:bg-navy-800 disabled:cursor-not-allowed disabled:opacity-40 focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2"
          >
            Record decision
          </button>
        </section>
      ) : (
        <section className="rounded-lg border border-border bg-surface-muted p-5 text-center">
          <p className="text-sm font-medium text-navy">Decision recorded</p>
          <p className="mt-1 text-xs text-navy/55">
            The human gate has been closed for this run.
          </p>
        </section>
      )}

      {/* Transcript disclosure */}
      <div className="mt-10">
        <button
          type="button"
          onClick={() => setShowTranscript((v) => !v)}
          className="text-sm font-medium text-navy/60 transition hover:text-navy"
        >
          {showTranscript ? "Hide" : "Show"} full deliberation transcript
        </button>
        {showTranscript && (
          <div className="mt-4 rounded-lg border border-border bg-surface-muted p-4">
            <p className="font-mono text-xs text-navy/50">
              {pkg.transcript_ref ?? "No transcript reference"}
            </p>
            <p className="mt-2 text-sm text-navy/60">
              Full chronological transcript will appear here once live deliberation
              logging is connected. Simulated runs currently show only the package.
            </p>
          </div>
        )}
      </div>
    </div>
  );
}

function ActionButton({
  label,
  active,
  primary,
  onClick,
}: {
  label: string;
  active: boolean;
  primary?: boolean;
  onClick: () => void;
}) {
  const base =
    "flex min-h-11 w-full items-center rounded-md px-4 text-left text-sm font-medium transition focus-visible:outline-none focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2";

  if (primary) {
    return (
      <button
        type="button"
        onClick={onClick}
        className={`${base} ${
          active
            ? "bg-navy text-surface"
            : "bg-navy/90 text-surface hover:bg-navy"
        }`}
      >
        {label}
      </button>
    );
  }

  return (
    <button
      type="button"
      onClick={onClick}
      className={`${base} ${
        active
          ? "border border-navy bg-surface-muted text-navy"
          : "border border-border bg-surface-elevated text-navy hover:bg-surface-muted"
      }`}
    >
      {label}
    </button>
  );
}
