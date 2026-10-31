'use strict';
// DRAFT bridge for the pinned, local TSWS repair package. No shell or generation API.
const fs = require('fs');
const path = require('path');
const crypto = require('crypto');
const { spawn } = require('child_process');

const METHODS = Object.freeze({
  TSWS_SHOT_COMPOSER: ['workflows/shot_composer/tsws_shot_composer.py', 'run', '--job'],
  TSWS_SHOT_CLEANUP: ['workflows/shot_cleanup/tsws_shot_cleanup.py', 'run', '--job'],
  TSWS_SCENE_BUILDER: ['workflows/scene_builder/tsws_scene_builder.py', 'build', '--spec'],
});
const ID = /^[A-Za-z0-9][A-Za-z0-9_.-]{0,63}$/;
const DRIVE_ID = /^[A-Za-z0-9_-]{1,160}$/;
const SHA = /^[a-f0-9]{64}$/;
const sha = bytes => crypto.createHash('sha256').update(bytes).digest('hex');
function fail(message, code = 400) { const e = new Error(message); e.statusCode = code; throw e; }
function obj(x) { return x !== null && typeof x === 'object' && !Array.isArray(x); }
function relName(x) {
  if (typeof x !== 'string' || x.length > 240 || !x.split('/').every(p => ID.test(p)) || x.includes('..'))
    fail('input paths must be relative, plain names with no dot traversal');
  return x;
}
function plainFile(p) {
  const st = fs.lstatSync(p);
  if (!st.isFile() || st.isSymbolicLink()) fail('not a regular input file');
  return st;
}
function under(root, rel) {
  const p = path.join(root, relName(rel));
  const real = fs.realpathSync(p);
  if (real !== p || !real.startsWith(root + path.sep)) fail('symlink or path escape refused');
  return p;
}
function atomicJSON(p, value) {
  const tmp = p + '.tmp';
  const fd = fs.openSync(tmp, 'wx', 0o600);
  try { fs.writeFileSync(fd, JSON.stringify(value, null, 2) + '\n'); fs.fsyncSync(fd); }
  finally { fs.closeSync(fd); }
  fs.renameSync(tmp, p);
  const dirfd = fs.openSync(path.dirname(p), 'r');
  try { fs.fsyncSync(dirfd); } finally { fs.closeSync(dirfd); }
}
function hashFile(p) {
  const h = crypto.createHash('sha256'), buf = Buffer.alloc(1024 * 1024), fd = fs.openSync(p, 'r');
  try { let n; while ((n = fs.readSync(fd, buf)) > 0) h.update(buf.subarray(0, n)); }
  finally { fs.closeSync(fd); }
  return h.digest('hex');
}
function rewriteJob(job, workflow, inputRoot, roles) {
  if (!obj(job) || job.workflow !== workflow || job.status !== 'DRAFT') fail('job workflow/status mismatch');
  function walk(v, key = '') {
    if (typeof v === 'string' && ['path', 'clean_plate', 'protected_mask'].includes(key)) {
      const rel = relName(v);
      if (!roles.some(r => r === rel || r.startsWith(rel + '/'))) fail('job references undeclared input: ' + rel);
      return under(inputRoot, rel);
    }
    if (typeof v === 'string' && ['id', 'name', 'job_id', 'scene_id'].includes(key) && !ID.test(v))
      fail('unsafe output identifier');
    if (key === 'pattern' && (typeof v !== 'string' || !/^[A-Za-z0-9_-]*%0?[1-8]?d\.(png|jpg|jpeg)$/.test(v)))
      fail('unsafe frame pattern');
    if (key === 'actor_mattes') {
      if (!obj(v)) fail('actor_mattes must be an object');
      return Object.fromEntries(Object.entries(v).map(([k, x]) => {
        if (!ID.test(k)) fail('unsafe actor id');
        return [k, walk(x, 'path')];
      }));
    }
    if (Array.isArray(v)) return v.map(x => walk(x));
    if (obj(v)) return Object.fromEntries(Object.entries(v).map(([k, x]) => [k, walk(x, k)]));
    return v;
  }
  const out = walk(job);
  const n = workflow === 'TSWS_SCENE_BUILDER' ? job.path?.frames : job.source?.last_frame - job.source?.first_frame + 1;
  if (!Number.isInteger(n) || n < 2 || n > 2400) fail('frame count outside 2..2400');
  const fps = workflow === 'TSWS_SCENE_BUILDER' ? job.path?.fps : job.source?.fps;
  if (!Number.isFinite(fps) || fps < 1 || fps > 120) fail('fps outside 1..120');
  return out;
}

function build(p, { safePath, getRoot }) {
  if (!obj(p) || !ID.test(p.envelope_id || '')) fail('invalid envelope_id');
  if (!Object.hasOwn(METHODS, p.workflow)) fail('unsupported repair workflow');
  const method = METHODS[p.workflow];
  if (p.command !== undefined && p.command !== path.basename(method[0]) + ' ' + method[1])
    fail('command must match the fixed workflow mapping');
  if (p.generation_requested || p.generation_jobs?.length) fail('generation is not supported');
  if (!obj(p.job) || !DRIVE_ID.test(p.job.job_file_drive_id || '') || !SHA.test(p.job.job_file_sha256 || ''))
    fail('job requires a Drive id and SHA-256');
  if (!Array.isArray(p.inputs) || !p.inputs.length || p.inputs.length > 10000) fail('inputs must contain 1..10000 files');
  const roles = new Set();
  for (const item of p.inputs) {
    if (!obj(item) || !DRIVE_ID.test(item.drive_id || '') || !SHA.test(item.sha256 || '')) fail('invalid input identity');
    relName(item.role);
    if (roles.has(item.role)) fail('duplicate input role');
    roles.add(item.role);
    if (item.bytes !== undefined && (!Number.isSafeInteger(item.bytes) || item.bytes < 0)) fail('invalid byte count');
  }
  // Config belongs to the operator; callers cannot choose a script, interpreter, URL or cache root.
  const packageRoot = process.env.TSWS_REPAIR_PACKAGE_ROOT;
  const cacheRoot = process.env.TSWS_REPAIR_CACHE_ROOT;
  const python = process.env.TSWS_REPAIR_PYTHON;
  const origin = process.env.TSWS_REPAIR_PUBLIC_ORIGIN;
  if (!packageRoot || !cacheRoot || !python || !origin) fail('BLOCKED_CONFIGURATION: repair runtime/cache/origin not configured', 503);
  let base;
  try { base = new URL(origin); } catch { fail('invalid configured repair origin', 503); }
  if (!['http:', 'https:'].includes(base.protocol) || base.username || base.password || base.search || base.hash || base.pathname !== '/')
    fail('repair origin must be an http(s) origin without credentials or path', 503);
  const pkg = fs.realpathSync(packageRoot), cache = fs.realpathSync(cacheRoot);
  const script = under(pkg, method[0]); plainFile(script);
  const pythonExe = fs.realpathSync(python); plainFile(pythonExe);
  const runRoot = safePath('repair/' + p.envelope_id);
  let child, aborted = false, claimed = false;
  function stop() { aborted = true; if (child?.pid) { try { process.kill(-child.pid, 'SIGKILL'); } catch (e) { if (e.code !== 'ESRCH') throw e; } } }
  function claim(id) {
    const parent = safePath('repair'); fs.mkdirSync(parent, { recursive: true, mode: 0o700 });
    try { fs.mkdirSync(runRoot, { mode: 0o700 }); }
    catch (e) { if (e.code === 'EEXIST') fail('envelope already claimed; automatic retry refused', 409); throw e; }
    // Exclusive directory plus fsynced receipt survives restarts. Never remove a failed claim.
    atomicJSON(path.join(runRoot, 'CLAIM.json'), { status: 'DRAFT', job_id: id, envelope_id: p.envelope_id,
      request_sha256: sha(JSON.stringify(p)), claimed_at: new Date().toISOString(), retry: 'REFUSED' });
    const fd = fs.openSync(parent, 'r'); try { fs.fsyncSync(fd); } finally { fs.closeSync(fd); }
    claimed = true;
  }
  async function native() {
    if (!claimed) fail('durable claim required');
    const inputRoot = path.join(runRoot, 'inputs'), out = path.join(runRoot, 'output');
    fs.mkdirSync(inputRoot, { mode: 0o700 });
    let stagedBytes = 0;
    function stage(id, expected, dest, bytes, maxBytes = 4 * 1024 ** 3) {
      if (aborted) fail('repair aborted');
      // Private pre-stage convention: CACHE/DRIVE_ID/SHA256. No public sharing or URL fetching.
      let src;
      try { src = under(cache, id + '/' + expected); }
      catch (e) { if (e.code === 'ENOENT') fail('BLOCKED_INPUT_DELIVERY: authenticated staging required for ' + id); throw e; }
      const st = plainFile(src);
      stagedBytes += st.size;
      if (st.size > maxBytes || stagedBytes > 16 * 1024 ** 3 || (bytes !== undefined && st.size !== bytes))
        fail('input byte count mismatch or size limit exceeded');
      fs.mkdirSync(path.dirname(dest), { recursive: true, mode: 0o700 });
      fs.copyFileSync(src, dest, fs.constants.COPYFILE_EXCL);
      if (hashFile(dest) !== expected) { fs.unlinkSync(dest); fail('input SHA-256 mismatch'); }
      fs.chmodSync(dest, 0o400);
    }
    try {
      const rawJob = path.join(runRoot, 'job_original.json');
      stage(p.job.job_file_drive_id, p.job.job_file_sha256, rawJob, undefined, 1024 * 1024);
      for (const item of p.inputs) stage(item.drive_id, item.sha256, path.join(inputRoot, item.role), item.bytes);
      const job = rewriteJob(JSON.parse(fs.readFileSync(rawJob, 'utf8')), p.workflow, inputRoot, [...roles]);
      const jobFile = path.join(runRoot, 'job_staged.json'); atomicJSON(jobFile, job);
      fs.mkdirSync(out, { mode: 0o700 });
      const childEnv = { PATH: process.env.TSWS_REPAIR_PATH || process.env.PATH, LANG: 'C.UTF-8',
        HOME: runRoot, TMPDIR: runRoot, PYTHONNOUSERSITE: '1', PYTHONDONTWRITEBYTECODE: '1',
        OMP_NUM_THREADS: '2', OPENBLAS_NUM_THREADS: '2' };
      const code = await new Promise((resolve, reject) => {
        if (aborted) return reject(new Error('repair aborted'));
        child = spawn(python, [script, method[1], method[2], jobFile, '--out', out],
          { cwd: pkg, env: childEnv, detached: true, stdio: ['ignore', 'pipe', 'pipe'] });
        let size = 0;
        const log = fs.createWriteStream(path.join(runRoot, 'PROCESS.log'), { flags: 'wx', mode: 0o600 });
        for (const stream of [child.stdout, child.stderr]) stream.on('data', b => {
          size += b.length;
          if (size > 16 * 1024 ** 2) { stop(); } else log.write(b);
        });
        child.once('error', e => { log.end(); reject(new Error('repair interpreter failed: ' + e.code)); });
        child.once('close', rc => { child = null; log.end(() => aborted ? reject(new Error('repair aborted or log limit exceeded')) : resolve(rc)); });
      });
      const rp = path.join(out, 'RESULT.json');
      if (![0, 1, 3].includes(code) || !fs.existsSync(rp)) fail('repair process failed: exit ' + code + '; see PROCESS.log');
      const result = JSON.parse(fs.readFileSync(rp, 'utf8'));
      if (typeof result.verdict !== 'string') fail('repair result has no verdict');
      const artifacts = [];
      function collect(dir) {
        for (const entry of fs.readdirSync(dir, { withFileTypes: true }).sort((a, b) => a.name.localeCompare(b.name))) {
          const file = path.join(dir, entry.name);
          if (entry.isSymbolicLink()) fail('output symlink refused');
          if (entry.isDirectory()) collect(file);
          else if (entry.isFile()) {
            const rel = path.relative(out, file), workerRel = path.relative(getRoot(), file);
            const digest = hashFile(file);
            artifacts.push({ name: sha(rel).slice(0, 12) + '_' + path.basename(file).replace(/[^A-Za-z0-9_.-]/g, '_').slice(-100),
              relative_path: rel, url: base.origin + '/files/' + workerRel.split(path.sep).map(encodeURIComponent).join('/'),
              sha256: digest, bytes: fs.statSync(file).size });
          } else fail('non-regular output refused');
          if (artifacts.length > 50000) fail('artifact count limit exceeded');
        }
      }
      collect(out);
      const receipt = { status: 'DRAFT', envelope_id: p.envelope_id, workflow: p.workflow, exit_code: code,
        verdict: result.verdict, complete_shot_accepted: false, continuous_playback: 'UNVERIFIED', human_review_required: true,
        result, artifacts };
      atomicJSON(path.join(runRoot, 'DELIVERY.json'), receipt);
      return receipt;
    } catch (e) {
      atomicJSON(path.join(runRoot, 'ERROR.json'), { status: 'DRAFT', error: e.message, artifacts: [], automatic_retry: false });
      throw e;
    }
  }
  return { claim, native, abort: stop };
}
module.exports = { build, METHODS, rewriteJob };
