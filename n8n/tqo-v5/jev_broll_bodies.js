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
// A still whose width and height can be read from its first bytes and fall
// outside TypeSafe's limits is skipped too: it would be rejected, never resized,
// and one rejected image fails the whole request for the segment. A still whose
// size cannot be read is kept, so the check fails open to what this node did
// before it existed.
//
// The four score levels are told apart so that each one means one thing, and
// TypeSafe judges each on its own without its number or its neighbours. Level 0
// is a picture that cannot be used as b-roll at all (black or blank, blurred, a
// watermark, a logo or large text), and says nothing about the sentence. Level 1
// is a clean shot about something other than the sentence, level 2 a clean shot
// that fits the general topic, and level 3 a clean shot that clearly shows what
// the sentence describes. The score that comes back is a probability weighted
// mean of the level numbers, so it falls between levels. Level 2 is the first
// that says the picture fits the sentence.
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
  'Unusable as b-roll: mostly black or blank, blurred, or carrying a watermark, a logo or large text',
  'A clean, usable shot about something other than the sentence',
  'A clean shot that fits the general topic of the sentence',
  'A clean shot that clearly shows what the sentence describes'
];

// TypeSafe rejects an image under 280 or over 1568 pixels on either side, or
// outside 78,400 to 2,458,624 pixels in all, and the ends of each range are in
// (docs.typesafe.ai/images, Limits). Given the side limits the area limits
// follow, and both are kept so the numbers read as the page has them.
const MIN_SIDE = 280;
const MAX_SIDE = 1568;
const MIN_PIXELS = 78400;
const MAX_PIXELS = 2458624;
// Only the head of a still is decoded: a PNG keeps its size in its first 24
// bytes and a JPEG keeps it in the first frame header. 65,536 base64 characters
// are 49,152 bytes. Plain loops and arrays only, with no Buffer and no atob, so
// this runs whatever globals the Code node sandbox has.
const HEAD_CHARS = 65536;
const B64_VALUE = [];
'ABCDEFGHIJKLMNOPQRSTUVWXYZabcdefghijklmnopqrstuvwxyz0123456789+/'.split('').forEach((ch, n) => { B64_VALUE[ch.charCodeAt(0)] = n; });

// The first bytes of a still, or null when they are not base64.
const headBytes = (b64) => {
  const end = Math.min(b64.length, HEAD_CHARS);
  const bytes = [];
  let acc = 0;
  let bits = 0;
  for (let n = 0; n < end; n++) {
    const code = b64.charCodeAt(n);
    if (code === 61) break;                      // '=' ends the data
    const v = B64_VALUE[code];
    if (v === undefined) return null;
    acc = (acc << 6) | v;
    bits += 6;
    if (bits >= 8) {
      bits -= 8;
      bytes.push((acc >> bits) & 255);
      acc &= (1 << bits) - 1;
    }
  }
  return bytes;
};
const u16 = (d, n) => d[n] * 256 + d[n + 1];
const u32 = (d, n) => d[n] * 16777216 + d[n + 1] * 65536 + d[n + 2] * 256 + d[n + 3];

// { w, h } from a PNG IHDR or from the first JPEG frame header (SOF), or null
// when the size cannot be read: the head is cut off, the structure is not what
// is expected, or a side is zero. It never throws.
const sizeOf = (b64, format) => {
  try {
    const d = headBytes(b64);
    if (!d) return null;
    let w;
    let h;
    if (format === 'png') {
      // 8 byte signature, then the first chunk, which is IHDR: its length, the
      // name, then width and height as 4 byte big endian numbers.
      if (d.length < 24 || d[12] !== 0x49 || d[13] !== 0x48 || d[14] !== 0x44 || d[15] !== 0x52) return null;
      w = u32(d, 16);
      h = u32(d, 20);
    } else {
      // SOI, then segments that each start FF and a marker code. A frame header
      // is 0xC0 to 0xCF except 0xC4 (Huffman tables), 0xC8 (reserved) and 0xCC
      // (arithmetic tables). Every other segment is stepped over by its length.
      let n = 2;
      for (;;) {
        if (d[n] !== 0xFF) return null;
        while (d[n + 1] === 0xFF) n++;           // fill bytes before a marker
        const m = d[n + 1];
        if (m === undefined || m === 0x00 || m === 0xD9 || m === 0xDA) return null;
        if (m >= 0xC0 && m <= 0xCF && m !== 0xC4 && m !== 0xC8 && m !== 0xCC) {
          if (d.length < n + 9) return null;
          h = u16(d, n + 5);
          w = u16(d, n + 7);
          break;
        }
        if (m === 0x01 || (m >= 0xD0 && m <= 0xD8)) { n += 2; continue; }   // no length
        const len = d.length < n + 4 ? 0 : u16(d, n + 2);
        if (len < 2) return null;
        n += 2 + len;
      }
    }
    return w > 0 && h > 0 ? { w, h } : null;
  } catch (e) { return null; }
};
const inLimits = (s) => s.w >= MIN_SIDE && s.w <= MAX_SIDE && s.h >= MIN_SIDE && s.h <= MAX_SIDE
  && s.w * s.h >= MIN_PIXELS && s.w * s.h <= MAX_PIXELS;

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
    // A size that is read and out of limits is skipped. One that cannot be read stays.
    const size = sizeOf(b64, format);
    if (size && !inLimits(size)) continue;
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
