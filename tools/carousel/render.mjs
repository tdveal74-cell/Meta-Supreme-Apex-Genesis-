/**
 * Draws every episode's carousel for Tee's review. Ruled by Tee 2026-10-07:
 * one carousel per episode, automatic, from our own HTML templates, delivered
 * as files for review only. Nothing here posts anywhere and nothing writes to
 * the instance: it reads the two content tables and writes PNGs to a folder.
 *
 *   node tools/carousel/render.mjs --out out/carousels
 *   node tools/carousel/render.mjs --from rows.json --out out/carousels
 *
 * Live reads need N8N_VPS_KEY (and N8N_VPS_URL, default the VPS). --from takes
 * a saved {"TQO": [rows], "NCO": [rows]} instead, which is how the tests run.
 *
 * A row is drawn when it has a CAROUSEL block in platform_packaging and its
 * status is past Idea and not Error, because a carousel is cut from a script
 * that has passed its gates. A carousel that fails check.mjs is not drawn; it
 * is listed with its reasons in summary.md. Exit 2 when the key is missing or
 * a read fails, so a scheduled run that could see nothing goes red rather than
 * reporting an empty, green day.
 */

import { mkdirSync, readFileSync, writeFileSync, existsSync } from "node:fs";
import { join } from "node:path";
import { parseCarousel } from "./parse.mjs";
import { checkCarousel } from "./check.mjs";
import { slideHtml, sheetHtml } from "./templates.mjs";

const TABLES = { TQO: "2GtmrFcTNqVMbddh", NCO: "DSH1tn4TZjzAEKxp" };
const SKIP = new Set(["", "idea", "error"]);

const args = process.argv.slice(2);
const opt = (name) => { const i = args.indexOf(name); return i >= 0 ? args[i + 1] : undefined; };
const OUT = opt("--out") || "out/carousels";

async function readTable(id) {
  const base = (process.env.N8N_VPS_URL || "https://n8n.editforge.online").replace(/\/+$/, "");
  const key = process.env.N8N_VPS_KEY;
  if (!key) throw new Error("N8N_VPS_KEY is required");
  const rows = [];
  let cursor = "";
  for (let page = 0; page < 50; page += 1) {
    const url = `${base}/api/v1/data-tables/${id}/rows?limit=100${cursor ? `&cursor=${encodeURIComponent(cursor)}` : ""}`;
    const res = await fetch(url, { headers: { "X-N8N-API-KEY": key } });
    if (!res.ok) throw new Error(`reading ${id} answered HTTP ${res.status}`);
    const body = await res.json();
    rows.push(...(body.data || []));
    if (!body.nextCursor) return rows;
    cursor = body.nextCursor;
  }
  throw new Error(`reading ${id} did not finish in 50 pages`);
}

async function loadRows() {
  const from = opt("--from");
  if (from) return JSON.parse(readFileSync(from, "utf8"));
  return { TQO: await readTable(TABLES.TQO), NCO: await readTable(TABLES.NCO) };
}

async function chromium() {
  const candidates = [process.env.PLAYWRIGHT_MODULE, "playwright"].filter(Boolean);
  let pw = null;
  for (const c of candidates) { try { pw = await import(c); break; } catch { /* next */ } }
  if (!pw) throw new Error("playwright could not be imported; set PLAYWRIGHT_MODULE");
  const binaries = [process.env.CHROMIUM_BINARY, "/opt/pw-browsers/chromium/chrome-linux/chrome"].filter((p) => p && existsSync(p));
  return (pw.chromium || pw.default.chromium).launch(binaries.length ? { executablePath: binaries[0] } : {});
}

export function plan(tables) {
  const work = [];
  const refused = [];
  for (const [show, rows] of Object.entries(tables)) {
    for (const row of rows) {
      if (SKIP.has(String(row.status || "").toLowerCase())) continue;
      const carousel = parseCarousel(row.platform_packaging);
      if (!carousel) continue;
      const problems = checkCarousel(carousel, { show, script: row.script });
      const entry = { show, id: row.id, status: row.status, title: carousel.title, slides: carousel.slides };
      (problems.length ? refused : work).push(problems.length ? { ...entry, problems } : entry);
    }
  }
  return { work, refused };
}

async function main() {
  let tables;
  try { tables = await loadRows(); } catch (e) { console.error(`refusing to report an empty day: ${e.message}`); process.exit(2); }
  const { work, refused } = plan(tables);
  mkdirSync(OUT, { recursive: true });
  const lines = [`# Carousels for review`, ``, `Drawn ${work.length}, refused ${refused.length}. Nothing here has been posted.`, ``];
  if (work.length) {
    const browser = await chromium();
    const page = await browser.newPage({ viewport: { width: 1080, height: 1350 }, deviceScaleFactor: 1 });
    for (const item of work) {
      const dir = join(OUT, `${item.show.toLowerCase()}-row${item.id}`);
      mkdirSync(dir, { recursive: true });
      const pngs = [];
      for (let i = 0; i < item.slides.length; i += 1) {
        await page.setContent(slideHtml({ ...item, index: i }), { waitUntil: "load" });
        await page.evaluate(() => document.fonts.ready);
        const png = await page.screenshot({ type: "png", clip: { x: 0, y: 0, width: 1080, height: 1350 } });
        writeFileSync(join(dir, `slide-${String(i + 1).padStart(2, "0")}.png`), png);
        pngs.push(png.toString("base64"));
      }
      const sheet = await browser.newPage({ viewport: { width: 1080, height: 800 } });
      await sheet.setContent(sheetHtml({ ...item, pngs }), { waitUntil: "load" });
      await sheet.evaluate(() => document.fonts.ready);
      writeFileSync(join(dir, "contact-sheet.png"), await sheet.screenshot({ type: "png", fullPage: true }));
      await sheet.close();
      writeFileSync(join(dir, "slides.json"), JSON.stringify(item, null, 2) + "\n");
      lines.push(`- ${item.show} row ${item.id} (${item.status}): ${item.title}, ${item.slides.length} slides, \`${dir}\``);
    }
    await browser.close();
  }
  if (refused.length) {
    lines.push(``, `## Refused, not drawn`, ``);
    for (const r of refused) lines.push(`- ${r.show} row ${r.id} (${r.status}): ${r.problems.join("; ")}`);
  }
  writeFileSync(join(OUT, "summary.md"), lines.join("\n") + "\n");
  console.log(lines.join("\n"));
}

if (import.meta.url === `file://${process.argv[1]}`) await main();
