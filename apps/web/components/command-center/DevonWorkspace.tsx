"use client";

import Link from "next/link";
import { useSearchParams } from "next/navigation";
import type { ReactNode } from "react";

export function DevonWorkspace({ command, control, agents }: {
  command: ReactNode; control: ReactNode; agents: ReactNode;
}) {
  const query = useSearchParams();
  const view = query.get("view") === "control" ? "control" : query.get("view") === "agents" ? "agents" : "command";
  return (
    <div className="min-h-screen bg-[#050a0e] text-[#e8edf2]">
      <header className="border-b border-white/10 px-4 py-4 sm:px-7">
        <div className="mx-auto flex max-w-[1780px] flex-wrap items-center justify-between gap-3">
          <Link href="/command-center" className="font-semibold tracking-[0.2em] text-[#d4a017]">DEVON</Link>
          <nav aria-label="DEVON workspace" className="flex flex-wrap gap-2 text-sm">
            {([
              ["command", "Command Center", "/command-center"],
              ["control", "Control Plane", "/command-center?view=control"],
              ["agents", "Agents", "/command-center?view=agents"],
            ] as const).map(([key, label, href]) => (
              <Link key={key} href={href} aria-current={view === key ? "page" : undefined}
                className={`rounded-lg border px-3 py-2 ${view === key ? "border-[#d4a017] text-[#edce75]" : "border-white/15 text-white/70"}`}>
                {label}
              </Link>
            ))}
            <Link href="/knowledge/import" className="rounded-lg border border-white/15 px-3 py-2 text-white/70">Notebook Import</Link>
          </nav>
        </div>
      </header>
      {view === "control" ? control : view === "agents" ? agents : command}
    </div>
  );
}
