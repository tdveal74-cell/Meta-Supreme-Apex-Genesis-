import type { DecisionPackage } from "./council-types";

/**
 * Offline mock generator — always labeled simulated.
 * Produces a realistic Decision Package for UI development and zero-key demos.
 */
export function generateMockPackage(question: string): DecisionPackage {
  const runId = `sim_${Date.now().toString(36)}`;

  return {
    run_id: runId,
    timestamp: new Date().toISOString(),
    mode: "simulated",
    question: question.trim() || "Untitled decision",
    plurality_view:
      "Proceed with a focused pilot of the structured Council surface before expanding scope.",
    key_reasons: [
      "A narrow pilot surfaces real operator friction faster than a broad rebuild.",
      "The current flagship protocol already contains the necessary gates and labeling rules.",
      "Visible dissent and a hard human gate reduce the risk of confident but wrong consensus.",
      "Offline simulated runs remain fully usable while live providers are optional.",
    ],
    strongest_dissent: [
      {
        seat: "Skeptic",
        position: "Delay the pilot until role prompts are fully hardened.",
        argument:
          "Shipping a surface before the nine seats have precise anti-pattern instructions risks producing polished but shallow deliberation.",
      },
      {
        seat: "Guardian",
        position: "Keep the first version strictly offline-only.",
        argument:
          "Introducing any live path too early increases the chance of unlabeled or partially labeled intelligence reaching the operator.",
      },
    ],
    confidence_range: "62–74",
    unresolved_unknowns: [
      "How often the debate gate will actually fire on real questions",
      "Whether the current dissent presentation is dense enough for rapid scanning",
    ],
    open_questions: [
      "What is the first real decision you will run through this surface?",
      "Should the sticky action bar appear immediately or only after scrolling past Open Questions?",
    ],
    transcript_ref: `transcript_${runId}`,
  };
}
