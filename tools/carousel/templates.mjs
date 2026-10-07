/**
 * The two slide templates, 1080 by 1350 (4:5, the shape LinkedIn and
 * Instagram both show in full).
 *
 * TQO follows sites/tqohq/DESIGN.md, the recorded design system: an interoffice
 * memo in navy ink on white bond, labels beside values never above, flat with
 * no shadow or card, one face, and pen blue only where a person checks
 * something, which here is the hand drawn tick on the Quiet Move.
 *
 * NCO Forge has no recorded design system in this repository. Its template is
 * a first draft for Tee's eye, a field note on manila with one forge colour on
 * the Forge Rule, and it says so in tools/carousel/README.md. It is not a
 * brand claim.
 *
 * The face is Atkinson Hyperlegible Next, read from the site's own self hosted
 * copy and embedded as a data URI, so a render never fetches anything.
 */

import { readFileSync } from "node:fs";
import { splitSlide } from "./parse.mjs";

const FONT = readFileSync(new URL("../../sites/tqohq/fonts/atkinson-hyperlegible-next-latin.woff2", import.meta.url)).toString("base64");

const esc = (t) => String(t).replace(/&/g, "&amp;").replace(/</g, "&lt;").replace(/>/g, "&gt;").replace(/"/g, "&quot;");

const THEMES = {
  TQO: {
    show: "The Quiet Operator", kind: "Memo", closer: "The quiet move",
    paper: "#ffffff", ink: "#0a1628", ink2: "#4b5870", rule: "#d3d8e1", mark: "#1f3fa6",
    headRule: "border-top:3px solid var(--ink);border-bottom:1px solid var(--ink);height:4px;",
  },
  NCO: {
    show: "NCO Forge", kind: "Field note", closer: "Forge rule",
    paper: "#efeadf", ink: "#1d2217", ink2: "#565b4b", rule: "#c9c2ad", mark: "#8a3412",
    headRule: "border-top:6px solid var(--ink);height:0;",
  },
};

function frame(theme, body) {
  return `<!doctype html><html><head><meta charset="utf-8"><style>
@font-face{font-family:"AHN";src:url(data:font/woff2;base64,${FONT}) format("woff2");font-weight:200 800;}
:root{--paper:${theme.paper};--ink:${theme.ink};--ink2:${theme.ink2};--rule:${theme.rule};--mark:${theme.mark};}
*{box-sizing:border-box;margin:0;padding:0}
html,body{width:1080px;height:1350px;background:var(--paper);color:var(--ink);font-family:"AHN",sans-serif;font-variant-numeric:tabular-nums;}
.page{width:1080px;height:1350px;padding:88px 96px 80px;display:flex;flex-direction:column;}
.head{display:flex;justify-content:space-between;align-items:baseline;font-size:30px;}
.show{font-weight:680;letter-spacing:-0.005em}.kind{font-weight:560;color:var(--ink2)}
.headrule{margin-top:22px;${theme.headRule}}
.row{display:grid;grid-template-columns:150px 1fr;column-gap:24px;align-items:baseline;margin-top:26px;font-size:30px;}
.row .l{font-weight:560;color:var(--ink2)}.row .v{font-weight:450}
.re{font-size:46px;font-weight:450;line-height:1.12;letter-spacing:-0.018em;text-wrap:balance}
.main{flex:1;display:flex;flex-direction:column;justify-content:center;}
.hook{font-size:104px;font-weight:380;line-height:1.06;letter-spacing:-0.026em;text-wrap:balance}
.item{display:grid;grid-template-columns:150px 1fr;column-gap:24px;align-items:baseline;}
.item .l{font-size:32px;font-weight:560;color:var(--ink2);line-height:1.3}
.item .v{font-size:90px;font-weight:380;line-height:1.08;letter-spacing:-0.024em;text-wrap:balance}
.item .lab{font-size:34px;font-weight:600;color:var(--ink2);margin-bottom:22px}
.close{display:grid;grid-template-columns:150px 1fr;column-gap:24px;align-items:start;}
.tick{width:96px;height:96px;border:3px solid var(--ink);border-radius:2px;position:relative;margin-top:8px}
.tick svg{position:absolute;left:8px;top:-34px;width:136px;height:126px;overflow:visible}
.forge{width:96px;height:96px;background:var(--mark);margin-top:8px}
.close .lab{font-size:34px;font-weight:600;color:var(--ink2);margin-bottom:18px}
.close .v{font-size:90px;font-weight:600;line-height:1.08;letter-spacing:-0.022em;text-wrap:balance}
.foot{display:flex;justify-content:space-between;align-items:baseline;border-top:1px solid var(--rule);padding-top:22px;font-size:28px;font-weight:560;color:var(--ink2)}
.foot .t{max-width:720px;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
</style></head><body><div class="page">${body}</div></body></html>`;
}

const TICK = `<svg viewBox="0 0 104 96"><path d="M8 58 L36 84 L98 6" fill="none" stroke="var(--mark)" stroke-width="9" stroke-linecap="round" stroke-linejoin="round"/></svg>`;

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
<div class="main"><div class="hook">${esc(line)}</div></div>`;
  } else if (index === total - 1) {
    const box = show === "NCO" ? `<div class="forge"></div>` : `<div class="tick">${TICK}</div>`;
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
@font-face{font-family:"AHN";src:url(data:font/woff2;base64,${FONT}) format("woff2");font-weight:200 800;}
*{margin:0;padding:0;box-sizing:border-box}body{width:1080px;background:#f1f3f7;font-family:"AHN",sans-serif;color:#0a1628;padding:32px}
h1{font-size:28px;font-weight:600;margin-bottom:20px}.g{display:grid;grid-template-columns:repeat(3,1fr);gap:16px}
figure{background:#fff;border:1px solid #d3d8e1}img{width:100%;display:block}figcaption{font-size:20px;padding:6px 10px;color:#4b5870}
</style></head><body><h1>${esc(theme.show)}: ${esc(title)}</h1><div class="g">${cells}</div></body></html>`;
}
