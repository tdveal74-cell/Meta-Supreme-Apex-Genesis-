/**
 * The verdict ladders for the agent roster panel.
 *
 * WHY THIS FILE EXISTS
 *
 * GET /api/v1/agents and GET /api/v1/agents/{slug} (app/api/v1/agents.py) are
 * registered on the v1 router at app/api/v1/router.py:36 and, before this panel,
 * no fetch() anywhere under apps/web named either one. Measured on 2026-09-10 in
 * the worktree at 32883cf:
 *
 *   grep -rn "agents" apps/web --include=*.ts --include=*.tsx
 *
 * returned five hits and not one of them was a request. Three were prose, one was
 * a type for `council.agents` inside CapabilityDock, and one was
 * `catalog?.council?.agents?.length` rendering that array's LENGTH as the string
 * "9 agents". So the count leaked out through a different route's tool catalog and
 * the roster itself, every agent's purpose, mission, capabilities, limitations,
 * declared output shape and evaluation criteria, had no surface at all.
 *
 * A roster is a soft target for exactly the inversion the control plane critic
 * used on 2026-09-09 (see the header of scripts/control-check.ts): a read that
 * FAILED drawn as an estate that has NO AGENTS. Those are opposite facts. Nine
 * agents that cannot be listed is a broken read. Zero agents is a registry
 * finding. A list of blank cards says neither.
 *
 * FOUR THINGS THIS FILE REFUSES, each of them one line of code away
 *
 *  1. A failed read is never an empty roster, and a 401 or 403 is neither of
 *     those: it is a third fact, the deployment gating the read. There is no
 *     pre-flight token gate here on purpose. Measured against a real TestClient
 *     on 2026-09-10: GET /api/v1/agents answers 200 with no Authorization header
 *     at all, and 200 again with `Bearer garbage`, because app/api/v1/agents.py
 *     declares no dependency. A panel that refused to read without a token would
 *     be inventing a lock the route does not have. So the token is sent when the
 *     device holds one and the read is attempted either way, and a 401 or 403
 *     from a deployment that does gate it lands in its own state.
 *
 *  2. No count the list route did not send. AgentSummary carries six fields:
 *     slug, name, purpose, mission, version, is_active. It carries no
 *     capabilities, no limitations and no evaluation_criteria, so a roster row
 *     cannot say how many an agent declares. `declaredCount` returns null until
 *     the detail route has actually answered for that slug, and null renders as
 *     absent rather than as 0.
 *
 *  3. `is_active` on a LIST row is not evidence. list_agents() iterates
 *     services/agents/registry.py list_active_agents(), which filters on
 *     `a.is_active`, so every row it can possibly return has is_active true.
 *     Painting that as a green tick would be drawing the filter, not the agent.
 *     The DETAIL route is different: it reads AGENT_REGISTRY.get(slug) with no
 *     filter, so it serves an inactive agent that the list omits, and there the
 *     same field is a real measurement. activeClaim keeps the two apart.
 *
 *  4. output_format is typed Dict[str, Any] on the wire. Every one of the nine
 *     currently answers {"type": ..., "fields": [...]}, but the contract does not
 *     promise that, so describeOutputFormat walks whatever keys arrived instead
 *     of reaching for two it hopes are there.
 *
 * All of it is pure: no DOM, no network, no clock. scripts/roster-check.ts proves
 * the ladders, in the same arrangement as readLearningVerdict in
 * components/mind/learning-honesty.ts and readVerdict in
 * components/ledger/provenance-payload.ts.
 */

/* ------------------------------------------------------------------ */
/* The list read                                                       */
/* ------------------------------------------------------------------ */

/** The list route's outcome, as the panel observes it. */
export type RosterRead =
  | { state: "loading" }
  /**
   * The route answered 2xx and this many rows survived shape checking.
   *
   * `contradicted` counts the surviving rows whose own `is_active` came back
   * FALSE. list_active_agents() filters on that field, so the honest value is
   * always 0 and any other value means the route's filter is not what this
   * panel was built against. It is carried here rather than assumed because the
   * sentence below used to say "N active agents" with the word hardcoded, so a
   * route that stopped filtering would have been described as filtering.
   */
  | { state: "ok"; count: number; dropped: number; contradicted: number }
  /** 401 or 403. This deployment gates the read; the roster is not empty. */
  | { state: "unauthorized"; status: number }
  | { state: "failed"; detail: string };

export type RosterVerdictCode =
  | "reading"
  /** Rows arrived whose own is_active denies the filter that served them. */
  | "contradicted"
  | "unauthorized"
  | "unreadable"
  | "empty"
  | "populated";

export type RosterVerdict = {
  code: RosterVerdictCode;
  label: string;
  /** "good" is reserved for a roster that was read and holds agents. */
  tone: "neutral" | "warn" | "good";
  sentence: string;
};

/**
 * Rank one list read into one honest verdict. Order is load bearing.
 *
 * `reading` comes first because a request in flight is not a fact about the
 * registry in either direction. `unauthorized` and `unreadable` both outrank
 * `empty` and `populated` because a roster that was not read supports no claim
 * about what is in it.
 */
export function readRosterVerdict(list: RosterRead): RosterVerdict {
  if (list.state === "loading") {
    return {
      code: "reading",
      label: "ROSTER READING",
      tone: "neutral",
      sentence:
        "The list route has not answered yet. Nothing is claimed about the roster while the request is in flight.",
    };
  }

  if (list.state === "unauthorized") {
    return {
      code: "unauthorized",
      label: "ROSTER GATED",
      tone: "warn",
      sentence: `The roster route answered ${list.status}, so this deployment requires a session token for it. That is a gate on the read, not an empty roster, and it says nothing about how many agents are registered.`,
    };
  }

  if (list.state === "failed") {
    return {
      code: "unreadable",
      label: "ROSTER UNREADABLE",
      tone: "warn",
      sentence: `The roster could not be read: ${list.detail}. This is a failed read, not an empty roster, and it says nothing about which agents are registered.`,
    };
  }

  if (list.count === 0) {
    return {
      code: "empty",
      label: "ROSTER EMPTY",
      tone: "neutral",
      sentence:
        list.dropped > 0
          ? `The route answered and returned rows, but none of them carried the six fields this panel reads, so ${list.dropped} ${plural(list.dropped, "row", "rows")} ${plural(list.dropped, "was", "were")} dropped. Treat this as a payload mismatch rather than as a registry with no agents.`
          : "The route answered and returned no rows. Every agent in the registry is marked inactive, or the registry is empty. Nothing on this surface can change that: the registry is code, not a table.",
    };
  }

  const dropNote =
    list.dropped > 0
      ? ` ${list.dropped} further ${plural(list.dropped, "row", "rows")} did not carry the six fields this panel reads and ${plural(list.dropped, "is", "are")} not shown.`
      : "";

  if (list.contradicted > 0) {
    return {
      code: "contradicted",
      label: "ROSTER CONTRADICTS ITSELF",
      tone: "warn",
      sentence: `The route answered with ${list.count} ${plural(list.count, "agent", "agents")}, and ${list.contradicted} of them came back with is_active FALSE.${dropNote} list_active_agents() filters on exactly that field, so this list cannot be read as the active roster: either the filter is gone or something other than that route answered. No count here is a measurement of anything until that is settled.`,
    };
  }

  return {
    code: "populated",
    label: "ROSTER PRESENT",
    tone: "good",
    sentence: `The route answered with ${list.count} active ${plural(list.count, "agent", "agents")}, and every row it sent agrees it is active.${dropNote} The list is filtered to active agents by list_active_agents(), so an inactive agent is absent here and still reachable by slug.`,
  };
}

function plural(count: number, one: string, many: string): string {
  return count === 1 ? one : many;
}

/* ------------------------------------------------------------------ */
/* The list payload                                                    */
/* ------------------------------------------------------------------ */

/** One roster row, only ever built from fields the route actually sent. */
export type RosterRow = {
  slug: string;
  name: string;
  purpose: string;
  mission: string;
  version: string;
  isActive: boolean;
};

export type ParsedRoster = {
  rows: RosterRow[];
  /** Entries that arrived but did not carry the six fields, counted out loud. */
  dropped: number;
  /** False when the payload was not a JSON array at all. */
  wasArray: boolean;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function str(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

/**
 * Turn the list payload into rows, dropping anything that is not the shape
 * AgentSummary declares and reporting how many were dropped. A row missing a
 * field is not defaulted to an empty string: a blank purpose would read as an
 * agent that declares none.
 */
export function parseRosterPayload(raw: unknown): ParsedRoster {
  if (!Array.isArray(raw)) {
    return { rows: [], dropped: 0, wasArray: false };
  }
  const rows: RosterRow[] = [];
  let dropped = 0;
  for (const entry of raw) {
    if (!isRecord(entry)) {
      dropped += 1;
      continue;
    }
    const slug = str(entry.slug);
    const name = str(entry.name);
    const purpose = str(entry.purpose);
    const mission = str(entry.mission);
    const version = str(entry.version);
    const isActive = entry.is_active;
    if (
      slug === null ||
      name === null ||
      purpose === null ||
      mission === null ||
      version === null ||
      typeof isActive !== "boolean"
    ) {
      dropped += 1;
      continue;
    }
    rows.push({ slug, name, purpose, mission, version, isActive });
  }
  return { rows, dropped, wasArray: true };
}

/* ------------------------------------------------------------------ */
/* is_active, and which route it means something on                     */
/* ------------------------------------------------------------------ */

export type ActiveClaim = {
  text: string;
  /**
   * False when the field could not have read otherwise on this route, so the
   * panel must not draw it as a measurement.
   */
  informative: boolean;
};

/**
 * What `is_active` is worth, per route.
 *
 * On the list it is worth nothing: list_agents() only iterates the agents that
 * already passed an `is_active` filter, so true is the only value a row can
 * carry. On the detail route it is a real read, because get_agent() does
 * AGENT_REGISTRY.get(slug) with no filter and will serve an inactive agent.
 */
export function activeClaim(source: "list" | "detail", isActive: boolean): ActiveClaim {
  if (source === "list") {
    if (isActive === false) {
      // The list branch used to ignore this argument entirely and return
      // "listed as active" for a row whose own payload said is_active false,
      // contradicting the payload the panel was holding in the same render.
      // Found by an adversary on 2026-09-10. It needs list_active_agents()'s
      // filter to be gone for the row to exist, which
      // test_agents_roster_surface.py catches in ci.yml's unfiltered lane, so
      // reaching here is a finding rather than a state to describe: say so.
      return {
        informative: true,
        text:
          "sent as INACTIVE by the list route, which contradicts that route's own filter. " +
          "list_active_agents() serves only active agents, so either the filter is gone or something " +
          "other than that route answered. Do not read this row as a measurement of anything.",
      };
    }
    return {
      informative: false,
      text: "listed as active, which is the only value this route can return",
    };
  }
  return {
    informative: true,
    text: isActive
      ? "active in the registry"
      : "inactive in the registry, and still served by slug",
  };
}

/* ------------------------------------------------------------------ */
/* The detail read                                                     */
/* ------------------------------------------------------------------ */

export type OutputFormatLine = { key: string; value: string };

/** One agent's full definition, again only from fields that arrived. */
export type AgentDetail = RosterRow & {
  capabilities: string[];
  limitations: string[];
  evaluationCriteria: string[];
  outputFormat: OutputFormatLine[];
  /** False when output_format was absent or was not a JSON object. */
  outputFormatWasObject: boolean;
};

export type DetailRead =
  /** Never asked for. Not a failure and not an absence of capabilities. */
  | { state: "idle" }
  | { state: "loading" }
  | { state: "ok"; detail: AgentDetail }
  /** 404. The registry does not hold this slug. */
  | { state: "missing"; status: number }
  | { state: "unauthorized"; status: number }
  | { state: "failed"; detail: string }
  /** 2xx whose body was not an AgentDetail. */
  | { state: "malformed"; detail: string };

export type DetailNote = {
  code: DetailRead["state"];
  label: string;
  tone: "neutral" | "warn";
  sentence: string;
};

/**
 * What to say about one agent's detail read.
 *
 * The load bearing branch is `missing`. A 404 here is not "this agent declares
 * no capabilities": the slug came out of the list route a moment earlier, so a
 * 404 means the two routes disagree about the registry, which is a finding.
 * Rendering it as an empty capability list would hide it completely.
 */
export function describeDetail(read: DetailRead): DetailNote {
  switch (read.state) {
    case "idle":
      return {
        code: "idle",
        label: "NOT READ",
        tone: "neutral",
        sentence:
          "The detail route has not been asked for this agent. Its capabilities, limitations, declared output shape and evaluation criteria are unread, not empty.",
      };
    case "loading":
      return {
        code: "loading",
        label: "READING",
        tone: "neutral",
        sentence: "The detail route has not answered yet.",
      };
    case "missing":
      return {
        code: "missing",
        label: "SLUG NOT IN REGISTRY",
        tone: "warn",
        sentence: `The detail route answered ${read.status} for a slug the list route had just returned. The two routes disagree about the registry; this is not an agent that declares nothing.`,
      };
    case "unauthorized":
      return {
        code: "unauthorized",
        label: "DETAIL GATED",
        tone: "warn",
        sentence: `The detail route answered ${read.status}, so this deployment gates it. Nothing is claimed about what this agent declares.`,
      };
    case "failed":
      return {
        code: "failed",
        label: "DETAIL UNREADABLE",
        tone: "warn",
        sentence: `The detail could not be read: ${read.detail}. This is a failed read, not an agent with no capabilities.`,
      };
    case "malformed":
      return {
        code: "malformed",
        label: "DETAIL NOT THE SHAPE",
        tone: "warn",
        sentence: `The detail route answered but the body was not an agent definition: ${read.detail}. Nothing is claimed about what this agent declares.`,
      };
    case "ok":
      return {
        code: "ok",
        label: "DETAIL READ",
        tone: "neutral",
        sentence: `Read from the detail route: ${read.detail.capabilities.length} declared ${plural(read.detail.capabilities.length, "capability", "capabilities")}, ${read.detail.limitations.length} ${plural(read.detail.limitations.length, "limitation", "limitations")}, ${read.detail.evaluationCriteria.length} evaluation ${plural(read.detail.evaluationCriteria.length, "criterion", "criteria")}.`,
      };
  }
}

/**
 * The count of something an agent declares, or null when nothing has measured it.
 *
 * The list route sends none of these three arrays, so every roster row starts at
 * null. Returning 0 instead would put a number on the surface that no route ever
 * sent, which is the defect this whole file is arranged against.
 */
export function declaredCount(
  read: DetailRead,
  field: "capabilities" | "limitations" | "evaluationCriteria",
): number | null {
  if (read.state !== "ok") return null;
  return read.detail[field].length;
}

/** Render a count that may not exist. Never "0" for "unmeasured". */
export function countLabel(count: number | null): string {
  return count === null ? "not read" : String(count);
}

/* ------------------------------------------------------------------ */
/* The detail payload                                                  */
/* ------------------------------------------------------------------ */

function stringList(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  const out: string[] = [];
  for (const item of value) {
    if (typeof item !== "string") return null;
    out.push(item);
  }
  return out;
}

/**
 * Flatten output_format without assuming its keys.
 *
 * The wire type is Dict[str, Any]. All nine agents happen to answer
 * {"type": ..., "fields": [...]} today, and a panel that reads `raw.fields`
 * directly is a panel that renders nothing the day one of them stops. So this
 * walks the object's own keys and stringifies each value by its actual JSON kind.
 */
export function describeOutputFormat(raw: unknown): {
  lines: OutputFormatLine[];
  wasObject: boolean;
} {
  if (!isRecord(raw)) return { lines: [], wasObject: false };
  const lines: OutputFormatLine[] = [];
  for (const [key, value] of Object.entries(raw)) {
    lines.push({ key, value: renderValue(value) });
  }
  return { lines, wasObject: true };
}

function renderValue(value: unknown): string {
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  if (value === null) return "null";
  if (Array.isArray(value)) {
    return value.map((item) => renderValue(item)).join(", ");
  }
  if (isRecord(value)) {
    return Object.entries(value)
      .map(([key, inner]) => `${key}: ${renderValue(inner)}`)
      .join("; ");
  }
  return String(value);
}

/**
 * Build an AgentDetail from the detail route's body, or null when the body is
 * not that. Null becomes the `malformed` state in the panel rather than an agent
 * whose arrays are all empty.
 */
export function parseAgentDetail(raw: unknown): AgentDetail | null {
  if (!isRecord(raw)) return null;
  const base = parseRosterPayload([raw]);
  if (base.rows.length !== 1) return null;
  const capabilities = stringList(raw.capabilities);
  const limitations = stringList(raw.limitations);
  const evaluationCriteria = stringList(raw.evaluation_criteria);
  if (capabilities === null || limitations === null || evaluationCriteria === null) {
    return null;
  }
  const outputFormat = describeOutputFormat(raw.output_format);
  return {
    ...base.rows[0],
    capabilities,
    limitations,
    evaluationCriteria,
    outputFormat: outputFormat.lines,
    outputFormatWasObject: outputFormat.wasObject,
  };
}

/* ------------------------------------------------------------------ */
/* Status to state                                                     */
/* ------------------------------------------------------------------ */

/**
 * Map one HTTP status onto the list read's failure states.
 *
 * Split out so the mapping is provable without a fetch: 401 and 403 must reach
 * `unauthorized` and nothing else may, and no status may ever reach an `ok`.
 */
export function listReadForStatus(status: number, statusText: string): RosterRead {
  if (status === 401 || status === 403) return { state: "unauthorized", status };
  const suffix = statusText ? ` ${statusText}` : "";
  return { state: "failed", detail: `the roster route answered ${status}${suffix}` };
}

/** The same mapping for the detail route, where 404 is its own fact. */
export function detailReadForStatus(status: number, statusText: string): DetailRead {
  if (status === 404) return { state: "missing", status };
  if (status === 401 || status === 403) return { state: "unauthorized", status };
  const suffix = statusText ? ` ${statusText}` : "";
  return { state: "failed", detail: `the detail route answered ${status}${suffix}` };
}
