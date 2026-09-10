// Mount point for the roster slice. apps/web/app/control/ belongs to another
// slice; it should be able to import from one path and get the component plus the
// pure honesty logic and wire types it may want for its own props.
export { AgentRosterPanel, type AgentRosterPanelProps } from "./AgentRosterPanel.tsx";
export {
  activeClaim,
  countLabel,
  declaredCount,
  describeDetail,
  describeOutputFormat,
  detailReadForStatus,
  listReadForStatus,
  parseAgentDetail,
  parseRosterPayload,
  readRosterVerdict,
  type ActiveClaim,
  type AgentDetail,
  type DetailNote,
  type DetailRead,
  type OutputFormatLine,
  type ParsedRoster,
  type RosterRead,
  type RosterRow,
  type RosterVerdict,
  type RosterVerdictCode,
} from "./agent-roster-honesty.ts";
