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

// Jev's check of the composed frame, ruled by Tee 2026-10-16 and SHIPPED IN
// SHADOW. If the side branch off Thumb: Compose ran, this node always records
// what Jev found on the output json: jevThumbNote, jevThumbChecked and
// jevHeadlineBox. It puts the note into thumb_warning only when JEV_APPLY is
// true, and flipping that is a ruling for Tee, so it ships false. With it false
// thumb_warning is exactly what the size check above set. The warning never
// blocks (OS 30 gate 8 still decides), so a wrong note costs a line of text and
// not a thumbnail. Any missing node, empty note or error records nothing found
// (null, false, null) and leaves thumb_warning as the size check set it. So does
// a verdict that is not this row's: see the guard in the try below.
const JEV_APPLY = false;
let jevNote = null;
let jevChecked = false;
let jevBox = null;
try {
  const v = $('Jev: Thumb Verdict').first().json;
  // Stale run guard. One Row at a Time is a Split In Batches loop, so when a
  // later row's Jev branch stops early this lookup may return an earlier row's
  // verdict (unverified n8n behaviour, guarded either way). The verdict carries
  // forHeadline, the headline its request was built for. It counts only when
  // that is a string equal to the trimmed headline of this row's Pick Still;
  // any other verdict is treated as absent.
  if (typeof v.forHeadline === 'string' && v.forHeadline === String(pick.headline || '').trim()) {
    if (typeof v.jevThumbNote === 'string' && v.jevThumbNote.trim()) jevNote = v.jevThumbNote.trim();
    jevChecked = v.jevThumbChecked === true;
    const b = v.jevHeadlineBox;
    if (b && [b.top, b.bottom, b.left, b.right].every(Number.isFinite)) {
      jevBox = { top: b.top, bottom: b.bottom, left: b.left, right: b.right };
    }
  }
} catch (e) {
  // The Jev nodes did not run, which is today's behaviour.
}
result[0].json.jevThumbNote = jevNote;
result[0].json.jevThumbChecked = jevChecked;
result[0].json.jevHeadlineBox = jevBox;
result[0].json.jevApplied = JEV_APPLY;
if (JEV_APPLY && jevNote) {
  // No verdict note names Jev, so this prefix names it once for the line.
  const jev = 'Jev: ' + jevNote;
  const was = result[0].json.thumb_warning;
  result[0].json.thumb_warning = was ? was + '; ' + jev : jev;
}
return result;
