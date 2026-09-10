/**
 * The verdict ladders for the workflow door.
 *
 * WHY THIS FILE EXISTS
 *
 * The workflow engine is the largest unreachable capability in the estate. Ten
 * registered operations across six paths in app/api/v1/workflows.py, a
 * definition parser and an execution engine under services/workflows/, an
 * application layer in app/services/workflows.py, a cron dispatcher in
 * app/services/dispatcher.py driven by dispatch.py at the repository root, a
 * workflows table and workflow_runs behind it. Measured on this commit with a
 * grep across apps/web and packages/ui: the only mentions of "workflows" were
 * app/page.tsx and scripts/honesty-check.ts, both of them PROSE SAYING THE
 * SURFACE DOES NOT EXIST. Nothing fetched any of the ten. So a person could not
 * create a workflow, could not start a run, and above all could not answer the
 * approval gate that the whole engine is built around.
 *
 * A door over those routes has four ways to lie, and every one of them is a
 * single line of code away. They live here, as pure functions with no DOM and
 * no network, and scripts/workflow-check.ts proves each one:
 *
 *  1. A FAILED READ RENDERED AS AN EMPTY LIST. "the route answered 500" and
 *     "you have written no workflows yet" are opposite facts. The first is a
 *     broken read; the second is a finding whose correct answer is to compose
 *     one. This is the estate's single most repeated defect (see the header of
 *     scripts/learning-check.ts), so the ladders below refuse to merge them.
 *
 *  2. A GATE APPROVED OVER A PAYLOAD NOBODY SAW. app/services/workflows.py
 *     seals the rendered payload as a sha256 when the run pauses, and the API
 *     reports `diverged: true` when the live definition no longer renders that
 *     seal (app/api/v1/workflows.py, _pending_view). A door that offers an
 *     approve button over a diverged gate is offering to approve one payload
 *     while displaying another. readGateRuling is the only thing here that may
 *     say a gate is approvable, and it says so for exactly one shape.
 *
 *  3. APPROVAL SEMANTICS GUESSED RATHER THAN READ. Which step types pause for a
 *     human comes from GET /workflows/step-types, whose `requires_approval` is
 *     computed from EFFECT_STEP_TYPES in services/workflows/definition.py. A
 *     local copy of that set would be a second source of truth that drifts
 *     silently in the direction of "this one does not need approval". When the
 *     catalog cannot be read, the door must say the semantics are unknown
 *     rather than fall back to a guess.
 *
 *  4. A NUMBER INVENTED FROM AN ABSENCE. The route's own describe_definition
 *     returns `step_count: 0` for a definition that does not parse, which is
 *     not a measurement of anything. Rendering that as "0 steps" states a fact
 *     about a workflow nobody could read. readSummary refuses it.
 *
 * Nothing in this file performs an effect, and nothing in it can grant one.
 * Approval is a shape it describes, never one it decides.
 */

/* ------------------------------------------------------------------ */
/* Reads                                                                */
/* ------------------------------------------------------------------ */

/** One route's outcome, as the door observes it. */
export type WorkflowRead =
  | { state: "locked" }
  | { state: "ok"; count: number }
  | { state: "failed"; detail: string };

export type ListVerdictCode = "locked" | "unreadable" | "empty" | "populated";

export type ListVerdict = {
  code: ListVerdictCode;
  label: string;
  /** "good" is reserved for a list that was read and holds something. */
  tone: "neutral" | "warn" | "good";
  sentence: string;
};

/**
 * The verdict on the workflow list alone.
 *
 * `locked` outranks `unreadable` because with no session token no request was
 * sent, so calling it a failed read would invent a failure. `unreadable`
 * outranks `empty` and `populated` because a list that did not come back
 * supports no claim about its contents in either direction.
 */
export function readListVerdict(list: WorkflowRead): ListVerdict {
  if (list.state === "locked") {
    return {
      code: "locked",
      label: "WORKFLOWS LOCKED",
      tone: "neutral",
      sentence:
        "No session token in this browser. Workflows are scoped to one account, so nothing was requested and nothing is claimed about what exists.",
    };
  }

  if (list.state === "failed") {
    return {
      code: "unreadable",
      label: "WORKFLOWS UNREADABLE",
      tone: "warn",
      sentence: `The workflow list could not be read: ${list.detail}. This is a failed read, not an empty list, and it says nothing about how many workflows exist or whether any run is waiting on a ruling.`,
    };
  }

  // A count that is not a finite, non-negative whole number is not a
  // measurement, so it may not reach either of the two branches below. The type
  // says `number`, and an adversary on 2026-09-10 got null, undefined and NaN
  // past it by deleting the panel's non-array guard: every one of them fell
  // through to `populated` and rendered "The list route answered with undefined
  // workflows" in a GOOD tone. The ladder refuses that here rather than relying
  // on its one caller staying correct.
  if (!Number.isInteger(list.count) || list.count < 0) {
    return {
      code: "unreadable",
      label: "WORKFLOWS UNREADABLE",
      tone: "warn",
      sentence:
        "The list route answered, and what came back does not carry a countable list of workflows. This is a failed read, not an empty list, and it says nothing about how many workflows exist or whether any run is waiting on a ruling.",
    };
  }

  if (list.count === 0) {
    return {
      code: "empty",
      label: "NO WORKFLOWS",
      tone: "neutral",
      sentence:
        "The list route answered and returned no rows. Nothing has ever been composed on this account, so the engine has no definition to run. Compose one below.",
    };
  }

  return {
    code: "populated",
    label: "WORKFLOWS PRESENT",
    tone: "good",
    sentence: `The list route answered with ${list.count} ${list.count === 1 ? "workflow" : "workflows"}. A workflow that exists is not a workflow that runs: runs are started here by hand, and every effect step stops for a ruling.`,
  };
}

export type CatalogVerdictCode = "locked" | "unreadable" | "empty" | "read";

export type CatalogVerdict = {
  code: CatalogVerdictCode;
  label: string;
  tone: "neutral" | "warn" | "good";
  sentence: string;
  /**
   * Whether the door may state which step types pause for a human. False for
   * every outcome except a catalog that actually came back with types in it.
   */
  semanticsKnown: boolean;
};

/**
 * The verdict on the step catalog, kept apart from the list verdict on purpose.
 *
 * These answer two different questions. "How many workflows exist" is settled
 * by the list route alone, and withholding it because the catalog failed would
 * be refusing to report a fact the door is holding. What the catalog decides is
 * narrower and sharper: whether this door is allowed to say which steps are
 * gated, and therefore whether it may offer a composer at all.
 */
export function readCatalogVerdict(catalog: WorkflowRead): CatalogVerdict {
  if (catalog.state === "locked") {
    return {
      code: "locked",
      label: "CATALOG LOCKED",
      tone: "neutral",
      sentence:
        "No session token in this browser, so the step catalog was not requested. Which steps pause for a human is not known here and is not guessed.",
      semanticsKnown: false,
    };
  }

  if (catalog.state === "failed") {
    return {
      code: "unreadable",
      label: "CATALOG UNREADABLE",
      tone: "warn",
      sentence: `The step catalog could not be read: ${catalog.detail}. Which step types exist, and which of them stop for a ruling, is decided by that route and by nothing on this page, so no step types are offered while it is unreadable.`,
      semanticsKnown: false,
    };
  }

  if (catalog.count === 0) {
    return {
      code: "empty",
      label: "CATALOG EMPTY",
      tone: "warn",
      sentence:
        "The step catalog answered and listed no step types. A workflow needs at least one step, so nothing can be composed against this build.",
      semanticsKnown: false,
    };
  }

  return {
    code: "read",
    label: "CATALOG READ",
    tone: "good",
    sentence: `The step catalog answered with ${catalog.count} step ${catalog.count === 1 ? "type" : "types"}. Which of them require a ruling is read from that route, never assumed here.`,
    semanticsKnown: true,
  };
}

/* ------------------------------------------------------------------ */
/* Numbers that were reported, and numbers that were not                */
/* ------------------------------------------------------------------ */

export type Reported = { known: true; value: number } | { known: false };

/** A number the route sent, or an explicit absence. Never a zero standing in. */
export function reportedNumber(raw: unknown): Reported {
  if (typeof raw !== "number" || !Number.isFinite(raw)) return { known: false };
  return { known: true, value: raw };
}

/** Render helper: the number, or the words that say it was not sent. */
export function reportedLabel(raw: unknown, absent = "not reported"): string {
  const reported = reportedNumber(raw);
  return reported.known ? String(reported.value) : absent;
}

/* ------------------------------------------------------------------ */
/* A stored definition, as the list route describes it                  */
/* ------------------------------------------------------------------ */

export type SummaryFacts = {
  /** Whether the stored definition parses at all. */
  parses: boolean;
  /** The parse error, when it does not parse. */
  error: string | null;
  /**
   * null when the definition does not parse. describe_definition sends 0 in
   * that case and 0 steps is not what it measured.
   */
  stepCount: number | null;
  /** The step ids that stop for a ruling, empty only when the definition parses. */
  gatedSteps: string[];
  /** null when unknown rather than a default. */
  trigger: string | null;
  /**
   * What the API itself reported about whether this trigger fires on its own.
   * null when the definition does not parse, because the field is then a
   * default rather than a report.
   */
  awaitingDispatcher: boolean | null;
  sentence: string;
};

export function readSummary(raw: unknown): SummaryFacts {
  const summary = (raw ?? {}) as Record<string, unknown>;
  const parses = summary.valid === true;
  const error = typeof summary.error === "string" && summary.error ? summary.error : null;

  if (!parses) {
    return {
      parses: false,
      error,
      stepCount: null,
      gatedSteps: [],
      trigger: null,
      awaitingDispatcher: null,
      sentence: error
        ? `The stored definition does not parse: ${error}. It cannot be run, and no step count is shown because the route reports zero for a definition it could not read.`
        : "The stored definition does not parse and the route named no reason. It cannot be run, and no step count is shown because the route reports zero for a definition it could not read.",
    };
  }

  const count = reportedNumber(summary.step_count);
  const gated = Array.isArray(summary.approval_steps)
    ? summary.approval_steps.filter((id): id is string => typeof id === "string")
    : [];
  const trigger = typeof summary.trigger_type === "string" ? summary.trigger_type : null;
  const awaiting =
    typeof summary.awaiting_dispatcher === "boolean" ? summary.awaiting_dispatcher : null;

  const parts: string[] = [];
  parts.push(
    count.known
      ? `${count.value} ${count.value === 1 ? "step" : "steps"}`
      : "a step count the route did not send",
  );
  parts.push(
    gated.length
      ? `${gated.length} of them ${gated.length === 1 ? "stops" : "stop"} for a ruling (${gated.join(", ")})`
      : "no step in it stops for a ruling",
  );
  if (trigger) parts.push(`trigger ${trigger}`);
  if (awaiting === true) {
    parts.push(
      "which the API reports as not dispatchable by this build, so runs are started by hand here",
    );
  } else if (awaiting === false) {
    parts.push("which the API reports as dispatchable");
  }

  return {
    parses: true,
    error: null,
    stepCount: count.known ? count.value : null,
    gatedSteps: gated,
    trigger,
    awaitingDispatcher: awaiting,
    sentence: `${parts.join(", ")}.`,
  };
}

/* ------------------------------------------------------------------ */
/* The gate. The load bearing part of this door.                        */
/* ------------------------------------------------------------------ */

/** The pending block the run route sends, exactly as PendingStep declares it. */
export type PendingGate = {
  step_id: string;
  step_type: string;
  preview: Record<string, unknown>;
  project_id: string | null;
  payload_sha256: string;
  diverged: boolean;
};

export type GateCode = "no_gate" | "malformed" | "diverged" | "open";

export type GateRuling = {
  code: GateCode;
  label: string;
  tone: "neutral" | "warn" | "bad";
  sentence: string;
  /**
   * Whether an approve control may exist at all. THE ONE PROPERTY THIS FILE
   * EXISTS FOR. True for exactly one shape: a run the API says is awaiting
   * approval, carrying a pending block, whose seal is a real sha256, and which
   * the API has not marked diverged.
   */
  approvable: boolean;
  /**
   * Whether a reject control may exist. Wider than approvable on purpose: a
   * rejection executes nothing and closes a run, and app/services/workflows.py
   * deliberately lets a rejection through a diverged or unparseable gate so an
   * owner can never be trapped in front of one.
   */
  rejectable: boolean;
};

const SEAL = /^[0-9a-f]{64}$/;

export function readGateRuling(
  runStatus: string,
  pending: PendingGate | null | undefined,
): GateRuling {
  if (runStatus !== "awaiting_approval") {
    return {
      code: "no_gate",
      label: "NO GATE",
      tone: "neutral",
      sentence: `This run is ${runStatus || "in an unreported state"} and is not waiting on a ruling. Nothing here approves anything.`,
      approvable: false,
      rejectable: false,
    };
  }

  if (!pending || typeof pending.step_id !== "string" || !pending.step_id) {
    return {
      code: "malformed",
      label: "GATE UNREADABLE",
      tone: "bad",
      sentence:
        "The API says this run is awaiting approval and sent no readable pending step with it, so there is nothing to show a person and nothing here to rule on. Approving what cannot be displayed is the one thing this door must never offer.",
      approvable: false,
      rejectable: false,
    };
  }

  if (pending.diverged) {
    return {
      code: "diverged",
      label: "GATE DIVERGED",
      tone: "bad",
      sentence:
        "The definition changed while this run waited. The preview below is the LIVE rendering and it is not the payload this run sealed when it paused, so approving it would approve something nobody previewed. The API refuses the approval too. Reject this run to close it, then start a new one to preview the current definition.",
      approvable: false,
      rejectable: true,
    };
  }

  if (!SEAL.test(pending.payload_sha256 || "")) {
    return {
      code: "malformed",
      label: "GATE UNSEALED",
      tone: "bad",
      sentence:
        "The pending step arrived without a payload hash, so there is nothing to bind an approval to and no way to prove later what was ruled on. Nothing is offered for approval here.",
      approvable: false,
      rejectable: true,
    };
  }

  return {
    code: "open",
    label: "AWAITING YOUR RULING",
    tone: "warn",
    sentence: `This run is stopped in front of ${pending.step_id} (${pending.step_type}). Everything it would write is shown below, exactly as rendered. Nothing happens until you rule.`,
    approvable: true,
    rejectable: true,
  };
}

/* ------------------------------------------------------------------ */
/* The request body, built where it can be proved                       */
/* ------------------------------------------------------------------ */

export type ApprovalBody = {
  decisions: Record<string, "approved" | "rejected">;
  expected_payload_sha256?: string;
};

/**
 * The body sent to POST /workflows/{id}/runs/{run_id}/approve.
 *
 * Two laws, both enforced here rather than at the call site:
 *
 *  - The decisions map carries EXACTLY ONE key, the step the run is actually
 *    sitting in front of. app/services/workflows.py refuses any other step, and
 *    building the body anywhere else invites a caller that sends more.
 *  - An approval always carries the seal that was displayed. The server then
 *    refuses the approval if the run is not waiting on that exact payload, so
 *    a definition edited in another tab between the render and the button
 *    cannot execute under this ruling. A rejection deliberately carries no
 *    seal: it executes nothing, and it must be able to close a run whose
 *    payload has already moved.
 *
 * Throws rather than returning a body when the ruling is not one the gate
 * allows. A caller cannot get an approval body for a diverged gate.
 */
export function approvalBody(
  gate: GateRuling,
  pending: PendingGate,
  decision: "approved" | "rejected",
): ApprovalBody {
  if (decision === "approved" && !gate.approvable) {
    throw new Error(
      `approvalBody refuses to build an approval for a ${gate.code} gate: ${gate.label}`,
    );
  }
  if (decision === "rejected" && !gate.rejectable) {
    throw new Error(
      `approvalBody refuses to build a rejection for a ${gate.code} gate: ${gate.label}`,
    );
  }
  const body: ApprovalBody = { decisions: { [pending.step_id]: decision } };
  if (decision === "approved") {
    body.expected_payload_sha256 = pending.payload_sha256;
  }
  return body;
}

/* ------------------------------------------------------------------ */
/* The composer                                                         */
/* ------------------------------------------------------------------ */

/** One entry of GET /workflows/step-types, as that route declares it. */
export type StepTypeEntry = {
  type: string;
  requires_approval: boolean;
  description: string;
};

export function parseCatalog(raw: unknown): StepTypeEntry[] | null {
  if (!raw || typeof raw !== "object") return null;
  const list = (raw as { step_types?: unknown }).step_types;
  if (!Array.isArray(list)) return null;
  const entries: StepTypeEntry[] = [];
  for (const item of list) {
    if (!item || typeof item !== "object") return null;
    const entry = item as Record<string, unknown>;
    if (typeof entry.type !== "string" || !entry.type) return null;
    if (typeof entry.requires_approval !== "boolean") return null;
    entries.push({
      type: entry.type,
      requires_approval: entry.requires_approval,
      description: typeof entry.description === "string" ? entry.description : "",
    });
  }
  return entries;
}

/**
 * The config field each known step type requires, mirrored from
 * _REQUIRED_TEXT_CONFIG in services/workflows/definition.py.
 *
 * WHY A MIRROR IS ALLOWED HERE AND NOT FOR APPROVAL SEMANTICS. The catalog
 * route sends the type and whether it is gated; it does not send the shape of
 * a step's config. So the composer either mirrors the field names or offers no
 * fields at all. The mirror is bounded and it fails safe in both directions:
 * a type the catalog offers that is missing from this map gets a raw config
 * editor rather than a guessed field, and every refusal the composer can hit
 * is the API's own 422 shown verbatim. Nothing here ever calls a definition
 * valid; only the server does that.
 */
export const REQUIRED_CONFIG_FIELD: Record<string, string> = {
  knowledge_search: "query",
  council: "prompt",
  memory_write: "content",
  decision_draft: "question",
  export: "title",
};

export type StepDraft = {
  /** Local row key, never sent. */
  key: string;
  id: string;
  type: string;
  /** The single required text field for a known type. */
  body: string;
  /** Raw JSON config, used only for a type this build has no field map for. */
  rawConfig: string;
};

export type DraftDefinition = {
  version: 1;
  trigger: { type: "manual"; config: Record<string, never> };
  steps: Array<{ id: string; type: string; config: Record<string, unknown> }>;
};

export type BuildResult =
  | { ok: true; definition: DraftDefinition }
  | { ok: false; refusals: string[] };

const STEP_ID = /^[a-z][a-z0-9_]{0,31}$/;

/**
 * Turn the composer's rows into the definition the create route is sent.
 *
 * The refusals below are this door declining to send something it can already
 * see is malformed. They are NOT a validity verdict: the definition parser in
 * services/workflows/definition.py is the only thing that decides that, and
 * whatever it says comes back as a 422 the panel prints verbatim.
 */
export function buildDefinition(drafts: StepDraft[]): BuildResult {
  const refusals: string[] = [];
  const seen = new Set<string>();
  const steps: DraftDefinition["steps"] = [];

  if (drafts.length === 0) {
    refusals.push("A workflow needs at least one step; the composer has none.");
  }

  drafts.forEach((draft, index) => {
    const position = index + 1;
    const id = draft.id.trim();
    if (!STEP_ID.test(id)) {
      refusals.push(
        `Step ${position} needs an id matching [a-z][a-z0-9_]* and at most 32 characters (this one is ${id ? `"${id}"` : "empty"}).`,
      );
      return;
    }
    if (seen.has(id)) {
      refusals.push(
        `Step ${position} repeats the id "${id}"; ids are unique within a workflow.`,
      );
      return;
    }
    seen.add(id);

    if (!draft.type) {
      refusals.push(`Step "${id}" has no type selected.`);
      return;
    }

    const field = REQUIRED_CONFIG_FIELD[draft.type];
    if (field === undefined) {
      // A type this build has no field map for. The raw editor is the honest
      // path: the composer will not invent a field name for it.
      let parsed: unknown;
      try {
        parsed = JSON.parse(draft.rawConfig || "{}");
      } catch {
        refusals.push(
          `Step "${id}" is of type "${draft.type}", which this composer has no field map for, and its raw config is not JSON.`,
        );
        return;
      }
      if (!parsed || typeof parsed !== "object" || Array.isArray(parsed)) {
        refusals.push(`Step "${id}" raw config must be a JSON object.`);
        return;
      }
      steps.push({ id, type: draft.type, config: parsed as Record<string, unknown> });
      return;
    }

    const body = draft.body.trim();
    if (!body) {
      refusals.push(`Step "${id}" (${draft.type}) needs a non-empty ${field}.`);
      return;
    }
    steps.push({ id, type: draft.type, config: { [field]: draft.body } });
  });

  if (refusals.length > 0) return { ok: false, refusals };
  return {
    ok: true,
    definition: { version: 1, trigger: { type: "manual", config: {} }, steps },
  };
}

/**
 * The references a step at `index` may use, mirrored from _validate_references.
 * Purely a hint printed beside the field; the server still decides.
 */
export function availableReferences(drafts: StepDraft[], index: number): string[] {
  const refs = ["input"];
  for (let i = 0; i < index && i < drafts.length; i += 1) {
    const id = drafts[i].id.trim();
    if (STEP_ID.test(id)) refs.push(id);
  }
  return refs;
}

/**
 * Whether starting a run would reach a step that stops for a ruling, said only
 * from what the routes reported. `gated` comes from the list route's summary,
 * which computes it from the same EFFECT_STEP_TYPES the catalog reports.
 */
export function describeStart(summary: SummaryFacts, workflowStatus: string): string {
  if (workflowStatus === "archived") {
    return "This workflow is archived. app/services/workflows.py refuses to run an archived workflow, so starting one here would only produce a 409.";
  }
  if (!summary.parses) {
    return "This workflow's stored definition does not parse, so a run cannot be started from it.";
  }
  if (summary.stepCount === 0) {
    return "This workflow has no steps. A run would start and end having done nothing.";
  }
  if (summary.gatedSteps.length === 0) {
    return "No step in this workflow writes anything, so a run reads and reasons and then stops on its own. It will not ask you for a ruling because it has nothing to ask about.";
  }
  return `A run reads and reasons unattended and then STOPS in front of ${summary.gatedSteps.join(", ")}, which ${summary.gatedSteps.length === 1 ? "writes" : "write"} something. Nothing is written until you rule on it here.`;
}
