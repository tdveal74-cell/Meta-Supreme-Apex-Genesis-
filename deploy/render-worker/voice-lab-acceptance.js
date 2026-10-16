'use strict';
/**
 * Voice Lab acceptance: REAL ffmpeg, synthetic media, measured output.
 *
 * jobs.test.js pins what the builders emit and runs no ffmpeg, so it cannot see
 * a defect that only shows up in the samples or the frames. This can, and the
 * first run proved why it has to exist: take_patch trimmed audio to the second
 * and video to the frame, every splice left the picture up to a frame longer
 * than the sound, and every builder test was green while it did.
 *
 * It needs ffmpeg and ffprobe with libx264, libx265, libmp3lame and zscale,
 * which the Ubuntu 24.04 package carries. It is NOT in `npm test` and not in
 * render-worker-ci.yml, because neither installs ffmpeg; it is run by hand on
 * the box, and in the container where it was written, and it exits non-zero on
 * any failure.
 *
 *   node voice-lab-acceptance.js [work_dir]
 */
const assert = require('assert');
const { execFileSync, spawnSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');
const J = require('./jobs.js');

const ROOT = process.argv[2] || fs.mkdtempSync(path.join(os.tmpdir(), 'voice-lab-'));
fs.rmSync(ROOT, { recursive: true, force: true });
fs.mkdirSync(ROOT, { recursive: true });
J.setRoot(ROOT);

const FPS = 30;
const ff = (a) => execFileSync('ffmpeg', ['-nostdin', '-hide_banner', '-loglevel', 'error', '-y', ...a], { cwd: ROOT });
const stderrOf = (a) => spawnSync('ffmpeg', ['-nostdin', '-hide_banner', '-nostats', ...a], { cwd: ROOT }).stderr.toString();
const dur = (f) => Number(JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format=duration', '-of', 'json', f], { cwd: ROOT })).format.duration);
const run = (b) => b.parse(execFileSync(b.bin, b.argv, { cwd: ROOT }).toString(), '');
// take_patch is native: it runs one ffmpeg per segment, then the join.
const runNative = (b) => b.native();

let pass = 0;
const check = async (name, fn) => { await fn(); pass++; console.log('  PASS  ' + name); };

(async () => {

// The take: every frame's own index is written into its pixels, Y = 16 + (N mod
// 200) and U = 64 + 64 * floor(N / 200), so a frame of the output can be traced
// to the exact source frame it came from. Flat frames survive x264 at crf 10 to
// within one code value. The sound is a 440 Hz tone standing in for Tee's voice.
ff(['-f', 'lavfi', '-i', `color=c=black:s=320x568:r=${FPS}:d=12,format=yuv420p,geq=lum=16+mod(N\\,200):cb=64+64*floor(N/200):cr=128`,
    '-f', 'lavfi', '-i', 'sine=f=440:r=48000:d=12',
    '-c:v', 'libx264', '-crf', '10', '-g', '30', '-bf', '2', '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-shortest', 'take.mov']);
// The clone's re-read of one line: 1000 Hz at 44.1 kHz, as an mp3, the way an
// ElevenLabs file arrives. Its real length comes from ffprobe, as the n8n lane
// will get it from the probe job.
ff(['-f', 'lavfi', '-i', 'sine=f=1000:r=44100:d=2.25', '-c:a', 'libmp3lame', 'line1.mp3']);
const cloneLen = dur('line1.mp3');

const edl = [
  { kind: 'take', start: 0.88, end: 3.4, lines: [0] },
  { kind: 'patch', audio: 'line1.mp3', duration: cloneLen, lines: [1] },
  { kind: 'take', start: 6.1, end: 10.0, lines: [2] },
];
const r = await runNative(J.JOBS.take_patch.build({ take: 'take.mov', take_duration: dur('take.mov'), output: 'base.mp4', narration_output: 'narration.wav', hdr: 'sdr', edl }));
const w = r.patch_windows[0];

console.log('\n-- take_patch, measured --');
const frames = (f, key) => [...stderrOf(['-i', f, '-vf', `signalstats,metadata=print:key=lavfi.signalstats.${key}`, '-f', 'null', '-'])
  .matchAll(new RegExp(`${key}=([\\d.]+)`, 'g'))].map(m => +m[1]);
const ids = (f) => { const y = frames(f, 'YAVG'); const u = frames(f, 'UAVG'); return y.map((v, i) => Math.round(v - 16) + 200 * Math.round((u[i] - 64) / 64)); };

await check('the synthetic take decodes as frames 0..359 in order (the instrument works)', () => {
  const t = ids('take.mov');
  assert.strictEqual(t.length, 360);
  assert.ok(t.every((n, i) => n === i), 'frame index encoding did not survive the encode');
});
const base = ids('base.mp4');
await check('every output frame comes from the source frame the edl asked for', () => {
  // 0.88 s sits 0.4 of a frame past frame 26, which the accurate seek drops.
  // Each output slot j shows the source frame nearest 0.88 + j/30: frame 26
  // for slot 0 is gone, so frame 27 fills it, then 27..101, 76 frames in all.
  // That is the picture on the audio's own clock (the critic's lip-sync nit).
  // The patch holds frame 101, two frames inside the take's snapped end, for
  // 69 frames (2.298776 s rounded UP). Then 6.1 s is exactly frame 183.
  const want = [
    27, ...Array.from({ length: 75 }, (_, k) => 27 + k),
    ...Array(69).fill(101),
    ...Array.from({ length: 117 }, (_, k) => 183 + k),
  ];
  assert.strictEqual(base.length, want.length, `base has ${base.length} frames, planned ${want.length}`);
  const bad = base.findIndex((n, i) => n !== want[i]);
  assert.strictEqual(bad, -1, bad === -1 ? '' : `frame ${bad} shows source ${base[bad]}, wanted ${want[bad]}`);
});
await check('picture and sound are the same length, to the frame (the defect this run found)', () => {
  const planned = Math.round(r.duration * FPS);
  assert.strictEqual(base.length, planned);
  assert.ok(Math.abs(dur('narration.wav') - r.duration) < 1 / 48000 * 2, `narration ${dur('narration.wav')} vs ${r.duration}`);
});
await check('the held frames land exactly on the returned patch window', () => {
  const fz = stderrOf(['-i', 'base.mp4', '-vf', 'freezedetect=n=-60dB:d=0.5', '-f', 'null', '-']);
  const s = +(/freeze_start: ([\d.]+)/.exec(fz) || [])[1];
  const e = +(/freeze_end: ([\d.]+)/.exec(fz) || [])[1];
  // The freeze may begin ONE frame early: the take's last shown frame is the
  // very frame the patch holds, so the two read as one still. Never more.
  assert.ok(s >= w.start - 1.5 / FPS && s <= w.start + 0.5 / FPS && Math.abs(e - w.end) < 0.5 / FPS, `held ${s}-${e}, window ${w.start}-${w.end}`);
});
const rms = (s, e, hz) => {
  const m = /RMS level dB:\s*(-?[\d.]+|-inf)/.exec(stderrOf(['-ss', String(s), '-t', String(e - s), '-i', 'narration.wav',
    '-af', `bandpass=f=${hz}:w=60,astats=metadata=0`, '-f', 'null', '-']));
  return m[1] === '-inf' ? -200 : +m[1];
};
await check('your voice before and after the patch, the clone only inside it, 30 dB apart', () => {
  const spans = { before: [0.2, w.start - 0.1], inside: [w.start + 0.1, w.end - 0.1], after: [w.end + 0.1, r.duration - 0.2] };
  const lv = Object.fromEntries(Object.entries(spans).map(([k, [s, e]]) => [k, { v440: rms(s, e, 440), v1000: rms(s, e, 1000) }]));
  console.log('        ' + JSON.stringify(lv));
  assert.ok(lv.before.v440 - lv.before.v1000 > 30);
  assert.ok(lv.inside.v1000 - lv.inside.v440 > 30);
  assert.ok(lv.after.v440 - lv.after.v1000 > 30);
});
await check('no click at a join: the largest sample step is no bigger than the 1000 Hz tone\'s own', () => {
  const o = stderrOf(['-i', 'narration.wav', '-af', 'astats=metadata=0', '-f', 'null', '-']);
  // astats reports pcm_s24le steps in 32 bit integer units.
  const step = Number(/Max difference:\s*([\d.e-]+)/.exec(o)[1]) / 2 ** 31;
  const peak = 10 ** (Number(/Peak level dB:\s*(-?[\d.]+)/.exec(o)[1]) / 20);
  const sine = peak * 2 * Math.PI * 1000 / 48000;
  console.log(`        max step ${step.toFixed(5)}, a clean 1000 Hz sine at this peak steps ${sine.toFixed(5)}`);
  assert.ok(step <= sine * 1.05);
});

console.log('\n-- presenter_composite with must_cover, measured --');
ff(['-f', 'lavfi', '-i', `color=c=black:s=320x568:r=${FPS}:d=4,format=yuv420p,geq=lum=120:cb=128:cr=240`, '-c:v', 'libx264', '-crf', '10', '-pix_fmt', 'yuv420p', 'cut.mp4']);
// No must_cover is sent anywhere below: take_patch wrote the clone windows into
// base.mp4's own metadata, and presenter_composite reads them back from the file.
const pcBase = { avatar: 'base.mp4', width: 320, height: 568, fps: FPS, duration: r.duration };
// A frame is the held face when it reads Y 117 and V 128 (source frame 101).
const isFace = (y, v) => Math.abs(y - 117) < 4 && Math.abs(v - 128) < 4;
const faceFramesIn = (f) => {
  const y = frames(f, 'YAVG'), v = frames(f, 'VAVG');
  const a = Math.round(w.start * FPS), b = Math.round(w.end * FPS);
  return { n: b - a, face: y.slice(a, b).filter((yy, i) => isFace(yy, v[a + i])).length };
};
await check('the windows ride in the file: a cutaway that misses them is refused with no must_cover sent', () => {
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pcBase, output: 'x.mp4', cutaways: [{ path: 'cut.mp4', start: 5.0, end: 7.0 }] }),
    /not inside one scheduled cutaway/);
});
await check('a COPY and a symlink of the base track carry the windows too (round three: a copy rendered 46 face frames)', () => {
  fs.mkdirSync(path.join(ROOT, 'final'), { recursive: true });
  fs.copyFileSync(path.join(ROOT, 'base.mp4'), path.join(ROOT, 'final/base.mp4'));
  fs.symlinkSync(path.join(ROOT, 'base.mp4'), path.join(ROOT, 'final/link.mp4'));
  for (const av of ['final/base.mp4', 'final/link.mp4']) {
    assert.throws(() => J.JOBS.presenter_composite.build({ ...pcBase, avatar: av, output: 'x.mp4', cutaways: [{ path: 'cut.mp4', start: 5.0, end: 7.0 }] }),
      /not inside one scheduled cutaway/, av);
  }
});
await check('a cutaway whose 0.3 s fade overlaps the clone shows the plate through the fade, never the face', () => {
  run(J.JOBS.presenter_composite.build({ ...pcBase, output: 'fade.mp4', cutaways: [{ path: 'cut.mp4', start: 2.4, end: 5.0 }] }));
  const m = faceFramesIn('fade.mp4');
  assert.strictEqual(m.face, 0, `${m.face} of ${m.n} frames in the window show the held face`);
});
await check('a hard cut (fade 0) laid exactly on a window whose edge rounds UP leaves no frame of face', async () => {
  // The window above starts at 76/30 s, which six decimals round DOWN, so it
  // could never show the defect. 173/30 s rounds UP to 5.766667, past the frame
  // it belongs to: before the fix the composite showed that frame, the held
  // face, under the clone (critic N2). The hold is source frame 171, Y = 187.
  const e2 = await runNative(J.JOBS.take_patch.build({ take: 'take.mov', take_duration: dur('take.mov'), output: 'base2.mp4', hdr: 'sdr',
    edl: [{ kind: 'take', start: 0, end: 5.766667 }, { kind: 'patch', audio: 'line1.mp3', duration: cloneLen }, { kind: 'take', start: 8, end: 10 }] }));
  const w2 = e2.patch_windows[0];
  run(J.JOBS.presenter_composite.build({ avatar: 'base2.mp4', width: 320, height: 568, fps: FPS, duration: e2.duration,
    output: 'hard.mp4', fade: 0, cutaways: [{ path: 'cut.mp4', start: w2.start, end: w2.end }] }));
  const y = frames('hard.mp4', 'YAVG'), v = frames('hard.mp4', 'VAVG');
  const a2 = Math.round(w2.start * FPS), b2 = Math.round(w2.end * FPS);
  const face = [];
  for (let i = a2; i < b2; i++) if (Math.abs(y[i] - 187.5) < 4 && Math.abs(v[i] - 128) < 4) face.push(i);
  assert.strictEqual(face.length, 0, `frames ${face.join(',')} of the window ${a2}..${b2 - 1} show the held face`);
});
await check('with a covering cutaway, no frame of the take shows anywhere in the patch window', () => {
  run(J.JOBS.presenter_composite.build({ ...pcBase, output: 'master.mp4', cutaways: [{ path: 'cut.mp4', start: 2.2, end: 5.2 }] }));
  const v = frames('master.mp4', 'VAVG');
  const inside = v.slice(Math.round(w.start * FPS), Math.round(w.end * FPS));
  assert.strictEqual(inside.length, 69);
  assert.ok(inside.every(x => x > 238), `min V inside the window ${Math.min(...inside)}; the cutaway is 240 and the take 128`);
});

await check('a cutaway with no frames to show (in past its end) shows the black plate, never the face', () => {
  run(J.JOBS.presenter_composite.build({ ...pcBase, output: 'empty.mp4', cutaways: [{ path: 'cut.mp4', start: 2.2, end: 5.2, in: 30 }] }));
  const y = frames('empty.mp4', 'YAVG').slice(Math.round(w.start * FPS), Math.round(w.end * FPS));
  // The held take frame is source 101, Y = 117. The plate is black, Y = 16.
  assert.ok(y.every(v => v < 20), `max Y inside the window ${Math.max(...y)}; the held face frame reads 117`);
});

const commentOf = (f) => {
  const j = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'format_tags', '-of', 'json', path.join(ROOT, f)]).toString());
  const tags = (j.format && j.format.tags) || {};
  const k = Object.keys(tags).find(x => x.toLowerCase() === 'comment');
  return k === undefined ? null : tags[k];
};
await check('the finished master does not carry the clone windows (ruled 2026-10-16), the base track does', () => {
  assert.ok(String(commentOf('base.mp4')).startsWith('voicelab-must-cover:'), 'the base lost its tag');
  const c = commentOf('master.mp4');
  assert.ok(c === null || !String(c).toLowerCase().includes('voicelab'), `the master carries: ${c}`);
});
await check('a base re-timed after take_patch is refused, not composited on its stale windows (round four: 30 face frames)', () => {
  // A re-encode that cuts the first second keeps the comment tag, as the
  // worker's own conform_grain keep_segments did in the critic's run.
  ff(['-ss', '1', '-i', 'base.mp4', '-c:v', 'libx264', '-crf', '10', '-pix_fmt', 'yuv420p', '-c:a', 'aac', 'retimed.mp4']);
  assert.ok(String(commentOf('retimed.mp4')).startsWith('voicelab-must-cover:'), 'the re-encode did not carry the tag, so this proves nothing');
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pcBase, avatar: 'retimed.mp4', duration: undefined, output: 'y.mp4',
    cutaways: [{ path: 'cut.mp4', start: 2.2, end: 5.2 }] }), /but its Voice Lab windows were written for a/);
});
await check('an mkv copy keeps its windows under COMMENT, and a .ts copy, which drops them, is refused', () => {
  ff(['-i', 'base.mp4', '-map', '0', '-c', 'copy', 'copy.mkv']);
  ff(['-i', 'base.mp4', '-map', '0', '-c', 'copy', 'copy.ts']);
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pcBase, avatar: 'copy.mkv', output: 'z.mp4', cutaways: [{ path: 'cut.mp4', start: 5.0, end: 7.0 }] }),
    /not inside one scheduled cutaway/);
  assert.ok(J.JOBS.presenter_composite.build({ ...pcBase, avatar: 'copy.mkv', output: 'z.mp4', cutaways: [{ path: 'cut.mp4', start: 2.2, end: 5.2 }] }));
  assert.throws(() => J.JOBS.presenter_composite.build({ ...pcBase, avatar: 'copy.ts', output: 'z.mp4', cutaways: [{ path: 'cut.mp4', start: 2.2, end: 5.2 }] }),
    /must be \.mp4, \.mov, \.m4v, \.mkv or \.webm/);
});

console.log('\n-- take_patch refuses rather than return a short episode --');
// Sound that runs 0.3 s past the picture, as an iPhone file can: the container
// says 12.3 s, the picture ends at 12.0 s.
ff(['-f', 'lavfi', '-i', `color=c=gray:s=320x568:r=${FPS}:d=12`, '-f', 'lavfi', '-i', 'sine=f=440:r=48000:d=12.3',
    '-c:v', 'libx264', '-pix_fmt', 'yuv420p', '-c:a', 'aac', 'long_audio.mov']);
await check('a span ending past the last frame of picture is refused, not rendered without its clone line', async () => {
  const b = J.JOBS.take_patch.build({ take: 'long_audio.mov', take_duration: dur('long_audio.mov'), output: 'la.mp4', hdr: 'sdr',
    edl: [{ kind: 'take', start: 9, end: dur('long_audio.mov') }, { kind: 'patch', audio: 'line1.mp3', duration: cloneLen }] });
  await assert.rejects(b.native(), /picture ends at 12\.0/);
  assert.ok(!fs.existsSync(path.join(ROOT, 'la.mp4')), 'a refused run left an output behind');
});
await check('a clone file longer than its stated duration is refused before the line is cut', async () => {
  const b = J.JOBS.take_patch.build({ take: 'take.mov', take_duration: dur('take.mov'), output: 'short.mp4', hdr: 'sdr',
    edl: [{ kind: 'take', start: 0.88, end: 3.4 }, { kind: 'patch', audio: 'line1.mp3', duration: 1.0 }, { kind: 'take', start: 6.1, end: 10.0 }] });
  await assert.rejects(b.native(), /the end of the line would be cut/);
});

console.log('\n-- an iPhone HDR take --');
ff(['-f', 'lavfi', '-i', `testsrc2=s=1280x720:r=${FPS}:d=4`, '-f', 'lavfi', '-i', 'sine=f=440:r=48000:d=4',
    '-c:v', 'libx265', '-x265-params', 'log-level=error', '-pix_fmt', 'yuv420p10le',
    '-color_primaries', 'bt2020', '-color_trc', 'arib-std-b67', '-colorspace', 'bt2020nc', '-c:a', 'aac', '-shortest', 'hlg.mov']);
await check('probe flags HLG, and the tonemap path renders BT.709 8 bit at the planned length', async () => {
  const pr = run(J.JOBS.probe.build({ path: 'hlg.mov' }));
  assert.strictEqual(pr.hdr, true);
  assert.strictEqual(pr.color_transfer, 'arib-std-b67');
  const h = await runNative(J.JOBS.take_patch.build({ take: 'hlg.mov', take_duration: dur('hlg.mov'), output: 'hlg_base.mp4', hdr: 'tonemap',
    edl: [{ kind: 'take', start: 0, end: 1.5 }, { kind: 'patch', audio: 'line1.mp3', duration: cloneLen }, { kind: 'take', start: 2, end: 3.8 }] }));
  const st = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-show_entries', 'stream=codec_type,pix_fmt,color_transfer', '-of', 'json', 'hlg_base.mp4'], { cwd: ROOT })).streams;
  const v = st.find(s => s.codec_type === 'video');
  assert.strictEqual(v.pix_fmt, 'yuv420p');
  assert.strictEqual(v.color_transfer, 'bt709');
  assert.ok(Math.abs(dur('hlg_base.mp4') - h.duration) < 0.5 / FPS, `${dur('hlg_base.mp4')} vs ${h.duration}`);
});
await check('scaled to the presenter canvas before the tonemap: 1280x720 HLG lands as 640x360 BT.709', async () => {
  const h = await runNative(J.JOBS.take_patch.build({ take: 'hlg.mov', take_duration: dur('hlg.mov'), output: 'hlg_small.mp4', hdr: 'tonemap',
    width: 640, height: 360, edl: [{ kind: 'take', start: 0, end: 1.5 }, { kind: 'patch', audio: 'line1.mp3', duration: cloneLen }, { kind: 'take', start: 2, end: 3.8 }] }));
  const v = JSON.parse(execFileSync('ffprobe', ['-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=width,height,pix_fmt,color_transfer', '-of', 'json', 'hlg_small.mp4'], { cwd: ROOT })).streams[0];
  assert.deepStrictEqual([v.width, v.height, v.pix_fmt, v.color_transfer], [640, 360, 'yuv420p', 'bt709']);
  assert.ok(Math.abs(dur('hlg_small.mp4') - h.duration) < 0.5 / FPS);
  // Brightness against the full-size tonemap: same picture, so the same mean luma within a few codes.
  const big = frames('hlg_base.mp4', 'YAVG'), small = frames('hlg_small.mp4', 'YAVG');
  const mean = (a) => a.reduce((x, y) => x + y, 0) / a.length;
  assert.ok(Math.abs(mean(big) - mean(small)) < 4, `mean Y ${mean(big).toFixed(1)} full size vs ${mean(small).toFixed(1)} scaled first`);
});

console.log(`\n${pass} passed, 0 failed  (work dir ${ROOT})\n`);
})().catch((e) => { console.error(e); process.exit(1); });
