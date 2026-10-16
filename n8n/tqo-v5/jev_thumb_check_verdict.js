// Jev's check of the finished thumbnail, ruled by Tee 2026-10-16 and shipped in
// shadow. This is the body of Jev: Thumb Verdict, the Code node after the
// TypeSafe call that Jev: Thumb Check Body built. It turns Jev's three answers
// into one note for the Shim to append to thumb_warning. Every rule is
// computed here from the numbers, none is left to Jev's own wording, so the
// same answers always give the same note.
//
// The rules, in order:
//   headline_present below 0.5   "Jev did not find the headline text on the
//                                thumbnail". The box answer is not looked at,
//                                not even to check its shape: TypeSafe's Box
//                                always returns four edges and has no not
//                                found answer, so with the headline absent the
//                                box is a guess, and its docs say to ignore it
//                                when the Noul is low. A reversed or zero area
//                                box beside an absent headline therefore still
//                                gives this note.
//   otherwise, box right edge above 0.594
//                                the headline runs off the dark panel. The
//                                panel covers x 0 to 760 of 1280 px, which is
//                                0.594 of the width.
//   box bottom above 0.95, or top or left below 0.02
//                                the headline touches the edge of the frame.
//   headline_readable below 0.5  Jev reads the headline as hard to read.
// Several notes join with "; ", in that order.
//
// jevThumbChecked says the answers were usable. A response that is not from a
// jev- model, or has headline_present or headline_readable missing, of the
// wrong type, not finite or out of range, is ignored whole: checked false, no
// note, no box. The same holds for the box answer, but only once the headline
// is found (present 0.5 or more), because only then is the box read. A silent
// note is then not mistaken for a clean frame. A box must also have top above
// bottom and left above right, or it is out of range too.
const SCRIM_RIGHT = 0.594;
const EDGE_LOW = 0.02;
const EDGE_BOTTOM = 0.95;
const HALF = 0.5;

const unit = (v) => typeof v === 'number' && Number.isFinite(v) && v >= 0 && v <= 1;
const noulOf = (a) => (a && a.type === 'noul' && unit(a.noul) ? a.noul : null);
const boxOf = (a) => {
  const b = a && a.type === 'box' ? a.box : null;
  if (!b || ![b.top, b.bottom, b.left, b.right].every(unit)) return null;
  if (!(b.top < b.bottom && b.left < b.right)) return null;
  return { top: b.top, bottom: b.bottom, left: b.left, right: b.right };
};

let verdict = { jevThumbNote: null, jevThumbChecked: false, jevHeadlineBox: null };
try {
  const r = $input.first().json;
  const answers = r && typeof r.model === 'string' && r.model.startsWith('jev-') ? r.answers : null;
  if (answers && typeof answers === 'object') {
    const present = noulOf(answers.headline_present);
    const readable = noulOf(answers.headline_readable);
    if (present !== null && readable !== null) {
      if (present < HALF) {
        // The box answer is never read on this branch.
        verdict = { jevThumbNote: 'Jev did not find the headline text on the thumbnail', jevThumbChecked: true, jevHeadlineBox: null };
      } else {
        const box = boxOf(answers.headline_box);
        if (box !== null) {
          const notes = [];
          if (box.right > SCRIM_RIGHT) notes.push('the headline runs off the dark panel onto the photograph');
          if (box.bottom > EDGE_BOTTOM || box.top < EDGE_LOW || box.left < EDGE_LOW) notes.push('the headline touches the edge of the frame');
          if (readable < HALF) notes.push('Jev reads the headline as hard to read at phone size');
          verdict = {
            jevThumbNote: notes.length ? notes.join('; ') : null,
            jevThumbChecked: true,
            jevHeadlineBox: box,
          };
        }
      }
    }
  }
} catch (e) {
  verdict = { jevThumbNote: null, jevThumbChecked: false, jevHeadlineBox: null };
}
return [{ json: verdict }];
