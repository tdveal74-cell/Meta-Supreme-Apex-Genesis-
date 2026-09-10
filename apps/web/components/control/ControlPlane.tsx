"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ExecutionHubPanel } from "@/components/control/ExecutionHubPanel";
import { CostPanel } from "@/components/control/CostPanel";
import { SecurityPanel } from "@/components/control/SecurityPanel";
import { SessionDoor } from "@/components/control/SessionDoor";
import { SkillProposalGate } from "@/components/control/SkillProposalGate";
import { TierPanel } from "@/components/control/TierPanel";

/**
 * The unified control plane: three tiers on one surface.
 *
 * Before this, the pieces the 2026-09-08 brief asked for lived on separate
 * pages, so there was no one place to stand. The tiers and their modules are
 * the ones named in
 * docs/devon/SYS_SPEC_devon-control-plane-workspace_v1_2026-09-08.md, and every
 * panel carries that document's own honesty on its face: whether it is reading
 * a real route, reading one with fields it cannot source, or waiting on a route
 * that does not exist.
 *
 * Built for a phone first. Tee's primary device is an iPhone, so the tiers
 * stack and the nav is a scroll target rather than a wide grid that only works
 * on a desktop.
 */

const TIERS = [
  { id: "sovereign", label: "Sovereign" },
  { id: "cognitive", label: "Cognitive" },
  { id: "execution", label: "Execution" },
] as const;

export type ControlPlaneProps = {
  /** Tier 1: agent readiness matrix. */
  readiness?: ReactNode;
  /** Tier 1: ledger provenance card, and whatever selects an intent for it. */
  provenance?: ReactNode;
  /** Tier 2: the avatar stage, voice and barge-in. */
  presence?: ReactNode;
  /** Tier 2: the knowledge corpus. */
  knowledge?: ReactNode;
  /** Tier 2: the learning store DEVON plans from. */
  learning?: ReactNode;
  /** Tier 1: the agent roster as the registry declares it. */
  roster?: ReactNode;
  /** Tier 1: the decision record, and the human final call on each open one. */
  decisions?: ReactNode;
  /** Tier 2: the projects every other read can be scoped by. */
  projects?: ReactNode;
  /** Tier 2: long term memory, read plus write plus edit plus hard delete. */
  memory?: ReactNode;
  /** Tier 3: the workflow engine, its runs and its approval gates. */
  workflows?: ReactNode;
};

export function ControlPlane({
  readiness,
  provenance,
  presence,
  knowledge,
  learning,
  roster,
  decisions,
  projects,
  memory,
  workflows,
}: ControlPlaneProps) {
  return (
    <main className="min-h-screen bg-[#04070d] text-[#e8edf2]">
      <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="sticky top-0 z-30 -mx-4 mb-5 border-b border-white/10 bg-[#04070d]/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              {/* The Merkaba. ACX's own mark, read from the reference folder in
                  Drive: the star tetrahedron that opens Node 01 and closes the
                  loop in Episode 5. It replaces a placeholder that read "DV". */}
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-cyan-400/30 bg-cyan-400/10">
                <svg viewBox="0 0 24 24" className="h-6 w-6" aria-hidden focusable="false">
                  <path
                    d="M12 3 L20.5 18 L3.5 18 Z"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.3"
                    strokeLinejoin="round"
                    className="text-cyan-300"
                  />
                  <path
                    d="M12 21 L3.5 6 L20.5 6 Z"
                    fill="none"
                    stroke="currentColor"
                    strokeWidth="1.3"
                    strokeLinejoin="round"
                    className="text-cyan-400/70"
                  />
                </svg>
              </div>
              <div>
                <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-cyan-300/80">
                  DEVON
                </p>
                <h1 className="text-base font-semibold tracking-tight text-white">
                  Control plane
                </h1>
              </div>
            </div>

            <div className="flex flex-wrap items-center gap-1.5">
              <nav className="flex items-center gap-1.5 text-xs">
                {TIERS.map((tier) => (
                  <a
                    key={tier.id}
                    href={`#${tier.id}`}
                    className="rounded-lg border border-white/10 px-2.5 py-1.5 font-medium text-white/60 transition hover:border-white/25 hover:text-white"
                  >
                    {tier.label}
                  </a>
                ))}
              </nav>
              {/* Four panels below tell the reader to sign in. Until this
                  landed, the page named that fix and offered no way to take
                  it. */}
              <SessionDoor />
            </div>
          </div>
        </header>

        <p className="mb-6 max-w-3xl text-xs leading-relaxed text-white/50">
          Every panel says where its numbers come from. A panel marked as having no route is
          waiting on a backend read, not broken, and it shows nothing rather than a placeholder.
          Agents recommend and humans decide here as everywhere: nothing on this page approves a
          write.
        </p>

        <div className="flex flex-col gap-8 pb-16">
          <Tier
            id="sovereign"
            index="Tier 1"
            title="Sovereign Admin"
            summary="Who is running, what they are allowed to touch, and whether the record of what happened can be trusted."
          >
            <TierPanel
              title="Agent readiness"
              purpose="Every agent task and the state its events put it in, with the risk class of the tools it can reach."
              sourcing={readiness ? "partial" : "unwired"}
              sourceNote={
                readiness
                  ? "Task states and tool risk classes are read from the API and the generated Hermes surface manifest. Latency and load balancing are not built, so no agent is ranked here."
                  : "The matrix component is not mounted on this build."
              }
            >
              {readiness}
            </TierPanel>

            <TierPanel
              title="Agent roster"
              purpose="What each Council agent declares it is for, what it says it cannot do, the shape it promises to answer in, and how it asks to be judged."
              sourcing={roster ? "live" : "unwired"}
              sourceNote={
                roster
                  ? "Read from GET /agents and, per row on demand, GET /agents/{slug}. Both were complete and had no caller under apps/web until this panel. Capability counts read 'not read' rather than 0 until the detail route answers, because the list route sends no arrays; and is_active is only called a measurement on the detail route, because the list route filters on that very field."
                  : "The roster panel is not mounted on this build."
              }
            >
              {roster}
            </TierPanel>

            <TierPanel
              title="Ledger provenance"
              purpose="Whether an intent's history is hash chained end to end and whether a signed receipt certifies exactly that chain."
              sourcing={provenance ? "live" : "unwired"}
              sourceNote={
                provenance
                  ? "Read from the provenance route added in migration 019. A chain that is intact but incomplete is receipted on trust, and the card says so rather than showing it as verified."
                  : "The provenance card is not mounted on this build."
              }
            >
              {provenance}
            </TierPanel>

            <TierPanel
              title="Skill proposal gate"
              purpose="The drafts DEVON wrote for itself from finished work, and the human ruling on each one."
              sourcing="live"
              sourceNote="Read from the skill proposal routes on the agent expansion surface. Every field shown comes back from that read. Approving a draft and activating a skill are two separate rulings and the panel sends them as two separate values, because the API defaults promotion to on when the key is left out."
            >
              <SkillProposalGate />
            </TierPanel>

            <TierPanel
              title="Decision record"
              purpose="Every question the Council was asked, and the human final call on it."
              sourcing={decisions ? "live" : "unwired"}
              sourceNote={
                decisions
                  ? "Read from the decision routes. Until this panel existed nothing under apps/web called any of them, so a ruling made on the deliberate page lived in one browser tab and a reload discarded it. A failed read is drawn as unreadable, never as an empty record, and an exchange whose tracked state could not be read says so rather than reading as not recorded. Recording a call writes to the decision record only: no tool runs from here."
                  : "The decision record panel is not mounted on this build."
              }
            >
              {decisions}
            </TierPanel>

            <TierPanel
              title="Security shell and secrets"
              purpose="The two doors that can execute, and where secrets do and do not live."
              sourcing="partial"
              sourceNote="Both shells are live and predate this arc, so this panel points at them rather than embedding a PTY inside the control plane. There is no secret vault, by design, and whether one should exist is a ruling rather than an omission."
            >
              <SecurityPanel />
            </TierPanel>
          </Tier>

          <Tier
            id="cognitive"
            index="Tier 2"
            title="Cognitive Hub"
            summary="The face and voice, and the memory behind them."
          >
            <TierPanel
              title="Presence"
              purpose="The avatar driven by blendshape frames over the presence socket, with client side barge-in."
              sourcing="partial"
              sourceNote="Frames, the sliding window buffer and the interrupt path are real against the presence service. Cartesia is reached and proven: Tee heard his own cloned voice on 2026-09-09, 113 frames sent and received with none dropped, ten audio chunks scheduled and none late or undecodable. LiveKit is still not configured and this build publishes no audio into a room, so the socket carries the voice. The face is a procedural placeholder until an owned rig exists."
            >
              {presence ?? (
                <p className="text-xs text-white/50">
                  The presence stage is not mounted on this build.{" "}
                  <Link href="/presence" className="underline decoration-white/30">
                    Open it on its own page
                  </Link>
                  .
                </p>
              )}
            </TierPanel>

            <TierPanel
              title="Projects"
              purpose="The scope every other read can be narrowed by, and the only place to create or rename one."
              sourcing={projects ? "live" : "unwired"}
              sourceNote={
                projects
                  ? "Rows, counts and every field shown come from GET /projects, and creating and renaming go to POST /projects and PATCH /projects/{id}. Until this panel existed nothing under apps/web called any of them, so the project_id the knowledge routes and the graph route filter on could only ever be null. A failed read is drawn as unreadable, never as an empty list, and a 200 carrying rows with no usable id is drawn as neither. Archiving is accepted by the patch route and is deliberately not offered here."
                  : "The projects panel is not mounted on this build."
              }
            >
              {projects}
            </TierPanel>

            <TierPanel
              title="Knowledge"
              purpose="The corpus DEVON recalls from, a search that runs against it, and the measured distances between its items drawn as a graph."
              sourcing={knowledge ? "partial" : "unwired"}
              sourceNote={
                knowledge
                  ? "Items, the source breakdown and search come from the knowledge routes. The graph below reads GET /knowledge/graph, whose distances are pgvector cosine distance, the minimum over each pair of items chunks. The first attempt at this panel was PULLED on 2026-09-10 for reading a payload shape the route does not send and stating a measurement over a query that had not run; it ships now with its fixtures generated from the route itself, so the two cannot drift apart again. It still refuses to call a simulated or unavailable embedding real, and it names every cap that bit."
                  : "The knowledge panel is not mounted on this build."
              }
            >
              {knowledge}
            </TierPanel>

            <TierPanel
              title="Learning"
              purpose="The memories and skills every agent plan is handed, and the only place to write one."
              sourcing={learning ? "live" : "unwired"}
              sourceNote={
                learning
                  ? "Rows and counts come from the two learning routes. Until this panel existed nothing in the estate wrote to either table, so the store was empty by construction. A failed read is drawn as unreadable, never as empty."
                  : "The learning panel is not mounted on this build."
              }
            >
              {learning}
            </TierPanel>

            <TierPanel
              title="Long term memory"
              purpose="Everything stored about you that the Council can recall, and the only place to write, edit, pause or destroy one."
              sourcing={memory ? "live" : "unwired"}
              sourceNote={
                memory
                  ? "Rows and every field shown come back from GET /memory. The four routes were finished and tested before this panel and nothing under apps/web called them, so the Council's own memories about the owner accumulated where the owner could not read them. DELETE on that route is a hard delete, so deleting here is a two step ruling and the panel names what would be lost. A failed read is drawn as unreadable, never as empty."
                  : "The memory panel is not mounted on this build."
              }
            >
              {memory}
            </TierPanel>
          </Tier>

          <Tier
            id="execution"
            index="Tier 3"
            title="Execution and Pipeline"
            summary="What the estate is spending, and what is running outside this repository."
          >
            <TierPanel
              title="Workflows"
              purpose="The automation engine, the runs it has made, and the human ruling on every step that would write something."
              sourcing={workflows ? "live" : "unwired"}
              sourceNote={
                workflows
                  ? "Read from the six workflow paths. Until this panel existed nothing under apps/web called one of the engine's ten operations, so a workflow could not be composed and the approval gate the engine is built around had nobody standing at it. The payload a gate would write is rendered in full and its sha256 seal is sent back with the approval, so the server refuses a ruling given over a payload the run has since moved past. A gate the API reports as diverged carries no approve control at all."
                  : "The workflow door is not mounted on this build."
              }
            >
              {workflows}
            </TierPanel>

            <TierPanel
              title="Token budget and cost"
              purpose="Today's spend against the hard cap that refuses at 429."
              sourcing="live"
              sourceNote="Read from the usage route over the provider usage ledger. Warning thresholds are not built, so nothing here claims a warning was sent."
            >
              <CostPanel />
            </TierPanel>

            <TierPanel
              title="n8n operations"
              purpose="Execution telemetry, retries, queue depth and version sync against GitHub."
              sourcing="partial"
              sourceNote="GET /n8n/executions reads the configured instances, so recent executions and failure counts are sourced. Retries, queue depth and version sync are not built and are not drawn. Any plan cap is stated by configuration and the spend against it is estimated from the execution id gap, never measured, and is refused entirely when the ids of a window contradict its clock. No date is projected: every date on this tier is observed from an execution row or stated by configuration. Workflow names are NOT in the executions response, so a row is labelled by its workflow id and says so."
            >
              <ExecutionHubPanel />
            </TierPanel>
          </Tier>
        </div>
      </div>
    </main>
  );
}

function Tier({
  id,
  index,
  title,
  summary,
  children,
}: {
  id: string;
  index: string;
  title: string;
  summary: string;
  children: ReactNode;
}) {
  return (
    <section id={id} className="scroll-mt-24">
      <div className="mb-3">
        <p className="text-[11px] font-semibold uppercase tracking-[0.24em] text-white/50">
          {index}
        </p>
        <h2 className="mt-0.5 text-lg font-semibold tracking-tight text-white">{title}</h2>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-white/50">{summary}</p>
      </div>
      <div className="grid min-w-0 gap-4 [&>*]:min-w-0 lg:grid-cols-2">{children}</div>
    </section>
  );
}
