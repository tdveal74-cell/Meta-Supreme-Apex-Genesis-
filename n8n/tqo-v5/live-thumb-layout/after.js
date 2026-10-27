// Choose the backdrop and compute the layout the compositor will draw.
//
// MERGED 2026-09-30 from the Tee-supplied n8n thumbnail packages: per-show
// brand palettes now come from the locked brand profiles in each package,
// replacing the old two-show ink/accent guess. Palettes: TQO navy #0A1628 +
// amber gold #D4A017; NCO Forge Field Charcoal #171C18 + Combat Khaki #A69F80;
// ACX Void #04090F + Signal Cyan #36D1D8 (Critic Red never on thumbnails,
// verdicts only); TSWS Void #050308 + His Sapphire #5D9DFF.
const p = $('Thumb: Plan').first().json;
const photos = ($json.photos || []);
let pick = photos.find(x => x && x.src && (x.src.landscape || x.src.large2x)) || photos[0] || null;
let src = pick ? (pick.src.landscape || pick.src.large2x || pick.src.large) : null;

// Jev scoring, ruled by Tee 2026-10-16, SHIPS IN SHADOW. Jev (TypeSafe) scores
// each candidate photo from 0 to 3 for how well it sits behind the headline: a
// dark panel covers the left 60 percent of the frame, so a photo whose subject
// sits on the right scores highest. This node always works out which photo Jev
// would choose and reports it as jevPick. It changes the photo actually used
// only when JEV_APPLY is true, and that is a ruling for Tee to flip, so it ships
// false. The scores arrive by a side branch, so $json above is still the Find
// Still output. Fail open: a Jev node that did not run, an error item, a wrong
// model, a malformed or out of range answer leaves no score for that photo, and
// with no score at all the choice above stands untouched.
const JEV_APPLY = false;
// The lowest score Jev may prefer or pick a photo at: 2, the level that reads
// "fits the subject". A Jev score is a probability weighted mean of the level
// numbers, so it falls between levels, and a picture Jev is sure is only "usable,
// but about something other than the subject" scores 1, below this floor.
const JEV_FLOOR = 2;
let jevPhoto = null;
let jevPick = null;
try {
  // The question p{k} was asked about urls[k-1]. Scores are kept by that url, so
  // a photo is matched on the url Pick Still would use, not on its position.
  const urls = $('Jev: Thumb Body').first().json.urls;
  const answers = {};
  for (const item of $('Jev: Rank Stills').all()) {
    const r = item && item.json;
    if (!r || typeof r.model !== 'string' || !r.model.startsWith('jev-')) continue;
    if (!r.answers || typeof r.answers !== 'object') continue;
    for (const name of Object.keys(r.answers)) if (!(name in answers)) answers[name] = r.answers[name];
  }
  const scoreByUrl = new Map();
  if (Array.isArray(urls)) {
    urls.forEach((u, i) => {
      const a = answers['p' + (i + 1)];
      const ok = typeof u === 'string' && a && a.type === 'score' && typeof a.score === 'number' && Number.isFinite(a.score) && a.score >= 0 && a.score <= 3;
      if (ok && !scoreByUrl.has(u)) scoreByUrl.set(u, a.score);
    });
  }
  // Highest score of JEV_FLOOR or more wins. A tie keeps the earlier photo, which
  // is Pexels order. A photo scored under JEV_FLOOR or not scored at all is never
  // chosen.
  let best = 0;
  for (const x of photos) {
    const u = x && x.src ? (x.src.landscape || x.src.large2x || x.src.large) : null;
    const s = u ? scoreByUrl.get(u) : undefined;
    if (s !== undefined && s >= JEV_FLOOR && s > best) { best = s; jevPhoto = x; jevPick = u; }
  }
} catch (e) { jevPhoto = null; jevPick = null; }
if (JEV_APPLY && jevPhoto) { pick = jevPhoto; src = jevPick; }

// Brand palettes, one entry per show, from the locked package profiles.
const SHOW = String(p.show || (p.isNCO ? 'NCO' : 'TQO')).toUpperCase();
const BRAND = {
  TQO:  { ink: '#0A1628', accent: '#D4A017' },
  NCO:  { ink: '#171C18', accent: '#A69F80' },
  ACX:  { ink: '#04090F', accent: '#36D1D8' },
  TSWS: { ink: '#050308', accent: '#5D9DFF' },
}[SHOW] || { ink: '#06080F', accent: '#C8A44D' };

const ink    = BRAND.ink;
const accent = BRAND.accent;

// Type scale. The headline sets in one of three sizes so a long headline stays
// inside the scrim instead of running over the photograph.
//
// FIXED 2026-10-27, ruled by Tee on a card, "Fix both, prove first". The wrap
// used to assume 0.52 em a character. Thumb: Compose draws in Arial, the Edit
// Image node's default font, whose capitals run about 0.66 em, so a full line
// ran about 100 px past the panel: harness execution 4737 drew "DASHBOARD FIRST"
// out to x 866 with the panel ending at x 760. The wrap is now worked out from
// Arial's advance widths, using the same word wrap Compose applies to
// lineLength, so every line of the headline fits TEXT_BUDGET. A word too wide to
// fit at a size steps the size down, and so does a block too tall for the frame.
const head = String(p.headline || '').trim();
const n = head.length;
// Arial advance widths in thousandths of an em. A character not listed counts
// as a full em, so an unexpected glyph can only make the wrap tighter.
const ARIAL = {
  ' ': 278, '!': 278, '"': 355, '#': 556, '$': 556, '%': 889, '&': 667, "'": 191,
  '(': 333, ')': 333, '*': 389, '+': 584, ',': 278, '-': 333, '.': 278, '/': 278,
  '0': 556, '1': 556, '2': 556, '3': 556, '4': 556, '5': 556, '6': 556, '7': 556,
  '8': 556, '9': 556, ':': 278, ';': 278, '<': 584, '=': 584, '>': 584, '?': 556,
  '@': 1015, A: 667, B: 667, C: 722, D: 722, E: 667, F: 611, G: 778, H: 722,
  I: 278, J: 500, K: 667, L: 556, M: 833, N: 722, O: 778, P: 667, Q: 778, R: 722,
  S: 667, T: 611, U: 722, V: 667, W: 944, X: 667, Y: 667, Z: 611, '[': 278,
  ']': 278, _: 556, a: 556, b: 556, c: 500, d: 556, e: 556, f: 278, g: 556,
  h: 556, i: 222, j: 222, k: 500, l: 222, m: 833, n: 556, o: 556, p: 556, q: 556,
  r: 333, s: 500, t: 278, u: 556, v: 500, w: 722, x: 500, y: 500, z: 500,
  '’': 222, '‘': 222, '“': 333, '”': 333,
};
// The headline is drawn from x 72 and the panel ends at x 760, so 680 px keeps
// the widest line about 8 px inside the panel.
const TEXT_BUDGET = 680;
const widthOf = (s, px) => [...s].reduce((w, ch) => w + (ARIAL[ch] || 1000), 0) * px / 1000;
// Compose's own wrap (n8n Edit Image, text operation): a word goes to a new line
// when the line, a space and the word would pass lineLength characters.
const wrapLines = (text, len) => {
  const lines = [];
  let line = '';
  for (const word of text.split(' ')) {
    if (line.length + word.length + 1 > len) { lines.push(line.trim()); line = word + ' '; }
    else line += word + ' ';
  }
  lines.push(line.trim());
  return lines;
};
// A lineLength shorter than a word makes Compose start with an empty line, so
// the search never goes below the longest word plus one.
const SIZES = [104, 84, 66, 54];
const TOP = { 104: 250, 84: 235, 66: 225, 54: 220 };
const FLOOR_Y = 680;
const minLen = Math.max(8, ...head.split(' ').map(w => w.length + 1));
let size = SIZES[SIZES.length - 1];
let wrapAt = minLen;
for (const px of SIZES.slice(n <= 14 ? 0 : (n <= 24 ? 1 : 2))) {
  let found = 0;
  for (let len = Math.max(40, minLen); len >= minLen && !found; len--) {
    const lines = wrapLines(head, len);
    const tall = TOP[px] + lines.length * px * 1.2 > FLOOR_Y;
    if (!tall && lines.every(l => widthOf(l, px) <= TEXT_BUDGET)) found = len;
  }
  if (found) { size = px; wrapAt = found; break; }
}

return [{ json: {
  airtableId: p.airtableId,
  headline: head,
  kicker: String(p.kicker || ''),
  photoUsed: src,
  photographer: pick ? (pick.photographer || '') : '',
  ink, accent,
  // GraphicsMagick reads the last pair of an 8 digit colour as transparency, not
  // as alpha: 'D9' drew the panel 85% clear (measured 0.15 opaque in execution
  // 4737). '26' is 15% clear, the 85% opaque panel the design meant. Fixed
  // 2026-10-27 on the same card as the wrap.
  scrimColor: ink + '26',
  headSize: size,
  headWrap: wrapAt,
  headY: TOP[size],
  jevPick,
  jevApplied: JEV_APPLY
} }];
