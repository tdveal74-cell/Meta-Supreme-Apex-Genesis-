/**
 * Do the carousel rules behave?
 *
 *   node tools/carousel/carousel.test.mjs
 *
 * Runs the parser, the checks, the row plan and the templates with no browser
 * and no network. The drawing itself is exercised by the scheduled
 * carousel-render job, which runs real Chromium. The TQO case is row 4's real
 * carousel block, read from tqo_content on 2026-10-07; the NCO case is a
 * template sample written for the test.
 */

import assert from "node:assert/strict";
import { readFileSync } from "node:fs";
import { parseCarousel, splitSlide } from "./parse.mjs";
import { checkCarousel } from "./check.mjs";
import { plan } from "./render.mjs";
import { slideHtml } from "./templates.mjs";

const rows = JSON.parse(readFileSync(new URL("./fixtures/rows.json", import.meta.url), "utf8"));
const row4 = rows.TQO[0];

// The parser reads the block and stops at the blank line.
const c = parseCarousel(row4.platform_packaging);
assert.equal(c.title, "The Quiet Move Framework");
assert.equal(c.from, "P10");
assert.equal(c.slides.length, 7);
assert.equal(c.slides[6], "Quiet Move: Pick a number, verify it");
assert.equal(parseCarousel("HOOK\nnothing here"), null);
assert.deepEqual(splitSlide("Capability: It did the work on real files"), { label: "Capability", line: "It did the work on real files" });
assert.deepEqual(splitSlide("Why it matters, according to Gallup: a lot"), { label: "", line: "Why it matters, according to Gallup: a lot" });

// Row 4 passes as written: its only figures are words.
assert.deepEqual(checkCarousel(c, { show: "TQO", script: row4.script }), []);

// The checks refuse each thing the packaging prompt forbids, and a figure the script never stated.
const bad = (slides, show = "TQO", script = "") => checkCarousel({ title: "T", slides }, { show, script });
const seven = (last = "Quiet Move: do it") => ["Hook", "a: b", "c: d", "e: f", "g: h", "i: j", last];
assert.match(bad(seven().slice(0, 6)).join(), /6 slides/);
assert.match(bad(seven("Action: do it")).join(), /last slide is not the Quiet Move/);
assert.match(bad(seven("Forge Rule: do it"), "TQO").join(), /not the Quiet Move/);
assert.deepEqual(bad(seven("Forge Rule: do it"), "NCO"), []);
assert.match(bad(["one two three four five six seven eight nine ten eleven twelve thirteen", ...seven().slice(1)]).join(), /slide 1 is 13 words/);
assert.match(bad(["A hook — with a dash", ...seven().slice(1)]).join(), /slide 1 carries an em or en dash/);
assert.match(bad(["Managers lost 41% of roles", ...seven().slice(1)], "TQO", "Nothing numeric here.").join(), /slide 1 states 41%, which the script does not/);
assert.deepEqual(bad(["Managers lost 41% of roles", ...seven().slice(1)], "TQO", "Korn Ferry found 41 percent."), []);

// Only rows past Idea and not in Error are drawn; a failing carousel is refused with its reasons.
const p = plan({
  TQO: [
    row4,
    { ...row4, id: 5, status: "Idea" },
    { ...row4, id: 6, status: "Error" },
    { ...row4, id: 7, status: "Scripted", script: "", platform_packaging: row4.platform_packaging.replace("verify it", "verify it — now") },
    { id: 8, status: "Ready", platform_packaging: "no carousel" },
  ],
  NCO: rows.NCO,
});
assert.deepEqual(p.work.map((w) => `${w.show}${w.id}`), ["TQO4", "NCO0"]);
assert.deepEqual(p.refused.map((r) => `${r.show}${r.id}`), ["TQO7"]);
assert.match(p.refused[0].problems.join(), /slide 7 carries an em or en dash/);

// The templates fetch nothing, carry the face inline, and keep the pen for the last slide.
const tqo = (index) => slideHtml({ show: "TQO", title: c.title, slides: c.slides, index });
for (let i = 0; i < 7; i += 1) {
  const html = tqo(i);
  assert.ok(!/(?:src|href)=["']?https?:/i.test(html), `slide ${i + 1} fetches something`);
  assert.match(html, /font\/woff2;base64,/);
  assert.equal(/<svg/.test(html), i === 6, `the hand drawn tick belongs on the Quiet Move only (slide ${i + 1})`);
}
assert.match(tqo(0), /From<\/span><span class="v">Terrance Veal/);
assert.match(tqo(3), /4 of 7/);
assert.match(slideHtml({ show: "TQO", title: "<b>", slides: ["<script>x</script>", ...seven().slice(1)], index: 0 }), /&lt;script&gt;/);
// The NCO mark, ruled in by Tee 2026-10-07, sits on the cover and the closing
// slide only, and never on TQO.
for (let i = 0; i < 7; i++) {
  const html = slideHtml({ show: "NCO", title: "T", slides: seven("Forge Rule: do it"), index: i });
  assert.equal(/class="mark(?:cover|close)" src="data:image\/png;base64,/.test(html), i === 0 || i === 6, `NCO mark on slide ${i + 1}`);
  assert.equal(/data:image\/png/.test(tqo(i)), false, `no mark on TQO slide ${i + 1}`);
}

console.log("Carousel: every case behaves");
