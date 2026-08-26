import Link from "next/link";
import { DevonChat } from "@/components/devon/DevonChat";

export default function DevonPage() {
  return (
    <main className="min-h-screen bg-[#05080c] text-[#e8edf2]">
      <div className="mx-auto flex min-h-screen max-w-4xl flex-col px-4 py-4 sm:px-6">
        <header className="mb-4 flex items-center justify-between gap-4 rounded-2xl border border-white/10 bg-white/[0.035] px-5 py-4 backdrop-blur">
          <div className="flex items-center gap-4">
            <div className="flex h-11 w-11 items-center justify-center rounded-xl border border-amber-400/30 bg-amber-400/10">
              <span className="text-sm font-bold tracking-[0.18em] text-amber-300">DV</span>
            </div>
            <div>
              <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-300/80">DEVON</p>
              <h1 className="text-lg font-semibold tracking-tight text-white">Talk to DEVON</h1>
            </div>
          </div>
          <Link
            href="/command-center"
            className="rounded-lg border border-white/10 px-3 py-2 text-xs font-medium text-white/70 transition hover:border-white/20 hover:text-white"
          >
            Command Center
          </Link>
        </header>

        <div className="flex flex-1 flex-col">
          <DevonChat />
        </div>
      </div>
    </main>
  );
}
