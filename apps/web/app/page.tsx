import Link from "next/link";

const pillars = [
  {
    title: "AI Council",
    description:
      "Nine specialized agents collaborate — Oracle, Analyst, Strategist, Architect, Engineer, Guardian, Creator, Librarian, and Skeptic.",
  },
  {
    title: "Knowledge + Memory",
    description:
      "Upload documents, retrieve with semantic precision, and keep transparent long-term memory you can edit or delete.",
  },
  {
    title: "Decision Intelligence",
    description:
      "Structure questions, surface tradeoffs, and record the human final call so future decisions stay accountable.",
  },
  {
    title: "Workflows with gates",
    description:
      "Reads run unattended. Writes wait for your approval — every time. Automation never acts in your name alone.",
  },
];

export default function HomePage() {
  return (
    <div className="ms-shell">
      <header className="ms-nav sticky top-0 z-40">
        <div className="mx-auto flex h-16 max-w-6xl items-center justify-between px-6">
          <div className="flex items-center gap-3">
            <div className="flex h-9 w-9 items-center justify-center rounded-lg bg-navy shadow-soft">
              <span className="text-sm font-bold tracking-tight text-amber">MS</span>
            </div>
            <div className="flex flex-col leading-none">
              <span className="text-sm font-semibold tracking-tight text-navy">
                Meta Supreme
              </span>
              <span className="text-[10px] font-medium uppercase tracking-widest text-navy/45">
                Apex Genesis
              </span>
            </div>
          </div>
          <nav className="flex items-center gap-3 sm:gap-4">
            <Link
              href="/login"
              className="hidden text-sm font-medium text-navy/70 transition hover:text-navy sm:inline"
            >
              Sign in
            </Link>
            <Link
              href="/login"
              className="rounded-lg bg-navy px-4 py-2 text-sm font-medium text-surface shadow-soft transition hover:bg-navy-800 focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2"
            >
              Enter system
            </Link>
          </nav>
        </div>
      </header>

      <main>
        <section className="relative overflow-hidden">
          <div
            className="pointer-events-none absolute inset-0 opacity-[0.035]"
            style={{
              backgroundImage:
                "radial-gradient(circle at 20% 20%, #D4A017 0%, transparent 40%), radial-gradient(circle at 80% 0%, #0A1628 0%, transparent 35%)",
            }}
          />
          <div className="relative mx-auto max-w-6xl px-6 pb-20 pt-24 sm:pt-28">
            <div className="mx-auto max-w-3xl text-center">
              <p className="ms-overline mb-5">Intelligence Operating System</p>
              <h1 className="text-balance text-4xl font-semibold tracking-tight text-navy sm:text-5xl md:text-[3.25rem] md:leading-[1.1]">
                Amplify judgment.
                <span className="block text-navy/80">Keep the final call human.</span>
              </h1>
              <p className="mx-auto mt-6 max-w-2xl text-balance text-base leading-relaxed text-navy/65 sm:text-lg">
                Multi-agent council, knowledge, memory, and gated workflows —
                built for clear thinking, not chat noise. Simulated intelligence
                is always labeled.
              </p>
              <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Link
                  href="/login"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg bg-navy px-7 text-sm font-medium text-surface shadow-elevated transition hover:bg-navy-800"
                >
                  Open Command Center
                </Link>
                <Link
                  href="#system"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border bg-surface-elevated px-7 text-sm font-medium text-navy shadow-soft transition hover:bg-surface-muted"
                >
                  View the system
                </Link>
              </div>
              <p className="mt-6 text-xs text-navy/45">
                Offline mock provider available · zero keys required for local runs
              </p>
            </div>
          </div>
        </section>

        <section id="system" className="border-t border-border/60 bg-surface-muted/40 py-20">
          <div className="mx-auto max-w-6xl px-6">
            <div className="mb-12 max-w-2xl">
              <p className="ms-overline mb-3">System</p>
              <h2 className="text-2xl font-semibold tracking-tight text-navy sm:text-3xl">
                Built for leverage, not dependency
              </h2>
              <p className="mt-3 text-sm leading-relaxed text-navy/65 sm:text-base">
                Humans provide values and responsibility. The system provides
                analysis, structure, and execution support — never silent
                automation on effects.
              </p>
            </div>
            <div className="grid gap-5 sm:grid-cols-2">
              {pillars.map((item) => (
                <div key={item.title} className="ms-card">
                  <h3 className="text-base font-semibold text-navy">{item.title}</h3>
                  <p className="mt-2 text-sm leading-relaxed text-navy/70">
                    {item.description}
                  </p>
                </div>
              ))}
            </div>
          </div>
        </section>

        <section className="py-20">
          <div className="mx-auto max-w-6xl px-6">
            <div className="ms-card-elevated flex flex-col items-start justify-between gap-8 md:flex-row md:items-center">
              <div className="max-w-xl">
                <p className="ms-overline mb-3">Flagship principle</p>
                <h2 className="text-xl font-semibold tracking-tight text-navy sm:text-2xl">
                  Reads flow. Writes wait.
                </h2>
                <p className="mt-3 text-sm leading-relaxed text-navy/65">
                  Workflow steps that only read can run alone. Memory writes,
                  decision drafts, and exports pause until you approve the
                  rendered payload.
                </p>
              </div>
              <Link
                href="/login"
                className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-lg bg-amber px-6 text-sm font-semibold text-navy shadow-soft transition hover:bg-amber-500"
              >
                Start with mock intelligence
              </Link>
            </div>
          </div>
        </section>
      </main>

      <footer className="border-t border-border/60 py-10">
        <div className="mx-auto flex max-w-6xl flex-col items-center justify-between gap-4 px-6 sm:flex-row">
          <div className="flex items-center gap-2">
            <div className="flex h-7 w-7 items-center justify-center rounded-md bg-navy">
              <span className="text-[10px] font-bold text-amber">MS</span>
            </div>
            <span className="text-sm text-navy/55">
              Meta Supreme Apex Genesis · Intelligence Operating System
            </span>
          </div>
          <span className="text-xs text-navy/40">Calm · precise · human-final</span>
        </div>
      </footer>
    </div>
  );
}
