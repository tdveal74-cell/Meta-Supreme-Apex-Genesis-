'use strict';
/**
 * Render worker defect tests.
 *
 * These pin what the BUILDERS emit. They do not run ffmpeg, so they prove the
 * argv and the filter graph are the intended ones; they do not prove the pixels
 * or the samples. The ffmpeg-level acceptance tests are in DEPLOY.md and have to
 * be run on the box. That split is deliberate and is stated rather than blurred.
 *
 *   node jobs.test.js
 */
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const J = require('./jobs.js');

const ROOT = fs.mkdtempSync(path.join(os.tmpdir(), 'tsws-worker-test-'));
J.setRoot(ROOT);
// presenter_composite reads a base track's container tags with ffprobe, which
// these tests never run. The stub answers from TAGS, keyed by absolute path,
// and every other file reads as untagged. Guarded so the negative control's
// pre-Voice-Lab fixture, which has no setter, still loads.
const TAGS = new Map();
// A file's own length and container, when a test needs them to differ from
// what its tag says. Otherwise the length is the tag's and the container mp4.
const DURS = new Map();
const FMTS = new Map();
const stubReader = (f) => {
  const c = TAGS.get(f);
  let d = DURS.get(f);
  if (d === undefined && typeof c === 'string') { try { d = JSON.parse(c.slice(20)).duration; } catch (_) { /* unreadable on purpose */ } }
  const dur = String(d === undefined ? 60 : d);
  return { format: { format_name: FMTS.get(f) || 'mov,mp4,m4a,3gp,3g2,mj2', duration: dur, tags: c === undefined ? {} : { comment: c } },
           streams: [{ duration: dur }] };
};
if (J.setTagReader) J.setTagReader(stubReader);
const touch = (rel) => {
  const abs = path.join(ROOT, rel);
  fs.mkdirSync(path.dirname(abs), { recursive: true });
  fs.writeFileSync(abs, 'x');
  return rel;
};

const mk = () => ({ narration: touch('a/nar.wav'), bed: touch('a/bed.wav'), output: 'a/mix.wav' });

let pass = 0, fail = 0;
const QUEUE = [];
/**
 * Queue a test. fn may be sync or return a promise; either way it is AWAITED.
 * An earlier version called fn() and ignored the returned promise, so a failing
 * async assertion became an unhandled rejection and was counted as a pass. The
 * scan_drop test passed against the known-defective original that way, which is
 * the exact shape of a green that means nothing.
 */
function t(name, fn) { QUEUE.push([name, fn]); }
function section(name) { QUEUE.push([name, null]); }

/**
 * Evaluate an ffmpeg expression string using ffmpeg's documented semantics for
 * the three functions these envelopes use. This is a model of the evaluator,
 * not ffmpeg itself, and is only used to compare two expressions against each
 * other -- both are run through the same model, so a modelling error cancels.
 */
function ffeval(expr, t) {
  const js = expr.replace(/\bmax\(/g, 'Math.max(').replace(/\bmin\(/g, 'Math.min(');
  // eslint-disable-next-line no-new-func
  return Function('t', 'lt', 'iff', `return (${js.replace(/\bif\(/g, 'iff(')});`)(
    t, (a, b) => (a < b ? 1 : 0), (c, a, b) => (c ? a : b));
}

section('\n-- F1: a still must be HELD, not emitted as one frame --');
t('3 stills + 1 clip report as 3 stills, 1 clip, 21.5s', () => {
  const shots = [
    { path: touch('plates/a.jpg'), in: 0, out: 6 },
    { path: touch('plates/b.png'), in: 0, out: 6 },
    { path: touch('plates/c.jpeg'), in: 0, out: 6 },
    { path: touch('plates/motion.mp4'), in: 0, out: 6.5 },
  ];
  const b = J.JOBS.assemble_cut.build({ shots, output: 'out/cut.mp4', crossfade: 1.0 });
  const r = b.parse();
  assert.strictEqual(r.stills, 3, 'stills');
  assert.strictEqual(r.clips, 1, 'clips');
  assert.strictEqual(r.fps, 24, 'fps');
  assert.strictEqual(r.normalized_to, '3840x2160', 'normalized_to');
  // 6+6+6+6.5 = 24.5, minus 3 crossfades of 1.0 => 21.5, exactly the audit's
  // end-to-end number (516 frames / 21.500000s at 24fps).
  assert.strictEqual(r.expected_duration, 21.5, 'expected_duration');
  assert.strictEqual(r.expected_duration * r.fps, 516, 'frames');
});

t('a 6s still at 24fps emits loop=loop=143 (144 frames), not one frame', () => {
  const shots = [{ path: touch('plates/a.jpg'), in: 0, out: 6 },
                 { path: touch('plates/b.jpg'), in: 0, out: 6 }];
  const b = J.JOBS.assemble_cut.build({ shots, output: 'out/c.mp4' });
  const fc = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(fc.includes('loop=loop=143:size=1:start=0'), 'loop count: ' + fc.slice(0, 200));
  assert.ok(fc.includes('setpts=N/24/TB'), 'setpts');
});

t('REGRESSION: a still is never handed to trim=start (the 1-frame defect)', () => {
  const shots = [{ path: touch('plates/only.jpg'), in: 0, out: 6 },
                 { path: touch('plates/two.jpg'), in: 0, out: 6 }];
  const b = J.JOBS.assemble_cut.build({ shots, output: 'out/c.mp4' });
  const fc = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(!fc.includes('trim=start='), 'still went through trim: ' + fc.slice(0, 200));
});

section('\n-- F2: geometry normalised before xfade --');
t('every shot carries scale+pad+setsar before xfade', () => {
  const shots = [{ path: touch('p/a.jpg'), in: 0, out: 6 },
                 { path: touch('p/m.mov'), in: 0, out: 6 }];
  const b = J.JOBS.assemble_cut.build({ shots, output: 'out/c.mp4', width: 1920, height: 1080, fps: 30 });
  const fc = b.argv[b.argv.indexOf('-filter_complex') + 1];
  const norms = fc.match(/force_original_aspect_ratio=decrease/g) || [];
  assert.strictEqual(norms.length, 2, 'one normalise per shot, got ' + norms.length);
  assert.ok(fc.includes('pad=1920:1080'), 'pad geometry');
  assert.ok(fc.includes('setsar=1'), 'setsar');
  assert.ok(!fc.includes('crop='), 'must pad, never crop');
  assert.strictEqual(b.parse().normalized_to, '1920x1080');
});

section('\n-- A1: the gain envelope, against the EP01 reference --');
t('envelope matches the reference nested-if at every sampled t', () => {
  const env = J.gainEnvelope([{ s: 544.0, e: 548.0 }], 0.4);
  // The reference expression from EP01_AUDIO_DEFECT_8AUG2026, verbatim shape.
  const ref = "if(lt(t,543.600),1,if(lt(t,544.000),(544.000-t)/0.4," +
              "if(lt(t,548.000),0,if(lt(t,548.400),(t-548.000)/0.4,1))))";
  let worst = 0, at = null;
  for (let x = 540; x <= 552; x += 0.0005) {
    const d = Math.abs(ffeval(env, x) - ffeval(ref, x));
    if (d > worst) { worst = d; at = x; }
  }
  assert.ok(worst < 1e-9, `max divergence ${worst} at t=${at}`);
  console.log(`        max divergence ${worst} over 540..552s at 0.5ms steps`);
});

t('envelope is EXACTLY 1 outside the window (a numerical no-op)', () => {
  const env = J.gainEnvelope([{ s: 544.0, e: 548.0 }], 0.4);
  for (const x of [0, 1, 100, 400, 543.5, 543.6, 548.4, 600, 880.9]) {
    assert.strictEqual(ffeval(env, x), 1, `gain at t=${x} was ${ffeval(env, x)}`);
  }
});

t('the gap is true silence in the file the job actually writes', () => {
  const env = J.gainEnvelope([{ s: 544.0, e: 548.0 }], 0.4);
  // Inside the gap the expression is exactly zero. At the two instants where a
  // ramp meets the gap boundary, binary rounding of 543.600000 leaves a residual
  // of about 5.7e-14, which is -265 dBFS. duck_mix writes pcm_s24le, whose LSB
  // is 2^-23 (-138.5 dBFS), so that residual quantises to exactly 0 in the
  // output. Asserting against the 24-bit floor is the honest test; asserting
  // exact float zero at the boundary would be testing the arithmetic, not the
  // silence.
  const LSB24 = Math.pow(2, -23);
  for (const x of [544.0, 544.5, 546, 547.99, 548.0]) {
    const g = ffeval(env, x);
    assert.ok(g < LSB24, `gain at t=${x} was ${g}, above the 24-bit floor`);
    assert.strictEqual(Math.round(g * Math.pow(2, 23)), 0, `t=${x} does not quantise to silence`);
  }
  for (const x of [545, 546, 547]) assert.strictEqual(ffeval(env, x), 0, `t=${x} not exactly 0`);
});

t('REGRESSION: the old afade pair silences everything, the envelope does not', () => {
  // Model the old chain: afade=t=out holds zero after its ramp; afade=t=in
  // multiplies by zero before its start. Composed, on the EP01 numbers.
  const oldGain = (x) => {
    const out = x < 543.6 ? 1 : x < 544.0 ? (544.0 - x) / 0.4 : 0;
    const inn = x < 548.0 ? 0 : x < 548.4 ? (x - 548.0) / 0.4 : 1;
    return out * inn;
  };
  assert.strictEqual(oldGain(700), 0, 'the old chain should be dead at 700s');
  assert.strictEqual(oldGain(870), 0, 'the old chain should be dead at 870s');
  const env = J.gainEnvelope([{ s: 544.0, e: 548.0 }], 0.4);
  assert.strictEqual(ffeval(env, 700), 1, 'the envelope must be alive at 700s');
  assert.strictEqual(ffeval(env, 870), 1, 'the envelope must be alive at 870s');
});

t('N disjoint guards stay inside [0,1]', () => {
  const env = J.gainEnvelope([{ s: 100, e: 104 }, { s: 200, e: 202 }, { s: 300, e: 310 }], 0.4);
  for (let x = 0; x <= 400; x += 0.01) {
    const g = ffeval(env, x);
    assert.ok(g >= 0 && g <= 1, `gain ${g} at t=${x}`);
  }
  assert.strictEqual(ffeval(env, 102), 0);
  assert.strictEqual(ffeval(env, 201), 0);
  assert.strictEqual(ffeval(env, 305), 0);
  assert.strictEqual(ffeval(env, 150), 1);
});

section('\n-- A1/A2: what duck_mix actually emits --');
t('no afade anywhere in the duck_mix filter', () => {
  const b = J.JOBS.duck_mix.build({ ...mk(), guards: [{ start: 544, end: 548 }] });
  const fc = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(!fc.includes('afade'), 'afade survived: ' + fc);
  assert.ok(fc.includes("volume=eval=frame:volume='"), 'envelope missing');
});

t('pinned: apad plus -t, at the planned length', () => {
  const b = J.JOBS.duck_mix.build({ ...mk(), guards: [], duration: 880.907 });
  const fc = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(fc.includes('apad[mix]'), 'apad missing');
  assert.strictEqual(b.argv[b.argv.indexOf('-t') + 1], '880.907000');
  assert.strictEqual(b.parse().pinned, true);
});

t('unpinned: NO apad, because apad without -t never terminates', () => {
  const b = J.JOBS.duck_mix.build({ ...mk(), guards: [] });
  const fc = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(!fc.includes('apad'), 'apad without -t would hang forever');
  assert.ok(!b.argv.includes('-t'), '-t present without a planned length');
  assert.strictEqual(b.parse().pinned, false, 'an unpinned mix must say so');
});

t('overlapping guards are refused, not silently summed', () => {
  assert.throws(() => J.JOBS.duck_mix.build({
    ...mk(), guards: [{ start: 100, end: 200 }, { start: 150, end: 250 }],
  }), /overlap/);
});

section('\n-- F4: scan_drop finds a manifest above two levels --');
t('depth 1 and depth 2 both found; .done skipped; root and depth reported', async () => {
  fs.mkdirSync(path.join(ROOT, 'drop/EP01'), { recursive: true });
  fs.writeFileSync(path.join(ROOT, 'drop/EP01/manifest.json'), '{}');
  fs.mkdirSync(path.join(ROOT, 'drop/season2/EP07'), { recursive: true });
  fs.writeFileSync(path.join(ROOT, 'drop/season2/EP07/manifest.json'), '{}');
  fs.mkdirSync(path.join(ROOT, 'drop/EP00'), { recursive: true });
  fs.writeFileSync(path.join(ROOT, 'drop/EP00/manifest.json'), '{}');
  fs.writeFileSync(path.join(ROOT, 'drop/EP00/.done'), '');
  const b = J.JOBS.scan_drop.build({ drop_dir: 'drop' });
  return b.native().then(r => {
    assert.strictEqual(r.count, 2, 'found ' + JSON.stringify(r.episodes));
    assert.ok(r.episodes.includes('drop/EP01'), 'depth-1 manifest missed (the F4 defect)');
    assert.ok(r.episodes.includes('drop/season2/EP07'), 'depth-2 manifest missed');
    assert.strictEqual(r.skipped_done, 1, 'skipped_done');
    assert.strictEqual(r.root, 'drop');
    assert.strictEqual(r.scanned_depth, 3);
  });
});

section('\n-- xfade offsets, which nothing pinned before --');
t('offsets tile the timeline and never run past their own input', () => {
  const shots = [
    { path: touch('x/a.jpg'), in: 0, out: 6 },
    { path: touch('x/b.jpg'), in: 0, out: 5 },
    { path: touch('x/c.jpg'), in: 0, out: 7 },
  ];
  const xf = 1.0;
  const b = J.JOBS.assemble_cut.build({ shots, output: 'x/cut.mp4', crossfade: xf, fps: 24 });
  const fc = b.argv[b.argv.indexOf('-filter_complex') + 1];
  const offsets = [...fc.matchAll(/xfade=transition=fade:duration=[\d.]+:offset=([\d.]+)/g)]
    .map(m => Number(m[1]));
  // Join k must start one crossfade before the running end of everything
  // already joined, or the transition reaches past the end of its first input.
  assert.deepStrictEqual(offsets, [5, 9], 'offsets were ' + JSON.stringify(offsets));
  assert.strictEqual(b.parse().expected_duration, 6 + 5 + 7 - 2 * xf);
});

t('REGRESSION: dropping the crossfade from the offset is caught', () => {
  // The mutation that previously passed 16/16: offset += dur instead of dur - xf.
  // Pinning the exact offsets is what makes that mutation fail.
  const shots = [{ path: touch('x/a.jpg'), in: 0, out: 6 },
                 { path: touch('x/b.jpg'), in: 0, out: 6 }];
  const b = J.JOBS.assemble_cut.build({ shots, output: 'x/c2.mp4', crossfade: 1.5, fps: 24 });
  const fc = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(fc.includes('offset=4.500'), 'offset should be 6 - 1.5 = 4.5, got: ' +
    (fc.match(/offset=[\d.]+/) || ['none'])[0]);
});

t('a still contributes its QUANTISED length to the offsets, not the requested one', () => {
  // 5.01s at 24fps is 120.24 frames, emitted as 120 = 5.0s. If the offset used
  // the requested 5.01 it would drift from the picture by 10ms per join.
  const shots = [{ path: touch('x/q1.jpg'), in: 0, out: 5.01 },
                 { path: touch('x/q2.jpg'), in: 0, out: 5.01 }];
  const b = J.JOBS.assemble_cut.build({ shots, output: 'x/q.mp4', crossfade: 1.0, fps: 24 });
  const fc = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(fc.includes('loop=loop=119:'), 'expected 120 frames: ' + fc.slice(0, 120));
  assert.ok(fc.includes('offset=4.000'), 'offset should be 5.0 - 1.0, not 5.01 - 1.0');
  const r = b.parse();
  assert.strictEqual(r.expected_duration, 9);
  assert.strictEqual(r.exact, true, 'an all-still assembly is frame exact');
  assert.strictEqual(r.expected_duration * r.fps, 216, 'must be a whole frame count');
});

section('\n-- conform_grain: the protected silence provision --');
const cg = (extra) => J.JOBS.conform_grain.build(Object.assign({
  input: touch('cg/in.mp4'), output: 'cg/out.mp4', has_audio: true,
}, extra));

t('a cut landing INSIDE a protected silence is refused', () => {
  // This is a performance hold that pipeline 02 deliberately preserved. The
  // guard was deleted in a mutation test and every test still passed.
  assert.throws(() => cg({
    keep_segments: [{ start: 0, end: 545 }, { start: 560, end: 600 }],
    protected_windows: [{ start: 544, end: 548 }],
  }), /protected silence/, 'a boundary at 545 inside 544..548 must be refused');
});

t('a cut passing cleanly THROUGH a whole window is allowed', () => {
  const b = cg({
    keep_segments: [{ start: 0, end: 600 }],
    protected_windows: [{ start: 544, end: 548 }],
  });
  assert.ok(Array.isArray(b.argv), 'a clean pass-through must build');
});

t('M1 REGRESSION: apad is never emitted without an ending to pad to', () => {
  // apad with pad_dur=0 and no -t pads forever. The same defect this file
  // already fixed in duck_mix was still live two jobs over.
  const b = cg({ keep_segments: [{ start: 0, end: 25 }] });
  const fc = b.argv[b.argv.indexOf('-filter_complex') + 1];
  const hasT = b.argv.includes('-t') || b.argv.includes('-shortest');
  assert.ok(!fc.includes('apad') || hasT,
    'apad emitted with no -t and no -shortest: ' + fc);
});

section('\n-- M6: duck_mix must be able to match its container --');
t('the codec is selectable, so pcm does not get forced into a flac container', () => {
  const b = J.JOBS.duck_mix.build({ ...mk(), guards: [], codec: 'flac', output: 'a/m.flac' });
  assert.strictEqual(b.argv[b.argv.indexOf('-c:a') + 1], 'flac');
  const d = J.JOBS.duck_mix.build({ ...mk(), guards: [] });
  assert.strictEqual(d.argv[d.argv.indexOf('-c:a') + 1], 'pcm_s24le', 'default unchanged');
  assert.throws(() => J.JOBS.duck_mix.build({ ...mk(), guards: [], codec: 'mp3' }), /codec/);
});

section('\n-- M2: safePath must resolve symlinks, not just strings --');
t('a symlink inside the work root cannot reach outside it', () => {
  const link = path.join(ROOT, 'escape');
  try { fs.unlinkSync(link); } catch { /* first run */ }
  fs.symlinkSync(os.tmpdir(), link);
  assert.throws(() => J.JOBS.read_text.build({ path: 'escape/anything' }),
    /escapes the work root|no such file/,
    'a symlinked path resolved outside the root was accepted');
  assert.throws(() => J.JOBS.exists.build({ path: 'escape/passwd' }),
    /escapes the work root/);
  fs.unlinkSync(link);
});

section('\n-- M3: https is a scheme check, not a destination check --');
t('private, loopback and link-local destinations are refused', () => {
  for (const u of ['https://127.0.0.1/x', 'https://localhost/x', 'https://10.0.0.5/x',
                   'https://169.254.169.254/latest/meta-data/', 'https://192.168.1.1/x',
                   'https://172.16.0.1/x', 'https://[::1]/x', 'https://100.64.0.1/x']) {
    assert.throws(() => J.JOBS.http_download.build({ url: u, output: 'd/x.bin' }),
      /private or loopback/, u + ' was accepted');
  }
});
t('an ordinary public https URL still works', () => {
  const b = J.JOBS.http_download.build({ url: 'https://example.com/a.mp4', output: 'd/a.mp4' });
  assert.ok(b.native, 'a public URL must still build');
});

section('\n-- H1: read_text must not block the event loop on a device --');
t('a non-regular file is refused rather than opened', async () => {
  const fifo = path.join(ROOT, 'r', 'dir_not_file');
  fs.mkdirSync(fifo, { recursive: true });
  const b = J.JOBS.read_text.build({ path: 'r/dir_not_file' });
  await assert.rejects(() => b.native(), /not a regular file/);
});

section('\n-- P1: presenter_composite, the TQO presenter build --');
const pc = () => ({
  avatar: touch('p/avatar.mp4'), output: 'p/master.mp4',
  cutaways: [
    { path: touch('p/cut-a.mp4'), start: 4, end: 10 },
    { path: touch('p/cut-b.mp4'), start: 20, end: 26.5, in: 3 },
  ],
  captions: touch('p/captions.srt'), bed: touch('p/bed.mp3'), duration: 60,
});
t('inputs are avatar, cutaways in window order, then the looped bed', () => {
  const b = J.JOBS.presenter_composite.build(pc());
  assert.strictEqual(b.bin, 'ffmpeg');
  const a = b.argv;
  const ins = [];
  for (let i = 0; i < a.length; i++) if (a[i] === '-i') ins.push(a[i + 1]);
  assert.strictEqual(ins.length, 4, JSON.stringify(ins));
  assert.ok(ins[0].endsWith('p/avatar.mp4'));
  assert.ok(ins[1].endsWith('p/cut-a.mp4'));
  assert.ok(ins[2].endsWith('p/cut-b.mp4'));
  assert.ok(ins[3].endsWith('p/bed.mp3'));
  const bedI = a.indexOf(ins[3]);
  assert.deepStrictEqual(a.slice(bedI - 3, bedI), ['-stream_loop', '-1', '-i'], 'the bed is not looped');
  assert.ok(a.includes('-nostdin'));
});
t('each cutaway is delayed to its window and gated by enable=between', () => {
  const b = J.JOBS.presenter_composite.build(pc());
  const g = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(g.includes('setpts=PTS+4.000000/TB[c0]'), g);
  assert.ok(g.includes('setpts=PTS+20.000000/TB[c1]'), g);
  assert.ok(g.includes("[base][c0]overlay=0:0:eof_action=pass:enable='between(t,4.000000,10.000000)'[v1]"), g);
  assert.ok(g.includes("[v1][c1]overlay=0:0:eof_action=pass:enable='between(t,20.000000,26.500000)'[v2]"), g);
  // the second clip is trimmed from its own `in`, for the window length
  assert.ok(g.includes('[2:v]trim=start=3.000000:end=9.500000,'), g);
  // a short clip holds its last frame for the window rather than leaving a hole
  assert.ok(g.includes('tpad=stop_mode=clone:stop_duration=6.500000,trim=end=6.500000'), g);
  // and fades on alpha at both ends
  assert.ok(g.includes('fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st=6.200000:d=0.3:alpha=1'), g);
});
t('captions burn in after the last overlay; no captions means null, never a missing label', () => {
  const b = J.JOBS.presenter_composite.build(pc());
  const g = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(/\[v2\]subtitles=filename=[^:]+p\/captions\.srt:force_style='FontSize=22,Outline=2,Shadow=0,MarginV=60'\[vout\]/.test(g), g);
  const nb = J.JOBS.presenter_composite.build({ ...pc(), captions: undefined });
  const g2 = nb.argv[nb.argv.indexOf('-filter_complex') + 1];
  assert.ok(g2.includes('[v2]null[vout]'), g2);
  assert.ok(!g2.includes('subtitles='), g2);
});
t('the bed is ducked under the avatar audio with the duck_mix chain and pinned to duration', () => {
  const b = J.JOBS.presenter_composite.build(pc());
  const g = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(g.includes('[0:a]aresample=48000,asplit=2[nar][key]'), g);
  assert.ok(g.includes('[3:a]aresample=48000[bedg]'), g);
  assert.ok(g.includes('[bedg][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400:makeup=1[duck]'), g);
  assert.ok(g.includes('[nar][duck]amix=inputs=2:duration=first:dropout_transition=0:weights=1 0.35[mixraw];[mixraw]apad[mix]'), g);
  assert.ok(!/afade/.test(g), 'afade crept in');
  const tI = b.argv.indexOf('-t');
  assert.ok(tI > 0 && b.argv[tI + 1] === '60.000000', 'not pinned');
  assert.ok(tI < b.argv.length - 2, '-t must precede the output');
  assert.deepStrictEqual(b.argv.slice(b.argv.indexOf('-map'), b.argv.indexOf('-map') + 4), ['-map', '[vout]', '-map', '[mix]']);
});
t('a separate narration file replaces the avatar audio as voice and key', () => {
  const b = J.JOBS.presenter_composite.build({ ...pc(), narration: touch('p/voice.mp3') });
  const g = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(g.includes('[4:a]aresample=48000,asplit=2[nar][key]'), g);
  assert.ok(!g.includes('[0:a]'), g);
  assert.strictEqual(b.parse().narration, 'separate file');
});
t('no bed and no pin: the avatar audio passes straight through', () => {
  const b = J.JOBS.presenter_composite.build({ ...pc(), bed: undefined, duration: undefined });
  const g = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(g.endsWith('[0:a]aresample=48000[mix]'), g);
  assert.ok(!g.includes('sidechaincompress'), g);
  assert.ok(!b.argv.includes('-stream_loop'));
  assert.ok(!b.argv.includes('-t'));
  assert.strictEqual(b.parse().pinned, false);
});
t('fade=0 emits no fade filter at all (d=0 would mean 25 frames, not none)', () => {
  const b = J.JOBS.presenter_composite.build({ ...pc(), fade: 0 });
  const g = b.argv[b.argv.indexOf('-filter_complex') + 1];
  assert.ok(!/fade=t=/.test(g), g);
});
t('parse reports what was composited', () => {
  const r = J.JOBS.presenter_composite.build(pc()).parse();
  assert.deepStrictEqual(r, { output: 'p/master.mp4', cutaways: 2, captions: true, bed: true,
    narration: 'avatar audio', pinned: true, planned_duration: 60, fps: 25, normalized_to: '1920x1080',
    layout: 'full', split_y: null, emphasis: 0, emphasis_cards: 0, emphasis_captions: false, loudness: null,
    full_cutaways: 2, must_cover: 0 });
});
t('overlapping windows are refused at submit', () => {
  const p = pc(); p.cutaways[1].start = 9;
  assert.throws(() => J.JOBS.presenter_composite.build(p), /windows overlap/);
});
t('a window past the planned duration is refused', () => {
  const p = pc(); p.cutaways[1].end = 61;
  assert.throws(() => J.JOBS.presenter_composite.build(p), /past the planned/);
});
t('a window shorter than two fades is refused', () => {
  const p = pc(); p.cutaways[0].end = 4.5;
  assert.throws(() => J.JOBS.presenter_composite.build(p), /shorter than two fades/);
});
t('end <= start, a missing clip, and a 65th cutaway are refused', () => {
  const p1 = pc(); p1.cutaways[0].end = 4;
  assert.throws(() => J.JOBS.presenter_composite.build(p1), /end must exceed start/);
  const p2 = pc(); p2.cutaways[0].path = 'p/absent.mp4';
  assert.throws(() => J.JOBS.presenter_composite.build(p2), /no such file/);
  const p3 = { ...pc(), cutaways: Array.from({ length: 65 }, (_, i) => ({ path: 'p/cut-a.mp4', start: i * 10, end: i * 10 + 5 })), duration: undefined };
  assert.throws(() => J.JOBS.presenter_composite.build(p3), /too many/);
});
t('a captions path or style the filter string cannot take verbatim is refused, not escaped', () => {
  const p1 = { ...pc(), captions: touch("p/it's.srt") };
  assert.throws(() => J.JOBS.presenter_composite.build(p1), /rename it/);
  const p2 = { ...pc(), caption_style: "FontSize=22'[vout];[0:v]null" };
  assert.throws(() => J.JOBS.presenter_composite.build(p2), /caption_style/);
});
t('a colon in the captions path is refused: it is the character that ends the filename option', () => {
  const p1 = { ...pc(), captions: touch('p/cue:1.srt') };
  assert.throws(() => J.JOBS.presenter_composite.build(p1), /rename it/);
  const p2 = { ...pc(), caption_style: 'FontSize=22;Outline=2' };
  assert.throws(() => J.JOBS.presenter_composite.build(p2), /caption_style/);
});
t('cutaways or emphasis that are present and not an array are refused, never defaulted to none', () => {
  const asString = { ...pc(), cutaways: JSON.stringify(pc().cutaways) };
  assert.throws(() => J.JOBS.presenter_composite.build(asString), /cutaways: must be an array/);
  const asObject = { ...pc(), cutaways: { path: 'p/cut-a.mp4', start: 1, end: 3 } };
  assert.throws(() => J.JOBS.presenter_composite.build(asObject), /cutaways: must be an array/);
  const emph = { ...pc(), layout: 'stacked', width: 1080, height: 1920, emphasis: '[{"start":1,"end":2}]' };
  assert.throws(() => J.JOBS.presenter_composite.build(emph), /emphasis: must be an array/);
});
t('a stacked cutaway with full as a string is refused instead of silently becoming a zone cutaway', () => {
  const p = { ...pc(), layout: 'stacked', width: 1080, height: 1920 };
  p.cutaways[0].full = 'true';
  assert.throws(() => J.JOBS.presenter_composite.build(p), /full: must be true or false/);
});
t('the avatar and the output are confined to the work root', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), avatar: '../../etc/passwd' }), /no such file|escapes/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), output: '../out.mp4' }), /escapes the work root/);
});

section('\n-- P2: presenter_composite stacked, the Anchor Desk Short --');
const st = () => ({
  avatar: touch('q/avatar.mp4'), output: 'q/short.mp4', layout: 'stacked', width: 1080, height: 1920,
  cutaways: [
    { path: touch('q/cut-a.mp4'), start: 2, end: 6 },
    { path: touch('q/cut-b.mp4'), start: 8, end: 11, full: true },
  ],
  emphasis: [{ start: 6.5, end: 7.5 }],
  captions: touch('q/captions.srt'), duration: 12,
});
const graph = (b) => b.argv[b.argv.indexOf('-filter_complex') + 1];
t('the presenter is cropped chest up into the bottom 35 percent over a plate the size of the canvas', () => {
  const g = graph(J.JOBS.presenter_composite.build(st()));
  assert.ok(g.includes('[0:v]split=2[a_desk][a_full]'), g);
  assert.ok(g.includes('[a_desk]scale=1080:670:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:670,'), g);
  assert.ok(g.includes('color=c=#0A1628:s=1080x1920:r=25[plate]'), g);
  assert.ok(g.includes('[plate][head]overlay=0:1250:shortest=1[base]'), g);
});
t('a zone cutaway is letterboxed into the top 1250 px; a full cutaway fills and crops the whole canvas', () => {
  const g = graph(J.JOBS.presenter_composite.build(st()));
  assert.ok(g.includes('[1:v]trim=start=0.000000:end=4.000000,setpts=PTS-STARTPTS,scale=1080:1250:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1250:'), g);
  assert.ok(g.includes('[2:v]trim=start=0.000000:end=3.000000,setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,'), g);
});
t('emphasis windows put the full-frame head on top of everything, gated by between()', () => {
  const g = graph(J.JOBS.presenter_composite.build(st()));
  assert.ok(g.includes('[a_full]scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,'), g);
  assert.ok(g.includes("[v2][headfull]overlay=0:0:eof_action=pass:enable='between(t,6.500000,7.500000)'[vemph]"), g);
  assert.ok(g.includes('[vemph]subtitles='), 'captions must burn in after the emphasis layer');
  const none = graph(J.JOBS.presenter_composite.build({ ...st(), emphasis: [] }));
  assert.ok(none.includes('[a_full]nullsink'), 'the unused split branch must be sunk, or ffmpeg refuses the graph');
  assert.ok(!none.includes('headfull'), none);
});
t('stacked captions default to the band between the zones in libass script units', () => {
  const g = graph(J.JOBS.presenter_composite.build(st()));
  assert.ok(g.includes("force_style='FontSize=12,Bold=1,Outline=2,Shadow=0,MarginV=92'"), g);
});
t('parse reports the layout, the emphasis count and the full cutaways', () => {
  const r = J.JOBS.presenter_composite.build(st()).parse();
  assert.strictEqual(r.layout, 'stacked'); assert.strictEqual(r.emphasis, 1); assert.strictEqual(r.full_cutaways, 1);
  assert.strictEqual(r.normalized_to, '1080x1920');
});
t('stacked refuses a landscape canvas, a bad plate colour, overlapping or late emphasis, and emphasis in the full layout', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), width: 1920, height: 1080 }), /portrait canvas/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), plate_color: 'navy' }), /plate_color/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), emphasis: [{ start: 1, end: 3 }, { start: 2, end: 4 }] }), /emphasis: windows overlap/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), emphasis: [{ start: 11, end: 13 }] }), /past the planned/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), layout: 'full', width: 1920, height: 1080 }), /only meaningful with layout stacked/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), layout: 'sideways' }), /layout: must be one of/);
});
t('the full layout ignores the full flag and never splits the avatar', () => {
  const g = graph(J.JOBS.presenter_composite.build({ ...st(), layout: 'full', width: 1920, height: 1080, emphasis: [] }));
  assert.ok(!g.includes('split=2'), g);
  assert.ok(!g.includes('color=c='), g);
  assert.ok(g.includes('[2:v]trim=start=0.000000:end=3.000000,setpts=PTS-STARTPTS,scale=1920:1080:force_original_aspect_ratio=decrease'), g);
});

section('\n-- P3: the 50/50 split Tee ruled for native Shorts, 2026-10-31 --');
t('split 0.5 puts the seam at 960: presenter fills 1080x960 at y 960, a zone cutaway letterboxes into 1080x960', () => {
  const b = J.JOBS.presenter_composite.build({ ...st(), split: 0.5 });
  const g = graph(b);
  assert.ok(g.includes('[a_desk]scale=1080:960:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:960,'), g);
  assert.ok(g.includes('[plate][head]overlay=0:960:shortest=1[base]'), g);
  assert.ok(g.includes('[1:v]trim=start=0.000000:end=4.000000,setpts=PTS-STARTPTS,scale=1080:960:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:960:'), g);
  assert.ok(g.includes('[2:v]trim=start=0.000000:end=3.000000,setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,'), 'a full cutaway still fills the canvas: ' + g);
  assert.strictEqual(b.parse().split_y, 960);
});
t('the default caption carries the measured 1250-seam offset to the new seam: MarginV 136 at 0.5', () => {
  // 288 * (1 - 960/1920) - 8.4 = 135.6. The measured 92 at the 1250 seam is
  // what the same formula gives there (92.1), so the offset moves with it.
  assert.ok(graph(J.JOBS.presenter_composite.build({ ...st(), split: 0.5 })).includes("force_style='FontSize=12,Bold=1,Outline=2,Shadow=0,MarginV=136'"));
  assert.ok(graph(J.JOBS.presenter_composite.build({ ...st(), split: 1250 / 1920 })).includes('MarginV=92'));
  const own = graph(J.JOBS.presenter_composite.build({ ...st(), split: 0.5, caption_style: 'FontSize=11,BorderStyle=3,MarginV=140' }));
  assert.ok(own.includes("force_style='FontSize=11,BorderStyle=3,MarginV=140'"), 'a caller style is used as given: ' + own);
});
t('no split leaves the stacked argv byte for byte as it was at b9422ef (golden, captured from that commit)', () => {
  const GOLDEN = ["-y","-nostdin","-hide_banner","-loglevel","error","-i","<ROOT>/q/avatar.mp4","-i","<ROOT>/q/cut-a.mp4","-i","<ROOT>/q/cut-b.mp4","-filter_complex","[0:v]split=2[a_desk][a_full];[a_desk]scale=1080:670:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:670,setsar=1,format=yuv420p,fps=25,setpts=PTS-STARTPTS[head];color=c=#0A1628:s=1080x1920:r=25[plate];[plate][head]overlay=0:1250:shortest=1[base];[1:v]trim=start=0.000000:end=4.000000,setpts=PTS-STARTPTS,scale=1080:1250:force_original_aspect_ratio=decrease:flags=lanczos,pad=1080:1250:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p,fps=25,tpad=stop_mode=clone:stop_duration=4.000000,trim=end=4.000000,format=yuva420p,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st=3.700000:d=0.3:alpha=1,setpts=PTS+2.000000/TB[c0];[2:v]trim=start=0.000000:end=3.000000,setpts=PTS-STARTPTS,scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,setsar=1,format=yuv420p,fps=25,tpad=stop_mode=clone:stop_duration=3.000000,trim=end=3.000000,format=yuva420p,fade=t=in:st=0:d=0.3:alpha=1,fade=t=out:st=2.700000:d=0.3:alpha=1,setpts=PTS+8.000000/TB[c1];[base][c0]overlay=0:0:eof_action=pass:enable='between(t,2.000000,6.000000)'[v1];[v1][c1]overlay=0:0:eof_action=pass:enable='between(t,8.000000,11.000000)'[v2];[a_full]scale=1080:1920:force_original_aspect_ratio=increase:flags=lanczos,crop=1080:1920,setsar=1,format=yuv420p,fps=25,setpts=PTS-STARTPTS[headfull];[v2][headfull]overlay=0:0:eof_action=pass:enable='between(t,6.500000,7.500000)'[vemph];[vemph]subtitles=filename=<ROOT>/q/captions.srt:force_style='FontSize=12,Bold=1,Outline=2,Shadow=0,MarginV=92'[vout];[0:a]aresample=48000,apad[mix]","-map","[vout]","-map","[mix]","-r","25","-c:v","libx264","-crf","18","-preset","medium","-pix_fmt","yuv420p","-c:a","aac","-b:a","192k","-metadata","comment=","-movflags","+faststart","-t","12.000000","<ROOT>/q/short.mp4"];
  const real = fs.realpathSync(ROOT);
  const argv = J.JOBS.presenter_composite.build(st()).argv.map(a => a.split(real).join('<ROOT>').split(ROOT).join('<ROOT>'));
  assert.deepStrictEqual(argv, GOLDEN);
});
t('any split lands the seam on an even row, so a square or portrait zone clip can pad', () => {
  // 0.333 and 0.56 gave rows 639 and 1075 and killed ffmpeg at render
  // (exit 234) on a 1080x1080 or 720x1280 zone clip; reproduced and fixed
  // 2026-10-31 on the critic's finding.
  for (const [split, want] of [[0.3, 576], [0.333, 640], [0.5, 960], [0.56, 1076], [0.66, 1268], [0.75, 1440]]) {
    const y = J.JOBS.presenter_composite.build({ ...st(), split }).parse().split_y;
    assert.strictEqual(y, want, `split ${split}`);
    assert.strictEqual(y % 2, 0, `split ${split} gave odd ${y}`);
  }
  for (const H of [1281, 1921, 960]) {
    const y = J.JOBS.presenter_composite.build({ ...st(), height: H, width: 540, split: 0.3111, emphasis: [] }).parse().split_y;
    assert.strictEqual(y % 2, 0, `height ${H} gave odd ${y}`);
  }
});
t('the split range edges: 0.3 and 0.75 accepted, 0.29 and 0.76 refused', () => {
  assert.doesNotThrow(() => J.JOBS.presenter_composite.build({ ...st(), split: 0.3 }));
  assert.doesNotThrow(() => J.JOBS.presenter_composite.build({ ...st(), split: 0.75 }));
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), split: 0.29 }), /split/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), split: 0.76 }), /split/);
});
t('no split reports the 1250 seam and the default caption margin', () => {
  const a = J.JOBS.presenter_composite.build(st());
  assert.ok(graph(a).includes('[plate][head]overlay=0:1250:shortest=1[base]'));
  assert.ok(graph(a).includes('MarginV=92'));
  assert.strictEqual(a.parse().split_y, 1250);
  assert.strictEqual(J.JOBS.presenter_composite.build({ ...st(), layout: 'full', width: 1920, height: 1080, emphasis: [] }).parse().split_y, null);
});
t('split is refused outside the stacked layout, outside 0.3 to 0.75, and as text', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), layout: 'full', width: 1920, height: 1080, emphasis: [], split: 0.5 }), /split: only meaningful with layout stacked/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), split: 0.2 }), /split/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), split: 0.8 }), /split/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), split: 'half' }), /split/);
});

section('\n-- P4: the NCO 30 layout test fixes Tee ruled, 2026-11-01 --');
const st50 = () => ({ ...st(), split: 0.5, cutaways: [{ path: touch('q/cut-a.mp4'), start: 2, end: 6 }],
  emphasis: [{ start: 6.5, end: 7.5, card: touch('q/num01.png'), card_y: 192 }, { start: 9, end: 10 }] });
t('an emphasis card is its own input after the cutaways, laid over the full-frame head inside its window only', () => {
  const b = J.JOBS.presenter_composite.build(st50());
  const g = graph(b);
  const ins = b.argv.filter((a, i) => b.argv[i - 1] === '-i').map(a => path.basename(a));
  assert.deepStrictEqual(ins, ['avatar.mp4', 'cut-a.mp4', 'num01.png']);
  assert.ok(g.includes("[v1][headfull]overlay=0:0:eof_action=pass:enable='between(t,6.500000,7.500000)+between(t,9.000000,10.000000)'[vemph]"), g);
  assert.ok(g.includes('[2:v]trim=end=1.000000,setpts=PTS-STARTPTS,format=rgba,scale=1080:1920:force_original_aspect_ratio=decrease:force_divisible_by=2:flags=lanczos,setsar=1,fps=25,tpad=stop_mode=clone:stop_duration=1.000000,trim=end=1.000000,format=yuva420p,setpts=PTS+6.500000/TB[k0]'), g);
  assert.ok(g.includes("[vemph][k0]overlay=x=(main_w-overlay_w)/2:y=192:eof_action=pass:enable='between(t,6.500000,7.500000)'[vk0]"), g);
  assert.ok(g.includes('[vk0]subtitles='), 'captions burn in after the card: ' + g);
  assert.ok(!g.includes('[k1]'), 'the window with no card gets no card layer');
  const r = b.parse();
  assert.strictEqual(r.emphasis, 2); assert.strictEqual(r.emphasis_cards, 1);
});
t('a card moves the bed and narration inputs along by one, and the audio graph names the moved indices', () => {
  const b = J.JOBS.presenter_composite.build({ ...st50(), bed: touch('q/bed.wav'), narration: touch('q/nar.wav') });
  const g = graph(b);
  const ins = b.argv.filter((a, i) => b.argv[i - 1] === '-i').map(a => path.basename(a));
  assert.deepStrictEqual(ins, ['avatar.mp4', 'cut-a.mp4', 'num01.png', 'bed.wav', 'nar.wav']);
  assert.ok(g.includes('[4:a]aresample=48000,asplit=2[nar][key];[3:a]aresample=48000[bedg]'), g);
});
t('a card is refused when its file is missing, its card_y is off the canvas, or card_y comes without a card', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), emphasis: [{ start: 6.5, end: 7.5, card: 'q/nope.png' }] }), /no such file/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), emphasis: [{ start: 6.5, end: 7.5, card: touch('q/num01.png'), card_y: 1920 }] }), /card_y/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), emphasis: [{ start: 6.5, end: 7.5, card: touch('q/num01.png'), card_y: -1 }] }), /card_y/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), emphasis: [{ start: 6.5, end: 7.5, card_y: 100 }] }), /only meaningful with a card/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), emphasis: [{ start: 6.5, end: 7.5, card: '../../etc/passwd' }] }), /no such file|escapes/);
});
t('emphasis_caption_style captions the picture twice and takes the second copy inside the emphasis windows only', () => {
  const b = J.JOBS.presenter_composite.build({ ...st50(), caption_style: 'FontSize=10,BorderStyle=3,MarginV=136', emphasis_caption_style: 'FontSize=10,BorderStyle=3,MarginV=60' });
  const g = graph(b);
  assert.ok(g.includes('[vk0]split=2[cap_a][cap_b]'), g);
  assert.ok(g.includes("[cap_a]subtitles=filename="), g);
  assert.ok(g.includes(":force_style='FontSize=10,BorderStyle=3,MarginV=136'[cap_s]"), g);
  assert.ok(g.includes(":force_style='FontSize=10,BorderStyle=3,MarginV=60'[cap_e]"), g);
  assert.ok(g.includes("[cap_s][cap_e]overlay=0:0:eof_action=pass:enable='between(t,6.500000,7.500000)+between(t,9.000000,10.000000)'[vout]"), g);
  assert.strictEqual(b.parse().emphasis_captions, true);
});
t('emphasis_caption_style is refused without captions, without emphasis, or with a character the filter cannot take', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), captions: undefined, emphasis_caption_style: 'MarginV=60' }), /only meaningful with captions/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), emphasis: [], emphasis_caption_style: 'MarginV=60' }), /only meaningful with emphasis/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), emphasis_caption_style: "MarginV=60':x" }), /emphasis_caption_style: only letters/);
});
t('loudness adds one loudnorm and a resample back to 48 kHz on the finished mix, before the pad', () => {
  const b = J.JOBS.presenter_composite.build({ ...st50(), loudness: -14 });
  assert.ok(graph(b).endsWith('[0:a]aresample=48000,loudnorm=I=-14:TP=-1:LRA=11,aresample=48000,apad[mix]'), graph(b));
  assert.deepStrictEqual(b.parse().loudness, { integrated: -14, true_peak: -1 });
  const unpinned = graph(J.JOBS.presenter_composite.build({ ...st50(), loudness: -16, true_peak: -2, duration: undefined }));
  assert.ok(unpinned.endsWith('[0:a]aresample=48000,loudnorm=I=-16:TP=-2:LRA=11,aresample=48000[mix]'), unpinned);
  const bed = graph(J.JOBS.presenter_composite.build({ ...st50(), loudness: -14, bed: touch('q/bed.wav') }));
  assert.ok(bed.endsWith('weights=1 0.35[mixraw];[mixraw]anull,loudnorm=I=-14:TP=-1:LRA=11,aresample=48000,apad[mix]'), bed);
  const bedUnpinned = graph(J.JOBS.presenter_composite.build({ ...st50(), loudness: -14, bed: touch('q/bed.wav'), duration: undefined }));
  assert.ok(bedUnpinned.endsWith('weights=1 0.35[mixraw];[mixraw]anull,loudnorm=I=-14:TP=-1:LRA=11,aresample=48000[mix]'), bedUnpinned);
});
t('loudness and true_peak are range checked, and true_peak alone is refused', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), loudness: -5 }), /loudness/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), loudness: -31 }), /loudness/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), loudness: 'loud' }), /loudness/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), loudness: -14, true_peak: 1 }), /true_peak/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st50(), true_peak: -1 }), /true_peak: only meaningful with loudness/);
});
t('none of the new fields given leaves the stacked argv byte for byte as before (the golden test above covers no split; this covers split 0.5)', () => {
  const plain = J.JOBS.presenter_composite.build({ ...st(), split: 0.5 });
  const g = graph(plain);
  assert.ok(!/loudnorm|cap_a|\[k0\]|force_divisible_by/.test(g), g);
  assert.ok(g.endsWith('[0:a]aresample=48000,apad[mix]'), g);
  const r = plain.parse();
  assert.strictEqual(r.emphasis_cards, 0); assert.strictEqual(r.emphasis_captions, false); assert.strictEqual(r.loudness, null);
});

section('\n-- C1: caption_srt, seam captions from word timings --');
const W = (pairs) => pairs.map(([text, start, end]) => ({ text, start, end, p: 0.9 }));
t('the reference hook breaks at punctuation into cues of at most four words (the rule, not his exact cut)', () => {
  const cues = J.seamCues(W([['Elon', 0, 0.2], ['Musk', 0.2, 0.45], ['just', 0.45, 0.6], ['gave', 0.6, 0.8], ['his', 0.8, 0.9], ['AI', 0.9, 1.1], ['bot', 1.1, 1.3], ['a', 1.3, 1.35], ['crazy', 1.35, 1.7], ['update.', 1.7, 2.1],
                              ['Now', 2.2, 2.4], ['it', 2.4, 2.5], ['controls', 2.5, 2.9], ['your', 2.9, 3.0], ['entire', 3.0, 3.4], ['phone.', 3.4, 3.9]]));
  assert.deepStrictEqual(cues.map(c => c.text), ['Elon Musk just gave', 'his AI bot a', 'crazy update.', 'Now it controls your', 'entire phone.']);
  assert.ok(cues.every(c => c.words >= 2 && c.words <= 5), JSON.stringify(cues));
});
t('a single word left at the end of a phrase joins the group before it instead of flashing alone', () => {
  const cues = J.seamCues(W([['one', 0, 0.2], ['two', 0.2, 0.4], ['three', 0.4, 0.6], ['four', 0.6, 0.8], ['five.', 0.8, 1.0]]));
  assert.deepStrictEqual(cues.map(c => c.text), ['one two three four five.']);
});
t('a one word phrase after a sentence opens the next phrase: "Before, the bot worked"', () => {
  const cues = J.seamCues(W([['It', 0, 0.2], ['works.', 0.2, 0.6], ['Before,', 0.8, 1.1], ['the', 1.1, 1.2], ['bot', 1.2, 1.4], ['worked.', 1.4, 1.8]]));
  assert.deepStrictEqual(cues.map(c => c.text), ['It works.', 'Before, the bot worked.']);
});
t('times: first start to last end plus tail, never overlapping the next cue, never under 0.3 s when there is room', () => {
  const cues = J.seamCues(W([['A', 0, 0.05], ['b.', 0.05, 0.1], ['Next', 1.0, 1.2], ['one', 1.2, 1.4], ['here', 1.4, 1.6], ['now.', 1.6, 1.62]]), { tail: 0.15 });
  assert.strictEqual(cues[0].start, 0); assert.strictEqual(cues[0].end, 0.3, 'floored to 0.3 s: ' + JSON.stringify(cues));
  const tight = J.seamCues(W([['A', 0, 0.5], ['b.', 0.5, 0.9], ['C', 0.95, 1.2], ['d.', 1.2, 1.5]]), { tail: 0.15 });
  assert.strictEqual(tight[0].end, 0.93, 'cut 20 ms short of the next cue: ' + JSON.stringify(tight));
  const shifted = J.seamCues(W([['A', 0, 0.5], ['b.', 0.5, 0.9]]), { offset: 2.5, tail: 0 });
  assert.deepStrictEqual([shifted[0].start, shifted[0].end], [2.5, 3.4]);
});
t('markup characters are stripped, a word they empty is dropped, and a word with no usable time is refused', () => {
  // The characters go and the letters between them stay: '{\an8}Hi' reads
  // 'an8Hi'. Ugly, and harmless: libass gets no tag to obey. Whisper output
  // carries none of these; the rule exists for a hand-edited words file.
  const cues = J.seamCues(W([['{\\an8}Hi', 0, 0.3], ['<b>there</b>', 0.3, 0.6], ['{}', 0.6, 0.7], ['friend.', 0.7, 1.0]]));
  assert.deepStrictEqual(cues.map(c => c.text), ['an8Hi bthere/b friend.']);
  assert.ok(cues.every(c => !/[{}\\<>]/.test(c.text)));
  assert.throws(() => J.seamCues(W([['a', 0.5, 0.2]])), /not a usable time span/);
  assert.throws(() => J.seamCues([{ text: 'a', start: 'soon', end: 1 }]), /not a usable time span/);
  assert.throws(() => J.seamCues([]), /none to caption/);
});
t('only real numbers are times: null, "", true, [3], a negative start and a time past a day are refused', () => {
  // Number() coerced the first four into 0, 0, 1 and 3, so a word with no
  // timing was captioned at 0 s (critic, 2026-10-31).
  for (const bad of [null, '', true, [3], '1.5']) {
    assert.throws(() => J.seamCues([{ text: 'a', start: bad, end: 1 }]), /not a usable time span/, JSON.stringify(bad));
    assert.throws(() => J.seamCues([{ text: 'a', start: 0, end: bad }]), /not a usable time span/, JSON.stringify(bad));
  }
  assert.throws(() => J.seamCues(W([['a', -0.5, 1]])), /not a usable time span/);
  assert.throws(() => J.seamCues(W([['a', 0, 1e300]])), /not a usable time span/);
  assert.throws(() => J.seamCues(W([['a', 0, 86400.5]])), /not a usable time span/);
});
t('words out of order are refused instead of making a 1 ms cue', () => {
  assert.throws(() => J.seamCues(W([['later.', 5, 5.4], ['earlier.', 1, 1.4]])), /out of order/);
  assert.doesNotThrow(() => J.seamCues(W([['same', 1, 1.2], ['start', 1, 1.3]])), 'equal starts are fine');
});
t('a control character inside a word becomes a space, not a glue', () => {
  assert.deepStrictEqual(J.seamCues(W([['foo\nbar', 0, 0.5], ['baz\tqux.', 0.5, 1]])).map(c => c.text), ['foo bar baz qux.']);
});
t('a cue never holds more than max_words + 1 words; a one word cue is only the last thing said', () => {
  const many = []; for (let i = 0; i < 40; i++) many.push([`w${i}`, i * 0.2, i * 0.2 + 0.15]);
  for (const maxWords of [2, 3, 4, 5, 6]) {
    const cues = J.seamCues(W(many), { maxWords });
    assert.ok(cues.every(c => c.words <= maxWords + 1), `${maxWords}: ${cues.map(c => c.words)}`);
  }
  const tail = J.seamCues(W([['Hello', 0, 0.3], ['there.', 0.3, 0.6], ['Bye.', 1, 1.3]]));
  assert.deepStrictEqual(tail.map(c => c.text), ['Hello there.', 'Bye.'], 'a closing one word sentence stands alone, and only at the end');
});
t('the 20000 word cap holds', () => {
  const lots = []; for (let i = 0; i < 20001; i++) lots.push({ text: 'w', start: i * 0.01, end: i * 0.01 + 0.005 });
  assert.throws(() => J.seamCues(lots), /too many/);
});
t('SRT out: numbered cues, HH:MM:SS,mmm, blank line between', () => {
  const s = J.seamSrt([{ start: 0, end: 1.25, text: 'Elon Musk just gave' }, { start: 3661.5, end: 3662, text: 'later' }]);
  assert.strictEqual(s, '1\n00:00:00,000 --> 00:00:01,250\nElon Musk just gave\n\n2\n01:01:01,500 --> 01:01:02,000\nlater\n\n');
});
t('caption_srt runs against a word_timings file and writes the SRT presenter_composite can take', async () => {
  const words = path.join(ROOT, 'q/short-words.json');
  fs.writeFileSync(words, JSON.stringify({ short01: { text: 'x', words: W([['Number', 0, 0.3], ['one,', 0.3, 0.6], ['phone', 0.6, 0.9], ['control.', 0.9, 1.4]]) } }));
  const r = await J.JOBS.caption_srt.build({ words: 'q/short-words.json', output: 'q/short01.srt' }).native();
  assert.strictEqual(r.line, 'short01'); assert.strictEqual(r.cues, 2); assert.strictEqual(r.words, 4);
  // The comma ends a phrase, so "Number one," and "phone control." are two
  // cues, and the first stops 20 ms before the second starts.
  assert.strictEqual(fs.readFileSync(path.join(ROOT, 'q/short01.srt'), 'utf8'),
    '1\n00:00:00,000 --> 00:00:00,580\nNumber one,\n\n2\n00:00:00,600 --> 00:00:01,550\nphone control.\n\n');
  const pcb = J.JOBS.presenter_composite.build({ ...st(), split: 0.5, captions: 'q/short01.srt' });
  assert.ok(graph(pcb).includes('subtitles=filename='), 'presenter_composite accepts the written SRT');
});
t('caption_srt refuses a non-.srt output, a path the subtitles filter cannot take, a bad max_words and an unnamed line in a multi-line file', async () => {
  fs.writeFileSync(path.join(ROOT, 'q/two-lines.json'), JSON.stringify({ L01: { words: W([['a', 0, 1]]) }, L02: { words: W([['b', 0, 1]]) } }));
  assert.throws(() => J.JOBS.caption_srt.build({ words: 'q/two-lines.json', output: 'q/x.txt' }), /must end .srt/);
  assert.throws(() => J.JOBS.caption_srt.build({ words: 'q/two-lines.json', output: 'q/bad name.srt' }), /subtitles filter/);
  assert.throws(() => J.JOBS.caption_srt.build({ words: 'q/two-lines.json', output: 'q/x.srt', max_words: 9 }), /max_words/);
  await assert.rejects(J.JOBS.caption_srt.build({ words: 'q/two-lines.json', output: 'q/x.srt' }).native(), /name one with line/);
  const r = await J.JOBS.caption_srt.build({ words: 'q/two-lines.json', output: 'q/x.srt', line: 'L02' }).native();
  assert.strictEqual(r.line, 'L02');
  await assert.rejects(J.JOBS.caption_srt.build({ words: 'q/two-lines.json', output: 'q/x.srt', line: 'L09' }).native(), /no line L09/);
});
t('caption_srt refuses to write over its own words file, and a words file over 8 MiB', async () => {
  fs.writeFileSync(path.join(ROOT, 'q/self.srt'), JSON.stringify({ L01: { words: W([['a', 0, 1]]) } }));
  assert.throws(() => J.JOBS.caption_srt.build({ words: 'q/self.srt', output: 'q/self.srt' }), /is the words file itself/);
  // An output that is a symlink to the words file is the same file (Codex on
  // PR #467 reproduced the overwrite through a link); so is one that becomes a
  // link after submit.
  fs.writeFileSync(path.join(ROOT, 'q/timings.json'), JSON.stringify({ L01: { words: W([['a', 0, 1]]) } }));
  fs.symlinkSync('timings.json', path.join(ROOT, 'q/alias.srt'));
  assert.throws(() => J.JOBS.caption_srt.build({ words: 'q/timings.json', output: 'q/alias.srt' }), /is the words file itself/);
  const late = J.JOBS.caption_srt.build({ words: 'q/timings.json', output: 'q/late.srt' });
  fs.symlinkSync('timings.json', path.join(ROOT, 'q/late.srt'));
  await assert.rejects(late.native(), /resolves to the words file itself/);
  assert.ok(fs.readFileSync(path.join(ROOT, 'q/timings.json'), 'utf8').startsWith('{'), 'the timings survive');
  fs.writeFileSync(path.join(ROOT, 'q/huge.json'), Buffer.alloc(8 * 1024 * 1024 + 1, 0x20));
  await assert.rejects(J.JOBS.caption_srt.build({ words: 'q/huge.json', output: 'q/huge.srt' }).native(), /over 8 MiB/);
});

section('\n-- C2: hard_max and bridge, the caption fixes Tee ruled 2026-11-01 --');
t('hard_max 3: no cue passes three words, and a long phrase is shared out evenly, larger groups first', () => {
  const seven = W([['a', 0, 0.2], ['b', 0.2, 0.4], ['c', 0.4, 0.6], ['d', 0.6, 0.8], ['e', 0.8, 1.0], ['f', 1.0, 1.2], ['g.', 1.2, 1.4]]);
  assert.deepStrictEqual(J.seamCues(seven, { maxWords: 3, hardMax: true }).map(c => c.words), [3, 2, 2]);
  const four = W([['one', 0, 0.2], ['two', 0.2, 0.4], ['three', 0.4, 0.6], ['four.', 0.6, 0.8]]);
  assert.deepStrictEqual(J.seamCues(four, { maxWords: 3, hardMax: true }).map(c => c.text), ['one two', 'three four.']);
  assert.deepStrictEqual(J.seamCues(four, { maxWords: 3 }).map(c => c.text), ['one two three four.'], 'without hard_max the old +1 rule stands');
  for (let n = 1; n <= 40; n++) {
    const ws = W(Array.from({ length: n }, (_, k) => [k === n - 1 ? `w${k}.` : `w${k}`, k * 0.2, k * 0.2 + 0.2]));
    for (const m of [2, 3, 4, 5, 6]) {
      const cues = J.seamCues(ws, { maxWords: m, hardMax: true });
      assert.ok(cues.every(c => c.words <= m), `n ${n} m ${m}: ${JSON.stringify(cues.map(c => c.words))}`);
      assert.strictEqual(cues.reduce((k, c) => k + c.words, 0), n, `n ${n} m ${m} lost or doubled a word`);
      // At max 2 an odd phrase cannot avoid a lone word (3 is 2 and 1); from 3 up it always can.
      if (n > 1 && m >= 3) assert.ok(cues.every(c => c.words >= 2), `n ${n} m ${m} left a word alone: ${JSON.stringify(cues.map(c => c.words))}`);
    }
  }
});
t('hard_max: a one word phrase joins the group before it only while that group stays at max_words', () => {
  const ws = W([['Before', 0, 0.2], ['assigning', 0.2, 0.5], ['blame,', 0.5, 0.8], ['inspect', 0.9, 1.2], ['the', 1.2, 1.3], ['direction.', 1.3, 1.8]]);
  const hard = J.seamCues(ws, { maxWords: 3, hardMax: true });
  assert.deepStrictEqual(hard.map(c => c.text), ['Before assigning blame,', 'inspect the direction.']);
  const join = W([['the', 0, 0.2], ['team,', 0.2, 0.5], ['too,', 0.5, 0.8], ['then', 0.9, 1.0], ['left.', 1.0, 1.4]]);
  assert.deepStrictEqual(J.seamCues(join, { maxWords: 3, hardMax: true }).map(c => c.text), ['the team, too,', 'then left.']);
  const full = W([['our', 0, 0.2], ['whole', 0.2, 0.4], ['team,', 0.4, 0.6], ['too,', 0.6, 0.8], ['then', 0.9, 1.0], ['left.', 1.0, 1.4]]);
  assert.deepStrictEqual(J.seamCues(full, { maxWords: 3, hardMax: true }).map(c => c.text), ['our whole team,', 'too, then left.']);
});
t('bridge closes a gap shorter than it and leaves a real pause open; off by default', () => {
  const ws = W([['A', 0, 0.4], ['b.', 0.4, 0.8], ['C', 0.9, 1.2], ['d.', 1.2, 1.5], ['E', 3.0, 3.4], ['f.', 3.4, 3.8]]);
  const off = J.seamCues(ws, { tail: 0.15 });
  assert.strictEqual(off[0].end, 0.88, 'the old 20 ms gap stands without bridge: ' + JSON.stringify(off));
  const on = J.seamCues(ws, { tail: 0.15, bridge: 0.3 });
  assert.strictEqual(on[0].end, on[1].start, 'a 20 ms gap is closed: ' + JSON.stringify(on));
  assert.strictEqual(on[1].end, 1.65, 'a 1.35 s pause stays open: ' + JSON.stringify(on));
  for (let k = 0; k + 1 < on.length; k++) assert.ok(on[k].end <= on[k + 1].start, 'bridge never overlaps cues');
});
t('max_chars cuts a cue whose text is longer, filling each piece; a word longer than it stands alone; absent, nothing changes', () => {
  const ws = W([['through', 0, 0.3], ['hypothetical', 0.3, 0.9], ['examples.', 0.9, 1.4], ['Make', 1.6, 1.8], ['sure', 1.8, 2.0], ['it.', 2.0, 2.3]]);
  assert.deepStrictEqual(J.seamCues(ws, { maxWords: 3, hardMax: true }).map(c => c.text), ['through hypothetical examples.', 'Make sure it.']);
  const cut = J.seamCues(ws, { maxWords: 3, hardMax: true, maxChars: 23 });
  assert.deepStrictEqual(cut.map(c => c.text), ['through hypothetical', 'examples.', 'Make sure it.']);
  assert.ok(cut.every(c => c.text.length <= 23), JSON.stringify(cut));
  assert.strictEqual(cut[1].start, 0.9, 'a cut piece starts at its own first word');
  const long = J.seamCues(W([['supercalifragilistic.', 0, 1]]), { maxChars: 10 });
  assert.deepStrictEqual(long.map(c => c.text), ['supercalifragilistic.']);
});
t('caption_srt passes hard_max and bridge through, and refuses a hard_max that is not a boolean or a bridge out of range', async () => {
  const words = [['Before', 0, 0.2], ['assigning', 0.2, 0.5], ['blame,', 0.5, 0.8], ['inspect', 0.82, 1.2], ['the', 1.2, 1.3], ['direction.', 1.3, 1.8]];
  fs.writeFileSync(path.join(ROOT, 'q/hm.json'), JSON.stringify({ L01: { words: W(words) } }));
  const r = await J.JOBS.caption_srt.build({ words: 'q/hm.json', output: 'q/hm.srt', max_words: 3, hard_max: true, bridge: 0.3 }).native();
  assert.strictEqual(r.cues, 2);
  const srt = fs.readFileSync(path.join(ROOT, 'q/hm.srt'), 'utf8');
  assert.ok(srt.includes('00:00:00,000 --> 00:00:00,820\nBefore assigning blame,'), srt);
  assert.throws(() => J.JOBS.caption_srt.build({ words: 'q/hm.json', output: 'q/hm.srt', hard_max: 'yes' }), /hard_max: must be true or false/);
  assert.throws(() => J.JOBS.caption_srt.build({ words: 'q/hm.json', output: 'q/hm.srt', hard_max: 1 }), /hard_max: must be true or false/);
  assert.throws(() => J.JOBS.caption_srt.build({ words: 'q/hm.json', output: 'q/hm.srt', bridge: 2 }), /bridge/);
  assert.throws(() => J.JOBS.caption_srt.build({ words: 'q/hm.json', output: 'q/hm.srt', bridge: -0.1 }), /bridge/);
  assert.throws(() => J.JOBS.caption_srt.build({ words: 'q/hm.json', output: 'q/hm.srt', max_chars: 9 }), /max_chars/);
  assert.throws(() => J.JOBS.caption_srt.build({ words: 'q/hm.json', output: 'q/hm.srt', max_chars: 22.5 }), /max_chars/);
  const mc = await J.JOBS.caption_srt.build({ words: 'q/hm.json', output: 'q/hm2.srt', max_words: 3, hard_max: true, max_chars: 12 }).native();
  const texts = fs.readFileSync(path.join(ROOT, 'q/hm2.srt'), 'utf8').split('\n\n').filter(Boolean).map(b => b.split('\n').slice(2).join(' '));
  assert.ok(texts.every(x => x.length <= 12 || !x.includes(' ')), 'max_chars reaches the file: ' + JSON.stringify(texts));
  assert.ok(mc.cues > 2);
});

section('\n-- A3: -nostdin reaches ffmpeg and never ffprobe --');
t('ffmpeg jobs carry -nostdin', () => {
  const b = J.JOBS.silence_detect.build({ input: touch('s/in.wav') });
  assert.strictEqual(b.bin, 'ffmpeg');
  assert.ok(b.argv.includes('-nostdin'), 'missing on an ffmpeg job');
});
t('the ffprobe job does NOT carry -nostdin (not a valid ffprobe flag)', () => {
  const b = J.JOBS.probe.build({ path: touch('s/in2.wav') });
  assert.strictEqual(b.bin, 'ffprobe');
  assert.ok(!b.argv.includes('-nostdin'), '-nostdin would break ffprobe');
});

// --- Voice Lab (2026-10-15) ------------------------------------------------

/** Turn "a b c" into timed words, 0.4 s each with 0.1 s gaps, starting at t0. */
const say = (text, t0) => text.split(' ').map((w, i) => ({ text: w, start: +(t0 + i * 0.5).toFixed(3), end: +(t0 + i * 0.5 + 0.4).toFixed(3) }));
const endOf = (ws) => ws[ws.length - 1].end;
const align = (params) => J.JOBS.align_script.build(params).native();
const SCRIPT = [
  'You post every day.',
  'Nobody buys. Here is why.',
  'Your first three seconds sell the whole video.',
];

section('\n-- V1: align_script, which stretch of the real take to keep --');
t('a clean read keeps every line and joins them into one continuous span', async () => {
  const a = say('you post every day', 1.0);
  const b = say('nobody buys here is why', endOf(a) + 0.6);
  const c = say('your first three seconds sell the whole video', endOf(b) + 0.6);
  const r = await align({ lines: SCRIPT, words: [...a, ...b, ...c] });
  assert.strictEqual(r.verdict, 'clean');
  assert.strictEqual(r.patched, 0);
  assert.strictEqual(r.edl.length, 1, JSON.stringify(r.edl));
  assert.deepStrictEqual(r.edl[0].lines, [0, 1, 2]);
  // Padded 0.12 s either side of the first and last word, never below zero.
  assert.strictEqual(r.edl[0].start, 0.88);
  assert.strictEqual(r.edl[0].end, +(endOf(c) + 0.12).toFixed(3));
});
t('a retake: the LAST clean reading of the line wins and the stumble is dropped', async () => {
  const a  = say('you post every day', 0);
  const b1 = say('nobody buys here is why', endOf(a) + 0.5);
  const um = say('uh hold on', endOf(b1) + 0.5);
  const b2 = say('nobody buys here is why', endOf(um) + 0.5);
  const c  = say('your first three seconds sell the whole video', endOf(b2) + 0.5);
  const r = await align({ lines: SCRIPT, words: [...a, ...b1, ...um, ...b2, ...c] });
  assert.strictEqual(r.verdict, 'clean');
  assert.strictEqual(r.edl.length, 2, JSON.stringify(r.edl));
  assert.deepStrictEqual(r.edl[0].lines, [0]);
  assert.deepStrictEqual(r.edl[1].lines, [1, 2]);
  assert.ok(r.edl[1].start > endOf(um) - 0.01, `start ${r.edl[1].start} is not after the stumble`);
});
t('a flubbed line is patched with the SCRIPT text verbatim, never the spoken words', async () => {
  const a = say('you post every day', 0);
  const b = say('nobody buys here is uh wait', endOf(a) + 0.5);
  const c = say('your first three seconds sell the whole video', endOf(b) + 0.5);
  // One of three lines is 33 percent, over the default 30 percent ceiling.
  const r = await align({ lines: SCRIPT, words: [...a, ...b, ...c], max_patch_share: 0.5 });
  assert.strictEqual(r.verdict, 'patch');
  assert.deepStrictEqual(r.edl.map(e => e.kind), ['take', 'patch', 'take']);
  assert.strictEqual(r.edl[1].text, 'Nobody buys. Here is why.');
});
t('critic B1: a reading one word off the script is NEVER kept, however long the line', async () => {
  const cases = [
    ['Our churn fell by thirty percent in the last year.', 'our churn fell by forty percent in the last year'],
    ['You should never put this file in a public folder.', 'you should always put this file in a public folder'],
    ['That is the whole answer to the question.', 'that is the whole answer to the'],
    ['Your first three seconds sell the whole video.', 'your first three seconds um sell the whole video'],
  ];
  for (const [line, spoken] of cases) {
    const r = await align({ lines: [line], words: say(spoken, 0), max_patch_share: 1 });
    assert.strictEqual(r.report[0].kind, 'patch', `kept "${spoken}" for "${line}"`);
  }
});
t('critic B1: a verbatim reading beats a later misreading of the same line', async () => {
  const good = say('our churn fell by thirty percent in the last year', 0);
  const bad = say('our churn fell by forty percent in the last year', endOf(good) + 1);
  const r = await align({ lines: ['Our churn fell by thirty percent in the last year.'], words: [...good, ...bad] });
  assert.strictEqual(r.verdict, 'clean');
  assert.ok(r.edl[0].end < bad[0].start, 'kept the misreading');
});
t('the old threshold parameter is refused, not silently ignored', () => {
  assert.throws(() => J.JOBS.align_script.build({ lines: ['a'], words: [], threshold: 0.9 }), /threshold: removed/);
});
t('critic F8: a skipped one word line does not steal the last word of the line before it', async () => {
  const a = say('you post every day', 0);
  const b = say('nobody buys here is why', endOf(a) + 0.5);
  const r = await align({ lines: ['You post every day.', 'Nobody buys. Here is why.', 'Why?'], words: [...a, ...b], max_patch_share: 0.5 });
  assert.deepStrictEqual(r.report.map(x => x.kind), ['take', 'take', 'patch'], JSON.stringify(r.report));
});
t('critic F8: a line written twice in the script but said once keeps the reading for one, patches the other', async () => {
  const a = say('you post every day', 0);
  const b = say('nobody buys here is why', endOf(a) + 0.5);
  const r = await align({ lines: ['You post every day.', 'Nobody buys. Here is why.', 'You post every day.'], words: [...a, ...b], max_patch_share: 0.5 });
  assert.deepStrictEqual(r.report.map(x => x.kind), ['take', 'take', 'patch'], JSON.stringify(r.report));
});
t('the choice keeps the most script WORDS, so a long clean line beats a short one', async () => {
  // Only one "why" is spoken; giving it to the one word line would clone five.
  const b = say('nobody buys here is why', 0);
  const r = await align({ lines: ['Why?', 'Nobody buys. Here is why.'], words: b, max_patch_share: 0.5 });
  assert.deepStrictEqual(r.report.map(x => x.kind), ['patch', 'take']);
});
t('over the patch ceiling is a re-record with NO edl, and the report says why', async () => {
  const a = say('you post every day', 0);
  const r = await align({ lines: SCRIPT, words: a });
  assert.strictEqual(r.verdict, 'rerecord');
  assert.strictEqual(r.edl, null);
  assert.ok(/2 of 3 lines/.test(r.reason), r.reason);
  assert.strictEqual(r.report.length, 3);
});
t('a pad never reaches past the midpoint to the neighbouring word', async () => {
  const a = say('you post every day', 0);
  const junk = [{ text: 'uh', start: endOf(a) + 0.05, end: endOf(a) + 0.15 }];
  const b = say('nobody buys here is why', endOf(a) + 0.2);
  const c = say('your first three seconds sell the whole video', endOf(b) + 0.5);
  const r = await align({ lines: SCRIPT, words: [...a, ...junk, ...b, ...c] });
  assert.strictEqual(r.edl[0].end, +(endOf(a) + 0.025).toFixed(3), JSON.stringify(r.edl));
});
t('take_duration stops the closing pad at the end of the file', async () => {
  const a = say('you post every day', 0);
  const r = await align({ lines: [SCRIPT[0]], words: a, take_duration: endOf(a) + 0.05 });
  assert.strictEqual(r.edl[0].end, +(endOf(a) + 0.05).toFixed(3));
});
t('digits and number words do not match: the safe direction is the clone reading the script', async () => {
  const r = await align({ lines: ['Your first 3 seconds sell it.'], words: say('your first three seconds sell it', 0), max_patch_share: 1 });
  assert.strictEqual(r.report[0].kind, 'patch');
});
t('spacing and sound events in the speech-to-text output are not speech', async () => {
  const ws = say('you post every day', 0);
  const mixed = [ws[0], { text: ' ', start: 0.4, end: 0.5, type: 'spacing' }, ws[1],
                 { text: '(laughs)', start: 0.9, end: 1.0, type: 'audio_event' }, ws[2], ws[3]];
  const r = await align({ lines: [SCRIPT[0]], words: mixed });
  assert.strictEqual(r.verdict, 'clean');
});
t('a later stray repeat of an earlier line is never spliced in after the next line', async () => {
  const a  = say('you post every day', 0);
  const b  = say('nobody buys here is why', endOf(a) + 0.5);
  const a2 = say('you post every day', endOf(b) + 0.5);
  const r = await align({ lines: SCRIPT.slice(0, 2), words: [...a, ...b, ...a2] });
  assert.strictEqual(r.edl.length, 1);
  assert.ok(r.edl[0].end < a2[0].start, 'line 0 was taken from after line 1');
});
t('critic F3: a 150 line, 20,000 word alignment finishes fast and a repetitive one is refused', async () => {
  const vocab = 'the a to and of you your it is that this in for on with as be at by'.split(' ');
  let seed = 7; const rnd = () => (seed = (seed * 16807) % 2147483647) / 2147483647;
  const lines = Array.from({ length: 150 }, () => Array.from({ length: 8 + Math.floor(rnd() * 20) }, () => vocab[Math.floor(rnd() * vocab.length)]).join(' '));
  const spoken = []; let t0 = 0;
  while (spoken.length < 20000) { for (const l of lines) { for (const w of l.split(' ')) { spoken.push({ text: w, start: t0, end: t0 + 0.3 }); t0 += 0.35; } if (spoken.length >= 20000) break; } }
  const t1 = Date.now();
  const r = await align({ lines, words: spoken, max_patch_share: 1 });
  const ms = Date.now() - t1;
  assert.ok(ms < 3000, `took ${ms} ms`);
  assert.strictEqual(r.patched, 0);
  // Critic N9: the bound counts comparisons, so a pathological script is
  // refused in well under a second rather than holding the loop for 8 s.
  const many = Array(2000).fill(Array(30).fill('the').join(' '));
  const t2 = Date.now();
  await assert.rejects(align({ lines: many, words: Array.from({ length: 20000 }, (_, i) => ({ text: 'the', start: i, end: i + 0.5 })) }), /too many comparisons|over 200,000 verbatim readings/);
  assert.ok(Date.now() - t2 < 2000, `refusal took ${Date.now() - t2} ms`);
});
t('critic N7: a symbol on either side means the line is never kept', async () => {
  const cases = [
    ['Our revenue rose 30 this year.', 'our revenue rose 30% this year'],
    ['It is 5 million.', 'it is $5 million'],
    ['It was 5 degrees.', 'it was -5 degrees'],
    ['Plan A & plan B.', 'plan a and plan b'],
    // Round three: symbols outside the old list, and words with no a to z.
    ['It costs 500.', 'it costs \u00a5500'],
    ['It was 5 degrees.', 'it was \u00b15 degrees'],
    ['It is 10 faster.', 'it is 10\u00d7 faster'],
    ['It was 5 below.', 'it was \u20135 below'],
    ['It was 5 below.', 'it was (-5) below'],
    ['We went there.', 'we went \u6771\u4eac there'],
  ];
  for (const [line, spoken] of cases) {
    const r = await align({ lines: [line], words: say(spoken, 0), max_patch_share: 1 });
    assert.strictEqual(r.report[0].kind, 'patch', `kept "${spoken}" for "${line}"`);
  }
  const ok = await align({ lines: ['It was minus 5 degrees, a twenty-six year low.'], words: say('it was minus 5 degrees a twenty-six year low', 0) });
  assert.strictEqual(ok.verdict, 'clean');
});
t('round three: a perfect read of a line WITH a symbol is kept, because the symbol matches itself', async () => {
  const r = await align({ lines: ['Our revenue rose 30% this year.'], words: say('our revenue rose 30% this year', 0) });
  assert.strictEqual(r.verdict, 'clean', JSON.stringify(r.report));
  const neg = await align({ lines: ['It was -5 out.'], words: say('it was \u22125 out', 0) });
  assert.strictEqual(neg.verdict, 'clean', 'a hyphen minus and a true minus are the same sign');
});
t('round three: ordinary English still matches, accents fold, points and commas in numbers hold', async () => {
  const pairs = [
    ["Don't stop, it's 2026.", "don\u2019t stop it's 2026"],
    ['Send me an e-mail.', 'send me an e-mail'],
    ['A caf\u00e9 opens.', 'a cafe opens'],
    ['We hired 1,000 people.', 'we hired 1,000 people'],
    ['It grew 3.5 times.', 'it grew 3.5 times'],
  ];
  for (const [line, spoken] of pairs) {
    const r = await align({ lines: [line], words: say(spoken, 0) });
    assert.strictEqual(r.verdict, 'clean', `${line} vs ${spoken}: ${JSON.stringify(r.report)}`);
  }
  const r = await align({ lines: ['It grew 3.5 times.'], words: say('it grew 3 5 times', 0), max_patch_share: 1 });
  assert.strictEqual(r.report[0].kind, 'patch', '"3.5" must not equal "3 5"');
});
t('round three: one word lines cannot pin the loop or the heap; the kept readings are capped', async () => {
  const t0 = Date.now();
  await assert.rejects(align({ lines: Array(399).fill('the'), words: Array.from({ length: 50000 }, (_, i) => ({ text: 'the', start: i, end: i + 0.5 })) }),
    /over 200,000 verbatim readings|too many comparisons/);
  assert.ok(Date.now() - t0 < 2000, `refusal took ${Date.now() - t0} ms`);
});
t('round four: a number written another way is never kept as a clean read of a different number', async () => {
  const pairs = [
    ['A .5 percent rise.', 'a 5 percent rise'],
    ['Only $.99 today.', 'only $99 today'],
    ['It covers 10² meters.', 'it covers 102 meters'],
    ['We made 1,5 million.', 'we made 15 million'],
    ['Do steps 3,4 now.', 'do steps 34 now'],
    ['Add ½ cup.', 'add 12 cup'],
    ['Pay 1234,567 now.', 'pay 1234567 now'],
  ];
  for (const [line, spoken] of pairs) {
    const r = await align({ lines: [line], words: say(spoken, 0), max_patch_share: 1 });
    assert.strictEqual(r.report[0].kind, 'patch', `${line} was kept for "${spoken}"`);
  }
  // Thousands separators still fold, so the safe cases are not all patched.
  for (const [line, spoken] of [['It hit 1,000,000 views.', 'it hit 1000000 views'], ['We hired 1,000 people.', 'we hired 1000 people'], ['It was 0.5 percent.', 'it was 0.5 percent']]) {
    const r = await align({ lines: [line], words: say(spoken, 0) });
    assert.strictEqual(r.verdict, 'clean', `${line} vs ${spoken}: ${JSON.stringify(r.report)}`);
  }
});
t('round four: one word cannot fold to unbounded tokens, and the totals are capped', async () => {
  const lig = 'ﷺ';
  await assert.rejects(align({ lines: ['hello'], words: [{ text: lig.repeat(2), start: 0, end: 1 }] }), /folds to \d+ tokens, over 16/);
  await assert.rejects(align({ lines: ['hello'], words: [{ text: 'a'.repeat(65), start: 0, end: 1 }] }), /over 64 characters/);
  const t0 = Date.now();
  const many = Array.from({ length: 50000 }, (_, i) => ({ text: lig, start: i, end: i + 0.5 }));
  await assert.rejects(align({ lines: ['hello'], words: many }), /over 100,000 tokens after folding/);
  assert.ok(Date.now() - t0 < 2000, `refusal took ${Date.now() - t0} ms`);
  assert.throws(() => J.JOBS.align_script.build({ lines: Array(40).fill(lig.repeat(200)), words: [] }), /over 100,000 tokens after folding; split the script/);
});
t('round four: overlapping vendor timestamps never trim the kept word', async () => {
  const words = [
    { text: 'we', start: 0.5, end: 0.7 }, { text: 'are', start: 0.8, end: 1.0 }, { text: 'done', start: 1.1, end: 3.0 },
    { text: 'uh', start: 2.9, end: 3.2 },
  ];
  const r = await align({ lines: ['We are done.'], words });
  assert.strictEqual(r.verdict, 'clean');
  assert.ok(r.edl[0].end >= 3.0, `the kept span ends at ${r.edl[0].end}, inside "done"`);
  const back = [{ text: 'uh', start: 0.2, end: 0.9 }, { text: 'we', start: 0.8, end: 1.0 }, { text: 'are', start: 1.1, end: 1.3 }, { text: 'done', start: 1.4, end: 1.8 }];
  const r2 = await align({ lines: ['We are done.'], words: back });
  assert.ok(r2.edl[0].start <= 0.8, `the kept span starts at ${r2.edl[0].start}, inside "we"`);
});
t('critic N8: a reading may not start or end inside a hyphenated spoken word', async () => {
  const r = await align({ lines: ['This is our year.'], words: say('this is our year-end', 0), max_patch_share: 1 });
  assert.strictEqual(r.report[0].kind, 'patch');
});
t('critic N10: edges round inward, so align_script output always fits take_duration', async () => {
  const a = say('you post every day', 0);
  const r = await align({ lines: [SCRIPT[0]], words: a, take_duration: 1.8456 });
  assert.ok(r.edl[0].end <= 1.8456, `end ${r.edl[0].end}`);
  assert.strictEqual(r.edl[0].end, 1.845);
});
t('critic N12: more than 64 patches is a re-record, since one composite lays at most 64 cutaways', async () => {
  const lines = Array.from({ length: 300 }, (_, i) => `line number ${i} is here`);
  const spoken = []; let t0 = 0;
  lines.slice(0, 230).forEach(l => { say(l.toLowerCase(), t0).forEach(w => spoken.push(w)); t0 = spoken[spoken.length - 1].end + 0.5; });
  const r = await align({ lines, words: spoken, max_patch_share: 0.5 });
  assert.strictEqual(r.verdict, 'rerecord');
  assert.ok(/70 lines need the clone, over the 64/.test(r.reason), r.reason);
});
t('bad input is refused, not defaulted', async () => {
  assert.throws(() => J.JOBS.align_script.build({ lines: 'one line', words: [] }), /lines: must be an array/);
  assert.throws(() => J.JOBS.align_script.build({ lines: ['...'], words: [] }), /has no words/);
  assert.throws(() => J.JOBS.align_script.build({ lines: ['a'], words: '[]' }), /words: must be an array/);
  assert.throws(() => J.JOBS.align_script.build({ lines: ['a'], words: [], words_path: 'x.json' }), /send one, not both/);
  await assert.rejects(align({ lines: ['a b'], words: [{ text: 'a', start: 2, end: 2.4 }, { text: 'b', start: 1, end: 1.4 }] }), /not in time order/);
  await assert.rejects(align({ lines: ['a'], words: [{ text: 'a', start: 2, end: 1 }] }), /end before start/);
  assert.throws(() => J.JOBS.align_script.build({ lines: ['a'], words_path: '../../etc/passwd' }), /escapes|outside|no such/);
});
t('words_path reads an ElevenLabs-shaped response from disk', async () => {
  const rel = 'vl/stt.json';
  fs.mkdirSync(path.join(ROOT, 'vl'), { recursive: true });
  fs.writeFileSync(path.join(ROOT, rel), JSON.stringify({ text: 'You post every day.', words: [
    { text: 'You', start: 0, end: 0.3, type: 'word' }, { text: ' ', start: 0.3, end: 0.35, type: 'spacing' },
    { text: 'post', start: 0.35, end: 0.6, type: 'word' }, { text: ' ', start: 0.6, end: 0.65, type: 'spacing' },
    { text: 'every', start: 0.65, end: 0.9, type: 'word' }, { text: ' ', start: 0.9, end: 0.95, type: 'spacing' },
    { text: 'day.', start: 0.95, end: 1.3, type: 'word' }] }));
  const r = await align({ lines: [SCRIPT[0]], words_path: rel });
  assert.strictEqual(r.verdict, 'clean');
});

section('\n-- V2: take_patch, the real take spliced with the clone --');
const tp = () => ({
  take: touch('vl/take.mov'), take_duration: 12, output: 'vl/base.mp4', narration_output: 'vl/narration.wav', hdr: 'sdr',
  edl: [
    { kind: 'take', start: 0.88, end: 3.4, lines: [0] },
    { kind: 'patch', audio: touch('vl/line1.mp3'), duration: 2.25, lines: [1] },
    { kind: 'take', start: 6.1, end: 10.0, lines: [2] },
  ],
});
const segA = (b, k) => b.plan.segments[k].argv;
const segG = (b, k) => { const a = segA(b, k); return a[a.indexOf('-filter_complex') + 1]; };
const inputsOf = (argv) => argv.filter(a => a === '-i').length;
t('critic F2 + measured: one ffmpeg run per item, never more than two inputs each', () => {
  const b = J.JOBS.take_patch.build(tp());
  assert.strictEqual(b.plan.segments.length, 3);
  assert.deepStrictEqual(b.plan.segments.map(s => inputsOf(s.argv)), [1, 2, 1]);
  assert.strictEqual(inputsOf(b.plan.join), 1, 'the join reads one concat list');
  assert.ok(segA(b, 0).join(' ').includes('-ss 0.880000 -t 2.533333 -i'), segA(b, 0).join(' '));
  // The hold is two frames inside the take's frame-snapped end, 0.88 + 76/30.
  assert.ok(segA(b, 1).join(' ').includes('-ss 3.346667 -t 0.066667 -i'), segA(b, 1).join(' '));
  assert.ok(segA(b, 1).join(' ').includes('line1.mp3'));
  assert.ok(segA(b, 2).join(' ').includes('-ss 6.100000 -t 3.900000 -i'), segA(b, 2).join(' '));
});
t('a 400 item edl is accepted; it is 400 small runs, not 400 live decoders', () => {
  const p = tp(); p.take_duration = 600;
  p.edl = Array.from({ length: 400 }, (_, i) => i % 2
    ? { kind: 'patch', audio: touch(`vl/m${i}.mp3`), duration: 0.5 }
    : { kind: 'take', start: i, end: i + 0.9 });
  const b = J.JOBS.take_patch.build(p);
  assert.ok(b.plan.segments.every(s => inputsOf(s.argv) <= 2));
  p.edl.push({ kind: 'take', start: 500, end: 501 });
  assert.throws(() => J.JOBS.take_patch.build(p), /too many items \(max 400\)/);
});
t('every segment carries identical encoder settings, so the join can copy the video', () => {
  const b = J.JOBS.take_patch.build(tp());
  const tail = (a) => { const i = a.indexOf('-map'); return a.slice(i, a.length - 3).join(' '); };   // drop "-t L out"
  const tails = b.plan.segments.map(s => tail(s.argv));
  assert.ok(tails.every(x => x === tails[0]), tails.join('\n'));
  assert.ok(tails[0].includes('-c:v libx264 -crf 16 -preset medium -pix_fmt yuv420p -g 60 -video_track_timescale 30000'), tails[0]);
  assert.ok(tails[0].includes('-c:a pcm_s24le -ar 48000 -ac 1'), tails[0]);
  assert.ok(b.plan.join.join(' ').includes('-f concat -safe 0 -i'), b.plan.join.join(' '));
  assert.ok(b.plan.join.join(' ').includes('-c:v copy -c:a aac -b:a 320k'), b.plan.join.join(' '));
});
t('the patch window is returned on the NEW timeline, frame exact, ready for must_cover', () => {
  const r = J.JOBS.take_patch.build(tp()).result();
  // 2.52 s rounds to 76 frames, the 2.25 s patch rounds UP to 68, 3.9 s is 117.
  assert.strictEqual(r.duration, 8.7);
  assert.deepStrictEqual(r.patch_windows, [{ item: 1, lines: [1], start: 2.533333, end: 4.8 }]);
  assert.strictEqual(r.takes, 2);
  assert.strictEqual(r.segments, 3);
  assert.deepStrictEqual(r.patch_durations, [2.266667]);
  assert.deepStrictEqual(r.patch_source_durations, [2.25]);
});
t('every segment is a whole number of frames, so picture and sound cannot drift', () => {
  const p = tp();
  p.take_duration = 30;
  p.edl = Array.from({ length: 20 }, (_, i) => i % 2
    ? { kind: 'patch', audio: touch(`vl/d${i}.mp3`), duration: 1.01 + i / 1000 }
    : { kind: 'take', start: i, end: i + 0.97 + i / 1000 });
  const r = J.JOBS.take_patch.build(p).result();
  const f = r.duration * 30;
  assert.ok(Math.abs(f - Math.round(f)) < 1e-6, `total is ${f} frames`);
  r.patch_windows.forEach(w => {
    assert.ok(Math.abs(w.start * 30 - Math.round(w.start * 30)) < 1e-4, `start ${w.start}`);
    assert.ok(Math.abs(w.end * 30 - Math.round(w.end * 30)) < 1e-4, `end ${w.end}`);
  });
  r.patch_durations.forEach((d, i) => assert.ok(d >= r.patch_source_durations[i], 'a patch was cut short'));
});
t('durations are pinned and take video is NOT re-zeroed before fps (critic lip-sync nit)', () => {
  const b = J.JOBS.take_patch.build(tp());
  assert.ok(segG(b, 0).startsWith('[0:v]fps=30:start_time=0,format=yuv420p,setsar=1,tpad=stop_mode=clone:stop_duration=1,trim=duration=2.533333'), segG(b, 0));
  assert.ok(!segG(b, 0).includes('[0:v]setpts=PTS-STARTPTS,fps'), segG(b, 0));
  assert.ok(segG(b, 1).includes('trim=end_frame=1,tpad=stop_mode=clone:stop_duration=2.266667,trim=duration=2.266667'), segG(b, 1));
  assert.ok(segG(b, 1).includes('[1:a]asetpts=PTS-STARTPTS'), segG(b, 1));
  assert.ok(segG(b, 1).includes('apad,atrim=duration=2.266667'), segG(b, 1));
  assert.ok(b.plan.join.join(' ').includes('-t 8.700000'), b.plan.join.join(' '));
  assert.ok(b.plan.join.join(' ').includes('-map 0:a -c:a pcm_s24le -t 8.700000'), b.plan.join.join(' '));
});
t('without a narration_output the join has one output', () => {
  const b = J.JOBS.take_patch.build({ ...tp(), narration_output: undefined });
  assert.strictEqual(b.plan.join.filter(a => a === '-map').length, 2);
  assert.ok(!b.plan.join.includes('pcm_s24le'));
});
t('hdr has no default; tonemap adds the zscale chain to every segment, sdr to none', () => {
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), hdr: undefined }), /hdr/);
  const tm = J.JOBS.take_patch.build({ ...tp(), hdr: 'tonemap' });
  [0, 1, 2].forEach(k => assert.ok(segG(tm, k).includes('tonemap=tonemap=hable'), segG(tm, k)));
  const sd = J.JOBS.take_patch.build(tp());
  [0, 1, 2].forEach(k => assert.ok(!segG(sd, k).includes('zscale'), segG(sd, k)));
});
t('width and height scale first, at the take\'s bit depth, then tonemap, then letterbox', () => {
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), width: 1920 }), /both or neither/);
  const g = segG(J.JOBS.take_patch.build({ ...tp(), hdr: 'tonemap', width: 1920, height: 1080 }), 0);
  const iScale = g.indexOf('scale=1920:1080:force_original_aspect_ratio=decrease:flags=lanczos,zscale');
  const iTone = g.indexOf('tonemap=tonemap=hable');
  const iPad = g.indexOf('pad=1920:1080');
  assert.ok(iScale > 0 && iScale < iTone && iTone < iPad, g);
});
t('a patch that opens the episode holds the FIRST frame of the next take', () => {
  const p = tp();
  p.edl = [{ kind: 'patch', audio: touch('vl/line0.mp3'), duration: 1.5 }, { kind: 'take', start: 4, end: 9 }];
  const b = J.JOBS.take_patch.build(p);
  assert.ok(segA(b, 0).join(' ').includes('-ss 4.000000 -t 0.066667 -i'), segA(b, 0).join(' '));
});
t('critic F4: take_duration is required and no span or hold may run past it', () => {
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), take_duration: undefined }), /take_duration: required/);
  const p = tp(); p.take_duration = 12;
  p.edl = [{ kind: 'take', start: 9, end: 12.05 }, { kind: 'patch', audio: touch('vl/z.mp3'), duration: 2 }];
  assert.throws(() => J.JOBS.take_patch.build(p), /past the take's 12s/);
  p.edl[0].end = 11.99;   // 89.7 frames rounds to 90, which ends at 12.0 exactly: allowed
  const ok = J.JOBS.take_patch.build(p);
  assert.ok(segA(ok, 1).join(' ').includes('-ss 11.933333 -t 0.066667 -i'), segA(ok, 1).join(' '));
  p.edl[0] = { kind: 'take', start: 9, end: 11.995 };
  p.take_duration = 11.995;   // 89.85 frames rounds to 90 = 12.0 s, past the file: snapped down to 89
  const r = J.JOBS.take_patch.build(p).result();
  assert.ok(9 + (r.duration - r.patch_durations[0]) <= 11.995 + 1e-6, JSON.stringify(r));
});
t('critic F6: take spans out of time order or overlapping are refused', () => {
  const p = tp(); p.take_duration = 12;
  p.edl = [{ kind: 'take', start: 6, end: 8 }, { kind: 'take', start: 1, end: 3 }];
  assert.throws(() => J.JOBS.take_patch.build(p), /time order/);
  p.edl = [{ kind: 'take', start: 1, end: 3 }, { kind: 'take', start: 2, end: 4 }];
  assert.throws(() => J.JOBS.take_patch.build(p), /time order/);
  p.edl = [{ kind: 'take', start: 1, end: 3 }, { kind: 'patch', audio: touch('vl/q.mp3'), duration: 1 }, { kind: 'take', start: 3, end: 5 }];
  assert.ok(J.JOBS.take_patch.build(p));
});
t('bad edls and paths are refused at submit', () => {
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: null }), /re-record/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [] }), /at least one/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [{ kind: 'patch', audio: touch('vl/x.mp3'), duration: 2 }] }), /no take item/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [{ kind: 'take', start: 2, end: 2.05 }] }), /shorter than two crossfades/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [{ kind: 'cut', start: 0, end: 3 }] }), /kind/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [{ kind: 'take', start: 0, end: 3 }, { kind: 'patch', audio: 'vl/missing.mp3', duration: 2 }] }), /no such file/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [{ kind: 'take', start: 0, end: 3 }, { kind: 'patch', audio: touch('vl/y.mp3') }] }), /duration/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), output: '../escape.mp4' }), /escapes|outside/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), output: "vl/it's.mp4" }), /concat list/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), fps: 29.97 }), /fps/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), fps: 29 }), /fps/);
  assert.ok(J.JOBS.take_patch.build({ ...tp(), fps: 25 }));
});
t('critic N6: an output that is also an input is refused before anything is overwritten', () => {
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), output: 'vl/take.mov' }), /is the take itself/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), narration_output: 'vl/take.mov' }), /collides/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), narration_output: 'vl/base.mp4' }), /collides/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), narration_output: 'vl/base.mp4.parts/n.wav' }), /deletes/);
  // A clone file named like a video, so the extension check lets it through
  // to the collision check this line is about.
  const clip = touch('vl/clone-as.mov');
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), output: 'vl/clone-as.mov', narration_output: undefined,
    edl: [{ kind: 'take', start: 0, end: 3 }, { kind: 'patch', audio: clip, duration: 1 }] }), /also an output/);
});
t('critic N11: a take that would round into the next one rounds down instead, no replay', () => {
  const p = tp(); p.take_duration = 12;
  p.edl = [{ kind: 'take', start: 1.0, end: 2.02 }, { kind: 'take', start: 2.02, end: 3.0 }];
  const b = J.JOBS.take_patch.build(p);
  // 1.02 s is 30.6 frames, which rounds to 31 and would end at 2.0333; it is held to 30.
  assert.ok(segA(b, 0).join(' ').includes('-ss 1.000000 -t 1.000000 -i'), segA(b, 0).join(' '));
});
t('critic N2: patch windows are rounded outward so an edge never cuts inside a frame', () => {
  const p = tp(); p.take_duration = 12;
  p.edl = [{ kind: 'take', start: 0, end: 6.766667 }, { kind: 'patch', audio: touch('vl/w.mp3'), duration: 1 }, { kind: 'take', start: 7, end: 9 }];
  const r = J.JOBS.take_patch.build(p).result();
  const w = r.patch_windows[0];
  assert.ok(w.start <= 203 / 30 + 1e-12 && w.end >= (203 + 30) / 30 - 1e-12, JSON.stringify(w));
});
t('critic N5: take_patch exposes abort so a timed-out job can kill what it started', () => {
  const b = J.JOBS.take_patch.build(tp());
  assert.strictEqual(typeof b.abort, 'function');
  b.abort();   // with nothing running it is a no-op
});
t('round three: the join writes the clone windows into the output\'s own metadata', () => {
  const b = J.JOBS.take_patch.build(tp());
  const i = b.plan.join.indexOf('-metadata');
  assert.ok(i > 0, b.plan.join.join(' '));
  const tag = b.plan.join[i + 1];
  assert.ok(tag.startsWith('comment=voicelab-must-cover:'), tag);
  const parsed = JSON.parse(tag.slice('comment=voicelab-must-cover:'.length));
  assert.deepStrictEqual(parsed.windows, [{ start: 2.533333, end: 4.8 }]);
});
t('round four: a patched last line ends at the tagged duration, never a microsecond past it', () => {
  // 82 frames at 30 fps: the window end rounded up to 2.733334 and the tag's
  // duration to nearest, 2.733333, and the composite refused the cutaway.
  const p = tp(); p.take_duration = 12; p.xfade = 0;
  p.edl = [{ kind: 'take', start: 0, end: 1 }, { kind: 'patch', audio: touch('vl/last.mp3'), duration: 52 / 30 }];
  const r = J.JOBS.take_patch.build(p).result();
  assert.strictEqual(r.duration, 2.733333);
  assert.ok(r.patch_windows[0].end <= r.duration, JSON.stringify(r));
  const tag = J.JOBS.take_patch.build(p).plan.join.find(a => a.startsWith('comment='));
  const parsed = JSON.parse(tag.slice('comment=voicelab-must-cover:'.length));
  assert.ok(parsed.windows[0].end <= parsed.duration, tag);
});
t('round three: output must be .mp4 or .mov, and collisions are judged by real path', () => {
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), output: 'vl/base.mkv' }), /must end \.mp4 or \.mov/);
  fs.symlinkSync(path.join(ROOT, 'vl/take.mov'), path.join(ROOT, 'vl/take-link.mov'));
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), take: 'vl/take-link.mov', output: 'vl/take.mov' }), /is the take itself/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), output: 'vl/take-link.mov' }), /is the take itself/);
});
t('round three: a one frame span at xfade 0 is not refused by float rounding', () => {
  const p = tp(); p.xfade = 0; p.edl = [{ kind: 'take', start: 1, end: 1 + 1 / 30 }];
  assert.ok(J.JOBS.take_patch.build(p));
});

section('\n-- V3: must_cover, no clone voice over the presenter\'s face --');
t('a window wholly inside one cutaway, inside its fades, renders', () => {
  const r = J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 4.5, end: 9.5 }] }).parse();
  assert.strictEqual(r.must_cover, 1);
});
t('critic F5: an opaque plate sits under every covered window, before the cutaways', () => {
  const g = graph(J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 4.5, end: 9.5 }] }));
  // One output frame (1/25 s) wider on each side than the window (critic N2).
  assert.ok(g.includes("[base]drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='between(t,4.460000,9.540000)'[baseplate]"), g);
  assert.ok(g.includes('[baseplate][c0]overlay'), g);
  const none = graph(J.JOBS.presenter_composite.build(pc()));
  assert.ok(!none.includes('drawbox'), 'the plate must not appear without must_cover');
});
t('critic N4: a window inside a fade, or at the very start, renders, because the plate is under it', () => {
  assert.strictEqual(J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 4.0, end: 10 }] }).parse().must_cover, 1);
  const first = { ...pc(), cutaways: [{ path: touch('p/cut-0.mp4'), start: 0, end: 3 }] };
  assert.strictEqual(J.JOBS.presenter_composite.build({ ...first, must_cover: [{ start: 0, end: 0.666667 }] }).parse().must_cover, 1);
});
t('a window outside every cutaway, or spanning two, is refused', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 9, end: 21 }] }), /not inside one scheduled cutaway/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 12, end: 14 }] }), /black plate with nothing on it/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 3.9, end: 9 }] }), /not inside one scheduled/);
});
t('critic N3, round three: windows carried in the base track\'s own metadata are enforced, copies included', () => {
  const base = touch('p/sc/base.mp4');
  const abs = path.join(ROOT, 'p/sc/base.mp4');
  TAGS.set(abs, 'voicelab-must-cover:' + JSON.stringify({ fps: 30, duration: 60, windows: [{ start: 12, end: 14 }] }));
  const p = { ...pc(), avatar: base };
  assert.throws(() => J.JOBS.presenter_composite.build(p), /must_cover\[0\]: 12s to 14s/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...p, mustCover: [] }), /must_cover\[0\]/);
  TAGS.set(abs, 'voicelab-must-cover:' + JSON.stringify({ fps: 30, duration: 60, windows: [{ start: 5, end: 9 }] }));
  assert.ok(graph(J.JOBS.presenter_composite.build(p)).includes('drawbox'), 'the carried window was not plated');
  // Sending the same window as must_cover too counts it once (round three, finding 2).
  assert.strictEqual(J.JOBS.presenter_composite.build({ ...p, must_cover: [{ start: 5, end: 9 }] }).parse().must_cover, 1);
  TAGS.set(abs, 'voicelab-must-cover:{not json');
  assert.throws(() => J.JOBS.presenter_composite.build(p), /windows are unreadable/);
  TAGS.delete(abs);
});
t('round three: a base track whose tags cannot be read is refused, never composited unchecked', () => {
  J.setTagReader(() => { throw new Error('moov atom not found'); });
  try {
    assert.throws(() => J.JOBS.presenter_composite.build(pc()), /could not read its tags/);
  } finally {
    J.setTagReader(stubReader);
  }
});
t('round three: 33 windows sent AND carried are 33, not 66', () => {
  const base = touch('p/sc/many.mp4');
  const wins = Array.from({ length: 33 }, (_, i) => ({ start: 4.2 + i * 0.15, end: 4.25 + i * 0.15 }));
  TAGS.set(path.join(ROOT, 'p/sc/many.mp4'), 'voicelab-must-cover:' + JSON.stringify({ fps: 30, duration: 60, windows: wins }));
  const r = J.JOBS.presenter_composite.build({ ...pc(), avatar: base, must_cover: wins }).parse();
  assert.strictEqual(r.must_cover, 33);
});
t('round four: the tag is read under any key case, and a container that drops it is refused', () => {
  const base = touch('p/r4/base.mkv');
  const abs = path.join(ROOT, 'p/r4/base.mkv');
  const tag = 'voicelab-must-cover:' + JSON.stringify({ fps: 30, duration: 60, windows: [{ start: 12, end: 14 }] });
  J.setTagReader(() => ({ format: { format_name: 'matroska,webm', duration: '60', tags: { COMMENT: tag } }, streams: [{}] }));
  try {
    assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), avatar: base }), /must_cover\[0\]: 12s to 14s/);
  } finally { J.setTagReader(stubReader); }
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), avatar: touch('p/r4/base.ts') }), /must be \.mp4, \.mov, \.m4v, \.mkv or \.webm/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), avatar: touch('p/r4/list.ffconcat') }), /must be \.mp4/);
  const disguised = touch('p/r4/really-a-ts.mp4');
  FMTS.set(path.join(ROOT, disguised), 'mpegts');
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), avatar: disguised }), /reads as mpegts/);
  FMTS.delete(path.join(ROOT, disguised));
  void abs;
});
t('round four: windows written for another length are refused, within a frame they are kept', () => {
  const base = touch('p/r4/cut.mp4');
  const abs = path.join(ROOT, base);
  TAGS.set(abs, 'voicelab-must-cover:' + JSON.stringify({ fps: 30, duration: 60, windows: [{ start: 5, end: 9 }] }));
  DURS.set(abs, 59);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), avatar: base }), /runs 59s, but its Voice Lab windows were written for a 60s cut/);
  DURS.set(abs, 60 + 1 / 30);
  assert.ok(J.JOBS.presenter_composite.build({ ...pc(), avatar: base }));
  TAGS.set(abs, 'voicelab-must-cover:' + JSON.stringify({ fps: 30, windows: [{ start: 5, end: 9 }] }));
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), avatar: base }), /no fps or duration/);
  TAGS.delete(abs); DURS.delete(abs);
});
t('round four: the finished master does not carry the clone windows (ruled 2026-10-16)', () => {
  const a = J.JOBS.presenter_composite.build(pc()).argv;
  const i = a.indexOf('-metadata');
  assert.ok(i > 0 && a[i + 1] === 'comment=', a.join(' '));
});
t('stacked: a payload-zone cutaway leaves the face visible, so only full-frame counts', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), emphasis: [], must_cover: [{ start: 3, end: 5 }] }), /full-frame cutaway/);
  const r = J.JOBS.presenter_composite.build({ ...st(), emphasis: [], must_cover: [{ start: 8.5, end: 10.5 }] }).parse();
  assert.strictEqual(r.must_cover, 1);
});
t('round three: stacked emphasis within one frame of a covered window is refused', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), fps: 25, emphasis: [{ start: 7.5, end: 8.4995 }], must_cover: [{ start: 8.5, end: 10.5 }] }), /within a frame/);
  assert.ok(J.JOBS.presenter_composite.build({ ...st(), fps: 25, emphasis: [{ start: 7.5, end: 8.45 }], must_cover: [{ start: 8.5, end: 10.5 }] }));
});
t('stacked: an emphasis window over, or merely touching, a covered span is refused', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), emphasis: [{ start: 9, end: 10 }], must_cover: [{ start: 8.5, end: 10.5 }] }), /within a frame/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), emphasis: [{ start: 7.5, end: 8.5 }], must_cover: [{ start: 8.5, end: 10.5 }] }), /within a frame/);
});
t('must_cover that is not an array is refused, never defaulted', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), must_cover: '[{"start":4.5,"end":9.5}]' }), /must_cover: must be an array/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 6, end: 5 }] }), /end must exceed start/);
});

section('\n-- V4: probe reports HDR so the caller can set take_patch hdr --');
t('probe flags HLG and PQ from the first VIDEO stream and leaves the old fields on stream 0', () => {
  const b = J.JOBS.probe.build({ path: touch('vl/p.mov') });
  assert.ok(b.argv.join(' ').includes('stream=codec_type,width,height,r_frame_rate,color_transfer,pix_fmt'), b.argv.join(' '));
  const hlg = b.parse(JSON.stringify({ format: { duration: '9.5' }, streams: [{ codec_type: 'video', width: 3840, height: 2160, r_frame_rate: '30/1', color_transfer: 'arib-std-b67', pix_fmt: 'yuv420p10le' }] }));
  assert.strictEqual(hlg.hdr, true);
  assert.strictEqual(hlg.pix_fmt, 'yuv420p10le');
  const sdr = b.parse(JSON.stringify({ format: { duration: '9.5' }, streams: [{ codec_type: 'video', width: 1920, height: 1080, r_frame_rate: '30/1', color_transfer: 'bt709' }] }));
  assert.strictEqual(sdr.hdr, false);
  // Audio first, video second: hdr is read from the video, width stays stream 0's as before.
  const mixed = b.parse(JSON.stringify({ format: { duration: '9.5' }, streams: [{ codec_type: 'audio' }, { codec_type: 'video', width: 3840, height: 2160, color_transfer: 'smpte2084' }] }));
  assert.strictEqual(mixed.hdr, true);
  assert.strictEqual(mixed.width, null);
  const audio = b.parse(JSON.stringify({ format: { duration: '2.1' }, streams: [{ codec_type: 'audio' }] }));
  assert.strictEqual(audio.color_transfer, null);
  assert.strictEqual(audio.duration, 2.1);
});

(async () => {
  for (const [name, fn] of QUEUE) {
    if (fn === null) { console.log(name); continue; }
    try { await fn(); pass++; console.log('  PASS  ' + name); }
    catch (e) { fail++; console.log('  FAIL  ' + name + '\n        ' + e.message); }
  }
  console.log(`\n${pass} passed, ${fail} failed\n`);
  fs.rmSync(ROOT, { recursive: true, force: true });
  process.exit(fail ? 1 : 0);
})();
