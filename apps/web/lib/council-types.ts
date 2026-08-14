/**
 * Decision Package contract — locked in Phase 2
 * Do not loosen these shapes without updating the UI contract.
 */

export type CouncilMode = "simulated" | "live";

export type CouncilSeat =
  | "Strategist"
  | "Analyst"
  | "Skeptic"
  | "Guardian"
  | "Engineer"
  | "Architect"
  | "Oracle"
  | "Librarian"
  | "Creator";

export interface DissentEntry {
  seat: CouncilSeat | string;
  position: string;
  argument: string;
}

export interface DecisionPackage {
  run_id: string;
  timestamp: string;
  mode: CouncilMode;
  question: string;
  plurality_view: string;
  key_reasons: string[];
  strongest_dissent: DissentEntry[];
  confidence_range: string;
  unresolved_unknowns: string[];
  open_questions: string[];
  transcript_ref?: string;
}

export type HumanDecision =
  | { choice: "A" }
  | { choice: "B"; modification: string }
  | { choice: "C"; alternative: string }
  | { choice: "D"; focus: string };
