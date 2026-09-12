/**
 * Proof for the agent roster panel's verdict ladders. No test framework:
 * node:assert and a plain process exit code, the same shape as
 * scripts/learning-check.ts and scripts/control-check.ts. Run from apps/web:
 *
 *   node --experimental-strip-types scripts/roster-check.ts
 *
 * WHY THIS FILE EXISTS
 *
 * The roster panel is the first surface over GET /api/v1/agents, and the one claim
 * it exists to make is which agents this system defines and what each declares. It
 * has the same single way to be wrong as every other read panel in this estate:
 * rendering a FAILED read as an EMPTY roster. That is the inversion a critic used
 * against the control plane on 2026-09-09, when `pnpm typecheck` and `pnpm build`
 * both exited 0 over a reversed safeguard, so neither of those is a guard on this.
 *
 * It also has three ways to be wrong that are particular to this door:
 *
 *   - putting a capability count on a roster row, when the list route sends no
 *     capability array at all, so the only truthful count before the detail read
 *     is no count;
 *   - drawing `is_active` from the list route as a measurement, when
 *     list_active_agents() filters on that very field and true is the only value a
 *     row can carry;
 *   - reading a 404 from the detail route as an agent that declares nothing, when
 *     the slug came out of the list route a moment earlier and a 404 means the two
 *     routes disagree.
 *
 * Everything under test is pure, with no DOM and no network, so there is no reason
 * for any of it to be unguarded.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { dirname, join } from "node:path";
import { fileURLToPath } from "node:url";
import ts from "typescript";
import {
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
  type AgentDetail,
  type DetailRead,
  type RosterRead,
  type RosterVerdict,
} from "../components/roster/agent-roster-honesty.ts";

const HERE = dirname(fileURLToPath(import.meta.url));

let checks = 0;
function check(name: string, run: () => void): void {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

const LOADING: RosterRead = { state: "loading" };
const OK_EMPTY: RosterRead = { state: "ok", count: 0, dropped: 0, contradicted: 0 };
const OK_FULL: RosterRead = { state: "ok", count: 9, dropped: 0, contradicted: 0 };
const FAILED: RosterRead = {
  state: "failed",
  detail: "the roster route answered 500 Internal Server Error",
};
const GATED: RosterRead = { state: "unauthorized", status: 401 };

/* ------------------------------------------------------------------ */
/* The load bearing law                                                */
/* ------------------------------------------------------------------ */

function refuseEmptyAndGood(verdict: RosterVerdict, why: string): void {
  assert.notEqual(verdict.code, "empty", "a read that did not succeed must never read as empty");
  assert.notEqual(verdict.tone, "good", "a read that did not succeed must never take a good tone");
  assert.notEqual(verdict.code, "populated", why);
}

check("a failed roster read is never reported as an empty roster", () => {
  const verdict = readRosterVerdict(FAILED);
  assert.equal(verdict.code, "unreadable");
  refuseEmptyAndGood(verdict, "a 500 supports no claim about the registry");
  assert.match(verdict.sentence, /failed read, not an empty roster/);
  // The status has to reach the operator, or "unreadable" is a shrug.
  assert.match(verdict.sentence, /500/);
});

check("a gated roster read is its own state, not a failure and not an emptiness", () => {
  const verdict = readRosterVerdict(GATED);
  assert.equal(verdict.code, "unauthorized");
  refuseEmptyAndGood(verdict, "a 401 supports no claim about the registry");
  assert.notEqual(
    verdict.code,
    "unreadable",
    "a deployment gating the read is a different fact from the route breaking",
  );
  assert.match(verdict.sentence, /401/);
  assert.match(verdict.sentence, /not an empty roster/);
});

check("403 lands in the same gated state as 401", () => {
  const verdict = readRosterVerdict({ state: "unauthorized", status: 403 });
  assert.equal(verdict.code, "unauthorized");
  assert.match(verdict.sentence, /403/);
});

check("a request in flight is neither empty nor failed", () => {
  const verdict = readRosterVerdict(LOADING);
  assert.equal(verdict.code, "reading");
  assert.equal(verdict.tone, "neutral");
  assert.notEqual(verdict.code, "empty");
  assert.notEqual(verdict.code, "unreadable");
});

check("the five verdict codes are five distinct labels", () => {
  const labels = [LOADING, GATED, FAILED, OK_EMPTY, OK_FULL].map(
    (read) => readRosterVerdict(read).label,
  );
  assert.equal(new Set(labels).size, 5, `two reads render the same label: ${labels.join(" / ")}`);
});

check("an answered roster with no rows is empty, and only that read is", () => {
  const verdict = readRosterVerdict(OK_EMPTY);
  assert.equal(verdict.code, "empty");
  assert.equal(verdict.tone, "neutral");
  assert.match(verdict.sentence, /answered and returned no rows/);
});

check("an answered roster with rows is the only read that takes a good tone", () => {
  const verdict = readRosterVerdict(OK_FULL);
  assert.equal(verdict.code, "populated");
  assert.equal(verdict.tone, "good");
  assert.match(verdict.sentence, /9 active agents/);
  // The filter has to be named, or a reader takes 9 for the size of the registry.
  assert.match(verdict.sentence, /list_active_agents/);
});

check("a roster whose every row was dropped is not reported as a registry with no agents", () => {
  // Nine rows arrived and none was the shape. Count is 0, and calling that an
  // empty registry would blame the registry for a payload mismatch.
  const verdict = readRosterVerdict({ state: "ok", count: 0, dropped: 9, contradicted: 0 });
  assert.equal(verdict.code, "empty");
  assert.match(verdict.sentence, /payload mismatch/);
  assert.doesNotMatch(verdict.sentence, /registry is empty/);
});

check("rows dropped alongside good rows are counted out loud", () => {
  const verdict = readRosterVerdict({ state: "ok", count: 7, dropped: 2, contradicted: 0 });
  assert.equal(verdict.code, "populated");
  assert.match(verdict.sentence, /7 active agents/);
  assert.match(verdict.sentence, /2 further rows/);
});

/* ------------------------------------------------------------------ */
/* No number the route did not send                                    */
/* ------------------------------------------------------------------ */

const DETAIL: AgentDetail = {
  slug: "oracle",
  name: "Oracle",
  purpose: "Future intelligence",
  mission: "Identify emerging patterns.",
  version: "1.0.0",
  isActive: true,
  capabilities: ["Trend detection", "Scenario thinking"],
  limitations: ["Cannot predict the future with certainty"],
  evaluationCriteria: ["Relevance", "Clarity", "Honesty"],
  outputFormat: [{ key: "type", value: "structured" }],
  outputFormatWasObject: true,
};

check("every count is absent until the detail route has answered", () => {
  const unread: DetailRead[] = [
    { state: "idle" },
    { state: "loading" },
    { state: "missing", status: 404 },
    { state: "unauthorized", status: 401 },
    { state: "failed", detail: "the detail route answered 500" },
    { state: "malformed", detail: "the body was not JSON" },
  ];
  for (const read of unread) {
    for (const field of ["capabilities", "limitations", "evaluationCriteria"] as const) {
      const count = declaredCount(read, field);
      assert.equal(
        count,
        null,
        `${read.state} produced a ${field} count of ${count}; the list route sends no such array, so any number here is invented`,
      );
      assert.equal(countLabel(count), "not read");
      assert.notEqual(countLabel(count), "0", "unmeasured must never render as zero");
    }
  }
});

check("a read detail reports the real array lengths", () => {
  const read: DetailRead = { state: "ok", detail: DETAIL };
  assert.equal(declaredCount(read, "capabilities"), 2);
  assert.equal(declaredCount(read, "limitations"), 1);
  assert.equal(declaredCount(read, "evaluationCriteria"), 3);
  assert.equal(countLabel(declaredCount(read, "capabilities")), "2");
});

check("an agent that genuinely declares nothing reads as 0, not as unread", () => {
  // The two must stay distinguishable in both directions.
  const bare: AgentDetail = { ...DETAIL, capabilities: [] };
  assert.equal(declaredCount({ state: "ok", detail: bare }, "capabilities"), 0);
  assert.equal(countLabel(0), "0");
  assert.notEqual(countLabel(0), "not read");
});

/* ------------------------------------------------------------------ */
/* is_active means something on one route and nothing on the other      */
/* ------------------------------------------------------------------ */

check("is_active from the list route is never presented as a measurement", () => {
  const claim = activeClaim("list", true);
  assert.equal(
    claim.informative,
    false,
    "list_agents() iterates list_active_agents(), which filters on is_active, so true is the only value a row can carry",
  );
  assert.match(claim.text, /only value this route can return/);
});

check("is_active from the detail route is a measurement, both ways", () => {
  const active = activeClaim("detail", true);
  assert.equal(active.informative, true);
  assert.match(active.text, /active in the registry/);
  const inactive = activeClaim("detail", false);
  assert.equal(inactive.informative, true);
  assert.match(inactive.text, /inactive/);
  // An inactive agent is absent from the list and still served by slug, and the
  // panel has to say the second half or the row looks like a contradiction.
  assert.match(inactive.text, /still served by slug/);
});

/* ------------------------------------------------------------------ */
/* The detail ladder                                                   */
/* ------------------------------------------------------------------ */

check("a 404 on a slug the list returned is reported as the routes disagreeing", () => {
  const note = describeDetail({ state: "missing", status: 404 });
  assert.equal(note.code, "missing");
  assert.equal(note.tone, "warn");
  assert.match(note.sentence, /disagree about the registry/);
  assert.match(note.sentence, /not an agent that declares nothing/);
});

check("an unasked detail is unread rather than empty", () => {
  const note = describeDetail({ state: "idle" });
  assert.equal(note.code, "idle");
  assert.match(note.sentence, /unread, not empty/);
});

check("every failing detail state warns and none of them claims emptiness", () => {
  const failing: DetailRead[] = [
    { state: "missing", status: 404 },
    { state: "unauthorized", status: 403 },
    { state: "failed", detail: "the detail route answered 500" },
    { state: "malformed", detail: "the body was not JSON" },
  ];
  const sentences = new Set<string>();
  for (const read of failing) {
    const note = describeDetail(read);
    assert.equal(note.tone, "warn", `${read.state} should warn`);
    assert.doesNotMatch(
      note.sentence,
      /declares no capabilities\b/,
      `${read.state} must not read as an agent with no capabilities`,
    );
    sentences.add(note.sentence);
  }
  assert.equal(sentences.size, 4, "two failing detail states render the same sentence");
});

/* ------------------------------------------------------------------ */
/* Status mapping                                                      */
/* ------------------------------------------------------------------ */

check("only 401 and 403 map to gated on the list route, and no status maps to ok", () => {
  for (const status of [400, 404, 418, 429, 500, 502, 503]) {
    const read = listReadForStatus(status, "");
    assert.equal(read.state, "failed", `${status} should be a plain failure on the list route`);
    assert.match((read as { detail: string }).detail, new RegExp(String(status)));
  }
  for (const status of [401, 403]) {
    assert.equal(listReadForStatus(status, "Unauthorized").state, "unauthorized");
  }
  for (const status of [200, 204, 301, 400, 401, 403, 404, 500]) {
    assert.notEqual(
      listReadForStatus(status, "").state,
      "ok",
      "a non-2xx branch must never manufacture a successful read",
    );
  }
});

check("404 is its own state on the detail route and a plain failure on the list route", () => {
  assert.equal(detailReadForStatus(404, "Not Found").state, "missing");
  assert.equal(listReadForStatus(404, "Not Found").state, "failed");
  assert.equal(detailReadForStatus(401, "").state, "unauthorized");
  assert.equal(detailReadForStatus(500, "").state, "failed");
});

/* ------------------------------------------------------------------ */
/* Payload shape                                                       */
/* ------------------------------------------------------------------ */

const WIRE_ROW = {
  slug: "oracle",
  name: "Oracle",
  purpose: "Future intelligence",
  mission: "Identify emerging patterns, long-term opportunities, and strategic direction.",
  version: "1.0.0",
  is_active: true,
};

check("the parser accepts the shape the route actually sends", () => {
  // Copied from a live read on 2026-09-10: GET /api/v1/agents answered 200 with
  // nine of these, keys is_active, mission, name, purpose, slug, version.
  const parsed = parseRosterPayload([WIRE_ROW]);
  assert.equal(parsed.wasArray, true);
  assert.equal(parsed.dropped, 0);
  assert.deepEqual(parsed.rows, [
    {
      slug: "oracle",
      name: "Oracle",
      purpose: "Future intelligence",
      mission: "Identify emerging patterns, long-term opportunities, and strategic direction.",
      version: "1.0.0",
      isActive: true,
    },
  ]);
});

check("a row missing a field is dropped and counted, never defaulted", () => {
  const { slug, ...noSlug } = WIRE_ROW;
  void slug;
  const parsed = parseRosterPayload([
    WIRE_ROW,
    noSlug,
    { ...WIRE_ROW, is_active: "yes" },
    null,
    "oracle",
  ]);
  assert.equal(parsed.rows.length, 1);
  assert.equal(parsed.dropped, 4);
  for (const row of parsed.rows) {
    assert.notEqual(row.purpose, "", "a blank purpose would read as an agent that declares none");
  }
});

check("a payload that is not a list is not an empty roster", () => {
  for (const payload of [{}, null, "nine", 9, { rows: [WIRE_ROW] }]) {
    const parsed = parseRosterPayload(payload);
    assert.equal(parsed.wasArray, false, `${JSON.stringify(payload)} is not a list`);
    assert.equal(parsed.rows.length, 0);
  }
  // And an actual empty list IS an empty roster, so the two stay apart.
  assert.equal(parseRosterPayload([]).wasArray, true);
});

check("output_format is walked rather than assumed", () => {
  // The wire type is Dict[str, Any]. Today every agent answers type + fields.
  const today = describeOutputFormat({
    type: "structured",
    fields: ["insight", "time_horizon", "confidence", "implications"],
  });
  assert.equal(today.wasObject, true);
  assert.deepEqual(today.lines, [
    { key: "type", value: "structured" },
    { key: "fields", value: "insight, time_horizon, confidence, implications" },
  ]);

  // A shape nobody has shipped yet must still render, because the contract allows
  // it and a panel keyed on `type` and `fields` would go blank.
  const tomorrow = describeOutputFormat({
    schema: { kind: "json", strict: true },
    max_tokens: 512,
    nullable: null,
  });
  assert.deepEqual(tomorrow.lines, [
    { key: "schema", value: "kind: json; strict: true" },
    { key: "max_tokens", value: "512" },
    { key: "nullable", value: "null" },
  ]);

  // Absent or wrong-typed output_format is reported as such, not as an agent that
  // declares no output shape.
  for (const raw of [undefined, null, "structured", ["insight"], 3]) {
    assert.equal(describeOutputFormat(raw).wasObject, false);
  }
  // An empty object is a real answer and stays distinguishable from an absent one.
  assert.deepEqual(describeOutputFormat({}), { lines: [], wasObject: true });
});

check("the detail parser refuses a body that is not an agent definition", () => {
  const full = {
    ...WIRE_ROW,
    capabilities: ["Trend detection"],
    limitations: ["Cannot predict the future with certainty"],
    output_format: { type: "structured", fields: ["insight"] },
    evaluation_criteria: ["Relevance"],
  };
  const parsed = parseAgentDetail(full);
  assert.ok(parsed, "the live detail shape must parse");
  assert.equal(parsed.capabilities.length, 1);
  assert.equal(parsed.outputFormatWasObject, true);

  // Each of these is a body the route could conceivably send and none of them is
  // an agent whose arrays are all empty.
  assert.equal(parseAgentDetail({ ...full, capabilities: "Trend detection" }), null);
  assert.equal(parseAgentDetail({ ...full, limitations: [3] }), null);
  assert.equal(parseAgentDetail({ detail: "Agent not found" }), null);
  assert.equal(parseAgentDetail(null), null);
  assert.equal(parseAgentDetail([full]), null);

  // output_format is the one field the contract does not pin, so its absence must
  // not sink the whole read; it is reported through outputFormatWasObject instead.
  const withoutFormat = { ...full, output_format: undefined };
  const lenient = parseAgentDetail(withoutFormat);
  assert.ok(lenient, "a missing output_format must not throw the whole definition away");
  assert.equal(lenient.outputFormatWasObject, false);
});

/* ------------------------------------------------------------------ */
/* The panel renders the ladders this file proves                        */
/* ------------------------------------------------------------------ */

const PANEL = readFileSync(join(HERE, "..", "components/roster/AgentRosterPanel.tsx"), "utf8");

check("the panel feeds its own reads into the ladder rather than a second copy", () => {
  assert.match(
    PANEL,
    /readRosterVerdict\(asRead\(roster\)\)/,
    "AgentRosterPanel no longer feeds asRead into readRosterVerdict, so the ladder this file guards is not the one the panel renders",
  );
  assert.match(
    PANEL,
    /describeDetail\(detail\)/,
    "AgentRosterPanel no longer feeds its detail read into describeDetail",
  );
});

check("asRead's failed branch carries no count", () => {
  const file = ts.createSourceFile(
    "AgentRosterPanel.tsx",
    PANEL,
    ts.ScriptTarget.Latest,
    true,
    ts.ScriptKind.TSX,
  );
  const decls: ts.FunctionDeclaration[] = [];
  const walk = (node: ts.Node) => {
    if (ts.isFunctionDeclaration(node) && node.name && node.name.text === "asRead") {
      decls.push(node);
    }
    ts.forEachChild(node, walk);
  };
  walk(file);
  assert.equal(decls.length, 1, "asRead is not a single function declaration in the panel");
  const text = decls[0].getText();
  const failed = /return\s*\{\s*state:\s*"failed"[^}]*\}/.exec(text);
  assert.ok(failed, "asRead has no failed branch");
  assert.ok(
    !/count:/.test(failed[0]),
    `asRead's failed branch carries a count (${failed[0]}). A count is a claim about the roster, and a read that failed supports no such claim`,
  );
  assert.match(
    text,
    /state:\s*"ok",\s*count:\s*roster\.rows\.length/,
    "asRead's ok branch does not report the actual row count, so the number on the panel is not the number the route returned",
  );
});

check("the panel does not invent a token gate the routes do not have", () => {
  // Measured 2026-09-10 against a TestClient at 32883cf: GET /api/v1/agents
  // answers 200 with no Authorization header and 200 with `Bearer garbage`,
  // because app/api/v1/agents.py declares no dependency. A panel that refused to
  // read without a token would render a lock that does not exist, which is the
  // same class of error as rendering a failure as an emptiness.
  assert.match(
    PANEL,
    /return token \? \{ Authorization: `Bearer \$\{token\}` \} : \{\};/,
    "authHeaders no longer omits the header when there is no token, so a tokenless device sends `Bearer ` and gets a different answer than the measurement this panel is built on",
  );
  assert.doesNotMatch(
    PANEL,
    /state:\s*"locked"/,
    "the panel has grown a locked state; these two routes need no token, so a lock here is invented",
  );
  // The one early return in load() must be the network failure, not a token check.
  const load = /const load = useCallback\(async \(\) => \{[\s\S]*?\}, \[token\]\);/.exec(PANEL);
  assert.ok(load, "load() is no longer a useCallback keyed on token");
  assert.doesNotMatch(
    load[0],
    /if \(!bearer\)/,
    "load() short-circuits on a missing token, which would report a lock the routes do not impose",
  );
});

check("the roster chips render countLabel rather than a length", () => {
  for (const field of ["capabilities", "limitations", "evaluationCriteria"]) {
    assert.match(
      PANEL,
      new RegExp(`countLabel\\(declaredCount\\(detail, "${field}"\\)\\)`),
      `the ${field} chip no longer goes through countLabel(declaredCount(...)), so it can put a number on a row the list route never measured`,
    );
  }
  assert.doesNotMatch(
    PANEL,
    /capabilities\.length/,
    "the panel reads an array length directly; before the detail route answers there is no array to read",
  );
});

/* ------------------------------------------------------------------ */
/* Legibility, on the files control-check.ts does not yet list          */
/* ------------------------------------------------------------------ */

const OWN_FILES = [
  "components/roster/AgentRosterPanel.tsx",
  "components/roster/agent-roster-honesty.ts",
  "components/roster/index.ts",
  "app/control/roster/page.tsx",
];

/** The same three patterns scripts/control-check.ts bans, on the same background. */
const BELOW_AA: Array<{ pattern: RegExp; why: string }> = [
  { pattern: /text-\[(?:[0-9]|10)px\]/g, why: "under 11px is unreadable on a phone" },
  {
    pattern: /text-white\/(?:[0-9]|[1-3][0-9]|4[0-5])\b/g,
    why: "white at 45% or less is below 4.5:1 on the ACX void",
  },
  { pattern: /text-\[#526979\]/g, why: "#526979 is 3.49:1 on the ACX void" },
];

check("no text in the roster slice renders below the AA floor", () => {
  // control-check.ts owns CONTROL_TREE and this slice is not in it yet, so the
  // floor is held here until it is. Duplicated on purpose: an unlisted file with
  // no guard is how the fourth critic got 8px text past a green check on
  // 2026-09-09.
  const offences: string[] = [];
  for (const relative of OWN_FILES) {
    const source = readFileSync(join(HERE, "..", relative), "utf8");
    const lines = source.split("\n");
    for (const { pattern, why } of BELOW_AA) {
      lines.forEach((line, index) => {
        for (const hit of line.matchAll(pattern)) {
          offences.push(`${relative}:${index + 1} ${hit[0]} (${why})`);
        }
      });
    }
  }
  assert.deepEqual(offences, [], `\n${offences.join("\n")}`);
});

check("the legibility sweep above is reading real files", () => {
  for (const relative of OWN_FILES) {
    const source = readFileSync(join(HERE, "..", relative), "utf8");
    assert.ok(source.length > 200, `${relative} is too small to be the real file`);
  }
  const panel = readFileSync(join(HERE, "..", OWN_FILES[0]), "utf8");
  assert.match(panel, /text-\[11px\]/, "the panel carries no 11px class, so the floor is untested");
});

/* ------------------------------------------------------------------ */
/* Reachable by a person                                               */
/* ------------------------------------------------------------------ */

check("the roster panel is mounted where a person can reach it", () => {
  // A panel nobody can open is the door this arc exists to close, so the mount is
  // part of the deliverable rather than an integration detail.
  const route = readFileSync(join(HERE, "..", "app/control/roster/page.tsx"), "utf8");
  assert.match(route, /AgentRosterPanel/, "/control/roster no longer renders AgentRosterPanel");
  assert.match(
    route,
    /from "@\/components\/roster\/AgentRosterPanel"/,
    "/control/roster imports the panel from somewhere else",
  );
});

check("nothing in the roster slice writes or runs", () => {
  // Hard rule: effects stay human gated. A read only roster has no business
  // holding a non-GET, and this is cheaper to assert than to re-audit later.
  for (const relative of OWN_FILES) {
    const source = readFileSync(join(HERE, "..", relative), "utf8");
    for (const verb of ["POST", "PUT", "PATCH", "DELETE"]) {
      assert.doesNotMatch(
        source,
        new RegExp(`method:\\s*"${verb}"`),
        `${relative} sends a ${verb}; this surface is read only`,
      );
    }
  }
  assert.match(
    PANEL,
    /Read only, by construction/,
    "the panel no longer tells the reader it is read only",
  );
});

/* ------------------------------------------------------------------ */
/* Added 2026-09-10, after an adversary beat all 32 checks above.       */
/* ------------------------------------------------------------------ */

check("a body that is not a list is a failed read in the panel, not an empty roster", () => {
  // THE HOLE: `wasArray` appeared in this file only over the pure module, never
  // over the panel. Deleting the panel's `if (!parsed.wasArray)` early return
  // left tsc, this file (32 passed), control-check, next build and pytest all at
  // exit 0, while a 200 carrying {"detail":"Internal Server Error"} rendered
  // "ROSTER EMPTY" in a neutral tone with the sentence "Every agent in the
  // registry is marked inactive, or the registry is empty" and no retry control.
  // Measured by the adversary, not argued.
  const load = /const load = useCallback\([\s\S]*?\n  \}, \[token\]\);/.exec(PANEL);
  assert.ok(load, "AgentRosterPanel no longer declares `load`, so this check cannot find the roster read");
  const branch = /if \(!parsed\.wasArray\) \{[\s\S]*?\n    \}/.exec(load[0]);
  assert.ok(
    branch,
    "the panel no longer refuses a payload that is not a list. Without it an error envelope arriving with a 200 renders as an empty registry",
  );
  assert.match(
    branch[0],
    /setRoster\(\{\s*state: "failed"/,
    `the non-array branch is ${branch[0]}, which does not set a failed read`,
  );
  assert.ok(
    !/state: "ok"/.test(branch[0]),
    `the non-array branch carries an ok state (${branch[0]})`,
  );
  assert.match(branch[0], /return;/, "the non-array branch does not return, so it falls through into the ok path");
  // the ok read must be the only place rows are handed over, and it must come
  // from the parser rather than from the raw payload
  assert.match(
    load[0],
    /setRoster\(\{ state: "ok", rows: parsed\.rows, dropped: parsed\.dropped \}\)/,
    "the panel no longer hands the parser's own rows to the ok state",
  );
});

check("the list route's own is_active is read, not assumed", () => {
  // THE HOLE: activeClaim's list branch took `isActive` and never read it, so a
  // row whose payload said is_active false was described as "listed as active"
  // in the same render that held the contradicting field. It takes the list
  // route's filter being gone to happen, which test_agents_roster_surface.py
  // catches, so the honest answer is to name the contradiction rather than to
  // describe a state.
  const contradicted = activeClaim("list", false);
  assert.ok(
    !/^listed as active/.test(contradicted.text),
    `a row sent as inactive by the list route is described as "${contradicted.text}"`,
  );
  assert.match(contradicted.text, /INACTIVE/, contradicted.text);
  assert.match(contradicted.text, /contradicts/, contradicted.text);
  assert.equal(contradicted.informative, true, "a contradiction is information, not a non-claim");

  // and the same contradiction at the store level, MEASURED from the rows
  // rather than assumed to be impossible. The populated sentence used to
  // hardcode the word "active".
  const store = readRosterVerdict({ state: "ok", count: 9, dropped: 0, contradicted: 2 });
  assert.equal(store.code, "contradicted", `a roster carrying two inactive rows read as ${store.code}`);
  assert.notEqual(store.tone, "good", "a roster that denies its own filter was drawn in a good tone");
  assert.match(store.sentence, /is_active FALSE/, store.sentence);
  assert.ok(
    !/9 active agents/.test(store.sentence),
    `the sentence still calls them active: "${store.sentence}"`,
  );
  // the healthy read is unchanged and still says every row agrees
  const clean = readRosterVerdict({ state: "ok", count: 9, dropped: 0, contradicted: 0 });
  assert.equal(clean.code, "populated");
  assert.match(clean.sentence, /every row it sent agrees it is active/, clean.sentence);
  // the panel must count it from the rows rather than pass a literal
  assert.match(
    PANEL,
    /contradicted: roster\.rows\.filter\(\(row\) => row\.isActive === false\)\.length/,
    "the panel no longer counts the contradicting rows from the rows themselves",
  );

  const normal = activeClaim("list", true);
  assert.equal(normal.informative, false, "the list route's true is still worth nothing on its own");
  assert.match(normal.text, /only value this route can return/);

  // the detail route is a real read in both directions, unchanged
  assert.equal(activeClaim("detail", true).informative, true);
  assert.match(activeClaim("detail", false).text, /inactive in the registry/);

  // and the panel must pass the row's own field rather than a literal
  assert.match(
    PANEL,
    /activeClaim\("list", row\.isActive\)/,
    "the panel no longer passes the row's own is_active into the list claim, so the branch above can never be reached",
  );
  assert.ok(
    !/activeClaim\("list", true\)/.test(PANEL),
    "the panel hardcodes true into the list claim, which is the assumption this check exists to refuse",
  );
});

console.log(`\n${checks} roster honesty checks passed`);
