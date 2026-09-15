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
 * (recall on, recall off, status unread) and AST checks in
 * scripts/honesty-check.ts to hold it. Two critics that day made twenty one
 * edits that made the panel lie; the AST checks passed twenty of them and the
 * first version of this file, which read document.body.innerText and nothing
 * else, would have passed six of the second critic's nine: a light lit green
 * from inside the map callback, header text painted in the background colour
 * beside a static ON, the soul fetch aimed at another route with a fallback
 * sentence identical to the route's own, the on state never driven at all.
 *
 * So this file asserts what a person sees and what the network carried, not
 * what a string search finds:
 *
 *   - the request: the browser's GET to /soul/status is captured, its status
 *     and its Authorization header asserted, in every context;
 *   - the pixels: the Soul light's computed background colour, the header
 *     value's computed colour and opacity, and document.elementFromPoint at
 *     the centre of the light, the header value, the tile word and the note,
 *     which must resolve to those elements and nothing painted over them;
 *     and, on every element inside the section, opacity, visibility, filter,
 *     background-image, transform, clip-path, box-shadow, font size, text
 *     fill colour and ::before and ::after content, because a third critic
 *     painted an emerald gradient over the grey light, zeroed the tile word
 *     and wrote "recall on" into ::after, and hid the header value and the
 *     note behind filter:opacity(0) beside ::after text, all invisible to
 *     innerText and to the reads above;
 *   - the grid: the tile labels are exactly the eight pinned ones in order,
 *     because a second Soul tile lit beside the first would be read by
 *     nobody, both readers taking the first match;
 *   - the words: exact innerText of the tile word, the header row and the
 *     note, scoped to the dock's own section, against sentences pinned HERE;
 *   - the on state: a third context answers /soul/status through a Playwright
 *     route mock with enabled true and the route's exact on detail, which the
 *     job's API cannot produce because it carries no soul variables;
 *   - the count: the shell button beside the section (the only place the
 *     mesh number renders) reads exactly MESH n/7, with n the count derived
 *     from the tools catalogue this run fetched, plus one in the on context;
 *   - the floor: an exact check count, so a deleted check is a red run.
 *
 * Change the words in the dock and this goes red, which is a decision and not
 * a drift. Same posture as panel-smoke.mjs: Playwright and Chromium resolved
 * from the environment, both resolvers THROW when missing.
 *
 * Running it on a web port other than 3000: the API's CORS_ORIGINS defaults
 * to ports 3000 only (app/core/config.py:123), so the browser's read dies in
 * preflight and this file times out at waitForResponse with no assertion
 * named. Set CORS_ORIGINS='["http://127.0.0.1:<port>"]' on the API first.
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
/* The words, pinned here. app/api/v1/soul.py:83-86 and                */
/* CapabilityDock.tsx soulNote. A change on either side is a red run.  */
/* ------------------------------------------------------------------ */

const OFF_DETAIL = "Soul recall is off. SOUL_RECALL_ENABLED and PINECONE_API_KEY turn it on.";
const ON_DETAIL = "Soul recall is on.";
const HOST = new URL(API_BASE).host;
const NOTE_UNREAD = `Soul status unread. GET /soul/status on ${HOST} did not answer, so whether recall is on is unknown here.`;
const NOTE_OFF = `${OFF_DETAIL} Those variables belong to the environment of ${HOST}, the only host this readout asks.`;
const NOTE_ON = `${ON_DETAIL} Configured rather than probed: the status route never calls Pinecone, so only a recall proves the connection.`;
const FAILED_FOOTER = "One or more telemetry reads failed.";

// Tailwind's emerald-400 and the dock's own greys and ambers, as Chromium
// reports them from getComputedStyle.
const EMERALD = "rgb(52, 211, 153)";
const GREY = "rgb(82, 105, 121)";
const AMBER = "rgb(212, 160, 23)";
const COPPER = "rgb(199, 123, 74)";

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
  const failures = [];
  for (const candidate of PLAYWRIGHT_CANDIDATES) {
    try {
      return await import(candidate);
    } catch (error) {
      failures.push(`${candidate}: ${error instanceof Error ? error.message : String(error)}`);
    }
  }
  throw new Error(`playwright could not be imported. Set PLAYWRIGHT_MODULE to its index.mjs, or install it. ${failures.join(" | ")}`);
}

function findChromium() {
  const found = CHROME_CANDIDATES.find((path) => path.startsWith("/") && existsSync(path));
  if (!found) {
    throw new Error("no Chromium binary found. Set CHROMIUM_BINARY. Tried: " + CHROME_CANDIDATES.join(", "));
  }
  return found;
}

/* ------------------------------------------------------------------ */
/* The two storage slots, cut out of the dock's own source             */
/* ------------------------------------------------------------------ */

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
  return String(text).replace(/\s+/g, " ").slice(0, 700);
}

/* ------------------------------------------------------------------ */
/* The stack, and a throwaway account                                  */
/* ------------------------------------------------------------------ */

await waitForHttp(`${API_BASE}/health`, "the API");
await waitForHttp(`${WEB_ORIGIN}/command-center`, "the web server");

const RUN = nonce();
const EMAIL = `dock-smoke-${RUN}@example.com`;
const PASSWORD = `dock-smoke-${nonce()}`;

const registered = await api("/auth/register", {
  method: "POST",
  body: { email: EMAIL, password: PASSWORD, full_name: `dock smoke ${RUN}`, registration_key: REGISTRATION_KEY },
});
expectStatus(registered, 201, "POST /auth/register");

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
check("GET /soul/status answers the real token with recall off and the pinned off detail, word for word", () => {
  expectStatus(statusRead, 200, "GET /soul/status");
  assert.equal(
    statusRead.json?.enabled,
    false,
    "this job's API reports soul recall ON. The stack this check stands up carries no " +
      "SOUL_RECALL_ENABLED or PINECONE_API_KEY, so an enabled answer means the job's " +
      "environment changed and this check's expectation has to be revisited, not skipped",
  );
  assert.equal(statusRead.json?.detail, OFF_DETAIL, "app/api/v1/soul.py's off detail is no longer the sentence pinned in this file");
});

const toolsRead = await api("/agent-tasks/tools", { token: TOKEN });
const catalog = toolsRead.json || {};
// The dock's own count, minus soul: CapabilityDock.tsx activeCount.
const EXPECTED_OFF = [
  Boolean(catalog.operator?.enabled && catalog.operator?.configured),
  Boolean(catalog.github?.configured),
  Boolean(catalog.browser?.enabled),
  Boolean(catalog.council?.enabled),
  Boolean(catalog.expansion?.scheduler_status?.runs_goals),
  Boolean(catalog.execution?.effect_receipts),
].filter(Boolean).length;
check("GET /agent-tasks/tools answers the real token with the sections the dock's count reads", () => {
  expectStatus(toolsRead, 200, "GET /agent-tasks/tools");
  for (const key of ["operator", "github", "browser", "council", "expansion", "execution"]) {
    assert.ok(catalog[key] && typeof catalog[key] === "object", `the tools catalogue has no ${key} section, so the derived count reads nothing there`);
  }
});

/** The tile labels the grid must carry, in order; the same list is pinned in the AST by honesty-check.ts. */
const TILE_LABELS = ["Operator", "GitHub", "Browser", "Council", "Scheduler", "Receipts", "Soul", "Leases"];

/* ------------------------------------------------------------------ */
/* The browser                                                         */
/* ------------------------------------------------------------------ */

const SLOTS = slotsFromSource();
const { chromium } = await loadPlaywright();
const executablePath = findChromium();
const browser = await chromium.launch({ executablePath });

const SETTLED = ["on", "off", "unread"];

/**
 * One context per token. `mockOn` answers /soul/status through a route mock
 * with the route's exact on payload, and answers its CORS preflight, because
 * the page and the API are different origins. Everything else still reaches
 * the real API.
 */
async function readDock(token, label, { mockOn = false } = {}) {
  const context = await browser.newContext({ viewport: { width: 1280, height: 1800 } });
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

  let mocked = 0;
  if (mockOn) {
    await page.route(/\/soul\/status(\?.*)?$/, async (route) => {
      const cors = {
        "access-control-allow-origin": WEB_ORIGIN,
        "access-control-allow-headers": "authorization, content-type",
        "access-control-allow-methods": "GET, OPTIONS",
      };
      if (route.request().method() === "OPTIONS") {
        await route.fulfill({ status: 204, headers: cors });
        return;
      }
      mocked += 1;
      await route.fulfill({
        status: 200,
        contentType: "application/json",
        headers: cors,
        body: JSON.stringify({ enabled: true, tee_host_configured: true, devon_host_configured: true, detail: ON_DETAIL }),
      });
    });
  }

  const soulResponse = page.waitForResponse(
    (r) => /\/soul\/status(\?.*)?$/.test(r.url()) && r.request().method() === "GET",
    { timeout: VERDICT_TIMEOUT_MS },
  );
  const at = Date.now();
  await page.goto(`${WEB_ORIGIN}/command-center`, { waitUntil: "domcontentloaded" });
  const response = await soulResponse;
  const request = {
    url: response.url(),
    status: response.status(),
    authorization: (await response.request().allHeaders())["authorization"] || null,
  };

  let unsettled = null;
  try {
    await page.waitForFunction(
      (words) => {
        const sec = document.querySelector('section[data-dock="capability-mesh"]');
        if (!sec) return false;
        // The mesh label lives on the toggle button beside the section, not
        // inside it, and it reads CHECKING until every read has answered, so
        // the soul state is not final while it does.
        const shell = sec.parentElement && sec.parentElement.querySelector('button[aria-expanded="true"]');
        if (!shell) return false;
        const label = shell.innerText;
        if (label.includes("MESH CHECKING") || label.includes("MESH LOCKED")) return false;
        return words.includes(sec.getAttribute("data-soul-state"));
      },
      SETTLED,
      { timeout: VERDICT_TIMEOUT_MS },
    );
  } catch (error) {
    unsettled = error instanceof Error ? error.message : String(error);
  }

  const seen = await page.evaluate(() => {
    const sec = document.querySelector('section[data-dock="capability-mesh"]');
    if (!sec) return null;
    const cs = (el) => getComputedStyle(el);
    const describe = (el) => (el ? `${el.tagName.toLowerCase()}${[...el.attributes].map((a) => `[${a.name}="${a.value.slice(0, 40)}"]`).join("")}` : "none");
    const atPoint = (el) => {
      const r = el.getBoundingClientRect();
      const hit = document.elementFromPoint(r.left + r.width / 2, r.top + r.height / 2);
      return hit === el ? "self" : hit && el.contains(hit) ? "descendant" : describe(hit);
    };
    const tile = sec.querySelector('[data-tile="Soul"]');
    const light = tile ? tile.querySelector('[data-indicator="light"]') : null;
    const para = tile ? tile.querySelector("p") : null;
    const headerRow = sec.querySelector('[data-soul-header="row"]');
    const headerValue = sec.querySelector('[data-soul-header="value"]');
    const note = sec.querySelector('[data-soul-note="text"]');
    const shell = sec.parentElement ? sec.parentElement.querySelector('button[aria-expanded="true"]') : null;
    const emerald = "rgb(52, 211, 153)";
    // Every element inside the section, read for the ways a lie can be
    // painted without changing a word: dimmed, filtered, shadowed, given a
    // gradient, moved, clipped, shrunk to nothing, text filled in another
    // colour, or given ::before or ::after content that innerText never sees.
    const all = [sec, ...sec.querySelectorAll("*")];
    const ownText = (el) => [...el.childNodes].some((n) => n.nodeType === 3 && n.textContent.trim() !== "");
    const violations = [];
    for (const el of all) {
      const c = cs(el);
      const where = describe(el);
      if (c.opacity !== "1") violations.push(`${where} opacity ${c.opacity}`);
      if (c.visibility !== "visible") violations.push(`${where} visibility ${c.visibility}`);
      if (c.display === "none") violations.push(`${where} display none`);
      if (c.filter !== "none") violations.push(`${where} filter ${c.filter}`);
      if (c.backgroundImage !== "none") violations.push(`${where} background-image ${c.backgroundImage}`);
      if (c.transform !== "none") violations.push(`${where} transform ${c.transform}`);
      if (c.clipPath !== "none") violations.push(`${where} clip-path ${c.clipPath}`);
      const litLight = el.getAttribute("data-indicator") === "light" && c.backgroundColor === emerald;
      if (el !== sec && c.boxShadow !== "none" && !litLight) violations.push(`${where} box-shadow ${c.boxShadow}`);
      for (const pseudo of ["::before", "::after"]) {
        const content = getComputedStyle(el, pseudo).content;
        if (content !== "none" && content !== "normal") violations.push(`${where}${pseudo} content ${content}`);
      }
      if (ownText(el)) {
        if (!(parseFloat(c.fontSize) >= 8)) violations.push(`${where} font-size ${c.fontSize}`);
        if (c.webkitTextFillColor !== c.color) violations.push(`${where} text-fill ${c.webkitTextFillColor} over color ${c.color}`);
        if (c.textIndent !== "0px") violations.push(`${where} text-indent ${c.textIndent}`);
      }
    }
    return {
      state: sec.getAttribute("data-soul-state"),
      text: sec.innerText,
      shell: shell ? shell.innerText : null,
      hygiene: { elements: all.length, violations },
      tiles: [...sec.querySelectorAll("[data-tile]")].map((e) => e.getAttribute("data-tile")),
      tile: tile
        ? {
            children: tile.children.length,
            lights: tile.querySelectorAll('[data-indicator="light"]').length,
            paintedGreenBesidesLight: [...tile.querySelectorAll("*")].filter((e) => e !== light && cs(e).backgroundColor === emerald).length,
            word: para ? para.innerText : null,
            wordColor: para ? cs(para).color : null,
            wordAtPoint: para ? atPoint(para) : null,
          }
        : null,
      light: light
        ? { bg: cs(light).backgroundColor, opacity: cs(light).opacity, visibility: cs(light).visibility, width: light.getBoundingClientRect().width, atPoint: atPoint(light) }
        : null,
      header: headerRow
        ? {
            children: headerRow.children.length,
            text: headerRow.innerText,
            value: headerValue ? headerValue.innerText : null,
            valueColor: headerValue ? cs(headerValue).color : null,
            valueOpacity: headerValue ? cs(headerValue).opacity : null,
            valueAtPoint: headerValue ? atPoint(headerValue) : null,
          }
        : null,
      note: note ? { text: note.innerText, color: cs(note).color, opacity: cs(note).opacity, visibility: cs(note).visibility, atPoint: atPoint(note) } : null,
    };
  });

  await context.close();
  console.log(`  ${label}: ${Date.now() - at} ms, soul ${request.status}, state ${seen ? seen.state : "no section"}${mockOn ? `, mocked ${mocked}` : ""}`);
  return { request, seen, unsettled, pageErrors, mocked };
}

let real;
let refused;
let on;
try {
  real = await readDock(TOKEN, "real token");
  refused = await readDock(REFUSED_TOKEN, "refused token");
  on = await readDock(TOKEN, "real token, /soul/status mocked on", { mockOn: true });
} finally {
  await browser.close();
}
console.log(`chromium: ${executablePath}`);

/* ------------------------------------------------------------------ */
/* Shared shape assertions                                             */
/* ------------------------------------------------------------------ */

function assertShape(ctx, label) {
  check(`${label}: the dock settled inside the timeout with no page error`, () => {
    assert.equal(ctx.unsettled, null, `the dock never settled: ${ctx.seen ? excerpt(ctx.seen.text) : "no section rendered"}`);
    assert.deepEqual(ctx.pageErrors, [], ctx.pageErrors.join(" | "));
    assert.ok(ctx.seen, "the dock's section is not on the page");
  });
  check(`${label}: the Soul tile is two rows with one light and nothing painted green beside it`, () => {
    const t = ctx.seen.tile;
    assert.ok(t, "no Soul tile in the dock");
    assert.equal(t.children, 2, `the Soul tile has ${t.children} children`);
    assert.equal(t.lights, 1, `the Soul tile has ${t.lights} lights`);
    assert.equal(t.paintedGreenBesidesLight, 0, "something besides the light is painted emerald inside the Soul tile");
    assert.equal(t.wordAtPoint, "self", `the tile word is covered by ${t.wordAtPoint}`);
    assert.equal(t.wordColor, GREY, `the tile word is not the pinned grey: ${t.wordColor}`);
  });
  check(`${label}: the light is a visible dot that nothing sits over`, () => {
    const l = ctx.seen.light;
    assert.ok(l, "no light in the Soul tile");
    assert.equal(l.atPoint, "self", `the light is covered by ${l.atPoint}`);
    assert.equal(l.opacity, "1", `the light's opacity is ${l.opacity}`);
    assert.equal(l.visibility, "visible", `the light's visibility is ${l.visibility}`);
    assert.ok(l.width >= 4, `the light is ${l.width}px wide`);
  });
  check(`${label}: the Soul recall header is two spans, the value in the pinned amber, uncovered`, () => {
    const h = ctx.seen.header;
    assert.ok(h, "no Soul recall header row");
    assert.equal(h.children, 2, `the header row has ${h.children} children`);
    assert.equal(h.valueColor, AMBER, `the header value is not the pinned amber: ${h.valueColor}`);
    assert.equal(h.valueOpacity, "1", `the header value's opacity is ${h.valueOpacity}`);
    assert.equal(h.valueAtPoint, "self", `the header value is covered by ${h.valueAtPoint}`);
  });
  check(`${label}: the note is visible, in the pinned copper, uncovered`, () => {
    const n = ctx.seen.note;
    assert.ok(n, "no note in the Soul recall panel");
    assert.equal(n.color, COPPER, `the note is not the pinned copper: ${n.color}`);
    assert.equal(n.opacity, "1", `the note's opacity is ${n.opacity}`);
    assert.equal(n.visibility, "visible", `the note's visibility is ${n.visibility}`);
    assert.equal(n.atPoint, "self", `the note is covered by ${n.atPoint}`);
  });
  check(`${label}: the section names no Vercel host and names the host it reads`, () => {
    assert.ok(!/vercel/i.test(ctx.seen.text), excerpt(ctx.seen.text));
    assert.ok(ctx.seen.text.includes(`Reads ${HOST}.`), excerpt(ctx.seen.text));
  });
  check(`${label}: nothing inside the section is dimmed, filtered, shadowed, painted by a gradient, moved, shrunk or given pseudo element text`, () => {
    const h = ctx.seen.hygiene;
    assert.ok(h && h.elements >= 40, `only ${h ? h.elements : 0} elements inside the section; the walk is broken`);
    assert.deepEqual(h.violations, [], h.violations.join(" | "));
  });
  check(`${label}: the tile grid is exactly the eight pinned labels in order`, () => {
    assert.deepEqual(ctx.seen.tiles, TILE_LABELS, `the tiles are ${JSON.stringify(ctx.seen.tiles)}`);
  });
}

function assertWords(ctx, label, { state, word, header, note, mesh, footerFailed, absent }) {
  check(`${label}: the browser sent GET /soul/status${state === "unread" ? " and was refused" : " with the bearer token"}`, () => {
    assert.equal(ctx.request.url, `${API_BASE}/soul/status`, `the soul read went to ${ctx.request.url}, not to this job's API`);
    if (state === "unread") {
      assert.equal(ctx.request.status, 401, `the refused token got ${ctx.request.status}`);
    } else {
      assert.equal(ctx.request.status, 200, `the real token got ${ctx.request.status}`);
      assert.equal(ctx.request.authorization, `Bearer ${TOKEN}`, "the soul read did not carry the bearer token");
    }
  });
  check(`${label}: the section, the tile, the header and the note all say ${JSON.stringify(state)}`, () => {
    assert.equal(ctx.seen.state, state, `data-soul-state is ${ctx.seen.state}`);
    assert.equal(ctx.seen.tile.word, word, `the tile word is ${JSON.stringify(ctx.seen.tile.word)}`);
    assert.equal(ctx.seen.header.text, `SOUL RECALL\n${header}`, `the header row reads ${JSON.stringify(ctx.seen.header.text)}`);
    assert.equal(ctx.seen.header.value, header, `the header value reads ${JSON.stringify(ctx.seen.header.value)}`);
    assert.equal(ctx.seen.note.text, note, `the note reads ${JSON.stringify(ctx.seen.note.text)}`);
  });
  check(`${label}: the light is ${state === "on" ? "emerald" : "grey"} and the mesh counts ${mesh}/7`, () => {
    assert.equal(ctx.seen.light.bg, state === "on" ? EMERALD : GREY, `the light is ${ctx.seen.light.bg}`);
    assert.equal(ctx.seen.shell, `MESH ${mesh}/7`, `the shell button reads ${JSON.stringify(ctx.seen.shell)}, not MESH ${mesh}/7`);
  });
  check(`${label}: the footer ${footerFailed ? "says a read failed" : "does not say a read failed"}, and the other states' words are absent`, () => {
    assert.equal(ctx.seen.text.includes(FAILED_FOOTER), footerFailed, excerpt(ctx.seen.text));
    for (const words of absent) {
      assert.ok(!ctx.seen.text.includes(words), `${JSON.stringify(words)} is on the panel in the ${state} state: ${excerpt(ctx.seen.text)}`);
    }
  });
}

assertShape(real, "real token");
assertWords(real, "real token", {
  state: "off",
  word: "recall off",
  header: "OFF",
  note: NOTE_OFF,
  mesh: EXPECTED_OFF,
  footerFailed: false,
  absent: ["status unread", "recall on", "has not answered yet", "gave no detail"],
});

assertShape(refused, "refused token");
assertWords(refused, "refused token", {
  state: "unread",
  word: "status unread",
  header: "UNREAD",
  note: NOTE_UNREAD,
  mesh: 0,
  footerFailed: true,
  absent: ["recall off", "recall on", OFF_DETAIL, "gave no detail"],
});

assertShape(on, "mocked on");
check("mocked on: the route mock answered the dock's soul read at least once", () => {
  assert.ok(on.mocked >= 1, `the mock answered ${on.mocked} times`);
});
assertWords(on, "mocked on", {
  state: "on",
  word: "recall on",
  header: "ON",
  note: NOTE_ON,
  mesh: EXPECTED_OFF + 1,
  footerFailed: false,
  absent: ["recall off", "status unread", "gave no detail", "Probed:"],
});

/* ------------------------------------------------------------------ */
/* An exact count, so a deleted check is a red run                     */
/* ------------------------------------------------------------------ */

const EXPECTED_CHECKS = 4 + 3 * (8 + 4) + 1;
assert.equal(checks, EXPECTED_CHECKS, `${checks} checks ran; this file makes exactly ${EXPECTED_CHECKS}. A check went missing rather than failing`);

const seconds = ((Date.now() - STARTED_AT) / 1000).toFixed(1);
console.log(`dock-smoke: ${checks} checks passed in real Chromium over three contexts in ${seconds}s`);
