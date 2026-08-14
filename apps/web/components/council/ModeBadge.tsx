import type { CouncilMode } from "@/lib/council-types";

export function ModeBadge({ mode }: { mode: CouncilMode }) {
  if (mode === "simulated") {
    return (
      <span className="inline-flex items-center rounded-md border border-amber/40 bg-surface-muted px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-amber">
        Simulated
      </span>
    );
  }

  return (
    <span className="inline-flex items-center rounded-md border border-border bg-surface-elevated px-2.5 py-1 text-[11px] font-semibold uppercase tracking-wider text-navy">
      Live
    </span>
  );
}
