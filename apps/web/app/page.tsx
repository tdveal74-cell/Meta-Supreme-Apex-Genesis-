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
 * word here has to have a matching path some component actually calls.
 *
 * ALL THREE ARE ALLOWED AGAIN, AND THE DATE IS THE SAME DAY.
 *
 * The two paragraphs above are the history, kept because the correction is the
 * reason the guard exists. Both bans were lifted later on 2026-09-10, when the
 * six remaining doors were closed in one pass:
 *
 *   - apps/web/components/control/WorkflowDoor.tsx composes a workflow through
 *     POST /workflows, starts a run, reads its history, and stands at the
 *     approval gate: it renders the sealed payload a paused run would write and
 *     sends that seal back with the ruling, so the server refuses an approval
 *     given over a payload the run has moved past. Mounted at /control and at
 *     /control/workflows.
 *   - apps/web/components/mind/MemoryPanel.tsx reads GET /memory and writes,
 *     edits, pauses and hard deletes through the other three routes. So
 *     "long-term memory you can edit or delete" is true, and the sentence that
 *     disclaimed it has come out of DISCLAIMERS in the same change.
 *
 * The engine and its tests stay where they are; what changed is that a visitor
 * can now reach them.
 *
 * The Decision Intelligence pillar said this site "records the human final call
 * so future decisions stay accountable", and it was corrected to say the
 * opposite, because app/api/v1/decisions.py was a registered, tested subsystem
 * with no caller anywhere under apps/web and handleDecision on the deliberate
 * page was a console.info.
 *
 * That is no longer true. apps/web/components/council/DecisionRecordPanel.tsx
 * reads GET /decisions, re-reads GET /decisions/{id}, records the call with
 * PATCH /decisions/{id} and puts a Council exchange on the record with
 * POST /decisions/from-message, and the deliberate page POSTs a decision and
 * PATCHes the ruling onto it. So the claim below is restored, in the narrower
 * shape that is actually true: the record is per account, so it is a signed-in
 * visitor whose call is written. The correction that said there was no page has
 * to come out of DISCLAIMERS in honesty-check.ts at the same time, because a
 * disclaimer the page no longer carries fails that check on purpose.
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
      "Read the ingested corpus and search it by meaning from the control plane, and read, edit, pause or destroy long-term memory in the same place. Ingestion is API side and has no page here yet.",
  },
  {
    title: "Decision Intelligence",
    description:
      "Structure questions and surface tradeoffs on a Council run this site labels as simulated. A signed-in visitor's final call is written to the decision record and read back from the control plane, so a past decision can be looked at again.",
  },
  {
    title: "Approval gate on effects",
    description:
      "Reads run unattended. Writes wait for your approval, every time, on a card you rule on in the DEVON chat or the operator terminal, and on the workflow door, where a paused run shows the exact sealed payload it would write before you rule on it. Automation never acts in your name alone.",
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
