import Link from "next/link";

/**
 * WHAT THIS PAGE IS ALLOWED TO SAY
 *
 * Every claim here has to name something a visitor can reach from this site.
 * Two did not, until 2026-09-10:
 *
 *   - "Workflows with gates". The workflow engine is real and substantial:
 *     ten routes in app/api/v1/workflows.py, about 2470 lines across that
 *     file, app/services/workflows.py, services/workflows/ and
 *     app/services/dispatcher.py, a workflows table in 001_baseline plus
 *     migrations 002_workflow_runs and 003_schedule_dispatch, and a cron
 *     entrypoint the API image ships
 *     (infrastructure/docker/Dockerfile.api:30). Nothing can create a
 *     workflow. There is no page for it under apps/web/app, no component in
 *     apps/web calls /workflows, and no agent tool registers one, so the
 *     engine only ever runs definitions nobody has a way to author.
 *   - "long-term memory you can edit or delete", and "Upload documents".
 *     apps/web/components/mind/KnowledgePanel.tsx reads GET /knowledge and
 *     posts /knowledge/search. It has no ingest control, no editor and no
 *     delete, and no component here calls /memory at all.
 *
 * apps/web/scripts/honesty-check.ts holds the prose to that rule: a capability
 * word here has to have a matching path some component actually calls. The
 * engine and its tests stay where they are; a landing page is the wrong place
 * to advertise them.
 */
const pillars = [
  {
    title: "AI Council",
    description:
      "Nine specialized agents collaborate: Oracle, Analyst, Strategist, Architect, Engineer, Guardian, Creator, Librarian, and Skeptic.",
  },
  {
    title: "Knowledge retrieval",
    description:
      "Read the ingested corpus and search it by meaning from the control plane. Ingestion and long-term memory are API side and have no page here yet.",
  },
  {
    title: "Decision Intelligence",
    description:
      "Structure questions and surface tradeoffs on a Council run this site labels as simulated. Recording the final call is an API route with no page here yet, so nothing on this site persists a decision.",
  },
  {
    title: "Approval gate on effects",
    description:
      "Reads run unattended. Writes wait for your approval, every time, on a card you rule on in the DEVON chat or the operator terminal. Automation never acts in your name alone.",
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
              href="/council/deliberate"
              className="hidden text-sm font-medium text-navy/70 transition hover:text-navy sm:inline"
            >
              Council
            </Link>
            <Link
              href="/control"
              className="hidden text-sm font-medium text-navy/70 transition hover:text-navy sm:inline"
            >
              Control plane
            </Link>
            <Link
              href="/command-center"
              className="rounded-lg bg-navy px-4 py-2 text-sm font-medium text-surface shadow-soft transition hover:bg-navy-800 focus-visible:ring-2 focus-visible:ring-amber focus-visible:ring-offset-2"
            >
              Command Center
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
                Multi-agent council, knowledge retrieval, and an approval gate
                on every effect, built for clear thinking rather than chat
                noise. Simulated intelligence is always labeled.
              </p>
              <div className="mt-10 flex flex-col items-center justify-center gap-3 sm:flex-row">
                <Link
                  href="/command-center"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg bg-navy px-7 text-sm font-medium text-surface shadow-elevated transition hover:bg-navy-800"
                >
                  Open Command Center
                </Link>
                <Link
                  href="/council/deliberate"
                  className="inline-flex min-h-11 items-center justify-center rounded-lg border border-border bg-surface-elevated px-7 text-sm font-medium text-navy shadow-soft transition hover:bg-surface-muted"
                >
                  Open Council
                </Link>
              </div>
              <p className="mt-6 text-xs text-navy/45">
                Council supports a zero-key simulated path. Operator execution is separately gated.
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
                analysis, structure, and execution support, never silent
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
                  The Operator Bridge lets DEVON hand approved work to the host
                  without giving DEVON core subprocess capability. Mutating
                  commands pause at the existing human approval gate.
                </p>
              </div>
              <Link
                href="/command-center"
                className="inline-flex min-h-11 shrink-0 items-center justify-center rounded-lg bg-amber px-6 text-sm font-semibold text-navy shadow-soft transition hover:bg-amber-500"
              >
                Open the Command Center
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
