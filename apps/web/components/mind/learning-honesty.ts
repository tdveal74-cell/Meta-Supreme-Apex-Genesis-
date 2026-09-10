/**
 * The verdict ladder for DEVON's learning store panel.
 *
 * WHY THIS FILE EXISTS
 *
 * The learning store has two list routes and, before this panel, no surface at
 * all: `GET /agent-tasks/learning/memories` and `GET /agent-tasks/learning/skills`
 * had no caller anywhere in the repository, so every plan DEVON made was handed
 * two empty lists and nobody could see it.
 *
 * A panel over those routes has exactly one way to lie, and it is the same one
 * the control plane critic exploited on 2026-09-09 (see the header of
 * scripts/control-check.ts): a read that FAILED rendered as a store that is
 * EMPTY. Those are opposite facts. An empty store is a finding, and the correct
 * response is to write a memory. A failed read is a nothing, and the correct
 * response is to fix the read. Collapsing them tells the operator the store is
 * fine when it may be full, or that DEVON has no learning when he may have
 * plenty.
 *
 * So the ladder lives here as a pure function with no DOM and no network, and
 * scripts/learning-check.ts proves the failed branch can never take a good
 * tone or an empty label. Same arrangement, and the same reasoning, as
 * readVerdict in components/ledger/provenance-payload.ts.
 */

/** One route's outcome, as the panel observes it. */
export type LearningRead =
  | { state: "locked" }
  | { state: "ok"; count: number }
  | { state: "failed"; detail: string };

export type LearningVerdictCode = "locked" | "unreadable" | "empty" | "populated";

export type LearningVerdict = {
  code: LearningVerdictCode;
  label: string;
  /** "good" is reserved for a store that was read and holds something. */
  tone: "neutral" | "warn" | "good";
  sentence: string;
};

/**
 * Rank the two reads into one honest verdict. Order is load bearing.
 *
 * `locked` outranks `unreadable` because no session token means no request was
 * ever sent, so calling that a failed read would invent a failure. `unreadable`
 * outranks both `empty` and `populated` because a half read store supports no
 * claim about its contents in either direction.
 */
export function readLearningVerdict(
  memories: LearningRead,
  skills: LearningRead,
): LearningVerdict {
  if (memories.state === "locked" || skills.state === "locked") {
    return {
      code: "locked",
      label: "LEARNING LOCKED",
      tone: "neutral",
      sentence:
        "No session token in this browser. The store is per account, so nothing is read and nothing is claimed about it.",
    };
  }

  if (memories.state === "failed" || skills.state === "failed") {
    const detail =
      memories.state === "failed" ? memories.detail : (skills as { detail: string }).detail;
    return {
      code: "unreadable",
      label: "LEARNING UNREADABLE",
      tone: "warn",
      sentence: `The learning store could not be read: ${detail}. This is a failed read, not an empty store, and it says nothing about what DEVON has stored.`,
    };
  }

  if (memories.count === 0 && skills.count === 0) {
    return {
      code: "empty",
      label: "LEARNING EMPTY",
      tone: "neutral",
      sentence:
        "Both routes answered and returned no rows. DEVON is planning with no memories and no skills, and every plan he makes is told so explicitly. Write a memory below to change that.",
    };
  }

  return {
    code: "populated",
    label: "LEARNING PRESENT",
    tone: "good",
    sentence: `Both routes answered: ${memories.count} ${plural(memories.count, "memory", "memories")} and ${skills.count} ${plural(skills.count, "skill", "skills")} stored. Only memories whose words overlap a task's goal reach that task's plan, so a stored memory is not a guarantee of recall.`,
  };
}

function plural(count: number, one: string, many: string): string {
  return count === 1 ? one : many;
}
