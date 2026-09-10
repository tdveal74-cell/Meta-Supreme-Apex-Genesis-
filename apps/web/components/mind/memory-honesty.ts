/**
 * The long term memory panel's arithmetic and its refusals, kept out of the
 * component so both can be proved.
 *
 * WHY THIS FILE EXISTS
 *
 * app/api/v1/memory.py is four complete routes over the `memories` table:
 * GET and POST on /memory, PATCH and DELETE on /memory/{id}. They are
 * registered (app/api/v1/router.py:48) and exercised by test_memory_api.py.
 * Measured on 32883cf with `grep -rn "/memory" apps/web`, the only hit under
 * apps/web was a comment in app/page.tsx saying no component calls it. So the
 * capability was real, tested, and unreachable: a door.
 *
 * It was also the subject of a claim. The landing page advertised "long-term
 * memory you can edit or delete" until 2026-09-10, when the sentence was
 * removed for being untrue rather than the surface being built.
 *
 * A panel over these routes can lie in four distinct ways, and each one is
 * decided here by a pure function with no DOM and no network, because that is
 * the only version scripts/memory-check.ts can mutate and re-measure:
 *
 *   1. A FAILED READ DRAWN AS AN EMPTY STORE. The estate's single most repeated
 *      defect (see the header of scripts/control-check.ts, and the whole of
 *      learning-honesty.ts). "The route answered 500" and "you have stored
 *      nothing" are opposite facts with opposite responses. readMemoryVerdict
 *      refuses to merge them, and it refuses `pending` and `locked` into either.
 *
 *   2. AN INVENTED FIELD. MemoryResponse declares importance and is_active as
 *      required, but a degraded or older payload can arrive without them, and
 *      the metadata dict carries `origin` only because the two writers happen to
 *      stamp it. Defaulting importance to 5 or is_active to true would put a
 *      number on the screen that nobody sent. Every field on ParsedMemory is
 *      nullable for that reason, and summarizeMemories keeps rows of unknown
 *      activity in their own bucket rather than folding them into active.
 *
 *   3. A ONE TAP DELETE. `delete_memory` calls `db.delete(memory)`: a hard
 *      delete with no archive, no tombstone and no undo, on a row the Council
 *      may have written and the owner may never have read. So deleting is a two
 *      step ruling here, and the two steps are a state machine in this file
 *      rather than a boolean in a component: armDelete only arms, and
 *      confirmDelete refuses any id that is not the armed one.
 *
 *   4. STORED READ AS RECALLED. app/services/memory.py:80 recalls by LEXICAL
 *      token overlap: words of three or more alphanumeric characters shared
 *      between the message and the memory, scored `overlap x importance/10 x
 *      exp(-age_days/30)`, top 5 by default, and `is_active` false is excluded
 *      from the query outright. So a stored memory reaches a Council answer only
 *      when its words appear in that message, and a paused one never does.
 *      describeRecall says which of those a row is in, and says it per row
 *      rather than as a footnote.
 */

/* ------------------------------------------------------------------ */
/* The wire shape                                                     */
/* ------------------------------------------------------------------ */

/**
 * One memory as the route sends it, with every field except the id nullable.
 *
 * The id is not nullable because a row with no id cannot be edited, cannot be
 * deleted and cannot be keyed in a list, so it is not a row this panel can
 * offer anything for. Those are counted as malformed and dropped, never
 * rendered with a made up identifier.
 */
export type ParsedMemory = {
  id: string;
  /** The text itself. null when the route sent the row without one. */
  content: string | null;
  /** One of preference, context, decision, lesson, pattern, other. */
  memoryType: string | null;
  /** 1 to 10. NEVER defaulted to the server's 5: that would be this panel's number. */
  importance: number | null;
  /** false is the pause. null means the route did not say, which is not the same as active. */
  isActive: boolean | null;
  /** metadata.origin. "user" for a POST from here, "council_interaction" for a Council write. */
  origin: string | null;
  /** metadata.conversation_id, present only on Council writes. */
  conversationId: string | null;
  projectId: string | null;
  createdAt: string | null;
  updatedAt: string | null;
};

/**
 * The result of reading the list route's body.
 *
 * `not-a-list` is its own shape rather than an empty list, because a 200 that
 * carries an object is a read that did not work. Falling through to `[]` there
 * would render "you have stored nothing" over a store nobody counted.
 */
export type ParsedMemories =
  | { shape: "not-a-list"; sawType: string }
  | { shape: "list"; rows: ParsedMemory[]; malformed: number };

export type MemoryTally = {
  total: number;
  /** is_active true. These are the only rows recall can reach at all. */
  active: number;
  /** is_active false. Stored, visible, edited on request, never recalled. */
  paused: number;
  /** is_active absent from the payload. Counted apart, never added to either. */
  unknownActivity: number;
  /** Rows the parser refused for having no usable id. */
  malformed: number;
};

/* ------------------------------------------------------------------ */
/* Parsing, which never fills a gap                                    */
/* ------------------------------------------------------------------ */

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" && value.length > 0 ? value : null;
}

function intOrNull(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function boolOrNull(value: unknown): boolean | null {
  return typeof value === "boolean" ? value : null;
}

/** What the payload actually was, for a message that names it. */
function describeType(value: unknown): string {
  if (value === null) return "null";
  if (Array.isArray(value)) return "an array";
  return typeof value;
}

export function parseMemoryPayload(payload: unknown): ParsedMemories {
  if (!Array.isArray(payload)) {
    return { shape: "not-a-list", sawType: describeType(payload) };
  }
  const rows: ParsedMemory[] = [];
  let malformed = 0;
  for (const raw of payload) {
    if (!isRecord(raw)) {
      malformed += 1;
      continue;
    }
    const id = stringOrNull(raw.id);
    if (id === null) {
      malformed += 1;
      continue;
    }
    const metadata = isRecord(raw.metadata) ? raw.metadata : null;
    rows.push({
      id,
      content: stringOrNull(raw.content),
      memoryType: stringOrNull(raw.memory_type),
      importance: intOrNull(raw.importance),
      isActive: boolOrNull(raw.is_active),
      origin: metadata === null ? null : stringOrNull(metadata.origin),
      conversationId: metadata === null ? null : stringOrNull(metadata.conversation_id),
      projectId: stringOrNull(raw.project_id),
      createdAt: stringOrNull(raw.created_at),
      updatedAt: stringOrNull(raw.updated_at),
    });
  }
  return { shape: "list", rows, malformed };
}

export function summarizeMemories(parsed: ParsedMemories): MemoryTally | null {
  // A payload that was not a list supports no tally at all. Returning zeroes
  // here is the same lie as an empty state over a failed read.
  if (parsed.shape !== "list") return null;
  let active = 0;
  let paused = 0;
  let unknownActivity = 0;
  for (const row of parsed.rows) {
    if (row.isActive === true) active += 1;
    else if (row.isActive === false) paused += 1;
    else unknownActivity += 1;
  }
  return {
    total: parsed.rows.length,
    active,
    paused,
    unknownActivity,
    malformed: parsed.malformed,
  };
}

/* ------------------------------------------------------------------ */
/* The verdict ladder                                                  */
/* ------------------------------------------------------------------ */

/** One read of GET /memory, as the panel observes it. */
export type MemoryRead =
  | { state: "pending" }
  | { state: "locked" }
  | { state: "ok"; tally: MemoryTally }
  | { state: "failed"; detail: string };

export type MemoryVerdictCode =
  | "reading"
  | "locked"
  | "unreadable"
  /**
   * Rows came back and not one of them was usable. Added 2026-09-10: a payload
   * of three rows carrying no id parsed to zero rows with malformed 3, and the
   * `empty` rung below stated as fact that nothing is stored for this account
   * while an amber line two lines above said three rows had come back. The
   * surface rendered both halves of a contradiction. Rows arriving is not a
   * store being empty, in either direction.
   */
  | "unusable"
  | "empty"
  | "populated";

export type MemoryVerdict = {
  code: MemoryVerdictCode;
  label: string;
  /** "good" is reserved for a store that was read and holds something. */
  tone: "neutral" | "warn" | "good";
  sentence: string;
  /**
   * True only when the rows in hand ARE the store, so the panel may render a
   * list and call it complete. Every other code renders no list at all.
   */
  rowsAreTheStore: boolean;
};

/**
 * Rank one read into one honest verdict. Order is load bearing.
 *
 * `pending` and `locked` come first and are separate from each other: mid
 * flight is not a fact about the store, and no token in this browser means no
 * request was ever sent, so calling either a failed read would invent a
 * failure. `failed` outranks any count because a read that did not complete
 * supports no claim about contents in either direction. Only a completed read
 * that returned nothing may be called empty.
 */
export function readMemoryVerdict(read: MemoryRead): MemoryVerdict {
  if (read.state === "pending") {
    return {
      code: "reading",
      label: "READING MEMORY",
      tone: "neutral",
      sentence:
        "The request to the memory route is in flight. Nothing is claimed about the store until it answers.",
      rowsAreTheStore: false,
    };
  }

  if (read.state === "locked") {
    return {
      code: "locked",
      label: "MEMORY LOCKED",
      tone: "neutral",
      sentence:
        "No session token in this browser. Memories are scoped to one account, so no request was sent and nothing is claimed about what is stored. Sign in through Talk to DEVON.",
      rowsAreTheStore: false,
    };
  }

  if (read.state === "failed") {
    return {
      code: "unreadable",
      label: "MEMORY UNREADABLE",
      tone: "warn",
      sentence: `The memory store could not be read: ${read.detail}. This is a failed read, not an empty store, and it says nothing about what is stored. Nothing is listed below rather than an empty list being shown.`,
      rowsAreTheStore: false,
    };
  }

  const tally = read.tally;
  if (tally.total === 0 && tally.malformed > 0) {
    return {
      code: "unusable",
      label: "MEMORY UNUSABLE",
      tone: "warn",
      sentence: `The route answered and sent ${tally.malformed} ${plural(tally.malformed, "row", "rows")}, and not one of them carried a usable identifier, so none can be listed, edited or deleted. Rows arrived, so this is not a claim that the store is empty.`,
      rowsAreTheStore: false,
    };
  }

  if (tally.total === 0) {
    return {
      code: "empty",
      label: "MEMORY EMPTY",
      tone: "neutral",
      sentence:
        "The route answered and returned no rows. Nothing is stored for this account, so no memory can be recalled into a Council answer. Write one below to change that.",
      rowsAreTheStore: true,
    };
  }

  return {
    code: "populated",
    label: "MEMORY PRESENT",
    tone: "good",
    sentence: `The route answered with ${tally.total} ${plural(tally.total, "memory", "memories")}: ${tally.active} active, ${tally.paused} paused${
      tally.unknownActivity > 0
        ? `, and ${tally.unknownActivity} whose active flag the route did not send`
        : ""
    }. Recall reaches only the 200 most recently created active rows, and only those in the conversation's project or in no project at all, and only those sharing a word with the message, so a stored memory is not a guarantee of recall.`,
    rowsAreTheStore: true,
  };
}

function plural(count: number, one: string, many: string): string {
  return count === 1 ? one : many;
}

/* ------------------------------------------------------------------ */
/* What one row can and cannot do                                      */
/* ------------------------------------------------------------------ */

/**
 * Whether this row can reach a Council answer at all, stated per row.
 *
 * The three cases are genuinely different and the middle one is the reason this
 * is not a footnote: a paused memory is fully visible on this panel and can
 * never be recalled, which is exactly the shape an operator misreads.
 *
 * ALL THREE GATES ARE NAMED HERE, since 2026-09-10. The first version named
 * one, the word overlap, and an adversary measured the other two against the
 * real service rather than arguing them:
 *
 *  1. is_active, app/services/memory.py:87. A paused row is never a candidate.
 *  2. PROJECT SCOPE, app/services/memory.py:88-93. When the conversation has a
 *     project, the candidate set is narrowed to rows in that project or rows
 *     with no project at all. Measured: one active importance-10 row with a
 *     perfect word overlap, scoped to project alpha, was recalled for alpha and
 *     for no project and NOT recalled for project beta. The Council's own rows
 *     get a project_id from the conversation, so this is the live path.
 *  3. A 200 ROW CANDIDATE WINDOW, app/services/memory.py:95, applied after
 *     `order_by(created_at.desc())`. Measured: the same perfect row stopped
 *     being recalled once 200 newer active rows sharing no word with the message
 *     were added. persist_memory_candidates writes one to five rows per
 *     exchange plus a fallback, so an owner crosses 200 in roughly 40 to 200
 *     exchanges and from then on older rows can never be candidates whatever
 *     they say.
 *
 * Only then does the word overlap, the importance weighting, the 30 day decay
 * and the top 5 cut apply.
 */
export function describeRecall(row: ParsedMemory): string {
  if (row.isActive === false) {
    return "Paused. Recall filters on is_active, so this row is stored and visible here and can never reach a Council answer until it is resumed.";
  }
  if (row.isActive === null) {
    return "The route did not send an active flag for this row, so whether recall can reach it is not something this panel can state.";
  }
  const scope =
    row.projectId === null
      ? "It carries no project, so it is a candidate in every conversation."
      : "It is scoped to one project, so a conversation in a different project can never recall it.";
  return (
    `Active. ${scope} Recall then reads only the 200 most recently created active rows in scope, so a store larger than that leaves older rows out whatever they say. ` +
    "Within those it reaches an answer only when a message shares a word of three or more characters with it, ranked by importance and decayed over about 30 days, top 5."
  );
}

/** A field the route did not send is named as absent, never filled in. */
export function statedOr(value: string | null, absent: string): string {
  return value === null ? absent : value;
}

export function importanceLabel(value: number | null): string {
  return value === null ? "the route did not send an importance" : `${value} of 10`;
}

export function originLabel(origin: string | null): string {
  if (origin === null) return "the route did not say where this came from";
  if (origin === "user") return "written by hand from a surface like this one";
  if (origin === "council_interaction")
    return "written by the Council after an exchange, not by you";
  return origin;
}

/* ------------------------------------------------------------------ */
/* Filtering, which is a fifth way to draw an empty store               */
/* ------------------------------------------------------------------ */

export type FilterOutcome = {
  shown: ParsedMemory[];
  hiddenByFilter: number;
  /** The query as applied. "" means no filter was applied at all. */
  applied: string;
};

/**
 * Narrow the rows on screen without ever narrowing what the panel claims.
 *
 * A text filter is the fifth way this surface can render "you have stored
 * nothing" over a store that holds plenty, and it is the easiest one to ship by
 * accident: the list is simply short, no state is wrong, and the empty branch
 * that fires is the honest one for a different question. Rows a filter hid are
 * counted here so the panel can say which question it is answering.
 *
 * A row whose content the route did not send cannot be matched against, so it is
 * treated as hidden rather than silently kept or silently dropped.
 */
export function filterMemories(rows: ParsedMemory[], query: string): FilterOutcome {
  const applied = query.trim().toLowerCase();
  if (applied === "") {
    return { shown: rows, hiddenByFilter: 0, applied: "" };
  }
  const shown = rows.filter((row) => (row.content ?? "").toLowerCase().includes(applied));
  return { shown, hiddenByFilter: rows.length - shown.length, applied };
}

/**
 * The sentence a filter owes the reader, or null when it owes none.
 *
 * It names the stored total in every case, and it never contains the word the
 * empty verdict uses, because "nothing matched what you typed" and "nothing is
 * stored" are the two facts this function exists to keep apart.
 */
export function describeFilter(outcome: FilterOutcome, tally: MemoryTally): string | null {
  if (outcome.applied === "") return null;
  if (outcome.shown.length === 0) {
    return `No stored memory contains "${outcome.applied}". ${tally.total} ${plural(
      tally.total,
      "memory is",
      "memories are",
    )} stored for this account and ${outcome.hiddenByFilter} ${plural(
      outcome.hiddenByFilter,
      "is",
      "are",
    )} hidden by this filter, so this is a filter that matched nothing rather than a store that holds nothing.`;
  }
  return `Showing ${outcome.shown.length} of ${tally.total} stored, filtered on "${outcome.applied}". ${outcome.hiddenByFilter} hidden.`;
}

/* ------------------------------------------------------------------ */
/* Deletion: two steps, and what is lost said out loud                 */
/* ------------------------------------------------------------------ */

export type DeletionNotice = {
  headline: string;
  /** The exact text that stops existing, or a refusal when the route sent none. */
  losing: string;
  /** One line per fact that goes with it. Absent fields say so. */
  facts: string[];
  irreversible: string;
  /** The non destructive option, always offered beside the destructive one. */
  alternative: string;
};

export function describeDeletion(row: ParsedMemory): DeletionNotice {
  return {
    headline: "Delete this memory permanently?",
    losing:
      row.content === null
        ? "The route sent no content for this row, so this panel cannot show you what you would be deleting."
        : row.content,
    facts: [
      `Identifier ${row.id}`,
      `Type ${statedOr(row.memoryType, "not sent by the route")}`,
      `Importance ${importanceLabel(row.importance)}`,
      `Stored ${statedOr(row.createdAt, "at a time the route did not send")}`,
      `Origin ${originLabel(row.origin)}`,
    ],
    irreversible:
      "DELETE on this route is a hard delete. The row is removed from the database with no archive, no tombstone and no undo, and this panel cannot recover it. Council answers that already quoted it stay as they are; the source of them does not.",
    alternative:
      "Pausing keeps the row and its history and takes it out of recall, which is the reversible version of this.",
  };
}

/**
 * The delete gate.
 *
 * One armed id at a time, held apart from the component so a single tap can
 * never reach the route. Arming is not deleting and does not send anything;
 * confirmDelete is the only function that says a request may go, and it says so
 * only for the exact id that was armed.
 */
export type DeleteGate = { armedId: string | null };

export const DELETE_DISARMED: DeleteGate = { armedId: null };

export function armDelete(id: string): DeleteGate {
  // Arming a second row disarms the first by construction: the gate holds one
  // id, not a set, so there is no state in which two rows are one tap away.
  return { armedId: id };
}

export function disarmDelete(): DeleteGate {
  return { armedId: null };
}

export function deleteIsArmedFor(gate: DeleteGate, id: string): boolean {
  return gate.armedId !== null && gate.armedId === id;
}

export type DeleteRuling = { proceed: true } | { proceed: false; reason: string };

/**
 * The only place that may say a delete request is allowed to leave.
 *
 * It is deliberately not `gate.armedId === id` inline in a handler: the refusal
 * has to be a value a check can read, and the reason has to be a sentence the
 * panel can show rather than a silent no-op.
 */
export function confirmDelete(gate: DeleteGate, id: string): DeleteRuling {
  if (gate.armedId === null) {
    return {
      proceed: false,
      reason:
        "nothing is armed for deletion, so this would have been a one tap destructive action",
    };
  }
  if (gate.armedId !== id) {
    return {
      proceed: false,
      reason: `the armed row is ${gate.armedId} and this request named ${id}, so nothing was sent`,
    };
  }
  return { proceed: true };
}
