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
  // Highest score of 1 or more wins. A tie keeps the earlier photo, which is
  // Pexels order. A photo scored 0 or not scored at all is never chosen.
  let best = 0;
  for (const x of photos) {
    const u = x && x.src ? (x.src.landscape || x.src.large2x || x.src.large) : null;
    const s = u ? scoreByUrl.get(u) : undefined;
    if (s !== undefined && s >= 1 && s > best) { best = s; jevPhoto = x; jevPick = u; }
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
const head = String(p.headline || '').trim();
const n = head.length;
const size = n <= 14 ? 104 : (n <= 24 ? 84 : 66);
const wrapAt = Math.max(8, Math.floor(700 / (size * 0.52)));

return [{ json: {
  airtableId: p.airtableId,
  headline: head,
  kicker: String(p.kicker || ''),
  photoUsed: src,
  photographer: pick ? (pick.photographer || '') : '',
  ink, accent,
  scrimColor: ink + 'D9',
  headSize: size,
  headWrap: wrapAt,
  headY: n <= 14 ? 250 : (n <= 24 ? 235 : 225),
  jevPick,
  jevApplied: JEV_APPLY
} }];
