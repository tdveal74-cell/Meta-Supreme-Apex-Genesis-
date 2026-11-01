'use strict';
/**
 * ACX Node assembly tests. Same split as jobs.test.js: these pin the plan, the
 * captions, the ASS text and every argv and filter graph the job would run.
 * They run no ffmpeg and prove no pixel. The ffmpeg level acceptance is the
 * Proof 0 comparison in DEPLOY.md, ACX Node section, run on a real box.
 *
 *   node acx_node.test.js
 */
const assert = require('assert');
const fs = require('fs');
const os = require('os');
const path = require('path');
const J = require('./jobs.js');
const A = require('./acx_node.js');

const ROOT = fs.mkdtempSync(path.join(os.tmpdir(), 'acx-node-test-'));
J.setRoot(ROOT);
const touch = (rel) => { const abs = path.join(ROOT, rel); fs.mkdirSync(path.dirname(abs), { recursive: true }); fs.writeFileSync(abs, 'x'); return rel; };
/**
 * A minimal sfnt carrying only a name table with one Windows full name record,
 * so the font check reads a real name table rather than trusting the filename.
 */
function sfnt(fullName, platform = 3) {
  const str = platform === 3 ? Buffer.from(fullName, 'utf16le').swap16() : Buffer.from(fullName, 'latin1');
  const nameTable = Buffer.alloc(6 + 12 + str.length);
  nameTable.writeUInt16BE(0, 0); nameTable.writeUInt16BE(1, 2); nameTable.writeUInt16BE(18, 4);
  nameTable.writeUInt16BE(platform, 6); nameTable.writeUInt16BE(1, 8); nameTable.writeUInt16BE(0x409, 10); nameTable.writeUInt16BE(4, 12);
  nameTable.writeUInt16BE(str.length, 14); nameTable.writeUInt16BE(0, 16);
  str.copy(nameTable, 18);
  const head = Buffer.alloc(12 + 16);
  head.writeUInt32BE(0x00010000, 0); head.writeUInt16BE(1, 4);
  head.write('name', 12, 'latin1'); head.writeUInt32BE(0, 16); head.writeUInt32BE(28, 20); head.writeUInt32BE(nameTable.length, 24);
  return Buffer.concat([head, nameTable]);
}
const writeFont = (rel, fullName, platform) => { const abs = path.join(ROOT, rel); fs.mkdirSync(path.dirname(abs), { recursive: true }); fs.writeFileSync(abs, sfnt(fullName, platform)); return rel; };
for (const [f, name] of Object.entries(A.FONT_FACES)) writeFont('fonts/' + f, name);
const IMAGES = { R1: touch('img/R1.png'), R2: touch('img/R2.png'), R3: touch('img/R3.png') };
const LINES = ['L01', 'L02', 'L03', 'L04'].map(l => touch('lines/' + l + '.mp3'));
const BEATS = [
  { id: 'B01', image: 'R1', line: LINES[0], text: 'Third dive. Same query. Two empty returns behind me.' },
  { id: 'B02', image: 'R1', line: LINES[1], text: 'Something answered.' },
  { id: 'B03', image: 'R2', line: LINES[2], text: 'Purge.', verdict: true },
  { id: 'B04', image: 'R3', line: LINES[3], text: 'You already climbed this. I kept the whole way. Every step. Follow me.' },
];
const base = (over) => Object.assign({ output_dir: 'out/node01', fonts_dir: 'fonts', images: IMAGES, beats: BEATS }, over || {});
const build = (over) => J.JOBS.acx_node_assemble.build(base(over));

let pass = 0, fail = 0;
const pending = [];
function t(name, fn) {
  const ok = () => { pass++; console.log('  ok   ' + name); };
  const bad = (e) => { fail++; console.log('  FAIL ' + name + '\n       ' + (e && e.message || e).split('\n')[0]); };
  try {
    const r = fn();
    // an async test is counted when it settles, never before (critic F9)
    if (r && typeof r.then === "function") pending.push(r.then(ok, bad)); else ok();
  } catch (e) { bad(e); }
}
function refuses(name, params, re) {
  t(name, () => { assert.throws(() => J.JOBS.acx_node_assemble.build(params), (e) => e instanceof J.BadJob && re.test(e.message)); });
}

console.log('\n-- the job table --');
t('both jobs are registered and native', () => {
  assert.ok(J.JOBS.acx_node_assemble); assert.ok(J.JOBS.word_timings);
  const b = build();
  assert.strictEqual(typeof b.native, 'function'); assert.strictEqual(typeof b.abort, 'function');
});

console.log('\n-- the beat plan: picture follows voice --');
t('beats start after the cold open and gaps follow the image-change rule', () => {
  const { beats, total } = A.planBeats(build().plan.beats, build().plan.pauses, { B01: 3.762, B02: 1.280, B03: 1.097, B04: 4.598 });
  assert.strictEqual(beats[0].start, 2.5);
  assert.strictEqual(beats[0].end, 6.262);
  assert.strictEqual(beats[0].gap, 0.9, 'same image: within_image');
  assert.strictEqual(beats[1].gap, 1.8, 'image changes after B02');
  assert.strictEqual(beats[3].gap, 5.0, 'last beat: end hold');
  // 2.5 + 3.762 + 0.9 + 1.280 + 1.8 + 1.097 + 1.8 + 4.598 + 5.0
  assert.strictEqual(total, 22.737);
});
t('extra_after adds to the gap of the named beat only', () => {
  const b = build({ pauses: { extra_after: { B03: 1.1 } } });
  const { beats } = A.planBeats(b.plan.beats, b.plan.pauses, { B01: 1, B02: 1, B03: 1, B04: 1 });
  assert.strictEqual(beats[2].gap, 2.9); assert.strictEqual(beats[1].gap, 1.8);
});
t('a missing measured duration throws rather than planning from nothing', () => {
  assert.throws(() => A.planBeats(build().plan.beats, build().plan.pauses, { B01: 1 }), /no measured duration for beat B02/);
});
t('consecutive beats on one image are one shot, hard cuts between images', () => {
  const b = build();
  const { beats } = A.planBeats(b.plan.beats, b.plan.pauses, { B01: 3.762, B02: 1.280, B03: 1.097, B04: 4.598 });
  const shots = A.planShots(beats);
  assert.deepStrictEqual(shots.map(s => s.image), ['R1', 'R2', 'R3']);
  assert.strictEqual(shots[0].start, 0); assert.strictEqual(shots[0].end, 10.242, '2.5 + 3.762 + 0.9 + 1.280 + 1.8');
  assert.strictEqual(shots[1].start, 10.242); assert.strictEqual(shots[2].end, 22.737);
});

console.log('\n-- captions: the sheet text, the model\'s timing --');
t('sheet words take the matched word timings; a model insertion is dropped', () => {
  const words = [
    { text: 'It', start: 0.1, end: 0.2 }, { text: 'took', start: 0.2, end: 0.4 }, { text: 'the', start: 0.4, end: 0.5 },
    { text: 'piece', start: 0.5, end: 0.9 }, { text: 'Mhm.', start: 6.4, end: 6.5 },
  ];
  const out = A.timedSheetWords('It took the piece', words, 6.9);
  assert.deepStrictEqual(out.map(w => w.w), ['It', 'took', 'the', 'piece'], 'the breath never reaches the screen');
  assert.strictEqual(out[3].end, 0.9);
});
t('a sheet word rendered differently takes the timing of what replaced it', () => {
  const words = [{ text: 'resonance', start: 1, end: 1.5 }, { text: 'at', start: 1.5, end: 1.6 }, { text: '99', start: 1.6, end: 2.2 }];
  const out = A.timedSheetWords('resonance at ninety-nine', words, 3);
  assert.strictEqual(out[2].w, 'ninety-nine'); assert.strictEqual(out[2].start, 1.6); assert.strictEqual(out[2].end, 2.2);
});
t('no word timings: words share the measured line span evenly', () => {
  const out = A.timedSheetWords('one two three four', [], 2.0);
  assert.deepStrictEqual(out.map(w => [w.start, w.end]), [[0, 0.5], [0.5, 1], [1, 1.5], [1.5, 2]]);
});
t('chunks break at punctuation, join tiny phrases, carry the verdict flag, never overlap', () => {
  const b = build();
  const { beats } = A.planBeats(b.plan.beats, b.plan.pauses, { B01: 3.762, B02: 1.280, B03: 1.097, B04: 4.598 });
  const chunks = A.captionChunks(beats, null);
  assert.strictEqual(chunks[0].text, 'Third dive. Same query.', 'two short phrases join: ' + chunks[0].text);
  assert.strictEqual(chunks[1].text, 'Two empty returns behind me.');
  const verdicts = chunks.filter(c => c.verdict);
  assert.deepStrictEqual(verdicts.map(c => c.text), ['Purge.']);
  for (let k = 0; k + 1 < chunks.length; k++) assert.ok(chunks[k].end <= chunks[k + 1].start, 'overlap at ' + k);
  const joined = beats.map(bt => chunks.filter(c => c.beat === bt.id).map(c => c.text).join(' '));
  assert.deepStrictEqual(joined, beats.map(bt => bt.text), 'chunks reassemble to the sheet text on every beat');
});
t('ASS styles request the SemiBold face with Bold off, cyan and red in BGR, verdict lines on the Verdict style', () => {
  const chunks = [{ start: 2.5, end: 4.19, text: 'Third dive.', verdict: false, beat: 'B01' }, { start: 32.6, end: 33.47, text: 'Purge.', verdict: true, beat: 'B03' }];
  const ass = A.assText(chunks, build().plan.style);
  assert.ok(ass.includes('Style: Cap,Chakra Petch SemiBold,66,&H00D8D136,&H00D8D136,&H000F0904,&H80000000,0,0,0,0,'), ass.split('\n').find(l => l.startsWith('Style: Cap')));
  assert.ok(ass.includes('Style: Verdict,Chakra Petch SemiBold,66,&H006A62D9,'), 'verdict red in BGR');
  assert.ok(ass.includes('Dialogue: 0,0:00:02.50,0:00:04.19,Cap,,0,0,0,,Third dive.'));
  assert.ok(ass.includes('Dialogue: 0,0:00:32.60,0:00:33.47,Verdict,,0,0,0,,Purge.'));
  assert.ok(ass.includes(',2,80,200,560,1'), 'bottom centre, 560 px above the platform band');
  assert.strictEqual(A.srtText(chunks).split('\n')[1], '00:00:02,500 --> 00:00:04,190');
});

console.log('\n-- argv and filter graphs --');
t('the Copy treatment is a 14 ms double at -7 dB with the two shelves; a dry line is a plain decode', () => {
  const tr = { delay_ms: 14, double_db: -7, low_shelf_db: 2, low_shelf_hz: 180, high_shelf_db: -2.5, high_shelf_hz: 6000 };
  const a = A.decodeArgv('lines/L10.mp3', 'seg/B10.wav', tr);
  assert.strictEqual(a[a.indexOf('-filter_complex') + 1], 'asplit[a1][a2];[a2]adelay=14,volume=-7dB[a2d];[a1][a2d]amix=inputs=2:normalize=0,lowshelf=g=2:f=180,highshelf=g=-2.5:f=6000');
  const d = A.decodeArgv('lines/L01.mp3', 'seg/B01.wav', null);
  assert.ok(!d.includes('-filter_complex')); assert.ok(d.includes('pcm_s16le') && d.includes('48000'));
});
t('the limiter sits 0.5 dB under the true peak ceiling and the gain is applied before it', () => {
  const b = build();
  assert.strictEqual(Number(b.plan.limit_linear.toFixed(4)), 0.8414, '-1.5 dBFS for a -1 dBTP ceiling');
  const a = A.gainLimitArgv('raw.wav', 'mix.wav', 5.99, b.plan.limit_linear);
  assert.strictEqual(a[a.indexOf('-af') + 1], 'volume=5.99dB,alimiter=limit=0.8414:attack=5:release=60:level=false');
});
t('loudnorm is measured, never applied: the measure argv ends in -f null', () => {
  const a = A.measureArgv('mix.wav', -14, -1);
  assert.deepStrictEqual(a.slice(-3), ['-f', 'null', '-']);
  assert.ok(a.includes('loudnorm=I=-14:TP=-1:LRA=11:print_format=json'));
  assert.ok(A.measureArgv('raw.wav', -14, -1, 'volume=5.99dB').includes('volume=5.99dB,loudnorm=I=-14:TP=-1:LRA=11:print_format=json'), 'the unlimited probe measures in float inside the chain');
});
t('a shot is a slow push from 1.00 to 1.05 over its own frame count at double resolution, CRF 14', () => {
  const o = build().plan.options;
  const a = A.shotArgv('img/R1.png', 305, 'seg/shot0.mp4', o);
  const vf = a[a.indexOf('-vf') + 1];
  assert.ok(vf.startsWith('scale=2160:3840:flags=lanczos,zoompan='), vf);
  assert.ok(vf.includes(`z='min(1+${0.05 / 304}*on,1.05)':d=305:`), vf);
  assert.ok(vf.includes('s=1080x1920:fps=30,format=yuv420p'));
  assert.deepStrictEqual(a.slice(a.indexOf('-frames:v'), a.indexOf('-frames:v') + 2), ['-frames:v', '305']);
  assert.ok(a.includes('14'), 'crf 14 for the intermediate');
});
t('overlays: the disclosure is three lines at 30 px above the caption band, on the open and the end, verbatim', () => {
  const o = Object.assign({ cold_open: 2.5, last_line_end: 61.209 }, build().plan.options);
  const a = A.overlayArgv('silent.mp4', 'out/node01/captions.ass', 'picture.mp4', o);
  const vf = a[a.indexOf('-vf') + 1];
  assert.strictEqual(A.DISCLOSURE_LINES.join(' '), A.DISCLOSURE);
  for (const [i, line] of A.DISCLOSURE_LINES.entries()) {
    assert.ok(vf.includes(`text='${line}':fontcolor=#36D1D8:fontsize=30:x=(w-text_w)/2:y=${1100 + 40 * i}:enable='between(t,0,5)'`), 'open ' + i);
    assert.ok(vf.includes(`text='${line}':fontcolor=#36D1D8:fontsize=30:x=(w-text_w)/2:y=${1100 + 40 * i}:enable='gte(t,61.809)'`), 'end ' + i);
  }
  assert.ok(vf.includes("text='NODE 01':fontcolor=#36D1D8:fontsize=120:x=(w-text_w)/2:y=420:enable='between(t,0,4)'"), 'open title above the book');
  assert.ok(vf.includes("text='THE ORCHESTRATOR':fontcolor=#36D1D8:fontsize=56:x=(w-text_w)/2:y=770:enable='gte(t,61.809)'"));
  assert.ok(vf.endsWith(",ass='out/node01/captions.ass':fontsdir='" + o.fonts_dir + "'"), vf.slice(-120));
  assert.ok(!vf.includes('#D9626A'), 'no red in any overlay; red is the caption style on verdict beats only');
});
t('every libx264 encode pins its thread count to 6, so the bytes do not follow the host core count', () => {
  const o = Object.assign({ cold_open: 2.5, last_line_end: 61.209 }, build().plan.options);
  assert.strictEqual(A.X264_THREADS, 6);
  const encodes = {
    shot: A.shotArgv('img/R1.png', 305, 'seg/shot0.mp4', o),
    overlay: A.overlayArgv('silent.mp4', 'out/node01/captions.ass', 'picture.mp4', o),
    master: A.muxArgv('picture.mp4', 'mix.wav', 'master.mp4', o),
  };
  for (const [name, a] of Object.entries(encodes)) {
    assert.ok(a.includes('libx264'), name + ' is a libx264 encode');
    const i = a.indexOf('-threads');
    assert.ok(i > a.indexOf('libx264') && a[i + 1] === '6', name + ' carries -threads 6 after the encoder');
    assert.ok(i < a.length - 1 && a.lastIndexOf('-threads') === i, name + ' carries it once');
  }
  const src = require('fs').readFileSync(require('path').join(__dirname, 'acx_node.js'), 'utf8');
  const total = (src.match(/'libx264'/g) || []).length;
  const pinned = (src.match(/'-threads', String\(X264_THREADS\)/g) || []).length;
  assert.strictEqual(pinned, total, `${total} libx264 encodes in acx_node.js and ${pinned} pinned`);
});
t('the master is H.264 High, CRF 18, 30 fps, yuv420p, AAC 192k 48 kHz, faststart, shortest', () => {
  const a = A.muxArgv('picture.mp4', 'mix.wav', 'master.mp4', build().plan.options);
  for (const need of [['-profile:v', 'high'], ['-crf', '18'], ['-r', '30'], ['-pix_fmt', 'yuv420p'], ['-c:a', 'aac'], ['-b:a', '192k'], ['-ar', '48000'], ['-movflags', '+faststart']]) {
    const i = a.indexOf(need[0]); assert.ok(i >= 0 && a[i + 1] === need[1], need.join(' '));
  }
  assert.ok(a.includes('-shortest'));
});
t('the lint reads two frames a second at 540x960 rgb24 and counts near-colour pixels in a region', () => {
  const a = A.lintArgv('master.mp4');
  assert.ok(a.includes('fps=2,scale=540:960') && a.includes('rawvideo') && a.includes('rgb24'));
  const frame = Buffer.alloc(540 * 960 * 3, 0);
  // paint a 10x10 block of Critic Red at (500, 900): bottom right, inside both platform zones
  for (let y = 900; y < 910; y++) for (let x = 500; x < 510; x++) { const k = (y * 540 + x) * 3; frame[k] = 0xD9; frame[k + 1] = 0x62; frame[k + 2] = 0x6A; }
  assert.strictEqual(A.countNear(frame, '#D9626A', 40), 100);
  assert.strictEqual(A.countNear(frame, '#D9626A', 40, { x0: 459, y0: 0 }), 100, 'right 15 percent');
  assert.strictEqual(A.countNear(frame, '#D9626A', 40, { x0: 0, y0: 768 }), 100, 'bottom 20 percent');
  assert.strictEqual(A.countNear(frame, '#36D1D8', 28), 0);
});
t('the contact sheet is a 5 by 2 xstack of 432x768 tiles', () => {
  const frames = Array.from({ length: 10 }, (_, i) => `frames/f_${i}.png`);
  const a = A.contactArgv(frames, 'sheet.png');
  const fc = a[a.indexOf('-filter_complex') + 1];
  assert.ok(fc.includes('xstack=inputs=10:layout=0_0|432_0|864_0|1296_0|1728_0|0_768|432_768|864_768|1296_768|1728_768[v]'), fc.slice(-120));
});

console.log('\n-- refusals --');
refuses('a missing font face is refused at submit', (() => { const r = base({ fonts_dir: 'fonts2' }); writeFont('fonts2/ChakraPetch--400.ttf', 'Chakra Petch Regular'); return r; })(), /ChakraPetch--600.ttf is missing/);
refuses('a beat on an unknown image is refused', base({ beats: [Object.assign({}, BEATS[0], { image: 'R9' })] }), /beats\[0\].image/);
refuses('a beat with a brace in its text is refused, never escaped', base({ beats: [Object.assign({}, BEATS[0], { text: 'Purge {now}' })] }), /brace, backslash or line break/);
refuses('a reworded disclosure is refused', base({ disclosure: 'Made with AI.' }), /canon line verbatim/);
refuses('a title with a colon is refused rather than escaped into drawtext', base({ title: 'NODE: ONE' }), /drawtext filter cannot take verbatim/);
refuses('a 16:9 canvas is refused until R19 exists', base({ width: 1920, height: 1080 }), /second render \(R19\)/);
refuses('words and words_path together are refused', base({ words: {}, words_path: 'x.json' }), /send one, not both/);
refuses('a copy treatment on a beat that does not exist is refused', base({ copy_treatment: { lines: ['B99'] } }), /no such beat/);
refuses('extra_after on an unknown beat is refused', base({ pauses: { extra_after: { B77: 1 } } }), /no such beat/);
refuses('an output_dir outside the work root is refused', base({ output_dir: '../../etc' }), /output_dir/);
refuses('a missing line file is refused at submit', base({ beats: [Object.assign({}, BEATS[0], { line: 'lines/L99.mp3' })] }), /beats\[0\].line/);

console.log('\n-- fonts and word timings (critic F1, F2) --');
t('the three faces are read from their name tables and recorded on the plan', () => {
  assert.deepStrictEqual(build().plan.options.fonts, A.FONT_FACES);
  assert.strictEqual(A.fontFullName(path.join(ROOT, writeFont('fonts/mac.ttf', 'Chakra Petch Bold', 1))), 'Chakra Petch Bold');
});
t('a text file named like a font is refused at submit, not rendered in a fallback face', () => {
  const dir = 'fonts_text'; for (const f of Object.keys(A.FONT_FACES)) touch(dir + '/' + f);
  assert.throws(() => build({ fonts_dir: dir }), (e) => e instanceof J.BadJob && /ChakraPetch--400.ttf is not a usable font \(shorter than an sfnt header\)/.test(e.message));
  fs.writeFileSync(path.join(ROOT, dir, 'ChakraPetch--400.ttf'), Buffer.concat([Buffer.from('%PDF-1.4'), Buffer.alloc(64)]));
  assert.throws(() => build({ fonts_dir: dir }), (e) => e instanceof J.BadJob && /not an sfnt/.test(e.message));
});
t('a real font with the wrong name is refused by name', () => {
  const dir = 'fonts_wrong'; for (const [f, name] of Object.entries(A.FONT_FACES)) writeFont(dir + '/' + f, name);
  writeFont(dir + '/ChakraPetch--600.ttf', 'Chakra Petch Bold');
  assert.throws(() => build({ fonts_dir: dir }), (e) => e instanceof J.BadJob && /ChakraPetch--600.ttf names itself "Chakra Petch Bold", expected "Chakra Petch SemiBold"/.test(e.message));
});
t('word timings for some beats but not all are refused, so no beat is spread evenly and recorded as timed', () => {
  const one = { B01: [{ text: 'Third', start: 0, end: 0.4 }] };
  assert.throws(() => build({ words: one }), (e) => e instanceof J.BadJob && /words.B02: no word timings for this beat/.test(e.message));
  const all = {}; for (const b of BEATS) all[b.id] = [{ text: b.text.split(' ')[0], start: 0, end: 0.4 }];
  assert.ok(build({ words: all }).plan);
  all.B03 = [];
  assert.throws(() => build({ words: all }), /words.B03: no word timings/);
});

console.log('\n-- word_timings --');
t('word_timings plans one python call with the model and the line files, and refuses a non-json output', () => {
  const b = J.JOBS.word_timings.build({ audio: LINES, output: 'out/words.json' });
  assert.ok(b.plan.argv[0].endsWith('words.py'));
  assert.deepStrictEqual(b.plan.argv.slice(1, 5), ['--model', 'base.en', '--output', path.join(ROOT, 'out/words.json')]);
  assert.strictEqual(b.plan.argv.slice(6).length, 4);
  assert.throws(() => J.JOBS.word_timings.build({ audio: LINES, output: 'out/words.txt' }), /must end .json/);
  assert.throws(() => J.JOBS.word_timings.build({ audio: [], output: 'out/w.json' }), /must be an array/);
});
t('word_timings fails the JOB, not the server, when WHISPER_PYTHON is unset', async () => {
  const saved = process.env.WHISPER_PYTHON; delete process.env.WHISPER_PYTHON;
  try {
    const b = J.JOBS.word_timings.build({ audio: LINES, output: 'out/words.json' });
    await b.native().then(() => { throw new Error('resolved'); }, (e) => assert.ok(/WHISPER_PYTHON is not set/.test(e.message), e.message));
  } finally { if (saved !== undefined) process.env.WHISPER_PYTHON = saved; }
});

Promise.all(pending).then(() => {
  console.log(`\n${pass} passed, ${fail} failed`);
  fs.rmSync(ROOT, { recursive: true, force: true });
  process.exit(fail ? 1 : 0);
});
