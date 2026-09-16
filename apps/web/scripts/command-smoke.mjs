/**
 * Do the Command Center's six status cards tell the truth, in a browser?
 *
 * Run from apps/web against a stack that is already up, the same stack
 * scripts/panel-smoke.mjs and scripts/dock-smoke.mjs run against:
 *
 *   SMOKE_API_BASE=http://127.0.0.1:8000/api/v1 \
 *   SMOKE_WEB_ORIGIN=http://127.0.0.1:3000 \
 *   DEVON_REGISTRATION_KEY=... \
 *   node --experimental-strip-types scripts/command-smoke.mjs
 *
 * WHY THIS FILE EXISTS
 *
 * /command-center mounts five components. Until 2026-09-16 exactly one of them
 * had ever been driven from a browser: dock-smoke.mjs opens the route three
 * ways and asserts the CapabilityDock's Soul readout. panel-smoke.mjs covers
 * /control. So the six cards at the top of UnifiedCommandCenter.tsx, the first
 * thing a person reads when they open the cockpit, had no guard at all. Every
 * honesty check under apps/web/scripts reads source text or an AST, and `next
 * build` prerenders the route while `tsc` compiles it, so a card wired to the
 * wrong route, reading the wrong key, or hardwired to a green word would pass
 * every gate this estate has.
 *
 * That is the same gap panel-smoke.mjs and dock-smoke.mjs were each built to
 * close, one route at a time. This closes the third.
 *
 * WHAT IT ASSERTS, and why each one is here
 *
 *   - the words: each card's value and detail, scoped to the section's own
 *     aria-label, read from innerText;
 *   - the truth: the four live cards are graded against what the API answered
 *     to this run's own calls, not against a sentence pinned in this file. A
 *     card that says ONLINE while /health refused is a red run, and so is one
 *     that says LIVE while the provider reported simulated;
 *   - three contexts, because a card that can only ever be green proves
 *     nothing. Signed out, the Mind card must read SIGN IN and the page must
 *     send no /intelligence/status at all; with a token the API refuses, it
 *     must read OFFLINE with a red light. A hardwired green fails both;
 *   - the request: every read the section makes is captured off the wire, and
 *     the Authorization header is asserted on the one route that needs it;
 *   - the pixels: the light's and the value's computed colour, and
 *     document.elementFromPoint at the centre of each, which must resolve to
 *     those elements and nothing painted over them; and, on every element
 *     inside the section, opacity, visibility, filter, background-image,
 *     transform, clip-path, font size and ::before and ::after content. That
 *     list is not speculative. A critic working on the dock in this same route
 *     on 2026-09-15 painted four lies through Tailwind arbitrary variants and
 *     ::after content that innerText never sees;
 *   - the floor: an exact check count, so a deleted check is a red run.
 *
 * Change the words in the cards and this goes red, which is a decision and not
 * a drift. Same posture as its two siblings: Playwright and Chromium resolved
 * from the environment, both resolvers THROW when missing, so a runner without
 * a browser turns the job RED rather than green.
 *
 * IF IT TIMES OUT WAITING FOR THE CARDS TO SETTLE, suspect the server before
 * the page. `next start` serves the build it loaded at boot, so rebuilding
 * .next underneath a running one leaves it handing out HTML that references
 * chunk names only the new build carries: Chromium gets 400 on
 * /_next/static/chunks/app/command-center/page-*.js, React never hydrates, the
 * section never renders, and the only symptom here is this file's settle
 * timeout. Stop EVERY next process before rebuilding, not just the first pgrep
 * match, because `npx next start` is three of them and leaving one bound to
 * 3000 makes the replacement fail silently. Measured three times on
 * 2026-09-16 while building this file, each time read first as a bug in the
 * check. CI does not hit it: the job builds once and then starts the server.
 *
 * Running it on a web port other than 3000: the API's CORS_ORIGINS defaults to
 * port 3000 only (app/core/config.py), so the browser's reads die in preflight
 * and every live card falls to OFFLINE for a reason that has nothing to do with
 * this page. Set CORS_ORIGINS='["http://127.0.0.1:<port>"]' on the API first.
 */

import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { existsSync, readFileSync } from "node:fs";

const STARTED_AT = Date.now();

const API_BASE = (process.env.SMOKE_API_BASE || "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");
const WEB_ORIGIN = (process.env.SMOKE_WEB_ORIGIN || "http://127.0.0.1:3000").replace(/\/$/, "");
const REGISTRATION_KEY = process.env.DEVON_REGISTRATION_KEY || "";
const SETTLE_TIMEOUT_MS = Number(process.env.SMOKE_SETTLE_TIMEOUT_MS || 20000);

if (!REGISTRATION_KEY) {
  throw new Error(
    "DEVON_REGISTRATION_KEY is not set. Registration is closed by default " +
      "(app/api/v1/auth.py:_require_registration_key), so without it no account can be " +
      "made, the Mind card can only ever reach SIGN IN, and two of this file's three " +
      "contexts would prove nothing. Refusing to run.",
  );
}

/* ------------------------------------------------------------------ */
/* The section, the labels and the words, pinned here.                 */
/* UnifiedCommandCenter.tsx. A change on either side is a red run.     */
/* ------------------------------------------------------------------ */

/** The section's own anchor. Renaming it is a decision, so it fails loudly. */
const SECTION = 'section[aria-label="Estate status and configured organs"]';

/** The six cards, in the order UnifiedCommandCenter.tsx renders them. */
const CARD_LABELS = ["DEVON API", "MIND", "OPERATOR BRIDGE", "CHATGPT LAYER", "HEARTBEAT", "WRITE AUTHORITY"];

/** The two cards that are static by design, and say so in their own detail. */
const HEARTBEAT_VALUE = "6H SCHEDULE";
const HEARTBEAT_DETAIL = "Build 13 pulse configured. Live last-beat telemetry is not exposed here";
const WRITE_VALUE = "TEE";
const WRITE_DETAIL = "Writes stop at human ruling";
const MIND_LOCKED_DETAIL = "Session required for provider status";

// Tailwind's own values, as Chromium reports them from getComputedStyle.
const EMERALD_DOT = "rgb(52, 211, 153)";
const SKY_DOT = "rgb(125, 211, 252)";
const RED_DOT = "rgb(248, 113, 113)";
const EMERALD_TEXT = "rgb(167, 243, 208)";
const SKY_TEXT = "rgb(186, 230, 253)";
const RED_TEXT = "rgb(254, 202, 202)";

/* ------------------------------------------------------------------ */
/* Playwright and Chromium, resolved the way its two siblings do       */
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
  throw new Error(
    `playwright could not be imported. Set PLAYWRIGHT_MODULE to its index.mjs, or install it. ${failures.join(" | ")}`,
  );
}

function findChromium() {
  const found = CHROME_CANDIDATES.find((path) => path.startsWith("/") && existsSync(path));
  if (!found) {
    throw new Error("no Chromium binary found. Set CHROMIUM_BINARY. Tried: " + CHROME_CANDIDATES.join(", "));
  }
  return found;
}

/* ------------------------------------------------------------------ */
/* The storage slot, cut out of the component's own source             */
/* ------------------------------------------------------------------ */

function tokenSlotFromSource() {
  const centre = readFileSync(new URL("../components/command-center/UnifiedCommandCenter.tsx", import.meta.url), "utf8");
  const chat = readFileSync(new URL("../components/devon/DevonChat.tsx", import.meta.url), "utf8");
  // The component reads two slots and the exec mode one comes first in the
  // file, so take the token by name rather than by position.
  const keys = [...centre.matchAll(/localStorage\.getItem\("([^"]+)"\)/g)].map((match) => match[1]);
  const read = keys.find((key) => key.includes("token"));
  assert.ok(
    read,
    `UnifiedCommandCenter.tsx reads no localStorage key whose name contains "token", so this check cannot know which slot to write; found ${JSON.stringify(keys)}`,
  );
  const written = chat.match(/const TOKEN_KEY = "([^"]+)"/);
  assert.ok(written, "DevonChat.tsx no longer declares TOKEN_KEY as a string literal");
  assert.equal(
    read,
    written[1],
    "the status cards read a different token slot from the one DevonChat writes at sign-in, " +
      "so signing in would never light the Mind card",
  );
  return read;
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

/* ------------------------------------------------------------------ */
/* The stack, and a throwaway account                                  */
/* ------------------------------------------------------------------ */

await waitForHttp(`${API_BASE}/health`, "the API");
await waitForHttp(`${WEB_ORIGIN}/command-center`, "the web server");

const RUN = nonce();
const EMAIL = `command-smoke-${RUN}@example.com`;
const PASSWORD = `command-smoke-${nonce()}`;

const registered = await api("/auth/register", {
  method: "POST",
  body: { email: EMAIL, password: PASSWORD, full_name: `command smoke ${RUN}`, registration_key: REGISTRATION_KEY },
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
/* Preflight: what the API itself says. The cards are graded against   */
/* THIS, not against a sentence pinned above, so a red run names the   */
/* side that moved.                                                    */
/* ------------------------------------------------------------------ */

const healthRead = await api("/health");
check("GET /health answers, so ONLINE is the only honest word for the first card", () => {
  expectStatus(healthRead, 200, "GET /health");
});

const operatorRead = await api("/operator/status");
check("GET /operator/status answers and declares both flags the Operator card reads", () => {
  expectStatus(operatorRead, 200, "GET /operator/status");
  for (const key of ["enabled", "configured"]) {
    assert.equal(typeof operatorRead.json?.[key], "boolean", `/operator/status did not declare ${key} as a boolean`);
  }
});

const layerRead = await api("/devon/operating-layer/status");
check("GET /devon/operating-layer/status answers with the two fields the ChatGPT layer card gates on", () => {
  expectStatus(layerRead, 200, "GET /devon/operating-layer/status");
  assert.equal(typeof layerRead.json?.canonical_orchestrator, "string", "the operating layer named no canonical orchestrator");
  assert.equal(
    typeof layerRead.json?.second_orchestrator_created,
    "boolean",
    "the operating layer did not declare second_orchestrator_created as a boolean",
  );
  assert.ok(Array.isArray(layerRead.json?.surfaces), "the operating layer returned no surfaces array, so the card's count reads nothing");
});

const mindOpen = await api("/intelligence/status");
check("GET /intelligence/status refuses an anonymous caller, so the signed out context below is a real absence", () => {
  expectStatus(mindOpen, 401, "GET /intelligence/status with no token");
});

const mindRefused = await api("/intelligence/status", { token: REFUSED_TOKEN });
check("GET /intelligence/status refuses the token this run will feed the third context", () => {
  expectStatus(mindRefused, 401, "GET /intelligence/status with a refused token");
});

const mindRead = await api("/intelligence/status", { token: TOKEN });
check("GET /intelligence/status answers the real token and names a provider", () => {
  expectStatus(mindRead, 200, "GET /intelligence/status");
  assert.ok(
    typeof mindRead.json?.provider === "string" && mindRead.json.provider.length > 0,
    "the provider probe answered 200 without naming a provider, so the Mind card's detail has nothing true to say",
  );
});

/* What each live card must read, derived from the answers above rather than
 * assumed. The expressions mirror UnifiedCommandCenter.tsx deliberately: if the
 * component's rule changes, this file has to change with it, on purpose. */
const EXPECT_SIGNED_IN = {
  "DEVON API": { value: "ONLINE", dot: EMERALD_DOT, text: EMERALD_TEXT },
  MIND: {
    value: mindRead.json?.simulated ? "SIMULATED" : "LIVE",
    dot: EMERALD_DOT,
    text: EMERALD_TEXT,
  },
  "OPERATOR BRIDGE": {
    value: operatorRead.json.enabled && operatorRead.json.configured ? "READY" : "LOCKED",
    dot: operatorRead.json.enabled && operatorRead.json.configured ? EMERALD_DOT : SKY_DOT,
    text: operatorRead.json.enabled && operatorRead.json.configured ? EMERALD_TEXT : SKY_TEXT,
  },
  "CHATGPT LAYER": {
    value:
      layerRead.json.canonical_orchestrator === "DEVON" && layerRead.json.second_orchestrator_created === false
        ? "ROUTING READY"
        : "OFFLINE",
    dot: SKY_DOT,
    text: SKY_TEXT,
  },
};

/** The external surface count the ChatGPT layer card's detail must carry. */
const EXTERNAL_READY = layerRead.json.surfaces.filter(
  (surface) => surface?.surface !== "devon" && surface?.contract_ready,
).length;
const LAYER_DETAIL = `${EXTERNAL_READY} external surfaces contract ready. Live state stays unclaimed`;

/* ------------------------------------------------------------------ */
/* The browser                                                         */
/* ------------------------------------------------------------------ */

const TOKEN_SLOT = tokenSlotFromSource();
const { chromium } = await loadPlaywright();
const executablePath = findChromium();
const browser = await chromium.launch({ executablePath });

/**
 * Open /command-center once, optionally with a token in the slot the component
 * reads, and bring back what a person would see plus what the wire carried.
 */
async function readCards(token) {
  const context = await browser.newContext();
  const page = await context.newPage();

  const sent = [];
  const pageErrors = [];
  page.on("pageerror", (error) => pageErrors.push(String(error)));
  page.on("request", (request) => {
    if (request.url().startsWith(API_BASE)) {
      sent.push({
        path: request.url().slice(API_BASE.length),
        method: request.method(),
        auth: request.headers()["authorization"] || "",
      });
    }
  });

  await page.goto(`${WEB_ORIGIN}/command-center`, { waitUntil: "domcontentloaded" });
  if (token) {
    await page.evaluate(([slot, value]) => localStorage.setItem(slot, value), [TOKEN_SLOT, token]);
    sent.length = 0;
    await page.reload({ waitUntil: "domcontentloaded" });
  }

  // Settle on the section having left its "checking" state on every card,
  // rather than on a fixed sleep. CHECKING is what the cards render before the
  // first probe answers, so waiting for its absence is waiting for the reads.
  await page.waitForFunction(
    (selector) => {
      const section = document.querySelector(selector);
      if (!section) return false;
      const cards = Array.from(section.children);
      if (cards.length === 0) return false;
      return cards.every((card) => {
        const value = card.querySelectorAll("p")[1];
        return value && value.innerText.trim() !== "" && !/CHECKING/i.test(value.innerText);
      });
    },
    SECTION,
    { timeout: SETTLE_TIMEOUT_MS },
  );

  const cards = await page.$$eval(`${SECTION} > div`, (nodes) =>
    nodes.map((node) => {
      const paragraphs = Array.from(node.querySelectorAll("p"));
      const [labelEl, valueEl, detailEl] = paragraphs;
      const dotEl = node.querySelector("span.rounded-full");
      const box = (element) => {
        if (!element) return null;
        const rect = element.getBoundingClientRect();
        if (rect.width === 0 || rect.height === 0) return null;
        return document.elementFromPoint(rect.left + rect.width / 2, rect.top + rect.height / 2) === element;
      };
      return {
        label: labelEl ? labelEl.innerText.trim() : "",
        value: valueEl ? valueEl.innerText.trim() : "",
        detail: detailEl ? detailEl.innerText.trim() : "",
        valueColor: valueEl ? getComputedStyle(valueEl).color : "",
        dotColor: dotEl ? getComputedStyle(dotEl).backgroundColor : "",
        valueOnTop: box(valueEl),
        dotOnTop: box(dotEl),
        paragraphs: paragraphs.length,
      };
    }),
  );

  // Every element inside the section, and the ways a previous critic in this
  // same route made words lie without touching innerText.
  const painted = await page.$$eval(`${SECTION} *`, (nodes) =>
    nodes
      .map((node) => {
        const style = getComputedStyle(node);
        const before = getComputedStyle(node, "::before").content;
        const after = getComputedStyle(node, "::after").content;
        return {
          tag: node.tagName,
          text: (node.textContent || "").replace(/\s+/g, " ").slice(0, 40),
          opacity: Number(style.opacity),
          visibility: style.visibility,
          filter: style.filter,
          backgroundImage: style.backgroundImage,
          transform: style.transform,
          clipPath: style.clipPath,
          fontSize: Number.parseFloat(style.fontSize),
          fillColor: style.webkitTextFillColor,
          color: style.color,
          before: before === "none" || before === "normal" ? "" : before,
          after: after === "none" || after === "normal" ? "" : after,
        };
      })
      .filter(
        (entry) =>
          entry.opacity < 1 ||
          entry.visibility !== "visible" ||
          entry.filter !== "none" ||
          entry.backgroundImage !== "none" ||
          entry.transform !== "none" ||
          entry.clipPath !== "none" ||
          entry.fontSize < 8 ||
          (entry.fillColor && entry.fillColor !== entry.color) ||
          entry.before !== "" ||
          entry.after !== "",
      ),
  );

  await context.close();
  return { cards, painted, sent, pageErrors };
}

/* ------------------------------------------------------------------ */
/* What every context must satisfy                                     */
/* ------------------------------------------------------------------ */

function assertShape(read, where) {
  check(`${where}: the section settled inside the timeout with no page error`, () => {
    assert.deepEqual(read.pageErrors, [], `the page threw: ${read.pageErrors.join(" | ")}`);
  });

  check(`${where}: the section is exactly the six pinned cards, in order`, () => {
    assert.deepEqual(
      read.cards.map((card) => card.label),
      CARD_LABELS,
      "the status cards are no longer the six pinned labels in order; a seventh card, a rename or a " +
        "reorder is a decision, so it fails here rather than drifting",
    );
    for (const card of read.cards) {
      assert.equal(card.paragraphs, 3, `the ${card.label} card renders ${card.paragraphs} paragraphs, not label, value and detail`);
    }
  });

  check(`${where}: every value and every light is a visible element that nothing sits over`, () => {
    for (const card of read.cards) {
      assert.equal(card.valueOnTop, true, `the ${card.label} card's value is covered, zero sized or absent at its own centre`);
      assert.equal(card.dotOnTop, true, `the ${card.label} card's light is covered, zero sized or absent at its own centre`);
    }
  });

  check(`${where}: nothing inside the section is dimmed, filtered, painted by a gradient, moved, shrunk or given pseudo element text`, () => {
    assert.deepEqual(
      read.painted,
      [],
      "something inside the status section is painted in a way innerText cannot see: " + JSON.stringify(read.painted).slice(0, 700),
    );
  });

  check(`${where}: the two static cards read their own pinned words`, () => {
    const heartbeat = read.cards.find((card) => card.label === "HEARTBEAT");
    const write = read.cards.find((card) => card.label === "WRITE AUTHORITY");
    assert.equal(heartbeat.value, HEARTBEAT_VALUE);
    assert.equal(heartbeat.detail, HEARTBEAT_DETAIL, "the Heartbeat card stopped saying that its telemetry is not exposed here, which is the sentence that keeps it honest");
    assert.equal(write.value, WRITE_VALUE);
    assert.equal(write.detail, WRITE_DETAIL);
    assert.equal(heartbeat.dotColor, SKY_DOT, "the Heartbeat card's light is not the configured-but-unread blue");
    assert.equal(write.dotColor, SKY_DOT, "the Write authority card's light is not the configured-but-unread blue");
  });
}

/**
 * The three cards that answer the same way whatever token the browser carries,
 * because their routes take none.
 */
function assertUnauthenticatedCards(read, where) {
  check(`${where}: the three unauthenticated cards read what the API answered this run`, () => {
    for (const label of ["DEVON API", "OPERATOR BRIDGE", "CHATGPT LAYER"]) {
      const card = read.cards.find((entry) => entry.label === label);
      const expected = EXPECT_SIGNED_IN[label];
      assert.equal(card.value, expected.value, `the ${label} card says ${card.value} while the API answered ${expected.value}`);
      assert.equal(card.dotColor, expected.dot, `the ${label} card's light is ${card.dotColor}, not the colour its own state calls for`);
      assert.equal(card.valueColor, expected.text, `the ${label} card's word is ${card.valueColor}, not the colour its own state calls for`);
    }
    const operator = read.cards.find((entry) => entry.label === "OPERATOR BRIDGE");
    assert.equal(
      operator.detail,
      `Root ${operatorRead.json.root}`,
      "the Operator bridge card names a root the API did not report",
    );
    const layer = read.cards.find((entry) => entry.label === "CHATGPT LAYER");
    assert.equal(layer.detail, LAYER_DETAIL, "the ChatGPT layer card's external surface count disagrees with the payload it read");
  });
}

function assertMind(read, where, { value, dot, text, detail }) {
  check(`${where}: the Mind card reads ${value}`, () => {
    const card = read.cards.find((entry) => entry.label === "MIND");
    assert.equal(card.value, value);
    assert.equal(card.dotColor, dot, `the Mind card's light is ${card.dotColor}, not the colour ${value} calls for`);
    assert.equal(card.valueColor, text, `the Mind card's word is ${card.valueColor}, not the colour ${value} calls for`);
    assert.equal(card.detail, detail);
  });
}

function assertRequests(read, where, { mind }) {
  check(`${where}: the browser sent the section's reads, and the bearer only where the route needs one`, () => {
    for (const path of ["/health", "/operator/status", "/devon/operating-layer/status"]) {
      const hit = read.sent.find((entry) => entry.path === path);
      assert.ok(hit, `the page never sent GET ${path}, so whatever that card says, it did not read it`);
      assert.equal(hit.method, "GET");
    }
    const probes = read.sent.filter((entry) => entry.path === "/intelligence/status");
    if (mind === null) {
      assert.equal(
        probes.length,
        0,
        "the page probed the provider with no token in the slot; the Mind card would then read a refusal rather than SIGN IN",
      );
      return;
    }
    assert.ok(probes.length >= 1, "the page never sent GET /intelligence/status, so the Mind card did not read what it claims");
    assert.equal(probes[0].auth, `Bearer ${mind}`, "the provider probe carried the wrong Authorization header");
  });
}

/* ------------------------------------------------------------------ */
/* Three contexts                                                      */
/* ------------------------------------------------------------------ */

const signedOut = await readCards(null);
assertShape(signedOut, "signed out");
assertUnauthenticatedCards(signedOut, "signed out");
assertMind(signedOut, "signed out", { value: "SIGN IN", dot: SKY_DOT, text: SKY_TEXT, detail: MIND_LOCKED_DETAIL });
assertRequests(signedOut, "signed out", { mind: null });

const signedIn = await readCards(TOKEN);
assertShape(signedIn, "real token");
assertUnauthenticatedCards(signedIn, "real token");
assertMind(signedIn, "real token", {
  value: EXPECT_SIGNED_IN.MIND.value,
  dot: EMERALD_DOT,
  text: EMERALD_TEXT,
  detail: `${mindRead.json.provider}${mindRead.json.model ? ` · ${mindRead.json.model}` : ""}`,
});
assertRequests(signedIn, "real token", { mind: TOKEN });

const refused = await readCards(REFUSED_TOKEN);
assertShape(refused, "refused token");
assertUnauthenticatedCards(refused, "refused token");
assertMind(refused, "refused token", { value: "OFFLINE", dot: RED_DOT, text: RED_TEXT, detail: "Provider probe failed" });
assertRequests(refused, "refused token", { mind: REFUSED_TOKEN });

check("the Mind card reached three different states across the three contexts, so it is reading rather than reciting", () => {
  const words = [signedOut, signedIn, refused].map((read) => read.cards.find((card) => card.label === "MIND").value);
  assert.equal(new Set(words).size, 3, `the Mind card said ${JSON.stringify(words)}; a card that cannot change is not a status`);
});

await browser.close();

/* ------------------------------------------------------------------ */
/* An exact count, so a deleted check is a red run                     */
/* ------------------------------------------------------------------ */

const EXPECTED_CHECKS = 6 + 3 * (5 + 1 + 1 + 1) + 1;
assert.equal(checks, EXPECTED_CHECKS, `${checks} checks ran; this file makes exactly ${EXPECTED_CHECKS}. A check went missing rather than failing`);

const seconds = ((Date.now() - STARTED_AT) / 1000).toFixed(1);
console.log(`command-smoke: ${checks} checks passed in real Chromium over three contexts in ${seconds}s`);
