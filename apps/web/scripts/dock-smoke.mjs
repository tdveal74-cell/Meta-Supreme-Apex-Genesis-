/**
 * Does the capability dock tell the truth about soul, in a browser?
 *
 * Run from apps/web against a stack that is already up, the same stack
 * scripts/panel-smoke.mjs runs against:
 *
 *   SMOKE_API_BASE=http://127.0.0.1:8000/api/v1 \
 *   SMOKE_WEB_ORIGIN=http://127.0.0.1:3000 \
 *   DEVON_REGISTRATION_KEY=... \
 *   node --experimental-strip-types scripts/dock-smoke.mjs
 *
 * WHY A BROWSER AND NOT ANOTHER AST CHECK
 *
 * On 2026-09-15 the Soul tile in CapabilityDock.tsx was given a three way read
 * (recall on, recall off, status unread) and two AST checks in
 * scripts/honesty-check.ts to hold it. A critic then made twelve edits that
 * made the panel lie and eleven of them passed those checks green, because a
 * shape check pins one expression and a lie can be written around it. The
 * checks were rewritten to pin more, and they will be beaten again by an edit
 * nobody has thought of yet. What cannot be edited around is the rendered
 * text: this file puts a real token and then a refused one into the slot the
 * dock reads, opens /command-center in real Chromium, and asserts the words on
 * the page against words pinned HERE, not read out of the component. Change
 * the words in the dock and this goes red, which is a decision and not a
 * drift.
 *
 * WHAT IT DRIVES
 *
 * Two browser contexts against the same API. The API in this job carries no
 * soul variables, so with a real token the honest readout is "recall off",
 * the route's own detail naming SOUL_RECALL_ENABLED and PINECONE_API_KEY, and
 * this job's API host as the environment they belong to. With a token the
 * API refuses, every authenticated read is a 401, and the honest readout is
 * "status unread", a mesh count of 0/7, and a footer that says a read failed.
 * That second context is the one the first guard let through: a 401 rendered
 * as "recall off" until this date.
 *
 * It preflights both expectations against the API directly before opening
 * the browser, so a red here says which side is wrong. Same posture as
 * panel-smoke.mjs: Playwright and Chromium are resolved from the environment
 * and both resolvers THROW when missing, so a runner without a browser turns
 * the job red rather than green.
 */

import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";

const STARTED_AT = Date.now();

const API_BASE = (process.env.SMOKE_API_BASE || "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");
const WEB_ORIGIN = (process.env.SMOKE_WEB_ORIGIN || "http://127.0.0.1:3000").replace(/\/$/, "");
const REGISTRATION_KEY = process.env.DEVON_REGISTRATION_KEY || "";
const VERDICT_TIMEOUT_MS = Number(process.env.SMOKE_VERDICT_TIMEOUT_MS || 20000);

if (!REGISTRATION_KEY) {
  throw new Error(
    "DEVON_REGISTRATION_KEY is not set. Registration is closed by default " +
      "(app/api/v1/auth.py:_require_registration_key), so without it no account can be " +
      "made and the dock can only ever reach its locked state. Refusing to run a smoke " +
      "check that would prove nothing.",
  );
}

/* ------------------------------------------------------------------ */
/* Playwright and Chromium, resolved the way panel-smoke.mjs does      */
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
/* The two storage slots, cut out of the dock's own source             */
/* ------------------------------------------------------------------ */

/**
 * The dock reads its bearer token and its open flag from localStorage by
 * literal key (CapabilityDock.tsx, tokenFromDevice and the open effect).
 * Typing those keys here would mean a rename leaves this file seeding slots
 * nothing reads and the dock sitting locked while this check reports on it, so
 * both are cut out of the shipped source, and the token slot is held equal to
 * the one DevonChat writes at sign-in, because that is the only writer.
 */
function slotsFromSource() {
  const dock = readFileSync(new URL("../components/command-center/CapabilityDock.tsx", import.meta.url), "utf8");
  const chat = readFileSync(new URL("../components/devon/DevonChat.tsx", import.meta.url), "utf8");
  const keys = [...dock.matchAll(/localStorage\.getItem\("([^"]+)"\)/g)].map((m) => m[1]);
  const token = keys.find((k) => k.includes("token"));
  const open = keys.find((k) => k.includes("open"));
  assert.ok(token && open, `could not find both storage keys in CapabilityDock.tsx; found ${JSON.stringify(keys)}`);
  const written = chat.match(/const TOKEN_KEY = "([^"]+)"/);
  assert.ok(written, "DevonChat.tsx no longer declares TOKEN_KEY as a string literal");
  assert.equal(token, written[1], "the dock reads a different token slot from the one DevonChat writes at sign-in");
  return { token, open };
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

async function api(path, { method = "GET", token = null, body = null } = {}) {
  const response = await fetch(`${API_BASE}${path}`, {
    method,
    cache: "no-store",
    headers: {
      ...(body ? { "Content-Type": "application/json" } : {}),
      ...(token ? { Authorization: `Bearer ${token}` } : {}),
    },
    body: body ? JSON.stringify(body) : undefined,
  });
  const text = await response.text();
  let json = null;
  try {
    json = JSON.parse(text);
  } catch {
    // Not JSON; the text is reported instead.
  }
  return { status: response.status, json, text };
}

function expectStatus(result, expected, what) {
  assert.equal(result.status, expected, `${what} answered ${result.status}, expected ${expected}: ${result.text.slice(0, 300)}`);
}

function excerpt(text) {
  return text.replace(/\s+/g, " ").slice(0, 900);
}

/** The non-empty line after the first line equal to `label`, or null. */
function lineAfter(text, label) {
  const lines = text.split("\n").map((l) => l.trim());
  const at = lines.indexOf(label);
  if (at < 0) return null;
  return lines.slice(at + 1).find((l) => l.length > 0) ?? null;
}

/* ------------------------------------------------------------------ */
/* The stack, and a throwaway account                                  */
/* ------------------------------------------------------------------ */

await waitForHttp(`${API_BASE}/health`, "the API");
await waitForHttp(`${WEB_ORIGIN}/command-center`, "the web server");

const HOST = new URL(API_BASE).host;
const RUN = nonce();
const EMAIL = `dock-smoke-${RUN}@example.com`;
const PASSWORD = `dock-smoke-${nonce()}`;

const registered = await api("/auth/register", {
  method: "POST",
  body: { email: EMAIL, password: PASSWORD, full_name: `dock smoke ${RUN}`, registration_key: REGISTRATION_KEY },
});
expectStatus(registered, 201, "POST /auth/register");

// panel-smoke.mjs measured one login in eight missing the row it had just
// registered, so this retries the same way rather than reporting that as a
// dock finding.
let loggedIn = null;
for (let attempt = 1; attempt <= 8; attempt += 1) {
  loggedIn = await api("/auth/login", { method: "POST", body: { email: EMAIL, password: PASSWORD } });
  if (loggedIn.status === 200) break;
  await new Promise((resolve) => setTimeout(resolve, 250));
}
expectStatus(loggedIn, 200, "POST /auth/login");
const TOKEN = loggedIn.json?.access_token;
assert.ok(typeof TOKEN === "string" && TOKEN.length > 20, "POST /auth/login answered without a plausible access_token");
const REFUSED_TOKEN = `not-a-token-${nonce()}`;

console.log(`account: ${EMAIL}`);

/* ------------------------------------------------------------------ */
/* Preflight: what the API itself says, so a red below names the side  */
/* ------------------------------------------------------------------ */

const statusOpen = await api("/soul/status");
check("GET /soul/status refuses an anonymous caller, so a refused token below is a real refusal", () => {
  expectStatus(statusOpen, 401, "GET /soul/status with no token");
});

const statusRefused = await api("/soul/status", { token: REFUSED_TOKEN });
check("GET /soul/status refuses the token this run will feed the second context", () => {
  expectStatus(statusRefused, 401, "GET /soul/status with a refused token");
});

const statusRead = await api("/soul/status", { token: TOKEN });
check("GET /soul/status answers the real token with recall off and names both variables", () => {
  expectStatus(statusRead, 200, "GET /soul/status");
  assert.equal(
    statusRead.json?.enabled,
    false,
    "this job's API reports soul recall ON. The stack this check stands up carries no " +
      "SOUL_RECALL_ENABLED or PINECONE_API_KEY, so an enabled answer means the job's " +
      "environment changed and this check's expectation has to be revisited, not skipped",
  );
  assert.ok(
    /SOUL_RECALL_ENABLED/.test(statusRead.json?.detail || "") && /PINECONE_API_KEY/.test(statusRead.json?.detail || ""),
    `the off detail no longer names both variables: ${JSON.stringify(statusRead.json?.detail)}`,
  );
});
const DETAIL = statusRead.json.detail;

const toolsRead = await api("/agent-tasks/tools", { token: TOKEN });
check("GET /agent-tasks/tools answers the real token, so the mesh count will be non-zero", () => {
  expectStatus(toolsRead, 200, "GET /agent-tasks/tools");
});

/* ------------------------------------------------------------------ */
/* The browser                                                         */
/* ------------------------------------------------------------------ */

const SLOTS = slotsFromSource();
const { chromium } = await loadPlaywright();
const executablePath = findChromium();
const browser = await chromium.launch({ executablePath });

const SETTLED = ["recall on", "recall off", "status unread"];

async function readDock(token, label) {
  const context = await browser.newContext();
  await context.addInitScript(
    ({ slots, value }) => {
      try {
        localStorage.setItem(slots.token, value);
        localStorage.setItem(slots.open, "1");
      } catch {
        // The dock reports this as its locked state, which fails below.
      }
    },
    { slots: SLOTS, value: token },
  );
  const page = await context.newPage();
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  const at = Date.now();
  await page.goto(`${WEB_ORIGIN}/command-center`, { waitUntil: "domcontentloaded" });
  let unsettled = null;
  try {
    await page.waitForFunction(
      (words) => {
        const text = document.body.innerText;
        return !text.includes("MESH CHECKING") && !text.includes("MESH LOCKED") && words.some((w) => text.includes(w));
      },
      SETTLED,
      { timeout: VERDICT_TIMEOUT_MS },
    );
  } catch (error) {
    unsettled = error instanceof Error ? error.message : String(error);
  }
  const text = await page.evaluate(() => document.body.innerText);
  await context.close();
  console.log(`  ${label}: ${Date.now() - at} ms, ${text.length} characters of rendered text`);
  return { text, unsettled, pageErrors };
}

let real;
let refused;
try {
  real = await readDock(TOKEN, "real token");
  refused = await readDock(REFUSED_TOKEN, "refused token");
} finally {
  await browser.close();
}
console.log(`chromium: ${executablePath}`);

/* ------------------------------------------------------------------ */
/* With a real token: recall off, the route's words, this API's host   */
/* ------------------------------------------------------------------ */

check("real token: the dock settled inside the timeout", () => {
  assert.equal(real.unsettled, null, `the dock never settled: ${excerpt(real.text)}`);
});
check("real token: no uncaught page error", () => {
  assert.deepEqual(real.pageErrors, [], real.pageErrors.join(" | "));
});
check("real token: the mesh counted at least one capability, so the tools read reached the page", () => {
  const m = real.text.match(/MESH (\d)\/7/);
  assert.ok(m, `no MESH n/7 readout on the page: ${excerpt(real.text)}`);
  assert.ok(Number(m[1]) >= 1, `the mesh reads ${m[0]} with a token the API accepted: ${excerpt(real.text)}`);
});
check('real token: the Soul tile reads "recall off"', () => {
  assert.ok(real.text.includes("recall off"), excerpt(real.text));
  assert.ok(!real.text.includes("recall on"), `the tile reads recall on while the API answered enabled false: ${excerpt(real.text)}`);
  assert.ok(!real.text.includes("status unread"), `the tile reads status unread while the API answered 200: ${excerpt(real.text)}`);
});
check('real token: the Soul recall panel header reads "OFF"', () => {
  assert.equal(lineAfter(real.text, "SOUL RECALL"), "OFF", excerpt(real.text));
});
check("real token: the note carries the route's own detail, word for word", () => {
  assert.ok(real.text.includes(DETAIL), `the page does not carry ${JSON.stringify(DETAIL)}: ${excerpt(real.text)}`);
});
check("real token: the note names this API's host as where the variables belong", () => {
  assert.ok(real.text.includes(`Those variables belong to the environment of ${HOST}`), excerpt(real.text));
});
check("real token: the note does not send the reader to a Vercel project", () => {
  assert.ok(!/vercel/i.test(real.text), excerpt(real.text));
});
check("real token: the footer names the host it read", () => {
  assert.ok(real.text.includes(`Reads ${HOST}.`), excerpt(real.text));
});
check("real token: the checking arm is gone once the route answered", () => {
  assert.ok(!real.text.includes("has not answered yet"), excerpt(real.text));
});

/* ------------------------------------------------------------------ */
/* With a refused token: unread, not off                               */
/* ------------------------------------------------------------------ */

check("refused token: the dock settled inside the timeout", () => {
  assert.equal(refused.unsettled, null, `the dock never settled: ${excerpt(refused.text)}`);
});
check("refused token: no uncaught page error", () => {
  assert.deepEqual(refused.pageErrors, [], refused.pageErrors.join(" | "));
});
check('refused token: the Soul tile reads "status unread", not "recall off"', () => {
  assert.ok(refused.text.includes("status unread"), excerpt(refused.text));
  assert.ok(
    !refused.text.includes("recall off"),
    `a 401 on /soul/status rendered as recall off, the same words the route uses when it answers enabled: false. This is the lie the tile existed to remove: ${excerpt(refused.text)}`,
  );
  assert.ok(!refused.text.includes("recall on"), excerpt(refused.text));
});
check('refused token: the Soul recall panel header reads "UNREAD"', () => {
  assert.equal(lineAfter(refused.text, "SOUL RECALL"), "UNREAD", excerpt(refused.text));
});
check("refused token: the note says the route did not answer and names the host it asked", () => {
  assert.ok(refused.text.includes(`Soul status unread. GET /soul/status on ${HOST} did not answer`), excerpt(refused.text));
});
check("refused token: the mesh counts nothing and the footer says a read failed", () => {
  assert.ok(refused.text.includes("MESH 0/7"), excerpt(refused.text));
  assert.ok(refused.text.includes("One or more telemetry reads failed."), excerpt(refused.text));
});
check("refused token: the route's off detail is not on the page, because the route never answered", () => {
  assert.ok(!refused.text.includes(DETAIL), excerpt(refused.text));
});

/* ------------------------------------------------------------------ */
/* A floor, so an assertion cannot go missing rather than fail         */
/* ------------------------------------------------------------------ */

const CHECK_FLOOR = 20;
assert.ok(checks >= CHECK_FLOOR, `only ${checks} checks ran; this file is expected to make at least ${CHECK_FLOOR}`);

const seconds = ((Date.now() - STARTED_AT) / 1000).toFixed(1);
console.log(`dock-smoke: ${checks} checks passed in real Chromium over two contexts in ${seconds}s`);
