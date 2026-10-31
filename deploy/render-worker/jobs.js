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
  // path.resolve does NOT follow symlinks, so a lexical prefix check alone lets
  // a single symlink inside the work root read and write anywhere on the box.
  // Measured: a `media -> /etc` link inside WORK_ROOT served /etc/passwd through
  // `exists` and /etc/hostname through `read_text`. Resolve the real path of the
  // deepest existing ancestor before comparing; an output file that does not
  // exist yet is judged by the directory it will be created in.
  const real = realDeepest(abs);
  const rootReal = realDeepest(WORK_ROOT);
  const root = rootReal.endsWith(path.sep) ? rootReal : rootReal + path.sep;
  if (real !== rootReal && !real.startsWith(root)) {
    throw new BadJob(`${label}: path escapes the work root`);
  }
  return abs;
}

/**
 * realpath of the deepest ancestor of `abs` that exists, with the unresolved
 * remainder appended. Never throws: a path whose ancestors are all missing
 * resolves to itself, which the caller's prefix check then judges lexically.
 */
function realDeepest(abs) {
  let head = abs;
  const tail = [];
  for (;;) {
    try { return tail.length ? path.join(fs.realpathSync(head), ...tail) : fs.realpathSync(head); }
    catch { /* fall through and climb */ }
    const parent = path.dirname(head);
    if (parent === head) return abs;
    tail.unshift(path.basename(head));
    head = parent;
  }
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

// --- picture normalisation and still handling ------------------------------

/**
 * Scale and pad to exactly WxH, then pin SAR and pixel format.
 *
 * decrease + pad, never increase + crop. A black bar is a bug report; a crop is
 * a lie that silently discards a deliberately framed edge.
 *
 * Without this ahead of every shot, xfade on mixed-size inputs fails to
 * configure the output pad and ffmpeg writes a 0-byte file. QC measured
 * *minimum* width 3840 on the EP01 plates, not uniform 3840, so the plates
 * looked compliant and were not.
 */
function normalizeChain(W, H) {
  return `scale=${W}:${H}:force_original_aspect_ratio=decrease:flags=lanczos,` +
         `pad=${W}:${H}:(ow-iw)/2:(oh-ih)/2:color=black,setsar=1,format=yuv420p`;
}

const STILL_EXT = new Set(['.jpg', '.jpeg', '.png', '.webp', '.bmp', '.tif', '.tiff']);

/** Inference of last resort. A declared shots[i].still always wins over this. */
function isStill(f) { return STILL_EXT.has(path.extname(f).toLowerCase()); }

/**
 * A gap in a signal is a gain envelope, not a pair of fades.
 *
 * The old chain was `afade=t=out` followed by `afade=t=in`. afade=t=out ramps
 * to zero and then HOLDS zero for the remainder of the stream; the following
 * afade=t=in multiplies everything before its own start by zero. Chained, they
 * do not reopen the gate, they close it for good. On EP01 that killed the bed
 * at 544.000s of an 880.907s episode and left the final 53 seconds as digital
 * silence under picture. It passed every gate that existed, because the only
 * gate measured length, and a silent file is exactly as long as a loud one.
 *
 * Each guard contributes an attenuation that is 0 outside its window, ramps to
 * 1 over `ramp` seconds, holds 1 across the gap, and ramps back down. The
 * overlap check rejects overlapping [s, e] windows but NOT windows whose ramps
 * overlap, so two guards closer than 2*ramp can both be non-zero at the same t
 * and the raw sum can exceed 1. The outer max(0, ...) is what makes that safe,
 * so it is load bearing and not belt and braces.
 *
 * Everywhere outside the ramps and the gap this evaluates to exactly 1, which
 * is what makes it a numerical no-op on the untouched remainder of the bed.
 */
function gainEnvelope(windows, ramp) {
  if (!windows.length) return null;
  const terms = windows.map(({ s, e }) => {
    const d0 = Math.max(0, s - ramp).toFixed(6);   // start of the down ramp
    const u1 = (e + ramp).toFixed(6);              // end of the up ramp
    return `max(0,min(1,min((t-${d0})/${ramp},(${u1}-t)/${ramp})))`;
  });
  return `max(0,1-(${terms.join('+')}))`;
}

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
  if (isPrivateHost(parsed.hostname)) {
    throw new BadJob(`${label}: refuses a private or loopback address (${parsed.hostname})`);
  }
  return u;
}

/**
 * A scheme check says nothing about the destination. Without this, a caller
 * holding the token turns http_download into a reader of the render box's own
 * private network, and read_text hands the result straight back. Measured
 * against a local service on 127.0.0.1: 53 bytes of a fake credential came back
 * through read_text before this guard existed.
 *
 * Name-based SSRF through DNS is NOT closed by this and cannot be closed here;
 * it needs resolution-time pinning in the agent. Stated rather than implied.
 */
function isPrivateHost(h) {
  const host = String(h || '').toLowerCase().replace(/^\[|\]$/g, '');
  if (!host) return true;
  if (host === 'localhost' || host.endsWith('.localhost') || host.endsWith('.internal')) return true;
  if (host === '::1' || host === '::' || host.startsWith('fe80:') ||
      host.startsWith('fc') || host.startsWith('fd')) return true;
  const m = /^(\d{1,3})\.(\d{1,3})\.(\d{1,3})\.(\d{1,3})$/.exec(host);
  if (!m) return false;                       // a name; see the caveat above
  const [a, b] = [Number(m[1]), Number(m[2])];
  if ([a, b, Number(m[3]), Number(m[4])].some(n => n > 255)) return true;
  return a === 0 || a === 10 || a === 127 ||
         (a === 169 && b === 254) ||          // link local, incl. cloud metadata
         (a === 172 && b >= 16 && b <= 31) ||
         (a === 192 && b === 168) ||
         (a === 100 && b >= 64 && b <= 127) || // carrier grade NAT
         a >= 224;                             // multicast and reserved
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
const QUIET = ['-nostdin', '-hide_banner', '-loglevel', 'error'];
const MEASURE = ['-nostdin', '-hide_banner', '-nostats'];

// --- jobs ------------------------------------------------------------------
// Each: { build(params) -> {bin, argv, capture?, parse?} }
//   capture: 'stdout' | 'stderr' | 'both'   (default 'both')
//   parse:   (stdout, stderr) -> result object

const JOBS = {

  tsws_repair: {
    build(p) { return require('./tsws-repair.js').build(p, { safePath, getRoot }); },
  },

  /** ffprobe duration. Replaces `Probe Duration` and `Probe Source Layer`. */
  probe: {
    build(p) {
      const f = existingPath(p.path, 'path');
      return {
        bin: FP,
        argv: ['-v','error','-show_entries',
               'format=duration:stream=codec_type,width,height,r_frame_rate,color_transfer,pix_fmt',
               '-of','json', f],
        parse: (out) => {
          const j = JSON.parse(out || '{}');
          const st = (j.streams || [])[0] || {};
          const [n, d] = String(st.r_frame_rate || '0/1').split('/');
          // color_transfer is how a caller tells an iPhone HDR take (HLG reads
          // arib-std-b67, PQ reads smpte2084) from SDR before take_patch, which
          // needs to be told. Added 2026-10-15 with the Voice Lab jobs. Read
          // from the first VIDEO stream: the fields above keep reading stream 0
          // exactly as they always have, for the TSWS callers.
          const vs = (j.streams || []).find(x => x.codec_type === 'video') || {};
          const tr = vs.color_transfer ?? null;
          return {
            duration: Number(j.format?.duration ?? 0),
            width: st.width ?? null, height: st.height ?? null,
            fps: Number(d) ? Number(n) / Number(d) : null,
            pix_fmt: vs.pix_fmt ?? null,
            color_transfer: tr,
            hdr: tr === 'arib-std-b67' || tr === 'smpte2084',
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
   * The guard envelope matters more than the sidechain does. Sidechain RELEASE
   * makes the bed swell back up exactly where nothing should be, inside the
   * protected silence. The envelope holds it down through those windows and,
   * unlike the afade pair it replaced, lets it back up afterwards.
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
      const windows = guards.map((g, idx) => {
        const s = num(g.start, `guards[${idx}].start`, { min: 0, max: 86400 });
        const e = num(g.end,   `guards[${idx}].end`,   { min: 0, max: 86400 });
        if (e <= s) throw new BadJob(`guards[${idx}]: end must exceed start`);
        return { s, e };
      }).sort((a, b) => a.s - b.s);
      // Disjoint windows are what keeps the summed envelope inside [0, 1].
      for (let i = 1; i < windows.length; i++) {
        if (windows[i].s < windows[i - 1].e) {
          throw new BadJob(`guards: windows overlap (${windows[i - 1].e} > ${windows[i].s})`);
        }
      }
      const env = gainEnvelope(windows, ramp);
      const bedChain = env
        ? `[1:a]volume=eval=frame:volume='${env}'[bedg]`
        : `[1:a]anull[bedg]`;

      // amix=duration=first does NOT produce the first input's length. Measured
      // on EP01: a dialogue stem of 880.906757s came out at 880.849000s, 58 ms
      // short, leaving the last frame and a half with no audio. duration=longest
      // returned the identical value, so it is not a duration= problem. The mix
      // has to be pinned: apad to run past the end, then -t to cut it exactly.
      // apad without -t never terminates, so the pin is all-or-nothing and the
      // caller must supply the planned length to get it.
      const pinned  = p.duration !== undefined;
      const planned = pinned ? num(p.duration, 'duration', { min: 0.001, max: 86400 }) : null;

      const mixTail = pinned ? '[mixraw];[mixraw]apad[mix]' : '[mix]';
      const filter =
        `[0:a]asplit=2[nar][key];` +
        bedChain + `;` +
        `[bedg][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400:makeup=1[duck];` +
        `[nar][duck]amix=inputs=2:duration=first:dropout_transition=0:weights=1 ${gain}` + mixTail;

      const argv = ['-y', ...QUIET, '-i', nar, '-i', bed, '-filter_complex', filter,
                    '-map', '[mix]', '-ar', '48000',
                    // loudnorm_apply two jobs up already takes a codec; this one
                    // did not, so pcm_s24le was forced into whatever container
                    // the output name implied. PCM does not mux into FLAC.
                    '-c:a', oneOf(p.codec ?? 'pcm_s24le', 'codec',
                                  ['pcm_s16le','pcm_s24le','pcm_f32le','aac','flac'])];
      if (pinned) argv.push('-t', planned.toFixed(6));
      argv.push(out);

      return {
        bin: FF,
        argv,
        parse: () => ({
          output: path.relative(WORK_ROOT, out),
          guards: windows.length,
          // pinned:false means the 58 ms short-mix defect is still live on this
          // call. Visible in the result rather than silent.
          pinned,
          planned_duration: planned,
        }),
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

      // Normalisation target. Every shot is scaled and padded to exactly this
      // geometry, SAR and rate before it reaches xfade.
      const W   = num(p.width  ?? 3840, 'width',  { min: 16, max: 8192, int: true });
      const H   = num(p.height ?? 2160, 'height', { min: 16, max: 8192, int: true });
      const fps = num(p.fps    ?? 24,   'fps',    { min: 1,  max: 240 });

      const inputs = [];
      const trims = [];
      // The duration each shot ACTUALLY emits, which for a still is quantised to
      // whole frames. The offsets and expected_duration are both accumulated
      // from these rather than from the requested durations: a still emits
      // round(d*fps)/fps, so on a 37 still manifest with durations that are not
      // frame aligned the requested and emitted timelines drift apart, measured
      // at up to 0.130s, which is 3.1 frames at 24fps. An xfade offset that
      // drifts past the end of its first input is a broken join, not a rounding
      // nit.
      const emitted = [];
      let offset = 0;
      let stills = 0;
      let clips  = 0;
      shots.forEach((s, i) => {
        const f  = existingPath(s.path, `shots[${i}].path`);
        const IN = num(s.in ?? 0, `shots[${i}].in`, { min: 0, max: 86400 });
        const OUT= num(s.out, `shots[${i}].out`, { min: 0, max: 86400 });
        if (OUT <= IN) throw new BadJob(`shots[${i}]: out must exceed in`);
        if (i < shots.length - 1 && (OUT - IN) <= xf) {
          throw new BadJob(`shots[${i}]: shorter than the crossfade (${(OUT-IN).toFixed(2)}s <= ${xf}s)`);
        }
        const d = OUT - IN;
        inputs.push('-i', f);

        // Declaration beats inference: an explicit shots[i].still always wins,
        // and the extension is consulted only when nothing was declared.
        const still = s.still === undefined ? isStill(f) : !!s.still;
        if (still) {
          // The image demuxer emits exactly ONE frame, so the old
          // trim=start=0:end=6 kept exactly that one frame. 37 of 37 EP01 shots
          // are stills, which is how a 14-minute episode rendered as a
          // 1.5-second slideshow and the fault looked like ffmpeg's.
          //
          // Decode once, normalise that single frame, then hold it with the
          // loop filter. `-loop 1` also works and is what v1 did, but it
          // re-reads and re-decodes the file for EVERY output frame: a 63s shot
          // decodes a 4K JPEG 1,512 times. Measured on 2 cores, the picture
          // stage went 62.04s -> 6.26s for a bit-identical result (PSNR inf).
          const F = Math.round(d * fps);
          if (F < 1) throw new BadJob(`shots[${i}]: still is shorter than one frame at ${fps}fps`);
          stills++;
          emitted.push(F / fps);
          trims.push(`[${i}:v]${normalizeChain(W, H)},` +
                     `loop=loop=${F - 1}:size=1:start=0,setpts=N/${fps}/TB,fps=${fps}[v${i}]`);
        } else {
          clips++;
          // A trimmed clip is exact in source time. What fps= then emits depends
          // on the source rate and cannot be known without probing, so this is
          // the requested duration and is reported as such.
          emitted.push(d);
          trims.push(`[${i}:v]trim=start=${IN.toFixed(6)}:end=${OUT.toFixed(6)},setpts=PTS-STARTPTS,` +
                     `${normalizeChain(W, H)},fps=${fps}[v${i}]`);
        }
      });

      const parts = [...trims];
      let last = 'v0';
      for (let k = 1; k < shots.length; k++) {
        offset += emitted[k - 1] - xf;
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
        // Returned so the assembly can be CHECKED against the manifest rather
        // than trusted. expected_duration x fps should equal the frame count
        // ffprobe reports on the output.
        parse: () => ({
          output: path.relative(WORK_ROOT, out),
          shots: shots.length,
          stills,
          clips,
          fps,
          normalized_to: `${W}x${H}`,
          // Exact when every shot is a still, which is the EP01 case (37 of 37).
          // With clips in the mix it is the requested length; only ffprobe on the
          // output settles that, which is why the runbook asks for a frame count
          // rather than trusting this number.
          expected_duration: Number((emitted.reduce((a, b) => a + b, 0)
                                     - xf * (shots.length - 1)).toFixed(6)),
          exact: clips === 0,
        }),
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

        // Phase 2: ffmpeg assembly, same as render_mark but inline.
        // execFileSync here blocked the event loop for the whole ProRes encode,
        // so the server answered nothing, including the polls the caller uses to
        // watch this very job. Async, so only this job waits.
        const { execFile } = require('child_process');
        fs.mkdirSync(path.dirname(out), { recursive: true });
        await new Promise((resolve, reject) => {
          execFile(FF, [
            '-y', ...QUIET, '-framerate', String(fps),
            '-i', path.join(framesDir, 'f_%06d.png'),
            '-c:v', 'prores_ks', '-profile:v', '4444',
            '-pix_fmt', 'yuva444p10le', out,
          ], { cwd: WORK_ROOT, env: { PATH: process.env.PATH, LANG: 'C' },
               maxBuffer: 32 * 1024 * 1024 },
          (err, _o, errOut) => err
            ? reject(new Error(String(errOut || err.message).trim().split('\n').slice(-8).join('\n')))
            : resolve());
        });

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
   * The presenter build for TQO and NCO Forge (added 2026-09-15).
   *
   * A HeyGen avatar render is the BASE TRACK: full frame, the whole episode,
   * carrying the ElevenLabs narration HeyGen was handed. Pexels cutaways are
   * laid over it full frame inside planned windows, captions are burned in
   * from an SRT, and the music bed is ducked under the narration with the same
   * sidechain chain duck_mix uses. One ffmpeg pass, one encode generation.
   *
   * Timing model: every cutaway window is on the EPISODE timeline, never the
   * clip's. cutaways[k] = { path, start, end, in? }. The clip is trimmed from
   * `in` for (end - start) seconds. A clip shorter than its window holds its
   * last frame (tpad clone) rather than leaving a hole, and the overlay is
   * delayed to `start` with setpts. Before the cutaway's first frame the
   * overlay filter has no second frame and passes the base through, and
   * eof_action=pass does the same after its last one. That is measured, not
   * assumed: the acceptance step in DEPLOY.md samples a pixel before, inside
   * and after a window.
   *
   * Windows must be disjoint. Two cutaways over the same second is a planning
   * error, not a creative choice, and refusing it at submit is cheaper than a
   * render that silently shows only the later one.
   *
   * The narration used as the sidechain KEY and as the voice in the mix is the
   * avatar's own audio stream unless `narration` names a separate file. HeyGen
   * re-encodes what it is given, so a caller who wants the untouched
   * ElevenLabs file in the mix passes it here.
   *
   * No guards (duck_mix's protected-silence envelope) in this first cut. A
   * teaching episode has no protected silence the way a TSWS episode does.
   *
   * params: { avatar, output, cutaways?: [{path, start, end, in?, full?}],
   *           captions?, caption_style?, bed?, bed_gain?, narration?, duration?,
   *           width?, height?, fps?, fade?, crf?, preset?,
   *           layout?: 'full' | 'stacked', plate_color?, emphasis?: [{start, end}] }
   */
  presenter_composite: {
    build(p) {
      const avatar = existingPath(p.avatar, 'avatar');
      const out = ensureDir(safePath(p.output, 'output'));
      const W   = num(p.width  ?? 1920, 'width',  { min: 16, max: 8192, int: true });
      const H   = num(p.height ?? 1080, 'height', { min: 16, max: 8192, int: true });
      // 25, not 24: HeyGen renders every avatar at 25 fps and a base track
      // resampled to another rate judders on every held frame.
      const fps = num(p.fps ?? 25, 'fps', { min: 1, max: 120 });
      const xf  = num(p.fade ?? 0.3, 'fade', { min: 0, max: 5 });
      const gain = num(p.bed_gain ?? 0.35, 'bed_gain', { min: 0, max: 2 });
      const pinned  = p.duration !== undefined;
      const planned = pinned ? num(p.duration, 'duration', { min: 0.001, max: 86400 }) : null;

      // layout 'full' is the long-form presenter: the avatar fills the frame and
      // a cutaway replaces it inside its window. layout 'stacked' is the Anchor
      // Desk Short from the AAA flagship canon (stacked-short-format.md): a
      // 9:16 canvas, the payload zone in the top 65 percent, the presenter chest
      // up in the bottom 35 percent, captions in the band between them, and the
      // three states the canon insists on alternating: split (the default),
      // full-frame head (`emphasis` windows) and full-frame payload (a cutaway
      // with `full: true`). Zone edges follow the spec's 1250 px split on a
      // 1080 x 1920 canvas and scale with the canvas when a caller changes it.
      //
      // `split` moves that edge: the payload zone's share of the canvas height.
      // Tee ruled 0.5 for the native Shorts on 2026-10-31, matching the
      // Vaibhav Sisinty reference he sent (proof top half, presenter bottom
      // half). Absent, the edge stays at 1250/1920, byte for byte the graph it
      // was, so every existing caller renders as before.
      const layout = oneOf(p.layout ?? 'full', 'layout', ['full', 'stacked']);
      const stacked = layout === 'stacked';
      if (stacked && !(H > W)) throw new BadJob(`layout stacked needs a portrait canvas (got ${W}x${H})`);
      if (p.split !== undefined && !stacked) throw new BadJob('split: only meaningful with layout stacked');
      const split = p.split === undefined ? null : num(p.split, 'split', { min: 0.3, max: 0.75 });
      const splitY = stacked ? Math.round(split === null ? H * 1250 / 1920 : H * split) : 0;   // top of the presenter zone
      const headH  = stacked ? H - splitY : H;
      const plate  = String(p.plate_color ?? '#0A1628');
      if (!/^#[0-9A-Fa-f]{6}$/.test(plate)) throw new BadJob('plate_color: must be #RRGGBB');
      // A field that is present and not an array is refused, never defaulted:
      // an n8n expression that hands over a JSON string would otherwise render
      // a cutaway-free episode that returns ok (critic finding, 2026-09-15).
      if (p.emphasis !== undefined && !Array.isArray(p.emphasis)) throw new BadJob('emphasis: must be an array of {start, end}');
      const emph = Array.isArray(p.emphasis) ? p.emphasis : [];
      if (emph.length > 64) throw new BadJob('emphasis: too many (max 64)');
      if (emph.length && !stacked) throw new BadJob('emphasis: only meaningful with layout stacked');
      const emphasis = emph.map((g, k) => {
        const s = num(g && g.start, `emphasis[${k}].start`, { min: 0, max: 86400 });
        const e = num(g && g.end,   `emphasis[${k}].end`,   { min: 0, max: 86400 });
        if (e <= s) throw new BadJob(`emphasis[${k}]: end must exceed start`);
        if (pinned && e > planned) throw new BadJob(`emphasis[${k}]: ends at ${e}s, past the planned ${planned}s`);
        return { s, e };
      }).sort((a, b) => a.s - b.s);
      for (let i = 1; i < emphasis.length; i++) {
        if (emphasis[i].s < emphasis[i - 1].e) throw new BadJob(`emphasis: windows overlap (${emphasis[i - 1].e} > ${emphasis[i].s})`);
      }

      if (p.cutaways !== undefined && !Array.isArray(p.cutaways)) throw new BadJob('cutaways: must be an array of {path, start, end}');
      const cuts = Array.isArray(p.cutaways) ? p.cutaways : [];
      if (cuts.length > 64) throw new BadJob('cutaways: too many (max 64)');
      const windows = cuts.map((c, k) => {
        if (!c || typeof c !== 'object') throw new BadJob(`cutaways[${k}]: not an object`);
        const f  = existingPath(c.path, `cutaways[${k}].path`);
        const s  = num(c.start, `cutaways[${k}].start`, { min: 0, max: 86400 });
        const e  = num(c.end,   `cutaways[${k}].end`,   { min: 0, max: 86400 });
        const IN = num(c.in ?? 0, `cutaways[${k}].in`,  { min: 0, max: 86400 });
        if (e <= s) throw new BadJob(`cutaways[${k}]: end must exceed start`);
        if (xf > 0 && (e - s) < 2 * xf) {
          throw new BadJob(`cutaways[${k}]: shorter than two fades (${(e - s).toFixed(2)}s < ${(2 * xf).toFixed(2)}s)`);
        }
        if (pinned && e > planned) {
          throw new BadJob(`cutaways[${k}]: ends at ${e}s, past the planned ${planned}s`);
        }
        // In the full layout every cutaway is full frame; in the stacked layout
        // it sits in the payload zone unless it asks for the whole canvas.
        if (c.full !== undefined && typeof c.full !== 'boolean') throw new BadJob(`cutaways[${k}].full: must be true or false, not ${JSON.stringify(c.full)}`);
        const full = stacked ? c.full === true : true;
        return { f, s, e, IN, full };
      }).sort((a, b) => a.s - b.s);
      for (let i = 1; i < windows.length; i++) {
        if (windows[i].s < windows[i - 1].e) {
          throw new BadJob(`cutaways: windows overlap (${windows[i - 1].e} > ${windows[i].s})`);
        }
      }

      // must_cover (added 2026-10-15 with Voice Lab): windows where the voice is
      // the clone and the base track is a held frame. Each must sit wholly
      // inside ONE scheduled cutaway, and an opaque black plate is laid under
      // every window, so wherever the cutaway is still fading in or out, or has
      // no frames at all, what shows through is black, never the presenter. In
      // the stacked layout only a full-frame cutaway hides the presenter, and
      // an emphasis window would put the head back on top, so both are checked.
      // Refused at submit: a clone line over Tee's own face is the failure this
      // exists to make impossible, and it would otherwise pass every other gate.
      //
      // A base track made by take_patch carries its windows INSIDE the file,
      // in its container metadata, and those are enforced whether or not the
      // caller sends must_cover. A critic omitted must_cover, misspelled it and
      // passed the wrong field, and each rendered the held face under the clone
      // (N3). The first fix kept the windows in a sidecar file beside the base
      // track, and a third critic copied the base with fs_ops and got 46 face
      // frames: a copy or a symlink lost the sidecar. The tag goes wherever the
      // file goes. Read with ffprobe at submit; a base whose tags cannot be read
      // is refused rather than rendered unchecked.
      if (p.must_cover !== undefined && !Array.isArray(p.must_cover)) throw new BadJob('must_cover: must be an array of {start, end}');
      const mustCover = Array.isArray(p.must_cover) ? p.must_cover.slice() : [];
      const carried = readVoiceLabWindows(avatar);
      if (carried) carried.forEach(w => mustCover.push({ start: w && w.start, end: w && w.end }));
      // The documented call sends take_patch's patch_windows as must_cover AND
      // the file carries them, so the same window arrives twice. Identical
      // windows count once (critic, round three: 33 patches were refused as 66).
      const seenWin = new Set();
      const uniqueCover = mustCover.filter((m) => {
        if (!m || typeof m !== 'object') return true;
        const key = `${Number(m.start).toFixed(6)}-${Number(m.end).toFixed(6)}`;
        if (seenWin.has(key)) return false;
        seenWin.add(key);
        return true;
      });
      if (uniqueCover.length > 64) throw new BadJob('must_cover: too many (max 64)');
      const covered = uniqueCover.map((m, k) => {
        if (!m || typeof m !== 'object') throw new BadJob(`must_cover[${k}]: not an object`);
        const s = num(m.start, `must_cover[${k}].start`, { min: 0, max: 86400 });
        const e = num(m.end,   `must_cover[${k}].end`,   { min: 0, max: 86400 });
        if (e <= s) throw new BadJob(`must_cover[${k}]: end must exceed start`);
        // Inside the cutaway's SCHEDULE, fades included: the plate makes a
        // fade read as black. The first cut required the opaque middle, and so
        // refused every episode whose first or last line was patched (N4).
        const hides = windows.some(w => w.full && w.s <= s && e <= w.e);
        if (!hides) {
          throw new BadJob(`must_cover[${k}]: ${s}s to ${e}s is not inside one scheduled` +
                           (stacked ? ' full-frame' : '') + ' cutaway; the clone voice would play over a black plate with nothing on it');
        }
        // An emphasis window lays the presenter OVER the plate, so it must stay
        // a full output frame clear of a covered window on both sides. Touching
        // was refused already; a third critic ended one 0.5 ms short and got a
        // frame of face across a 30 to 25 fps conversion.
        const gap = 1 / fps;
        const back = emphasis.find(g => g.s < e + gap && s - gap < g.e);
        if (back) throw new BadJob(`must_cover[${k}]: emphasis ${back.s}s to ${back.e}s is within a frame of it, which puts the presenter back on top`);
        return { s, e };
      });

      // Inputs: 0 is the avatar, then one per cutaway in window order, then
      // the bed (looped, so a 90 second track covers a 12 minute episode), then
      // the narration override. The indices below follow that order exactly.
      const inputs = ['-i', avatar];
      const parts = [];
      // Fill a zone edge to edge: scale so the shorter side matches, then crop
      // the centre. The chest-up presenter and a full-frame payload both want
      // this; letterboxing (normalizeChain) is for the payload zone, where a
      // 16:9 clip is shown whole.
      const fillChain = (w, h) => `scale=${w}:${h}:force_original_aspect_ratio=increase:flags=lanczos,crop=${w}:${h},setsar=1,format=yuv420p`;
      if (stacked) {
        // The presenter, chest up, in the bottom zone over a plate the height of
        // the canvas. shortest=1 ends the plate with the presenter, so a pinned
        // render still pads on -t and an unpinned one ends where the avatar does.
        parts.push(`[0:v]split=2[a_desk][a_full]`);
        parts.push(`[a_desk]${fillChain(W, headH)},fps=${fps},setpts=PTS-STARTPTS[head]`);
        parts.push(`color=c=${plate}:s=${W}x${H}:r=${fps}[plate]`);
        parts.push(`[plate][head]overlay=0:${splitY}:shortest=1[base]`);
      } else {
        parts.push(`[0:v]${normalizeChain(W, H)},fps=${fps},setpts=PTS-STARTPTS[base]`);
      }
      // An opaque plate under every must_cover window, laid before any cutaway.
      // The window check above proves a cutaway is SCHEDULED there; it cannot
      // prove the clip has frames to show (a cutaway with `in` past its own end
      // rendered 58 frames of the presenter in the critic's run). With the
      // plate, an empty cutaway shows black, never the face. It reaches one
      // output frame past each edge: the base track and this render rarely
      // share a frame grid, and a window edge between two frames left one frame
      // of held face showing (critic N2, up to 33 ms).
      let baseLbl = 'base';
      if (covered.length) {
        const en = covered.map(c => `between(t,${Math.max(0, c.s - 1 / fps).toFixed(6)},${(c.e + 1 / fps).toFixed(6)})`).join('+');
        parts.push(`[base]drawbox=x=0:y=0:w=iw:h=ih:color=black:t=fill:enable='${en}'[baseplate]`);
        baseLbl = 'baseplate';
      }
      windows.forEach((w, i) => {
        inputs.push('-i', w.f);
        const len = w.e - w.s;
        const fades = xf > 0
          ? `,fade=t=in:st=0:d=${xf}:alpha=1,fade=t=out:st=${(len - xf).toFixed(6)}:d=${xf}:alpha=1`
          : '';
        // full frame fills the canvas; the payload zone shows the clip whole.
        const geometry = w.full ? (stacked ? fillChain(W, H) : normalizeChain(W, H)) : normalizeChain(W, splitY);
        parts.push(
          `[${i + 1}:v]trim=start=${w.IN.toFixed(6)}:end=${(w.IN + len).toFixed(6)},setpts=PTS-STARTPTS,` +
          `${geometry},fps=${fps},` +
          `tpad=stop_mode=clone:stop_duration=${len.toFixed(6)},trim=end=${len.toFixed(6)},` +
          `format=yuva420p${fades},setpts=PTS+${w.s.toFixed(6)}/TB[c${i}]`);
      });
      let last = baseLbl;
      windows.forEach((w, i) => {
        const lbl = `v${i + 1}`;
        parts.push(`[${last}][c${i}]overlay=0:0:eof_action=pass:enable='between(t,${w.s.toFixed(6)},${w.e.toFixed(6)})'[${lbl}]`);
        last = lbl;
      });
      if (stacked && emphasis.length) {
        // The emphasis line: the presenter takes the whole canvas. Laid last so
        // it wins over any cutaway that shares the second.
        const en = emphasis.map(g => `between(t,${g.s.toFixed(6)},${g.e.toFixed(6)})`).join('+');
        parts.push(`[a_full]${fillChain(W, H)},fps=${fps},setpts=PTS-STARTPTS[headfull]`);
        parts.push(`[${last}][headfull]overlay=0:0:eof_action=pass:enable='${en}'[vemph]`);
        last = 'vemph';
      } else if (stacked) {
        parts.push(`[a_full]nullsink`);
      }

      let captions = null;
      if (p.captions !== undefined && p.captions !== null && p.captions !== '') {
        captions = existingPath(p.captions, 'captions');
        // The SRT path lives INSIDE the filter string, the one place argv
        // cannot protect. A colon, a quote, a backslash or a comma there
        // changes the graph. Refuse rather than escape: the caller renames.
        if (!/^[A-Za-z0-9_./-]+$/.test(captions)) {
          throw new BadJob('captions: the resolved path carries a character the subtitles filter cannot take verbatim; rename it');
        }
        // libass sizes an SRT against a 384 x 288 script and scales to the
        // canvas, so FontSize and MarginV here are in those units, not pixels
        // (one unit is 6.67 px on a 1920 high canvas). Stacked: the caption
        // sits on the seam between the zones, inside the spec's band (y 1150 to
        // 1630 of 1920) and above the presenter's face, not across it. MarginV
        // 92 puts the baseline near y 1300. The first cut used 45 and the
        // 2026-09-15 acceptance frame showed the line across the presenter's
        // chest, which is why this is measured rather than derived.
        // With a `split`, the same placement is carried to the new seam: 92
        // units is the measured bottom of the line 56 px (of 1920) below the
        // 1250 seam, and 288 * (1 - seam / H) - 8.4 reproduces it (92.1), so
        // the formula moves that measured offset rather than inventing one.
        const marginV = split === null ? 92 : Math.round(288 * (1 - splitY / H) - 8.4);
        const style = String(p.caption_style ?? (stacked
          ? `FontSize=12,Bold=1,Outline=2,Shadow=0,MarginV=${marginV}`
          : 'FontSize=22,Outline=2,Shadow=0,MarginV=60'));
        if (!/^[A-Za-z0-9=,._&# -]+$/.test(style)) {
          throw new BadJob('caption_style: only letters, digits, space and = , . _ & # - are accepted');
        }
        parts.push(`[${last}]subtitles=filename=${captions}:force_style='${style}'[vout]`);
      } else {
        parts.push(`[${last}]null[vout]`);
      }

      let bed = null;
      let narration = null;
      let idx = windows.length + 1;
      let bedIdx = null;
      let narIdx = null;
      if (p.bed !== undefined && p.bed !== null && p.bed !== '') {
        bed = existingPath(p.bed, 'bed');
        bedIdx = idx++;
        inputs.push('-stream_loop', '-1', '-i', bed);
      }
      if (p.narration !== undefined && p.narration !== null && p.narration !== '') {
        narration = existingPath(p.narration, 'narration');
        narIdx = idx++;
        inputs.push('-i', narration);
      }
      const narSrc = narIdx === null ? '[0:a]' : `[${narIdx}:a]`;
      // Same pin as duck_mix: amix=duration=first came out 58 ms short on EP01,
      // so the mix is padded and cut to the planned length when one is given.
      const mixTail = pinned ? '[mixraw];[mixraw]apad[mix]' : '[mix]';
      if (bed) {
        parts.push(
          `${narSrc}aresample=48000,asplit=2[nar][key];` +
          `[${bedIdx}:a]aresample=48000[bedg];` +
          `[bedg][key]sidechaincompress=threshold=0.03:ratio=8:attack=20:release=400:makeup=1[duck];` +
          `[nar][duck]amix=inputs=2:duration=first:dropout_transition=0:weights=1 ${gain}` + mixTail);
      } else {
        parts.push(`${narSrc}aresample=48000` + (pinned ? ',apad[mix]' : '[mix]'));
      }

      const argv = ['-y', ...QUIET, ...inputs, '-filter_complex', parts.join(';'),
                    '-map', '[vout]', '-map', '[mix]', '-r', String(fps),
                    '-c:v', 'libx264', '-crf', String(num(p.crf ?? 18, 'crf', { min: 0, max: 51, int: true })),
                    '-preset', oneOf(p.preset ?? 'medium', 'preset', PRESETS),
                    '-pix_fmt', 'yuv420p', '-c:a', 'aac', '-b:a', '192k',
                    // The master is the delivered file. The clone windows have
                    // done their job by now, under the cutaways, and Tee ruled
                    // on 2026-10-16 that the list of where his clone speaks
                    // does not travel inside it.
                    '-metadata', 'comment=',
                    '-movflags', '+faststart'];
      if (pinned) argv.push('-t', planned.toFixed(6));
      argv.push(out);

      return {
        bin: FF,
        argv,
        parse: () => ({
          output: path.relative(WORK_ROOT, out),
          cutaways: windows.length,
          captions: captions !== null,
          bed: bed !== null,
          narration: narration === null ? 'avatar audio' : 'separate file',
          pinned,
          planned_duration: planned,
          fps,
          normalized_to: `${W}x${H}`,
          layout,
          split_y: stacked ? splitY : null,
          emphasis: emphasis.length,
          full_cutaways: windows.filter(w => w.full).length,
          must_cover: covered.length,
        }),
      };
    },
  },

  /**
   * Voice Lab, step two (added 2026-10-15). The real take, spliced.
   *
   * Input is align_script's edl with each patch line's clone audio filled in.
   * A take item keeps that stretch of the iPhone take, picture and sound. A
   * patch item plays the clone reading over the take's nearest frame, HELD,
   * because a held frame under a voice is honest about being a cut and moving
   * lips under someone else's audio is not. presenter_composite then lays a
   * cutaway over every patch window and refuses to render if one is bare
   * (`must_cover`), so the held frame is never what a viewer sees either.
   *
   * ONE SEGMENT AT A TIME. The first cut put every item into one ffmpeg run as
   * its own seeked input, and the memory of that was measured, not guessed:
   * 64 items on a 40 s 4K HEVC HLG take, 96 inputs, peaked at 13.6 GiB and
   * died. The VPS has 7.8 GiB. Every input is a live decoder, about 140 MB
   * each at 4K, whether or not the concat has reached it. So this job is
   * native: it renders each item to its own short intermediate, one or two
   * inputs per ffmpeg run, then joins them with the concat demuxer as a
   * stream copy. Picture is encoded once, in the segments; sound is PCM in the
   * segments and encoded once, at the join.
   *
   * Durations are pinned at every step and every segment is a whole number of
   * frames, so the windows returned here are exact, which is what lets
   * must_cover check them at submit rather than by eye.
   *
   * A patch's `duration` must be the clone file's real length, from the probe
   * job. Shorter than the file cuts the reading off; that is stated here rather
   * than guessed around, and the result echoes every duration it used.
   *
   * `hdr` has no default on purpose. An iPhone 15 Pro shoots HLG by default, and
   * a 10-bit HLG take squeezed to yuv420p without a tonemap comes out grey and
   * washed. The probe job reports `hdr`; the caller passes 'tonemap' or 'sdr'.
   *
   * `take_duration` is required, from probe. The first cut never checked a span
   * against the file, and a critic rendered a take span ending 0.05 s past the
   * end that left the patch after it with zero frames and returned ok. Take
   * spans must also run in time order without overlapping: an edl of 6-8, 1-3,
   * 2-4 repeated a second of speech and returned ok.
   *
   * params: { take, take_duration, output, hdr: 'sdr'|'tonemap',
   *           edl: [{kind:'take', start, end} | {kind:'patch', audio, duration}],
   *           narration_output?, fps?, xfade?, crf?, preset?, width?, height? }
   *
   * width and height scale every segment to the presenter canvas (with the
   * same letterbox rule as everywhere else) instead of carrying the iPhone's
   * 4K through. presenter_composite lands on 1920x1080 regardless, and the
   * 4K segments cost 214 s for 24.5 s of picture at preset ultrafast in the
   * 2026-10-15 measurement, which on the 2 core box is hours per episode.
   */
  take_patch: {
    build(p) {
      const take = existingPath(p.take, 'take');
      const out  = safePath(p.output, 'output');
      // The segment list is a file ffmpeg parses, so the paths written into it
      // are held to the same rule as a caption path inside a filter graph.
      if (!/^[A-Za-z0-9_./-]+$/.test(out)) {
        throw new BadJob('output: the resolved path carries a character the concat list cannot take verbatim; rename it');
      }
      const hdr  = oneOf(p.hdr, 'hdr', ['sdr', 'tonemap']);
      if (p.take_duration === undefined) throw new BadJob('take_duration: required, from the probe job');
      const takeDur = num(p.take_duration, 'take_duration', { min: 0.001, max: 86400 });
      // A rate that divides 48 kHz, so every segment's sound is a whole number
      // of samples and the join cannot drift. 29.97 and 29 do not.
      const fps  = Number(oneOf(String(p.fps ?? 30), 'fps', ['24', '25', '30', '48', '50', '60']));
      const xf   = num(p.xfade ?? 0.02, 'xfade', { min: 0, max: 0.5 });
      const crf  = num(p.crf ?? 16, 'crf', { min: 0, max: 51, int: true });
      const preset = oneOf(p.preset ?? 'medium', 'preset', PRESETS);
      if ((p.width === undefined) !== (p.height === undefined)) throw new BadJob('width and height: send both or neither');
      const size = p.width === undefined ? null : {
        W: num(p.width,  'width',  { min: 16, max: 8192, int: true }),
        H: num(p.height, 'height', { min: 16, max: 8192, int: true }),
      };
      const narOut = (p.narration_output === undefined || p.narration_output === null || p.narration_output === '')
        ? null : safePath(p.narration_output, 'narration_output');
      if (!Array.isArray(p.edl)) throw new BadJob('edl: must be an array (align_script returns null on a re-record)');
      if (p.edl.length < 1) throw new BadJob('edl: need at least one item');
      if (p.edl.length > 400) throw new BadJob('edl: too many items (max 400)');
      // An output that is also an input is overwritten while it is read. The
      // single-run version had ffmpeg's own same-file guard; the join reads
      // only the concat list, so a critic pointed `output` at the take and the
      // take shrank from 107,343 bytes to 21,476 with the job returning ok.
      const partsDirAbs = `${out}.parts`;
      // Compared by REAL path: a third critic symlinked the take, pointed
      // output at the symlink's name, and the cleanup step deleted the take.
      const realOut = realish(out), realTake = realish(take), realNar = narOut === null ? null : realish(narOut);
      if (realOut === realTake) throw new BadJob('output: is the take itself, which the job would overwrite');
      if (realNar !== null && (realNar === realTake || realNar === realOut)) throw new BadJob('narration_output: collides with the take or the output');
      if (narOut !== null && (narOut.startsWith(partsDirAbs + path.sep) || realNar.startsWith(realish(partsDirAbs) + path.sep))) {
        throw new BadJob('narration_output: inside the working directory the job deletes');
      }
      // The output check reads the frame count an mp4 or mov records; an mkv
      // does not record one, and a critic's .mkv rendered in full and was then
      // refused. Refused up front instead.
      if (!/\.(mp4|mov)$/i.test(out)) throw new BadJob('output: must end .mp4 or .mov');

      // Every segment is a whole number of frames, on BOTH tracks. The first
      // cut trimmed audio to the second and video to the frame, so each splice
      // left the picture up to a frame longer than the sound: measured 13 ms on
      // the 2026-10-15 acceptance run, and it accumulates. A take rounds to the
      // nearest frame; a patch rounds UP, because rounding down cuts the
      // clone's last syllable and rounding up only adds silence.
      const minLen = 2 * xf + 1 / fps;
      const frames = (sec, up) => Math.max(1, up ? Math.ceil(sec * fps - 1e-6) : Math.round(sec * fps));
      let prevEnd = null;
      const items = p.edl.map((it, k) => {
        if (!it || typeof it !== 'object') throw new BadJob(`edl[${k}]: not an object`);
        const kind = oneOf(it.kind, `edl[${k}].kind`, ['take', 'patch']);
        if (kind === 'take') {
          const s = num(it.start, `edl[${k}].start`, { min: 0, max: 86400 });
          const e = num(it.end,   `edl[${k}].end`,   { min: 0, max: 86400 });
          if (e > takeDur + 1e-6) throw new BadJob(`edl[${k}]: ends at ${e}s, past the take's ${takeDur}s`);
          if (e - s < minLen - 1e-6) throw new BadJob(`edl[${k}]: ${(e - s).toFixed(3)}s is shorter than two crossfades and a frame`);
          if (prevEnd !== null && s < prevEnd - 1e-6) {
            throw new BadJob(`edl[${k}]: starts at ${s}s, before the previous take ends at ${prevEnd}s; take spans must be in time order and must not overlap`);
          }
          prevEnd = e;
          // Snap to whole frames, but never past the end of the file.
          let n = frames(e - s, false);
          if (s + n / fps > takeDur + 1e-6) n = Math.max(1, Math.floor((takeDur - s) * fps + 1e-6));
          const len = n / fps;
          return { kind, s, e: s + len, len, lines: it.lines };
        }
        const audio = existingPath(it.audio, `edl[${k}].audio`);
        if (realish(audio) === realOut || realish(audio) === realNar) throw new BadJob(`edl[${k}].audio: is also an output, which the job would overwrite`);
        const d = num(it.duration, `edl[${k}].duration`, { min: minLen, max: 600 });
        return { kind, audio, len: frames(d, true) / fps, source_len: d, lines: it.lines };
      });
      if (!items.some(it => it.kind === 'take')) {
        throw new BadJob('edl: no take item, so there is no frame of the presenter to hold');
      }
      // Rounding to the nearest frame can stretch a take up to half a frame
      // into the next one, which replays that sliver (13.3 ms, critic N11).
      // Where it would, round that take down instead.
      const takesOnly = items.filter(it => it.kind === 'take');
      for (let i = 0; i + 1 < takesOnly.length; i++) {
        const a = takesOnly[i], b = takesOnly[i + 1];
        if (a.s + a.len > b.s + 1e-9) {
          const n = Math.floor((b.s - a.s) * fps + 1e-6);
          if (n < 1) throw new BadJob(`edl: the take at ${a.s}s is under a frame long once snapped`);
          a.len = n / fps;
          a.e = a.s + a.len;
        }
      }

      // The frame a patch holds: two frames inside the end of the take before
      // it, or the first frame of the take after it when the patch opens.
      const holdAt = (k) => {
        for (let i = k - 1; i >= 0; i--) {
          if (items[i].kind === 'take') return Math.max(0, Math.min(items[i].e, takeDur) - 2 / fps);
        }
        for (let i = k + 1; i < items.length; i++) {
          if (items[i].kind === 'take') return items[i].s;
        }
        return 0;
      };

      // Downscale FIRST, still at the take's own bit depth, so the float
      // tonemap runs on a quarter of the pixels; then letterbox to the canvas.
      const picture = (size ? `scale=${size.W}:${size.H}:force_original_aspect_ratio=decrease:flags=lanczos,` : '') +
        (hdr === 'tonemap'
          ? 'zscale=t=linear:npl=100,format=gbrpf32le,zscale=p=bt709,tonemap=tonemap=hable:desat=0,' +
            'zscale=t=bt709:m=bt709:r=tv,format=yuv420p'
          : 'format=yuv420p') +
        (size ? `,${normalizeChain(size.W, size.H)}` : '');
      const mono = 'aformat=sample_fmts=fltp:sample_rates=48000:channel_layouts=mono';
      const fades = (len) => xf > 0
        ? `,afade=t=in:st=0:d=${xf}:curve=tri,afade=t=out:st=${(len - xf).toFixed(6)}:d=${xf}:curve=tri`
        : '';
      // Identical encoder settings in every segment, so the join can copy the
      // video rather than encode it a second time.
      const encode = (L) => ['-map', '[v]', '-map', '[a]', '-r', String(fps),
        '-c:v', 'libx264', '-crf', String(crf), '-preset', preset, '-pix_fmt', 'yuv420p',
        '-g', String(2 * fps), '-video_track_timescale', String(fps * 1000),
        '-c:a', 'pcm_s24le', '-ar', '48000', '-ac', '1', '-t', L];

      const partsDir = partsDirAbs;
      const segments = [];
      const windows = [];
      let t = 0;
      items.forEach((it, k) => {
        const L = it.len.toFixed(6);
        const seg = path.join(partsDir, `${String(k).padStart(3, '0')}.mov`);
        let argv;
        if (it.kind === 'take') {
          // No setpts before fps. After an input seek the clock is already zero
          // at the seek point, which is where the audio starts; resetting it to
          // the first decoded frame instead slid the picture up to a frame ahead
          // of the voice (+28.4 ms measured by the critic at a 1.001 s seek).
          // fps with start_time=0 lands each frame on the nearest slot of the
          // audio's own clock: -5.0, +9.4 and -10.6 ms against a -4.0 ms source.
          argv = ['-y', ...QUIET, '-ss', it.s.toFixed(6), '-t', L, '-i', take, '-filter_complex',
            `[0:v]fps=${fps}:start_time=0,${picture},setsar=1,` +
            `tpad=stop_mode=clone:stop_duration=1,trim=duration=${L},setpts=PTS-STARTPTS[v];` +
            `[0:a]asetpts=PTS-STARTPTS,${mono},apad,atrim=duration=${L}${fades(it.len)}[a]`,
            ...encode(L), seg];
        } else {
          // A two frame slice is enough to hold one; trim keeps the first.
          argv = ['-y', ...QUIET, '-ss', holdAt(k).toFixed(6), '-t', (2 / fps).toFixed(6), '-i', take,
            '-i', it.audio, '-filter_complex',
            `[0:v]setpts=PTS-STARTPTS,fps=${fps},${picture},setsar=1,trim=end_frame=1,` +
            `tpad=stop_mode=clone:stop_duration=${L},trim=duration=${L},setpts=PTS-STARTPTS[v];` +
            `[1:a]asetpts=PTS-STARTPTS,${mono},apad,atrim=duration=${L}${fades(it.len)}[a]`,
            ...encode(L), seg];
          // Rounded OUTWARD. toFixed alone put a window edge a hair past the
          // frame it belongs to, and the composite then showed that one frame
          // of held face under the clone (critic N2, 9 windows in 26).
          windows.push({
            item: k,
            lines: Array.isArray(it.lines) ? it.lines : null,
            start: Math.floor(t * 1e6 + 1e-6) / 1e6,
            end: Math.ceil((t + it.len) * 1e6 - 1e-6) / 1e6,
          });
        }
        segments.push({ bin: FF, argv, output: seg });
        t += it.len;
      });
      const total = t;
      // A window rounded up past the end of the file is clamped back to it.
      // The tagged duration rounds to nearest, so a patched LAST line ended a
      // microsecond past it and the composite refused one frame count in three
      // at 30 fps (critic, round four). Nothing plays past the end, so the
      // clamp cannot uncover a frame.
      windows.forEach((w) => { w.end = Math.min(w.end, +total.toFixed(6)); });
      const list = `${partsDir}/list.ffconcat`;
      // The windows ride inside the output's own metadata, where
      // presenter_composite reads them back, so a copy of the file keeps them.
      const tag = VOICE_LAB_TAG + JSON.stringify({ fps, duration: +total.toFixed(6), windows: windows.map(w => ({ start: w.start, end: w.end })) });
      const join = ['-y', ...QUIET, '-f', 'concat', '-safe', '0', '-i', list,
                    '-map', '0:v', '-map', '0:a', '-c:v', 'copy', '-c:a', 'aac', '-b:a', '320k',
                    '-metadata', `comment=${tag}`,
                    '-movflags', '+faststart', '-t', total.toFixed(6), out];
      if (narOut) join.push('-map', '0:a', '-c:a', 'pcm_s24le', '-t', total.toFixed(6), narOut);

      const result = () => ({
        output: path.relative(WORK_ROOT, out),
        narration_output: narOut === null ? null : path.relative(WORK_ROOT, narOut),
        duration: +total.toFixed(6),
        takes: items.filter(it => it.kind === 'take').length,
        patches: windows.length,
        // Feed these to presenter_composite as must_cover, unchanged.
        patch_windows: windows,
        // Frame-snapped lengths as rendered, then the clone files' own.
        patch_durations: items.filter(it => it.kind === 'patch').map(it => +it.len.toFixed(6)),
        patch_source_durations: items.filter(it => it.kind === 'patch').map(it => it.source_len),
        segments: segments.length,
        must_cover_carried_in_file: true,
        letterboxed,
        hdr,
        fps,
      });

      let letterboxed = null;

      const { execFile } = require('child_process');
      // Set when the job STARTS, not when it is submitted, so time spent
      // waiting in the queue is never charged against its run.
      let deadline = Infinity;
      let child = null;
      let aborted = false;
      const exec = (bin, argv) => new Promise((resolve, reject) => {
        if (aborted) return reject(new Error('aborted'));
        child = execFile(bin, argv, { cwd: WORK_ROOT, env: { PATH: process.env.PATH, LANG: 'C' },
                                      maxBuffer: 32 * 1024 * 1024,
                                      timeout: Math.max(1000, deadline - Date.now()), killSignal: 'SIGKILL' },
          (err, o, errOut) => { child = null; return err
            ? reject(new Error(String(errOut || err.message).trim().split('\n').slice(-8).join('\n')))
            : resolve(String(o)); });
      });
      const probeJson = async (f, entries) => JSON.parse(await exec(FP, ['-v', 'error', ...entries, '-of', 'json', f]));

      return {
        // Exposed so the builder tests can pin every argv without running ffmpeg.
        plan: { segments, join, list },
        result,
        // Called by server.js when JOB_TIMEOUT abandons this job. Without it the
        // abandoned job kept its ffmpeg running and the freed slot started the
        // next job beside it, the very memory risk segmenting exists to avoid
        // (critic N5).
        abort: () => { aborted = true; if (child) { try { child.kill('SIGKILL'); } catch (_) { /* gone */ } } },
        native: async () => {
          deadline = Date.now() + Number(process.env.JOB_TIMEOUT_MS || 6 * 3600 * 1000);
          // A failed run must not leave the last good run's files looking
          // current (critic N15), so they go first.
          for (const f of [out, narOut]) if (f) fs.rmSync(f, { force: true });
          fs.rmSync(partsDir, { recursive: true, force: true });

          // What the take and the clone files really are, read here rather than
          // trusted. take_duration is the container's length, and an iPhone's
          // sound can outlast its picture: a hold seeked past the last frame
          // rendered no picture at all, the join dropped the clone line, and the
          // job returned ok (critic N1).
          const tp = await probeJson(take, ['-select_streams', 'v:0', '-show_entries',
            'stream=duration,width,height:stream_tags=rotate:stream_side_data=rotation']);
          const vs = (tp.streams || [])[0] || {};
          // The PICTURE's own length, never the container's: an mkv records
          // none per stream, and falling back to the container let a span run
          // past the last frame with the picture frozen (critic, round three).
          const vidEnd = Number(vs.duration);
          if (!(vidEnd > 0)) throw new Error("take: the picture's own length is not in the file; remux it to .mov or .mp4 first");
          for (const it of items) {
            if (it.kind === 'take' && it.e > vidEnd + 0.5 / fps) {
              throw new Error(`take: a span ends at ${it.e.toFixed(3)}s but the picture ends at ${vidEnd.toFixed(3)}s`);
            }
          }
          for (const sg of segments) {
            const ss = Number(sg.argv[sg.argv.indexOf('-ss') + 1]);
            if (ss > vidEnd - 1 / fps + 1e-6) throw new Error(`take: a held frame at ${ss.toFixed(3)}s is past the last frame at ${vidEnd.toFixed(3)}s`);
          }
          for (const it of items) {
            if (it.kind !== 'patch') continue;
            const ap = await probeJson(it.audio, ['-show_entries', 'format=duration']);
            const real = Number(ap.format?.duration);
            if (real > it.source_len + 1 / fps) {
              throw new Error(`patch: ${path.relative(WORK_ROOT, it.audio)} is ${real.toFixed(3)}s but its duration says ${it.source_len}s; the end of the line would be cut`);
            }
          }
          if (size && vs.width && vs.height) {
            // An iPhone portrait take is stored landscape with a rotation flag,
            // which ffmpeg applies when it decodes.
            const rot = Math.abs(Number((vs.side_data_list || []).find(d => d.rotation !== undefined)?.rotation ?? vs.tags?.rotate ?? 0)) % 180;
            const [sw, sh] = rot === 90 ? [vs.height, vs.width] : [vs.width, vs.height];
            letterboxed = Math.abs(sw / sh - size.W / size.H) > 0.01
              ? { source: `${sw}x${sh}`, canvas: `${size.W}x${size.H}` } : false;
          }

          fs.mkdirSync(partsDir, { recursive: true });
          ensureDir(out);
          if (narOut) ensureDir(narOut);
          for (const sg of segments) await exec(FF, sg.argv);
          fs.writeFileSync(list, 'ffconcat version 1.0\n' +
            segments.map(sg => `file '${sg.output}'\nduration ${(+sg.argv[sg.argv.length - 2]).toFixed(6)}\n`).join(''));
          try { await exec(FF, join); }
          catch (e) { for (const f of [out, narOut]) if (f) fs.rmSync(f, { force: true }); throw e; }

          // The output against the plan, every time. A short picture or a short
          // sound is a failure, never a result.
          const op = await probeJson(out, ['-show_entries', 'stream=codec_type,nb_frames,duration:format_tags=comment']);
          const ov = (op.streams || []).find(x => x.codec_type === 'video') || {};
          const oa = (op.streams || []).find(x => x.codec_type === 'audio') || {};
          const want = Math.round(total * fps);
          const bad = [];
          if (Number(ov.nb_frames) !== want) bad.push(`picture has ${ov.nb_frames} frames, planned ${want}`);
          if (!(Math.abs(Number(oa.duration) - total) < 1 / fps)) bad.push(`sound is ${oa.duration}s, planned ${total.toFixed(6)}s`);
          if ((op.format?.tags?.comment ?? '') !== tag) bad.push('the clone windows did not land in the file\'s metadata');
          if (narOut) {
            const np = await probeJson(narOut, ['-show_entries', 'format=duration']);
            if (!(Math.abs(Number(np.format?.duration) - total) < 0.002)) bad.push(`narration is ${np.format?.duration}s, planned ${total.toFixed(6)}s`);
          }
          if (bad.length) {
            for (const f of [out, narOut]) if (f) fs.rmSync(f, { force: true });
            throw new Error(`the joined output does not match the plan, so it was removed: ${bad.join('; ')}`);
          }
          // Kept on failure, for diagnosis; removed once the join has landed.
          fs.rmSync(partsDir, { recursive: true, force: true });
          return result();
        },
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
          parts.push(`[0:v]trim=start=${s.start.toFixed(6)}:end=${s.end.toFixed(6)},setpts=PTS-STARTPTS[v${i}]`);
          pairs.push(`[v${i}]`);
          if (!hasAudio) return;
          parts.push(
            `[0:a]atrim=start=${s.start.toFixed(6)}:end=${s.end.toFixed(6)},asetpts=PTS-STARTPTS,` +
            `afade=t=in:st=0:d=${FA},afade=t=out:st=${Math.max(0, d - FA).toFixed(6)}:d=${FA}[a${i}]`);
          pairs[pairs.length - 1] = `[v${i}][a${i}]`;
        });
        parts.push(`${pairs.join('')}concat=n=${keep.length}:v=1:a=${hasAudio ? 1 : 0}` +
                   (hasAudio ? '[vcut][acut]' : '[vcut]'));
        parts.push(`[vcut]${baseChain}[vout]`);
        // apad is emitted ONLY when there is an ending to pad to. With no
        // ending padDur is 0, and ffmpeg documents pad_dur as "used only if set
        // to a non-zero value", so apad falls back to padding indefinitely. With
        // no -t and no -shortest on this argv that is a render that never ends,
        // which is the same defect this file already fixed in duck_mix.
        if (hasAudio) {
          parts.push(hasEnding
            ? `[acut]apad=pad_dur=${padDur.toFixed(6)}[aout]`
            : `[acut]anull[aout]`);
        }
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
      // The old walk hard-coded exactly two levels: readdir(drop)/readdir(a).
      // A manifest at drop/EP01/manifest.json sits one level down and was never
      // seen, so the job returned count:0 -- which reads as "nothing to do"
      // rather than as "I looked in the wrong place". Walk to MAX_DEPTH instead,
      // and report the depth and the root so a zero is diagnosable.
      const MAX_DEPTH = num(p.max_depth ?? 3, 'max_depth', { min: 1, max: 6, int: true });
      return { native: async () => {
        const found = [];
        let skippedDone = 0;
        const walk = (d, depth) => {
          if (depth > MAX_DEPTH) return;
          if (fs.existsSync(path.join(d, marker))) {
            // Skip anything already finished, same as the old `.done` check.
            if (fs.existsSync(path.join(d, '.done'))) { skippedDone++; return; }
            found.push(path.relative(WORK_ROOT, d));
            return;  // an episode directory does not contain further episodes
          }
          let entries;
          try { entries = fs.readdirSync(d, { withFileTypes: true }); }
          catch { return; }
          for (const ent of entries) {
            if (ent.isDirectory()) walk(path.join(d, ent.name), depth + 1);
          }
        };
        walk(dir, 0);
        found.sort();
        return {
          root: path.relative(WORK_ROOT, dir),
          scanned_depth: MAX_DEPTH,
          skipped_done: skippedDone,
          count: found.length,
          episodes: found,
        };
      }};
    },
  },

  /**
   * Seam captions for a Short, from word timings (added 2026-10-31). Reads the
   * JSON that word_timings writes, {stem: {text, words: [{text, start, end}]}},
   * and writes an SRT of short spoken phrases for presenter_composite's
   * `captions`. The format comes from the Vaibhav Sisinty Short Tee sent as
   * the reference: 2 to 5 words on screen at a time, broken where he breathes,
   * timed to the voice. Phrase rules live in seamCues below and are pinned by
   * jobs.test.js; a word with no usable timing is refused, never guessed.
   *
   * params: { words, output, line?, max_words?, offset?, tail? }
   */
  caption_srt: {
    build(p) {
      const src = existingPath(p.words, 'words');
      const out = ensureDir(safePath(p.output, 'output'));
      if (!/\.srt$/.test(out)) throw new BadJob('output: must end .srt');
      // presenter_composite refuses a captions path the subtitles filter cannot
      // take verbatim; refuse it here too, so the failure lands on this job.
      if (!/^[A-Za-z0-9_./-]+$/.test(out)) throw new BadJob('output: the resolved path carries a character the subtitles filter cannot take verbatim; rename it');
      const maxWords = num(p.max_words ?? 4, 'max_words', { min: 2, max: 6, int: true });
      const offset = num(p.offset ?? 0, 'offset', { min: 0, max: 86400 });
      const tail = num(p.tail ?? 0.15, 'tail', { min: 0, max: 1 });
      const line = p.line === undefined ? null : String(p.line);
      if (line !== null && !/^[A-Za-z0-9._-]{1,64}$/.test(line)) throw new BadJob('line: must be 1 to 64 of A-Z a-z 0-9 . _ -');
      return { native: async () => {
        const st = await fs.promises.stat(src);
        if (!st.isFile()) throw new Error(`not a regular file (${p.words})`);
        if (st.size > 8 * 1024 * 1024) throw new Error(`words file is ${st.size} bytes, over 8 MiB`);
        let doc;
        try { doc = JSON.parse(await fs.promises.readFile(src, 'utf8')); }
        catch (e) { throw new Error(`words: not valid JSON: ${e.message}`); }
        if (!doc || typeof doc !== 'object' || Array.isArray(doc)) throw new Error('words: expected an object keyed by line');
        const keys = Object.keys(doc);
        const key = line !== null ? line : (keys.length === 1 ? keys[0] : null);
        if (key === null) throw new Error(`words: the file holds ${keys.length} lines; name one with line`);
        const entry = Object.prototype.hasOwnProperty.call(doc, key) ? doc[key] : null;
        if (!entry || !Array.isArray(entry.words)) throw new Error(`words: no line ${key} with a words array`);
        const cues = seamCues(entry.words, { maxWords, offset, tail });
        await fs.promises.writeFile(out, seamSrt(cues), 'utf8');
        return { output: path.relative(WORK_ROOT, out), line: key, cues: cues.length,
                 words: cues.reduce((n, c) => n + c.words, 0), first: cues[0].start, last: cues[cues.length - 1].end };
      }};
    },
  },

  /** Read a text file. Replaces `cat manifest.json`. */
  read_text: {
    build(p) {
      const f = existingPath(p.path, 'path');
      const max = num(p.max_bytes ?? 1024 * 1024, 'max_bytes', { min: 1, max: 16 * 1024 * 1024 });
      return { native: async () => {
        // readFileSync on a FIFO blocks in open() forever, and because this runs
        // on the event loop it took the ENTIRE server with it, /health included,
        // without exiting, so systemd's Restart=on-failure never fired. One
        // authenticated request was a permanent wedge. Refuse anything that is
        // not a regular file, and read asynchronously so a slow device stalls
        // one job rather than the process.
        const st = await fs.promises.stat(f);
        if (!st.isFile()) throw new Error(`not a regular file (${p.path})`);
        if (st.size > max) throw new Error(`file is ${st.size} bytes, over max_bytes ${max}`);
        const text = await fs.promises.readFile(f, 'utf8');
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

  /**
   * Voice Lab, step one (added 2026-10-15). Native, no subprocess.
   *
   * Tee records the approved script on his iPhone, retakes and flubs included.
   * A speech-to-text pass gives every spoken word a start and an end. This job
   * lines the script up against those words and says, line by line, which
   * stretch of the real take to keep and which lines go to the voice clone,
   * read from the SCRIPT, word for word.
   *
   * A take is kept only when it says the line EXACTLY: the same words in the
   * same order once case and punctuation are folded away. The first cut kept
   * anything scoring 0.9 on a word-overlap ratio, and a fresh critic showed what
   * that means on a ten word line: "thirty percent" spoken as "forty" was kept,
   * "never" spoken as "always" was kept, and a dropped last word was kept. Any
   * line not said verbatim, a filler in the middle included, is patched. A
   * patch costs a clone reading; a kept misreading puts words on air that Tee
   * never approved.
   *
   * Which readings are kept is a dynamic program over every verbatim occurrence
   * of every line: the chosen readings must run in script order without
   * overlapping, and the choice keeps the most script WORDS. Ties go to the
   * later readings, so the last clean take wins. The first cut placed lines
   * greedily from the end, and the critic showed it handing the word "why" to a
   * skipped one word line and cloning the whole line before it.
   *
   * Too many patches is a re-record, not a patch. Above `max_patch_share` of
   * the lines the job returns verdict 'rerecord' and NO edl, so take_patch has
   * nothing to build from, and the per-line report says which lines missed.
   *
   * params: { lines: [string], words?: [{text, start, end, type?}],
   *           words_path?, take_duration?, max_patch_share?, pad? }
   */
  align_script: {
    build(p) {
      if (!Array.isArray(p.lines)) throw new BadJob('lines: must be an array of strings');
      if (p.lines.length < 1) throw new BadJob('lines: need at least one');
      if (p.lines.length > 2000) throw new BadJob('lines: too many (max 2000)');
      let lineToks = 0;
      const lines = p.lines.map((l, i) => {
        if (typeof l !== 'string') throw new BadJob(`lines[${i}]: not a string`);
        if (l.length > 4000) throw new BadJob(`lines[${i}]: over 4000 characters`);
        const toks = alignTokens(l);
        if (toks.length === 0) throw new BadJob(`lines[${i}]: has no words`);
        // Same reason as the cap on the transcript below: characters can fold
        // to many tokens, so the script is bounded by what it folds to.
        if ((lineToks += toks.length) > 100000) throw new BadJob('lines: over 100,000 tokens after folding; split the script');
        return { text: l, toks };
      });
      if (p.words !== undefined && p.words_path !== undefined) {
        throw new BadJob('words and words_path: send one, not both');
      }
      const wordsFile = p.words_path !== undefined ? existingPath(p.words_path, 'words_path') : null;
      if (wordsFile === null && !Array.isArray(p.words)) {
        throw new BadJob('words: must be an array of {text, start, end}');
      }
      if (p.threshold !== undefined) {
        throw new BadJob('threshold: removed 2026-10-15; a take is kept only when it says the line verbatim');
      }
      const maxShare = num(p.max_patch_share ?? 0.3, 'max_patch_share', { min: 0, max: 1 });
      const pad      = num(p.pad ?? 0.12, 'pad', { min: 0, max: 1 });
      const takeDur  = p.take_duration === undefined ? null
        : num(p.take_duration, 'take_duration', { min: 0.001, max: 86400 });

      const run = (rawWords) => {
        if (!Array.isArray(rawWords)) throw new BadJob('words: must be an array of {text, start, end}');
        if (rawWords.length > 50000) throw new BadJob('words: too many (max 50000)');
        // Speech-to-text vendors interleave spacing and sound events with the
        // words. Anything that declares a type other than 'word' is not speech.
        // The word count alone did not bound the work: one word can fold to
        // many tokens, and a fourth critic held the loop 20.2 s and grew the
        // server to 3.3 GiB with words of a single ligature that decomposes to
        // eighteen characters. Each word's text and token count are capped, and
        // so is the total, checked as it grows so a hostile file stops early.
        const words = [];
        rawWords.forEach((w, i) => {
          if (!w || typeof w !== 'object') throw new BadJob(`words[${i}]: not an object`);
          if (w.type !== undefined && w.type !== 'word') return;
          if (typeof w.text !== 'string') throw new BadJob(`words[${i}].text: not a string`);
          if (w.text.length > 64) throw new BadJob(`words[${i}].text: over 64 characters; that is not one spoken word`);
          const s = num(w.start, `words[${i}].start`, { min: 0, max: 86400 });
          const e = num(w.end,   `words[${i}].end`,   { min: 0, max: 86400 });
          if (e < s) throw new BadJob(`words[${i}]: end before start`);
          // One transcript word can fold to two tokens ("twenty-six") or to
          // none (a lone dash). Each token keeps the word's own timing and
          // remembers whether it opens or closes its word, because a reading
          // may only start and end on a word boundary: "this is our year"
          // matched the front half of a spoken "year-end" and cut it mid word.
          const tk = alignTokens(w.text);
          if (tk.length > 16) throw new BadJob(`words[${i}].text: folds to ${tk.length} tokens, over 16; that is not one spoken word`);
          if (words.length + tk.length > 100000) throw new BadJob('words: over 100,000 tokens after folding; split the take');
          tk.forEach((t, j) => words.push({ tok: t, s, e, opens: j === 0, closes: j === tk.length - 1 }));
        });
        for (let i = 1; i < words.length; i++) {
          if (words[i].s < words[i - 1].s) throw new BadJob('words: not in time order');
        }
        const W = words.map(w => w.tok);
        const byTok = new Map();
        W.forEach((t, i) => { if (!byTok.has(t)) byTok.set(t, []); byTok.get(t).push(i); });

        // Every verbatim occurrence of every line. The scan is bounded by
        // token COMPARISONS, so a pathological script is refused rather than
        // allowed to hold the event loop: this is a native job, and server.js
        // cannot interrupt one. The first bound counted starting positions,
        // and a critic held the loop 8.3 s inside it with 41 lines of 1,999
        // words; 20 million comparisons is a fraction of a second here.
        // Every candidate also costs a fixed 8, and the readings KEPT are capped
        // at 200,000: one word lines cost one comparison each, and a third
        // critic held the loop 11 s and grew the heap 2.1 GiB with 399 lines of
        // "the" against 50,000 words inside the comparison bound alone.
        let budget = 20000000;
        let kept = 0;
        const occ = lines.map(({ toks }) => {
          const out = [];
          for (const s of byTok.get(toks[0]) || []) {
            if (s + toks.length > W.length) break;
            budget -= toks.length + 8;
            if (budget < 0) throw new BadJob('lines: too many comparisons to search (over 20,000,000); split the take');
            if (!words[s].opens || !words[s + toks.length - 1].closes) continue;
            let ok = true;
            for (let j = 1; j < toks.length; j++) if (W[s + j] !== toks[j]) { ok = false; break; }
            if (ok) {
              if (++kept > 200000) throw new BadJob('lines: over 200,000 verbatim readings to place; the script repeats itself too much to align, split it');
              out.push({ s, e: s + toks.length - 1 });
            }
          }
          return out;
        });

        // Keep the most script words, in order, without overlap; ties go to the
        // later readings. A Fenwick tree over transcript positions answers
        // "the best chain ending before position x" in log time, and a line's
        // own occurrences are only inserted after all of them have queried, so
        // no chain ever uses one line twice.
        const better = (a, b) => (a.w !== b.w ? a.w > b.w : a.sec > b.sec);
        const ZERO = { w: 0, sec: 0, node: null };
        const tree = new Array(W.length + 1).fill(ZERO);
        const query = (x) => { let r = ZERO; for (let i = x; i > 0; i -= i & -i) if (better(tree[i], r)) r = tree[i]; return r; };
        const update = (x, v) => { for (let i = x + 1; i <= W.length; i += i & -i) if (better(v, tree[i])) tree[i] = v; };
        let best = ZERO;
        lines.forEach((l, li) => {
          const made = occ[li].map((o) => {
            const q = query(o.s);   // chains whose last reading ends before o.s
            const v = { w: q.w + l.toks.length, sec: q.sec + o.s, node: { li, o, prev: q.node } };
            if (better(v, best)) best = v;
            return v;
          });
          made.forEach((v) => update(v.node.o.e, v));
        });
        const chosen = new Array(lines.length).fill(null);
        for (let n = best.node; n; n = n.prev) chosen[n.li] = n.o;

        const report = lines.map((l, i) => chosen[i]
          ? { line: i, kind: 'take', from_word: chosen[i].s, to_word: chosen[i].e }
          : { line: i, kind: 'patch', said_verbatim_times: occ[i].length, text: l.text });
        const patched = report.filter(r => r.kind === 'patch').length;
        const taken = lines.length - patched;
        const share = patched / lines.length;

        // presenter_composite lays at most 64 cutaways, one per clone window,
        // so more patches than that cannot be covered and are a re-record too.
        if (share > maxShare || taken === 0 || patched > 64) {
          return {
            verdict: 'rerecord',
            reason: taken === 0
              ? 'no line of the script was said verbatim in the take'
              : patched > 64
                ? `${patched} lines need the clone, over the 64 cutaways one composite can lay`
                : `${patched} of ${lines.length} lines were not said verbatim (${(share * 100).toFixed(1)}%), over the ${(maxShare * 100).toFixed(1)}% ceiling`,
            lines: lines.length, patched, patch_share: +share.toFixed(4),
            edl: null, report,
          };
        }

        // Lines back to back in the transcript, with no word between them,
        // stay one span so the natural pause survives. A pad either side never
        // reaches past the midpoint to the neighbouring word, so it cannot
        // pull in half of a flubbed one, and never runs past the take's end.
        // When the vendor's timestamps overlap, the midpoint falls INSIDE the
        // kept word, and a fourth critic got 50 ms cut off the end of "done".
        // The kept words themselves are never trimmed: the edge stops at the
        // midpoint or at the word, whichever leaves the word whole.
        const edges = (sIdx, eIdx) => {
          const a = words[sIdx].s, b = words[eIdx].e;
          const lo = Math.min(a, sIdx > 0 ? (words[sIdx - 1].e + a) / 2 : 0);
          let hi = Math.max(b, eIdx < words.length - 1 ? (b + words[eIdx + 1].s) / 2 : b + pad);
          if (takeDur !== null) hi = Math.min(hi, takeDur);
          return { start: Math.max(lo, a - pad), end: Math.min(hi, b + pad) };
        };
        const edl = [];
        report.forEach((r) => {
          const last = edl[edl.length - 1];
          if (r.kind === 'patch') { edl.push({ kind: 'patch', lines: [r.line], text: r.text }); return; }
          if (last && last.kind === 'take' && r.from_word === last.to_word + 1) {
            last.lines.push(r.line);
            last.to_word = r.to_word;
          } else {
            edl.push({ kind: 'take', lines: [r.line], from_word: r.from_word, to_word: r.to_word });
          }
        });
        // Rounded INWARD to the millisecond, so a rounded end can never land
        // past take_duration and get the edl refused by take_patch (12.3456
        // rounded to 12.346 did, in the critic's run).
        edl.forEach((it) => {
          if (it.kind !== 'take') return;
          const { start, end } = edges(it.from_word, it.to_word);
          it.start = Math.ceil(start * 1000 - 1e-6) / 1000;
          it.end = Math.floor(end * 1000 + 1e-6) / 1000;
        });

        return {
          verdict: patched === 0 ? 'clean' : 'patch',
          lines: lines.length, patched, patch_share: +share.toFixed(4),
          edl, report,
        };
      };

      return { native: async () => {
        if (wordsFile === null) return run(p.words);
        const st = await fs.promises.stat(wordsFile);
        if (!st.isFile()) throw new Error(`not a regular file (${p.words_path})`);
        if (st.size > 16 * 1024 * 1024) throw new Error(`words_path is ${st.size} bytes, over 16 MiB`);
        let parsed;
        try { parsed = JSON.parse(await fs.promises.readFile(wordsFile, 'utf8')); }
        catch (e) { throw new BadJob(`words_path: not JSON (${e.message})`); }
        // An ElevenLabs speech-to-text response carries the list under `words`.
        return run(Array.isArray(parsed) ? parsed : parsed && parsed.words);
      }};
    },
  },
};

/**
 * Words are compared after folding case, accents and curly quotes. Then ONLY
 * a fixed set of punctuation is dropped: . , ; : ! ? quotes brackets and the
 * em dash. Every other character that is not a letter a to z, a digit or an
 * apostrophe inside a word becomes a token of its own, \u0001 plus the
 * character, so it matches only the same character on the other side.
 *
 * The first cut dropped everything else, and a critic got "rose 30% this
 * year" kept for a script saying "rose 30". The second cut marked a LIST of
 * symbols so they matched nothing, and a third critic walked "\u00a5500",
 * "\u00b15", an en dash minus and whole Japanese words straight through it,
 * while a perfect read of a line with % could never be kept at all.
 *
 * Digits stay digits: "3" and "three" do not match, the safe direction. A
 * minus or en dash in front of a digit is a token, and so is a point in front
 * of a digit (".5" is not "5", "$.99" is not "$99"). A comma between digits is
 * dropped ONLY as a thousands separator, one to three digits then groups of
 * exactly three ("1,000" is "1000"); anywhere else it is a token, so a
 * decimal "1,5" is not "15" and "3,4" is not "34". A character that is not a
 * plain digit but folds to one ("\u00b2", "\u00bd", a circled or full width
 * digit) is a token of its own, so "10\u00b2" is not "102". The fourth critic
 * had all five of those kept as clean readings of a different number.
 */
function alignTokens(s) {
  // Folded one code point at a time, so a character that folds to a digit is
  // caught BEFORE the fold makes it indistinguishable from one.
  const u = [];
  for (const cp of String(s)) {
    if (cp <= '\u007f') { u.push({ c: cp.toLowerCase(), sym: false }); continue; }
    const n = cp.normalize('NFKD').replace(/[\u0300-\u036f]/g, '').toLowerCase()
      .replace(/[\u2018\u2019\u02bc]/g, "'");
    if (/[0-9]/.test(n)) { u.push({ c: cp, sym: true }); continue; }
    for (const c of n) u.push({ c, sym: false });
  }
  const DROP = new Set([',', ';', ':', '!', '?', '"', '\u201c', '\u201d', '(', ')', '[', ']', '{', '}', '\u2014', '\u2026']);
  const at = (i) => (i >= 0 && i < u.length && !u[i].sym ? u[i].c : undefined);
  const isWord = (c) => c !== undefined && /[a-z0-9']/.test(c);
  const isDigit = (c) => c !== undefined && c >= '0' && c <= '9';
  const thousands = new Set();
  const isThousands = (i) => {
    let k = i - 1;
    while (isDigit(at(k))) k--;
    const run = i - 1 - k;
    if (run < 1 || run > 3 || (k >= 0 && !thousands.has(k) && (at(k) === ',' || at(k) === '.'))) return false;
    return isDigit(at(i + 1)) && isDigit(at(i + 2)) && isDigit(at(i + 3)) && !isDigit(at(i + 4));
  };
  const out = [];
  let word = '';
  const flush = () => { const w = word.replace(/^'+|'+$/g, ''); if (w) out.push(w); word = ''; };
  for (let i = 0; i < u.length; i++) {
    if (u[i].sym) { flush(); out.push('\u0001' + u[i].c); continue; }
    const c = u[i].c, prev = at(i - 1), next = at(i + 1);
    if (isWord(c)) { word += c; continue; }
    if (c === ',' && isDigit(prev) && isThousands(i)) { thousands.add(i); continue; }
    if ((c === '.' || c === ',') && isDigit(next)) { flush(); out.push('\u0001' + c); continue; }
    if ((c === '-' || c === '\u2212') && isDigit(next) && !(prev && /[a-z0-9]/.test(prev))) {
      flush(); out.push('\u0001\u2212'); continue;
    }
    if (/\s/.test(c) || c === '-' || c === '.' || DROP.has(c)) { flush(); continue; }
    flush(); out.push('\u0001' + c);
  }
  flush();
  return out;
}

/**
 * The clone windows take_patch writes into its output's container metadata,
 * read back with ffprobe. null when the file carries none. Throws a BadJob
 * when the file cannot be read at all, so an unreadable base track is refused
 * rather than composited unchecked.
 */
const VOICE_LAB_TAG = 'voicelab-must-cover:';
// Containers whose global comment survives a stream copy and reads back. The
// fourth critic wrote a tagged base to .ts, which drops the tag, and to .mkv,
// which keeps it under the key COMMENT that the first reader never looked
// for; both composited 37 face frames under the clone.
const TAGGED_EXT = new Set(['.mp4', '.mov', '.m4v', '.mkv', '.webm']);
const TAGGED_FORMATS = new Set(['mov,mp4,m4a,3gp,3g2,mj2', 'matroska,webm']);
let tagReader = (f) => {
  const { execFileSync } = require('child_process');
  return JSON.parse(execFileSync(FP, ['-v', 'error', '-select_streams', 'v:0',
    '-show_entries', 'format=format_name,duration:format_tags=comment:stream=duration:stream_tags=duration', '-of', 'json', f],
  { timeout: 15000, maxBuffer: 4 * 1024 * 1024, stdio: ['ignore', 'pipe', 'ignore'] }).toString());
};
function readVoiceLabWindows(f) {
  // Checked before ffprobe opens it: a playlist or an ffconcat as the base
  // held the event loop 861 ms in the critic's run before being read at all.
  if (!TAGGED_EXT.has(path.extname(f).toLowerCase())) {
    throw new BadJob('avatar: must be .mp4, .mov, .m4v, .mkv or .webm, the containers that carry Voice Lab windows through a copy');
  }
  let j;
  try { j = tagReader(f); }
  catch (e) { throw new BadJob(`avatar: could not read its tags to check for Voice Lab windows (${String(e.message).split('\n')[0]})`); }
  const fmt = (j && j.format) || {};
  if (!TAGGED_FORMATS.has(String(fmt.format_name))) {
    throw new BadJob(`avatar: its container reads as ${fmt.format_name || 'unknown'}, not mp4, mov, mkv or webm, so its Voice Lab windows cannot be trusted`);
  }
  const tags = fmt.tags || {};
  const key = Object.keys(tags).find(k => k.toLowerCase() === 'comment');
  const c = key === undefined ? undefined : String(tags[key]).trimStart();
  if (typeof c !== 'string' || !c.toLowerCase().startsWith(VOICE_LAB_TAG)) return null;
  let parsed;
  try { parsed = JSON.parse(c.slice(VOICE_LAB_TAG.length)); }
  catch (e) { throw new BadJob(`avatar: its Voice Lab windows are unreadable (${e.message}); re-run take_patch`); }
  if (!parsed || !Array.isArray(parsed.windows)) throw new BadJob('avatar: its Voice Lab tag has no windows; re-run take_patch');
  // A job that re-times the file copies the tag unchanged, and a critic cut
  // one second from a base and got 30 face frames from the stale windows. The
  // tag records the length it was written for; the file must still be it.
  const fps = Number(parsed.fps), dur = Number(parsed.duration);
  if (!(fps > 0) || !(dur > 0)) throw new BadJob('avatar: its Voice Lab tag has no fps or duration; re-run take_patch');
  // The PICTURE's length: an mkv has no stream duration but tags one as
  // HH:MM:SS.fffffffff, and its format duration includes audio padding, which
  // read 88 ms long after loudnorm_apply in the round four run.
  const st = Array.isArray(j.streams) ? j.streams[0] : null;
  const stTags = (st && st.tags) || {};
  const tagKey = Object.keys(stTags).find(k => k.toLowerCase() === 'duration');
  const hms = tagKey === undefined ? null : /^(\d+):(\d\d):(\d\d(?:\.\d+)?)$/.exec(String(stTags[tagKey]));
  const have = Number(st && st.duration) > 0 ? Number(st.duration)
    : hms ? (+hms[1]) * 3600 + (+hms[2]) * 60 + (+hms[3])
      : Number(fmt.duration);
  if (!(have > 0)) throw new BadJob('avatar: has no readable duration to check its Voice Lab windows against');
  if (Math.abs(have - dur) > 1.5 / fps) {
    throw new BadJob(`avatar: runs ${have}s, but its Voice Lab windows were written for a ${dur}s cut; ` +
                     'something after take_patch changed the timeline, so run take_patch on the final cut');
  }
  return parsed.windows;
}
/** For the builder tests, which run without ffprobe. */
function setTagReader(fn) { tagReader = fn; }

/**
 * Seam caption cues from timed words, for caption_srt. A phrase ends after a
 * word that ends in . ? ! , ; or :, and a phrase longer than maxWords is cut
 * into groups of maxWords, except that a single word left over joins the group
 * before it rather than flashing alone. A one word phrase joins the phrase
 * before it when that keeps the cue at maxWords + 1 or under. Text loses the
 * characters libass would read as markup ({ } \ < >) and nothing else; a word
 * left empty by that is dropped. Times: first word's start to last word's end
 * plus tail, shifted by offset, cut 20 ms short of the next cue, and never
 * under 0.3 s unless the next cue leaves less room. A word without a finite
 * start and end, or with end before start, is refused: a guessed time puts a
 * caption on the wrong line.
 */
function seamCues(words, { maxWords = 4, offset = 0, tail = 0.15 } = {}) {
  if (!Array.isArray(words) || !words.length) throw new Error('words: none to caption');
  if (words.length > 20000) throw new Error('words: too many (max 20000)');
  const clean = [];
  words.forEach((w, k) => {
    const s = Number(w && w.start), e = Number(w && w.end);
    if (!Number.isFinite(s) || !Number.isFinite(e) || s < 0 || e < s) {
      throw new Error(`words[${k}]: start ${w && w.start} and end ${w && w.end} are not a usable time span`);
    }
    const text = String((w && (w.text ?? w.word)) ?? '').replace(/[{}\\<>\u0000-\u001f\u007f]/g, '').replace(/\s+/g, ' ').trim();
    if (text) clean.push({ text, s, e });
  });
  if (!clean.length) throw new Error('words: none left after removing markup characters');
  const phrases = []; let cur = [];
  for (const w of clean) { cur.push(w); if (/[.?!,;:]["')\]]?$/.test(w.text)) { phrases.push(cur); cur = []; } }
  if (cur.length) phrases.push(cur);
  const endsSentence = (g) => /[.?!]["')\]]?$/.test(g[g.length - 1].text);
  const groups = [];
  for (let q = 0; q < phrases.length; q++) {
    const ph = phrases[q];
    // A one word phrase joins the group before it when that group did not end
    // a sentence and has room; otherwise it opens the next phrase ("Before,"
    // then "the bot worked" reads "Before, the bot worked"). Only a one word
    // phrase with nothing after it stands alone.
    if (ph.length === 1 && groups.length && !endsSentence(groups[groups.length - 1]) &&
        groups[groups.length - 1].length + 1 <= maxWords + 1) {
      groups[groups.length - 1].push(ph[0]);
      continue;
    }
    if (ph.length === 1 && q + 1 < phrases.length) { phrases[q + 1] = [ph[0], ...phrases[q + 1]]; continue; }
    let i = 0;
    while (i < ph.length) {
      const take = ph.length - (i + maxWords) === 1 ? maxWords + 1 : maxWords;
      groups.push(ph.slice(i, i + take));
      i += take;
    }
  }
  const r3 = (x) => Math.round(x * 1000) / 1000;
  const cues = groups.map(g => ({ start: r3(g[0].s + offset), end: r3(g[g.length - 1].e + tail + offset),
                                  text: g.map(w => w.text).join(' '), words: g.length }));
  for (let k = 0; k < cues.length; k++) {
    const next = k + 1 < cues.length ? cues[k + 1].start - 0.02 : Infinity;
    let end = Math.max(cues[k].end, cues[k].start + 0.3);
    end = Math.min(end, next);
    if (!(end > cues[k].start)) end = cues[k].start + 0.001;
    cues[k].end = r3(end);
  }
  return cues;
}
function seamSrt(cues) {
  const ts = (t) => {
    const ms = Math.round(t * 1000);
    const h = Math.floor(ms / 3600000), m = Math.floor(ms / 60000) % 60, s = Math.floor(ms / 1000) % 60, f = ms % 1000;
    return `${String(h).padStart(2, '0')}:${String(m).padStart(2, '0')}:${String(s).padStart(2, '0')},${String(f).padStart(3, '0')}`;
  };
  return cues.map((c, n) => `${n + 1}\n${ts(c.start)} --> ${ts(c.end)}\n${c.text}\n\n`).join('');
}

/** A path's real location, resolving symlinks, for a file that may not exist yet. */
function realish(p) {
  try { return fs.realpathSync(p); }
  catch (_) {
    try { return path.join(fs.realpathSync(path.dirname(p)), path.basename(p)); }
    catch (__) { return path.resolve(p); }
  }
}

// ACX Node assembly (2026-10-28, ruled R22): two native jobs in their own file,
// built against the same validators so a path, a number or a choice is refused
// the same way here as everywhere else in this table.
Object.assign(JOBS, require('./acx_node.js').jobs({ BadJob, safePath, existingPath, num, oneOf, getRoot, ensureDir }));

module.exports = { JOBS, BadJob, safePath, existingPath, num, oneOf, setRoot, getRoot, PRESETS,
                   normalizeChain, isStill, gainEnvelope, setTagReader, alignTokens, seamCues, seamSrt };
