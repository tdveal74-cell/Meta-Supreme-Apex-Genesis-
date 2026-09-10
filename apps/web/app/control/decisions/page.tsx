import Link from "next/link";
import { DecisionRecordPanel } from "@/components/council/DecisionRecordPanel";

/**
 * The decision record on its own page.
 *
 * It lives here rather than only inside Tier 1 for the same reason
 * /control/learning does: the tier shell is one shared file, and a panel that
 * can stand alone should not have to wait on it. Folding this into Tier 1 as
 * well is a two line change to ControlPlane and one line in
 * app/control/page.tsx, written out in the door notes; until that lands the
 * surface is reachable here and nothing about it is faked inside the shell.
 *
 * The dark surface is the control plane one rather than the Council page one.
 * The record is an operator surface, and mixing this panel into the light
 * Council theme would have meant two visual languages inside one panel.
 */
export default function DecisionRecordPage() {
  return (
    <main className="min-h-screen bg-[#04070d] text-[#e8edf2]">
      <div className="mx-auto flex min-h-screen max-w-3xl flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="mb-5 flex flex-col gap-4 rounded-2xl border border-white/10 bg-white/[0.035] px-5 py-4 backdrop-blur md:flex-row md:items-center md:justify-between">
          <div>
            <p className="text-xs font-semibold uppercase tracking-[0.24em] text-amber-300/80">
              DEVON
            </p>
            <h1 className="mt-1 text-lg font-semibold tracking-tight text-white">
              Decision record
            </h1>
            <p className="mt-1.5 max-w-xl text-xs leading-relaxed text-white/60">
              The human final call on every question the Council was asked. Until this page
              existed the routes behind it had no caller anywhere in this web app, so a ruling
              made on the deliberate page lived in one browser tab and a reload discarded it.
            </p>
          </div>

          <nav className="flex flex-wrap items-center gap-3 text-xs text-white/60">
            <Link
              href="/council/deliberate"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Deliberate
            </Link>
            <Link
              href="/control"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Control plane
            </Link>
          </nav>
        </header>

        <section className="rounded-2xl border border-white/10 bg-white/[0.025] px-5 py-5 backdrop-blur">
          <DecisionRecordPanel />
        </section>
      </div>
    </main>
  );
}
