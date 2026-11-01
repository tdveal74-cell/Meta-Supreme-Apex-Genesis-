'use strict';
/**
 * ACX Node assembly for the render worker (added 2026-10-28, ruled R22).
 *
 * Two jobs, both native, both argv only, no shell anywhere:
 *
 *   word_timings       one python process (WHISPER_PYTHON, a venv carrying
 *                      faster-whisper) over the line files, word timings out
 *   acx_node_assemble  the Node 01 Proof 0 pipeline, stage for stage, as
 *                      build.py ran it in the cloud sandbox on 2026-10-28:
 *                      decode the owned lines, lay them on a silent timeline,
 *                      raise to the target under a limiter, one slow push shot
 *                      per image, title and disclosure overlays, captions in
 *                      the sheet's own words timed by the word timings, mux,
 *                      thumbnail, contact sheet, a measured canon lint, and a
 *                      build record with every measurement read back from the
 *                      rendered file.
 *
 * Everything that is not a rendered pixel or sample is a pure function here so
 * the test file can pin it without ffmpeg: the beat plan, the caption chunks,
 * the ASS text, every argv and every filter graph. native() only sequences them.
 *
 * Nothing in this file is canon. The canon lives in the manifest the caller
 * sends: palette, type, disclosure, beats. The defaults below are the values
 * Tee ruled or the Proof 0 build used, and every one of them can be overridden.
 */
const fs = require('fs');
const path = require('path');
const { execFile, spawn } = require('child_process');
const crypto = require('crypto');

const SAFE_PATH = /^[A-Za-z0-9_./-]+$/;
// drawtext text is quoted inside a filter graph; rather than escape, refuse.
const SAFE_TEXT = /^[A-Za-z0-9 ,.;!?-]+$/;
// ASS dialogue text: braces open override blocks and a backslash opens a tag.
const SAFE_ASS = /^[^{}\\\r\n]+$/;

const DISCLOSURE = 'Presented with a synthetic voice and synthetic likeness of Terrance Veal, used with his consent.';
/** The three faces the job needs, by file name, and the full name each one must carry in its name table. */
const FONT_FACES = { 'ChakraPetch--400.ttf': 'Chakra Petch Regular', 'ChakraPetch--600.ttf': 'Chakra Petch SemiBold', 'ChakraPetch--700.ttf': 'Chakra Petch Bold' };
const DISCLOSURE_LINES = ['Presented with a synthetic voice and', 'synthetic likeness of Terrance Veal,', 'used with his consent.'];
/**
 * libx264 picks its thread count from the cores it can see, and its bitstream
 * depends on that count, so the same job on a 2 core box and a 4 core sandbox
 * wrote different bytes (measured 2026-11-01: shot 0 hashed 840abf06... on 2
 * cores and 5418cb7a... on 4). Six is what a 4 core host picks on its own, so
 * pinning it makes every host write the Proof 0 bytes. Every libx264 encode in
 * this file carries it; acx_node.test.js fails if one does not.
 */
const X264_THREADS = 6;

/** #RRGGBB -> &H00BBGGRR, the colour order ASS styles use. */
function hexbgr(h) { return '&H00' + h.slice(5, 7) + h.slice(3, 5) + h.slice(1, 3); }

function assTime(t) {
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = t % 60;
  return `${h}:${String(m).padStart(2, '0')}:${s.toFixed(2).padStart(5, '0')}`;
}
function srtTime(t) {
  const h = Math.floor(t / 3600), m = Math.floor((t % 3600) / 60), s = Math.floor(t % 60);
  const ms = Math.round((t - Math.floor(t)) * 1000);
  return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(ms).padStart(3, '0')}`;
}
const r3 = (x) => Math.round(x * 1000) / 1000;

/**
 * Beat start and end from MEASURED line durations plus the pause rule.
 * Picture follows voice; nothing is time stretched.
 */
function planBeats(beats, pauses, durations) {
  let t = pauses.cold_open;
  const out = beats.map((b, i) => {
    const d = durations[b.id];
    if (!(d > 0)) throw new Error(`no measured duration for beat ${b.id}`);
    const nxt = beats[i + 1];
    let gap = nxt === undefined ? pauses.end_hold : (nxt.image !== b.image ? pauses.image_change : pauses.within_image);
    gap += (pauses.extra_after && pauses.extra_after[b.id]) || 0;
    const row = Object.assign({}, b, { start: r3(t), end: r3(t + d), line_dur: r3(d), gap: r3(gap) });
    t += d + gap;
    return row;
  });
  return { beats: out, total: r3(t) };
}

/** Consecutive beats on one image are one shot. */
function planShots(plannedBeats) {
  const shots = [];
  for (const b of plannedBeats) {
    const end = r3(b.end + b.gap);
    if (shots.length && shots[shots.length - 1].image === b.image) shots[shots.length - 1].end = end;
    else shots.push({ image: b.image, start: shots.length ? shots[shots.length - 1].end : 0, end });
  }
  return shots;
}

function norm(w) { return w.toLowerCase().replace(/’/g, "'").replace(/[^a-z0-9']+/g, ''); }

/**
 * The caption text is the sheet line, verbatim. Timings come from the word
 * timings aligned word by word: a word the model heard that is not in the sheet
 * is dropped, a sheet word the model rendered differently takes the timing of
 * what replaced it, and a sheet word the model missed takes the gap between its
 * neighbours. No word timings at all: every word shares the line's own span.
 */
function timedSheetWords(text, words, lineDur) {
  const sheet = text.split(/\s+/).filter(Boolean);
  if (!Array.isArray(words) || words.length === 0) {
    const per = lineDur / sheet.length;
    return sheet.map((w, i) => ({ w, start: r3(i * per), end: r3((i + 1) * per) }));
  }
  const a = sheet.map(norm), c = words.map(w => norm(w.text));
  const out = new Array(sheet.length).fill(null);
  // longest common subsequence alignment, the same shape as difflib's opcodes
  const n = a.length, m = c.length;
  const L = Array.from({ length: n + 1 }, () => new Int32Array(m + 1));
  for (let i = n - 1; i >= 0; i--) for (let j = m - 1; j >= 0; j--) {
    L[i][j] = a[i] === c[j] ? L[i + 1][j + 1] + 1 : Math.max(L[i + 1][j], L[i][j + 1]);
  }
  let i = 0, j = 0;
  const pending = [];   // sheet indexes between matches, timed by the model words they replaced
  let pendingWords = [];
  const flush = () => {
    if (pending.length && pendingWords.length) {
      const s0 = pendingWords[0].start, e0 = pendingWords[pendingWords.length - 1].end;
      pending.forEach((k, q) => { out[k] = [s0 + (e0 - s0) * q / pending.length, s0 + (e0 - s0) * (q + 1) / pending.length]; });
    }
    pending.length = 0; pendingWords = [];
  };
  while (i < n && j < m) {
    if (a[i] === c[j]) { flush(); out[i] = [words[j].start, words[j].end]; i++; j++; }
    else if (L[i + 1][j] >= L[i][j + 1]) { pending.push(i); i++; }
    else { pendingWords.push(words[j]); j++; }
  }
  while (i < n) pending.push(i++);
  while (j < m) pendingWords.push(words[j++]);
  flush();
  for (let k = 0; k < n; k++) {
    if (out[k] === null) {
      let prevEnd = 0; for (let q = k - 1; q >= 0; q--) if (out[q]) { prevEnd = out[q][1]; break; }
      let nextStart = prevEnd + 0.3; for (let q = k + 1; q < n; q++) if (out[q]) { nextStart = out[q][0]; break; }
      out[k] = [prevEnd, Math.max(nextStart, prevEnd + 0.1)];
    }
  }
  return sheet.map((w, k) => ({ w, start: r3(out[k][0]), end: r3(out[k][1]) }));
}

/**
 * Caption chunks: break at punctuation first, then at five words; a one or two
 * word phrase joins the phrase before it so a lone "Nothing wrong." does not
 * flash. Tail +0.30 s, floor 0.6 s, no overlaps.
 */
function captionChunks(plannedBeats, wordsByLine, tail = 0.30) {
  const chunks = [];
  for (const b of plannedBeats) {
    const words = timedSheetWords(b.text, wordsByLine && wordsByLine[b.id], b.line_dur);
    const phrases = []; let cur = [];
    for (const w of words) { cur.push(w); if ('.?!,;:'.includes(w.w.slice(-1))) { phrases.push(cur); cur = []; } }
    if (cur.length) phrases.push(cur);
    const merged = [];
    for (const ph of phrases) {
      if (merged.length && ph.length <= 2 && merged[merged.length - 1].length + ph.length <= 6) merged[merged.length - 1] = merged[merged.length - 1].concat(ph);
      else merged.push(ph);
    }
    for (const ph of merged) {
      let i = 0;
      while (i < ph.length) {
        let grp = ph.slice(i, i + 5);
        if (ph.length - (i + 5) === 1) grp = ph.slice(i, i + 6);
        const start = b.start + grp[0].start;
        const end = Math.max(b.start + grp[grp.length - 1].end + tail, start + 0.6);
        chunks.push({ start: r3(start), end: r3(end), text: grp.map(w => w.w).join(' '), verdict: !!b.verdict, beat: b.id });
        i += grp.length;
      }
    }
  }
  for (let k = 0; k + 1 < chunks.length; k++) if (chunks[k].end > chunks[k + 1].start) chunks[k].end = r3(chunks[k + 1].start - 0.02);
  return chunks;
}

function assText(chunks, style) {
  const { font, size, cyan, red, void: v, marginL, marginR, marginV } = style;
  const head = '[Script Info]\nScriptType: v4.00+\nPlayResX: 1080\nPlayResY: 1920\nWrapStyle: 0\nScaledBorderAndShadow: yes\n\n' +
    '[V4+ Styles]\nFormat: Name, Fontname, Fontsize, PrimaryColour, SecondaryColour, OutlineColour, BackColour, Bold, Italic, Underline, StrikeOut, ScaleX, ScaleY, Spacing, Angle, BorderStyle, Outline, Shadow, Alignment, MarginL, MarginR, MarginV, Encoding\n' +
    `Style: Cap,${font},${size},${hexbgr(cyan)},${hexbgr(cyan)},${hexbgr(v)},&H80000000,0,0,0,0,100,100,1,0,1,3,0,2,${marginL},${marginR},${marginV},1\n` +
    `Style: Verdict,${font},${size},${hexbgr(red)},${hexbgr(red)},${hexbgr(v)},&H80000000,0,0,0,0,100,100,1,0,1,3,0,2,${marginL},${marginR},${marginV},1\n\n` +
    '[Events]\nFormat: Layer, Start, End, Style, Name, MarginL, MarginR, MarginV, Effect, Text\n';
  return head + chunks.map(c => `Dialogue: 0,${assTime(c.start)},${assTime(c.end)},${c.verdict ? 'Verdict' : 'Cap'},,0,0,0,,${c.text}\n`).join('');
}
function srtText(chunks) {
  return chunks.map((c, n) => `${n + 1}\n${srtTime(c.start)} --> ${srtTime(c.end)}\n${c.text}\n\n`).join('');
}

// --- argv builders, every one pure ----------------------------------------

const ff = (...a) => ['ffmpeg', '-v', 'error', '-y', ...a];

function decodeArgv(src, out, treat) {
  if (!treat) return ff('-i', src, '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', out);
  const af = `asplit[a1][a2];[a2]adelay=${treat.delay_ms},volume=${treat.double_db}dB[a2d];[a1][a2d]amix=inputs=2:normalize=0,` +
             `lowshelf=g=${treat.low_shelf_db}:f=${treat.low_shelf_hz},highshelf=g=${treat.high_shelf_db}:f=${treat.high_shelf_hz}`;
  return ff('-i', src, '-filter_complex', af, '-ar', '48000', '-ac', '1', '-c:a', 'pcm_s16le', out);
}
function silenceArgv(sec, out) {
  return ff('-f', 'lavfi', '-i', 'anullsrc=r=48000:cl=mono', '-t', sec.toFixed(3), '-c:a', 'pcm_s16le', out);
}
function concatArgv(list, out, copy) {
  return ff('-f', 'concat', '-safe', '0', '-i', list, ...(copy ? ['-c', 'copy'] : ['-c:a', 'pcm_s16le']), out);
}
const LOUDNORM = (I, TP) => `loudnorm=I=${I}:TP=${TP}:LRA=11:print_format=json`;
function measureArgv(src, I, TP, pre) {
  return ['ffmpeg', '-nostats', '-hide_banner', '-i', src, '-af', (pre ? pre + ',' : '') + LOUDNORM(I, TP), '-f', 'null', '-'];
}
function gainLimitArgv(src, out, gainDb, limitLinear) {
  return ff('-i', src, '-af', `volume=${gainDb.toFixed(2)}dB,alimiter=limit=${limitLinear.toFixed(4)}:attack=5:release=60:level=false`, '-ar', '48000', '-c:a', 'pcm_s16le', out);
}
function shotArgv(img, frames, out, o) {
  const inc = o.push / Math.max(frames - 1, 1);
  const vf = `scale=${o.width * 2}:${o.height * 2}:flags=lanczos,zoompan=z='min(1+${inc}*on,${1 + o.push})':d=${frames}:x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)':s=${o.width}x${o.height}:fps=${o.fps},format=yuv420p`;
  return ff('-loop', '1', '-i', img, '-vf', vf, '-frames:v', String(frames), '-r', String(o.fps), '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-threads', String(X264_THREADS), out);
}
function drawtext(font, text, color, size, y, enable) {
  return `drawtext=fontfile='${font}':text='${text}':fontcolor=${color}:fontsize=${size}:x=(w-text_w)/2:y=${y}:enable='${enable}'`;
}
function overlayArgv(silent, ass, out, o) {
  // rounded to the millisecond so a float sum never prints as 61.809000000000005 inside a filter graph
  const openEnd = r3(o.cold_open + 1.5), discEnd = r3(o.cold_open + 2.5), endStart = r3(o.last_line_end + 0.6);
  const disc = (en) => o.disclosure_lines.map((t, i) => drawtext(o.font_regular, t, o.cyan, 30, 1100 + 40 * i, en));
  const draw = [
    drawtext(o.font_regular, o.brand, o.cyan, 44, 360, `between(t,0,${openEnd})`),
    drawtext(o.font_bold, o.node_label, o.cyan, 120, 420, `between(t,0,${openEnd})`),
    ...disc(`between(t,0,${discEnd})`),
    drawtext(o.font_regular, o.brand, o.cyan, 44, 560, `gte(t,${endStart})`),
    drawtext(o.font_bold, o.node_label, o.cyan, 120, 620, `gte(t,${endStart})`),
    drawtext(o.font_semibold, o.title, o.cyan, 56, 770, `gte(t,${endStart})`),
    ...disc(`gte(t,${endStart})`),
  ];
  const vf = draw.join(',') + `,ass='${ass}':fontsdir='${o.fonts_dir}'`;
  return ff('-i', silent, '-vf', vf, '-c:v', 'libx264', '-preset', 'medium', '-crf', '14', '-pix_fmt', 'yuv420p', '-threads', String(X264_THREADS), out);
}
function muxArgv(picture, mix, out, o) {
  return ff('-i', picture, '-i', mix, '-map', '0:v', '-map', '1:a', '-c:v', 'libx264', '-profile:v', 'high', '-preset', 'slow', '-crf', String(o.crf),
            '-pix_fmt', 'yuv420p', '-threads', String(X264_THREADS), '-r', String(o.fps), '-c:a', 'aac', '-b:a', '192k', '-ar', '48000', '-movflags', '+faststart', '-shortest', out);
}
function thumbnailArgv(img, out, o) {
  const vf = drawtext(o.font_regular, o.brand, o.cyan, 52, 520, '1') + ',' + drawtext(o.font_bold, o.node_label, o.cyan, 150, 590, '1');
  return ff('-i', img, '-vf', vf, '-frames:v', '1', out);
}
function frameArgv(master, t, out) { return ff('-ss', String(t), '-i', master, '-frames:v', '1', out); }
function contactArgv(frames, out) {
  const ins = frames.flatMap(f => ['-i', f]);
  const fc = frames.map((_, i) => `[${i}:v]scale=432:768[s${i}];`).join('') + frames.map((_, i) => `[s${i}]`).join('') +
    `xstack=inputs=${frames.length}:layout=${frames.map((_, i) => `${(i % 5) * 432}_${Math.floor(i / 5) * 768}`).join('|')}[v]`;
  return ff(...ins, '-filter_complex', fc, '-map', '[v]', out);
}
function lintArgv(master) {
  return ['ffmpeg', '-v', 'error', '-i', master, '-vf', 'fps=2,scale=540:960', '-f', 'rawvideo', '-pix_fmt', 'rgb24', '-'];
}

/** Count pixels within `tol` of an #RRGGBB colour in a 540x960 rgb24 frame, optionally inside a region. */
function countNear(buf, hex, tol, region) {
  const R = parseInt(hex.slice(1, 3), 16), G = parseInt(hex.slice(3, 5), 16), B = parseInt(hex.slice(5, 7), 16);
  const W = 540, H = 960;
  const x0 = region ? region.x0 : 0, y0 = region ? region.y0 : 0;
  let n = 0;
  for (let y = y0; y < H; y++) {
    let k = (y * W + x0) * 3;
    for (let x = x0; x < W; x++, k += 3) {
      if (Math.abs(buf[k] - R) <= tol && Math.abs(buf[k + 1] - G) <= tol && Math.abs(buf[k + 2] - B) <= tol) n++;
    }
  }
  return n;
}

function sha256(p) { return crypto.createHash('sha256').update(fs.readFileSync(p)).digest('hex'); }

/**
 * The full name (name id 4) out of a TrueType or OpenType font's name table,
 * read from the bytes rather than trusted from the filename. drawtext and
 * libass both fall back to a generic face when a file named .ttf is not a
 * font, exit 0 and say nothing, so this is the only place a wrong font can be
 * refused (critic finding F1, 2026-10-28). Throws with a reason on anything
 * that is not an sfnt with a readable name table.
 */
function fontFullName(file) {
  const d = fs.readFileSync(file);
  if (d.length < 12) throw new Error('shorter than an sfnt header');
  const tag = d.readUInt32BE(0);
  if (tag !== 0x00010000 && tag !== 0x74727565 && tag !== 0x4F54544F) throw new Error('not an sfnt (TrueType or OpenType) file');
  const n = d.readUInt16BE(4);
  for (let i = 0; i < n; i++) {
    const e = 12 + 16 * i;
    if (e + 16 > d.length) break;
    if (d.toString('latin1', e, e + 4) !== 'name') continue;
    const off = d.readUInt32BE(e + 8), len = d.readUInt32BE(e + 12);
    if (off + 6 > d.length || off + len > d.length) throw new Error('name table runs past the end of the file');
    const count = d.readUInt16BE(off + 2), strOff = d.readUInt16BE(off + 4);
    let fallback = null;
    for (let j = 0; j < count; j++) {
      const r = off + 6 + 12 * j;
      if (r + 12 > off + len) break;
      const pid = d.readUInt16BE(r), nid = d.readUInt16BE(r + 6), l = d.readUInt16BE(r + 8), o = d.readUInt16BE(r + 10);
      if (nid !== 4) continue;
      const a = off + strOff + o;
      if (a + l > d.length) continue;
      // platform 3 (Windows) strings are UTF-16BE; platform 1 (Macintosh) strings are single byte
      const name = pid === 3 ? Buffer.from(d.subarray(a, a + l)).swap16().toString('utf16le') : d.toString('latin1', a, a + l);
      if (pid === 3) return name;
      if (fallback === null) fallback = name;
    }
    if (fallback !== null) return fallback;
    throw new Error('name table carries no full name (id 4)');
  }
  throw new Error('no name table');
}

// --- the jobs --------------------------------------------------------------

function jobs(H) {
  const { BadJob, safePath, existingPath, num, oneOf, getRoot, ensureDir } = H;

  function hexColor(v, label, dflt) {
    const s = v === undefined ? dflt : String(v);
    if (!/^#[0-9A-Fa-f]{6}$/.test(s)) throw new BadJob(`${label}: must be #RRGGBB`);
    return s.toUpperCase();
  }
  function safeText(v, label, dflt) {
    const s = v === undefined ? dflt : String(v);
    if (!SAFE_TEXT.test(s)) throw new BadJob(`${label}: carries a character the drawtext filter cannot take verbatim; use letters, digits, spaces and , . ; ! ? -`);
    if (s.length > 80) throw new BadJob(`${label}: over 80 characters`);
    return s;
  }

  return {
    word_timings: {
      build(p) {
        if (!Array.isArray(p.audio) || p.audio.length < 1) throw new BadJob('audio: must be an array of line files');
        if (p.audio.length > 200) throw new BadJob('audio: too many (max 200)');
        const audio = p.audio.map((a, i) => existingPath(a, `audio[${i}]`));
        const out = ensureDir(safePath(p.output, 'output'));
        if (!/\.json$/.test(out)) throw new BadJob('output: must end .json');
        const model = oneOf(p.model ?? 'base.en', 'model', ['tiny.en', 'base.en', 'small.en']);
        const python = process.env.WHISPER_PYTHON || '';
        const script = path.join(__dirname, 'words.py');
        const argv = [script, '--model', model, '--output', out, '--', ...audio];
        let child = null, aborted = false;
        return {
          native: () => new Promise((resolve, reject) => {
            // Refused at run time, not at submit: the job table and the health
            // route must not depend on which box this runs on.
            if (!python) return reject(new Error('WHISPER_PYTHON is not set on this worker: point it at a python with faster-whisper installed (DEPLOY.md, ACX Node section)'));
            child = execFile(python, argv, { maxBuffer: 32 * 1024 * 1024, windowsHide: true }, (err, stdout, stderr) => {
              child = null;
              if (aborted) return reject(new Error('aborted'));
              if (err) return reject(new Error(String(stderr || err.message).trim().split('\n').slice(-12).join('\n')));
              let parsed;
              try { parsed = JSON.parse(fs.readFileSync(out, 'utf8')); } catch (e) { return reject(new Error(`words.py ran but wrote no readable JSON: ${e.message}`)); }
              resolve({ output: out, lines: Object.keys(parsed).length, words: Object.values(parsed).reduce((n, l) => n + l.words.length, 0), model, stt: String(stdout).trim().split('\n').slice(-3) });
            });
          }),
          abort() { aborted = true; if (child) try { child.kill('SIGKILL'); } catch (_) { /* gone */ } },
          plan: { python: python || null, argv },
        };
      },
    },

    acx_node_assemble: {
      build(p) {
        const outDir = safePath(p.output_dir, 'output_dir');
        if (!SAFE_PATH.test(outDir)) throw new BadJob('output_dir: the resolved path carries a character the concat list and the filter graph cannot take verbatim; rename it');
        const o = {
          // node_id names files, never a drawtext string, so it takes an identifier
          node_id: (() => { const v = p.node_id === undefined ? 'ACX_NODE' : String(p.node_id); if (!/^[A-Za-z0-9_-]{1,40}$/.test(v)) throw new BadJob('node_id: letters, digits, underscore and hyphen only, up to 40'); return v; })(),
          node_label: safeText(p.node_label, 'node_label', 'NODE 01'),
          brand: safeText(p.brand, 'brand', 'ASCENSION CAUDEX'),
          title: safeText(p.title, 'title', 'THE ORCHESTRATOR'),
          width: num(p.width ?? 1080, 'width', { min: 16, max: 8192, int: true }),
          height: num(p.height ?? 1920, 'height', { min: 16, max: 8192, int: true }),
          fps: num(p.fps ?? 30, 'fps', { min: 1, max: 120, int: true }),
          crf: num(p.crf ?? 18, 'crf', { min: 0, max: 51, int: true }),
          push: num(p.push ?? 0.05, 'push', { min: 0, max: 0.5 }),
          target_lufs: num(p.target_lufs ?? -14, 'target_lufs', { min: -30, max: -6 }),
          true_peak: num(p.true_peak ?? -1, 'true_peak', { min: -6, max: 0 }),
          window: [num((p.window || [])[0] ?? 60, 'window[0]', { min: 1, max: 3600 }), num((p.window || [])[1] ?? 90, 'window[1]', { min: 1, max: 3600 })],
          cyan: hexColor(p.signal_cyan, 'signal_cyan', '#36D1D8'),
          red: hexColor(p.critic_red, 'critic_red', '#D9626A'),
          void: hexColor(p.void, 'void', '#04090F'),
        };
        if (o.width !== 1080 || o.height !== 1920) throw new BadJob('width and height: this job renders the 1080x1920 Node canvas only; the 16:9 long form is a second render (R19) that does not exist yet');
        // The disclosure is canon and verbatim; it is only ever wrapped, never reworded.
        const disclosure = p.disclosure === undefined ? DISCLOSURE : String(p.disclosure);
        if (disclosure !== DISCLOSURE) throw new BadJob('disclosure: must be the canon line verbatim, or omitted');
        o.disclosure_lines = DISCLOSURE_LINES;
        if (DISCLOSURE_LINES.join(' ') !== DISCLOSURE) throw new Error('disclosure wrap drifted from the canon line');

        const fontsDir = existingPath(p.fonts_dir, 'fonts_dir');
        if (!SAFE_PATH.test(fontsDir)) throw new BadJob('fonts_dir: carries a character the filter graph cannot take verbatim');
        o.fonts = {};
        for (const [f, want] of Object.entries(FONT_FACES)) {
          const file = path.join(fontsDir, f);
          if (!fs.existsSync(file)) throw new BadJob(`fonts_dir: ${f} is missing; the three Chakra Petch faces must sit there`);
          let got;
          try { got = fontFullName(file); } catch (e) { throw new BadJob(`fonts_dir: ${f} is not a usable font (${e.message}); drawtext and libass would fall back to another face without saying so`); }
          if (got !== want) throw new BadJob(`fonts_dir: ${f} names itself ${JSON.stringify(got)}, expected ${JSON.stringify(want)}`);
          o.fonts[f] = got;
        }
        o.fonts_dir = fontsDir;
        o.font_regular = path.join(fontsDir, 'ChakraPetch--400.ttf');
        o.font_semibold = path.join(fontsDir, 'ChakraPetch--600.ttf');
        o.font_bold = path.join(fontsDir, 'ChakraPetch--700.ttf');

        if (!p.images || typeof p.images !== 'object') throw new BadJob('images: must be an object of image key to still path');
        const images = {};
        for (const [k, v] of Object.entries(p.images)) {
          if (!/^[A-Za-z0-9_]{1,16}$/.test(k)) throw new BadJob(`images: key ${JSON.stringify(k)} is not a short identifier`);
          images[k] = existingPath(v, `images.${k}`);
        }
        if (!Array.isArray(p.beats) || p.beats.length < 1) throw new BadJob('beats: must be a non-empty array');
        if (p.beats.length > 200) throw new BadJob('beats: too many (max 200)');
        const ids = new Set();
        const beats = p.beats.map((b, k) => {
          if (!b || typeof b !== 'object') throw new BadJob(`beats[${k}]: not an object`);
          const id = String(b.id ?? '');
          if (!/^[A-Za-z0-9_]{1,16}$/.test(id)) throw new BadJob(`beats[${k}].id: must be a short identifier`);
          if (ids.has(id)) throw new BadJob(`beats[${k}].id: ${id} repeats`);
          ids.add(id);
          if (typeof b.text !== 'string' || !b.text.trim()) throw new BadJob(`beats[${k}].text: the sheet line is required`);
          if (b.text.length > 400) throw new BadJob(`beats[${k}].text: over 400 characters`);
          if (!SAFE_ASS.test(b.text)) throw new BadJob(`beats[${k}].text: carries a brace, backslash or line break the caption file cannot take verbatim`);
          if (!Object.prototype.hasOwnProperty.call(images, String(b.image))) throw new BadJob(`beats[${k}].image: ${JSON.stringify(b.image)} is not in images`);
          if (b.verdict !== undefined && typeof b.verdict !== 'boolean') throw new BadJob(`beats[${k}].verdict: must be a boolean`);
          return { id, image: String(b.image), text: b.text.trim(), verdict: !!b.verdict, line: existingPath(b.line, `beats[${k}].line`) };
        });
        const pz = p.pauses || {};
        const pauses = {
          cold_open: num(pz.cold_open ?? 2.5, 'pauses.cold_open', { min: 0, max: 30 }),
          within_image: num(pz.within_image ?? 0.9, 'pauses.within_image', { min: 0, max: 30 }),
          image_change: num(pz.image_change ?? 1.8, 'pauses.image_change', { min: 0, max: 30 }),
          end_hold: num(pz.end_hold ?? 5.0, 'pauses.end_hold', { min: 0, max: 60 }),
          extra_after: {},
        };
        if (pz.extra_after !== undefined) {
          if (!pz.extra_after || typeof pz.extra_after !== 'object') throw new BadJob('pauses.extra_after: must be an object of beat id to seconds');
          for (const [k, v] of Object.entries(pz.extra_after)) {
            if (!ids.has(k)) throw new BadJob(`pauses.extra_after.${k}: no such beat`);
            pauses.extra_after[k] = num(v, `pauses.extra_after.${k}`, { min: 0, max: 30 });
          }
        }
        let treat = null;
        if (p.copy_treatment !== undefined && p.copy_treatment !== null) {
          const c = p.copy_treatment;
          if (!c || typeof c !== 'object' || !Array.isArray(c.lines)) throw new BadJob('copy_treatment: must be {lines: [beat ids], ...}');
          for (const l of c.lines) if (!ids.has(String(l))) throw new BadJob(`copy_treatment.lines: no such beat ${JSON.stringify(l)}`);
          treat = {
            lines: new Set(c.lines.map(String)),
            delay_ms: num(c.delay_ms ?? 14, 'copy_treatment.delay_ms', { min: 0, max: 200, int: true }),
            double_db: num(c.double_db ?? -7, 'copy_treatment.double_db', { min: -40, max: 0 }),
            low_shelf_db: num(c.low_shelf_db ?? 2, 'copy_treatment.low_shelf_db', { min: -12, max: 12 }),
            low_shelf_hz: num(c.low_shelf_hz ?? 180, 'copy_treatment.low_shelf_hz', { min: 20, max: 2000, int: true }),
            high_shelf_db: num(c.high_shelf_db ?? -2.5, 'copy_treatment.high_shelf_db', { min: -12, max: 12 }),
            high_shelf_hz: num(c.high_shelf_hz ?? 6000, 'copy_treatment.high_shelf_hz', { min: 1000, max: 20000, int: true }),
          };
        }
        let wordsByLine = null;
        if (p.words !== undefined && p.words_path !== undefined) throw new BadJob('words and words_path: send one, not both');
        const wordsPath = p.words_path === undefined ? null : existingPath(p.words_path, 'words_path');
        if (p.words !== undefined) {
          if (!p.words || typeof p.words !== 'object') throw new BadJob('words: must be an object of beat id to [{text, start, end}]');
          wordsByLine = p.words;
        }
        const checkWords = (W) => {
          // Either every beat has timings or none does: a beat silently spread evenly
          // beside beats timed from the audio would be recorded as timed (critic F2).
          for (const b of beats) {
            if (!Array.isArray(W[b.id]) || W[b.id].length === 0) throw new BadJob(`words.${b.id}: no word timings for this beat; send timings for every beat or for none`);
          }
          for (const [k, arr] of Object.entries(W)) {
            if (!Array.isArray(arr)) throw new BadJob(`words.${k}: not an array`);
            arr.forEach((w, i) => {
              if (!w || typeof w.text !== 'string') throw new BadJob(`words.${k}[${i}].text: not a string`);
              num(w.start, `words.${k}[${i}].start`, { min: 0, max: 86400 }); num(w.end, `words.${k}[${i}].end`, { min: 0, max: 86400 });
            });
          }
        };
        if (wordsByLine) checkWords(wordsByLine);
        const style = { font: 'Chakra Petch SemiBold', size: 66, cyan: o.cyan, red: o.red, void: o.void, marginL: 80, marginR: 200, marginV: 560 };
        const limitLinear = Math.pow(10, (o.true_peak - 0.5) / 20);
        const P = (rel) => path.join(outDir, rel);
        const segA = P('audio_segments'), segV = P('video_segments'), framesDir = P('frames');

        let child = null, aborted = false;
        const run = (argv, label, opts) => new Promise((resolve, reject) => {
          if (aborted) return reject(new Error('aborted'));
          const [bin, ...args] = argv;
          child = execFile(bin, args, Object.assign({ maxBuffer: 64 * 1024 * 1024, windowsHide: true }, opts || {}), (err, stdout, stderr) => {
            child = null;
            if (aborted) return reject(new Error('aborted'));
            if (err) return reject(new Error(`${label}: ` + String(stderr || err.message).trim().split('\n').slice(-12).join('\n')));
            resolve({ stdout: String(stdout), stderr: String(stderr) });
          });
        });
        const probeDur = async (f) => {
          const r = await run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration', '-of', 'csv=p=0', f], 'ffprobe');
          const d = Number(r.stdout.trim()); if (!(d > 0)) throw new Error(`ffprobe: no duration for ${f}`); return d;
        };
        const measure = async (f, pre) => {
          const r = await run(measureArgv(f, o.target_lufs, o.true_peak, pre), 'loudnorm measure');
          const m = /\{[\s\S]*\}/.exec(r.stderr); if (!m) throw new Error('loudnorm printed no JSON');
          return JSON.parse(m[0]);
        };
        const lint = (master, chunks) => new Promise((resolve, reject) => {
          if (aborted) return reject(new Error('aborted'));
          const [bin, ...args] = lintArgv(master);
          const ch = spawn(bin, args, { windowsHide: true });
          child = ch;
          const FRAME = 540 * 960 * 3;
          const windows = chunks.filter(c => c.verdict).map(c => [c.start - 0.1, c.end + 0.1]);
          let buf = Buffer.alloc(0), n = 0, redFrames = 0; const breaches = []; let art = 0; let errText = '';
          ch.stdout.on('data', (d) => {
            buf = Buffer.concat([buf, d]);
            while (buf.length >= FRAME) {
              const fr = buf.subarray(0, FRAME); buf = buf.subarray(FRAME);
              const t = n / 2; n++;
              const red = countNear(fr, o.red, 40);
              if (red > 20) { redFrames++; if (!windows.some(([lo, hi]) => lo <= t && t <= hi)) breaches.push({ t, red_pixels: red }); }
              const right = countNear(fr, o.cyan, 28, { x0: Math.floor(540 * 0.85), y0: 0 });
              const bottom = countNear(fr, o.cyan, 28, { x0: 0, y0: Math.floor(960 * 0.80) });
              if (right > 150 || bottom > 150) art++;
            }
          });
          ch.stderr.on('data', (d) => { errText += d; });
          ch.on('error', reject);
          ch.on('close', (code) => {
            child = null;
            if (aborted) return reject(new Error('aborted'));
            if (code !== 0) return reject(new Error(`lint: ffmpeg exited ${code}: ${errText.trim().split('\n').slice(-3).join('\n')}`));
            resolve({ frames_checked: n, frames_with_red: redFrames, red_breaches: breaches, frames_with_dense_cyan_in_platform_zone: art, verdict_windows: windows });
          });
        });

        const native = async () => {
          const T = {}; const tick = async (label, fn) => { const t0 = Date.now(); const r = await fn(); T[label] = Number(((Date.now() - t0) / 1000).toFixed(2)); return r; };
          for (const d of [segA, segV, framesDir]) fs.mkdirSync(d, { recursive: true });
          let W = wordsByLine;
          if (wordsPath) {
            const raw = JSON.parse(fs.readFileSync(wordsPath, 'utf8'));
            W = {};
            for (const b of beats) {
              const key = path.basename(b.line).replace(/\.[^.]+$/, '');
              const entry = raw[b.id] || raw[key];
              if (entry) W[b.id] = Array.isArray(entry) ? entry : (entry.words || []).map(w => ({ text: w.text !== undefined ? w.text : w.w, start: w.start, end: w.end }));
            }
            checkWords(W);
          }
          // 1. decode the lines, Copy treatment where the manifest says so, and measure the DECODED files
          const durations = {};
          for (const b of beats) {
            const out = path.join(segA, `${b.id}.wav`);
            const tr = treat && treat.lines.has(b.id) ? treat : null;
            await tick(`decode_${b.id}`, () => run(decodeArgv(b.line, out, tr), `decode ${b.id}`));
            durations[b.id] = await probeDur(out);
          }
          const plan = planBeats(beats, pauses, durations);
          const planned = plan.beats;
          // 2. the timeline: silences between, concat, gain to target under a limiter
          const list = [];
          const sil = async (sec, name) => { const f = path.join(segA, name); await run(silenceArgv(sec, f), 'silence'); list.push(f); };
          await sil(pauses.cold_open, 's_open.wav');
          for (const b of planned) { list.push(path.join(segA, `${b.id}.wav`)); await sil(b.gap, `s_${b.id}.wav`); }
          for (const f of list) if (!SAFE_PATH.test(f)) throw new Error(`concat list cannot take ${f}`);
          fs.writeFileSync(path.join(segA, 'concat.txt'), list.map(f => `file '${f}'\n`).join(''));
          const raw = P('narration_timeline_raw.wav'), mix = P('narration_mix.wav');
          await tick('concat_audio', () => run(concatArgv(path.join(segA, 'concat.txt'), raw, false), 'concat audio'));
          const m1 = await measure(raw);
          let gain = o.target_lufs - Number(m1.input_i); let m3 = null;
          for (let attempt = 0; attempt < 4; attempt++) {
            await tick(`gain_limit_${attempt}`, () => run(gainLimitArgv(raw, mix, gain, limitLinear), 'gain and limit'));
            m3 = await measure(mix);
            const err = o.target_lufs - Number(m3.input_i);
            if (Math.abs(err) <= 0.2) break;
            gain += err;
          }
          const mu = await measure(raw, `volume=${gain.toFixed(2)}dB`);
          const audio = {
            raw_measured: m1, applied_gain_db: Number(gain.toFixed(2)),
            limiter: `alimiter limit=${(o.true_peak - 0.5).toFixed(1)} dBFS attack 5 ms release 60 ms, 0.5 dB headroom for the AAC encode`,
            same_gain_no_limiter: { integrated_lufs: mu.input_i, true_peak_dbtp: mu.input_tp },
            limiter_removed_lu: Number((Number(mu.input_i) - Number(m3.input_i)).toFixed(2)),
            limiter_peak_reduction_db: Number((Number(mu.input_tp) - Number(m3.input_tp)).toFixed(2)),
            mix_remeasured: { integrated_lufs: m3.input_i, true_peak_dbtp: m3.input_tp, lra: m3.input_lra },
            mix_duration_s: r3(await probeDur(mix)), planned_total_s: plan.total,
          };
          // 3. captions from the sheet text and the word timings
          const chunks = captionChunks(planned, W);
          const assPath = P('captions.ass'), srtPath = P('captions.srt');
          fs.writeFileSync(assPath, assText(chunks, style)); fs.writeFileSync(srtPath, srtText(chunks));
          fs.writeFileSync(P('caption_chunks.json'), JSON.stringify(chunks, null, 1));
          // 4. one slow push shot per image run, hard cuts, then the overlays
          const shots = planShots(planned);
          const vlist = [];
          for (let n = 0; n < shots.length; n++) {
            const s = shots[n];
            s.frames = Math.round((s.end - s.start) * o.fps);
            s.file = path.join(segV, `shot${n}_${s.image}.mp4`);
            await tick(`shot${n}`, () => run(shotArgv(images[s.image], s.frames, s.file, o), `shot ${n}`));
            vlist.push(s.file);
          }
          fs.writeFileSync(path.join(segV, 'concat.txt'), vlist.map(f => `file '${f}'\n`).join(''));
          const silent = P('picture_silent.mp4'), picture = P('picture_overlays.mp4');
          await tick('concat_video', () => run(concatArgv(path.join(segV, 'concat.txt'), silent, true), 'concat video'));
          const ov = Object.assign({ cold_open: pauses.cold_open, last_line_end: planned[planned.length - 1].end }, o);
          await tick('overlays', () => run(overlayArgv(silent, assPath, picture, ov), 'overlays'));
          // 5. mux, thumbnail, contact sheet, lint, measure
          const master = P(`${o.node_id}_master.mp4`);
          await tick('mux_master', () => run(muxArgv(picture, mix, master, o), 'mux'));
          const thumb = P('thumbnail.png');
          const firstImage = images[Object.keys(images).includes('R4') ? 'R4' : beats[0].image];
          await tick('thumbnail', () => run(thumbnailArgv(firstImage, thumb, o), 'thumbnail'));
          const total = await probeDur(master);
          const times = Array.from({ length: 10 }, (_, i) => r3(1 + (total - 2) * i / 9));
          const framePaths = [];
          for (const t of times) { const f = path.join(framesDir, `f_${t}.png`); await run(frameArgv(master, t, f), 'frame'); framePaths.push(f); }
          await tick('contact_sheet', () => run(contactArgv(framePaths, P('contact_sheet.png')), 'contact sheet'));
          const lintRep = await tick('lint', () => lint(master, chunks));
          const ln = await measure(master);
          const probe = JSON.parse((await run(['ffprobe', '-v', 'error', '-show_entries', 'format=duration,size,bit_rate:stream=codec_name,profile,width,height,r_frame_rate,pix_fmt,sample_rate,channels,bit_rate', '-of', 'json', master], 'ffprobe')).stdout);
          const vdur = Number((await run(['ffprobe', '-v', 'error', '-select_streams', 'v:0', '-show_entries', 'stream=duration', '-of', 'csv=p=0', master], 'ffprobe')).stdout);
          const adur = Number((await run(['ffprobe', '-v', 'error', '-select_streams', 'a:0', '-show_entries', 'stream=duration', '-of', 'csv=p=0', master], 'ffprobe')).stdout);
          const ffv = (await run(['ffmpeg', '-version'], 'ffmpeg -version')).stdout.split('\n')[0];
          const runtime = Number(probe.format.duration);
          const hashes = {};
          for (const f of [master, srtPath, assPath, thumb, P('contact_sheet.png'), ...framePaths, mix, raw, silent, picture, ...vlist, ...list, path.join(segA, 'concat.txt'), path.join(segV, 'concat.txt'), P('caption_chunks.json'), ...(wordsPath ? [wordsPath] : []), ...Object.values(images), ...beats.map(b => b.line), o.font_regular, o.font_semibold, o.font_bold]) {
            hashes[path.relative(getRoot(), f)] = sha256(f);
          }
          const record = {
            node_id: o.node_id, built_at_utc: new Date().toISOString(), built_by: 'render worker acx_node_assemble',
            voice_slot: p.voice_slot === undefined ? 'unstated by the caller' : String(p.voice_slot).slice(0, 200),
            fonts: o.fonts,
            labels: { mapping: 'as sent by the caller', verdict_beats: planned.filter(b => b.verdict).map(b => b.id), copy_treatment: treat ? [...treat.lines] : [], pauses },
            measured: {
              runtime_s_from_file: r3(runtime), video_stream_s: r3(vdur), audio_stream_s: r3(adur), av_length_delta_frames: Number(((vdur - adur) * o.fps).toFixed(2)),
              integrated_lufs: ln.input_i, true_peak_dbtp: ln.input_tp, lra: ln.input_lra, streams: probe.streams, bytes: Number(probe.format.size), bit_rate: Number(probe.format.bit_rate),
            },
            runtime_window_ok: runtime >= o.window[0] && runtime <= o.window[1], window: o.window,
            lint: lintRep, audio, beats: planned, shots: shots.map(s => ({ image: s.image, start: s.start, end: s.end, frames: s.frames, file: path.relative(getRoot(), s.file) })),
            captions: { chunks: chunks.length, srt: path.relative(getRoot(), srtPath), ass: path.relative(getRoot(), assPath), words: wordsPath ? `word timings for every beat from words_path ${path.relative(getRoot(), wordsPath)}` : (W ? 'word timings for every beat sent inline by the caller' : 'no word timings: each line shared evenly over its measured span') },
            stage_timings_s: T, tool_versions: { ffmpeg: ffv, node: process.version },
            outputs: { master: path.relative(getRoot(), master), thumbnail: path.relative(getRoot(), thumb), contact_sheet: path.relative(getRoot(), P('contact_sheet.png')), srt: path.relative(getRoot(), srtPath) },
            sha256: hashes,
          };
          fs.writeFileSync(P('build.json'), JSON.stringify(record, null, 1));
          if (lintRep.red_breaches.length) throw new Error(`canon lint failed: Critic Red outside a verdict beat at ${lintRep.red_breaches.map(b => b.t + 's').join(', ')} (build.json written)`);
          return record;
        };
        return {
          native,
          abort() { aborted = true; if (child) try { child.kill('SIGKILL'); } catch (_) { /* gone */ } },
          // pure views for the tests and for a caller that wants to see the plan before it runs
          plan: { beats, images, pauses, treat: treat ? Object.assign({}, treat, { lines: [...treat.lines] }) : null, style, options: o, limit_linear: limitLinear, output_dir: outDir },
        };
      },
    },
  };
}

module.exports = {
  jobs, planBeats, planShots, timedSheetWords, captionChunks, assText, srtText, hexbgr, assTime, srtTime,
  decodeArgv, silenceArgv, concatArgv, measureArgv, gainLimitArgv, shotArgv, overlayArgv, muxArgv, thumbnailArgv, frameArgv, contactArgv, lintArgv, countNear,
  fontFullName, FONT_FACES, DISCLOSURE, DISCLOSURE_LINES, SAFE_PATH, SAFE_TEXT, SAFE_ASS, X264_THREADS,
};
