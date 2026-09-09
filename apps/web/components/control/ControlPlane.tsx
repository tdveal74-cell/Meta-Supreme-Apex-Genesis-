"use client";

import Link from "next/link";
import type { ReactNode } from "react";
import { ExecutionHubPanel } from "@/components/control/ExecutionHubPanel";
import { CostPanel } from "@/components/control/CostPanel";
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
};

export function ControlPlane({ readiness, provenance, presence, knowledge }: ControlPlaneProps) {
  return (
    <main className="min-h-screen bg-[#05080c] text-[#e8edf2]">
      <div className="mx-auto flex min-h-screen max-w-[1600px] flex-col px-4 py-4 sm:px-6 lg:px-8">
        <header className="sticky top-0 z-30 -mx-4 mb-5 border-b border-white/10 bg-[#05080c]/90 px-4 py-3 backdrop-blur sm:-mx-6 sm:px-6 lg:-mx-8 lg:px-8">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div className="flex items-center gap-3">
              <div className="flex h-10 w-10 items-center justify-center rounded-xl border border-amber-400/30 bg-amber-400/10">
                <span className="text-xs font-bold tracking-[0.16em] text-amber-300">DV</span>
              </div>
              <div>
                <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-amber-300/80">
                  DEVON
                </p>
                <h1 className="text-base font-semibold tracking-tight text-white">
                  Control plane
                </h1>
              </div>
            </div>

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
          </div>
        </header>

        <p className="mb-6 max-w-3xl text-xs leading-relaxed text-white/45">
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
              sourceNote="Frames, the sliding window buffer and the interrupt path are real against the presence service. The face is a procedural placeholder until an owned rig exists, and no LiveKit or Cartesia endpoint has been reached, so audio is unproven here."
            >
              {presence ?? (
                <p className="text-xs text-white/45">
                  The presence stage is not mounted on this build.{" "}
                  <Link href="/presence" className="underline decoration-white/30">
                    Open it on its own page
                  </Link>
                  .
                </p>
              )}
            </TierPanel>

            <TierPanel
              title="Knowledge"
              purpose="The corpus DEVON recalls from, and a search that runs against it."
              sourcing={knowledge ? "partial" : "unwired"}
              sourceNote={
                knowledge
                  ? "Items and search results are read from the knowledge routes. No route exposes vector activations or edges between the indexes, so no graph is drawn."
                  : "The knowledge panel is not mounted on this build."
              }
            >
              {knowledge}
            </TierPanel>
          </Tier>

          <Tier
            id="execution"
            index="Tier 3"
            title="Execution and Pipeline"
            summary="What the estate is spending, and what is running outside this repository."
          >
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
              sourcing="unwired"
              sourceNote="No route in this repository reads the n8n instance. The tier shows the API's own health instead of inventing execution data."
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
        <p className="text-[10px] font-semibold uppercase tracking-[0.24em] text-white/35">
          {index}
        </p>
        <h2 className="mt-0.5 text-lg font-semibold tracking-tight text-white">{title}</h2>
        <p className="mt-1 max-w-2xl text-xs leading-relaxed text-white/45">{summary}</p>
      </div>
      <div className="grid gap-4 lg:grid-cols-2">{children}</div>
    </section>
  );
}
