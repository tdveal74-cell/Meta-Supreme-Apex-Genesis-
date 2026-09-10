/**
 * The decision record's arithmetic and its refusals, kept out of the component
 * so both can be proved without a DOM and without a network.
 *
 * WHY THIS FILE EXISTS
 *
 * app/api/v1/decisions.py is a complete, tested, registered subsystem:
 * GET and POST /decisions, POST /decisions/from-message, GET and PATCH
 * /decisions/{id}, registered at app/api/v1/router.py:50 and exercised by
 * test_decisions_api.py. Measured on commit 32883cf with a grep across
 * apps/web and packages/ui, the only occurrences of the word were a comment in
 * app/council/deliberate/page.tsx explaining that nothing calls it and the
 * CLAIMS entry in scripts/honesty-check.ts holding the landing page to that
 * fact. So the estate could record the human final call and no person could
 * reach the capability, and nothing failed.
 *
 * handleDecision on the deliberate page was a console.info. A visitor pressed
 * "Record decision", the page told them their call was held in that tab only,
 * and a reload discarded it.
 *
 * THE FOUR WAYS A DECISION RECORD CAN LIE, AND WHERE EACH IS REFUSED
 *
 *   1. A FAILED READ DRAWN AS AN EMPTY RECORD. "the route answered 500" and
 *      "you have never decided anything" are opposite facts. An empty record is
 *      a finding, and the response is to record a decision. A failed read is a
 *      nothing, and the response is to fix the read. readDecisionsVerdict keeps
 *      them apart and scripts/decisions-check.ts walks every state.
 *   2. AN UNKNOWN DRAWN AS A NEGATIVE. Whether a Council exchange has already
 *      been recorded is only knowable when the decision list was actually read.
 *      trackedState returns "unknown" rather than "untracked" whenever it was
 *      not, because "not yet recorded" invites a person to record a duplicate.
 *   3. A TRUNCATED FIELD PRESENTED AS THE RECORD. The route caps question at
 *      2000 characters and the free text fields at 20000. Silently cutting a
 *      question to fit stores a different question under the human's name, so
 *      prepareCreate and prepareRuling REFUSE and say by how much. CLAUDE.md:
 *      "Never widen a rule on speculation about intent. If a transformation
 *      could change a number, a name, a path or a line of dialogue, refuse
 *      instead."
 *   4. A REQUEST FOR ANOTHER ROUND FILED AS A DECISION. PATCH /decisions/{id}
 *      advances status to "decided" on its own whenever chosen_option is set
 *      and no status is sent (app/api/v1/decisions.py, update_decision). Choice
 *      D on the deliberate page asks the Council to look again, which is the
 *      opposite of a final call, so rulingFor carries an explicit status on
 *      every ruling and sends "open" for D. Nothing here relies on a server
 *      default, for the same reason SkillProposalGate sends promote explicitly.
 *
 * Nothing in this file invents a figure. A field the route did not send stays
 * null, and null is rendered as "the route did not say" rather than as zero.
 */

import type { DecisionPackage, HumanDecision } from "../../lib/council-types.ts";

/* ------------------------------------------------------------------ */
/* The wire shape                                                     */
/* ------------------------------------------------------------------ */

/**
 * One decision as the route sends it. Every field except the id is nullable,
 * because a field the route omitted must stay visibly absent. `options: null`
 * means the route did not send an option list; `options: []` means it sent an
 * empty one. Those are different facts and this type keeps them different.
 */
export type DecisionRow = {
  id: string;
  question: string | null;
  options: string[] | null;
  recommendation: string | null;
  chosenOption: string | null;
  outcome: string | null;
  outcomeNotes: string | null;
  status: string | null;
  projectId: string | null;
  /** metadata.origin: "manual" for a created decision, "council" from a message. */
  origin: string | null;
  /** metadata.message_id, present only on council origin rows. */
  messageId: string | null;
  conversationId: string | null;
  agentsConsulted: string[] | null;
  createdAt: string | null;
  updatedAt: string | null;
};

function isRecord(value: unknown): value is Record<string, unknown> {
  return typeof value === "object" && value !== null && !Array.isArray(value);
}

function stringOrNull(value: unknown): string | null {
  return typeof value === "string" ? value : null;
}

function stringListOrNull(value: unknown): string[] | null {
  if (!Array.isArray(value)) return null;
  const strings = value.filter((entry): entry is string => typeof entry === "string");
  // A list that lost entries to the filter is not the list the route sent, so
  // it is refused rather than silently shortened.
  return strings.length === value.length ? strings : null;
}

/**
 * Read one row, or refuse it. A row with no usable id cannot be re-read, ruled
 * on, or matched against a message, so there is nothing honest to draw for it.
 */
export function parseDecisionRow(value: unknown): DecisionRow | null {
  if (!isRecord(value)) return null;
  const id = stringOrNull(value.id);
  if (!id) return null;
  const meta = isRecord(value.metadata) ? value.metadata : null;
  return {
    id,
    question: stringOrNull(value.question),
    options: stringListOrNull(value.options),
    recommendation: stringOrNull(value.recommendation),
    chosenOption: stringOrNull(value.chosen_option),
    outcome: stringOrNull(value.outcome),
    outcomeNotes: stringOrNull(value.outcome_notes),
    status: stringOrNull(value.status),
    projectId: stringOrNull(value.project_id),
    origin: meta ? stringOrNull(meta.origin) : null,
    messageId: meta ? stringOrNull(meta.message_id) : null,
    conversationId: meta ? stringOrNull(meta.conversation_id) : null,
    agentsConsulted: meta ? stringListOrNull(meta.agents_consulted) : null,
    createdAt: stringOrNull(value.created_at),
    updatedAt: stringOrNull(value.updated_at),
  };
}

export type ParsedDecisionList = {
  rows: DecisionRow[];
  /** Entries the parser refused. Reported, never dropped in silence. */
  malformed: number;
};

/**
 * Read a list payload, or refuse the whole thing. A payload that is not an
 * array is a failed read, not an empty record: returning `{rows: []}` here is
 * exactly the collapse this module exists to prevent, so it returns null and
 * the caller has to say the route did not send a list.
 */
export function parseDecisionList(payload: unknown): ParsedDecisionList | null {
  if (!Array.isArray(payload)) return null;
  const rows: DecisionRow[] = [];
  let malformed = 0;
  for (const entry of payload) {
    const row = parseDecisionRow(entry);
    if (row) rows.push(row);
    else malformed += 1;
  }
  return { rows, malformed };
}

/* ------------------------------------------------------------------ */
/* The verdict ladder                                                 */
/* ------------------------------------------------------------------ */

/** The list route's outcome, as the panel observes it. */
export type DecisionsRead =
  | { state: "locked" }
  | { state: "ok"; rows: DecisionRow[]; malformed: number }
  | { state: "failed"; detail: string };

export type DecisionVerdictCode = "locked" | "unreadable" | "empty" | "present";

export type DecisionVerdict = {
  code: DecisionVerdictCode;
  label: string;
  /** "good" is reserved for a record that was read and holds something. */
  tone: "neutral" | "warn" | "good";
  sentence: string;
};

/** Status counts, taken only from rows that were actually read. */
export type StatusTally = {
  open: number;
  decided: number;
  reviewed: number;
  archived: number;
  /** Rows whose status the route did not send. Never folded into open. */
  unstated: number;
  /** Rows carrying a status this panel has no column for. */
  other: number;
};

export function summarizeStatuses(rows: DecisionRow[]): StatusTally {
  const tally: StatusTally = {
    open: 0,
    decided: 0,
    reviewed: 0,
    archived: 0,
    unstated: 0,
    other: 0,
  };
  for (const row of rows) {
    if (row.status === null) tally.unstated += 1;
    else if (row.status === "open") tally.open += 1;
    else if (row.status === "decided") tally.decided += 1;
    else if (row.status === "reviewed") tally.reviewed += 1;
    else if (row.status === "archived") tally.archived += 1;
    else tally.other += 1;
  }
  return tally;
}

function plural(count: number, one: string, many: string): string {
  return count === 1 ? one : many;
}

/**
 * Rank one read into an honest verdict. Order is load bearing.
 *
 * `locked` outranks `unreadable` because no session token means no request was
 * ever sent, so calling that a failed read would invent a failure. `unreadable`
 * outranks both `empty` and `present` because a record that was not read
 * supports no claim about its contents in either direction.
 */
export function readDecisionsVerdict(read: DecisionsRead): DecisionVerdict {
  if (read.state === "locked") {
    return {
      code: "locked",
      label: "DECISION RECORD LOCKED",
      tone: "neutral",
      sentence:
        "No session token in this browser. The decision record is scoped to one account, so nothing is read and nothing is claimed about it. Sign in through Talk to DEVON.",
    };
  }

  if (read.state === "failed") {
    return {
      code: "unreadable",
      label: "DECISION RECORD UNREADABLE",
      tone: "warn",
      sentence: `The decision record could not be read: ${read.detail}. This is a failed read, not an empty record, and it says nothing about what has or has not been decided on this account.`,
    };
  }

  const malformedNote =
    read.malformed > 0
      ? ` ${read.malformed} ${plural(read.malformed, "entry", "entries")} came back without a usable id and ${plural(read.malformed, "was", "were")} refused rather than drawn.`
      : "";

  if (read.rows.length === 0) {
    return {
      code: "empty",
      label: "DECISION RECORD EMPTY",
      tone: "neutral",
      sentence:
        "The route answered and returned no rows. Nothing has been recorded on this account, so no ruling made on this site is accountable yet." +
        malformedNote,
    };
  }

  const tally = summarizeStatuses(read.rows);
  const parts: string[] = [];
  if (tally.decided > 0) parts.push(`${tally.decided} decided`);
  if (tally.open > 0) parts.push(`${tally.open} still open`);
  if (tally.reviewed > 0) parts.push(`${tally.reviewed} reviewed`);
  if (tally.archived > 0) parts.push(`${tally.archived} archived`);
  if (tally.other > 0) parts.push(`${tally.other} carrying another status`);
  if (tally.unstated > 0) parts.push(`${tally.unstated} whose status the route did not send`);

  return {
    code: "present",
    label: "DECISION RECORD PRESENT",
    tone: "good",
    sentence:
      `The route answered with ${read.rows.length} ${plural(read.rows.length, "decision", "decisions")}: ${parts.join(", ")}. ` +
      "A recorded ruling is a record of what a person chose. It is not a claim that anything acted on it, and nothing on this surface runs an effect." +
      malformedNote,
  };
}

/* ------------------------------------------------------------------ */
/* Whether a Council exchange is already on the record                */
/* ------------------------------------------------------------------ */

/**
 * "tracked" and "untracked" are both claims about the record. "unknown" is the
 * only honest answer when the record was not read, and it is the default here
 * rather than an afterthought: telling a person an exchange is NOT yet recorded
 * when you could not read the record invites them to record it twice.
 */
export type TrackedState = "tracked" | "untracked" | "unknown";

export function trackedState(messageId: string, read: DecisionsRead): TrackedState {
  if (read.state !== "ok") return "unknown";
  if (!messageId) return "unknown";
  return read.rows.some((row) => row.messageId === messageId) ? "tracked" : "untracked";
}

/* ------------------------------------------------------------------ */
/* The ruling                                                          */
/* ------------------------------------------------------------------ */

/**
 * The four rulings the deliberate page offers, in the order its buttons offer
 * them. Recorded as the decision's option list so the record shows what the
 * human could have chosen, not only what they did choose.
 */
export const COUNCIL_OPTIONS = [
  "A. Accept the plurality view",
  "B. Accept with modifications",
  "C. Override with an alternative",
  "D. Request another round on a specific point",
] as const;

export type Ruling = {
  /** The option text, sent verbatim as chosen_option. */
  chosenOption: string;
  /** The human's own words, or null when they wrote none. Never an empty string. */
  note: string | null;
  /**
   * Sent explicitly on every ruling. The route advances an open decision to
   * "decided" by itself when this key is absent, and choice D is not a
   * decision.
   */
  status: "open" | "decided";
  /** Why the status is what it is, in a sentence a person reads before the record does. */
  statusReason: string;
};

const DECIDED_REASON =
  "The final call is on the record and the decision is closed. A later review can reopen it.";

function blankToNull(value: string | undefined): string | null {
  const trimmed = (value ?? "").trim();
  return trimmed.length > 0 ? trimmed : null;
}

export function rulingFor(decision: HumanDecision): Ruling {
  if (decision.choice === "A") {
    return {
      chosenOption: COUNCIL_OPTIONS[0],
      note: null,
      status: "decided",
      statusReason: DECIDED_REASON,
    };
  }
  if (decision.choice === "B") {
    return {
      chosenOption: COUNCIL_OPTIONS[1],
      note: blankToNull(decision.modification),
      status: "decided",
      statusReason: DECIDED_REASON,
    };
  }
  if (decision.choice === "C") {
    return {
      chosenOption: COUNCIL_OPTIONS[2],
      note: blankToNull(decision.alternative),
      status: "decided",
      statusReason: DECIDED_REASON,
    };
  }
  return {
    chosenOption: COUNCIL_OPTIONS[3],
    note: blankToNull(decision.focus),
    status: "open",
    statusReason:
      "Asking the Council to look again is not a final call, so this is recorded as still open rather than decided.",
  };
}

/**
 * The same ruling shape, built from an option a person picked on an already
 * recorded decision rather than from a deliberate page package. `open` is
 * offered here too, because a decision can be annotated without being closed.
 */
export function rulingForOption(
  option: string,
  note: string | undefined,
  status: "open" | "decided",
): Ruling {
  return {
    chosenOption: option,
    note: blankToNull(note),
    status,
    statusReason:
      status === "decided"
        ? DECIDED_REASON
        : "Recorded against the decision without closing it, so it stays open.",
  };
}

/* ------------------------------------------------------------------ */
/* Bodies, and the refusals that stop a field being reshaped to fit    */
/* ------------------------------------------------------------------ */

/** app/api/v1/decisions.py, DecisionCreate.question. */
export const QUESTION_MAX = 2000;
/** app/api/v1/decisions.py, DecisionCreate.recommendation and DecisionUpdate.outcome_notes. */
export const LONG_TEXT_MAX = 20_000;
/** app/api/v1/decisions.py, DecisionUpdate.chosen_option. */
export const CHOSEN_OPTION_MAX = 2000;

export type Prepared<T> = { ok: true; body: T } | { ok: false; reason: string };

export type CreateBody = {
  question: string;
  options: string[];
  recommendation: string;
};

export type RulingBody = {
  chosen_option: string;
  status: "open" | "decided";
  outcome_notes?: string;
};

function tooLong(what: string, actual: number, cap: number): string {
  return (
    `${what} is ${actual} characters and the record accepts ${cap}. ` +
    "Nothing was sent and nothing was shortened, because a trimmed question is a different question and a trimmed note is a different note."
  );
}

/**
 * The create body for a Council package.
 *
 * The recommendation carries the run's own mode. A record that did not say the
 * run was simulated would read, later, as nine agents having deliberated.
 * mock-deliberation.ts stamps every package it makes as "simulated" and the
 * deliberate page labels it on screen; that label has to survive into the
 * record or the label was decoration.
 */
export function prepareCreate(pkg: DecisionPackage): Prepared<CreateBody> {
  const question = pkg.question.trim();
  if (question.length === 0) {
    return {
      ok: false,
      reason: "The package carries no question, so there is nothing to record.",
    };
  }
  if (question.length > QUESTION_MAX) {
    return { ok: false, reason: tooLong("The question", question.length, QUESTION_MAX) };
  }

  const recommendation =
    `Council run ${pkg.run_id}, mode ${pkg.mode}.\n\n` +
    `Plurality position: ${pkg.plurality_view}`;
  if (recommendation.length > LONG_TEXT_MAX) {
    return {
      ok: false,
      reason: tooLong("The Council's plurality position", recommendation.length, LONG_TEXT_MAX),
    };
  }

  return {
    ok: true,
    body: { question, options: [...COUNCIL_OPTIONS], recommendation },
  };
}

/**
 * The PATCH body for a ruling. `status` is always present and `outcome_notes`
 * is present only when the human wrote something, so an empty note is never
 * stored as an empty string pretending to be a note.
 */
export function prepareRuling(ruling: Ruling): Prepared<RulingBody> {
  if (ruling.chosenOption.trim().length === 0) {
    return { ok: false, reason: "No option was chosen, so there is no ruling to record." };
  }
  if (ruling.chosenOption.length > CHOSEN_OPTION_MAX) {
    return {
      ok: false,
      reason: tooLong("The chosen option", ruling.chosenOption.length, CHOSEN_OPTION_MAX),
    };
  }
  if (ruling.note !== null && ruling.note.length > LONG_TEXT_MAX) {
    return { ok: false, reason: tooLong("The note", ruling.note.length, LONG_TEXT_MAX) };
  }
  const body: RulingBody = { chosen_option: ruling.chosenOption, status: ruling.status };
  if (ruling.note !== null) body.outcome_notes = ruling.note;
  return { ok: true, body };
}

/* ------------------------------------------------------------------ */
/* What the write actually achieved                                    */
/* ------------------------------------------------------------------ */

/**
 * Recording a ruling on the deliberate page is two requests: a POST that
 * creates the decision and a PATCH that records the call. Either can fail on
 * its own, so "created but not ruled on" is a real state and it is neither a
 * success nor a clean failure. It is named here so the page cannot round it to
 * whichever neighbour is easier to render.
 */
export type WriteOutcome =
  | { kind: "idle" }
  | { kind: "locked" }
  | { kind: "refused"; reason: string }
  | { kind: "sending"; step: "create" | "rule" }
  | { kind: "create-failed"; detail: string }
  | { kind: "rule-failed"; decisionId: string; detail: string }
  | { kind: "recorded"; decisionId: string; ruling: Ruling };

/** True only for the one outcome in which the human's call reached the record. */
export function isRecorded(outcome: WriteOutcome): boolean {
  return outcome.kind === "recorded";
}

/**
 * The bold line above the sentence, one per outcome kind.
 *
 * This used to be a ternary chain in app/council/deliberate/page.tsx built from
 * `recorded`, `halfWritten` and a `failed` flag that listed `create-failed` and
 * `refused` and NOT `locked`. So a signed-out visitor who pressed Record
 * decision fell through to the else branch and read "Sending your call to the
 * decision record" forever, over a request that was never sent. Found by an
 * adversary on 2026-09-10, in shipped code.
 *
 * It is a switch on the union here rather than a chain of booleans there for the
 * reason the chain failed: the compiler makes a missing kind an error, and a
 * check can enumerate every kind and assert that only one of them is allowed to
 * claim something is in flight.
 */
export function writeHeadline(outcome: WriteOutcome): { text: string; tone: "neutral" | "bad" | "good" } {
  switch (outcome.kind) {
    case "idle":
      return { text: "Sending your call to the decision record.", tone: "neutral" };
    case "sending":
      return { text: "Sending your call to the decision record.", tone: "neutral" };
    case "locked":
      return { text: "Your call was NOT sent.", tone: "bad" };
    case "refused":
      return { text: "Your call was NOT sent.", tone: "bad" };
    case "create-failed":
      return { text: "Your call is NOT on the decision record.", tone: "bad" };
    case "rule-failed":
      return { text: "Your call is NOT on the decision record.", tone: "bad" };
    case "recorded":
      return { text: "Your call is on the decision record.", tone: "good" };
  }
}

export function describeWriteOutcome(outcome: WriteOutcome): string {
  switch (outcome.kind) {
    case "idle":
      return "";
    case "locked":
      return "No session token in this browser, so nothing was sent and your call is not recorded anywhere. The decision record is scoped to one account. Sign in through Talk to DEVON and rule again.";
    case "refused":
      return `Nothing was sent. ${outcome.reason}`;
    case "sending":
      return outcome.step === "create"
        ? "Creating the decision."
        : "Recording your call on it.";
    case "create-failed":
      return `Your call is NOT recorded: the decision could not be created, ${outcome.detail}. Nothing was written, so there is no half record to clean up.`;
    case "rule-failed":
      return (
        `Half recorded. Decision ${outcome.decisionId} exists with the Council position on it, and your call was NOT written: ${outcome.detail}. ` +
        "The decision is open on the record and can be ruled on from the decision record panel."
      );
    case "recorded":
      return (
        `Recorded as decision ${outcome.decisionId}. ${outcome.ruling.chosenOption}. ${outcome.ruling.statusReason} ` +
        (outcome.ruling.note === null
          ? "You wrote no note with it, so the record carries the option and not a reason."
          : "Your note is on the record with it.")
      );
  }
}
