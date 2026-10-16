// Jev: B-Roll Stills, ruled by Tee 2026-10-16. Lists the stock clips each b-roll
// segment would choose from, with the preview still of each, so Jev can look at
// the frames and score them against the narration. It decides which clips are
// in the running and nothing else: a Code node has no network access, so the
// stills are fetched by the HTTP node that follows. The branch runs in shadow
// and never changes which clip Build Movie picks.
//
// The candidate rule below is the rule in Build Movie's candidates(), and
// jev_broll_bodies.test.mjs keeps them in step by running both on the same
// Pexels response: mp4 files with a width, widest first, the first at or under
// 3840 wide (the smallest if none is), one link per video. The only difference
// is that each candidate also carries its video's still and id.
//
// A clip whose still is not on the Pexels image host is left out, so nothing
// from an unexpected host is ever fetched. Of the rest the first K_BROLL are
// kept, in Pexels order, and cand counts them from 1.
//
// Fails open: a missing node, a response with no videos (a failed Pexels call
// leaves an item with an error and no videos) or a malformed video gives that
// segment no candidates, and a segment with none adds nothing. Nothing here
// throws, because a Jev node must never stop the movie.
const K_BROLL = 4;
const STILL_HOST = 'https://images.pexels.com/';

function candidates(resp) {
  const vids = (resp && Array.isArray(resp.videos)) ? resp.videos : [];
  const out = [];
  for (const v of vids) {
    const files = (v.video_files || []).filter(f => (f.file_type || '').includes('mp4') && f.width);
    if (!files.length) continue;
    files.sort((a, b) => (b.width || 0) - (a.width || 0));
    const pick = files.find(f => f.width && f.width <= 3840) || files[files.length - 1];
    if (pick && pick.link) out.push({ link: pick.link, stillUrl: v.image, videoId: v.id });
  }
  return out;
}

const items = [];
try {
  const segs = $('Plan B-Roll Segments').all();
  const px = $('Pexels Search').all();
  for (let i = 0; i < segs.length; i++) {
    // Pexels Search runs once per segment in segment order, so item i answers segment i.
    let kept = [];
    try {
      kept = candidates(px[i] && px[i].json)
        .filter(c => typeof c.stillUrl === 'string' && c.stillUrl.startsWith(STILL_HOST))
        .slice(0, K_BROLL);
    } catch (e) { kept = []; }
    kept.forEach((c, n) => items.push({ json: { segIndex: i, cand: n + 1, link: c.link, stillUrl: c.stillUrl, videoId: c.videoId } }));
  }
} catch (e) { return []; }
return items;
