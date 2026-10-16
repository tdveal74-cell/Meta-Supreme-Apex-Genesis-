/**
 * The DEVON console, driven in real Chromium against a real API.
 *
 *   SMOKE_API_BASE=http://127.0.0.1:8000/api/v1 \
 *   DEVON_REGISTRATION_KEY=<the key the API was started with> \
 *   node --experimental-strip-types scripts/console-smoke.mjs
 *
 * WHY THIS EXISTS
 *
 * The console's main script did not run at all from 2026-09-10 to 2026-10-16.
 * Commit 747fcb6 left five lines of a patch note inside it as bare text, the
 * browser threw a SyntaxError at load, and remember, find, recall and approve
 * were dead on both hosts for five weeks while every console test stayed
 * green, because every one of them read the HTML as text. The 2026-10-16 sign
 * in work found it only by loading the page in Chromium.
 *
 * test_devon_console_scripts_parse.py now parses the scripts on every push.
 * This drives the page, so it also sees what parsing cannot: a throw at load,
 * a dead handler, the sign in doing something other than what its source
 * appears to say. It pins the credential contract by behaviour, not by text:
 * a critic beat the static contracts in test_devon_console_signin.py with
 * edits that kept every pinned string, and none of those edits survives this.
 *
 * WHAT IT ASSERTS
 *
 *   platform host, as app.main serves GET /console:
 *     loads with no page error, the sign in form shown, the tile NOT SIGNED IN
 *     a wrong password keeps nothing, says so and clears the field
 *     the right password keeps a JWT the API accepts, in sessionStorage only,
 *       and the tile then agrees with what this run's /soul/status said
 *     a refused retry after that leaves the kept sign in alone and says so
 *     the password is in no storage, cookie, console message, page text, URL
 *       or request body but this origin's POST /api/v1/auth/login
 *     a recall question reaches GET /soul/find with the bearer, and the page
 *       says what this run's API said about soul recall
 *     the kept JWT is never at rest in localStorage or a cookie
 *     a find answer that failed, came back empty, withheld records, mixed
 *       hits with a failure or a withheld count, or carried markup reads as
 *       exactly that, and markup is never injected
 *     an unsigned recall points at the sign in
 *     a tap on any example chip, signed out or in, and a held Enter on a
 *       focused chip, send nothing
 *     saved PLATFORM and soul bases pull no password, JWT or ruling key off
 *       this origin through sign in, find, propose or approve
 *     a redirect from the login route is refused rather than followed
 *   soul host, the same bytes with the soul role cookie:
 *     loads with no page error, and the sign in form is never shown, even
 *     with a CONSOLE_TOKEN kept and SAVE and TEST tapped
 *   no script at all:
 *     the sign in form is never shown
 *
 * Nothing here contacts a deployed surface. The account it registers lives
 * and dies with the job's Postgres container, as in panel-smoke.mjs.
 */

import assert from "node:assert/strict";
import { randomBytes } from "node:crypto";
import { existsSync } from "node:fs";

const API_BASE = (process.env.SMOKE_API_BASE || "http://127.0.0.1:8000/api/v1").replace(/\/$/, "");
const ORIGIN = new URL(API_BASE).origin;
const CONSOLE_URL = `${ORIGIN}/console`;
const REGISTRATION_KEY = process.env.DEVON_REGISTRATION_KEY || "";
const SETTLE_MS = Number(process.env.SMOKE_SETTLE_MS || 15000);

if (!REGISTRATION_KEY) {
  throw new Error(
    "DEVON_REGISTRATION_KEY is not set. Registration is closed by default, so no account " +
      "can be made and the sign in can only ever be refused. Refusing to run a smoke check " +
      "that would prove nothing.",
  );
}

/* ------------------------------------------------------------------ */
/* Playwright and Chromium, resolved the way dock-smoke.mjs does       */
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

const flat = (text) => String(text ?? "").replace(/\s+/g, " ").trim();

/* ------------------------------------------------------------------ */
/* The stack, and a throwaway account                                  */
/* ------------------------------------------------------------------ */

await waitForHttp(`${API_BASE}/health`, "the API");
await waitForHttp(CONSOLE_URL, "the console");

const RUN = nonce();
const EMAIL = `console-smoke-${RUN}@example.com`;
const PASSWORD = `console-pw-${nonce()}`;
const WRONG = `console-wrong-${nonce()}`;

const registered = await api("/auth/register", {
  method: "POST",
  body: { email: EMAIL, password: PASSWORD, full_name: `console smoke ${RUN}`, registration_key: REGISTRATION_KEY },
});
assert.equal(registered.status, 201, `POST /auth/register answered ${registered.status}: ${registered.text.slice(0, 300)}`);

const direct = await api("/auth/login", { method: "POST", body: { email: EMAIL, password: PASSWORD } });
assert.equal(direct.status, 200, `POST /auth/login answered ${direct.status}`);
const statusRead = await api("/soul/status", { token: direct.json.access_token });
assert.equal(statusRead.status, 200, `GET /soul/status answered ${statusRead.status}`);
const RECALL_ON = statusRead.json.enabled === true;
const EXPECTED_TILE = RECALL_ON ? "ON" : "REACHABLE, RECALL OFF";
console.log(`account: ${EMAIL}; this API reports soul recall ${RECALL_ON ? "on" : "off"}`);

/* ------------------------------------------------------------------ */
/* One instrumented browser context                                    */
/* ------------------------------------------------------------------ */

const { chromium } = await loadPlaywright();
const browser = await chromium.launch({ executablePath: findChromium() });

async function open({ role = null, javaScriptEnabled = true } = {}) {
  const context = await browser.newContext({
    viewport: { width: 390, height: 844 },
    isMobile: true,
    hasTouch: true,
    javaScriptEnabled,
  });
  const page = await context.newPage();
  const seen = { errors: [], logs: [], requests: [], navigations: [] };
  page.on("pageerror", (error) => seen.errors.push(String(error)));
  page.on("console", async (message) => {
    seen.logs.push(message.text());
    // text() prints a nested object as "Object"; read every argument's value.
    const values = await Promise.all(
      message.args().map((arg) => arg.jsonValue().then((value) => JSON.stringify(value)).catch(() => "")),
    );
    seen.logs.push(...values);
  });
  page.on("framenavigated", (frame) => seen.navigations.push(frame.url()));
  page.on("request", (request) =>
    seen.requests.push({
      method: request.method(),
      url: request.url(),
      body: request.postData() || "",
      auth: request.headers().authorization || "",
      headers: JSON.stringify(request.headers()),
    }),
  );
  if (role) {
    // The soul service serves these same bytes behind its own gate. Serve
    // them here with the soul role cookie and without app.main's platform
    // cookie, so the page renders exactly as it does on that host.
    const html = await (await fetch(CONSOLE_URL)).text();
    await context.addCookies([{ name: "devon_host", value: role, url: ORIGIN }]);
    await page.route(CONSOLE_URL, (route) => route.fulfill({ status: 200, contentType: "text/html", body: html }));
  }
  await page.goto(CONSOLE_URL);
  return { context, page, seen };
}

async function atRest(page, context) {
  const local = await page.evaluate(() => {
    const values = [];
    for (let index = 0; index < localStorage.length; index += 1) values.push(localStorage.getItem(localStorage.key(index)) || "");
    return values;
  });
  const cookies = (await context.cookies()).map((cookie) => cookie.value);
  return [...local, ...cookies];
}

async function settle(page, selector, predicate, what) {
  const deadline = Date.now() + SETTLE_MS;
  let last = "";
  while (Date.now() < deadline) {
    last = flat(await page.textContent(selector));
    if (predicate(last)) return last;
    await page.waitForTimeout(150);
  }
  throw new Error(`${what}: ${selector} still read "${last}" after ${SETTLE_MS}ms`);
}

async function signIn(page, password) {
  await page.fill("#signEmail", EMAIL);
  await page.fill("#signPass", password);
  // Wait for this attempt's own answer: the note still holds the last one.
  await Promise.all([
    page.waitForResponse((response) => response.url() === `${ORIGIN}/api/v1/auth/login`, { timeout: SETTLE_MS }),
    page.click("#signGo"),
  ]);
  await page.waitForFunction(() => !document.querySelector("#signGo").disabled, null, { timeout: SETTLE_MS });
  return settle(page, "#signNote", (text) => text.length > 0, "the sign in never answered");
}

async function ask(page, question) {
  const before = flat(await page.innerText("#plan"));
  await page.fill("#cmd", question);
  await page.press("#cmd", "Enter");
  return settle(page, "#plan", (text) => text !== before && !/PROPOSING|^$/.test(text) && /FIND|SOUL|LEDGER/.test(text), `the answer to "${question}"`);
}

/* ------------------------------------------------------------------ */
/* Platform host                                                       */
/* ------------------------------------------------------------------ */

const platform = await open();
const { page, seen } = platform;

const loadTile = await settle(page, "#soulState", (text) => text !== "NOT CONFIGURED" && text !== "CHECKING", "the Soul tile never left its initial text");
check("the platform console loads with no page error, so its script ran at all", () => {
  assert.deepEqual(seen.errors, [], `page errors: ${seen.errors.join(" | ")}`);
});
const formShown = await page.isVisible("#signForm");
const tokenRowShown = await page.isVisible("#soulTokRow");
check("an unsigned platform console reads NOT SIGNED IN, shows the sign in form and hides the CONSOLE_TOKEN row", () => {
  assert.equal(loadTile, "NOT SIGNED IN");
  assert.equal(formShown, true, "the sign in form is not visible on the platform console");
  assert.equal(tokenRowShown, false, "the CONSOLE_TOKEN row is visible on the platform console");
});

const requestsBeforeChips = seen.requests.length;
const chipCount = await page.locator("#chips button").count();
for (let index = 0; index < chipCount; index += 1) {
  await page.locator("#chips button").nth(index).click();
}
await page.waitForTimeout(800);
const chipFilled = await page.inputValue("#cmd");
check("a tap on every example chip fills the command line and sends nothing", () => {
  assert.ok(chipCount >= 3, `only ${chipCount} chips found`);
  const sent = seen.requests.slice(requestsBeforeChips).filter((r) => r.url.startsWith(ORIGIN + "/api/"));
  assert.deepEqual(sent.map((r) => r.method + " " + r.url), [], "a chip tap reached the API");
  assert.ok(chipFilled.length > 0, "the chip did not fill the command line");
});
await page.fill("#cmd", "");

const unsigned = await ask(page, `what did we decide about ${RUN}`);
check("an unsigned recall points at the sign in rather than echoing Not authenticated", () => {
  assert.match(unsigned, /Not signed in\. Sign in with your email and password in the Soul Layer panel/);
});

const wrongNote = await signIn(page, WRONG);
const wrongField = await page.inputValue("#signPass");
const wrongKept = await page.evaluate(() => sessionStorage.getItem("devon.platform.jwt"));
const wrongTile = await settle(page, "#soulState", (t) => t !== "SIGNING IN", "tile after refusal");
check("a wrong password says so, keeps nothing, clears the field and leaves the tile NOT SIGNED IN", () => {
  assert.equal(wrongNote, "Wrong email or password. Nothing was kept.");
  assert.equal(wrongField, "", "the password field kept the wrong password");
  assert.equal(wrongKept, null, "a refused sign in kept a token");
  assert.equal(wrongTile, "NOT SIGNED IN");
});

const rightNote = await signIn(page, PASSWORD);
const signedTile = await settle(page, "#soulState", (t) => t !== "SIGNING IN" && t !== "CHECKING", "tile after sign in");
const kept = await page.evaluate(() => sessionStorage.getItem("devon.platform.jwt") || "");
const keptStatus = await api("/soul/status", { token: kept });
const rightField = await page.inputValue("#signPass");
const restAfterSignIn = await atRest(page, platform.context);
check("the kept JWT is in no localStorage value and no cookie, so closing the tab signs out", () => {
  assert.ok(kept.length > 20, "no token was kept to look for");
  assert.ok(!restAfterSignIn.some((value) => value.includes(kept)), "the JWT is at rest in localStorage or a cookie");
});
check("the right password keeps a JWT the API accepts, clears the field, and the tile agrees with this run's API", () => {
  assert.match(rightNote, /^Signed in for this tab\./);
  assert.equal(keptStatus.status, 200, "the kept token was refused by GET /soul/status");
  assert.equal(rightField, "", "the password field kept the right password");
  assert.equal(signedTile, EXPECTED_TILE);
});

await signIn(page, WRONG);
const retryTile = await settle(page, "#soulState", (t) => t !== "SIGNING IN" && t !== "CHECKING", "tile after retry");
const retryNote = await settle(page, "#signNote", (t) => /tab (still works|has run out|could not)/.test(t) || /I could not check/.test(t), "the note after a refused retry");
const retryKept = await page.evaluate(() => sessionStorage.getItem("devon.platform.jwt"));
check("a refused retry leaves the kept sign in alone and says it is still kept", () => {
  assert.equal(retryNote, "Wrong email or password. Nothing was kept. The token already in this tab still works.");
  assert.equal(retryTile, EXPECTED_TILE);
  assert.equal(retryKept, kept, "a refused retry changed the kept token");
});

const requestsBeforeSignedChips = seen.requests.length;
for (let index = 0; index < chipCount; index += 1) {
  await page.locator("#chips button").nth(index).tap();
}
const lastChip = await page.inputValue("#cmd");
await page.locator("#chips button").first().focus();
await page.keyboard.down("Enter");
await page.keyboard.down("Enter");
await page.keyboard.down("Enter");
await page.keyboard.up("Enter");
await page.waitForTimeout(800);
check("signed in, a tap on every chip and a held Enter on a focused chip still send nothing", () => {
  const sent = seen.requests.slice(requestsBeforeSignedChips).filter((r) => r.url.startsWith(ORIGIN + "/api/"));
  assert.deepEqual(sent.map((r) => r.method + " " + r.url), [], "a chip reached the API while signed in");
  assert.ok(lastChip.length > 0, "the last chip did not fill the command line");
});
await page.fill("#cmd", "");

const realAnswer = await ask(page, `what did we decide about ${RUN}`);
check("a recall question reaches GET /soul/find with the bearer and says what this API said about soul recall", () => {
  const finds = seen.requests.filter((r) => r.url.startsWith(`${ORIGIN}/api/v1/soul/find`));
  assert.ok(finds.some((r) => r.auth === `Bearer ${kept}`), "no /soul/find request carried the kept bearer");
  if (RECALL_ON) {
    assert.match(realAnswer, /SOUL (SEARCHED|PARTIAL|WINDOW)|\(soul\)/);
  } else {
    assert.match(realAnswer, /SOUL OFF Soul recall is switched off on the API, so only the ledger was searched\./);
  }
});

const FIXTURES = {
  partial: {
    body: { query: "x", ledger: [], soul: [], soul_errors: ["tee-soul-layer: PineconeApiException 403 Forbidden"], soul_withheld: 0, soul_recall_enabled: true },
    expect: /SOUL PARTIAL The soul search did not finish: tee-soul-layer: PineconeApiException 403 Forbidden/,
    refuse: /measured empty/,
  },
  empty: {
    body: { query: "x", ledger: [], soul: [], soul_errors: [], soul_withheld: 0, soul_recall_enabled: true },
    expect: /SOUL SEARCHED Nothing recalled from the soul\. A measured empty, not a guess\./,
    refuse: /SOUL PARTIAL|SOUL OFF/,
  },
  withheld: {
    body: { query: "x", ledger: [], soul: [], soul_errors: [], soul_withheld: 3, soul_recall_enabled: true },
    expect: /SOUL WINDOW 3 soul record\(s\) withheld as no longer active\. They used slots in the search, so an active record may not have been fetched\./,
    refuse: /measured empty/,
  },
  hitsAndErrors: {
    body: { query: "x", ledger: [], soul: [{ source: "devon-soul", text: "A note that did come back." }], soul_errors: ["tee-soul-layer: timed out"], soul_withheld: 0, soul_recall_enabled: true },
    expect: /DEVON NOTED \(soul\) A note that did come back\..*SOUL PARTIAL The soul search did not finish: tee-soul-layer: timed out/,
    refuse: /measured empty/,
  },
  hitsAndWithheld: {
    body: { query: "x", ledger: [], soul: [{ source: "tee-soul-layer", text: "A ruling that did come back." }], soul_errors: [], soul_withheld: 2, soul_recall_enabled: true },
    expect: /TEE RULED \(soul\) A ruling that did come back\..*SOUL WINDOW 2 soul record\(s\) withheld/,
    refuse: /measured empty/,
  },
  markup: {
    body: {
      query: "x",
      ledger: [],
      soul: [{ source: "tee-soul-layer", text: `Render stays local.<img src=x onerror="window.__owned=1"><script>window.__owned=1</script>` }],
      soul_errors: [],
      soul_withheld: 0,
      soul_recall_enabled: true,
    },
    expect: /TEE RULED \(soul\) Render stays local\.<img src=x onerror="window\.__owned=1"><script>window\.__owned=1<\/script>/,
    refuse: /measured empty/,
  },
};
for (const [label, fixture] of Object.entries(FIXTURES)) {
  await page.route(`${ORIGIN}/api/v1/soul/find**`, (route) =>
    route.fulfill({ status: 200, contentType: "application/json", body: JSON.stringify(fixture.body) }),
  );
  const answer = await ask(page, `what did we decide about ${label} ${RUN}`);
  await page.unroute(`${ORIGIN}/api/v1/soul/find**`);
  check(`a ${label} find answer reads as exactly that`, () => {
    assert.match(answer, fixture.expect);
    assert.doesNotMatch(answer, fixture.refuse);
  });
}
const ownedRan = await page.evaluate(() => window.__owned === 1);
const ownedElements = await page.evaluate(() => !!document.querySelector("#plan script, #plan img"));
check("markup in a recalled record is shown as text and never injected", () => {
  assert.equal(ownedRan, false, "recalled markup ran in the page");
  assert.equal(ownedElements, false, "recalled markup became elements");
});

// The credential contract, by behaviour.
const storage = await page.evaluate(() => {
  const values = [];
  for (const store of [localStorage, sessionStorage]) {
    for (let index = 0; index < store.length; index += 1) values.push(store.getItem(store.key(index)) || "");
  }
  return values;
});
const cookies = await platform.context.cookies();
const pageText = (await page.evaluate(() => document.body.innerText)) + (await page.evaluate(() =>
  [...document.querySelectorAll("input,textarea")].map((element) => element.value).join(" "),
));
check("the password is in no storage, cookie, console message, page text or navigation", () => {
  for (const secret of [PASSWORD, WRONG]) {
    assert.ok(!storage.some((value) => value.includes(secret)), "the password is in web storage");
    assert.ok(!cookies.some((cookie) => cookie.value.includes(secret)), "the password is in a cookie");
    assert.ok(!seen.logs.some((line) => line.includes(secret)), "the password reached the browser console");
    assert.ok(!pageText.includes(secret), "the password is on the page");
    assert.ok(!seen.navigations.some((url) => url.includes(secret)), "the password reached a navigation URL");
  }
});
check("the password left the page only in this origin's POST /api/v1/auth/login, never in a URL", () => {
  for (const secret of [PASSWORD, WRONG]) {
    const carrying = seen.requests.filter((r) => r.body.includes(secret) || r.url.includes(secret) || r.url.includes(encodeURIComponent(secret)));
    assert.ok(carrying.length > 0, "no request carried the password, so the sign in never ran");
    for (const request of carrying) {
      assert.equal(request.method, "POST", `${request.method} ${request.url} carried the password`);
      assert.equal(request.url, `${ORIGIN}/api/v1/auth/login`, `${request.url} carried the password`);
    }
  }
});
const restAtEnd = await atRest(page, platform.context);
check("the kept JWT is still at rest nowhere at the end of the platform pass", () => {
  assert.ok(!restAtEnd.some((value) => value.includes(kept)), "the JWT is at rest in localStorage or a cookie");
});
check("the platform console threw no page error across everything above", () => {
  assert.deepEqual(seen.errors, [], `page errors: ${seen.errors.join(" | ")}`);
});
await platform.context.close();

// Bases saved in localStorage, the PLATFORM field's and the soul host's, must
// not pull the password, the JWT or the ruling key off this origin.
const RULING_KEY = `ruling-${nonce()}`;
const based = await open();
await based.page.evaluate(() => {
  localStorage.setItem("devon.soul.platform", "http://127.0.0.1:9");
  localStorage.setItem("devon.soul.base", "http://127.0.0.1:9");
});
await based.page.reload();
await based.page.evaluate((key) => sessionStorage.setItem("devon.ruling.key", key), RULING_KEY);
await signIn(based.page, PASSWORD);
const basedJwt = await based.page.evaluate(() => sessionStorage.getItem("devon.platform.jwt") || "");
await settle(based.page, "#soulState", (t) => t !== "SIGNING IN" && t !== "CHECKING", "tile with saved bases");
await ask(based.page, `what did we decide about saved bases ${RUN}`);
await based.page.fill("#cmd", `Devon, remember the saved base probe ${RUN}`);
await based.page.press("#cmd", "Enter");
await based.page.waitForTimeout(1500);
const approve = based.page.locator(".abtn.yes").first();
if (await approve.count()) await approve.click();
await based.page.waitForTimeout(1200);
const platformRowShown = await based.page.isVisible("#loopBaseRow");
check("saved bases pull no password, JWT or ruling key off this origin, and the PLATFORM row is not offered", () => {
  const off = based.seen.requests.filter((r) => !r.url.startsWith(ORIGIN + "/") && !r.url.startsWith("data:"));
  const leaked = off.filter(
    (r) => r.body.includes(PASSWORD) || r.auth.includes(basedJwt) || JSON.stringify(r).includes(RULING_KEY),
  );
  assert.ok(basedJwt.length > 20, "the sign in with saved bases kept no token");
  assert.deepEqual(leaked.map((r) => r.method + " " + r.url), []);
  assert.deepEqual(off.filter((r) => r.url.startsWith("http://127.0.0.1:9")).map((r) => r.url), [], "a request went to the saved base");
  assert.equal(platformRowShown, false, "the PLATFORM row is offered on the platform console");
  // Not vacuous: the probe did reach find, propose and approve on this origin,
  // and approve carried the ruling key there.
  const here = (path) => based.seen.requests.filter((r) => r.url.startsWith(`${ORIGIN}/api/v1/soul/${path}`));
  assert.ok(here("find").length > 0, "the probe never reached /soul/find");
  assert.ok(here("propose").length > 0, "the probe never reached /soul/propose");
  assert.ok(here("approve").some((r) => r.headers.includes(RULING_KEY)), "approve never carried the ruling key on this origin");
});
await based.context.close();

// A login that answers with a redirect must not carry the password onward.
const redirected = await open();
await redirected.page.route(`${ORIGIN}/api/v1/auth/login`, (route) =>
  route.fulfill({ status: 307, headers: { location: `${ORIGIN}/__followed_login` }, body: "" }),
);
// fetch refuses the redirect before any response event fires, so this waits
// on the note, which starts empty in a fresh context.
await redirected.page.fill("#signEmail", EMAIL);
await redirected.page.fill("#signPass", PASSWORD);
await redirected.page.click("#signGo");
const redirectNote = await settle(redirected.page, "#signNote", (text) => text.length > 0, "the redirected sign in never answered");
const redirectKept = await redirected.page.evaluate(() => sessionStorage.getItem("devon.platform.jwt"));
check("a redirect from the login route is refused, not followed, and nothing is kept", () => {
  const followed = redirected.seen.requests.filter((r) => r.url.includes("__followed_login"));
  assert.deepEqual(followed.map((r) => r.method + " " + r.url), [], "the redirect was followed");
  assert.equal(redirectNote, "I could not reach the API from here. Nothing was kept.");
  assert.equal(redirectKept, null, "a redirected sign in kept a token");
});
await redirected.context.close();

/* ------------------------------------------------------------------ */
/* Soul host, and no script at all                                     */
/* ------------------------------------------------------------------ */

const soul = await open({ role: "soul" });
await soul.page.waitForTimeout(1000);
await soul.page.evaluate(() => sessionStorage.setItem("devon.soul.token", "dst_" + "0".repeat(32)));
await soul.page.reload();
await soul.page.waitForTimeout(800);
await soul.page.click("#soulSave");
await soul.page.click("#soulTest");
await soul.page.waitForTimeout(1200);
const soulFormShown = await soul.page.isVisible("#signForm");
const soulTokenRowShown = await soul.page.isVisible("#soulTokRow");
check("on the soul host, with a CONSOLE_TOKEN kept and SAVE and TEST tapped, no page error and the sign in form is never shown", () => {
  assert.deepEqual(soul.seen.errors, [], `soul host page errors: ${soul.seen.errors.join(" | ")}`);
  assert.equal(soulFormShown, false, "the sign in form is visible on the soul host");
  assert.equal(soulTokenRowShown, true, "the CONSOLE_TOKEN row is not visible on the soul host");
});
await soul.context.close();

const scriptless = await open({ javaScriptEnabled: false });
const scriptlessFormShown = await scriptless.page.isVisible("#signForm");
check("with no script running, the sign in form is never shown", () => {
  assert.equal(scriptlessFormShown, false, "the sign in form is visible with scripting off");
});
await scriptless.context.close();

await browser.close();
console.log(`console-smoke: ${checks} checks passed`);
