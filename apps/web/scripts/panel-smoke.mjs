/**
 * Do the six control plane panels actually READ, in a browser?
 *
 * Run from apps/web against a stack that is already up:
 *
 *   SMOKE_API_BASE=http://127.0.0.1:8000/api/v1 \
 *   SMOKE_WEB_ORIGIN=http://127.0.0.1:3000 \
 *   DEVON_REGISTRATION_KEY=... \
 *   node --experimental-strip-types scripts/panel-smoke.mjs
 *
 * WHY A BROWSER AND NOT ANOTHER PURE CHECK
 *
 * Six panels shipped in PR #194. `next build` prerenders all six routes and
 * `tsc` compiles them, so each renders its INITIAL state without throwing. No
 * `fetch` in any of them had ever executed. Every other check under
 * scripts/ reads source text or an AST: control-check, roster-check,
 * memory-check, projects-check, decisions-check and workflow-check all prove the
 * pure ladders and the shape of the JSX around them, and not one of them sends a
 * request. So a wrong path, a malformed Authorization header, a response parsed
 * against the wrong key, or a CORS refusal would pass every gate this estate
 * has. That is the same class of gap `scripts/audio-check.mjs` was written for,
 * and this file takes the same posture as that one.
 *
 * WHAT IT DRIVES
 *
 * A whole stack, stood up beside it: PostgreSQL with the Alembic build, the real
 * FastAPI app, and a built Next server. It registers a THROWAWAY account through
 * the real registration path (POST /auth/register behind DEVON_REGISTRATION_KEY,
 * then POST /auth/login for the token), seeds one row per account scoped panel
 * carrying a nonce generated in this process, puts the token in the browser at
 * the same storage slot DevonChat writes at sign-in, and opens each route in
 * real Chromium.
 *
 * WHAT IT ASSERTS, and why it is not theatre
 *
 * Two independent layers per panel, so a defect has to defeat both:
 *
 *  1. THE NONCE. Each seeded row carries a random string minted milliseconds
 *     earlier and its server assigned uuid. Neither can be in the bundle, in a
 *     fixture, or in anybody's cache. If it is on the rendered page, the browser
 *     fetched it from the API in this run. Nothing else explains it.
 *
 *  2. THE SHIPPED LADDER'S OWN SENTENCE. This file fetches the same payload the
 *     browser will fetch, runs it through the SAME pure modules the panel runs
 *     it through, and asserts the rendered page carries the resulting verdict
 *     label and sentence VERBATIM. A parse that drifts from the payload, a count
 *     read off the wrong key, or a panel that reaches a different rung all
 *     produce a different sentence.
 *
 * And the ladders' other rungs are asserted ABSENT by name. "Locked",
 * "unreadable", "unusable" and "empty" are computed from the same shipped
 * functions rather than typed in here, so a rename cannot leave this file
 * asserting a string nothing renders any more.
 *
 * IT FAILS LOUDLY WHEN THE BROWSER IS MISSING. `loadPlaywright` and
 * `findChromium` both THROW rather than skip, exactly as audio-check.mjs does. A
 * smoke run that silently skips is worse than none, because it is credited.
 */

import assert from "node:assert/strict";
import { existsSync, readFileSync } from "node:fs";
import { randomBytes } from "node:crypto";

import {
  parseRosterPayload,
  readRosterVerdict,
} from "../components/roster/agent-roster-honesty.ts";
import {
  parseProjectsPayload,
  readProjectsVerdict,
} from "../components/projects/projects-honesty.ts";
import {
  parseMemoryPayload,
  readMemoryVerdict,
  summarizeMemories,
} from "../components/mind/memory-honesty.ts";
import {
  parseDecisionList,
  readDecisionsVerdict,
} from "../components/council/decision-record.ts";
import {
  parseCatalog,
  readCatalogVerdict,
  readListVerdict,
  readSummary,
} from "../components/control/workflow-honesty.ts";

const STARTED_AT = Date.now();

const API_BASE = (process.env.SMOKE_API_BASE || "http://127.0.0.1:8000/api/v1").replace(
  /\/$/,
  "",
);
const WEB_ORIGIN = (process.env.SMOKE_WEB_ORIGIN || "http://127.0.0.1:3000").replace(
  /\/$/,
  "",
);
const REGISTRATION_KEY = process.env.DEVON_REGISTRATION_KEY || "";
/** How long one panel gets to reach a terminal verdict. */
const VERDICT_TIMEOUT_MS = Number(process.env.SMOKE_VERDICT_TIMEOUT_MS || 20000);

if (!REGISTRATION_KEY) {
  throw new Error(
    "DEVON_REGISTRATION_KEY is not set. Registration is closed by default " +
      "(app/api/v1/auth.py:_require_registration_key), so without it no account " +
      "can be made and five of the six panels can only ever reach their locked " +
      "state. Refusing to run a smoke check that would prove nothing.",
  );
}

/* ------------------------------------------------------------------ */
/* Playwright and Chromium, resolved the way audio-check.mjs does      */
/* ------------------------------------------------------------------ */

const PLAYWRIGHT_CANDIDATES = [
  process.env.PLAYWRIGHT_MODULE,
  "/opt/node22/lib/node_modules/playwright/index.mjs",
  "playwright",
].filter(Boolean);

const CHROME_CANDIDATES = [
  process.env.CHROMIUM_BINARY,
  "/opt/pw-browsers/chromium-1194/chrome-linux/chrome",
  "/opt/pw-browsers/chromium/chrome-linux/chrome",
  "/usr/bin/chromium",
  "/usr/bin/google-chrome",
].filter(Boolean);

async function loadPlaywright() {
  for (const candidate of PLAYWRIGHT_CANDIDATES) {
    try {
      return await import(candidate);
    } catch {
      // Try the next one. The failure is reported once, below.
    }
  }
  throw new Error(
    "playwright could not be imported. Set PLAYWRIGHT_MODULE to its index.mjs, " +
      `or install it. Tried: ${PLAYWRIGHT_CANDIDATES.join(", ")}`,
  );
}

function findChromium() {
  const found = CHROME_CANDIDATES.find((path) => path.startsWith("/") && existsSync(path));
  if (!found) {
    throw new Error(
      "no Chromium binary found. Set CHROMIUM_BINARY. Tried: " + CHROME_CANDIDATES.join(", "),
    );
  }
  return found;
}

/* ------------------------------------------------------------------ */
/* The storage slot, read out of the shipped source rather than typed  */
/* ------------------------------------------------------------------ */

/**
 * Every panel reads its bearer token with `readDevonToken` from
 * components/presence/usePresenceSocket.ts, which reads one storage key. Typing
 * that key in here would mean a rename leaves this file seeding a slot nothing
 * reads, and all five account scoped panels would sit locked while this check
 * happily reported on the one panel that needs no token. So the value is cut out
 * of the shipped module and a rename of the constant throws.
 */
function tokenSlotFromSource() {
  const source = readFileSync(
    new URL("../components/presence/usePresenceSocket.ts", import.meta.url),
    "utf8",
  );
  const match = source.match(/export const TOKEN_SLOT = "([^"]+)"/);
  assert.notEqual(
    match,
    null,
    "TOKEN_SLOT is no longer exported as a string literal from usePresenceSocket.ts, " +
      "so this check cannot know which storage slot the panels read.",
  );
  assert.ok(
    source.includes("export function readDevonToken()"),
    "readDevonToken is no longer exported from usePresenceSocket.ts",
  );
  return match[1];
}

/* ------------------------------------------------------------------ */
/* Small helpers                                                       */
/* ------------------------------------------------------------------ */

let checks = 0;
function check(name, run) {
  run();
  checks += 1;
  console.log(`ok ${checks} ${name}`);
}

function nonce() {
  return randomBytes(9).toString("hex");
}

async function waitForHttp(url, what, attempts = 60) {
  for (let attempt = 1; attempt <= attempts; attempt += 1) {
    try {
      const response = await fetch(url, { cache: "no-store" });
      if (response.ok) return;
    } catch {
      // Not up yet.
    }
    await new Promise((resolve) => setTimeout(resolve, 1000));
  }
  throw new Error(`${what} never answered at ${url} after ${attempts} attempts`);
}

async function api(path, { method = "GET", token = null, body = null, headers = {} } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    cache: "no-store",
    headers: {
      ...(body === null ? {} : { "Content-Type": "application/json" }),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
      ...headers,
    },
    body: body === null ? undefined : JSON.stringify(body),
  });
  const text = await response.text();
  let json = null;
  try {
    json = text ? JSON.parse(text) : null;
  } catch {
    json = null;
  }
  return { status: response.status, json, text };
}

function expectStatus(result, expected, what) {
  assert.equal(
    result.status,
    expected,
    `${what} answered ${result.status}, expected ${expected}: ${result.text.slice(0, 400)}`,
  );
}

/* ------------------------------------------------------------------ */
/* Stand the account up through the real registration path             */
/* ------------------------------------------------------------------ */

await waitForHttp(`${API_BASE}/health`, "the API");
await waitForHttp(`${WEB_ORIGIN}/control`, "the web server");

/**
 * THE ORIGIN THE BROWSER WILL SPEAK FROM, checked before a panel is blamed.
 *
 * Measured on 2026-09-10 while proving this file: with the web server on port
 * 3001 and everything else identical, every API side check passed, the page
 * loaded, no page error was thrown, and `/control/roster` rendered
 * "ROSTER UNREADABLE ... Failed to fetch". The panel was correct and the
 * harness was wrong. `app/core/config.py:CORS_ORIGINS` allows exactly
 * `http://localhost:3000` and `http://127.0.0.1:3000`, so a run pointed at any
 * other origin gets refused at the browser and the refusal reads, everywhere it
 * surfaces, as a broken read.
 *
 * A red that names the wrong culprit is the failure mode this whole estate is
 * organised against, so the condition is MEASURED rather than documented: an
 * actual CORS preflight, from the actual origin, against a route the panels
 * actually call. The API's allowlist is not read from a file here, because a
 * file is a claim and the header the browser will obey is the fact.
 */
const preflight = await fetch(`${API_BASE}/agents`, {
  method: "OPTIONS",
  cache: "no-store",
  headers: {
    Origin: WEB_ORIGIN,
    "Access-Control-Request-Method": "GET",
    "Access-Control-Request-Headers": "authorization",
  },
});
const allowedOrigin = preflight.headers.get("access-control-allow-origin");
if (allowedOrigin !== WEB_ORIGIN && allowedOrigin !== "*") {
  throw new Error(
    `the API will not accept a browser request from ${WEB_ORIGIN}. Its preflight ` +
      `answered ${preflight.status} with access-control-allow-origin ` +
      `${allowedOrigin === null ? "absent" : JSON.stringify(allowedOrigin)}. Every ` +
      "panel would render its unreadable rung and the run would blame the panel " +
      "for the harness. Serve the web app on an origin in " +
      "app/core/config.py:CORS_ORIGINS (http://127.0.0.1:3000 or " +
      "http://localhost:3000), or add this one there deliberately.",
  );
}

const RUN = nonce();
// example.com is reserved by IANA for documentation and can never route to a
// real mailbox, so a throwaway account here cannot become mail to anybody.
const EMAIL = `panel-smoke-${RUN}@example.com`;
const PASSWORD = `panel-smoke-${nonce()}`;

const registered = await api("/auth/register", {
  method: "POST",
  body: { email: EMAIL, password: PASSWORD, full_name: "panel smoke" },
  headers: { "X-Devon-Registration-Key": REGISTRATION_KEY },
});
expectStatus(registered, 201, "POST /auth/register");

/**
 * Log in, with a bounded retry, and say out loud when one was needed.
 *
 * Measured on 2026-09-10 while building this file: one run in eight registered
 * 201 and then got 401 from the very next request, and the API's own SQL log
 * showed the login SELECT returning in 3 ms. A login that finds the row and
 * rejects the password takes 292 ms here, because bcrypt at 12 rounds does the
 * work; a login that finds no row takes 6 ms. So that read did not see a row
 * committed 11 ms earlier, on a pooled connection that had been idle four
 * minutes. It did not recur in 25 dedicated register-then-login attempts or in
 * seven further whole runs, and it is not understood.
 *
 * The retry is in the harness rather than in the assertions on purpose: it waits
 * for the API's own write to become visible and it fails loudly if it never
 * does. It cannot mask a broken panel, because no panel has run yet. When it
 * takes more than one attempt the run says so, so the fact reaches the log
 * instead of being smoothed away.
 */
const LOGIN_ATTEMPTS = 8;
let loggedIn = null;
let loginAttempt = 0;
for (loginAttempt = 1; loginAttempt <= LOGIN_ATTEMPTS; loginAttempt += 1) {
  loggedIn = await api("/auth/login", {
    method: "POST",
    body: { email: EMAIL, password: PASSWORD },
  });
  if (loggedIn.status === 200) break;
  await new Promise((resolve) => setTimeout(resolve, 500));
}
if (loginAttempt > 1 && loggedIn.status === 200) {
  console.log(
    `note: POST /auth/login needed ${loginAttempt} attempts after a 201 from register`,
  );
}
expectStatus(loggedIn, 200, `POST /auth/login (after ${loginAttempt} attempt(s))`);
const TOKEN = loggedIn.json?.access_token;
assert.equal(
  typeof TOKEN,
  "string",
  `POST /auth/login answered 200 without an access_token: ${loggedIn.text.slice(0, 200)}`,
);
assert.ok(TOKEN.length > 20, "the access token is implausibly short");

console.log(`account: ${EMAIL}`);

/* ------------------------------------------------------------------ */
/* Seed one row per account scoped panel, each carrying this run's nonce */
/* ------------------------------------------------------------------ */

const PROJECT_NAME = `smoke project ${RUN}`;
const project = await api("/projects", {
  method: "POST",
  token: TOKEN,
  body: { name: PROJECT_NAME, description: `seeded by panel-smoke run ${RUN}` },
});
expectStatus(project, 201, "POST /projects");
const PROJECT_ID = project.json.id;

const MEMORY_CONTENT = `smoke memory ${RUN}`;
const memory = await api("/memory", {
  method: "POST",
  token: TOKEN,
  body: { content: MEMORY_CONTENT, memory_type: "context", importance: 7 },
});
expectStatus(memory, 201, "POST /memory");
const MEMORY_ID = memory.json.id;

const DECISION_QUESTION = `smoke decision ${RUN}`;
const decision = await api("/decisions", {
  method: "POST",
  token: TOKEN,
  body: { question: DECISION_QUESTION, options: [`option ${RUN}`, "the other one"] },
});
expectStatus(decision, 201, "POST /decisions");
const DECISION_ID = decision.json.id;

const WORKFLOW_NAME = `smoke workflow ${RUN}`;
// Two steps on purpose, one of them an effect step. The door renders a sentence
// derived from the API's own description of the stored definition, so a run that
// gets that sentence back has proved a read the list route alone could not.
const workflow = await api("/workflows", {
  method: "POST",
  token: TOKEN,
  body: {
    name: WORKFLOW_NAME,
    description: `seeded by panel-smoke run ${RUN}`,
    definition: {
      version: 1,
      trigger: { type: "manual", config: {} },
      steps: [
        { id: "recall", type: "knowledge_search", config: { query: "{{ input }}", limit: 3 } },
        {
          id: "remember",
          type: "memory_write",
          config: { content: "{{ recall }}", importance: 4 },
        },
      ],
    },
  },
});
expectStatus(workflow, 201, "POST /workflows");
const WORKFLOW_ID = workflow.json.id;

console.log(
  `seeded: project ${PROJECT_ID}, memory ${MEMORY_ID}, decision ${DECISION_ID}, workflow ${WORKFLOW_ID}`,
);

/* ------------------------------------------------------------------ */
/* The verdicts the shipped ladders reach over what the API is serving  */
/* ------------------------------------------------------------------ */

const agentsRead = await api("/agents", { token: TOKEN });
expectStatus(agentsRead, 200, "GET /agents");
const roster = parseRosterPayload(agentsRead.json);
assert.ok(roster.wasArray, "GET /agents did not answer with a JSON array");
const rosterVerdict = readRosterVerdict({
  state: "ok",
  count: roster.rows.length,
  dropped: roster.dropped,
  contradicted: roster.rows.filter((row) => row.isActive === false).length,
});

const projectsRead = await api("/projects", { token: TOKEN });
expectStatus(projectsRead, 200, "GET /projects");
const projects = parseProjectsPayload(projectsRead.json);
assert.notEqual(projects, null, "GET /projects did not answer with a readable list");
const projectsVerdict = readProjectsVerdict({
  state: "ok",
  count: projects.rows.length,
  malformed: projects.malformedRows,
  duplicates: projects.duplicateRows,
});

const memoryRead = await api("/memory?include_inactive=true", { token: TOKEN });
expectStatus(memoryRead, 200, "GET /memory");
const memories = parseMemoryPayload(memoryRead.json);
const memoryTally = summarizeMemories(memories);
assert.notEqual(memoryTally, null, "GET /memory did not answer with a readable list");
const memoryVerdict = readMemoryVerdict({ state: "ok", tally: memoryTally });

const decisionsRead = await api("/decisions", { token: TOKEN });
expectStatus(decisionsRead, 200, "GET /decisions");
const decisions = parseDecisionList(decisionsRead.json);
assert.notEqual(decisions, null, "GET /decisions did not answer with a readable list");
const decisionsVerdict = readDecisionsVerdict({
  state: "ok",
  rows: decisions.rows,
  malformed: decisions.malformed,
});

const workflowsRead = await api("/workflows?limit=100", { token: TOKEN });
expectStatus(workflowsRead, 200, "GET /workflows");
assert.ok(Array.isArray(workflowsRead.json), "GET /workflows did not answer with an array");
const workflowsVerdict = readListVerdict({ state: "ok", count: workflowsRead.json.length });

const catalogRead = await api("/workflows/step-types", { token: TOKEN });
expectStatus(catalogRead, 200, "GET /workflows/step-types");
const catalog = parseCatalog(catalogRead.json);
assert.notEqual(catalog, null, "GET /workflows/step-types did not answer with a step catalog");
const catalogVerdict = readCatalogVerdict({ state: "ok", count: catalog.length });

const seededRow = workflowsRead.json.find((row) => row.id === WORKFLOW_ID);
assert.ok(seededRow, "the workflow just created is not in GET /workflows");
const summarySentence = readSummary(seededRow.summary).sentence;

/* ------------------------------------------------------------------ */
/* Layer 3: what this run SEEDED, not what the API replayed            */
/* ------------------------------------------------------------------ */

/**
 * WHY THIS BLOCK EXISTS, and what went green without it.
 *
 * The two layers above are independent of the PANEL. Neither is independent of
 * the API. Both the expected verdict and, for the roster, the evidence needles
 * are computed from the very payload the browser is about to render, so when
 * the API's own answer degrades the harness degrades with it and the two agree.
 * Measured on 2026-09-10 at 5ff4348, twice:
 *
 *  - GET /agents returning its nine rows with `slug` renamed to `SLUG`: every
 *    row was dropped, `roster.rows` went empty, so the nine slug needles
 *    VANISHED rather than failing, the expected verdict became ROSTER EMPTY,
 *    the panel rendered ROSTER EMPTY, and the run reported "98 checks passed"
 *    and exit 0. Twenty checks disappeared and nothing noticed.
 *  - describe_definition returning `approval_steps: []`: the door rendered
 *    "2 steps, no step in it stops for a ruling" over a definition whose second
 *    step is an effect step, the harness asserted that exact sentence, and the
 *    run reported "118 checks passed" and exit 0. A human gate was drawn as
 *    absent and the check certified it.
 *
 * So these assertions are pinned to what this process SEEDED and to what the
 * registry is known to be, and never re-derived from the response. They run
 * before the browser opens, so a red here is unambiguous: the API is wrong,
 * not the panel.
 */

// The registry is module level code in services/agents/registry.py, not a
// table, so the list route cannot honestly answer with nothing and cannot
// honestly drop a row it just built from AgentSummary.
check("GET /agents dropped no row for failing AgentSummary's shape", () => {
  assert.equal(
    roster.dropped,
    0,
    `GET /agents returned ${roster.dropped} row(s) that did not carry the six fields ` +
      `AgentSummary declares. The roster panel draws that as a payload mismatch and this ` +
      `check would otherwise agree with it, so the run would go green over a broken route.`,
  );
});
check("GET /agents returned a non-empty roster", () => {
  assert.ok(
    roster.rows.length > 0,
    "GET /agents returned no usable rows. The registry is code, so an empty roster here is a " +
      "broken read rather than a registry finding.",
  );
});

// This process created the workflow below, so its shape is known here and is
// not a thing to read back out of the answer.
const SEEDED_STEP_COUNT = 2;
const SEEDED_GATED_STEP = "remember";
const seededSummary = readSummary(seededRow.summary);
check("the seeded workflow's definition still parses on the API side", () => {
  assert.ok(
    seededSummary.parses,
    `the API could not parse the definition just stored: ${seededSummary.error}`,
  );
});
check(`the API still reports ${SEEDED_STEP_COUNT} steps for the workflow this run seeded`, () => {
  assert.equal(seededSummary.stepCount, SEEDED_STEP_COUNT);
});
check(`the API still reports ${JSON.stringify(SEEDED_GATED_STEP)} as stopping for a ruling`, () => {
  assert.ok(
    seededSummary.gatedSteps.includes(SEEDED_GATED_STEP),
    `the workflow this run seeded has an effect step (${SEEDED_GATED_STEP}, a memory_write) that ` +
      `requires human approval, and the API described its gated steps as ` +
      `${JSON.stringify(seededSummary.gatedSteps)}. The door renders that description verbatim, ` +
      `so without this line the run certifies a human gate drawn as absent.`,
  );
});

// The rows this run seeded must survive each panel's own shape check. A parser
// that drops them renders an honest "payload mismatch" rung that the layers
// above would happily agree with.
check("GET /projects dropped no row and saw no duplicate", () => {
  assert.equal(projects.malformedRows, 0, "GET /projects returned unusable rows");
  assert.equal(projects.duplicateRows, 0, "GET /projects returned duplicate ids");
});
check("GET /memory dropped no row", () => {
  assert.equal(memoryTally.malformed, 0, "GET /memory returned rows with no usable id");
});
check("GET /decisions dropped no row", () => {
  assert.equal(decisions.malformed, 0, "GET /decisions returned unusable rows");
});

// Each seeded row must be reachable by id in the payload the browser will get,
// so that a needle which VANISHES is caught here rather than silently reducing
// the number of assertions the run makes.
for (const [what, rows, id] of [
  ["project", projects.rows, PROJECT_ID],
  ["memory", memories.shape === "list" ? memories.rows : [], MEMORY_ID],
  ["decision", decisions.rows, DECISION_ID],
]) {
  check(`the ${what} this run seeded is in the list the browser will fetch`, () => {
    assert.ok(
      rows.some((row) => row.id === id),
      `the ${what} created moments ago (${id}) is not in the parsed list, so the needle ` +
        `asserted on the page below could only ever be absent.`,
    );
  });
}


// Every rung of every ladder that is NOT the one a live read reaches. Computed
// from the shipped functions rather than typed, so a rename cannot leave this
// file guarding a string nothing renders.
function otherRungs(reached, reads, ladder) {
  const labels = new Set();
  for (const read of reads) {
    const label = ladder(read).label;
    if (label !== reached.label) labels.add(label);
  }
  return [...labels];
}

const FORBIDDEN = {
  roster: otherRungs(
    rosterVerdict,
    [
      { state: "loading" },
      { state: "unauthorized", status: 401 },
      { state: "failed", detail: "x" },
      { state: "ok", count: 0, dropped: 0, contradicted: 0 },
      { state: "ok", count: 1, dropped: 0, contradicted: 1 },
    ],
    readRosterVerdict,
  ),
  projects: otherRungs(
    projectsVerdict,
    [
      { state: "locked" },
      { state: "failed", detail: "x" },
      { state: "ok", count: 0, malformed: 1, duplicates: 0 },
      { state: "ok", count: 0, malformed: 0, duplicates: 0 },
    ],
    readProjectsVerdict,
  ),
  memory: otherRungs(
    memoryVerdict,
    [
      { state: "pending" },
      { state: "locked" },
      { state: "failed", detail: "x" },
      { state: "ok", tally: { total: 0, active: 0, paused: 0, unknownActivity: 0, malformed: 1 } },
      { state: "ok", tally: { total: 0, active: 0, paused: 0, unknownActivity: 0, malformed: 0 } },
    ],
    readMemoryVerdict,
  ),
  decisions: otherRungs(
    decisionsVerdict,
    [
      { state: "locked" },
      { state: "failed", detail: "x" },
      { state: "ok", rows: [], malformed: 0 },
    ],
    readDecisionsVerdict,
  ),
  workflows: otherRungs(
    workflowsVerdict,
    [
      { state: "locked" },
      { state: "failed", detail: "x" },
      { state: "ok", count: 0 },
    ],
    readListVerdict,
  ),
  catalog: otherRungs(
    catalogVerdict,
    [{ state: "locked" }, { state: "failed", detail: "x" }, { state: "ok", count: 0 }],
    readCatalogVerdict,
  ),
};

// A ladder whose rungs all render the same words would make the absence checks
// vacuous, so say so here rather than discovering it in a green run.
for (const [name, labels] of Object.entries(FORBIDDEN)) {
  assert.ok(
    labels.length >= 2,
    `the ${name} ladder produced only ${labels.length} distinct label(s) other than the one a live read reaches, so the absence checks below would prove almost nothing`,
  );
}

/* ------------------------------------------------------------------ */
/* Drive the panels                                                    */
/* ------------------------------------------------------------------ */

const TOKEN_SLOT = tokenSlotFromSource();
const { chromium } = await loadPlaywright();
const executablePath = findChromium();
const browser = await chromium.launch({ executablePath });

/**
 * One panel as a route carries it: the rung a live read reaches, every other
 * rung its ladder can render, and the evidence only a live read produces.
 */
/**
 * The rungs that mean "the request has not answered yet".
 *
 * Two of these six ladders render a label while the read is in flight: the
 * roster's `loading` and memory's `pending`. Those are forbidden outcomes like
 * every other wrong rung, but they must not count as SETTLED, or the page
 * settles on the loading state milliseconds after navigation and every
 * assertion below fires against a panel that has not read anything yet.
 *
 * That is not hypothetical. The first version of this file put them in the
 * settle set and the very next run failed with "/control/roster did not render
 * ROSTER PRESENT; it rendered ROSTER READING instead". The other four ladders
 * draw a plain loading line rather than a rung, so they have none.
 */
const IN_FLIGHT = {
  roster: [readRosterVerdict({ state: "loading" }).label],
  projects: [],
  memory: [readMemoryVerdict({ state: "pending" }).label],
  decisions: [],
  workflows: [],
  catalog: [],
};

const PANEL = {
  roster: {
    expected: rosterVerdict,
    others: FORBIDDEN.roster,
    inFlight: IN_FLIGHT.roster,
    // The slugs the registry served in THIS run. A roster baked into the bundle
    // could not know them; only the read does.
    evidence: roster.rows.map((row) => row.slug),
  },
  projects: {
    expected: projectsVerdict,
    others: FORBIDDEN.projects,
    inFlight: IN_FLIGHT.projects,
    evidence: [PROJECT_NAME, PROJECT_ID],
  },
  memory: {
    expected: memoryVerdict,
    others: FORBIDDEN.memory,
    inFlight: IN_FLIGHT.memory,
    evidence: [MEMORY_CONTENT, MEMORY_ID],
  },
  decisions: {
    expected: decisionsVerdict,
    others: FORBIDDEN.decisions,
    inFlight: IN_FLIGHT.decisions,
    evidence: [DECISION_QUESTION, DECISION_ID],
  },
  workflows: {
    expected: workflowsVerdict,
    others: FORBIDDEN.workflows,
    inFlight: IN_FLIGHT.workflows,
    // The last of these is derived by the door from the API's own description of
    // the stored definition: step count, which step stops for a ruling, trigger.
    evidence: [WORKFLOW_NAME, WORKFLOW_ID, summarySentence],
  },
  catalog: {
    expected: catalogVerdict,
    others: FORBIDDEN.catalog,
    inFlight: IN_FLIGHT.catalog,
    // The catalog read has no row of its own to seed. Its sentence carries the
    // step type count the route served, which is asserted like every other.
    evidence: [],
  },
};

// An in-flight rung this file did not recognise as one would silently weaken
// every settle below, so prove each named rung is really on its own ladder.
for (const [name, labels] of Object.entries(IN_FLIGHT)) {
  for (const label of labels) {
    assert.ok(
      PANEL[name].others.includes(label),
      `${label} is named as ${name}'s in flight rung but its ladder no longer produces it`,
    );
  }
}

const ROUTES = [
  { path: "/control/roster", panels: ["roster"] },
  { path: "/control/projects", panels: ["projects"] },
  { path: "/control/memory", panels: ["memory"] },
  { path: "/control/decisions", panels: ["decisions"] },
  { path: "/control/workflows", panels: ["workflows", "catalog"] },
  // The hub, with every panel mounted at once. A panel that only works alone is
  // not the surface Tee opens.
  {
    path: "/control",
    panels: ["roster", "projects", "memory", "decisions", "workflows", "catalog"],
  },
];

/**
 * Settling is waiting for a TERMINAL rung, not for the right one.
 *
 * Waiting only for the rung a live read reaches makes every broken panel cost
 * the whole timeout and then report "timed out" rather than naming what the
 * panel rendered. Measured on 2026-09-10 against ten deliberate breakages: each
 * cost 20 s and reported a Playwright timeout. Waiting for ANY rung of the
 * ladder settles a broken panel in about a second and hands the assertions
 * below the real text to fail on.
 */
function settledLabels(name) {
  const panel = PANEL[name];
  return [panel.expected.label, ...panel.others].filter(
    (label) => !panel.inFlight.includes(label),
  );
}

function settleGroups(route) {
  return route.panels.map((name) => settledLabels(name));
}

const results = [];
try {
  const context = await browser.newContext();
  // The same slot DevonChat writes at sign-in, seeded before any page script
  // runs, on every page and frame in this context.
  await context.addInitScript(
    ({ slot, token }) => {
      try {
        localStorage.setItem(slot, token);
      } catch {
        // Reported by the panels themselves as a locked state, which fails below.
      }
    },
    { slot: TOKEN_SLOT, token: TOKEN },
  );

  for (const route of ROUTES) {
    const page = await context.newPage();
    const pageErrors = [];
    page.on("pageerror", (error) => pageErrors.push(String(error)));
    const at = Date.now();
    await page.goto(`${WEB_ORIGIN}${route.path}`, { waitUntil: "domcontentloaded" });
    let unsettled = null;
    try {
      await page.waitForFunction(
        (groups) => {
          const text = document.body.innerText;
          return groups.every((group) => group.some((label) => text.includes(label)));
        },
        settleGroups(route),
        { timeout: VERDICT_TIMEOUT_MS },
      );
    } catch (error) {
      unsettled = error instanceof Error ? error.message : String(error);
    }
    const text = await page.evaluate(() => document.body.innerText);
    results.push({
      path: route.path,
      panels: route.panels,
      text,
      unsettled,
      pageErrors,
      elapsedMs: Date.now() - at,
    });
    await page.close();
  }
} finally {
  await browser.close();
}

console.log(`chromium: ${executablePath}`);
for (const result of results) {
  console.log(
    `  ${result.path}: ${result.elapsedMs} ms, ${result.text.length} characters of rendered text`,
  );
}

/* ------------------------------------------------------------------ */
/* The assertions                                                      */
/* ------------------------------------------------------------------ */

function excerpt(text) {
  return text.replace(/\s+/g, " ").slice(0, 900);
}

function excerptNeedle(needle) {
  return needle.length > 70 ? `${needle.slice(0, 67)}...` : needle;
}

for (const result of results) {
  const { path, text } = result;

  check(`${path} settled every panel on it inside ${VERDICT_TIMEOUT_MS} ms`, () => {
    const stuck = result.panels.filter(
      (name) => !settledLabels(name).some((label) => text.includes(label)),
    );
    assert.equal(
      result.unsettled,
      null,
      `${path} never rendered any verdict for ${JSON.stringify(stuck)}. Those panels are still ` +
        `loading, or rendering something no rung of their ladder produces. Rendered text: ` +
        excerpt(text),
    );
  });

  check(`${path} threw no uncaught page error`, () => {
    assert.deepEqual(result.pageErrors, [], `${path} threw: ${result.pageErrors.join(" | ")}`);
  });

  for (const name of result.panels) {
    const panel = PANEL[name];

    check(`${path} ${name} reached ${JSON.stringify(panel.expected.label)}`, () => {
      const wrong = panel.others.filter((label) => text.includes(label));
      assert.ok(
        text.includes(panel.expected.label),
        `${path} did not render ${JSON.stringify(panel.expected.label)} for the ${name} panel` +
          (wrong.length ? `; it rendered ${JSON.stringify(wrong)} instead` : "") +
          `. Rendered text: ${excerpt(text)}`,
      );
    });

    check(`${path} ${name} rendered the ladder's own sentence for that rung`, () => {
      assert.ok(
        text.includes(panel.expected.sentence),
        `${path} rendered ${JSON.stringify(panel.expected.label)} for the ${name} panel without ` +
          `the sentence that rung carries, computed here from the payload the API is serving: ` +
          `${JSON.stringify(panel.expected.sentence)}. Rendered text: ${excerpt(text)}`,
      );
    });

    for (const needle of panel.evidence) {
      check(`${path} ${name} rendered ${JSON.stringify(excerptNeedle(needle))}`, () => {
        assert.ok(
          text.includes(needle),
          `${path} did not render ${JSON.stringify(needle)}, which was minted or read in this ` +
            `run and can only be on the page if the browser fetched it. Rendered text: ` +
            excerpt(text),
        );
      });
    }

    for (const label of panel.others) {
      check(`${path} ${name} did not render ${JSON.stringify(label)}`, () => {
        assert.ok(
          !text.includes(label),
          `${path} rendered ${JSON.stringify(label)} for the ${name} panel: a locked, ` +
            `unreadable, unusable or empty rung over a store this run seeded. Rendered text: ` +
            excerpt(text),
        );
      });
    }
  }
}

/**
 * A floor on the work this run did, because an assertion can go MISSING rather
 * than fail. Every evidence needle is derived from a list, and a list that comes
 * back short makes its needles disappear: the malformed /agents payload measured
 * on 2026-09-10 took the run from 118 checks to 98 and still exited 0.
 *
 * The structure is asserted first, because that is the thing worth pinning: a
 * route quietly dropped from ROUTES, or a panel dropped from a route's list,
 * removes a whole block of assertions and shows up nowhere else.
 *
 * The numeric floor deliberately EXCLUDES the roster slug needles. There is one
 * of those per registered agent per route the roster is on, so counting them
 * would couple this number to services/agents/registry.py and turn "an agent was
 * retired" into a red run with a message about missing assertions. Registering a
 * tenth agent must not be able to hide a lost check either, so they are counted
 * out rather than absorbed.
 */
const ROSTER_ROUTES = ROUTES.filter((route) => route.panels.includes("roster")).length;
const rosterNeedleChecks = PANEL.roster.evidence.length * ROSTER_ROUTES;
const structuralChecks = checks - rosterNeedleChecks;

assert.equal(ROUTES.length, 6, "a route has been added to or removed from ROUTES");
assert.deepEqual(
  ROUTES.map((route) => `${route.path}:${route.panels.join(",")}`),
  [
    "/control/roster:roster",
    "/control/projects:projects",
    "/control/memory:memory",
    "/control/decisions:decisions",
    "/control/workflows:workflows,catalog",
    "/control:roster,projects,memory,decisions,workflows,catalog",
  ],
  "the routes this check drives, or the panels it asserts on one of them, have changed. " +
    "Update this list deliberately; a panel silently dropped from a route removes every " +
    "assertion about it and the run still ends green.",
);

const CHECK_FLOOR = Number(process.env.SMOKE_CHECK_FLOOR || 111);
assert.ok(
  structuralChecks >= CHECK_FLOOR,
  `only ${structuralChecks} registry independent checks ran (${checks} total, less ` +
    `${rosterNeedleChecks} roster slug needles), and this run is expected to make at least ` +
    `${CHECK_FLOOR}. Assertions did not fail, they went MISSING: an evidence list came back ` +
    `shorter than it should have, so the needles derived from it were never asserted.`,
);

const seconds = ((Date.now() - STARTED_AT) / 1000).toFixed(1);
console.log(
  `panel-smoke: ${checks} checks passed in real Chromium over ${ROUTES.length} routes in ${seconds}s`,
);
