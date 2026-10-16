// Jev's check of the finished thumbnail, ruled by Tee 2026-10-16 and shipped in
// shadow. This is the body of Jev: Thumb Check Body, the Code node between the
// Extract From File that turned the composed frame into base64 (still_b64) and
// the TypeSafe call. It builds the request and sends nothing: Code nodes have
// no network access, and Jev: Check Thumb does the POST.
//
// It asks three things about the 1280x720 frame Thumb: Compose made, and the
// verdict node turns the answers into a note:
//   headline_present   is the headline on the image as text at all
//   headline_box       where that text sits (jev-preview is the only model that
//                      answers a box question, so the whole request uses it)
//   headline_readable  is every word readable at phone size, none cut off
// A box question has no absent answer, so it is always paired with
// headline_present, and the verdict ignores the box when the headline is not found.
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
      state: { headline },
      questions: {
        headline_present: {
          type: 'noul',
          instructions: 'Does <thumb> show the words in `headline` as text on the image?',
          criteria: {
            true: 'The words in headline appear on the image as text',
            false: 'The words in headline do not appear on the image as text',
          },
        },
        headline_box: {
          type: 'box',
          instructions: 'The headline text on <thumb>, the words in `headline`',
        },
        headline_readable: {
          type: 'noul',
          instructions: 'Is every word of the headline on <thumb> fully readable at phone size, with no letter cut off by the edge of the image?',
          criteria: {
            true: 'Every word of the headline is fully readable at phone size and no letter is cut off by the edge of the image',
            false: 'A word of the headline is hard to read at phone size, or a letter is cut off by the edge of the image',
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
