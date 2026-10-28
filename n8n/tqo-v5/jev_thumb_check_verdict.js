// Jev's check of the finished thumbnail, ruled by Tee 2026-10-16 and shipped in
// shadow. This is the body of Jev: Thumb Verdict, the Code node after the
// TypeSafe call that Jev: Thumb Check Body built. It turns Jev's three answers
// into one note. The Shim records it, and adds it to thumb_warning only when
// its JEV_APPLY is true. No note names Jev, because the Shim's "Jev: " prefix
// does that once for the whole line. Every rule is
// computed here from the numbers, none is left to Jev's own wording, so the
// same answers always give the same note.
//
// It also returns forHeadline, the headline the request was built for, read from
// Jev: Thumb Check Body's state. One Row at a Time is a Split In Batches loop, so
// when a later row's Jev branch stops early the Shim's lookup of this node may
// hand it an earlier row's verdict (unverified n8n behaviour, guarded either
// way). The Shim uses forHeadline to tell: it takes the verdict only when
// forHeadline equals the headline of the row it is shaping.
//
// The rules, in order:
//   headline_present below 0.5   "the headline text was not found on the
//                                thumbnail". The box answer is not looked at,
//                                not even to check its shape: TypeSafe's Box
//                                always returns four edges and has no not
//                                found answer, so with the headline absent the
//                                box is a guess, and its docs say to ignore it
//                                when the Noul is low. A reversed or zero area
//                                box beside an absent headline therefore still
//                                gives this note. headline_readable is not read
//                                either.
//   otherwise, box right edge above TEXT_RIGHT (0.5875)
//                                the headline runs off the dark panel. The
//                                threshold is the designed right edge of the
//                                text, not the scrim edge: see TEXT_RIGHT.
//   box bottom above 0.95, or top or left below 0.02
//                                the headline touches the edge of the frame.
//   headline_readable below 0.5  the headline is hard to read at phone size.
// Several notes join with "; ", in that order.
//
// jevThumbChecked says the answers were usable. A response that is not from a
// jev- model, or has headline_present missing, of the wrong type, not finite
// or out of range, is ignored whole: checked false, no note, no box. The same
// holds for headline_readable and the box answer, but only once the headline
// is found (present 0.5 or more), because only then are they read. A silent
// note is then not mistaken for a clean frame. A box must also have top above
// bottom and left above right, or it is out of range too. A value of exactly 0
// or exactly 1 is in range, for an answer and for a box edge alike.
//
// forHeadline is read apart from all of that, so a failure to read it never
// changes the verdict: null when Jev: Thumb Check Body did not run or holds no
// headline string, the headline otherwise. It rides on every verdict, checked
// or not.
//
// TEXT_RIGHT is the designed right edge of the headline text, as a fraction of
// the 1280 px frame. Thumb: Compose draws the headline at x 72 and Thumb: Pick
// Still wraps it to TEXT_BUDGET, 680 px measured from Arial's advance widths, so
// a full line ends at or before x 752, inside the dark panel (scrim) that ends
// at x 760. It read 700 until 2026-10-28, when Tee ruled on a card to follow the
// layout: the layout had moved to 680 and this line had not, so the note fired
// about 20 px late.
// This is a STARTING VALUE to tune from shadow data, not a measured one.
// jev_thumb_check.test.mjs reads the export and fails when the compositor's
// position, width or budget moves without this line.
const TEXT_RIGHT = (72 + 680) / 1280;
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
    if (present !== null) {
      if (present < HALF) {
        // Neither the box nor readable is read on this branch.
        verdict = { jevThumbNote: 'the headline text was not found on the thumbnail', jevThumbChecked: true, jevHeadlineBox: null };
      } else {
        const box = boxOf(answers.headline_box);
        if (box !== null && readable !== null) {
          const notes = [];
          if (box.right > TEXT_RIGHT) notes.push('the headline runs off the dark panel onto the photograph');
          if (box.bottom > EDGE_BOTTOM || box.top < EDGE_LOW || box.left < EDGE_LOW) notes.push('the headline touches the edge of the frame');
          if (readable < HALF) notes.push('the headline is hard to read at phone size');
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

// The headline this request was built for, so the Shim can tell a stale verdict
// from this row's own. Read apart from the verdict: unreadable is null.
let forHeadline = null;
try {
  const h = $('Jev: Thumb Check Body').first().json.body.state.headline;
  if (typeof h === 'string') forHeadline = h;
} catch (e) {
  forHeadline = null;
}
return [{ json: { ...verdict, forHeadline } }];
