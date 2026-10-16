// Jev's check of the finished thumbnail, ruled by Tee 2026-10-16 and shipped in
// shadow. This is the body of Jev: Thumb Check Body, the Code node between the
// Extract From File that turned the composed frame into base64 (still_b64) and
// the TypeSafe call. It builds the request and sends nothing: Code nodes have
// no network access, and Jev: Check Thumb does the POST.
//
// It asks three things about the 1280x720 frame Thumb: Compose made, and the
// verdict node turns the answers into a note:
//   headline_present   is the headline on the image as text at all
//   headline_box       where that text sits. A Box question needs Jev 1.14, which
//                      is jev-preview or jev-1.14.0 (box.md), so the whole request
//                      uses one of them. It names the moving alias jev-preview on
//                      purpose: nothing is tuned against a version yet, and the
//                      response's own model field logs which version answered.
//                      Pin jev-1.14.0 once thresholds are tuned on shadow data.
//   headline_readable  is every word of the headline easy to read at phone size.
//                      One condition, as noul.md asks for one per Noul. A headline
//                      touching the edge is the box rules' job in the verdict.
// A box question has no absent answer, so it is always paired with
// headline_present, and the verdict ignores the box when the headline is not found.
//
// The composed frame is sent once, in state, as images.md says for an image that
// several questions share (an image in a question's instructions is sent again for
// every question that holds it). The state is { thumb: "<thumb>", headline } and
// the three questions name `thumb` in backticks. None of them holds the reference
// string itself, so the image goes out once.
//
// Only a PNG or JPEG goes out, told apart by the base64 prefix. A request body
// is held to 20,000,000 characters of base64. An image that is missing, in
// another format or over that, or a row with no headline, returns [] and the
// branch stops. The Shim then reports exactly as it does today, because a check
// that cannot run must never make the thumbnail lane fail.
const MAX_B64 = 20000000;
let out = [];
try {
  const b64 = $input.first().json.still_b64;
  const headline = String($('Thumb: Pick Still').first().json.headline || '').trim();
  let format = null;
  if (typeof b64 === 'string' && b64.length > 0 && b64.length <= MAX_B64) {
    if (b64.startsWith('/9j/')) format = 'jpeg';
    else if (b64.startsWith('iVBORw0KGgo')) format = 'png';
  }
  if (format && headline) {
    out = [{ json: { body: {
      model: 'jev-preview',
      state: { thumb: '<thumb>', headline },
      questions: {
        headline_present: {
          type: 'noul',
          instructions: 'Does `thumb` show the words in `headline` as text on the image?',
          criteria: {
            true: 'The words in headline appear on the image as text',
            false: 'The words in headline do not appear on the image as text',
          },
        },
        headline_box: {
          type: 'box',
          instructions: 'the headline text in `thumb`, the words in `headline`',
        },
        headline_readable: {
          type: 'noul',
          instructions: 'Is every word of the headline in `thumb` easy to read at phone size?',
          criteria: {
            true: 'Every word of the headline is easy to read at phone size',
            false: 'A word of the headline is hard to read at phone size',
          },
        },
      },
      assets: { '<thumb>': { type: 'image', format, data_base64: b64 } },
    } } }];
  }
} catch (e) {
  out = [];
}
return out;
