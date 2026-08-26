import Link from "next/link";
import { RealShell } from "@/components/terminal/RealShell";

export default function ShellPage() {
  return (
    <main className="min-h-screen bg-[#05080c] text-[#e8edf2]">
      <div className="mx-auto flex min-h-screen max-w-6xl flex-col px-4 py-4 sm:px-6">
        <header className="mb-4 flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.035] px-5 py-4 backdrop-blur">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-amber-400/30 bg-amber-400/10">
              <span className="text-sm font-bold tracking-[0.18em] text-amber-300">DV</span>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-300/80">DEVON</p>
              <h1 className="text-lg font-semibold tracking-tight text-white">Real Shell</h1>
            </div>
          </div>
          <nav className="flex items-center gap-3 text-xs">
            <Link
              href="/terminal"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Gated terminal
            </Link>
            <Link
              href="/command-center"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Command Center
            </Link>
          </nav>
        </header>

        <div className="flex flex-1 flex-col">
          <RealShell />
        </div>
      </div>
    </main>
  );
}
