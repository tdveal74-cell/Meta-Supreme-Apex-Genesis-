// Reports what actually happened and carries the binary through untouched.
// Non-fatal by design: OS 30 gate 8 decides whether a row without a thumbnail
// may publish. Throwing here would skip that decision rather than make it.
//
// The bar is the composed frame. A bare stock photograph with no headline on it
// is not a thumbnail, and reporting one as rendered is worse than reporting
// nothing, because the gate then passes something that was never made.
const p    = $('Thumb: Plan').first().json;
const pick = $('Thumb: Pick Still').first().json;
const item = $input.first();
const bin  = item.binary && item.binary.thumbData ? item.binary : null;

const base = {
  airtableId: p.airtableId,
  thumb_title: p.headline,
  thumb_rendered: false,
  thumb_error: null,
  thumb_warning: null,
};

if (!pick.photoUsed) {
  return [{ json: { ...base,
    thumb_error: 'no Pexels still matched "' + p.query + '" (from "' + (p.queryRaw || '') + '"). '
      + 'Give this row a Primary Subject naming a concrete object, place or person.' } }];
}
if (!bin) {
  return [{ json: { ...base,
    thumb_error: 'the still downloaded but the compositor returned no image. '
      + 'Backdrop: ' + pick.photoUsed } }];
}

const bytes = Number(bin.thumbData.bytes || 0) || 0;
const result = [{
  json: { ...base,
    thumb_rendered: true,
    thumb_photo: pick.photoUsed,
    thumb_credit: pick.photographer || null,
    thumb_bytes: bytes,
    thumb_warning: bytes && bytes < 15000
      ? 'composed image is only ' + bytes + ' bytes, which usually means the backdrop failed to decode'
      : null },
  binary: bin
}];

// Jev's check of the composed frame, ruled by Tee 2026-10-16 and shipped in
// shadow: if the side branch off Thumb: Compose ran and found something wrong
// with the headline, say so in thumb_warning and change nothing else. The
// warning never blocks (OS 30 gate 8 still decides), so a wrong note costs a
// line of text and not a thumbnail. Any missing node, empty note or error
// leaves thumb_warning exactly as the size check above set it.
try {
  const note = $('Jev: Thumb Verdict').first().json.jevThumbNote;
  if (typeof note === 'string' && note.trim()) {
    const jev = 'Jev: ' + note.trim();
    const was = result[0].json.thumb_warning;
    result[0].json.thumb_warning = was ? was + '; ' + jev : jev;
  }
} catch (e) {
  // The Jev nodes did not run, which is today's behaviour.
}
return result;
