// Jev: Thumb Stills. First node of the Jev side branch off Thumb: Find Still,
// ruled by Tee 2026-10-16, SHIPS IN SHADOW. It decides which photos Jev will be
// shown: the same photos Thumb: Pick Still considers, in the same order, at most
// three, each by the url Pick Still would draw (landscape, then large2x, then
// large). The next node fetches each url as a file.
//
// k is the photo's 1-based place in the Pexels result, so a skipped photo leaves
// a gap in k rather than renumbering the rest. Jev: Thumb Body names its
// question p{k} from it and Thumb: Pick Still reads the score back the same way.
// Only a url on https://images.pexels.com/ is fetched, so this branch can never
// be made to call some other host. A Code node has no network access, so this
// node names urls and fetches nothing.
//
// Fail open: a Find Still that did not run, an error item with no photos or a
// photo with no usable url gives fewer items or none. An empty return stops the
// branch, and Pick Still then keeps today's choice. This node never throws.
const K_THUMB = 3;
const HOST = 'https://images.pexels.com/';
const out = [];
try {
  const photos = $('Thumb: Find Still').first().json.photos;
  if (Array.isArray(photos)) {
    photos.slice(0, K_THUMB).forEach((photo, i) => {
      const src = photo && photo.src;
      const url = src ? (src.landscape || src.large2x || src.large) : null;
      if (typeof url !== 'string' || !url.startsWith(HOST)) return;
      out.push({ json: { k: i + 1, photoId: photo.id === undefined ? null : photo.id, url } });
    });
  }
} catch (e) { return []; }
return out;
