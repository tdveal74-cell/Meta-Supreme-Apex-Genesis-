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

let poolIdx = 0, lastSrc = null, poolUsed = 0, heldClips = 0;
const recent = [];            // short memory so a clip does not reappear immediately
const usedAll = new Set();    // benchmark visual rule: no clip reuse within an episode
const broll = [];

for (let i = 0; i < segs.length; i++) {
  const s = segs[i].json;
  const cands = candidates(px[i] && px[i].json);

  // Pexels first: those clips were chosen against the narration for this beat.
  // Prefer one unused in the last three segments, then one not equal to the
  // previous, then anything.
  let src = cands.find(c => !usedAll.has(c))
         || cands.find(c => !recent.includes(c))
         || cands.find(c => c !== lastSrc)
         || cands[0]
         || null;

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
                  leadPad: LEAD_PAD, runtimeSec: Math.round(bodyEnd), srt, rowId: ROW.rowId, videoTitle: TITLE } }];