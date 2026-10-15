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
    layout: 'full', emphasis: 0, full_cutaways: 2, must_cover: 0 });
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
  // The kept reading of line 1 is the second one, after the "uh hold on".
  assert.ok(r.edl[1].start > endOf(um) - 0.01, `start ${r.edl[1].start} is not after the stumble`);
});
t('a flubbed line is patched with the SCRIPT text verbatim, never the spoken words', async () => {
  const a = say('you post every day', 0);
  const b = say('nobody buys here is uh wait', endOf(a) + 0.5);
  const c = say('your first three seconds sell the whole video', endOf(b) + 0.5);
  // One of three lines is 33 percent, over the default 30 percent ceiling.
  const r = await align({ lines: SCRIPT, words: [...a, ...b, ...c], max_patch_share: 0.5 });
  assert.strictEqual(r.verdict, 'patch');
  assert.strictEqual(r.edl.length, 3);
  assert.deepStrictEqual(r.edl.map(e => e.kind), ['take', 'patch', 'take']);
  assert.strictEqual(r.edl[1].text, 'Nobody buys. Here is why.');
  assert.deepStrictEqual(r.edl[1].lines, [1]);
});
t('a pad never reaches past the midpoint to the neighbouring word', async () => {
  const a = say('you post every day', 0);
  const junk = [{ text: 'uh', start: endOf(a) + 0.05, end: endOf(a) + 0.15 }];
  const b = say('nobody buys here is why', endOf(a) + 0.2);
  const c = say('your first three seconds sell the whole video', endOf(b) + 0.5);
  const r = await align({ lines: SCRIPT, words: [...a, ...junk, ...b, ...c] });
  // line 0 ends at endOf(a); the next transcript word starts 0.05 later, so the
  // pad is clamped to the midpoint, 0.025, not the full 0.12.
  assert.strictEqual(r.edl[0].end, +(endOf(a) + 0.025).toFixed(3), JSON.stringify(r.edl));
});
t('the threshold is a floor: 0.9 passes at exactly 0.9 and fails just below', async () => {
  // Ten script words against nine spoken (one dropped): 2*9/(10+9) = 0.947.
  const line = 'one two three four five six seven eight nine ten';
  const spoken = say('one two three four five six seven eight nine', 0);
  const hit = await align({ lines: [line], words: spoken, threshold: 0.94 });
  assert.strictEqual(hit.verdict, 'clean');
  const miss = await align({ lines: [line], words: spoken, threshold: 0.95, max_patch_share: 1 });
  assert.strictEqual(miss.verdict, 'rerecord', 'a lone line with no take is a re-record');
});
t('over the patch ceiling is a re-record with NO edl, and the report says why', async () => {
  const a = say('you post every day', 0);
  const r = await align({ lines: SCRIPT, words: a });
  assert.strictEqual(r.verdict, 'rerecord');
  assert.strictEqual(r.edl, null);
  assert.ok(/2 of 3 lines/.test(r.reason), r.reason);
  assert.strictEqual(r.report.length, 3);
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
  fs.writeFileSync(path.join(ROOT, rel), JSON.stringify({ text: 'you post every day', words: say('you post every day', 0) }));
  const r = await align({ lines: [SCRIPT[0]], words_path: rel });
  assert.strictEqual(r.verdict, 'clean');
});

section('\n-- V2: take_patch, the real take spliced with the clone --');
const tp = () => ({
  take: touch('vl/take.mov'), output: 'vl/base.mp4', narration_output: 'vl/narration.wav', hdr: 'sdr',
  edl: [
    { kind: 'take', start: 0.88, end: 3.4, lines: [0] },
    { kind: 'patch', audio: touch('vl/line1.mp3'), duration: 2.25, lines: [1] },
    { kind: 'take', start: 6.1, end: 10.0, lines: [2] },
  ],
});
t('each take item is its own seeked input; a patch adds a two frame hold slice and its audio', () => {
  const b = J.JOBS.take_patch.build(tp());
  const ins = [];
  b.argv.forEach((a, i) => { if (a === '-i') ins.push(b.argv.slice(Math.max(0, i - 4), i + 2).join(' ')); });
  assert.strictEqual(ins.length, 4, ins.join('\n'));
  assert.ok(ins[0].includes('-ss 0.880000 -t 2.533333 -i'), ins[0]);
  // The hold is the take's last frame before the patch: its frame-snapped
  // end, 0.88 + 76/30 = 3.413333, less two frames.
  assert.ok(ins[1].includes('-ss 3.346667 -t 0.066667 -i'), ins[1]);
  assert.ok(ins[2].endsWith('line1.mp3'), ins[2]);
  assert.ok(ins[3].includes('-ss 6.100000 -t 3.900000 -i'), ins[3]);
});
t('the patch window is returned on the NEW timeline, frame exact, ready for must_cover', () => {
  const r = J.JOBS.take_patch.build(tp()).parse();
  // 2.52 s rounds to 76 frames, the 2.25 s patch rounds UP to 68, 3.9 s is 117.
  assert.strictEqual(r.duration, 8.7);
  assert.deepStrictEqual(r.patch_windows, [{ item: 1, lines: [1], start: 2.533333, end: 4.8 }]);
  assert.strictEqual(r.takes, 2);
  assert.deepStrictEqual(r.patch_durations, [2.266667]);
  assert.deepStrictEqual(r.patch_source_durations, [2.25]);
});
t('every segment is a whole number of frames, so picture and sound cannot drift', () => {
  const p = tp();
  p.edl = Array.from({ length: 20 }, (_, i) => i % 2
    ? { kind: 'patch', audio: touch(`vl/d${i}.mp3`), duration: 1.01 + i / 1000 }
    : { kind: 'take', start: i, end: i + 0.97 + i / 1000 });
  const r = J.JOBS.take_patch.build(p).parse();
  const f = r.duration * 30;
  assert.ok(Math.abs(f - Math.round(f)) < 1e-6, `total is ${f} frames`);
  r.patch_windows.forEach(w => {
    assert.ok(Math.abs(w.start * 30 - Math.round(w.start * 30)) < 1e-4, `start ${w.start}`);
    assert.ok(Math.abs(w.end * 30 - Math.round(w.end * 30)) < 1e-4, `end ${w.end}`);
  });
  r.patch_durations.forEach((d, i) => assert.ok(d >= r.patch_source_durations[i], 'a patch was cut short'));
});
t('durations are pinned: tpad then trim on picture, apad then atrim on sound, -t on both outputs', () => {
  const b = J.JOBS.take_patch.build(tp());
  const g = graph(b);
  assert.ok(g.includes('tpad=stop_mode=clone:stop_duration=1,trim=duration=2.533333'), g);
  assert.ok(g.includes('trim=end_frame=1,tpad=stop_mode=clone:stop_duration=2.266667,trim=duration=2.266667'), g);
  assert.ok(g.includes('apad,atrim=duration=2.266667'), g);
  assert.ok(g.includes('concat=n=3:v=1:a=1[vcat][acat];[acat]asplit=2[amux][anar]'), g);
  assert.strictEqual(b.argv.filter(a => a === '-t').length, 3 + 2, 'two seeked takes and one hold, plus two outputs');
  assert.ok(b.argv.join(' ').includes('-map [anar] -c:a pcm_s24le -t 8.700000'), b.argv.join(' '));
});
t('without a narration_output there is one output and no asplit', () => {
  const b = J.JOBS.take_patch.build({ ...tp(), narration_output: undefined });
  assert.ok(graph(b).endsWith('concat=n=3:v=1:a=1[vcat][amux]'), graph(b));
  assert.ok(!b.argv.includes('[anar]'));
});
t('hdr has no default; tonemap adds the zscale chain, sdr does not', () => {
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), hdr: undefined }), /hdr/);
  const tm = graph(J.JOBS.take_patch.build({ ...tp(), hdr: 'tonemap' }));
  assert.ok(tm.includes('tonemap=tonemap=hable'), tm);
  const sd = graph(J.JOBS.take_patch.build(tp()));
  assert.ok(!sd.includes('zscale'), sd);
});
t('a patch that opens the episode holds the FIRST frame of the next take', () => {
  const p = tp();
  p.edl = [{ kind: 'patch', audio: touch('vl/line0.mp3'), duration: 1.5 }, { kind: 'take', start: 4, end: 9 }];
  const b = J.JOBS.take_patch.build(p);
  assert.ok(b.argv.join(' ').includes('-ss 4.000000 -t 0.066667 -i'), b.argv.join(' '));
});
t('bad edls are refused at submit', () => {
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: null }), /re-record/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [] }), /at least one/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [{ kind: 'patch', audio: touch('vl/x.mp3'), duration: 2 }] }), /no take item/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [{ kind: 'take', start: 2, end: 2.05 }] }), /shorter than two crossfades/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [{ kind: 'cut', start: 0, end: 3 }] }), /kind/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [{ kind: 'take', start: 0, end: 3 }, { kind: 'patch', audio: 'vl/missing.mp3', duration: 2 }] }), /no such file/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: [{ kind: 'take', start: 0, end: 3 }, { kind: 'patch', audio: touch('vl/y.mp3') }] }), /duration/);
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), output: '../escape.mp4' }), /escapes|outside/);
  const many = Array.from({ length: 65 }, (_, i) => ({ kind: 'take', start: i, end: i + 0.9 }));
  assert.throws(() => J.JOBS.take_patch.build({ ...tp(), edl: many }), /too many/);
});

section('\n-- V3: must_cover, no clone voice over the presenter\'s face --');
t('a window wholly inside one cutaway, inside its fades, renders', () => {
  const r = J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 4.5, end: 9.5 }] }).parse();
  assert.strictEqual(r.must_cover, 1);
});
t('a window that reaches into a fade is refused', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 4.1, end: 9 }] }), /not inside one opaque cutaway/);
});
t('a window spanning two cutaways, or none, is refused', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 9, end: 21 }] }), /not inside one opaque/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 12, end: 14 }] }), /presenter would show/);
});
t('stacked: a payload-zone cutaway leaves the face visible, so only full-frame counts', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...st(), emphasis: [], must_cover: [{ start: 3, end: 5 }] }), /full-frame cutaway/);
  const r = J.JOBS.presenter_composite.build({ ...st(), emphasis: [], must_cover: [{ start: 8.5, end: 10.5 }] }).parse();
  assert.strictEqual(r.must_cover, 1);
});
t('stacked: an emphasis window over a covered span puts the head back, refused', () => {
  const p = { ...st(), emphasis: [{ start: 9, end: 10 }], must_cover: [{ start: 8.5, end: 10.5 }] };
  assert.throws(() => J.JOBS.presenter_composite.build(p), /overlaps emphasis/);
});
t('must_cover that is not an array is refused, never defaulted', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), must_cover: '[{"start":4.5,"end":9.5}]' }), /must_cover: must be an array/);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pc(), must_cover: [{ start: 6, end: 5 }] }), /end must exceed start/);
});

section('\n-- V4: probe reports HDR so the caller can set take_patch hdr --');
t('probe asks for color_transfer and pix_fmt and flags HLG and PQ', () => {
  const b = J.JOBS.probe.build({ path: touch('vl/p.mov') });
  assert.ok(b.argv.join(' ').includes('color_transfer,pix_fmt'), b.argv.join(' '));
  const hlg = b.parse(JSON.stringify({ format: { duration: '9.5' }, streams: [{ width: 3840, height: 2160, r_frame_rate: '30/1', color_transfer: 'arib-std-b67', pix_fmt: 'yuv420p10le' }] }));
  assert.strictEqual(hlg.hdr, true);
  const sdr = b.parse(JSON.stringify({ format: { duration: '9.5' }, streams: [{ width: 1920, height: 1080, r_frame_rate: '30/1', color_transfer: 'bt709' }] }));
  assert.strictEqual(sdr.hdr, false);
  const audio = b.parse(JSON.stringify({ format: { duration: '2.1' }, streams: [{}] }));
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
