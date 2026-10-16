// Jev: B-Roll Bodies, ruled by Tee 2026-10-16. Builds one TypeSafe request per
// b-roll segment that has at least one usable still, asking Jev how well each
// still works on screen while the narrator speaks that segment's sentence. It
// decides which stills go into a request and what is asked of them; the HTTP
// node after it sends the request and Build Movie reads the answers. The branch
// runs in shadow and never changes which clip Build Movie picks.
//
// Input is the Extract From File output, one item per still, in the order of
// the items from Jev: B-Roll Stills. The two are paired by position, so unequal
// lengths mean the pairing cannot be trusted and nothing is emitted. A Code node
// cannot read binary in separate mode, which is why the bytes arrive here as
// base64 in still_b64.
//
// A still is usable when its still_b64 is a non-empty string that starts like a
// JPEG or a PNG. TypeSafe accepts only those two, so a GIF, a WebP, an HTML
// error page fetched in place of an image and an error item are all skipped.
//
// k counts the usable stills of a segment from 1, not the cand numbers from the
// stills node. Build Movie scores links[k-1] from the answer to s{segIndex}c{k},
// so the two must line up even when an earlier cand was skipped.
//
// One request body is capped at MAX_B64 base64 characters. Stills are in Pexels
// order, so when the cap bites the later ones, which Pexels ranked lowest, are
// dropped and the earlier ones stay.
//
// Fails open: any missing node, missing field or odd value gives that segment,
// or the whole node, no output, and the movie is built as it is today. Nothing
// here throws.
const MAX_B64 = 20000000;
const CRITERIA = [
  'Unusable as b-roll: mostly black or blank, blurred, carrying a watermark, a logo or large text, or showing something unrelated to the sentence',
  'A clean, usable shot that does not relate to the sentence',
  'Fits the general topic of the sentence',
  'Clearly shows what the sentence describes'
];

// TypeSafe reads the format from us, so it is taken from the first bytes: every
// JPEG base64 starts /9j/ and every PNG starts iVBORw0KGgo.
const formatOf = (b64) => {
  if (typeof b64 !== 'string') return null;
  if (b64.startsWith('/9j/')) return 'jpeg';
  if (b64.startsWith('iVBORw0KGgo')) return 'png';
  return null;
};

try {
  const stills = $('Jev: B-Roll Stills').all();
  const fetched = $input.all();
  // Unequal lengths: an item was dropped somewhere, so position no longer says
  // which still belongs to which segment.
  if (stills.length !== fetched.length) return [];
  const segs = $('Plan B-Roll Segments').all();

  // Usable stills grouped by segment, in segment order and then Pexels order.
  const bySeg = new Map();
  for (let n = 0; n < stills.length; n++) {
    const s = (stills[n] && stills[n].json) || {};
    const b64 = fetched[n] && fetched[n].json && fetched[n].json.still_b64;
    const format = formatOf(b64);
    if (!format || typeof s.link !== 'string' || !s.link) continue;
    if (!Number.isInteger(s.segIndex) || s.segIndex < 0) continue;
    if (!bySeg.has(s.segIndex)) bySeg.set(s.segIndex, []);
    bySeg.get(s.segIndex).push({ link: s.link, format, b64 });
  }

  const out = [];
  for (const [segIndex, usable] of bySeg) {
    // Plan B-Roll Segments sets segIndex to the item's own position, and Build
    // Movie reads it by that position, so the sentence is read the same way.
    const narration = segs[segIndex] && segs[segIndex].json && segs[segIndex].json.narration;
    if (typeof narration !== 'string' || !narration.trim()) continue;

    const links = [];
    const questions = {};
    const assets = {};
    let total = 0;
    for (const u of usable) {
      if (total + u.b64.length > MAX_B64) break;
      total += u.b64.length;
      links.push(u.link);
      const name = 's' + segIndex + 'c' + links.length;
      questions[name] = {
        type: 'score',
        instructions: 'How well does <' + name + '> work as b-roll on screen while a narrator says the sentence in `sentence`?',
        criteria: CRITERIA.slice()
      };
      assets['<' + name + '>'] = { type: 'image', format: u.format, data_base64: u.b64 };
    }
    if (!links.length) continue;

    out.push({ json: { segIndex, links, body: { model: 'jev-latest', state: { sentence: narration }, questions, assets } } });
  }
  return out;
} catch (e) { return []; }
