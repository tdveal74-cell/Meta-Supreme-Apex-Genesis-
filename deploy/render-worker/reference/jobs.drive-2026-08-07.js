'use strict';
/**
 * TSWS render worker — job definitions.
 *
 * THE ONE RULE
 * Every job builds an **argv array**. Nothing here ever produces a shell string,
 * and the server never spawns a shell. That is the whole security model.
 *
 * The n8n Code nodes currently build strings like
 *     mkdir -p '/data/out' && ffmpeg -i '/data/in.wav' ... && echo OK
 * If the worker accepted those verbatim it would be a remote-code-execution
 * endpoint sitting on the public internet behind one bearer token. A single
 * quote in an episode title would be enough. So instead: the caller sends
 * validated PARAMETERS, and the worker decides what ffmpeg gets run.
 *
 * The mkdir/echo parts of those old strings are handled in Node (fs.mkdirSync)
 * rather than shelled out, which is also just better — a failed mkdir throws
 * instead of being swallowed by &&.
 */
const path = require('path');
const fs = require('fs');

// --- validation ------------------------------------------------------------

class BadJob extends Error {
  constructor(msg) { super(msg); this.statusCode = 400; }
}

let WORK_ROOT = process.env.WORK_ROOT || '/data/tsws';

function setRoot(r) { WORK_ROOT = path.resolve(r); }
function getRoot()  { return WORK_ROOT; }

/**
 * Confine a path to WORK_ROOT.
 *
 * Rejects absolute escapes, ../ traversal, and NUL bytes. Note it resolves
 * BEFORE comparing — checking for the literal string '..' is not enough,
 * because 'a/b/../../../etc/passwd' contains no leading '..' at all.
 */
function safePath(p, label) {
  if (typeof p !== 'string' || !p.length) throw new BadJob(`${label}: missing`);
  if (p.includes('\0')) throw new BadJob(`${label}: NUL byte`);
  const abs = path.resolve(WORK_ROOT, p);
  const root = WORK_ROOT.endsWith(path.sep) ? WORK_ROOT : WORK_ROOT + path.sep;
  if (abs !== WORK_ROOT && !abs.startsWith(root)) {
    throw new BadJob(`${label}: path escapes the work root`);
  }
  return abs;
}

function existingPath(p, label) {
  const abs = safePath(p, label);
  if (!fs.existsSync(abs)) throw new BadJob(`${label}: no such file (${p})`);
  return abs;
}

function num(v, label, { min = -Infinity, max = Infinity, int = false } = {}) {
  const n = Number(v);
  if (!Number.isFinite(n)) throw new BadJob(`${label}: not a number`);
  if (int && !Number.isInteger(n)) throw new BadJob(`${label}: must be an integer`);
  if (n < min || n > max) throw new BadJob(`${label}: out of range [${min}, ${max}]`);
  return n;
}

function oneOf(v, label, allowed) {
  if (!allowed.includes(v)) {
    throw new BadJob(`${label}: must be one of ${allowed.join(', ')} (got ${JSON.stringify(v)})`);
  }
  return v;
}

function ensureDir(p) { fs.mkdirSync(path.dirname(p), { recursive: true }); return p; }

// x265 presets. 'placebo' is deliberately excluded — measured at 4K it is hours
// per minute of footage for no visible gain, and someone will eventually try it.
const PRESETS = ['ultrafast','superfast','veryfast','faster','fast','medium','slow','slower','veryslow'];

// --- network helpers (for the Topaz transfers) -----------------------------

const https = require('https');

/**
 * HTTPS only. Plain HTTP would put presigned URLs and 4K masters on the wire in
 * the clear, and this worker exists partly to stop doing that.
 */
function httpsUrl(u, label) {
  if (typeof u !== 'string' || !u) throw new BadJob(`${label}: missing`);
  let parsed;
  try { parsed = new URL(u); } catch { throw new BadJob(`${label}: not a URL`); }
  if (parsed.protocol !== 'https:') throw new BadJob(`${label}: must be https`);
  return u;
}

function downloadTo(url, dest, maxBytes, redirects = 0) {
  return new Promise((resolve, reject) => {
    if (redirects > 5) return reject(new Error('too many redirects'));
    https.get(url, res => {
      if ([301,302,303,307,308].includes(res.statusCode) && res.headers.location) {
        res.resume();
        return resolve(downloadTo(httpsUrl(new URL(res.headers.location, url).href, 'redirect'),
                                  dest, maxBytes, redirects + 1));
      }
      if (res.statusCode !== 200) {
        res.resume();
        return reject(new Error(`GET returned ${res.statusCode}`));
      }
      let n = 0;
      const out = fs.createWriteStream(dest);
      res.on('data', c => {
        n += c.length;
        if (n > maxBytes) { res.destroy(); out.destroy();
          try { fs.unlinkSync(dest); } catch {}
          reject(new Error(`exceeded max_mb`)); }
      });
      res.pipe(out);
      out.on('finish', () => out.close(() => resolve(n)));
      out.on('error', reject);
    }).on('error', reject);
  });
}

function putRange(url, file, start, end) {
  return new Promise((resolve, reject) => {
    const len = end - start + 1;
    const req = https.request(url, {
      method: 'PUT',
      headers: { 'content-length': len },
    }, res => {
      let body = '';
      res.on('data', d => { if (body.length < 8192) body += d; });
      res.on('end', () => {
        if (res.statusCode < 200 || res.statusCode >= 300) {
          return reject(new Error(`PUT returned ${res.statusCode}: ${body.slice(0, 200)}`));
        }
        resolve(String(res.headers.etag || '').replace(/"/g, ''));
      });
    });
    req.on('error', reject);
    fs.createReadStream(file, { start, end }).pipe(req);
  });
}

const FF = 'ffmpeg';
const FP = 'ffprobe';
const QUIET = ['-hide_banner', '-loglevel', 'error'];
const MEASURE = ['-hide_banner', '-nostats'];

// --- jobs ------------------------------------------------------------------
// Each: { build(params) -> {bin, argv, capture?, parse?} }
//   capture: 'stdout' | 'stderr' | 'both'   (default 'both')
//   parse:   (stdout, stderr) -> result object

const JOBS = {

  /** ffprobe duration. Replaces `Probe Duration` and `Probe Source Layer`. */
  probe: {
    build(p) {
      const f = existingPath(p.path, 'path');
      return {
        bin: FP,
        argv: ['-v','error','-show_entries','format=duration:stream=width,height,r_frame_rate',
               '-of','json', f],
        parse: (out) => {
          const j = JSON.parse(out || '{}');
          const st = (j.streams || [])[0] || {};
          const [n, d] = String(st.r_frame_rate || '0/1').split('/');
          return {
            duration: Number(j.format?.duration ?? 0),
            width: st.width ?? null, height: st.height ?? null,
            fps: Number(d) ? Number(n) / Number(d) : null,
          };
        },
      };
    },
  },

  /**
   * loudnorm pass 1 — measure only.
   * Two-pass is deliberate in the pipeline and must stay that way: single-pass
   * loudnorm is a live guess that drifts on the first few seconds of programme.
   */
  loudnorm_measure: {
    build(p) {
      const f = existingPath(p.input, 'input');
      const I   = num(p.target_i  ?? -16, 'target_i',  { min: -40, max: -5 });
      const TP  = num(p.target_tp ?? -1.5,'target_tp', { min: -9,  max: 0 });
      const LRA = num(p.lra       ?? 11,  'lra',       { min: 1,   max: 50 });
      return {
        bin: FF,
        argv: [...MEASURE, '-i', f, '-af',
               `loudnorm=I=${I}:TP=${TP}:LRA=${LRA}:print_format=json`,
               '-f','null','-'],
        capture: 'stderr',
        parse: (_o, err) => {
          // loudnorm prints its JSON as the LAST object on stderr. Taking the
          // first '{' grabs ffmpeg's own noise on some builds.
          const i = err.lastIndexOf('{');
          const j = err.lastIndexOf('}');
          if (i === -1 || j === -1) throw new Error('loudnorm pass 1 produced no JSON');
          const m = JSON.parse(err.slice(i, j + 1));
          return {
            measured_I: Number(m.input_i), measured_TP: Number(m.input_tp),
            measured_LRA: Number(m.input_lra), measured_thresh: Number(m.input_thresh),
            offset: Number(m.target_offset),
          };
        },
      };
    },
  },

  /** loudnorm pass 2 — apply the measurement from pass 1. */
  loudnorm_apply: {
    build(p) {
      const f = existingPath(p.input, 'input');
      const out = ensureDir(safePath(p.output, 'output'));
      const I   = num(p.target_i  ?? -16, 'target_i',  { min: -40, max: -5 });
      const TP  = num(p.target_tp ?? -1.5,'target_tp', { min: -9,  max: 0 });
      const LRA = num(p.lra       ?? 11,  'lra',       { min: 1,   max: 50 });
      const m = p.measured || {};
      for (const k of ['measured_I','measured_TP','measured_LRA','measured_thresh','offset']) {
        num(m[k], `measured.${k}`);
      }
      const af = `loudnorm=I=${I}:TP=${TP}:LRA=${LRA}` +
        `:measured_I=${m.measured_I}:measured_TP=${m.measured_TP}` +
        `:measured_LRA=${m.measured_LRA}:measured_thresh=${m.measured_thresh}` +
        `:offset=${m.offset}:linear=true:print_format=summary`;
      return {
        bin: FF,
        argv: ['-y', ...QUIET, '-i', f, '-af', af,
               '-ar', String(num(p.sample_rate ?? 48000, 'sample_rate', { min: 8000, max: 192000, int: true })),
               '-c:a', oneOf(p.codec ?? 'pcm_s24le', 'codec', ['pcm_s16le','pcm_s24le','pcm_f32le','aac','flac']),
               out],
        parse: () => ({ output: path.relative(WORK_ROOT, out) }),
      };
    },
  },

  /**
   * Duck the bed under the narration and mix.
   *
   * The afade guards matter more than the sidechain does. Sidechain RELEASE
   * makes the bed swell back up exactly where nothing should be — in the
   * protected silence. The explicit fades hold it down through those windows.
   */
  duck_mix: {
    build(p) {
      const nar = existingPath(p.narration, 'narration');
      const bed = existingPath(p.bed, 'bed');
      const out = ensureDir(safePath(p.output, 'output'));
      const gain = num(p.bed_gain ?? 0.35, 'bed_gain', { min: 0, max: 2 });
      const ramp = num(p.ramp ?? 0.4, 'ramp', { min: 0.05, max: 3 });

      const guards = Array.isArray(p.guards) ? p.guards : [];
      if (guards.length > 64) throw new BadJob('guards: too many (max 64)');
      const fades = [];
      for (const [idx, g] of guards.entries()) {
        const s = num(g.start, `guards[${idx}].start`, { min: 0, max: 86400 });
        const e = num(g.end,   `guards[${idx}].end`,   { min: 0, max: 86400 });
        if (e <= s) throw new BadJob(`guards[${idx}]: end must exceed start`);
        fades.push(`afade=t=out:st=${Math.max(0, s - ramp).toFixed(3)}:d=${ramp}`);
        fades.push(`afade=t=in:st=${e.toFixed(3)}:d=${ramp}`);
      }
      const bedChain = ['[1:a]', fades.length ? fades.join(',') + ',' : '', 'anull[bedg]'].join('');

      const filter =
        `[0:a]asplit=2[nar][key];` +
        bedChain + `;` +
        `[bedg][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400:makeup=1[duck];` +
        `[nar][duck]amix=inputs=2:duration=first:dropout_transition=0:weights=1 ${gain}[mix]`;

      return {
        bin: FF,
        argv: ['-y', ...QUIET, '-i', nar, '-i', bed, '-filter_complex', filter,
               '-map', '[mix]', '-ar', '48000', '-c:a', 'pcm_s24le', out],
        parse: () => ({ output: path.relative(WORK_ROOT, out), guards: guards.length }),
      };
    },
  },

  /**
   * silencedetect. Returns every silence found, not a count.
   *
   * The old node piped into `grep -c silence_start || true`, which under
   * `set -o pipefail` returns 141 on SIGPIPE and reads as a failure when it
   * isn't. Parsing in Node removes the pipeline and the whole class of bug.
   */
  silence_detect: {
    build(p) {
      const f = existingPath(p.input, 'input');
      const noise = num(p.noise_db ?? -50, 'noise_db', { min: -90, max: 0 });
      const dur   = num(p.min_duration ?? 3.5, 'min_duration', { min: 0.1, max: 600 });
      return {
        bin: FF,
        argv: [...MEASURE, '-i', f, '-af', `silencedetect=noise=${noise}dB:d=${dur}`,
               '-f','null','-'],
        capture: 'stderr',
        parse: (_o, err) => {
          const silences = [];
          const re = /silence_start:\s*(-?[\d.]+)[\s\S]*?silence_end:\s*(-?[\d.]+)\s*\|\s*silence_duration:\s*([\d.]+)/g;
          let m;
          while ((m = re.exec(err)) !== null) {
            silences.push({ start: +m[1], end: +m[2], duration: +m[3] });
          }
          return {
            count: silences.length,
            longest: silences.reduce((a, s) => Math.max(a, s.duration), 0),
            silences,
          };
        },
      };
    },
  },

  /** Assemble the cut: N shots, xfade chained, one encode. */
  assemble_cut: {
    build(p) {
      const shots = Array.isArray(p.shots) ? p.shots : [];
      if (shots.length < 1) throw new BadJob('shots: need at least one');
      if (shots.length > 200) throw new BadJob('shots: too many (max 200)');
      const out = ensureDir(safePath(p.output, 'output'));
      const xf  = num(p.crossfade ?? 1.0, 'crossfade', { min: 0, max: 10 });

      const inputs = [];
      const trims = [];
      let offset = 0;
      shots.forEach((s, i) => {
        const f  = existingPath(s.path, `shots[${i}].path`);
        const IN = num(s.in ?? 0, `shots[${i}].in`, { min: 0, max: 86400 });
        const OUT= num(s.out, `shots[${i}].out`, { min: 0, max: 86400 });
        if (OUT <= IN) throw new BadJob(`shots[${i}]: out must exceed in`);
        if (i < shots.length - 1 && (OUT - IN) <= xf) {
          throw new BadJob(`shots[${i}]: shorter than the crossfade (${(OUT-IN).toFixed(2)}s <= ${xf}s)`);
        }
        inputs.push('-i', f);
        trims.push(`[${i}:v]trim=start=${IN}:end=${OUT},setpts=PTS-STARTPTS[v${i}]`);
      });

      const parts = [...trims];
      let last = 'v0';
      for (let k = 1; k < shots.length; k++) {
        const dur = num(shots[k-1].out, '', {}) - num(shots[k-1].in ?? 0, '', {});
        offset += dur - xf;
        const outLbl = (k === shots.length - 1) ? 'vout' : `x${k}`;
        parts.push(`[${last}][v${k}]xfade=transition=fade:duration=${xf}:offset=${offset.toFixed(3)}[${outLbl}]`);
        last = outLbl;
      }
      if (shots.length === 1) parts.push(`[v0]null[vout]`);

      return {
        bin: FF,
        argv: ['-y', ...QUIET, ...inputs, '-filter_complex', parts.join(';'),
               '-map', '[vout]', '-an',
               '-c:v', 'libx264', '-crf', String(num(p.crf ?? 16, 'crf', { min: 0, max: 51, int: true })),
               '-preset', oneOf(p.preset ?? 'medium', 'preset', PRESETS),
               '-pix_fmt', 'yuv420p', out],
        parse: () => ({ output: path.relative(WORK_ROOT, out), shots: shots.length }),
      };
    },
  },

  /**
   * Full mark render: Playwright capture + ffmpeg assembly.
   *
   * Captures frames from the living HTML mark using headless Chromium, then
   * assembles them into a ProRes 4444 alpha layer. This is the one job that
   * needs a browser engine — everything else in the worker is ffmpeg or Node.
   *
   * Requires: playwright and chromium installed on the box.
   *   npm install playwright && npx playwright install chromium
   *
   * params: { mark_html, output, width, height, fps, mark_seconds,
   *           seed?, trail_build? }
   */
  render_mark_full: {
    build(p) {
      const markHtml = existingPath(p.mark_html, 'mark_html');
      const out      = ensureDir(safePath(p.output, 'output'));
      const W   = num(p.width  ?? 3840, 'width',  { min: 16, max: 8192, int: true });
      const H   = num(p.height ?? 2160, 'height', { min: 16, max: 8192, int: true });
      const fps = num(p.fps ?? 24, 'fps', { min: 1, max: 120 });
      const secs = num(p.mark_seconds ?? 6, 'mark_seconds', { min: 0.1, max: 120 });
      const frames = Math.round(secs * fps);
      const seed = num(p.seed ?? 72126, 'seed', { min: 0, max: 999999, int: true });
      const warm = num(p.trail_build ?? 4.5, 'trail_build', { min: 0, max: 30 });

      // Temporary frames directory — cleaned up after assembly.
      const tmpDir = safePath(`tmp/mark_${Date.now()}`, 'tmpDir');
      const framesDir = path.join(tmpDir, 'frames');

      return { native: async () => {
        // Phase 1: Playwright capture
        let chromium;
        try { ({ chromium } = require('playwright')); }
        catch (e) { throw new Error('playwright not installed — npm install playwright'); }

        fs.mkdirSync(framesDir, { recursive: true });
        const browser = await chromium.launch({
          args: ['--use-gl=angle', '--use-angle=swiftshader',
                 '--enable-unsafe-swiftshader'],
        });
        try {
          const page = await browser.newPage({
            viewport: { width: W, height: H },
            deviceScaleFactor: 1,
          });
          const url = `file://${markHtml}?size=${W}&text=0`;
          await page.goto(url);
          await page.waitForTimeout(1500);

          for (let f = 0; f < frames; f++) {
            const t = warm + f / fps;
            await page.evaluate((t) => {
              if (typeof window.renderAt === 'function') return window.renderAt(t);
              window.__virtualTime = t;
            }, t);
            const name = `f_${String(f).padStart(6, '0')}.png`;
            await page.screenshot({
              path: path.join(framesDir, name),
              omitBackground: true,
            });
          }
        } finally {
          await browser.close();
        }

        // Phase 2: ffmpeg assembly — same as render_mark but inline.
        const { execFileSync } = require('child_process');
        fs.mkdirSync(path.dirname(out), { recursive: true });
        execFileSync(FF, [
          '-y', ...QUIET, '-framerate', String(fps),
          '-i', path.join(framesDir, 'f_%06d.png'),
          '-c:v', 'prores_ks', '-profile:v', '4444',
          '-pix_fmt', 'yuva444p10le', out,
        ], { cwd: WORK_ROOT, env: { PATH: process.env.PATH, LANG: 'C' } });

        // Cleanup
        fs.rmSync(tmpDir, { recursive: true, force: true });
        return { output: path.relative(WORK_ROOT, out), frames };
      }};
    },
  },

  /** PNG frame sequence -> ProRes 4444 with alpha. The mark layer. */
  render_mark: {
    build(p) {
      const dir = existingPath(p.frames_dir, 'frames_dir');
      const out = ensureDir(safePath(p.output, 'output'));
      const fps = num(p.fps ?? 24, 'fps', { min: 1, max: 120 });
      const pat = oneOf(p.pattern ?? 'f_%06d.png', 'pattern',
                        ['f_%06d.png','f_%05d.png','frame_%06d.png','%06d.png']);
      return {
        bin: FF,
        argv: ['-y', ...QUIET, '-framerate', String(fps), '-i', path.join(dir, pat),
               '-c:v', 'prores_ks', '-profile:v', '4444', '-pix_fmt', 'yuva444p10le', out],
        parse: () => ({ output: path.relative(WORK_ROOT, out) }),
      };
    },
  },

  /** visual + mark (alpha, faded in) + audio -> master. */
  composite_mux: {
    build(p) {
      const vis  = existingPath(p.visual, 'visual');
      const mark = existingPath(p.mark, 'mark');
      const aud  = existingPath(p.audio, 'audio');
      const out  = ensureDir(safePath(p.output, 'output'));
      const markIn  = num(p.mark_fade_in ?? 1, 'mark_fade_in', { min: 0, max: 10 });
      const markSec = num(p.mark_seconds ?? 6, 'mark_seconds', { min: 0, max: 120 });
      const filter =
        `[1:v]format=yuva444p10le,fade=t=in:st=0:d=${markIn}:alpha=1,` +
        `fade=t=out:st=${(markSec - markIn).toFixed(3)}:d=${markIn}:alpha=1[mk];` +
        `[0:v][mk]overlay=0:0:enable='lte(t,${markSec})'[v]`;
      return {
        bin: FF,
        argv: ['-y', ...QUIET, '-i', vis, '-i', mark, '-i', aud,
               '-filter_complex', filter, '-map', '[v]', '-map', '2:a',
               '-c:v', 'libx264', '-crf', String(num(p.crf ?? 15, 'crf', { min: 0, max: 51, int: true })),
               '-preset', oneOf(p.preset ?? 'medium', 'preset', PRESETS),
               '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '320k',
               '-movflags', '+faststart', out],
        parse: () => ({ output: path.relative(WORK_ROOT, out) }),
      };
    },
  },

  /**
   * Conform + grain in ONE ffmpeg pass. Splitting scale/grain/encode costs a
   * full generation of re-encode for nothing.
   *
   * Default preset is 'medium', NOT 'slow'. Measured on real EP01 footage at
   * 4K: slow = 0.436 fps, medium = 1.154 fps on two cores — 2.6x — and at crf16
   * slow was not buying quality, it was preserving more of the grain we add on
   * purpose. Override if a test says otherwise for a given episode.
   *
   * ---------------------------------------------------------------------
   * THE SPLIT (added with EditForge v3.1)
   *
   * For TSWS, EditForge is a PLANNER. It does not render. Its plan — the cut,
   * the ending sequence, the grade — is executed HERE, inside the encode this
   * stage was already going to do. That is the entire point: a separate
   * EditForge render pass would cost a full extra generation on a 10-bit
   * master, which is the one thing this stage exists to protect.
   *
   * Everything below is OPTIONAL. Send none of it and this job behaves
   * byte-for-byte as it did before: scale, 10-bit, setrange, grain, copy audio.
   *
   *   keep_segments      [{start,end}]  cut, from the ORIGINAL, concatenated
   *   protected_windows  [{start,end}]  a cut boundary inside one is refused
   *   color              {...}          house-style grade, in 10-bit
   *   ending             {...}          still hold -> fade to black -> tail
   *
   * Filter order is deliberate and not rearrangeable without consequence:
   *   trim/concat -> scale -> 10-bit -> setrange -> grade -> hold/fade -> grain
   * Grade after the 10-bit conversion so the grade does not band. Fade after
   * the grade so black is true black and not a graded near-black. Grain last
   * because grain is film, and film grain sits on top of everything including
   * the fade.
   */
  conform_grain: {
    build(p) {
      const f   = existingPath(p.input, 'input');
      const out = ensureDir(safePath(p.output, 'output'));
      const W = num(p.width  ?? 3840, 'width',  { min: 16, max: 8192, int: true });
      const H = num(p.height ?? 2160, 'height', { min: 16, max: 8192, int: true });
      const crf   = num(p.crf ?? 16, 'crf', { min: 0, max: 51, int: true });
      const grain = num(p.grain ?? 0, 'grain', { min: 0, max: 100, int: true });
      const preset= oneOf(p.preset ?? 'medium', 'preset', PRESETS);
      const fps   = num(p.fps ?? 24, 'fps', { min: 1, max: 240 });

      // --- the cut ---------------------------------------------------------
      const segs = Array.isArray(p.keep_segments) ? p.keep_segments : [];
      if (segs.length > 200) throw new BadJob('keep_segments: too many (max 200)');
      const guards = Array.isArray(p.protected_windows) ? p.protected_windows : [];

      const keep = segs.map((s, i) => {
        const a = num(s.start, `keep_segments[${i}].start`, { min: 0, max: 86400 });
        const b = num(s.end,   `keep_segments[${i}].end`,   { min: 0, max: 86400 });
        if (b <= a) throw new BadJob(`keep_segments[${i}]: end must be greater than start`);
        return { start: a, end: b };
      }).sort((x, y) => x.start - y.start);

      for (let i = 1; i < keep.length; i++) {
        if (keep[i].start < keep[i - 1].end) {
          throw new BadJob(`keep_segments: [${i}] overlaps [${i - 1}]`);
        }
      }

      // STANDING PROVISION. A protected silence is a performance, not dead air.
      // Landing a cut boundary inside one truncates a hold that pipeline 02
      // deliberately preserved. Passing cleanly THROUGH a whole window is fine;
      // slicing into one is refused here, at the layer that actually runs
      // ffmpeg, regardless of what the planner or the workflow believed.
      const EPS = 0.001;
      for (let i = 0; i < guards.length; i++) {
        const g = guards[i];
        const gs = num(g.start, `protected_windows[${i}].start`, { min: 0, max: 86400 });
        const ge = num(g.end,   `protected_windows[${i}].end`,   { min: 0, max: 86400 });
        for (const k of keep) {
          for (const edge of [k.start, k.end]) {
            if (edge > gs + EPS && edge < ge - EPS) {
              throw new BadJob(
                `keep_segments: cut at ${edge}s falls inside protected silence ` +
                `${gs}–${ge}s. Move the boundary outside the window.`);
            }
          }
        }
      }

      const cutting = keep.length > 0;
      const kept = keep.reduce((a, s) => a + (s.end - s.start), 0);
      // The caller probes; the caller tells us. Guessing here and guessing wrong
      // produces an ffmpeg graph error about a stream that does not exist,
      // which reads like a bug in the filter rather than a missing track.
      const hasAudio = p.has_audio === undefined ? true : !!p.has_audio;

      // --- the grade -------------------------------------------------------
      // House style. The planner chooses WHERE; it never chooses HOW MUCH.
      const c = p.color && typeof p.color === 'object' ? p.color : null;
      let grade = '';
      if (c) {
        const bright = num(c.exposure   ?? 0, 'color.exposure',   { min: -1,  max: 1 });
        const contr  = num(c.contrast   ?? 1, 'color.contrast',   { min: 0,   max: 3 });
        const sat    = num(c.saturation ?? 1, 'color.saturation', { min: 0,   max: 3 });
        const kelvin = num(c.warmth_k   ?? 0, 'color.warmth_k',   { min: 0,   max: 40000 });
        const vig    = num(c.vignette   ?? 0, 'color.vignette',   { min: 0,   max: 1.5 });
        const bits = [];
        if (bright !== 0 || contr !== 1 || sat !== 1) {
          bits.push(`eq=brightness=${bright}:contrast=${contr}:saturation=${sat}`);
        }
        if (kelvin > 0) bits.push(`colortemperature=temperature=${kelvin}:mix=1:pl=0`);
        if (vig > 0)    bits.push(`vignette=angle=${vig}`);
        grade = bits.join(',');
      }

      // --- the ending ------------------------------------------------------
      // Contract: the still hold runs its FULL duration, THEN the fade begins,
      // THEN a short black tail so the fade actually completes and leaves a
      // segment blackdetect can find. A fade that merely reaches the last frame
      // renders an ending that cannot be verified — see references/video-file-audit.
      const e = p.ending && typeof p.ending === 'object' ? p.ending : null;
      let hold = 0, fadeDur = 0, tailDur = 0;
      if (e) {
        hold    = num(e.still_hold_s   ?? 0,  'ending.still_hold_s',   { min: 0, max: 30 });
        const ff = num(e.fade_frames   ?? 0,  'ending.fade_frames',    { min: 0, max: 240, int: true });
        const bt = num(e.black_tail_frames ?? 6, 'ending.black_tail_frames', { min: 0, max: 240, int: true });
        fadeDur = ff / fps;
        tailDur = ff > 0 ? bt / fps : 0;
      }
      const padDur = hold + fadeDur + tailDur;
      const hasEnding = padDur > 0;

      // The ending needs to know where the timeline ends. With a cut we know it
      // exactly (sum of kept segments). Without one we must probe, and this job
      // does not probe — so an ending without a cut requires source_duration.
      let timelineEnd = kept;
      if (hasEnding && !cutting) {
        timelineEnd = num(p.source_duration, 'source_duration',
          { min: 0.001, max: 86400 });  // required when ending without a cut
      }

      const baseChain =
        `scale=${W}:${H}:flags=lanczos+accurate_rnd+full_chroma_int,` +
        `format=yuv420p10le,setrange=tv` +
        (grade ? `,${grade}` : '') +
        (hasEnding
          ? `,tpad=stop_mode=clone:stop_duration=${padDur.toFixed(6)}` +
            (fadeDur > 0
              ? `,fade=t=out:st=${(timelineEnd + hold).toFixed(6)}:d=${fadeDur.toFixed(6)}`
              : '')
          : '') +
        (grain > 0 ? `,noise=alls=${grain}:allf=t+u` : '');

      const argv = ['-y', ...QUIET, '-i', f];

      if (cutting) {
        // Trim from the ORIGINAL and concatenate. Never cut-then-recut: each
        // intermediate is a generation, and -ss before -i seeks to a keyframe,
        // which lands the cut up to a GOP away from where the plan said.
        //
        // concat wants its inputs INTERLEAVED per segment — [v0][a0][v1][a1] —
        // not all video then all audio. Getting that wrong is a graph-link
        // error with a famously unhelpful message.
        const parts = [];
        const pairs = [];
        const FA = 0.02;  // 20 ms de-click at every join. A hard audio cut
                          // mid-waveform pops, and on a two-voice show that
                          // reads as cheap long before anyone can name why.
        keep.forEach((s, i) => {
          const d = s.end - s.start;
          parts.push(`[0:v]trim=start=${s.start}:end=${s.end},setpts=PTS-STARTPTS[v${i}]`);
          pairs.push(`[v${i}]`);
          if (!hasAudio) return;
          parts.push(
            `[0:a]atrim=start=${s.start}:end=${s.end},asetpts=PTS-STARTPTS,` +
            `afade=t=in:st=0:d=${FA},afade=t=out:st=${Math.max(0, d - FA).toFixed(6)}:d=${FA}[a${i}]`);
          pairs[pairs.length - 1] = `[v${i}][a${i}]`;
        });
        parts.push(`${pairs.join('')}concat=n=${keep.length}:v=1:a=${hasAudio ? 1 : 0}` +
                   (hasAudio ? '[vcut][acut]' : '[vcut]'));
        parts.push(`[vcut]${baseChain}[vout]`);
        if (hasAudio) parts.push(`[acut]apad=pad_dur=${padDur.toFixed(6)}[aout]`);
        argv.push('-filter_complex', parts.join(';'), '-map', '[vout]');
        if (hasAudio) argv.push('-map', '[aout]');
      } else if (hasEnding) {
        argv.push('-filter_complex',
          `[0:v]${baseChain}[vout]` +
          (hasAudio ? `;[0:a]apad=pad_dur=${padDur.toFixed(6)}[aout]` : ''),
          '-map', '[vout]');
        if (hasAudio) argv.push('-map', '[aout]');
      } else {
        argv.push('-vf', baseChain);
      }

      argv.push('-c:v', 'libx265', '-crf', String(crf), '-preset', preset,
                '-x265-params', 'log-level=error', '-pix_fmt', 'yuv420p10le');
      // Audio is copied when we do not touch it. The moment we cut or pad we
      // have to re-encode — one generation, unavoidable, and stated rather
      // than hidden.
      if (hasAudio) {
        argv.push(...(cutting || hasEnding
          ? ['-c:a', 'aac', '-b:a', '320k']
          : ['-c:a', 'copy']));
      } else {
        argv.push('-an');
      }
      argv.push('-movflags', '+faststart', out);

      return {
        bin: FF,
        argv,
        parse: () => ({
          output: path.relative(WORK_ROOT, out),
          width: W, height: H, crf, preset, grain,
          plan_applied: cutting || hasEnding || !!grade,
          cut: cutting,
          segments: keep.length,
          kept_duration: cutting ? Number(kept.toFixed(3)) : null,
          expected_duration: hasEnding || cutting
            ? Number((timelineEnd + padDur).toFixed(3)) : null,
          graded: !!grade,
          ending: hasEnding
            ? { hold_s: hold, fade_s: Number(fadeDur.toFixed(4)), tail_s: Number(tailDur.toFixed(4)) }
            : null,
          audio: !hasAudio ? 'none'
               : (cutting || hasEnding) ? 're-encoded aac 320k' : 'copied',
        }),
      };
    },
  },

  // =========================================================================
  // NATIVE JOBS — no subprocess at all.
  //
  // Nine of the 26 original nodes were not ffmpeg: find, cat, test -f, mkdir,
  // printf >>, touch, and two curl transfers. Shelling out for those would
  // reintroduce exactly the injection surface the ffmpeg jobs avoid, for
  // operations Node does natively and better. `test -f X && echo HIT || echo
  // MISS` in particular can never report a real error — a permissions failure
  // and a genuine miss both print MISS.
  // =========================================================================

  /** Find episode dirs containing a manifest. Replaces `find -name manifest.json`. */
  scan_drop: {
    build(p) {
      const dir = existingPath(p.drop_dir, 'drop_dir');
      const marker = oneOf(p.marker ?? 'manifest.json', 'marker', ['manifest.json']);
      return { native: async () => {
        const found = [];
        for (const a of fs.readdirSync(dir, { withFileTypes: true })) {
          if (!a.isDirectory()) continue;
          for (const b of fs.readdirSync(path.join(dir, a.name), { withFileTypes: true })) {
            if (!b.isDirectory()) continue;
            const epDir = path.join(dir, a.name, b.name);
            if (fs.existsSync(path.join(epDir, marker))) {
              // Skip anything already finished, same as the old `.done` check.
              if (fs.existsSync(path.join(epDir, '.done'))) continue;
              found.push(path.relative(WORK_ROOT, epDir));
            }
          }
        }
        found.sort();
        return { count: found.length, episodes: found };
      }};
    },
  },

  /** Read a text file. Replaces `cat manifest.json`. */
  read_text: {
    build(p) {
      const f = existingPath(p.path, 'path');
      const max = num(p.max_bytes ?? 1024 * 1024, 'max_bytes', { min: 1, max: 16 * 1024 * 1024 });
      return { native: async () => {
        const st = fs.statSync(f);
        if (st.size > max) throw new Error(`file is ${st.size} bytes, over max_bytes ${max}`);
        const text = fs.readFileSync(f, 'utf8');
        let parsed = null;
        if (p.parse_json) {
          try { parsed = JSON.parse(text); }
          catch (e) { throw new Error(`not valid JSON: ${e.message}`); }
        }
        return { text, json: parsed, bytes: st.size };
      }};
    },
  },

  /**
   * Artifact cache probe. Replaces `test -f X && echo HIT || echo MISS`.
   * Returns size and mtime too — a zero-byte file from a crashed render is a
   * MISS as far as anything downstream is concerned, and the shell version
   * called it a HIT.
   */
  exists: {
    build(p) {
      const f = safePath(p.path, 'path');
      const minBytes = num(p.min_bytes ?? 1, 'min_bytes', { min: 0 });
      return { native: async () => {
        if (!fs.existsSync(f)) return { hit: false, reason: 'missing' };
        const st = fs.statSync(f);
        if (!st.isFile()) return { hit: false, reason: 'not a file' };
        if (st.size < minBytes) return { hit: false, reason: `only ${st.size} bytes`, bytes: st.size };
        return { hit: true, bytes: st.size, mtime: st.mtime.toISOString() };
      }};
    },
  },

  /**
   * An ordered batch of filesystem writes. Replaces `Build Finalise Command`
   * and all four `Append To * Log` nodes.
   *
   * One job rather than four sub-workflow calls, but still no pipeline
   * semantics baked into the worker — it's a list of primitives, each
   * path-confined.
   */
  fs_ops: {
    build(p) {
      const ops = Array.isArray(p.ops) ? p.ops : [];
      if (!ops.length) throw new BadJob('ops: empty');
      if (ops.length > 32) throw new BadJob('ops: too many (max 32)');
      const plan = ops.map((o, i) => {
        const op = oneOf(o.op, `ops[${i}].op`, ['mkdir', 'write', 'append_line', 'touch', 'copy']);
        const target = safePath(o.path, `ops[${i}].path`);
        if (op === 'write' || op === 'append_line') {
          if (typeof o.content !== 'string') throw new BadJob(`ops[${i}].content: must be a string`);
          if (o.content.length > 1024 * 1024) throw new BadJob(`ops[${i}].content: too large`);
        }
        const src = op === 'copy' ? existingPath(o.src, `ops[${i}].src`) : null;
        return { op, target, content: o.content, src };
      });
      return { native: async () => {
        const done = [];
        for (const s of plan) {
          if (s.op === 'mkdir') fs.mkdirSync(s.target, { recursive: true });
          else {
            fs.mkdirSync(path.dirname(s.target), { recursive: true });
            if (s.op === 'write') fs.writeFileSync(s.target, s.content);
            else if (s.op === 'append_line') fs.appendFileSync(s.target, s.content.replace(/\n*$/, '') + '\n');
            else if (s.op === 'copy') fs.copyFileSync(s.src, s.target);
            else fs.closeSync(fs.openSync(s.target, 'a'));   // touch
          }
          done.push({ op: s.op, path: path.relative(WORK_ROOT, s.target) });
        }
        return { applied: done.length, ops: done };
      }};
    },
  },

  /** Download a URL to a file. Replaces `curl -sS -L -o out url`. */
  http_download: {
    build(p) {
      const out = ensureDir(safePath(p.output, 'output'));
      const url = httpsUrl(p.url, 'url');
      const maxMB = num(p.max_mb ?? 8192, 'max_mb', { min: 1, max: 65536 });
      return { native: async () => {
        const bytes = await downloadTo(url, out, maxMB * 1024 * 1024);
        return { output: path.relative(WORK_ROOT, out), bytes };
      }};
    },
  },

  /**
   * Upload a file to presigned URLs in parts, collecting ETags.
   * Replaces `Build Upload Script` — a generated bash loop with `sed -n`,
   * `awk`, and a curl per part.
   *
   * Doing it here means a failed part throws with which part and why, instead
   * of producing an empty ETag that only surfaces when Topaz rejects the
   * completed upload much later.
   */
  multipart_upload: {
    build(p) {
      const f = existingPath(p.input, 'input');
      const urls = Array.isArray(p.urls) ? p.urls : [];
      if (!urls.length) throw new BadJob('urls: empty');
      if (urls.length > 10000) throw new BadJob('urls: too many');
      urls.forEach((u, i) => httpsUrl(u, `urls[${i}]`));
      const partSize = num(p.part_size ?? 64 * 1024 * 1024, 'part_size',
                           { min: 5 * 1024 * 1024, max: 512 * 1024 * 1024, int: true });
      return { native: async () => {
        const total = fs.statSync(f).size;
        const need = Math.ceil(total / partSize);
        if (need !== urls.length) {
          throw new Error(`file is ${total} bytes = ${need} parts at ${partSize}, ` +
                          `but ${urls.length} URLs were supplied`);
        }
        const results = [];
        for (let i = 0; i < urls.length; i++) {
          const start = i * partSize;
          const end = Math.min(start + partSize, total) - 1;
          const etag = await putRange(urls[i], f, start, end);
          if (!etag) throw new Error(`part ${i + 1}/${urls.length}: no ETag returned`);
          results.push({ PartNumber: i + 1, ETag: etag });
        }
        return { parts: results.length, uploadResults: results, bytes: total };
      }};
    },
  },

  /** PSNR against a native reference. The conform quality gate. */
  psnr: {
    build(p) {
      const a = existingPath(p.input, 'input');
      const b = existingPath(p.reference, 'reference');
      const W = num(p.width  ?? 3840, 'width',  { min: 16, max: 8192, int: true });
      const H = num(p.height ?? 2160, 'height', { min: 16, max: 8192, int: true });
      const lavfi =
        `[0:v]scale=${W}:${H}:flags=bicubic,format=yuv420p,setrange=tv[a];` +
        `[1:v]scale=${W}:${H}:flags=bicubic,format=yuv420p,setrange=tv[b];[a][b]psnr`;
      return {
        bin: FF,
        argv: [...MEASURE, '-i', a, '-i', b, '-lavfi', lavfi, '-f','null','-'],
        capture: 'stderr',
        parse: (_o, err) => {
          const m = /average:([\d.]+|inf)/.exec(err);
          if (!m) throw new Error('psnr: ffmpeg produced no average');
          return { psnr: m[1] === 'inf' ? Infinity : Number(m[1]) };
        },
      };
    },
  },

  /**
   * Verify a rendered ending against the doctrine. The gate for a planned cut.
   *
   * PSNR is the void-fabrication gate, and it only works when the output
   * corresponds frame-for-frame to a native reference. The moment a plan removes
   * segments that correspondence is gone and PSNR measures nothing — so the
   * honest move is to skip it, say why, and put a gate here that *does* apply.
   *
   * A Premium Restraint ending leaves three measurable signatures in the file:
   * a held frame, a fade, and sustained black. If the doctrine was applied,
   * these are present. If they are absent, the claim fails on evidence rather
   * than on opinion. That is the whole point of measuring instead of asserting.
   */
  ending_verify: {
    build(p) {
      const f = existingPath(p.input, 'input');
      const expected = p.expected_duration === undefined
        ? null : num(p.expected_duration, 'expected_duration', { min: 0, max: 86400 });
      const tolFrames = num(p.tolerance_frames ?? 2, 'tolerance_frames', { min: 0, max: 240 });
      const fps = num(p.fps ?? 24, 'fps', { min: 1, max: 240 });
      const wantBlack  = p.expect_black  === undefined ? true : !!p.expect_black;
      const wantFreeze = p.expect_freeze === undefined ? true : !!p.expect_freeze;

      return {
        bin: FF,
        argv: [...MEASURE, '-i', f,
               // One pass, both detectors. Two passes over a 4K master to learn
               // two facts is a waste of the only slow resource here.
               '-vf', 'blackdetect=d=0.1:pic_th=0.98,freezedetect=n=-60dB:d=0.5',
               '-f', 'null', '-'],
        capture: 'stderr',
        parse: (_o, err) => {
          const blacks = [];
          const rb = /black_start:([\d.]+) black_end:([\d.]+) black_duration:([\d.]+)/g;
          let m;
          while ((m = rb.exec(err)) !== null) {
            blacks.push({ start: +m[1], end: +m[2], duration: +m[3] });
          }
          const freezes = [];
          const rf = /freeze_start:\s*([\d.]+)/g;
          while ((m = rf.exec(err)) !== null) freezes.push(Number(m[1]));

          // Duration comes from the demuxer line ffmpeg prints for the input.
          let actual = null;
          const dm = /Duration:\s*(\d+):(\d+):([\d.]+)/.exec(err);
          if (dm) actual = (+dm[1]) * 3600 + (+dm[2]) * 60 + parseFloat(dm[3]);

          const failures = [];
          const tol = tolFrames / fps;
          if (expected !== null && actual !== null && Math.abs(actual - expected) > tol) {
            failures.push(`duration ${actual.toFixed(3)}s differs from the planned ` +
                          `${expected.toFixed(3)}s by more than ${tolFrames} frame(s)`);
          }
          if (wantBlack && blacks.length === 0) {
            failures.push('no sustained black — the fade to black either did not run ' +
                          'or never completed, so the ending cannot be verified');
          }
          if (wantFreeze && freezes.length === 0) {
            failures.push('no held frame — the still-frame hold is missing');
          }

          return {
            passed: failures.length === 0,
            failures,
            duration_s: actual,
            expected_duration_s: expected,
            black_segments: blacks,
            freeze_starts: freezes,
            last_black: blacks.length ? blacks[blacks.length - 1] : null,
          };
        },
      };
    },
  },
};

module.exports = { JOBS, BadJob, safePath, existingPath, num, oneOf, setRoot, getRoot, PRESETS };
