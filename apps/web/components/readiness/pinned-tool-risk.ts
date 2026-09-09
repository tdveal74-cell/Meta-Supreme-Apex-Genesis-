// Risk and blast radius for every tool DEVON's agent runtime registers.
//
// PROVENANCE. Transcribed by script out of docs/devon/hermes-surface.json,
// which its own _readme describes as generated from the code and never hand
// typed, and which test_devon_hermes_surface.py fails on when the code and the
// manifest disagree. Twenty tools were pinned there when this file was written.
//
// This map is a PIN, not the live truth. The live truth is
// GET /api/v1/agent-tasks/tools, whose `tools` array is ToolSpec.to_dict() and
// carries the same four fields plus `approval_required` and `parameters`. The
// matrix prefers that read and falls back here only when the catalog request
// fails, and it labels which of the two answered.
//
// Regenerating: re-run the manifest generator named in hermes-surface.json,
// then rebuild this file from it. Do not edit a row by hand.

import type { ToolRisk } from "./readiness-types";

export type PinnedTool = {
  risk: ToolRisk;
  reversible: boolean;
  blastRadius: string;
};

export const PINNED_TOOL_RISK: Readonly<Record<string, PinnedTool>> = {
  "browser.fetch": { risk: "read", reversible: true, blastRadius: "read-only HTTP GET to one allowlisted host" },
  "browser.navigate": { risk: "write", reversible: true, blastRadius: "one approved navigation record to an allowlisted host" },
  "council.consult": { risk: "read", reversible: true, blastRadius: "provider tokens only; no external effect" },
  "editforge.control": { risk: "high_impact", reversible: false, blastRadius: "one retry or cancellation for one EditForge command" },
  "editforge.execution": { risk: "read", reversible: true, blastRadius: "one authenticated EditForge execution read" },
  "editforge.render": { risk: "high_impact", reversible: false, blastRadius: "one governed EditForge render command for one project cut" },
  "editforge.status": { risk: "read", reversible: true, blastRadius: "one authenticated read from the EditForge health boundary" },
  "editforge.validate": { risk: "read", reversible: true, blastRadius: "local validation of one proposed EditForge intent" },
  "github.create_branch": { risk: "write", reversible: false, blastRadius: "one new Git branch in one allowlisted repository" },
  "github.create_pull_request": { risk: "write", reversible: false, blastRadius: "one pull request in one allowlisted repository" },
  "github.merge_pull_request": { risk: "high_impact", reversible: false, blastRadius: "target branch history and repository state for one pull request" },
  "github.pull_request": { risk: "read", reversible: true, blastRadius: "read-only GitHub pull request request in one allowlisted repository" },
  "github.read_file": { risk: "read", reversible: true, blastRadius: "read-only GitHub contents request in one allowlisted repository" },
  "github.repo_status": { risk: "read", reversible: true, blastRadius: "read-only GitHub API request in one allowlisted repository" },
  "github.write_file": { risk: "high_impact", reversible: false, blastRadius: "one commit affecting one file in one allowlisted repository" },
  "operator.command": { risk: "high_impact", reversible: false, blastRadius: "local operator host and resources reachable by the API process user" },
  "operator.read": { risk: "read", reversible: true, blastRadius: "read-only process on the configured operator host" },
  "runtime.propose_skill": { risk: "write", reversible: true, blastRadius: "one SkillProposal row awaiting human decision" },
  "runtime.schedule_goal": { risk: "write", reversible: true, blastRadius: "one delayed goal row in the schedule table" },
  "runtime.spawn_subagent": { risk: "write", reversible: true, blastRadius: "one child AgentTask row and one parent-child link" },
};

export const PINNED_TOOL_COUNT = Object.keys(PINNED_TOOL_RISK).length;

// ToolSpec.approval_required in services/agent_runtime/tools.py is exactly
// `self.risk in {ToolRisk.WRITE, ToolRisk.HIGH_IMPACT}`, so the pinned rows can
// answer it without the live catalog. The live catalog sends the field itself
// and the matrix uses that value when it has it.
export function approvalRequiredForRisk(risk: ToolRisk): boolean {
  return risk === "write" || risk === "high_impact";
}
