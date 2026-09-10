/**
 * The project list's parser and its verdict ladder, kept out of the component
 * so both can be proved without a DOM.
 *
 * WHY THIS FILE EXISTS
 *
 * `app/api/v1/projects.py` registers four operations and, before this panel,
 * had no caller under `apps/web`: `GET /api/v1/projects`, `POST /api/v1/projects`,
 * `GET /api/v1/projects/{id}` and `PATCH /api/v1/projects/{id}`. Measured on
 * commit 32883cf with `grep -rn "projects" --include=*.ts --include=*.tsx
 * apps/web packages/ui`, which returned nothing at all. So the scoping construct
 * the rest of the estate reads was real, complete, and unreachable: nobody could
 * create a project, so `project_id` on `GET /api/v1/knowledge/graph`
 * (app/api/v1/knowledge_graph.py:104) and on the knowledge item and search
 * bodies (app/api/v1/knowledge.py:34, :43, :53) could only ever be null.
 *
 * The narrow claim is the true one, and it is the only one made here: the gap
 * was a WEB surface, not a caller in the abstract. The routes are registered in
 * `app/api/v1/router.py:35` and reachable by anything holding a bearer token.
 *
 * THE LIE THIS MODULE EXISTS TO REFUSE
 *
 * A panel over a list route has one dominant way to be wrong, and it is the one
 * the control plane critic exploited on 2026-09-09 (see the header of
 * `apps/web/scripts/control-check.ts`): a read that FAILED rendered as a list
 * that is EMPTY. On this door those are not merely different, they are opposite
 * instructions. An empty list means "create a project", and the right response
 * is the form below it. A failed read means "the route is down", and the right
 * response is to fix the route; creating a project against it would be writing
 * into something whose state nobody can see.
 *
 * A third state sits between them and is easy to collapse into either: the route
 * answered 200 with rows this parser could not use. That is not an empty list,
 * because rows arrived, and it is not a populated one, because none of them can
 * be named or renamed. It gets its own rung.
 *
 * Same arrangement, and the same reasoning, as `readLearningVerdict` in
 * `components/mind/learning-honesty.ts` and `parseGraphPayload` in
 * `components/mind/knowledge-graph.ts`.
 */

/* ------------------------------------------------------------------ */
/* The wire shape                                                     */
/* ------------------------------------------------------------------ */

/**
 * One project as the route sends it.
 *
 * Every field except the id is nullable here on purpose. `ProjectResponse`
 * (app/api/v1/projects.py:33) declares `description` and `organization_id` as
 * genuinely optional, and the rest are only as reliable as the payload that
 * actually arrives. A name defaulted to the id, or a status defaulted to
 * "active", is a value this panel invented, and the panel has no way to know it
 * later. So an absent field stays null all the way to the render, where it is
 * shown as absent.
 */
export type ProjectRow = {
  id: string;
  name: string | null;
  description: string | null;
  status: string | null;
  organizationId: string | null;
  createdAt: string | null;
  updatedAt: string | null;
};

export type ParsedProjects = {
  /** The rows that survived, in the order the route sent them. */
  rows: ProjectRow[];
  /**
   * Rows refused for being unreadable: not an object at all, or carrying no
   * usable id. These are counted apart from duplicates because the sentence the
   * operator reads names a reason, and until 2026-09-10 it named this one for a
   * duplicate too. A person sent looking for a null id in the payload would not
   * have found one.
   */
  malformedRows: number;
  /**
   * Rows refused for repeating an id already seen. The row is well formed and
   * its id is usable; it is refused because drawing it twice would send two
   * rename requests to the same project.
   */
  duplicateRows: number;
  /** Rows kept whose name the route did not send, so they cannot be labelled. */
  rowsWithoutName: number;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function textOrNull(value: unknown): string | null {
  return typeof value === "string" && value.trim() !== "" ? value : null;
}

/**
 * Read a project list payload without trusting any part of it.
 *
 * Returns null when the body is not an array. `list_projects` is declared
 * `response_model=List[ProjectResponse]` (app/api/v1/projects.py:44), so a body
 * that is not an array is a failed read rather than a short one, and the caller
 * must report it as such. Falling through to an empty array here is exactly the
 * inversion this file exists to prevent: it would render a broken route as an
 * account with no projects.
 *
 * Everything else comes back with the rows that survived plus a count of the
 * rows that did not, so the panel can report the shortfall instead of quietly
 * showing less than it was sent.
 */
export function parseProjectsPayload(raw: unknown): ParsedProjects | null {
  if (!Array.isArray(raw)) return null;

  const rows: ProjectRow[] = [];
  let malformedRows = 0;
  let duplicateRows = 0;
  let rowsWithoutName = 0;
  const seen = new Set<string>();

  for (const entry of raw) {
    if (!isRecord(entry)) {
      malformedRows += 1;
      continue;
    }
    const id = textOrNull(entry.id);
    if (id === null) {
      // A row with no id cannot be renamed: the PATCH path is built from it.
      malformedRows += 1;
      continue;
    }
    if (seen.has(id)) {
      // A duplicate id would put one project on the panel twice and send two
      // rename requests to the same place. Counted apart from the line above
      // because the reason the operator is told has to be the real one.
      duplicateRows += 1;
      continue;
    }
    seen.add(id);
    const name = textOrNull(entry.name);
    if (name === null) rowsWithoutName += 1;
    rows.push({
      id,
      name,
      description: textOrNull(entry.description),
      status: textOrNull(entry.status),
      organizationId: textOrNull(entry.organization_id),
      createdAt: textOrNull(entry.created_at),
      updatedAt: textOrNull(entry.updated_at),
    });
  }

  return { rows, malformedRows, duplicateRows, rowsWithoutName };
}

/* ------------------------------------------------------------------ */
/* The verdict ladder                                                 */
/* ------------------------------------------------------------------ */

/** The list route's outcome, as the panel observes it. */
export type ProjectsRead =
  | { state: "locked" }
  | { state: "ok"; count: number; malformed: number; duplicates: number }
  | { state: "failed"; detail: string };

export type ProjectsVerdictCode = "locked" | "unreadable" | "unusable" | "empty" | "populated";

export type ProjectsVerdict = {
  code: ProjectsVerdictCode;
  label: string;
  /** "good" is reserved for a list that was read and holds a usable row. */
  tone: "neutral" | "warn" | "good";
  sentence: string;
};

/**
 * Rank one read into one honest verdict. The order is load bearing.
 *
 * `locked` outranks `unreadable` because with no token no request was ever
 * sent, so calling that a failed read would invent a failure that did not
 * happen. `unreadable` outranks everything below it because a list that was not
 * read supports no claim about its contents in either direction. `unusable`
 * outranks `empty` because rows did arrive: the route is not telling us the
 * account has no projects, it is telling us something this panel cannot read.
 */
export function readProjectsVerdict(read: ProjectsRead): ProjectsVerdict {
  if (read.state === "locked") {
    return {
      code: "locked",
      label: "PROJECTS LOCKED",
      tone: "neutral",
      sentence:
        "No session token in this browser. Projects are scoped to one owner, so no request was sent and nothing is claimed about how many exist.",
    };
  }

  if (read.state === "failed") {
    return {
      code: "unreadable",
      label: "PROJECTS UNREADABLE",
      tone: "warn",
      sentence: `The project list could not be read: ${read.detail}. This is a failed read, not an empty list, and it says nothing about how many projects exist.`,
    };
  }

  if (read.count === 0 && read.malformed + read.duplicates > 0) {
    const sent = read.malformed + read.duplicates;
    return {
      code: "unusable",
      label: "PROJECTS UNUSABLE",
      tone: "warn",
      sentence: `The route answered and sent ${sent} ${plural(sent, "row", "rows")}, and not one of them survived: ${refusalReasons(read)}. Rows arrived, so this is not an empty list, and none of them can be shown or renamed.`,
    };
  }

  if (read.count === 0) {
    return {
      code: "empty",
      label: "NO PROJECTS",
      tone: "neutral",
      sentence:
        "The route answered and returned no rows. You own no projects, so nothing in the estate is scoped to one yet and every project_id the knowledge routes accept can only be null. Create one below to change that.",
    };
  }

  const dropped = read.malformed + read.duplicates;
  const refused =
    dropped > 0
      ? ` ${dropped} further ${plural(dropped, "row was", "rows were")} refused: ${refusalReasons(read)}. So this list is shorter than what the route sent.`
      : "";
  return {
    code: "populated",
    label: "PROJECTS PRESENT",
    tone: "good",
    sentence: `The route answered: ${read.count} ${plural(read.count, "project", "projects")} owned by this account.${refused}`,
  };
}

function plural(count: number, one: string, many: string): string {
  return count === 1 ? one : many;
}

/**
 * The refusal reasons, each named only when it actually happened.
 *
 * The single sentence this replaced said "refused for carrying no usable id"
 * for every refusal, including a duplicate, whose id is perfectly usable. An
 * operator told that would go looking for a null id in the payload and not find
 * one, which is worse than being told nothing.
 */
function refusalReasons(read: { malformed: number; duplicates: number }): string {
  const parts: string[] = [];
  if (read.malformed > 0) {
    parts.push(
      `${read.malformed} ${plural(read.malformed, "was not an object or carried", "were not objects or carried")} no usable id`,
    );
  }
  if (read.duplicates > 0) {
    parts.push(
      `${read.duplicates} repeated an id already sent, so ${plural(read.duplicates, "it was", "they were")} dropped rather than drawn twice`,
    );
  }
  return parts.join("; ");
}
