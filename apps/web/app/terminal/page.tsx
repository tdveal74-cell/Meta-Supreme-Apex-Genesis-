import Link from "next/link";
import { OperatorTerminal } from "@/components/terminal/OperatorTerminal";

export default function DevonTerminalPage() {
  return (
    <main className="min-h-screen bg-[#05080c] text-[#e8edf2]">
      <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="mb-4 flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/[0.035] px-5 py-4 backdrop-blur md:flex-row md:items-center md:justify-between">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-amber-400/30 bg-amber-400/10">
              <span className="text-sm font-bold tracking-[0.18em] text-amber-300">DV</span>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-300/80">DEVON</p>
              <h1 className="text-lg font-semibold tracking-tight text-white">Operator Terminal</h1>
            </div>
          </div>

          <div className="flex flex-wrap items-center gap-3 text-xs text-white/55">
            <span className="rounded-full border border-white/10 bg-black/30 px-3 py-1.5">Full screen</span>
            <span className="rounded-full border border-white/10 bg-black/30 px-3 py-1.5">Human final</span>
            <Link
              href="/shell"
              className="rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 font-semibold text-emerald-200 transition hover:bg-emerald-400/20"
            >
              Real shell
            </Link>
            <Link
              href="/command-center"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Command Center
            </Link>
          </div>
        </header>

        <OperatorTerminal />
      </div>
    </main>
  );
}
