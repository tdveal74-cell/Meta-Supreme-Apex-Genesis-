/**
 * The two slide templates, 1080 by 1350 (4:5, the shape LinkedIn and
 * Instagram both show in full).
 *
 * TQO follows its brand package v2 (TQO_Brand_Package_v2, revision
 * 2026-09-30, handed over by Tee 2026-10-11 and ruled in on a card the same
 * day): deep navy #0A1628 as the ground, Amber Gold #D4A017 for the wordmark,
 * labels and mark, the package's proposed warm off-white #F4F0E8 for text, and
 * Inter Bold. The mark is "The Denominator", a fraction bar over one dot, drawn
 * here as vector so its gold is the exact hex rather than a generated pixel; it
 * sits on the cover and on the closing slide. The memo layout of
 * sites/tqohq/DESIGN.md (labels beside values, flat, no card) is kept.
 *
 * NCO Forge follows its brand package v1 (Drive, NCO_BRAND_brand-package_v1,
 * 2026-08-03, read through its 2026-09-24 text extract): Deep Navy #0A1628 as
 * the ground, Gold #C5A46E for accents and highlights, Olive #3D4F2F for depth,
 * a bold sans serif from its recommended list (Inter), and the NCO FORGE
 * wordmark set in type. The mark, a shield with an anvil and a star in the
 * package's gold and olive, is brand/nco-mark.png: Tee generated it from a
 * prompt on 2026-10-07 and ruled it in on a card the same day. Its olive field
 * had four holes punched through by background removal; they were filled with
 * the field's own colour. It sits on the cover and the closing slide only. NCO
 * stays on v1 by Tee's ruling of 2026-10-11: its v2 package marks its gold and
 * olive as proposals and its anvil and chevron emblem is not the ruled mark.
 *
 * Every face is embedded as a data URI, Inter from tools/carousel/fonts, so a
 * render never fetches anything.
 */

import { readFileSync } from "node:fs";
import { splitSlide } from "./parse.mjs";

const b64 = (path) => readFileSync(new URL(path, import.meta.url)).toString("base64");
const INTER = [["regular", 400], ["semibold", 600], ["bold", 700], ["extrabold", 800]]
  .map(([file, weight]) => `@font-face{font-family:"F";src:url(data:font/woff2;base64,${b64(`./fonts/inter-${file}.woff2`)}) format("woff2");font-weight:${weight};}`)
  .join("");

const NCO_MARK = `data:image/png;base64,${b64("./brand/nco-mark.png")}`;
// The Denominator: bar and dot in the proportions of the package's
// Profile_Denominator_Emblem.png (bar 222 by 29, dot 40 across, 30 between).
const TQO_MARK = (cls) => `<svg class="${cls}" viewBox="0 0 222 99" role="img" aria-label=""><rect x="0" y="0" width="222" height="29" fill="#d4a017"/><circle cx="111" cy="79" r="20" fill="#d4a017"/></svg>`;

const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const THEMES = {
  TQO: {
    show: "THE QUIET OPERATOR", kind: "Memo", closer: "The quiet move", faces: INTER,
    paper: "#0a1628", ink: "#f4f0e8", ink2: "#d4a017", rule: "rgba(212,160,23,0.35)", mark: "#d4a017", brand: "#d4a017",
    headRule: "border-top:3px solid var(--brand);height:0;",
    showCss: "font-weight:700;letter-spacing:0.08em",
    w: { body: 400, hook: 700, line: 700, close: 700, label: 600 },
  },
  NCO: {
    show: "NCO FORGE", kind: "", closer: "Forge rule", faces: INTER,
    paper: "#0a1628", ink: "#f4f1ea", ink2: "#c5a46e", rule: "#3d4f2f", mark: "#c5a46e", brand: "#c5a46e",
    headRule: "border-top:8px solid #3d4f2f;height:0;",
    showCss: "font-weight:800;letter-spacing:0.14em",
    w: { body: 600, hook: 700, line: 700, close: 800, label: 600 },
  },
};

function frame(theme, body) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>
${theme.faces}
:root{--brand:${theme.brand};--paper:${theme.paper};--ink:${theme.ink};--ink2:${theme.ink2};--rule:${theme.rule};--mark:${theme.mark};}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px;background:var(--paper);color:var(--ink);font-family:"F",sans-serif;font-variant-numeric:tabular-nums;}
.page{width:1080px;height:1350px;padding:88px 96px 80px;display:flex;flex-direction:column;}
.head{display:flex;justify-content:space-between;align-items:baseline;font-size:30px;}
.show{${theme.showCss};color:var(--brand)}.kind{font-weight:${theme.w.label};color:var(--ink2)}
.headrule{margin-top:22px;${theme.headRule}}
.row{display:grid;grid-template-columns:150px 1fr;column-gap:24px;align-items:baseline;margin-top:26px;font-size:30px;}
.row .l{font-weight:${theme.w.label};color:var(--ink2)}.row .v{font-weight:${theme.w.body}}
.re{font-size:46px;font-weight:${theme.w.body};line-height:1.12;letter-spacing:-0.018em;text-wrap:balance}
.main{flex:1;display:flex;flex-direction:column;justify-content:center;}
.hook{font-size:104px;font-weight:${theme.w.hook};line-height:1.06;letter-spacing:-0.026em;text-wrap:balance}
.item{display:grid;grid-template-columns:150px 1fr;column-gap:24px;align-items:baseline;}
.item .l{font-size:32px;font-weight:${theme.w.label};color:var(--ink2);line-height:1.3}
.item .v{font-size:90px;font-weight:${theme.w.line};line-height:1.08;letter-spacing:-0.024em;text-wrap:balance}
.item .lab{font-size:34px;font-weight:${theme.w.label};color:var(--ink2);margin-bottom:22px}
.close{display:grid;grid-template-columns:150px 1fr;column-gap:24px;align-items:start;}
.forge{width:96px;height:96px;background:var(--mark);margin-top:8px}
.markclose{width:120px;height:auto;margin-top:4px}
.markcover{width:150px;height:auto;margin-bottom:44px}
svg.markcover{width:180px}svg.markclose{width:120px;margin-top:30px}
.close .lab{font-size:34px;font-weight:${theme.w.label};color:var(--ink2);margin-bottom:18px}
.close .v{font-size:90px;font-weight:${theme.w.close};line-height:1.08;letter-spacing:-0.022em;text-wrap:balance}
.foot{display:flex;justify-content:space-between;align-items:baseline;border-top:1px solid var(--rule);padding-top:22px;font-size:28px;font-weight:${theme.w.label};color:var(--ink2)}
.foot .t{max-width:720px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
</style></head><body><div class="page">${body}</div></body></html>`;
}


/** One slide as a complete HTML document. index is 0 based. */
export function slideHtml({ show, title, slides, index }) {
  const theme = THEMES[show === "NCO" ? "NCO" : "TQO"];
  const total = slides.length;
  const head = `<div class="head"><span class="show">${esc(theme.show)}</span><span class="kind">${esc(theme.kind)}</span></div><div class="headrule"></div>`;
  const foot = `<div class="foot"><span class="t">Re: ${esc(title)}</span><span>${index + 1} of ${total}</span></div>`;
  const { label, line } = splitSlide(slides[index]);
  let main;
  if (index === 0) {
    main = `<div class="row"><span class="l">From</span><span class="v">Terrance Veal</span></div>
<div class="row"><span class="l">Re</span><span class="v re">${esc(title)}</span></div>
<div class="main">${show === "NCO" ? `<img class="markcover" src="${NCO_MARK}" alt="">` : TQO_MARK("markcover")}<div class="hook">${esc(line)}</div></div>`;
  } else if (index === total - 1) {
    const box = show === "NCO" ? `<img class="markclose" src="${NCO_MARK}" alt="">` : TQO_MARK("markclose");
    main = `<div class="main"><div class="close">${box}<div><div class="lab">${esc(theme.closer)}</div><div class="v">${esc(line)}</div></div></div></div>`;
  } else {
    main = `<div class="main"><div class="item"><span class="l">${index + 1}</span><div>${label ? `<div class="lab">${esc(label)}</div>` : ""}<div class="v">${esc(line)}</div></div></div></div>`;
  }
  return frame(theme, head + main + foot);
}

/** A contact sheet of every slide for one look on a phone, three across. */
export function sheetHtml({ show, title, pngs }) {
  const theme = THEMES[show === "NCO" ? "NCO" : "TQO"];
  const cells = pngs.map((b64, i) => `<figure><img src="data:image/png;base64,${b64}"><figcaption>${i + 1}</figcaption></figure>`).join("");
  return `<!doctype html><html><head><meta charset="utf-8"><style>
${INTER}
*{margin:0;padding:0;box-sizing:border-box}body{width:1080px;background:#f1f3f7;font-family:"F",sans-serif;color:#0a1628;padding:32px}
h1{font-size:28px;font-weight:600;margin-bottom:20px}.g{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
figure{background:#fff;border:1px solid #d3d8e1}img{width:100%;display:block}figcaption{font-size:20px;padding:6px 10px;color:#4b5870}
</style></head><body><h1>${esc(theme.show)}: ${esc(title)}</h1><div class="g">${cells}</div></body></html>`;
}
