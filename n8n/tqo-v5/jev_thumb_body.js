// Jev: Thumb Body. Builds the one TypeSafe request that asks Jev to score the
// candidate photos for a thumbnail, ruled by Tee 2026-10-16, SHIPS IN SHADOW.
// Its output item feeds Jev: Rank Stills, which posts json.body as it stands.
//
// The question asked of each photo is how well it works as the picture behind a
// thumbnail headline when a dark panel covers the left 60 percent of the frame,
// because that is what Thumb: Compose does. Scores run 0 to 3. A 3 means what
// matters in the photo sits in the right part of the frame, where it stays
// visible. A photo whose subject sits under the panel scores 2, one unrelated to
// the subject scores 1, and an unusable photo scores 0. Thumb: Pick Still reads
// the answers and reports the photo Jev would choose, and it uses that photo
// only once its own JEV_APPLY is true, so today's choice stands until then.
//
// Input is the Extract From File output, one item per fetched still with the
// image in json.still_b64, in the same order as Jev: Thumb Stills. The two are
// paired by position, so unequal lengths mean something dropped out between
// them and the pairing cannot be trusted. Only PNG and JPEG are accepted, found
// by the base64 prefix, and anything else is skipped. Question p{k} refers to
// its photo by the placeholder <p{k}>, and every asset must be referenced, so
// each asset key appears in its own question.
//
// urls[k-1] is the url the question p{k} was about, null where no question was
// asked, so Pick Still can match a score to a photo by url.
//
// Fail open: a missing node, a length mismatch, no readable image or no subject
// or headline returns [], the branch stops, and the thumbnail is chosen as it is
// today. One request body is held under 20,000,000 characters of base64, and
// the later photos, the lower ranked in Pexels order, are dropped beyond that.
// This node never throws.
const BODY_CAP = 20000000;
const CRITERIA = [
  'Unusable: dark, cluttered, blurred, carrying text or a watermark, or unrelated to the subject',
  'Usable but unrelated to the subject',
  'Fits the subject, but what matters sits under the dark panel on the left',
  'Fits the subject, and what matters sits in the right part of the frame where it stays visible',
];
const formatOf = (b64) => (b64.startsWith('/9j/') ? 'jpeg' : (b64.startsWith('iVBORw0KGgo') ? 'png' : null));
try {
  const files = $input.all();
  const stills = $('Jev: Thumb Stills').all();
  if (!files.length || files.length !== stills.length) return [];
  const plan = $('Thumb: Plan').first().json;
  const subject = String(plan.queryRaw || '').trim();
  const headline = String(plan.headline || '').trim();
  if (!subject || !headline) return [];
  const questions = {};
  const assets = {};
  const urls = [];
  let size = 0;
  for (let i = 0; i < files.length; i++) {
    const meta = stills[i] && stills[i].json;
    const b64 = files[i] && files[i].json && files[i].json.still_b64;
    const k = meta && meta.k;
    if (!Number.isInteger(k) || k < 1 || typeof meta.url !== 'string') continue;
    if (typeof b64 !== 'string' || !b64) continue;
    const format = formatOf(b64);
    if (!format) continue;
    if (size + b64.length > BODY_CAP) break;
    size += b64.length;
    const ref = 'p' + k;
    questions[ref] = {
      type: 'score',
      instructions: 'How well does <' + ref + '> work as the photograph behind a YouTube thumbnail about `subject`, where a dark panel covers its left 60 percent and `headline` sits on that panel?',
      criteria: CRITERIA.slice(),
    };
    assets['<' + ref + '>'] = { type: 'image', format, data_base64: b64 };
    while (urls.length < k) urls.push(null);
    urls[k - 1] = meta.url;
  }
  if (!Object.keys(questions).length) return [];
  return [{ json: { urls, body: { model: 'jev-latest', state: { subject, headline }, questions, assets } } }];
} catch (e) { return []; }
