// check.mjs: rendered checks for the tqohq.online static site.
//
// Usage:
//   NODE_PATH=$(npm root -g) node check.mjs [dir]
//
// dir defaults to the folder this script lives in, so a critic can point it at a copy.
// It needs the globally installed playwright package and a Chromium build under
// /opt/pw-browsers. Both are required: if either is missing the script throws, so a
// machine without a browser goes red rather than green.
//
// Every HTML file in dir is loaded over file:// and checked. The run FAILS (exit 1) on:
//   em or en dashes (U+2012 to U+2015) in visible text, attributes or source
//   a banned house word
//   horizontal overflow at 320px or 390px
//   any request to a non-file URL
//   zero or several h1 elements
//   a form control with no label, or a link or button with no name
//   an image with no alt text
//   a font file that fails to load
//   a console error or uncaught page error
//   a relative link or #fragment that points nowhere
//   a signup form that claims success it did not receive, or breaks with JS off
//   an exclamation mark, a curly quote or an ellipsis in visible text
//   a missing Content-Security-Policy, or one whose script hash or connect-src is stale
//   a form status region or field error that is not in the page from load
//   a form answer drawn off screen at 393x659, the iPhone Safari visible area
//   any wrong answer from the form against a local stand-in for the list provider,
//     served from a second origin: CORS allowed, no CORS, 503, a 200 whose body
//     reports an error, a redirect, and no answer before the timeout
// It WARNS (exit 0) with "DEPLOY BLOCKER: SIGNUP_ENDPOINT is empty" while it is empty,
// and while any passage is marked data-unconfirmed. Once SIGNUP_ENDPOINT is set, a
// data-unconfirmed passage FAILS the run: those wait on a ruling from Tee.
//
// Screenshots at 390x844 and 1280x800, light and dark, go to TQO_SHOTS_DIR when set,
// otherwise to the session scratchpad path below.

import { createRequire } from "node:module";
import { readdirSync, existsSync, statSync, readFileSync, mkdirSync } from "node:fs";
import { join, dirname, resolve, basename, extname } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createHash } from "node:crypto";
import http from "node:http";

const require = createRequire(import.meta.url);

const HERE = dirname(fileURLToPath(import.meta.url));
const DIR = resolve(process.argv[2] || HERE);
const SHOTS = process.env.TQO_SHOTS_DIR ||
  "/tmp/claude-0/-home-user-Meta-Supreme-Apex-Genesis-/331556fb-8043-5725-a414-72bc8745c2d9/scratchpad/shots";

function loadPlaywright() {
  try {
    return require("playwright");
  } catch (err) {
    throw new Error(
      "The playwright package could not be loaded. Run as NODE_PATH=$(npm root -g) node check.mjs, " +
      "with playwright installed globally. Underlying error: " + err.message
    );
  }
}

function findChromium() {
  const root = "/opt/pw-browsers";
  if (!existsSync(root)) throw new Error("No " + root + " directory, so there is no Chromium to render with.");
  const dirs = readdirSync(root).filter((d) => /^chromium-\d+$/.test(d)).sort().reverse();
  for (const d of dirs) {
    for (const sub of ["chrome-linux", "chrome-linux64"]) {
      const candidate = join(root, d, sub, "chrome");
      if (existsSync(candidate)) {
        const st = statSync(candidate);
        if (st.isFile() && (st.mode & 0o111)) return candidate;
      }
    }
  }
  throw new Error("No chrome executable found under " + root + "/chromium-*/chrome-linux/chrome.");
}

// The house word list. Inflections count; "landscape" is flagged in any sense because a
// script cannot tell figurative from literal.
const BANNED = new RegExp(
  "\\b(" + [
    "delv(?:e|es|ed|ing)", "tapestr(?:y|ies)", "testaments?", "pivotal", "vibrant(?:ly)?",
    "robust(?:ly|ness)?", "seamless(?:ly)?", "intricate(?:ly)?", "intricac(?:y|ies)",
    "meticulous(?:ly)?", "landscapes?", "interplay", "showcas(?:e|es|ed|ing)",
    "underscor(?:e|es|ed|ing)", "highlight(?:s|ed|ing)?", "foster(?:s|ed|ing)?",
    "enhanc(?:e|es|ed|ing|ement|ements)", "bolster(?:s|ed|ing)?", "leverag(?:e|es|ed|ing)",
    "boast(?:s|ed|ing)?", "nestled", "align(?:s|ed|ing)?\\s+with",
  ].join("|") + ")\\b",
  "gi"
);
const BANNED_OPENER = /(?:^|[.?!]\s+)(Additionally|Moreover|Notably)\b/g;
const DASH = /[\u2012-\u2015]/;
// House punctuation: no exclamation marks, straight quotes only, no ellipses.
const PUNCT = /!|\u2026|\.\.\.|[\u2018\u2019\u201c\u201d]/g;
const SUCCESS = /received|success|thank|subscribed|you're in|you are in|welcome|accepted/i;
const ENDPOINT_RE = /\bconst\s+SIGNUP_ENDPOINT\s*=\s*(["'])(.*?)\1/;

function sha256(text) { return "'sha256-" + createHash("sha256").update(text).digest("base64") + "'"; }
function inlineScripts(src) { return [...src.matchAll(/<script>([\s\S]*?)<\/script>/g)].map((m) => m[1]); }
function cspOf(src) {
  const m = /<meta\s+http-equiv="Content-Security-Policy"\s+content="([^"]+)"/i.exec(src);
  if (!m) return null;
  return Object.fromEntries(m[1].split(";").map((d) => d.trim()).filter(Boolean).map((d) => {
    const [name, ...values] = d.split(/\s+/);
    return [name, values];
  }));
}

const results = [];
function record(name, status, detail) { results.push({ name, status, detail }); }

function lineOf(source, index) { return source.slice(0, index).split("\n").length; }

// Static read of each file, before any browser work.
const htmlFiles = readdirSync(DIR).filter((f) => f.toLowerCase().endsWith(".html")).sort();
if (htmlFiles.length === 0) throw new Error("No .html files in " + DIR);
const sources = Object.fromEntries(htmlFiles.map((f) => [f, readFileSync(join(DIR, f), "utf8")]));

// Collected text per page, filled in by the browser pass.
const collected = {};

const { chromium } = loadPlaywright();
const executablePath = findChromium();
mkdirSync(SHOTS, { recursive: true });
const browser = await chromium.launch({ executablePath });

const foreignRequests = [];
const consoleProblems = [];

// ignore: a URL prefix that the form test intercepts itself, so it never leaves the machine.
function watch(page, file, ignore = "") {
  page.on("request", (r) => {
    const url = r.url();
    if (ignore && url.startsWith(ignore)) return;
    if (!url.startsWith("file:") && !url.startsWith("data:") && !url.startsWith("about:")) {
      foreignRequests.push(file + ": " + url);
    }
  });
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    if (ignore && (m.location().url || "").startsWith(ignore)) return;
    consoleProblems.push(file + ": console error: " + m.text());
  });
  page.on("pageerror", (e) => consoleProblems.push(file + ": uncaught: " + e.message));
}

async function open(context, file, ignore = "") {
  const page = await context.newPage();
  watch(page, file, ignore);
  await page.goto(pathToFileURL(join(DIR, file)).href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  return page;
}

const perPage = {};
for (const file of htmlFiles) perPage[file] = { overflow: [], fonts: [], h1: null, labels: [], alts: [], links: [], form: [], regions: [], harness: [] };

for (const file of htmlFiles) {
  const info = perPage[file];

  // 1. Text, attributes and structure, read once at 390 in light.
  {
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: "light" });
    const page = await open(context, file);
    const snapshot = await page.evaluate(() => {
      const CONTENT_ATTRS = ["content", "alt", "title", "aria-label", "aria-description", "placeholder", "value", "label"];
      const texts = [];
      const walker = document.createTreeWalker(document.documentElement, NodeFilter.SHOW_TEXT);
      for (let n = walker.nextNode(); n; n = walker.nextNode()) {
        const parent = n.parentElement ? n.parentElement.tagName : "";
        if (parent === "SCRIPT" || parent === "STYLE") continue;
        if (n.nodeValue.trim()) texts.push(n.nodeValue);
      }
      const attrs = [];
      const allAttrs = [];
      for (const el of document.querySelectorAll("*")) {
        for (const a of el.attributes) {
          allAttrs.push(el.tagName.toLowerCase() + "[" + a.name + "]=" + a.value);
          if (CONTENT_ATTRS.includes(a.name)) attrs.push(a.value);
        }
      }
      const scripts = [...document.querySelectorAll("script:not([src])")].map((s) => s.textContent);

      const h1 = document.querySelectorAll("h1").length;

      const unlabeled = [];
      for (const el of document.querySelectorAll("input, select, textarea")) {
        const type = (el.getAttribute("type") || "").toLowerCase();
        if (["hidden", "submit", "button", "reset", "image"].includes(type)) continue;
        const byLabel = el.labels && [...el.labels].some((l) => l.textContent.trim());
        const byAria = (el.getAttribute("aria-label") || "").trim();
        const byRef = (el.getAttribute("aria-labelledby") || "").split(/\s+/).filter(Boolean)
          .some((id) => { const t = document.getElementById(id); return t && t.textContent.trim(); });
        if (!byLabel && !byAria && !byRef) unlabeled.push(el.tagName.toLowerCase() + "#" + (el.id || "?"));
      }
      for (const el of document.querySelectorAll("a[href], button")) {
        const name = (el.textContent || "").trim() || (el.getAttribute("aria-label") || "").trim();
        if (!name) unlabeled.push(el.tagName.toLowerCase() + " with no name");
      }

      const noAlt = [];
      for (const img of document.querySelectorAll("img, input[type=image]")) {
        if (!img.hasAttribute("alt")) noAlt.push(img.outerHTML.slice(0, 80));
      }
      for (const svg of document.querySelectorAll('svg[role="img"]')) {
        if (!svg.getAttribute("aria-label") && !svg.getAttribute("aria-labelledby") && !svg.querySelector("title")) {
          noAlt.push("svg role=img with no name");
        }
      }

      const hrefs = [...document.querySelectorAll("a[href]")].map((a) => a.getAttribute("href"));
      const ids = [...document.querySelectorAll("[id]")].map((e) => e.id);
      const unconfirmed = [...document.querySelectorAll("[data-unconfirmed]")]
        .map((e) => e.textContent.replace(/\s+/g, " ").trim().slice(0, 64));
      // Live regions must exist before their first message, or it may never be heard.
      const regions = [];
      for (const form of document.querySelectorAll("form")) {
        const live = form.querySelector('[role="status"], [aria-live]');
        if (!live) regions.push("the form has no status region");
        else if (getComputedStyle(live).display === "none") regions.push("the status region is display:none on load");
        for (const input of form.querySelectorAll("input[aria-describedby]")) {
          for (const id of input.getAttribute("aria-describedby").split(/\s+/)) {
            const el = document.getElementById(id);
            if (!el) continue;
            if (el.getAttribute("role") !== "alert" && !el.hasAttribute("aria-live")) regions.push("#" + id + " is not a live region");
            if (el.hidden || getComputedStyle(el).display === "none") regions.push("#" + id + " is not rendered on load");
          }
        }
      }
      return { texts, attrs, allAttrs, scripts, h1, unlabeled, noAlt, hrefs, ids, unconfirmed, regions };
    });
    collected[file] = snapshot;
    info.regions = snapshot.regions;
    // The accessibility tree itself, read over CDP: a status role must be there on load.
    if (/<form\b/i.test(sources[file])) {
      const cdp = await context.newCDPSession(page);
      const { nodes } = await cdp.send("Accessibility.getFullAXTree");
      const status = nodes.filter((n) => n.role && n.role.value === "status" && !n.ignored);
      if (!status.length) info.regions.push("no status node in the accessibility tree on load");
    }
    info.h1 = snapshot.h1;
    info.labels = snapshot.unlabeled;
    info.alts = snapshot.noAlt;

    // Fonts: force the face, then read every declared face's status.
    const fontState = await page.evaluate(async () => {
      const faces = [...document.fonts];
      await Promise.all(faces.map((f) => f.load().catch(() => null)));
      await document.fonts.ready;
      return faces.map((f) => ({ family: f.family, status: f.status }));
    });
    if (fontState.length === 0) info.fonts.push("no @font-face declared");
    for (const f of fontState) if (f.status !== "loaded") info.fonts.push(f.family + " is " + f.status);
    const srcs = [...sources[file].matchAll(/url\(["']?([^"')]+\.woff2?)["']?\)/g)].map((m) => m[1]);
    for (const s of new Set(srcs)) {
      if (!existsSync(join(DIR, s))) info.fonts.push("missing file " + s);
      else {
        const lic = readdirSync(join(DIR, dirname(s))).filter((f) => /^OFL|LICENSE/i.test(f));
        if (lic.length === 0) info.fonts.push("no license text beside " + s);
      }
    }
    await context.close();
  }

  // 2. Overflow at the two narrow widths.
  for (const width of [320, 390]) {
    const context = await browser.newContext({ viewport: { width, height: 800 }, colorScheme: "light" });
    const page = await open(context, file);
    const over = await page.evaluate(() => {
      const root = document.documentElement;
      const extra = root.scrollWidth - root.clientWidth;
      const wide = [...document.querySelectorAll("body *")]
        .filter((el) => el.getBoundingClientRect().right > root.clientWidth + 0.5)
        .slice(0, 5)
        .map((el) => el.tagName.toLowerCase() + (el.className && typeof el.className === "string" ? "." + el.className.split(" ")[0] : ""));
      return { extra, wide };
    });
    if (over.extra > 0 || over.wide.length) {
      info.overflow.push(width + "px: " + over.extra + "px wider than the viewport" + (over.wide.length ? " (" + over.wide.join(", ") + ")" : ""));
    }
    await context.close();
  }

  // 3. Screenshots, light and dark, phone and desktop.
  const stem = basename(file, ".html");
  for (const scheme of ["light", "dark"]) {
    for (const v of [{ w: 390, h: 844, dpr: 2 }, { w: 1280, h: 800, dpr: 1 }]) {
      const context = await browser.newContext({ viewport: { width: v.w, height: v.h }, deviceScaleFactor: v.dpr, colorScheme: scheme });
      const page = await open(context, file);
      await page.waitForTimeout(250);
      await page.screenshot({ path: join(SHOTS, `${stem}-${v.w}x${v.h}-${scheme}.png`) });
      await page.screenshot({ path: join(SHOTS, `${stem}-${v.w}x${v.h}-${scheme}-full.png`), fullPage: true });
      await context.close();
    }
  }

  // 4. The signup form, with JavaScript on and off.
  if (/<form\b/i.test(sources[file])) {
    const endpointMatch = ENDPOINT_RE.exec(sources[file]);
    const endpointUrl = endpointMatch ? endpointMatch[2] : "";
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: "light" });
    const page = await open(context, file, endpointUrl);
    // With an endpoint set, answer it here. The check must never post a test address to the real list.
    let mockStatus = 503;
    if (endpointUrl) {
      await page.route((url) => url.href.startsWith(endpointUrl), (route) =>
        route.fulfill({ status: mockStatus, headers: { "access-control-allow-origin": "*" }, contentType: "application/json", body: "{}" }));
    }
    const form = page.locator("form").first();
    const readStatus = async (p) => ((await p.locator('[role="status"]').first().textContent()) || "").trim();
    const hasEmail = await page.locator('input[type="email"]').count();
    // The script enables the submit. Still disabled with JS on means it never ran.
    const scriptRan = hasEmail ? await form.locator('[type="submit"]').isEnabled() : false;
    if (!hasEmail) info.form.push("the form has no email input");
    else if (!scriptRan) info.form.push("with JS on, the submit button is still disabled, so the page script never ran (see the csp and console lines)");
    else {
      await page.fill('input[type="email"]', "not-an-address");
      await form.locator('[type="submit"]').click();
      await page.waitForTimeout(150);
      const invalid = await page.locator('input[type="email"][aria-invalid="true"]').count();
      if (!invalid) info.form.push("an invalid address was not flagged");
      await page.fill('input[type="email"]', "reader@example.com");
      await form.locator('[type="submit"]').click();
      await page.waitForTimeout(400);
      const status = await readStatus(page);
      if (endpointMatch && endpointUrl === "") {
        if (!/not open yet/i.test(status)) info.form.push("with SIGNUP_ENDPOINT empty, the status did not say signup is not open yet (read: " + JSON.stringify(status) + ")");
        if (SUCCESS.test(status)) info.form.push("with SIGNUP_ENDPOINT empty, the status claims success: " + JSON.stringify(status));
      } else if (endpointUrl) {
        // The first submit met a mocked 503, which must never read as success.
        if (SUCCESS.test(status)) info.form.push("a mocked HTTP 503 from the endpoint was reported as success: " + JSON.stringify(status));
        if (!status) info.form.push("a mocked HTTP 503 from the endpoint produced no message");
        mockStatus = 200;
        await page.fill('input[type="email"]', "reader@example.com");
        await form.locator('[type="submit"]').click();
        await page.waitForTimeout(600);
        const ok = await readStatus(page);
        if (!SUCCESS.test(ok)) info.form.push("a mocked HTTP 200 from the endpoint was not reported as received (read: " + JSON.stringify(ok) + ")");
      }
      // A screenshot of the form state, for the reviewer.
      await page.locator("form").first().screenshot({ path: join(SHOTS, `${stem}-form-after-submit.png`) });
    }
    await context.close();

    // The answer must land on screen. 393x659 is the iPhone Safari visible area with its
    // toolbars shown; the submit button starts at the bottom edge, the worst case.
    if (hasEmail && scriptRan) {
      const small = await browser.newContext({ viewport: { width: 393, height: 659 }, deviceScaleFactor: 2, colorScheme: "light" });
      const phone = await open(small, file, endpointUrl);
      if (endpointUrl) {
        await phone.route((url) => url.href.startsWith(endpointUrl), (route) =>
          route.fulfill({ status: 200, headers: { "access-control-allow-origin": "*" }, contentType: "application/json", body: "{}" }));
      }
      await phone.fill('input[type="email"]', "reader@example.com");
      await phone.evaluate(() => {
        const b = document.querySelector('form [type="submit"]').getBoundingClientRect();
        window.scrollBy(0, b.bottom - (window.innerHeight - 8));
      });
      await phone.waitForTimeout(100);
      await phone.locator('form [type="submit"]').click();
      await phone.waitForTimeout(900);
      const box = await phone.evaluate(() => {
        const s = document.querySelector('[role="status"]').getBoundingClientRect();
        return { top: Math.round(s.top), bottom: Math.round(s.bottom), h: window.innerHeight };
      });
      if (box.top < 0 || box.bottom > box.h || box.bottom - box.top < 1) {
        info.form.push(`at 393x659 the form's answer is off screen after submit (top ${box.top}, bottom ${box.bottom}, viewport ${box.h})`);
      }
      await phone.screenshot({ path: join(SHOTS, `${stem}-393x659-after-submit.png`) });
      await small.close();
    }

    const noJs = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: "light", javaScriptEnabled: false });
    const plain = await open(noJs, file);
    const state = await plain.evaluate(() => {
      const f = document.querySelector("form");
      const button = f && f.querySelector('[type="submit"]');
      const note = [...document.querySelectorAll("noscript")].map((n) => n.textContent).join(" ");
      return { disabled: button ? button.disabled : null, note: note.trim() };
    });
    if (state.disabled !== true) info.form.push("with JS off, the submit button is live, so a post would go nowhere");
    if (!state.note) info.form.push("with JS off, no noscript line explains the form");
    await plain.locator("form").first().screenshot({ path: join(SHOTS, `${stem}-form-no-js.png`) });
    await noJs.close();

    // 5. The form against a stand-in for the list provider, on a second origin.
    info.harness = await standIn(file);
  }
}

await browser.close();

// The page is served over http from one local origin, with SIGNUP_ENDPOINT pointed at a
// stand-in on another, so CORS applies exactly as it will in production. The page's own
// Content-Security-Policy is kept, re-pinned to the rewritten script and the stand-in.
// Each case says what the visitor must be told, and what they must never be told.
async function standIn(file) {
  const problems = [];
  let mode = "cors-200";
  const posts = [];
  const cors = { "access-control-allow-origin": "*" };
  const json = { ...cors, "content-type": "application/json" };
  const provider = http.createServer((req, res) => {
    const send = (status, headers, body) => { try { res.writeHead(status, headers); res.end(body); } catch (e) { /* client gone */ } };
    if (req.method === "OPTIONS") { posts.push({ mode, preflight: true }); return send(204, { ...cors, "access-control-allow-methods": "POST", "access-control-allow-headers": "accept, content-type" }, ""); }
    if (req.url === "/done") return send(200, json, "{}");
    let body = "";
    req.on("data", (c) => { body += c; });
    req.on("end", () => {
      posts.push({ mode, stored: body.includes("reader@example.com") });
      if (mode === "cors-200") return send(200, json, "{}");
      if (mode === "cors-503") return send(503, json, "{}");
      if (mode === "nocors-200") return send(200, { "content-type": "application/json" }, "{}");
      if (mode === "cors-200-error") return send(200, json, JSON.stringify({ success: false, error: "invalid_email" }));
      if (mode === "cors-302") return send(302, { ...cors, location: "/done" }, "");
      if (mode === "slow") return setTimeout(() => send(200, json, "{}"), 2500);
      return send(500, json, "{}");
    });
  });
  await new Promise((r) => provider.listen(0, "127.0.0.1", r));
  const endpoint = "http://127.0.0.1:" + provider.address().port + "/submit";

  const types = { ".html": "text/html; charset=utf-8", ".woff2": "font/woff2", ".txt": "text/plain; charset=utf-8" };
  const site = http.createServer((req, res) => {
    const path = decodeURIComponent(new URL(req.url, "http://x").pathname).replace(/^\/+/, "") || file;
    const full = join(DIR, path);
    if (!full.startsWith(DIR) || !existsSync(full) || statSync(full).isDirectory()) { res.writeHead(404); return res.end(); }
    let body = readFileSync(full);
    if (path === file) {
      let src = body.toString("utf8")
        .replace(ENDPOINT_RE, () => 'const SIGNUP_ENDPOINT = "' + endpoint + '"')
        .replace(/(\bconst\s+SIGNUP_TIMEOUT_MS\s*=\s*)\d+/, (m, a) => a + "1500");
      const hashes = inlineScripts(src).map(sha256).join(" ");
      src = src.replace(/(script-src )[^;"]+/, (m, a) => a + hashes)
        .replace(/(connect-src )[^;"]+/, (m, a) => a + new URL(endpoint).origin);
      body = Buffer.from(src, "utf8");
    }
    res.writeHead(200, { "content-type": types[extname(full)] || "application/octet-stream" });
    res.end(body);
  });
  await new Promise((r) => site.listen(0, "127.0.0.1", r));
  const pageUrl = "http://127.0.0.1:" + site.address().port + "/" + file;

  const cases = [
    { mode: "cors-200", say: /^Received\b/, never: /not added|not confirmed/i },
    { mode: "cors-503", say: /^Not added\b/, never: SUCCESS },
    { mode: "cors-200-error", say: /^Not added\b/, never: SUCCESS },
    { mode: "nocors-200", say: /^Not confirmed\b/, never: /received|accepted|not added|could not be reached/i, stored: true },
    { mode: "cors-302", say: /^Not confirmed\b/, never: SUCCESS },
    { mode: "slow", say: /^Not confirmed\b/, never: /received|accepted|not added/i },
  ];
  for (const c of cases) {
    mode = c.mode;
    const before = posts.length;
    const context = await browser.newContext({ viewport: { width: 390, height: 844 }, colorScheme: "light" });
    const page = await context.newPage();
    const policy = [];
    page.on("console", (m) => { if (/Content Security Policy/i.test(m.text())) policy.push(m.text().slice(0, 120)); });
    page.on("pageerror", (e) => policy.push("uncaught: " + e.message));
    await page.goto(pageUrl, { waitUntil: "load" });
    await page.fill('input[type="email"]', "reader@example.com");
    await page.locator('form [type="submit"]').click();
    let said = "";
    for (let i = 0; i < 60; i++) {
      said = ((await page.locator('[role="status"]').first().textContent()) || "").trim();
      if (said) break;
      await page.waitForTimeout(100);
    }
    if (!c.say.test(said)) problems.push(`${c.mode}: expected ${c.say} but read ${JSON.stringify(said)}`);
    if (c.never.test(said)) problems.push(`${c.mode}: told the visitor ${JSON.stringify(said)}`);
    if (c.stored && !posts.slice(before).some((p) => p.stored)) problems.push(`${c.mode}: the stand-in never received the address, so the case proved nothing`);
    for (const p of policy) problems.push(`${c.mode}: ${p}`);
    await context.close();
  }
  for (const server of [provider, site]) {
    if (server.closeAllConnections) server.closeAllConnections();
    await new Promise((r) => server.close(r));
  }
  return problems;
}

// Dashes: source, text and every attribute value.
{
  const hits = [];
  for (const file of htmlFiles) {
    const src = sources[file];
    for (let i = 0; i < src.length; i++) {
      if (DASH.test(src[i])) hits.push(`${file}:${lineOf(src, i)} U+${src.charCodeAt(i).toString(16).toUpperCase()}`);
    }
    const c = collected[file];
    for (const t of c.texts) if (DASH.test(t)) hits.push(`${file} text: ${t.trim().slice(0, 60)}`);
    for (const a of c.allAttrs) if (DASH.test(a)) hits.push(`${file} attribute: ${a.slice(0, 60)}`);
  }
  record("dashes", hits.length ? "FAIL" : "PASS",
    hits.length ? hits.slice(0, 6).join("; ") : "no U+2012 to U+2015 in text, attributes or source");
}

// Banned words: visible text, content attributes and the strings scripts can show.
{
  const hits = [];
  for (const file of htmlFiles) {
    const c = collected[file];
    const strings = c.scripts.flatMap((s) => [...s.matchAll(/(["'])((?:\\.|(?!\1).)*)\1/g)].map((m) => m[2]));
    const pool = [...c.texts, ...c.attrs, ...strings];
    for (const t of pool) {
      for (const m of t.matchAll(BANNED)) hits.push(`${file}: "${m[0]}"`);
      for (const m of t.matchAll(BANNED_OPENER)) hits.push(`${file}: opener "${m[1]}"`);
    }
  }
  record("banned words", hits.length ? "FAIL" : "PASS",
    hits.length ? [...new Set(hits)].slice(0, 8).join("; ") : "none of the house list in text, attributes or script strings");
}

{
  const bad = htmlFiles.flatMap((f) => perPage[f].overflow.map((o) => f + " " + o));
  record("overflow", bad.length ? "FAIL" : "PASS", bad.length ? bad.join("; ") : "no horizontal scroll at 320px or 390px");
}

record("requests", foreignRequests.length ? "FAIL" : "PASS",
  foreignRequests.length ? [...new Set(foreignRequests)].slice(0, 6).join("; ") : "every request stayed on file: or data:");

{
  const bad = htmlFiles.filter((f) => perPage[f].h1 !== 1).map((f) => f + " has " + perPage[f].h1);
  record("one h1", bad.length ? "FAIL" : "PASS", bad.length ? bad.join("; ") : "exactly one h1 per page");
}

{
  const bad = htmlFiles.flatMap((f) => perPage[f].labels.map((l) => f + ": " + l));
  record("labels", bad.length ? "FAIL" : "PASS", bad.length ? bad.join("; ") : "every control, link and button has a name");
}

{
  const bad = htmlFiles.flatMap((f) => perPage[f].alts.map((l) => f + ": " + l));
  record("image alt", bad.length ? "FAIL" : "PASS", bad.length ? bad.join("; ") : "no image without alt text");
}

{
  const bad = htmlFiles.flatMap((f) => perPage[f].fonts.map((l) => f + ": " + l));
  record("fonts", bad.length ? "FAIL" : "PASS", bad.length ? bad.join("; ") : "every declared face loaded, files and license present");
}

record("console", consoleProblems.length ? "FAIL" : "PASS",
  consoleProblems.length ? [...new Set(consoleProblems)].slice(0, 5).join("; ") : "no console errors or uncaught exceptions");

// Links: relative files exist and #fragments resolve.
{
  const bad = [];
  for (const file of htmlFiles) {
    for (const href of collected[file].hrefs) {
      if (/^[a-z][a-z0-9+.-]*:/i.test(href)) continue;
      const [path, frag] = href.split("#");
      const target = path ? path : file;
      if (path && !existsSync(join(DIR, path))) { bad.push(`${file}: ${href} (no such file)`); continue; }
      if (frag) {
        const ids = target === file ? collected[file].ids
          : (collected[target] ? collected[target].ids : [...(sources[target] || "").matchAll(/\bid="([^"]+)"/g)].map((m) => m[1]));
        if (!ids.includes(frag)) bad.push(`${file}: ${href} (no id "${frag}")`);
      }
    }
  }
  record("links", bad.length ? "FAIL" : "PASS", bad.length ? bad.join("; ") : "every relative link and fragment resolves");
}

{
  const bad = htmlFiles.flatMap((f) => perPage[f].form.map((l) => f + ": " + l));
  const formPages = htmlFiles.filter((f) => /<form\b/i.test(sources[f]));
  record("form honesty", bad.length ? "FAIL" : "PASS",
    bad.length ? bad.join("; ") : `${formPages.join(", ")}: flags a bad address, claims success only on a 2xx (none while the endpoint is empty), explains itself with JS off`);
}

// House punctuation in visible text, content attributes and script strings.
{
  const hits = [];
  for (const file of htmlFiles) {
    const c = collected[file];
    const strings = c.scripts.flatMap((s) => [...s.matchAll(/(["'])((?:\\.|(?!\1).)*)\1/g)].map((m) => m[2]));
    for (const t of [...c.texts, ...c.attrs, ...strings]) {
      for (const m of t.matchAll(PUNCT)) hits.push(`${file}: ${JSON.stringify(m[0])} in "${t.trim().slice(0, 50)}"`);
    }
  }
  record("punctuation", hits.length ? "FAIL" : "PASS",
    hits.length ? [...new Set(hits)].slice(0, 6).join("; ") : "no exclamation marks, curly quotes or ellipses");
}

{
  const bad = htmlFiles.flatMap((f) => perPage[f].regions.map((l) => f + ": " + l));
  const formPages = htmlFiles.filter((f) => /<form\b/i.test(sources[f]));
  record("live regions", bad.length ? "FAIL" : "PASS",
    bad.length ? bad.join("; ") : `${formPages.join(", ")}: status region and field error are in the page and the accessibility tree from load`);
}

{
  const bad = htmlFiles.flatMap((f) => perPage[f].harness.map((l) => f + ": " + l));
  const formPages = htmlFiles.filter((f) => /<form\b/i.test(sources[f]));
  record("form answers", bad.length ? "FAIL" : "PASS",
    bad.length ? bad.join("; ") : `${formPages.join(", ")} against a second-origin stand-in: 200 received; 503 and an error body not added; no CORS, a redirect and a timeout not confirmed`);
}

// Content-Security-Policy: present, pinned to the inline scripts as they are now, and
// letting the form reach its endpoint and nothing else.
{
  const bad = [];
  for (const file of htmlFiles) {
    const src = sources[file];
    const csp = cspOf(src);
    if (!csp) { bad.push(file + ": no Content-Security-Policy meta"); continue; }
    if (!(csp["default-src"] || []).includes("'none'")) bad.push(file + ": default-src is not 'none'");
    const scripts = inlineScripts(src);
    const allowed = csp["script-src"] || [];
    if (!scripts.length && !allowed.includes("'none'")) bad.push(file + ": no inline script, so script-src should be 'none'");
    for (const body of scripts) {
      const h = sha256(body);
      if (!allowed.includes(h)) bad.push(file + ": script-src does not carry the inline script's hash, which is now " + h);
    }
    const m = ENDPOINT_RE.exec(src);
    const connect = csp["connect-src"] || [];
    if (m && m[2]) {
      let origin = "";
      try { origin = new URL(m[2]).origin; } catch (e) { bad.push(file + ": SIGNUP_ENDPOINT is not a URL"); }
      if (origin && !connect.includes(origin)) bad.push(file + ": connect-src must name " + origin);
    } else if (!connect.includes("'none'")) bad.push(file + ": connect-src should be 'none' while nothing is sent");
  }
  record("csp", bad.length ? "FAIL" : "PASS",
    bad.length ? bad.join("; ") : "each page has a policy; script hashes and connect-src match the source");
}

// Passages marked data-unconfirmed wait on a ruling from Tee. Allowed while signup is closed.
{
  const endpointSet = htmlFiles.some((f) => { const m = ENDPOINT_RE.exec(sources[f]); return m && m[2]; });
  const marked = htmlFiles.flatMap((f) => collected[f].unconfirmed.map((t) => `${f}: "${t}"`));
  if (!marked.length) record("unconfirmed", "PASS", "no passage is marked data-unconfirmed");
  else record("unconfirmed", endpointSet ? "FAIL" : "WARN",
    (endpointSet ? "SIGNUP_ENDPOINT is set while these still wait on Tee: " : "DEPLOY BLOCKER: these wait on Tee's ruling: ") + marked.join("; "));
}

// The endpoint constant. Missing is a failure; empty is a deploy blocker, not a build failure.
{
  const formPages = htmlFiles.filter((f) => /<form\b/i.test(sources[f]));
  const missing = [];
  const empty = [];
  const insecure = [];
  for (const f of formPages) {
    const m = ENDPOINT_RE.exec(sources[f]);
    if (!m) missing.push(f);
    else if (m[2] === "") empty.push(f);
    else if (!/^https:\/\//.test(m[2])) insecure.push(f + " (" + m[2] + ")");
  }
  // Once the endpoint is set, any page still saying signup is not open is stale.
  const stale = empty.length ? [] : htmlFiles.filter((f) => collected[f].texts.some((t) => /not open yet/i.test(t)));
  if (missing.length) record("signup endpoint", "FAIL", "no const SIGNUP_ENDPOINT in " + missing.join(", "));
  else if (insecure.length) record("signup endpoint", "FAIL", "SIGNUP_ENDPOINT is not https in " + insecure.join(", "));
  else if (empty.length) record("signup endpoint", "WARN", "DEPLOY BLOCKER: SIGNUP_ENDPOINT is empty in " + empty.join(", "));
  else if (stale.length) record("signup endpoint", "FAIL", "SIGNUP_ENDPOINT is set but these pages still say signup is not open yet: " + stale.join(", "));
  else record("signup endpoint", "PASS", "SIGNUP_ENDPOINT is set to an https URL");
}

record("screenshots", "INFO", `390x844 and 1280x800, light and dark, for ${htmlFiles.join(", ")} in ${SHOTS}`);

const width = Math.max(...results.map((r) => r.name.length));
console.log(`Checked ${htmlFiles.length} page(s) in ${DIR} with ${executablePath}`);
for (const r of results) console.log(`${r.status.padEnd(5)} ${r.name.padEnd(width)}  ${r.detail}`);
const fails = results.filter((r) => r.status === "FAIL").length;
const warns = results.filter((r) => r.status === "WARN").length;
console.log(fails ? `RESULT: FAIL, ${fails} check(s) failed, ${warns} warning(s)` : `RESULT: PASS, ${warns} warning(s)`);
process.exit(fails ? 1 : 0);
