import Link from "next/link";
import { AgentRosterPanel } from "@/components/roster/AgentRosterPanel";

/**
 * The agent roster on its own page.
 *
 * It lives here rather than only inside a tier for the same reason
 * /control/learning does: the tier shell is one shared file, and a panel that can
 * stand alone should not have to wait on it. Folding it into Tier 1 as well is a
 * two line change to ControlPlane's props and one line in app/control/page.tsx;
 * until that lands the surface is reachable here and nothing about it is faked
 * inside the shell.
 */
export default function RosterPage() {
  return (
    <main className="min-h-screen bg-[#04070d] text-[#e8edf2]">
      <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="mb-5 flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/[0.035] px-5 py-4 backdrop-blur md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-300/80">
              DEVON
            </p>
            <h1 className="mt-1 text-lg font-semibold tracking-tight text-white">
              Agent roster
            </h1>
            <p className="mt-1.5 max-w-xl text-xs leading-relaxed text-white/55">
              What each Council agent declares it is for, what it says it can and cannot do, the
              shape it promises to answer in, and how it asks to be judged. Read from
              GET /agents and GET /agents/{"{slug}"}, which were complete and had no caller under
              apps/web until this page.
            </p>
          </div>

          <nav className="flex flex-wrap items-center gap-3 text-xs text-white/55">
            <Link
              href="/control"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Control plane
            </Link>
            <Link
              href="/command-center"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Command Center
            </Link>
          </nav>
        </header>

        <section className="rounded-2xl border border-white/10 bg-white/[0.025] px-5 py-5 backdrop-blur">
          <AgentRosterPanel />
        </section>
      </div>
    </main>
  );
}
