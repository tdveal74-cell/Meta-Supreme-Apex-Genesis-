// Pure helpers. No fetch, no React, so the rules can be reasoned about and
// exercised on their own.

import {
  PINNED_TOOL_RISK,
  approvalRequiredForRisk,
  type PinnedTool,
} from "./pinned-tool-risk.ts";
import {
  isToolRisk,
  type AgentTaskView,
  type ToolCatalogEntry,
  type ToolRisk,
} from "./readiness-types.ts";

// Where a risk answer came from. Displayed, because a pinned answer and a live
// one are not the same claim.
export type RiskSource = "catalog" | "manifest" | "unknown";

export type ResolvedTool = {
  name: string;
  risk: ToolRisk | null;
  approvalRequired: boolean | null;
  reversible: boolean | null;
  blastRadius: string | null;
  source: RiskSource;
};

// Order of concern, highest first. Rank 0 means nothing was resolved.
const RISK_RANK: Record<ToolRisk, number> = {
  blocked: 4,
  high_impact: 3,
  write: 2,
  read: 1,
};

export function riskRank(risk: ToolRisk | null): number {
  return risk ? RISK_RANK[risk] : 0;
}

export const RISK_LABEL: Record<ToolRisk, string> = {
  read: "READ",
  write: "WRITE",
  high_impact: "HIGH IMPACT",
  blocked: "BLOCKED",
};

export function buildCatalogIndex(
  entries: ToolCatalogEntry[] | null | undefined,
): Map<string, ToolCatalogEntry> {
  const index = new Map<string, ToolCatalogEntry>();
  for (const entry of entries || []) {
    if (entry && typeof entry.name === "string" && entry.name) {
      index.set(entry.name, entry);
    }
  }
  return index;
}

export function resolveTool(
  name: string,
  catalog: Map<string, ToolCatalogEntry>,
): ResolvedTool {
  const live = catalog.get(name);
  if (live && isToolRisk(live.risk)) {
    return {
      name,
      risk: live.risk,
      approvalRequired: Boolean(live.approval_required),
      reversible: Boolean(live.reversible),
      blastRadius: live.blast_radius || null,
      source: "catalog",
    };
  }

  const pinned: PinnedTool | undefined = PINNED_TOOL_RISK[name];
  if (pinned) {
    return {
      name,
      risk: pinned.risk,
      approvalRequired: approvalRequiredForRisk(pinned.risk),
      reversible: pinned.reversible,
      blastRadius: pinned.blastRadius,
      source: "manifest",
    };
  }

  // A tool the running API registered after the manifest was pinned, or a name
  // a plan carries that no registry ever had. Either way it is not knowledge,
  // so it is reported as unknown rather than defaulted to read.
  return {
    name,
    risk: null,
    approvalRequired: null,
    reversible: null,
    blastRadius: null,
    source: "unknown",
  };
}

export type TaskRiskSummary = {
  // The peak risk across the task's planned tool calls, or null when the plan
  // has no steps or nothing in it resolved.
  peak: ResolvedTool | null;
  // Distinct tool names named by the plan, in plan order.
  toolNames: string[];
  // Names that neither the live catalog nor the pinned manifest knew.
  unresolved: string[];
  // True when at least one resolved tool needs a human approval.
  approvalRequired: boolean;
};

export function summarizeTaskRisk(
  task: AgentTaskView,
  catalog: Map<string, ToolCatalogEntry>,
): TaskRiskSummary {
  const seen = new Set<string>();
  const toolNames: string[] = [];
  for (const step of task.plan?.steps || []) {
    const name = step?.tool_call?.name;
    if (typeof name === "string" && name && !seen.has(name)) {
      seen.add(name);
      toolNames.push(name);
    }
  }

  let peak: ResolvedTool | null = null;
  const unresolved: string[] = [];
  let approvalRequired = false;

  for (const name of toolNames) {
    const resolved = resolveTool(name, catalog);
    if (resolved.risk === null) {
      unresolved.push(name);
      continue;
    }
    if (resolved.approvalRequired) {
      approvalRequired = true;
    }
    if (riskRank(resolved.risk) > riskRank(peak?.risk ?? null)) {
      peak = resolved;
    }
  }

  return { peak, toolNames, unresolved, approvalRequired };
}

// Human readable elapsed time. Returns null for anything unparseable so the
// caller can say "unavailable" instead of printing a number it made up.
export function ageLabel(iso: string | null | undefined, now: number): string | null {
  if (!iso) return null;
  const then = Date.parse(iso);
  if (!Number.isFinite(then)) return null;
  const seconds = Math.round((now - then) / 1000);
  if (seconds < 0) return "in the future";
  if (seconds < 60) return `${seconds}s`;
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes}m ${seconds % 60}s`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours}h ${minutes % 60}m`;
  const days = Math.floor(hours / 24);
  return `${days}d ${hours % 24}h`;
}
