// Jev: Thumb Body. Builds the one TypeSafe request that asks Jev to score the
// candidate photos for a thumbnail, ruled by Tee 2026-10-16, SHIPS IN SHADOW.
// Its output item feeds Jev: Rank Stills, which posts json.body as it stands.
//
// The question asked of each photo is how well it works as the picture behind a
// thumbnail headline when a dark panel covers the left 60 percent of the frame,
// because that is what Thumb: Compose does. Scores run 0 to 3 and each level
// describes one situation on its own, because the model judges every level
// separately and never sees its number or its neighbours. A 0 is unusable: dark,
// cluttered, blurred, or carrying text or a watermark. A 1 is usable but about
// something other than the subject. A 2 fits the subject, but what matters sits
// on the left 60 percent of the frame, under the dark panel. A 3 fits the
// subject, and what matters sits in the right part of the frame, where it stays
// visible. A score comes back as a probability weighted mean of the level
// numbers, so it can fall between levels. Thumb: Pick Still reads the answers
// and reports the photo Jev would choose, and it uses that photo only once its
// own JEV_APPLY is true, so today's choice stands until then.
//
// Input is the Extract From File output, one item per fetched still with the
// image in json.still_b64, in the same order as Jev: Thumb Stills. The two are
// paired by position, so unequal lengths mean something dropped out between
// them and the pairing cannot be trusted. Only PNG and JPEG are accepted, found
// by the base64 prefix, and anything else is skipped. Question p{k} refers to
// its photo by the placeholder <p{k}>, and every asset must be referenced, so
// each asset key appears in its own question.
//
// Size check. TypeSafe rejects an image under 280 or over 1568 pixels on either
// side, and one rejected image fails the whole request with no partial answers.
// The total pixel range in its docs, 78,400 to 2,458,624, is the area of a 280 by
// 280 and a 1568 by 1568 square, so the side check already covers it. The size is
// read from the first 65,536 base64 characters only, by hand, with no Buffer and
// no atob, so it works whatever globals the Code sandbox has. A PNG gives it in
// IHDR and a JPEG in the first SOF marker. A still whose size is read and is out
// of limits is skipped like any other unusable still. A still whose size cannot
// be read, because the header is odd or the SOF sits past that window, is kept,
// so the check fails open to what this node did before it existed.
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
  'Unusable: dark, cluttered, blurred, or carrying text or a watermark',
  'Usable, but about something other than the subject',
  'Fits the subject, but what matters sits on the left 60 percent of the frame, under the dark panel',
  'Fits the subject, and what matters sits in the right part of the frame, where it stays visible',
];
const formatOf = (b64) => (b64.startsWith('/9j/') ? 'jpeg' : (b64.startsWith('iVBORw0KGgo') ? 'png' : null));
const MIN_SIDE = 280;
const MAX_SIDE = 1568;
const HEAD_CHARS = 65536;
const B64 = 'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/';
// The leading bytes of a base64 string as plain numbers. It stops at the first
// character that is not in the standard alphabet, which is the '=' padding.
const headBytes = (b64) => {
  const s = b64.slice(0, HEAD_CHARS);
  const out = [];
  let acc = 0;
  let bits = 0;
  for (let i = 0; i < s.length; i++) {
    const v = B64.indexOf(s.charAt(i));
    if (v < 0) break;
    acc = ((acc << 6) | v) & 0xffff;
    bits += 6;
    if (bits >= 8) { bits -= 8; out.push((acc >> bits) & 255); }
  }
  return out;
};
const be16 = (b, i) => b[i] * 256 + b[i + 1];
const be32 = (b, i) => b[i] * 16777216 + b[i + 1] * 65536 + b[i + 2] * 256 + b[i + 3];
// PNG: the signature, then IHDR as the first chunk, 13 bytes long, width and
// height as 32 bit big endian numbers.
const pngSize = (b) => {
  if (b.length < 24 || be32(b, 8) !== 13) return null;
  if (b[12] !== 0x49 || b[13] !== 0x48 || b[14] !== 0x44 || b[15] !== 0x52) return null;
  const w = be32(b, 16);
  const h = be32(b, 20);
  return w > 0 && h > 0 ? { w, h } : null;
};
// JPEG: walk the segments by their length, so a thumbnail embedded in an APP
// segment is skipped whole, and read the first SOF marker (0xC0 to 0xCF except
// 0xC4, 0xC8 and 0xCC). Reaching the scan or the end first, or a byte that is
// not a marker, means the size cannot be read. A height of 0 is defined later by
// a DNL segment, so that is unreadable too.
const jpegSize = (b) => {
  let i = 2;
  while (i + 3 < b.length) {
    if (b[i] !== 0xff) return null;
    const m = b[i + 1];
    if (m === 0xff) { i += 1; continue; }
    if (m === 0x00 || m === 0xd9 || m === 0xda) return null;
    if (m === 0x01 || (m >= 0xd0 && m <= 0xd8)) { i += 2; continue; }
    const len = be16(b, i + 2);
    if (m >= 0xc0 && m <= 0xcf && m !== 0xc4 && m !== 0xc8 && m !== 0xcc) {
      if (len < 8 || i + 8 >= b.length) return null;
      const h = be16(b, i + 5);
      const w = be16(b, i + 7);
      return w > 0 && h > 0 ? { w, h } : null;
    }
    if (len < 2) return null;
    i += 2 + len;
  }
  return null;
};
const sizeOf = (b64, format) => {
  const b = headBytes(b64);
  return format === 'png' ? pngSize(b) : jpegSize(b);
};
const outOfLimits = (d) => d.w < MIN_SIDE || d.h < MIN_SIDE || d.w > MAX_SIDE || d.h > MAX_SIDE;
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
    const dim = sizeOf(b64, format);
    if (dim && outOfLimits(dim)) continue;
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
