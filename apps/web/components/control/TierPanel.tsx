"use client";

import type { ReactNode } from "react";

/**
 * How honest a panel is about its own data, shown on its face.
 *
 * The map in docs/devon/SYS_SPEC_devon-control-plane-workspace_v1_2026-09-08.md
 * marks every module lives, built, or not built. A workspace that renders all
 * three the same way is the drift that document exists to prevent, so the
 * badge is part of the panel rather than a footnote somewhere else.
 *
 * live      every field on the panel comes from a route that returns it
 * partial   the panel reads a real route and some fields have no source yet
 * unwired   no route exposes this at all; the panel says so and shows nothing
 */
export type PanelSourcing = "live" | "partial" | "unwired";

const BADGE: Record<PanelSourcing, { label: string; className: string }> = {
  live: {
    // Deliberately not "Live data". A browser run on 2026-09-09 showed this
    // badge reading as a claim about the current numbers while the panel below
    // it had no session and could read nothing. The badge is about where the
    // data comes from; the panel body owns whether a read just succeeded.
    label: "Fully sourced",
    className: "border-emerald-400/30 bg-emerald-400/10 text-emerald-200",
  },
  partial: {
    label: "Partly sourced",
    className: "border-amber-400/30 bg-amber-400/10 text-amber-200",
  },
  unwired: {
    label: "No route yet",
    className: "border-white/15 bg-white/5 text-white/55",
  },
};

export type TierPanelProps = {
  title: string;
  /** One line on what the panel is for. Plain language, no marketing. */
  purpose: string;
  sourcing: PanelSourcing;
  /**
   * Why the sourcing is what it is. Required for partial and unwired so a
   * reader never has to guess whether a blank panel is broken or honest.
   */
  sourceNote?: string;
  children?: ReactNode;
};

export function TierPanel({ title, purpose, sourcing, sourceNote, children }: TierPanelProps) {
  const badge = BADGE[sourcing];
  return (
    <section className="min-w-0 overflow-hidden rounded-2xl border border-white/10 bg-white/[0.035] backdrop-blur">
      <header className="flex flex-col gap-2 border-b border-white/10 px-4 py-3 sm:px-5">
        <div className="flex flex-wrap items-center justify-between gap-2">
          <h3 className="text-sm font-semibold tracking-tight text-white">{title}</h3>
          <span
            className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${badge.className}`}
          >
            {badge.label}
          </span>
        </div>
        <p className="text-xs leading-relaxed text-white/50">{purpose}</p>
        {sourceNote ? (
          <p className="text-xs leading-relaxed text-white/40">{sourceNote}</p>
        ) : null}
      </header>
      {children ? (
        <div className="min-w-0 overflow-x-auto px-4 py-4 sm:px-5">{children}</div>
      ) : null}
    </section>
  );
}
