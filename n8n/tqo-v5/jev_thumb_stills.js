// Jev: Thumb Stills. First node of the Jev side branch off Thumb: Find Still,
// ruled by Tee 2026-10-16, SHIPS IN SHADOW. It decides which photos Jev will be
// shown: the same photos Thumb: Pick Still considers, in the same order, at most
// three, each by the url Pick Still would draw (landscape, then large2x, then
// large). The next node fetches each photo as a file.
//
// Two urls travel on each item and they are not the same thing. url is exactly
// the url Pick Still would draw, and it is the key Pick Still uses to match a
// score to a photo, so it must not change. fetchUrl is what the HTTP fetch node
// must READ, and it is landscape, else large. TypeSafe rejects an image under
// 280 or over 1568 pixels on either side, and one rejected image fails the whole
// request with no partial answers. The large2x size is left out of fetchUrl on
// purpose: Pexels is said to document large2x as the 940x650 size at dpr 2, which
// would make it about 1880 pixels wide and over that limit. That Pexels figure is
// UNVERIFIED here, since no live Pexels response was read, so large2x is simply
// never fetched. A photo whose only url is large2x gets no item at all.
//
// k is the photo's 1-based place in the Pexels result, so a skipped photo leaves
// a gap in k rather than renumbering the rest. Jev: Thumb Body names its
// question p{k} from it and Thumb: Pick Still reads the score back the same way.
// Only a url on https://images.pexels.com/ is fetched, so this branch can never
// be made to call some other host. A Code node has no network access, so this
// node names urls and fetches nothing.
//
// Fail open: a Find Still that did not run, an error item with no photos or a
// photo with no usable url or fetchUrl gives fewer items or none. An empty return
// stops the branch, and Pick Still then keeps today's choice. This node never
// throws.
const K_THUMB = 3;
const HOST = 'https://images.pexels.com/';
const usable = (u) => typeof u === 'string' && u.startsWith(HOST);
const out = [];
try {
  const photos = $('Thumb: Find Still').first().json.photos;
  if (Array.isArray(photos)) {
    photos.slice(0, K_THUMB).forEach((photo, i) => {
      const src = photo && photo.src;
      const url = src ? (src.landscape || src.large2x || src.large) : null;
      if (!usable(url)) return;
      const fetchUrl = usable(src.landscape) ? src.landscape : (usable(src.large) ? src.large : null);
      if (!fetchUrl) return;
      out.push({ json: { k: i + 1, photoId: photo.id === undefined ? null : photo.id, url, fetchUrl } });
    });
  }
} catch (e) { return []; }
return out;
