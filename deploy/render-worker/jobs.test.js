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
