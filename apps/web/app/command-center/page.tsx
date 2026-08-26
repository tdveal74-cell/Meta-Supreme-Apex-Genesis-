import Link from "next/link";
import { DevonChat } from "@/components/devon/DevonChat";
import { OperatorTerminal } from "@/components/terminal/OperatorTerminal";

const panels = [
  {
    overline: "Council",
    title: "Nine seats, one synthesis",
    body:
      "Pose a decision and the Council pressure-tests it before anything runs. Gated jobs consult the same Council, and its latest word rides on every approval card.",
    href: "/council/deliberate",
    cta: "Open deliberation",
  },
  {
    overline: "Gates",
    title: "Reads flow. Writes wait.",
    body:
      "Read-only work runs unattended. Every write pauses at the approval queue for a human ruling, and refusal executes nothing. The final call never leaves you.",
    href: null,
    cta: null,
  },
  {
    overline: "Estate organs",
    title: "The estate watches itself",
    body:
      "Heartbeat pulses every 6 hours, the Ledger Janitor sweeps stale jobs daily at 02:30 UTC, and the weekly backup mails the learning-lane tables every Sunday. Silence means idle, never unknown.",
    href: null,
    cta: null,
  },
];

export default function CommandCenterPage() {
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
              <h1 className="text-lg font-semibold tracking-tight text-white">Command Center</h1>
            </div>
          </div>

          <nav className="flex flex-wrap items-center gap-3 text-xs text-white/55">
            <Link
              href="/"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Home
            </Link>
            <Link
              href="/council/deliberate"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Council
            </Link>
            <Link
              href="/devon"
              className="rounded-lg bg-amber-300 px-3 py-2 font-semibold text-[#151006] transition hover:bg-amber-200"
            >
              DEVON full screen
            </Link>
            <Link
              href="/terminal"
              className="rounded-lg border border-white/10 px-3 py-2 font-medium text-white/70 transition hover:border-white/20 hover:text-white"
            >
              Terminal
            </Link>
            <Link
              href="/shell"
              className="rounded-lg border border-emerald-400/30 bg-emerald-400/10 px-3 py-2 font-semibold text-emerald-200 transition hover:bg-emerald-400/20"
            >
              Real shell
            </Link>
          </nav>
        </header>

        <div className="mb-4">
          <DevonChat />
        </div>

        <section className="mb-4 grid gap-4 md:grid-cols-3">
          {panels.map((panel) => (
            <div
              key={panel.overline}
              className="flex flex-col rounded-2xl border border-white/10 bg-white/[0.035] p-5"
            >
              <p className="text-[10px] font-semibold uppercase tracking-[0.2em] text-amber-300/75">
                {panel.overline}
              </p>
              <h2 className="mt-2 text-base font-semibold text-white">{panel.title}</h2>
              <p className="mt-2 flex-1 text-sm leading-6 text-white/50">{panel.body}</p>
              {panel.href && panel.cta && (
                <Link
                  href={panel.href}
                  className="mt-4 inline-flex w-fit items-center rounded-lg border border-amber-300/30 bg-amber-300/10 px-4 py-2 text-xs font-semibold text-amber-200 transition hover:bg-amber-300/20"
                >
                  {panel.cta}
                </Link>
              )}
            </div>
          ))}
        </section>

        <OperatorTerminal />
      </div>
    </main>
  );
}
