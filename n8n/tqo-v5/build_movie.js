// Build Movie v9 - PRESENTER LAYER. Matched b-roll + presenter segments. Cold open.
//
// PRESENTER-LED (Quality Law rev2, ruled by Tee 2026-09-30): the avatar segments
// from the Presenter Clips lane (Plan Presenter Segments -> HeyGen/Runway batch)
// are the on-camera identity; b-roll is the bridge. Every presenter clip must be
// share-verified in at_tqo_presenter_clips BEFORE inclusion - the moov-atom
// failure lesson: an owner-only file downloads as an HTML sign-in page and the
// worker writes the HTML into the clip, and ffmpeg refuses it.
//
// v8 history below, retained:
//
// POOL RETIRED - 10 Aug 2026.
//
// All 21 clips in the pool folder were reviewed frame by frame. Every one is
// abstract texture: aerial city at night, rain on glass with bokeh, smoke,
// silk folds, ocean surface, a spiral staircase, a flat orange field. Four are
// close to solid black and would read as a dead frame in an episode.
//
// Not one contains a person, a desk, a screen, a keyboard or an office. So no
// clip in the pool matches any keyword 'Plan B-Roll Segments' produces, and the
// pool was inserting unrelated mood texture on any beat Pexels could not fill.
//
// POOL_SHARED false restores the original fallback: hold the previous clip. That
// is the designed behaviour and heldClips already reports how often it happens.
// Watch that number. If it climbs, the fix is better Pexels queries or real
// owned footage, NOT switching the pool back on.
//
// Re-enable only when the folder contains footage about the subject - screen
// recordings of the workflow canvas, Airtable views, the render queue, the
// Human Review tick. Those are tracked in the B-Roll Library table
// (tbl2pr5GLeeUJK1rr) and every row there carries a Verified flag meaning share
// permission AND file size were both checked.
//
// The POOL array below is left in place, unused, so re-enabling is one boolean
// rather than an archaeology exercise. Do not add to it. Add to the folder and
// the library table instead.
//
// History worth keeping, because this failed silently for a long time.
// Render uYn0b5SzQwGflxwh died with:
//   ffmpeg failed: moov atom not found
//   Error opening input file /data/work/.../clip9.mp4
// clip9 came from POOL. Those Drive files were owner-only, so an
// unauthenticated download returned an HTML sign-in page, the worker wrote the
// HTML to clip9.mp4, and ffmpeg refused it. The voice mp3 uses the same host
// and worked only because 'Make Audio Public' shares that one file first.
//
// Drive also serves a scan interstitial above roughly 25MB, which produces the
// identical symptom. Both share permission and file size have to be right.
//
// If moov atom errors come back, check those two things first before assuming
// the render worker is at fault. It was never the worker.
const POOL_SHARED = false;

const W = 1920, H = 1080;

// INTRO AND END CARDS REMOVED - 9 Aug 2026.
//
// Both bumpers lived on the ops box and were brand-agnostic: the same 3.5s
// intro and 16s end card played on NCO Forge as on The Quiet Operator. Once
// both brands went daily that was simply wrong, and neither card matched the
// register of either show. A cold open suits writing this restrained better
// than a bumper does, and 16 seconds of card at the end is 16 seconds of a
// viewer deciding to leave.
//
// LEAD_PAD replaces INTRO_DUR everywhere it was used, so the timing maths
// downstream is unchanged - it is just a much smaller number now. It exists so
// the first syllable is not clipped by the encoder; it is silence, not a card.
//
// To bring cards back, set LEAD_PAD to the intro duration and re-add the two
// video elements at the bottom of the scene. Make them brand-aware off
// Show Context: Render if you do - do not go back to one file for both shows.
const LEAD_PAD = 0.5;

const segs = $('Plan B-Roll Segments').all();
const px   = $('Pexels Search').all();
const POOL = [
  "https://drive.usercontent.google.com/download?id=1ljdeliylCdqu81Mbyar4lwknc35dbEAJ&export=download&confirm=t",
  "https://drive.usercontent.google.com/download?id=1FrtF4HrT3JvvllCXMRU96u_7238ug8jn&export=download&confirm=t",
  "https://drive.usercontent.google.com/download?id=1lJMu49tUqXNx1xBMRBDVB4Aa4zdvTyK9&export=download&confirm=t",
  "https://drive.usercontent.google.com/download?id=1P2OZjX92rl8DH1-D_zXbGQuXu4qAwSPM&export=download&confirm=t",
  "https://drive.usercontent.google.com/download?id=1d-f-HmzVeFyodq1tWJKeZmCmW4Yp8QRd&export=download&confirm=t",
  "https://drive.usercontent.google.com/download?id=10VMbspxabGdXEaaxksmFyyNLX0WLMfzb&export=download&confirm=t",
  "https://drive.usercontent.google.com/download?id=1Kt3fiWaSmYFDhFFgiMwYROdaUlISExsD&export=download&confirm=t",
  "https://drive.usercontent.google.com/download?id=10j_YmgIs3zNSwkz2r19jPC0YkTjkRJ77&export=download&confirm=t",
  "https://drive.usercontent.google.com/download?id=1Jgy_6SLa0BC65BIcE1papnWQwvOEwxVA&export=download&confirm=t",
  "https://drive.usercontent.google.com/download?id=11z7GEcmVie4BUxgeJ1oJxgs9z--H_bwe&export=download&confirm=t"
];

// Every usable file from a Pexels response, best-fit width first, one per video.
// The old version read videos[0] only and threw away two clips it had already
// paid for on the same call. per_page is now 15, so this list is much longer
// and the recency filter below has real room to work.
function candidates(resp){
  const vids = (resp && Array.isArray(resp.videos)) ? resp.videos : [];
  const out = [];
  for (const v of vids) {
    const files = (v.video_files || []).filter(f => (f.file_type || '').includes('mp4') && f.width);
    if (!files.length) continue;
    files.sort((a, b) => (b.width || 0) - (a.width || 0));
    const pick = files.find(f => f.width && f.width <= 3840) || files[files.length - 1];
    if (pick && pick.link) out.push(pick.link);
  }
  return out;
}

// JEV SHADOW - 16 Oct 2026. The Jev side branch (Jev: B-Roll Stills through Jev:
// Rank B-Roll) has TypeSafe score up to four stills per segment for how well
// each clip fits the sentence spoken over it. This node reads those scores and
// works out which clip Jev would pick, but it keeps today's pick until JEV_APPLY
// is true. Flipping it is a ruling for Tee, not an edit to make in passing: read
// jevRanked and jevWouldChange on real episodes first. Both are counts of
// segments and both are returned whether or not the flag is on: jevRanked is the
// segments where Jev scored at least one candidate, jevWouldChange the segments
// where Jev's pick differs from today's.
const JEV_APPLY = false;

// Jev scores by segment: Map of segment position to a Map of clip link to a
// score from 0 to 3. It fails open everywhere. A Jev node that did not run (the
// $() lookup throws), an error item from the HTTP node, a response from a model
// whose name does not start with jev-, an answer of the wrong type and a score
// that is not a finite number from 0 to 3 each mean no score, and no score
// means today's order. It must never throw, so a Jev fault cannot stop a render.
function readJev() {
  const bySeg = new Map();
  try {
    const bodies = $('Jev: B-Roll Bodies').all();
    const ranks = $('Jev: Rank B-Roll').all();
    // The bodies node lists links in the order of the questions it asked and
    // leaves out stills it could not use, so the k in s{seg}c{k} is not always
    // the place in links. Pair each question name with its link by position
    // instead, and when the two counts disagree trust neither for that item.
    const linkOf = new Map();
    for (const b of bodies) {
      const j = (b && b.json) || {};
      const links = Array.isArray(j.links) ? j.links : [];
      const qs = (j.body && j.body.questions && typeof j.body.questions === 'object') ? Object.keys(j.body.questions) : null;
      if (qs) { if (qs.length === links.length) qs.forEach((name, n) => linkOf.set(name, links[n])); }
      else links.forEach((l, n) => linkOf.set('s' + j.segIndex + 'c' + (n + 1), l));
    }
    // The answers come back with no segment on the item, so the segment is
    // read from the question name.
    for (const r of ranks) {
      const j = (r && r.json) || {};
      if (typeof j.model !== 'string' || !j.model.startsWith('jev-')) continue;
      const answers = (j.answers && typeof j.answers === 'object') ? j.answers : {};
      for (const name of Object.keys(answers)) {
        const a = answers[name];
        const m = /^s(\d+)c(\d+)$/.exec(name);
        const link = linkOf.get(name);
        if (!m || typeof link !== 'string' || !a || a.type !== 'score') continue;
        if (!Number.isFinite(a.score) || a.score < 0 || a.score > 3) continue;
        const seg = Number(m[1]);
        if (!bySeg.has(seg)) bySeg.set(seg, new Map());
        bySeg.get(seg).set(link, a.score);
      }
    }
  } catch (e) { return new Map(); }
  return bySeg;
}

// Jev's order of one segment's candidates. A clip scored 1 or more goes first,
// best score first. A clip Jev did not score keeps its Pexels place behind
// those. A clip scored under 1 (blank, blurred, watermarked or unrelated) goes
// last. Equal scores keep Pexels order. Nothing is ever dropped: the same clips
// come back, only the order differs.
function jevOrder(list, scores) {
  if (!scores) return list.slice();
  const at = (n) => scores.get(list[n]);
  const ix = list.map((_, n) => n);
  const best = (a, b) => (at(b) - at(a)) || (a - b);
  const top = ix.filter(n => at(n) >= 1).sort(best);
  const none = ix.filter(n => at(n) === undefined);
  const low = ix.filter(n => at(n) < 1).sort(best);
  return [...top, ...none, ...low].map(n => list[n]);
}

let poolIdx = 0, lastSrc = null, poolUsed = 0, heldClips = 0;
let jevRanked = 0, jevWouldChange = 0;
const recent = [];            // short memory so a clip does not reappear immediately
const usedAll = new Set();    // benchmark visual rule: no clip reuse within an episode
const broll = [];
const jev = readJev();

// The selection rule, unchanged, as a function so it can run over Pexels order
// and over Jev order against the same memory of what has been used.
const pickFrom = (list) => list.find(c => !usedAll.has(c))
                        || list.find(c => !recent.includes(c))
                        || list.find(c => c !== lastSrc)
                        || list[0]
                        || null;

for (let i = 0; i < segs.length; i++) {
  const s = segs[i].json;
  const cands = candidates(px[i] && px[i].json);

  // Pexels first: those clips were chosen against the narration for this beat.
  // Prefer one unused in the last three segments, then one not equal to the
  // previous, then anything.
  // Both picks are always worked out, against the same memory. Today's pick
  // stands unless JEV_APPLY is on. jevWouldChange counts segments where Jev's
  // pick differs from today's, so it still reads true once the flag is on.
  const scores = jev.get(i);
  const todayPick = pickFrom(cands);
  const jevPick = pickFrom(jevOrder(cands, scores));
  if (scores && cands.some(c => scores.has(c))) jevRanked++;
  if (jevPick !== todayPick) jevWouldChange++;
  let src = JEV_APPLY ? jevPick : todayPick;

  if (!src) {
    if (POOL_SHARED) { src = POOL[poolIdx % POOL.length]; poolIdx++; poolUsed++; }
    else { src = lastSrc; heldClips++; }
  }
  if (!src) continue;                          // nothing at all for the opening segment

  lastSrc = src;
  recent.push(src);
  if (recent.length > 3) recent.shift();
  usedAll.add(src);

  broll.push({ type: "video", src, start: LEAD_PAD + s.start, duration: s.duration, muted: true });
}

const first = segs[0].json;
const voiceUrl = "https://drive.usercontent.google.com/download?id=" + first.uploadId + "&export=download&confirm=t";
const MUSIC = [
  "http://150.136.200.85/music/track1.mp3","http://150.136.200.85/music/track2.mp3",
  "http://150.136.200.85/music/track3.mp3","http://150.136.200.85/music/track4.mp3",
  "http://150.136.200.85/music/track5.mp3",
];
let hash = 0; for (const ch of String(first.uploadId)) hash = (hash * 31 + ch.charCodeAt(0)) >>> 0;
const musicUrl = MUSIC[hash % MUSIC.length];

// --- PRESENTER LAYER (v9) ---
// Plan Presenter Segments emits the ordered presenter/broll timeline and the
// shot list for the HeyGen/Runway batch. Clips live in the Presenter Clips
// Drive folder (1SyqzTVQYxsGXol4N1vBQfI4FVC1cVeK8), one per segment,
// named presenter-{rowId}-{segmentIndex}.mp4, voice already baked in.
//
// Clip URLs come from the shot-list writer's share results carried on the item
// (presenterClips: [{segmentIndex, publicUrl, duration}]). A required presenter
// segment with no verified clip REFUSES to render: a presenter-led episode
// shipping without its presenter is a quality law failure, not a degraded mode.
const pres = $json.presenterClips || [];
const requiredMissing = [];
for (const seg of pres) {
  if (!seg.publicUrl || !seg.shareVerified) {
    requiredMissing.push('segment ' + seg.segmentIndex + ' (' + (seg.file || 'unnamed') + '): ' + (!seg.publicUrl ? 'no clip' : 'not share-verified'));
  }
}
if (requiredMissing.length) {
  throw new Error('PRESENTER REFUSAL - missing or unverified presenter clips: ' + requiredMissing.join('; ') + '. Fill the Presenter Clips folder and set share_verified in at_tqo_presenter_clips, then re-run.');
}

// Presenter elements render ABOVE b-roll (inserted after the b-roll spread).
// Voice: presenter clips carry the ElevenLabs voice baked in, so when any
// presenter clip exists the single audio element points at the FIRST presenter
// clip's audio track... but the worker historically kept ONE audio element and
// one audio SOURCE per element. Safety design (no probe risk): keep the voice
// mp3 audio element as-is and lay presenter clips MUTED. The voice timing is
// unchanged and nothing double-speaks. If the adapter later proves multi-source
// audio, flip presenterAudioFirst to true to take audio from the presenter clip
// instead of the mp3 (the mp3 then becomes the fallback voice track).
const PRESENTER_AUDIO_FIRST = false;
const presenterElements = pres.map(seg => ({
  type: "video",
  src: seg.publicUrl,
  start: LEAD_PAD + seg.start,
  duration: seg.duration,
  muted: true
}));

const lastSeg = segs[segs.length - 1].json;
const bodyEnd = LEAD_PAD + (lastSeg.start + lastSeg.duration);   // now the true end of the video


function srtTime(value) {
  const ms = Math.max(0, Math.round(Number(value || 0) * 1000));
  const h = String(Math.floor(ms / 3600000)).padStart(2, '0');
  const m = String(Math.floor((ms % 3600000) / 60000)).padStart(2, '0');
  const s = String(Math.floor((ms % 60000) / 1000)).padStart(2, '0');
  const x = String(ms % 1000).padStart(3, '0');
  return h + ':' + m + ':' + s + ',' + x;
}
const srt = segs.map((item, index) => {
  const segment = item.json;
  const start = LEAD_PAD + Number(segment.start || 0);
  const end = start + Number(segment.duration || 0);
  const narration = String(segment.narration || '').trim();
  if (!narration) return '';
  return (index + 1) + '\n' + srtTime(start) + ' --> ' + srtTime(end) + '\n' + narration + '\n';
}).filter(Boolean).join('\n');
if (!srt.trim()) throw new Error('Subtitle SRT is empty');

const movie = {
  resolution: "custom", width: W, height: H,
  scenes: [{ elements: [
    ...broll,
    ...presenterElements,
    // ONE AUDIO ELEMENT ONLY - 15 Sep 2026. The VPS adapter at 172.16.2.1:8081
    // keeps a single audio element and it was the music: execution 46 carried
    // the bed and no narration, probe A (voice alone) carried the clone voice,
    // probe B (music first, voice second) carried music only. The bed comes
    // back ducked under the voice through our own worker's duck_mix job in the
    // presenter build. musicUrl is still computed above so that step can use it.
    { type: "audio", src: voiceUrl, start: LEAD_PAD, volume: 1.0 }
    // NO BURNED CAPTIONS ON LONG FORM - ruled by Tee 15 Sep 2026 on an inline
    // card: Shorts carry burned captions, long form ships clean with the SRT
    // uploaded as a YouTube caption track and numbers shown as on-screen
    // callouts. The SRT is still built above and returned below so Mark Ready
    // saves it on the row for the publish lane. Before this ruling the element
    // { type: "subtitles", srt, settings: {...} } sat here.
  ]}]
};

const ROW = $('Presenter: Attach Clips').first().json || {};
const TITLE = (ROW.videoTitle || ROW.title || ('episode-' + (ROW.rowId ?? 'untitled')));
return [{ json: { j2vBody: movie, clipCount: broll.length, presenterCount: pres.length, presenterAudioFirst: PRESENTER_AUDIO_FIRST,
                  poolUsed, heldClips, poolEnabled: POOL_SHARED,
                  leadPad: LEAD_PAD, runtimeSec: Math.round(bodyEnd), srt, rowId: ROW.rowId, videoTitle: TITLE,
                  jevRanked, jevWouldChange, jevApplied: JEV_APPLY } }];
