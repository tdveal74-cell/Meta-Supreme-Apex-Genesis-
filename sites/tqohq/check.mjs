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
// The signup form is Hostinger Reach's own page, framed on index.html without any
// Hostinger script (ruled by Tee 2026-09-23). The hosted form can never load here, and
// a check must never touch the real list, so every browser context in this script
// routes the one allowed URL, the Reach form document, to a local stand-in page and
// aborts every other off-file request. Screenshots therefore show the stand-in.
//
// Every HTML file in dir is loaded over file:// and checked. The run FAILS (exit 1) on:
//   em or en dashes (U+2012 to U+2015) in visible text, attributes or source
//   a banned house word
//   horizontal overflow at 320px or 390px
//   any request to a non-file URL other than the Reach form document in a frame,
//     named outright when it goes to cdn-reach.hostinger.com or to an impression URL
//   zero or several h1 elements
//   a form control or frame with no label or title, or a link or button with no name
//   an image with no alt text
//   a font file that fails to load
//   a console error or uncaught page error
//   a relative link or #fragment that points nowhere
//   an exclamation mark, a curly quote or an ellipsis in visible text
//   a missing Content-Security-Policy, or one that is not exactly as tight as the page
//     needs: script-src only the inline hashes, frame-src only the Reach origin on the
//     page with the frame and nothing on any other, connect-src 'none' everywhere
//   the reach frame check: the frame's src, title and sandbox tokens, no
//     allow-top-navigation, a white background of its own in light and dark, sizing
//     from a reach:resize message sent by the frame (the CSS min-height gives way to it,
//     between a 120px floor and a cap), no sizing from any other window or origin, no
//     redirect followed, empty web storage, IndexedDB and CacheStorage, and the frame at
//     its min-height with the fallback link when JavaScript is off
//   the phone fold: at 393x659, the iPhone Safari visible area, the submit is off screen
//     after tapping the Cc button, measured against a stand-in sized from the Reach
//     template with its heading and paragraph
//   an inline script that names a browser store (document.cookie, cookieStore,
//     indexedDB, localStorage, sessionStorage, caches or serviceWorker)
//   any page that references Hostinger's embed script, cdn-reach.hostinger.com or a
//     data-reach-form mount point
// It WARNS (exit 0) with "DEPLOY BLOCKER" while any passage is marked data-unconfirmed.
// Those wait on a ruling from Tee.
//
// Screenshots at 390x844 and 1280x800, light and dark, and at 393x659 after the Cc tap,
// go to TQO_SHOTS_DIR when set, otherwise to the session scratchpad path below.

import { createRequire } from "node:module";
import { readdirSync, existsSync, statSync, readFileSync, mkdirSync } from "node:fs";
import { join, dirname, resolve, basename } from "node:path";
import { fileURLToPath, pathToFileURL } from "node:url";
import { createHash } from "node:crypto";

const require = createRequire(import.meta.url);

const HERE = dirname(fileURLToPath(import.meta.url));
const DIR = resolve(process.argv[2] || HERE);
const SHOTS = process.env.TQO_SHOTS_DIR ||
  "/tmp/claude-0/-home-user-Meta-Supreme-Apex-Genesis-/331556fb-8043-5725-a414-72bc8745c2d9/scratchpad/shots";

// The Reach form, as created and activated by Tee on 2026-09-23 ("TQO home page").
const REACH_ORIGIN = "https://reach-forms.hostingerusercontent.com";
const REACH_FORM = REACH_ORIGIN + "/form/d2047809-a203-479e-8db7-f598580f7b7b";
const REACH_DECOY = REACH_FORM + "?decoy";
const REACH_HOME = "index.html";
const REACH_TITLE = "Signup form, run by Hostinger Reach";
const REACH_SANDBOX = ["allow-scripts", "allow-forms", "allow-same-origin", "allow-popups", "allow-popups-to-escape-sandbox"];
// The Reach template measured 543px at its tallest (a 288px frame, the 320 viewport,
// with an 8px body margin). The CSS min-height must hold at least that with no script.
const REACH_TEMPLATE_HEIGHT = 543;
// Once Reach reports its height, the frame takes it, but never below this floor...
const REACH_FLOOR = 120;
// ...and however tall Reach says it is, the frame must never grow past this.
const REACH_CAP_LIMIT = 2400;
const REACH_SCRIPT = /embed\.js|cdn-reach\.hostinger\.com|data-reach-form/gi;
// The one ask on a phone: 393x659 is the iPhone Safari visible area. After the Cc button's
// jump, the form's submit must be on screen there.
const FOLD = { width: 393, height: 659 };
// Browser storage the page's own script must never name. Over file:// Chromium drops
// cookie writes silently, so a cookie can only be caught by reading the source.
const STORAGE_API = /\b(?:document\s*\.\s*cookie|cookieStore|indexedDB|localStorage|sessionStorage|caches|serviceWorker)\b/g;

// The stand-in served at REACH_FORM. It is sized from the Reach template "TQO home page"
// as read on 2026-09-23: the same 8px body margin, box sizes and type sizes, with the
// template's own heading and paragraph, so the phone fold case measures the form as Reach
// serves it today. It says in its title and in the badge's place that it is a stand-in,
// loads nothing, and sends one reach:resize with its own height, margins included.
const STUB_BADGE = "data:image/svg+xml," + encodeURIComponent(
  '<svg xmlns="http://www.w3.org/2000/svg" width="159" height="40"><rect width="159" height="40" fill="#ffe58a"/>' +
  '<text x="79.5" y="25" font-family="sans-serif" font-size="13" font-weight="600" text-anchor="middle" fill="#111">Test stand-in</text></svg>');
const STUB = `<!doctype html>
<html lang="en"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>Test stand-in for the Reach form</title>
<style>
body { margin: 8px; }
.f { width: 100%; background: #fff; font-family: system-ui, -apple-system, Segoe UI, Roboto, Helvetica, Arial, sans-serif; box-sizing: border-box; }
.w { max-width: 520px; width: 100%; margin: 0 auto; padding: 32px 20px; box-sizing: border-box; }
h1 { margin: 0 0 12px; font-size: 26px; font-weight: 700; line-height: 1.2; color: #111; }
p { margin: 0 0 24px; font-size: 16px; line-height: 1.5; color: #444; }
label { display: block; margin-bottom: 8px; font-size: 14px; font-weight: 500; line-height: 1.4; color: #333; }
input { width: 100%; padding: 12px; border: 1px solid #d1d1d1; border-radius: 8px; font-family: inherit; font-size: 16px; color: #111; box-sizing: border-box; background: #fff; }
.gap { min-height: 22px; }
button { width: 100%; margin-top: 8px; padding: 14px; border: none; border-radius: 8px; background: #111; color: #fff; font-family: inherit; font-size: 16px; font-weight: 600; }
.badge { margin-top: 20px; padding: 8px 0; width: 100%; text-align: center; }
.badge img { max-height: 40px; }
</style></head><body><div class="f"><div class="w">
<h1>Stay in the loop</h1>
<p>Get an email each time a new TQO episode is published.</p>
<div><label for="n">First name</label><input id="n" type="text"><div class="gap"></div></div>
<div><label for="e">Email</label><input id="e" type="email" placeholder="your@email.com"><div class="gap"></div></div>
<button type="button" data-reach-submit>Join the club</button>
<div class="badge"><img alt="Test stand-in, not the Reach form" width="159" height="40" src="${STUB_BADGE}"></div>
</div></div>
<script>var b = document.body; parent.postMessage({ type: "reach:resize", payload: { height: Math.ceil(b.getBoundingClientRect().bottom + parseFloat(getComputedStyle(b).marginBottom)) } }, "*");</script>
</body></html>`;

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
const LOCAL = /^(file|data|about|blob):/;

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
function sameSet(a, b) { return a.length === b.length && a.every((x) => b.includes(x)); }
function hasFrame(src) { return /<iframe\b/i.test(src); }
function describe(url) {
  if (/cdn-reach\.hostinger\.com/i.test(url)) return "the Reach CDN, " + url;
  if (/impression/i.test(url)) return "an impression beacon, " + url;
  return url;
}
async function until(test, ms) {
  const end = Date.now() + ms;
  for (;;) {
    try { if (await test()) return true; } catch (e) { /* the page may be mid-navigation */ }
    if (Date.now() > end) return false;
    await new Promise((r) => setTimeout(r, 50));
  }
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
const framedRequests = [];
const consoleProblems = [];

// Every context gets this route: the Reach form document goes to the stand-in, and
// every other off-file request is aborted, so nothing this script does leaves the machine.
async function newContext(options) {
  const context = await browser.newContext(options);
  await context.route((url) => !LOCAL.test(url.href), (route) => {
    const req = route.request();
    const url = req.url();
    if ((url === REACH_FORM || url === REACH_DECOY) && req.resourceType() === "document" && req.method() === "GET") {
      return route.fulfill({ status: 200, contentType: "text/html; charset=utf-8", body: STUB });
    }
    return route.abort("blockedbyclient");
  });
  return context;
}

function watch(page, file) {
  page.on("request", (r) => {
    const url = r.url();
    if (LOCAL.test(url)) return;
    let framed = false;
    try { framed = Boolean(r.frame().parentFrame()); } catch (e) { framed = false; }
    if (url === REACH_FORM && r.resourceType() === "document" && framed) {
      framedRequests.push(file);
      return;
    }
    foreignRequests.push(file + ": " + describe(url));
  });
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    consoleProblems.push(file + ": console error: " + m.text());
  });
  page.on("pageerror", (e) => consoleProblems.push(file + ": uncaught: " + e.message));
}

async function open(context, file) {
  const page = await context.newPage();
  watch(page, file);
  await page.goto(pathToFileURL(join(DIR, file)).href, { waitUntil: "load" });
  await page.evaluate(() => document.fonts.ready);
  return page;
}

function reachFrameOf(page, url = REACH_FORM) { return page.frames().find((f) => f.url() === url); }

// The frame is lazy: bring it near the screen, let the stand-in load and send its size,
// then go back to the top. Returns false when the size never arrived.
async function wakeFrame(page) {
  const el = page.locator("iframe").first();
  await el.scrollIntoViewIfNeeded();
  const sized = await until(async () => (await el.evaluate((f) => f.style.height)) !== "", 4000);
  await page.evaluate(() => window.scrollTo({ top: 0, left: 0, behavior: "instant" }));
  return sized;
}

const perPage = {};
for (const file of htmlFiles) perPage[file] = { overflow: [], fonts: [], h1: null, labels: [], alts: [], wake: [] };

for (const file of htmlFiles) {
  const info = perPage[file];

  // 1. Text, attributes and structure, read once at 390 in light.
  {
    const context = await newContext({ viewport: { width: 390, height: 844 }, colorScheme: "light" });
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
      for (const el of document.querySelectorAll("iframe")) {
        if (!(el.getAttribute("title") || "").trim()) unlabeled.push("iframe with no title");
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
      return { texts, attrs, allAttrs, scripts, h1, unlabeled, noAlt, hrefs, ids, unconfirmed };
    });
    collected[file] = snapshot;
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
    const context = await newContext({ viewport: { width, height: 800 }, colorScheme: "light" });
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

  // 3. Screenshots, light and dark, phone and desktop. A framed page is woken first, so
  // the frame holds the stand-in at its sent size, and at 390 the frame's own section
  // gets a viewport shot too.
  const stem = basename(file, ".html");
  for (const scheme of ["light", "dark"]) {
    for (const v of [{ w: 390, h: 844, dpr: 2 }, { w: 1280, h: 800, dpr: 1 }]) {
      const context = await newContext({ viewport: { width: v.w, height: v.h }, deviceScaleFactor: v.dpr, colorScheme: scheme });
      const page = await open(context, file);
      const framed = hasFrame(sources[file]);
      if (framed && !(await wakeFrame(page))) info.wake.push(`${v.w}x${v.h} ${scheme}: the stand-in's size never reached the frame`);
      // The page, not the browser, sets what shows behind the Reach page: white, in
      // both schemes, whatever the framed document or the browser's canvas does.
      if (framed) {
        const bg = await page.locator("iframe").first().evaluate((f) => getComputedStyle(f).backgroundColor);
        if (bg !== "rgb(255, 255, 255)") info.wake.push(`${v.w}x${v.h} ${scheme}: the frame's own background is ${bg}, not white`);
      }
      await page.waitForTimeout(250);
      await page.screenshot({ path: join(SHOTS, `${stem}-${v.w}x${v.h}-${scheme}.png`) });
      await page.screenshot({ path: join(SHOTS, `${stem}-${v.w}x${v.h}-${scheme}-full.png`), fullPage: true });
      if (framed && v.w === 390) {
        await page.locator("iframe").first().evaluate((f) => (f.closest("section") || f).scrollIntoView({ block: "start", behavior: "instant" }));
        await page.waitForTimeout(150);
        await page.screenshot({ path: join(SHOTS, `${stem}-${v.w}x${v.h}-${scheme}-reach-frame.png`) });
      }
      await context.close();
    }
  }
}

// 4. The Reach frame, on the one page that carries it.
const reach = await reachFrame();

// 5. The one ask on a phone, after the Cc button's jump.
const fold = await phoneFold();

await browser.close();

// A visitor on an iPhone taps the Cc button. The page jumps to the signup section, and the
// submit inside the frame must then be on screen at 393x659, the Safari visible area. The
// stand-in carries the Reach template's own heading and paragraph, so this measures the
// form as Reach serves it today; deleting them in Reach only moves the button up.
async function phoneFold() {
  const problems = [];
  const done = [];
  if (!sources[REACH_HOME] || !hasFrame(sources[REACH_HOME])) return { problems: [`${REACH_HOME} has no frame to measure`], done };
  const home = pathToFileURL(join(DIR, REACH_HOME)).href;
  const context = await newContext({
    viewport: FOLD, deviceScaleFactor: 2, isMobile: true, hasTouch: true, colorScheme: "light", reducedMotion: "reduce",
  });
  const page = await context.newPage();
  watch(page, REACH_HOME + " at " + FOLD.width + "x" + FOLD.height);
  page.setDefaultTimeout(8000);
  try {
    await page.goto(home, { waitUntil: "load" });
    await page.evaluate(() => document.fonts.ready);
    const cc = page.locator('a[href="#distribution"].button');
    if ((await cc.count()) !== 1) throw new Error(`there are ${await cc.count()} Cc buttons that jump to #distribution, not one`);
    await cc.tap();
    const el = page.locator("iframe").first();
    let frame = null;
    await until(() => (frame = reachFrameOf(page)), 4000);
    if (!frame) throw new Error("after the Cc jump the frame never loaded the Reach form URL");
    await frame.waitForLoadState("load");
    if (!(await until(async () => (await el.evaluate((f) => f.style.height)) !== "", 3000))) {
      throw new Error("after the Cc jump the stand-in's size never reached the frame");
    }
    await page.waitForTimeout(300);
    const top = await el.evaluate((f) => f.getBoundingClientRect().top);
    const vh = await page.evaluate(() => innerHeight);
    const heading = await page.evaluate(() => {
      const h = document.getElementById("distribution-title");
      return h ? h.getBoundingClientRect().top : null;
    });
    const inside = await frame.evaluate(() => {
      const box = (s) => { const e = document.querySelector(s); if (!e) return null; const r = e.getBoundingClientRect(); return { top: r.top, bottom: r.bottom }; };
      return { email: box('input[type="email"]'), submit: box("[data-reach-submit]") };
    });
    if (!inside.submit || !inside.email) throw new Error("the stand-in has no email field or submit to measure");
    const at = (b) => ({ top: Math.round(top + b.top), bottom: Math.round(top + b.bottom) });
    const email = at(inside.email);
    const submit = at(inside.submit);
    if (heading === null || heading < 0 || heading > vh) problems.push(`after the Cc jump the section heading is not on screen (top ${heading})`);
    if (email.bottom > vh) problems.push(`after the Cc jump the email field ends at ${email.bottom}px, below the ${vh}px fold`);
    if (submit.bottom > vh) problems.push(`after the Cc jump the submit is at ${submit.top} to ${submit.bottom}px, below the ${vh}px fold`);
    if (!problems.length) done.push(`${FOLD.width}x${FOLD.height} after tapping Cc: frame top ${Math.round(top)}px, email ${email.top} to ${email.bottom}px, submit ${submit.top} to ${submit.bottom}px, all above the ${vh}px fold`);
    await page.screenshot({ path: join(SHOTS, `${basename(REACH_HOME, ".html")}-${FOLD.width}x${FOLD.height}-light-after-cc.png`) });
  } catch (e) {
    problems.push("the phone fold case stopped: " + String(e.message || e).split("\n")[0]);
  }
  await context.close();
  return { problems, done };
}

// The frame's contract, tested against the stand-in. Each case must bite: the decoy
// cases prove they reached the page before their answer counts.
async function reachFrame() {
  const problems = [];
  const done = [];
  for (const f of htmlFiles) {
    if (f !== REACH_HOME && hasFrame(sources[f])) problems.push(`${f} carries a frame; only ${REACH_HOME} may`);
  }
  if (!sources[REACH_HOME]) return { problems: problems.concat(`there is no ${REACH_HOME}`), done };
  if (!hasFrame(sources[REACH_HOME])) return { problems: problems.concat(`${REACH_HOME} has no frame`), done };
  for (const f of htmlFiles) for (const w of perPage[f].wake) problems.push(`${f} ${w}`);

  const home = pathToFileURL(join(DIR, REACH_HOME)).href;
  const context = await newContext({ viewport: { width: 390, height: 844 }, colorScheme: "light" });
  const page = await context.newPage();
  const seen = [];
  const errors = [];
  const navigations = [];
  page.on("request", (r) => { if (!LOCAL.test(r.url())) seen.push({ url: r.url(), type: r.resourceType() }); });
  page.on("console", (m) => { if (m.type() === "error") errors.push("console error: " + m.text()); });
  page.on("pageerror", (e) => errors.push("uncaught: " + e.message));
  await page.goto(home, { waitUntil: "load" });
  page.on("framenavigated", (f) => { if (f === page.mainFrame()) navigations.push(f.url()); });

  // (a) The frame's attributes, as written. The min-height is the stylesheet's, read with
  // any inline value the script has already set put aside, because the frame may have
  // loaded and reported its size before this line runs.
  const attrs = await page.evaluate(() => [...document.querySelectorAll("iframe")].map((f) => {
    const inline = f.style.minHeight;
    f.style.minHeight = "";
    const cs = getComputedStyle(f);
    const cssMin = parseFloat(cs.minHeight) || 0;
    f.style.minHeight = inline;
    return {
      src: f.getAttribute("src"), title: f.getAttribute("title"), sandbox: f.getAttribute("sandbox"),
      loading: f.getAttribute("loading"), referrerpolicy: f.getAttribute("referrerpolicy"),
      allow: f.getAttribute("allow"), srcdoc: f.hasAttribute("srcdoc"),
      border: [cs.borderTopWidth, cs.borderRightWidth, cs.borderBottomWidth, cs.borderLeftWidth],
      width: f.getBoundingClientRect().width, room: f.parentElement.clientWidth,
      cap: cs.maxWidth === "none" ? Infinity : parseFloat(cs.maxWidth),
      minHeight: cssMin,
    };
  }));
  if (attrs.length !== 1) problems.push(`${REACH_HOME} has ${attrs.length} frames, not one`);
  const a = attrs[0];
  const minH = a ? a.minHeight : 0;
  if (a) {
    if (a.src !== REACH_FORM) problems.push(`src is ${JSON.stringify(a.src)}, not ${REACH_FORM}`);
    if (a.title !== REACH_TITLE) problems.push(`title is ${JSON.stringify(a.title)}, not ${JSON.stringify(REACH_TITLE)}`);
    const tokens = (a.sandbox === null ? [] : a.sandbox.split(/\s+/).filter(Boolean));
    if (a.sandbox === null) problems.push("the frame has no sandbox attribute");
    const top = tokens.filter((t) => /^allow-top-navigation/.test(t));
    if (top.length) problems.push("sandbox allows top navigation: " + top.join(" "));
    if (!sameSet([...new Set(tokens)], REACH_SANDBOX)) problems.push(`sandbox is "${tokens.join(" ")}", not "${REACH_SANDBOX.join(" ")}"`);
    if (a.loading !== "lazy") problems.push(`loading is ${JSON.stringify(a.loading)}, not "lazy"`);
    if (a.referrerpolicy !== "strict-origin-when-cross-origin") problems.push(`referrerpolicy is ${JSON.stringify(a.referrerpolicy)}`);
    if (a.allow !== null) problems.push(`the frame delegates permissions: allow="${a.allow}"`);
    if (a.srcdoc) problems.push("the frame has a srcdoc, which would replace the Reach page");
    if (a.border.some((b) => b !== "0px")) problems.push("the frame has a border: " + a.border.join(" "));
    if (Math.abs(a.width - Math.min(a.room, a.cap)) > 0.5) problems.push(`the frame is ${a.width}px wide in ${a.room}px of room, not 100% up to its ${a.cap}px cap`);
    if (minH < REACH_TEMPLATE_HEIGHT) problems.push(`the CSS min-height is ${minH}px, below the ${REACH_TEMPLATE_HEIGHT}px the Reach template needs with no script`);
    done.push(`(a) src, title, sandbox "${REACH_SANDBOX.join(" ")}", lazy, no border, full width, min-height ${minH}px`);
  }
  // Every store a page script can reach from file://. Cookies are not here: Chromium
  // drops cookie writes over file:// without an error, so the "storage apis" check reads
  // the script's source for them instead.
  const storage = () => page.evaluate(async () => {
    const out = {};
    try { out.local = localStorage.length; out.session = sessionStorage.length; } catch (e) { out.error = "web storage: " + e.message; }
    try { out.idb = (await indexedDB.databases()).map((d) => d.name); } catch (e) { out.error = "IndexedDB: " + e.message; }
    try { out.caches = await caches.keys(); } catch (e) { out.error = "CacheStorage: " + e.message; }
    return out;
  });
  const atLoad = await storage();

  // The stand-in loads when the frame nears the screen and sends its own size.
  // Any step that throws ends the message cases as a named failure, never a crash.
  page.setDefaultTimeout(8000);
  const el = page.locator("iframe").first();
  await el.scrollIntoViewIfNeeded();
  let frame = null;
  await until(() => (frame = reachFrameOf(page)), 4000);
  if (!frame) {
    problems.push("the frame never loaded the Reach form URL (served by the stand-in)");
  } else try {
    await frame.waitForLoadState("load");
    const origin = await frame.evaluate(() => location.origin);
    if (origin !== REACH_ORIGIN) problems.push(`the stand-in ran at ${origin}, not ${REACH_ORIGIN}, so the origin cases prove nothing`);
    const height = () => el.evaluate((f) => Math.round(f.getBoundingClientRect().height));
    const settle = () => page.waitForTimeout(150);
    if (!(await until(async () => (await el.evaluate((f) => f.style.height)) !== "", 3000))) {
      problems.push("the stand-in's load-time reach:resize never set a height");
    } else {
      // The stand-in's own report fits it exactly: the frame takes that height, below the
      // CSS min-height, with no dead space under the form and no scroll bar inside it.
      await settle();
      const fit = await frame.evaluate(() => ({ scroll: document.documentElement.scrollHeight, inner: innerHeight }));
      const own = await height();
      if (own >= minH) problems.push(`after the stand-in reported its size the frame is ${own}px, still held at its ${minH}px min-height`);
      if (fit.scroll > fit.inner) problems.push(`after sizing, the stand-in scrolls inside the frame: ${fit.scroll}px of content in ${fit.inner}px`);
      if (own < minH && fit.scroll <= fit.inner) done.push(`(b) the stand-in's own report made the frame ${own}px, under the ${minH}px min-height, with no inner scroll`);
    }

    // (b) A reach:resize from the frame sets the height.
    const send = (target, message) => target.evaluate((m) => parent.postMessage(m, "*"), message);
    await send(frame, { type: "reach:resize", payload: { height: 700 } });
    await settle();
    const b = await height();
    if (b !== 700) problems.push(`a reach:resize of 700 from the frame left it at ${b}px`);
    else done.push("reach:resize 700 from the frame made it 700px");
    await send(frame, { type: "reach:resize", payload: { height: 300 } });
    await settle();
    const under = await height();
    if (under !== 300) problems.push(`a reach:resize of 300 from the frame left it at ${under}px, so the CSS min-height never gave way`);

    // The clamp: never below the floor, never past the cap.
    await send(frame, { type: "reach:resize", payload: { height: 10 } });
    await settle();
    const low = await height();
    if (low !== REACH_FLOOR) problems.push(`a reach:resize of 10 made the frame ${low}px, not the ${REACH_FLOOR}px floor`);
    await send(frame, { type: "reach:resize", payload: { height: 1e7 } });
    await settle();
    const high = await height();
    if (high > REACH_CAP_LIMIT || high <= low) problems.push(`a reach:resize of 10000000 made the frame ${high}px`);
    else if (under === 300) done.push(`300 made it 300px; clamped to ${low}px and ${high}px`);

    // Shapes that are not a finite height change nothing. Each case starts from 700, so
    // one failure cannot hide or fake another. Labels are written out because
    // JSON.stringify prints NaN and Infinity as null.
    const bad = [
      ["height NaN", { type: "reach:resize", payload: { height: NaN } }],
      ["height Infinity", { type: "reach:resize", payload: { height: Infinity } }],
      ["height -Infinity", { type: "reach:resize", payload: { height: -Infinity } }],
      ['height "900", a string', { type: "reach:resize", payload: { height: "900" } }],
      ["payload 900, not an object", { type: "reach:resize", payload: 900 }],
      ["no payload", { type: "reach:resize" }],
      ['type "reach:size"', { type: "reach:size", payload: { height: 900 } }],
      ['the bare string "reach:resize"', "reach:resize"],
    ];
    for (const [label, m] of bad) {
      await send(frame, { type: "reach:resize", payload: { height: 700 } });
      await settle();
      await send(frame, m);
      await settle();
      const h = await height();
      if (h !== 700) problems.push(`a message with ${label} changed the height to ${h}px`);
    }
    await send(frame, { type: "reach:resize", payload: { height: 700 } });
    await settle();

    // (c) The right shape from the wrong window, or the wrong origin, changes nothing.
    await page.evaluate(() => window.postMessage({ type: "reach:resize", payload: { height: 900 } }, "*"));
    await settle();
    const c1 = await height();
    if (c1 !== 700) problems.push(`a reach:resize posted by the top window changed the height to ${c1}px`);

    // A second frame at the Reach origin: right origin, wrong source.
    await page.evaluate((src) => {
      const d = document.createElement("iframe");
      d.id = "decoy";
      d.src = src;
      document.body.append(d);
    }, REACH_DECOY);
    let decoy = null;
    await until(() => (decoy = reachFrameOf(page, REACH_DECOY)), 4000);
    if (!decoy) problems.push("the decoy frame at the Reach origin never loaded, so the source case proved nothing");
    else {
      await decoy.waitForLoadState("load");
      const decoyOrigin = await decoy.evaluate(() => location.origin);
      if (decoyOrigin !== REACH_ORIGIN) problems.push(`the decoy ran at ${decoyOrigin}, so the source case proved nothing`);
      await send(decoy, { type: "reach:resize", payload: { height: 900 } });
      await settle();
      const c2 = await height();
      if (c2 !== 700) problems.push(`a reach:resize from another frame at the Reach origin changed the height to ${c2}px`);
      else done.push("(c) ignored from the top window and from a second Reach-origin frame");
    }
    await page.evaluate(() => { const d = document.getElementById("decoy"); if (d) d.remove(); });

    // (d) reach:redirect and reach:submitted are ignored: no navigation, no request.
    const before = seen.length;
    await send(frame, { type: "reach:redirect", payload: { url: pathToFileURL(join(DIR, "privacy.html")).href } });
    await send(frame, { type: "reach:redirect", payload: { url: "https://example.com/thanks" } });
    await send(frame, { type: "reach:submitted", payload: {} });
    await page.waitForTimeout(500);
    if (page.url() !== home || navigations.length) problems.push("a reach:redirect navigated the page to " + (navigations[0] || page.url()));
    const after = seen.slice(before);
    if (after.length) problems.push("reach:redirect or reach:submitted caused requests: " + after.map((r) => r.url).join(", "));
    if (page.url() === home && !navigations.length && !after.length) done.push("(d) reach:redirect and reach:submitted did nothing");
    if (page.url() !== home || navigations.length) throw new Error("the page left " + home + ", so the origin case could not run");

    // The same frame, moved off the Reach origin: right source, wrong origin.
    await el.evaluate((f) => { f.src = "about:blank"; });
    await until(() => frame.url() === "about:blank", 3000);
    const blankOrigin = await frame.evaluate(() => location.origin).catch(() => REACH_ORIGIN);
    if (frame.url() !== "about:blank" || blankOrigin === REACH_ORIGIN) problems.push("the frame could not be moved off the Reach origin, so the origin case proved nothing");
    else {
      await send(frame, { type: "reach:resize", payload: { height: 900 } });
      await settle();
      const c3 = await height();
      if (c3 !== 700) problems.push(`a reach:resize from the frame at origin ${blankOrigin} changed the height to ${c3}px`);
      else done.push(`ignored from the frame itself once at origin ${blankOrigin}`);
    }
  } catch (e) {
    problems.push("the message cases stopped: " + String(e.message || e).split("\n")[0]);
  }

  // (e) Nothing stored, at load or after all of the above.
  const atEnd = await storage();
  const empty = (s) => !s.error && !s.local && !s.session && !s.idb.length && !s.caches.length;
  for (const [when, s] of [["at load", atLoad], ["after the messages", atEnd]]) {
    if (s.error) problems.push(`storage could not be read ${when}: ${s.error}`);
    else if (!empty(s)) problems.push(`storage is not empty ${when}: ${s.local} in localStorage, ${s.session} in sessionStorage, IndexedDB ${JSON.stringify(s.idb)}, CacheStorage ${JSON.stringify(s.caches)}`);
  }
  if (empty(atLoad) && empty(atEnd)) done.push("(e) localStorage, sessionStorage, IndexedDB and CacheStorage empty");

  // Only the Reach form document, and the test's own decoy of it, may leave the page.
  for (const r of seen) {
    if ((r.url === REACH_FORM || r.url === REACH_DECOY) && r.type === "document") continue;
    problems.push("request to " + describe(r.url));
  }
  for (const e of errors) problems.push(e);
  await context.close();

  // (f) JavaScript off: the frame still stands at its min-height, with the fallback link.
  const off = await newContext({ viewport: { width: 390, height: 844 }, colorScheme: "light", javaScriptEnabled: false });
  const plain = await off.newPage();
  const offSeen = [];
  plain.on("request", (r) => { if (!LOCAL.test(r.url())) offSeen.push(r.url()); });
  plain.setDefaultTimeout(8000);
  await plain.goto(home, { waitUntil: "load" });
  const plainFrame = plain.locator("iframe").first();
  if (!(await plainFrame.count())) problems.push("with JS off there is no frame");
  else try {
    await plainFrame.scrollIntoViewIfNeeded();
    const loaded = await until(() => reachFrameOf(plain), 4000);
    const box = await plainFrame.boundingBox();
    const offMin = await plainFrame.evaluate((f) => parseFloat(getComputedStyle(f).minHeight) || 0);
    if (!loaded) problems.push("with JS off the frame never loaded the Reach form URL");
    if (!box || Math.abs(box.height - offMin) > 0.5) problems.push(`with JS off the frame is ${box ? box.height : 0}px tall, not its min-height ${offMin}px`);
    const fallback = plain.locator(`a[href="${REACH_FORM}"]`);
    const text = (await fallback.count()) ? ((await fallback.first().textContent()) || "").trim() : "";
    if (!text || !(await fallback.first().isVisible())) problems.push("with JS off there is no visible fallback link to the Reach form");
    if (loaded && box && Math.abs(box.height - offMin) <= 0.5 && text) done.push(`(f) with JS off the frame stands at ${offMin}px and the fallback link "${text}" is there`);
    await plainFrame.evaluate((f) => (f.closest("section") || f).scrollIntoView({ block: "start", behavior: "instant" }));
    await plain.screenshot({ path: join(SHOTS, `${basename(REACH_HOME, ".html")}-390x844-light-no-js-reach-frame.png`) });
  } catch (e) {
    problems.push("the JS off case stopped: " + String(e.message || e).split("\n")[0]);
  }
  for (const u of offSeen) if (u !== REACH_FORM) problems.push("with JS off, request to " + describe(u));
  await off.close();
  return { problems, done };
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
  foreignRequests.length ? [...new Set(foreignRequests)].slice(0, 6).join("; ")
    : `every request stayed on file: or data:, except ${framedRequests.length} framed document request(s) for ${REACH_FORM}, each answered by the local stand-in`);

{
  const bad = htmlFiles.filter((f) => perPage[f].h1 !== 1).map((f) => f + " has " + perPage[f].h1);
  record("one h1", bad.length ? "FAIL" : "PASS", bad.length ? bad.join("; ") : "exactly one h1 per page");
}

{
  const bad = htmlFiles.flatMap((f) => perPage[f].labels.map((l) => f + ": " + l));
  record("labels", bad.length ? "FAIL" : "PASS", bad.length ? bad.join("; ") : "every control, frame, link and button has a name");
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

// Content-Security-Policy: present, pinned to the inline scripts as they are now, framing
// only Reach and only where the frame is, and letting the page connect nowhere.
{
  const bad = [];
  for (const file of htmlFiles) {
    const src = sources[file];
    const csp = cspOf(src);
    if (!csp) { bad.push(file + ": no Content-Security-Policy meta"); continue; }
    if (!sameSet(csp["default-src"] || [], ["'none'"])) bad.push(file + ": default-src is not 'none'");
    if (/<script\b[^>]*\bsrc\s*=/i.test(src)) bad.push(file + ": loads a script file");
    const hashes = inlineScripts(src).map(sha256);
    const allowed = csp["script-src"] || [];
    if (!hashes.length && !sameSet(allowed, ["'none'"])) bad.push(file + ": no inline script, so script-src should be 'none'");
    for (const h of hashes) {
      if (!allowed.includes(h)) bad.push(file + ": script-src does not carry the inline script's hash, which is now " + h);
    }
    if (hashes.length && !sameSet(allowed, [...new Set(hashes)])) bad.push(file + ": script-src allows more than the inline script's hash: " + allowed.join(" "));
    if (!sameSet(csp["connect-src"] || [], ["'none'"])) bad.push(file + ": connect-src should be 'none', the page sends nothing");
    const frameSrc = csp["frame-src"];
    if (hasFrame(src)) {
      if (!frameSrc || !sameSet(frameSrc, [REACH_ORIGIN])) bad.push(file + ": frame-src must be exactly " + REACH_ORIGIN + ", not " + (frameSrc ? frameSrc.join(" ") : "missing"));
    } else if (frameSrc && !sameSet(frameSrc, ["'none'"])) bad.push(file + ": has no frame, so frame-src must be 'none' or absent, not " + frameSrc.join(" "));
    if (csp["child-src"] && !sameSet(csp["child-src"], ["'none'"])) bad.push(file + ": child-src widens framing: " + csp["child-src"].join(" "));
    for (const d of ["form-action", "base-uri"]) if (!sameSet(csp[d] || [], ["'none'"])) bad.push(file + ": " + d + " is not 'none'");
  }
  record("csp", bad.length ? "FAIL" : "PASS",
    bad.length ? bad.join("; ") : `each page has a policy; script-src is the inline hash or 'none'; frame-src is ${REACH_ORIGIN} on ${REACH_HOME} only; connect-src 'none'`);
}

{
  record("reach frame", reach.problems.length ? "FAIL" : "PASS",
    reach.problems.length ? reach.problems.join("; ") : `${REACH_HOME}, frame routed to a local stand-in: ` + reach.done.join("; ") + "; the frame's own background is white in light and dark");
}

record("phone fold", fold.problems.length ? "FAIL" : "PASS",
  fold.problems.length ? fold.problems.join("; ") : fold.done.join("; ") + ", against a stand-in sized from the Reach template with its heading and paragraph");

// The page's own scripts name no browser store. This is read from the source because
// Chromium drops cookie writes over file:// silently, so no run here could see one.
{
  const hits = [];
  for (const file of htmlFiles) {
    const src = sources[file];
    const scriptStart = [...src.matchAll(/<script>/g)].map((m) => m.index + m[0].length);
    inlineScripts(src).forEach((body, i) => {
      for (const m of body.matchAll(STORAGE_API)) hits.push(`${file}:${lineOf(src, scriptStart[i] + m.index)} "${m[0]}"`);
    });
  }
  record("storage apis", hits.length ? "FAIL" : "PASS",
    hits.length ? hits.join("; ") : "no inline script names document.cookie, cookieStore, indexedDB, localStorage, sessionStorage, caches or serviceWorker");
}

// Hostinger's own embed script is ruled out. Any trace of it in a page fails the run.
{
  const hits = [];
  for (const file of htmlFiles) {
    for (const m of sources[file].matchAll(REACH_SCRIPT)) hits.push(`${file}:${lineOf(sources[file], m.index)} "${m[0]}"`);
  }
  record("no reach script", hits.length ? "FAIL" : "PASS",
    hits.length ? hits.join("; ") : "no page references embed.js, cdn-reach.hostinger.com or data-reach-form");
}

// Passages marked data-unconfirmed wait on a ruling from Tee. They block deploy, not the build.
{
  const marked = htmlFiles.flatMap((f) => collected[f].unconfirmed.map((t) => `${f}: "${t}"`));
  if (!marked.length) record("unconfirmed", "PASS", "no passage is marked data-unconfirmed");
  else record("unconfirmed", "WARN", "DEPLOY BLOCKER: these wait on Tee's ruling: " + marked.join("; "));
}

record("screenshots", "INFO", `390x844 and 1280x800, light and dark, for ${htmlFiles.join(", ")}, plus the framed section at 390x844 light, dark and with JS off, and the phone fold at 393x659 after the Cc tap, in ${SHOTS}. The Reach frame in them shows the local stand-in page, not the real Hostinger form, which cannot load here`);

const width = Math.max(...results.map((r) => r.name.length));
console.log(`Checked ${htmlFiles.length} page(s) in ${DIR} with ${executablePath}`);
for (const r of results) console.log(`${r.status.padEnd(5)} ${r.name.padEnd(width)}  ${r.detail}`);
const fails = results.filter((r) => r.status === "FAIL").length;
const warns = results.filter((r) => r.status === "WARN").length;
console.log(fails ? `RESULT: FAIL, ${fails} check(s) failed, ${warns} warning(s)` : `RESULT: PASS, ${warns} warning(s)`);
process.exit(fails ? 1 : 0);
