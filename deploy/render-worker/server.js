'use strict';
/**
 * TSWS render worker - HTTP server.
 *
 * jobs.js is a library of job DEFINITIONS and nothing more. It was recovered
 * from Drive on its own, with no server beside it, so for five weeks the
 * documented worker could not have been started by anybody. This is that
 * missing half, written to the contract the caller already expects.
 *
 * THE CALLER IS ALREADY WRITTEN AND IS NOT NEGOTIABLE.
 * n8n workflow TSWS 00 (VPS CX07qa6O1hTSXlpj, Cloud o4ctniOsIq2VSfgm) pins all
 * of this. Read those nodes before changing any status string or status code:
 *
 *   Submit Job   POST <base>/jobs   header auth, json {type, params}
 *                Accepted? requires statusCode === 202
 *                Poll Job reads  $('Submit Job').first().json.body.id
 *   Poll Job     GET  <base>/jobs/{id}
 *                Finished? fires on status done | error | invalid, or ok false
 *                Succeeded? requires status === 'done'
 *   Return Result reads  id, result, seconds, type
 *   Return Failure reads status, id, error, exitCode, type
 *   Submit Rejected reads statusCode and body.error
 *
 * THE ONE RULE, inherited from jobs.js: every job builds an argv array, and the
 * server never spawns a shell. execFile, never exec. A single quote in an
 * episode title must not be able to become a command.
 */
const http = require('http');
const crypto = require('crypto');
const { execFile } = require('child_process');
const path = require('path');
const fs = require('fs');

const J = require('./jobs.js');

// --- configuration ---------------------------------------------------------

const PORT        = Number(process.env.PORT || 8080);
const HOST        = process.env.HOST || '0.0.0.0';
const TOKEN       = process.env.WORKER_TOKEN || '';
const WORK_ROOT   = process.env.WORK_ROOT || '/data/tsws';
// Matches the 6h poll budget Prep Request defaults to in TSWS 00. A job that
// outlives the caller's own budget is only burning the box.
const JOB_TIMEOUT = Number(process.env.JOB_TIMEOUT_MS || 6 * 3600 * 1000);
// Renders are CPU bound. Two 4K x264 encodes on the same box are slower than
// two in sequence and make both look hung.
const CONCURRENCY = Number(process.env.CONCURRENCY || 1);
const MAX_BODY    = Number(process.env.MAX_BODY_BYTES || 1024 * 1024);
// Results are held so a caller that loses its poll can still collect. 24h is
// well past the longest render plus the longest plausible retry.
const RESULT_TTL  = Number(process.env.RESULT_TTL_MS || 24 * 3600 * 1000);
// An unbounded queue is a memory exhaustion primitive for anyone holding the
// token. Measured before this cap: 100 submissions sat with nothing draining
// and nothing reclaiming them, because the sweep only collects FINISHED jobs.
const MAX_QUEUE   = Number(process.env.MAX_QUEUE || 64);

if (!TOKEN) {
  console.error('WORKER_TOKEN is not set. Refusing to start.');
  console.error('An unauthenticated worker on a public address is a remote');
  console.error('command endpoint, whatever the argv discipline inside it.');
  process.exit(2);
}
if (TOKEN.length < 24) {
  console.error(`WORKER_TOKEN is ${TOKEN.length} characters. Refusing to start.`);
  console.error('Use at least 24. openssl rand -hex 32');
  process.exit(2);
}

fs.mkdirSync(WORK_ROOT, { recursive: true });
J.setRoot(WORK_ROOT);

// --- auth ------------------------------------------------------------------

/**
 * The credential in n8n is Header Auth with value `Bearer <WORKER_TOKEN>`, so
 * the word and the single space are stripped and the remainder compared. The
 * comparison is length-padded and timing safe: a plain === on a secret leaks
 * its prefix to anyone willing to measure.
 */
function authorized(req) {
  const h = req.headers['authorization'];
  if (typeof h !== 'string') return false;
  if (!h.startsWith('Bearer ')) return false;
  const given = Buffer.from(h.slice(7));
  const want = Buffer.from(TOKEN);
  if (given.length !== want.length) {
    // Still spend the comparison so length is not a free oracle.
    crypto.timingSafeEqual(want, want);
    return false;
  }
  return crypto.timingSafeEqual(given, want);
}

// --- job table -------------------------------------------------------------

/** id -> { id, type, status, result, error, exitCode, seconds, started, ended } */
const jobs = new Map();
const queue = [];
let running = 0;

function sweep() {
  const now = Date.now();
  for (const [id, j] of jobs) {
    if (j.ended && now - j.ended > RESULT_TTL) jobs.delete(id);
  }
}
setInterval(sweep, 600 * 1000).unref();

function runNext() {
  if (running >= CONCURRENCY) return;
  const j = queue.shift();
  if (!j) return;
  running++;
  j.status = 'running';
  j.started = Date.now();

  const finish = (patch) => {
    Object.assign(j, patch);
    j.ended = Date.now();
    j.seconds = Number(((j.ended - j.started) / 1000).toFixed(3));
    running--;
    setImmediate(runNext);
  };

  // The native escape hatch: seven jobs (scan_drop, read_text, exists, fs_ops,
  // http_download, multipart_upload, render_mark_full) do their work in Node
  // rather than by spawning ffmpeg.
  if (j.spec.native) {
    // execFile gets JOB_TIMEOUT; the native path had none at all, so a job that
    // never settled held the single concurrency slot for the life of the
    // process. This bounds the wait. It cannot interrupt a synchronous call
    // that has already blocked the event loop, which is why the fix for that
    // belongs in the jobs themselves (read_text and render_mark_full are now
    // async) and this is the backstop rather than the guard.
    let settled = false;
    const done = (patch) => { if (!settled) { settled = true; clearTimeout(timer); finish(patch); } };
    const timer = setTimeout(() => done({
      status: 'error',
      error: `job exceeded JOB_TIMEOUT of ${JOB_TIMEOUT} ms and was abandoned`,
      killed: true,
    }), JOB_TIMEOUT);
    timer.unref();
    Promise.resolve()
      .then(() => j.spec.native())
      .then(result => done({ status: 'done', result }))
      .catch(err => done({ status: 'error', error: String(err && err.message || err) }));
    return;
  }

  // execFile, not exec. No shell is involved at any point.
  //
  // Wrapped because a synchronous throw here (a malformed spec, a bad argv
  // type) escaped as an uncaught exception, killed the process, and left
  // `running` incremented, so even a restart-free recovery would have leaked
  // the single concurrency slot. Found by mutation testing the queue cap: the
  // right failure for a bad job is a failed job, never a dead server.
  try {
    execFile(j.spec.bin, j.spec.argv, {
      timeout: JOB_TIMEOUT,
      maxBuffer: 32 * 1024 * 1024,
      cwd: WORK_ROOT,
      windowsHide: true,
    }, (err, stdout, stderr) => {
        if (err) {
          // Surface the tail of stderr verbatim. Return Failure in TSWS 00 prints
          // whatever lands here, and rewriting an ffmpeg error into something
          // friendlier just means the real one never reaches the log.
          const tail = String(stderr || err.message || '').trim().split('\n').slice(-12).join('\n');
          return finish({
            status: 'error',
            error: tail || String(err.message || 'no error text'),
            exitCode: typeof err.code === 'number' ? err.code : null,
            killed: !!err.killed,
          });
        }
        let result = {};
        if (typeof j.spec.parse === 'function') {
          try {
            result = j.spec.parse(stdout, stderr);
          } catch (e) {
            return finish({
              status: 'error',
              error: `the job ran but its output could not be parsed: ${e.message}`,
            });
          }
        }
      finish({ status: 'done', result });
    });
  } catch (e) {
    finish({ status: 'error', error: `could not start the job: ${String(e && e.message || e)}` });
  }
}

// --- http ------------------------------------------------------------------

function send(res, code, obj) {
  const body = JSON.stringify(obj);
  res.writeHead(code, {
    'content-type': 'application/json',
    'content-length': Buffer.byteLength(body),
    'cache-control': 'no-store',
  });
  res.end(body);
}

function readBody(req) {
  return new Promise((resolve, reject) => {
    let n = 0;
    const chunks = [];
    req.on('data', c => {
      n += c.length;
      if (n > MAX_BODY) { req.destroy(); return reject(new Error('body too large')); }
      chunks.push(c);
    });
    req.on('end', () => resolve(Buffer.concat(chunks).toString('utf8')));
    req.on('error', reject);
  });
}

const server = http.createServer(async (req, res) => {
  let url;
  try { url = new URL(req.url, 'http://localhost'); }
  catch { return send(res, 400, { error: 'bad request line' }); }
  const p = url.pathname.replace(/\/+$/, '') || '/';

  // /health is the one unauthenticated route. It reveals the job type names and
  // nothing else: the sticky note in TSWS 00 tells an operator to compare that
  // list against 18 to tell a stale jobs.js from a current one, so it has to be
  // reachable before the token is known good. WORK_ROOT and the queue depth used
  // to be here too, which is a filesystem path and a load signal handed to
  // anyone who can reach the TLS terminator. They moved behind the token.
  if (req.method === 'GET' && p === '/health') {
    return send(res, 200, {
      ok: true,
      jobs: Object.keys(J.JOBS).sort(),
      job_count: Object.keys(J.JOBS).length,
    });
  }

  if (!authorized(req)) {
    res.setHeader('www-authenticate', 'Bearer');
    return send(res, 401, { error: 'unauthorized' });
  }

  if (req.method === 'POST' && p === '/jobs') {
    let payload;
    try {
      payload = JSON.parse(await readBody(req) || '{}');
    } catch (e) {
      return send(res, 400, { error: `body is not valid JSON: ${e.message}` });
    }
    const type = payload && payload.type;
    if (typeof type !== 'string' || !Object.prototype.hasOwnProperty.call(J.JOBS, type)) {
      return send(res, 400, {
        error: `unknown job type ${JSON.stringify(type)}. Known: ${Object.keys(J.JOBS).sort().join(', ')}`,
      });
    }
    let spec;
    try {
      // Validation happens HERE, at submit, synchronously. That is why a
      // non-202 means bad parameters and retrying will not help, which is
      // exactly what Submit Rejected in TSWS 00 tells the operator.
      spec = J.JOBS[type].build(payload.params || {});
    } catch (e) {
      const code = e && e.statusCode === 400 ? 400 : 500;
      return send(res, code, { error: String(e && e.message || e) });
    }
    if (queue.length >= MAX_QUEUE) {
      // 503 and not 400: the parameters were fine, the box is full. TSWS 00's
      // Accepted? treats any non-202 as a rejection and stops, which is the
      // correct behaviour here too.
      res.setHeader('retry-after', '60');
      return send(res, 503, { error: `queue is full (${queue.length}/${MAX_QUEUE})` });
    }
    const id = crypto.randomUUID();
    const j = {
      id, type, spec,
      status: 'queued',
      result: null, error: null, exitCode: null, seconds: null,
      queued_at: Date.now(), started: null, ended: null,
    };
    jobs.set(id, j);
    queue.push(j);
    setImmediate(runNext);
    // 202, not 200. Accepted? in TSWS 00 compares against 202 exactly.
    return send(res, 202, { id, type, status: 'queued' });
  }

  const m = /^\/jobs\/([A-Za-z0-9-]{1,64})$/.exec(p);
  if (req.method === 'GET' && m) {
    const j = jobs.get(m[1]);
    if (!j) return send(res, 404, { error: 'no such job (it may have expired)' });
    return send(res, 200, {
      id: j.id,
      type: j.type,
      status: j.status,
      ok: j.status === 'done',
      result: j.result,
      error: j.error,
      exitCode: j.exitCode,
      seconds: j.seconds,
    });
  }

  if (req.method === 'GET' && p === '/status') {
    return send(res, 200, {
      ok: true, work_root: WORK_ROOT, running,
      queued: queue.length, concurrency: CONCURRENCY, tracked: jobs.size,
    });
  }

  if (req.method === 'GET' && p === '/jobs') {
    return send(res, 200, {
      count: jobs.size,
      jobs: [...jobs.values()].map(j => ({ id: j.id, type: j.type, status: j.status })),
    });
  }

  return send(res, 404, { error: `no route for ${req.method} ${p}` });
});

server.headersTimeout = 65 * 1000;
server.requestTimeout = 0;   // a submit is small; a poll is smaller

/**
 * SIGTERM arrives on `systemctl stop` and on every deploy. Without a handler,
 * node's default action kills the process and the render at once and every job
 * id the caller is still polling vanishes with the in-memory table, so the unit
 * file's TimeoutStopSec was protecting nothing. Stop accepting, let the running
 * job finish inside the unit's stop timeout, then go.
 */
let shuttingDown = false;
function shutdown(signal) {
  if (shuttingDown) return;
  shuttingDown = true;
  console.log(`${signal} received. Not accepting new work; ${running} job(s) running.`);
  server.close();
  const deadline = Date.now() + Number(process.env.DRAIN_MS || 25000);
  const tick = setInterval(() => {
    if (running === 0 || Date.now() > deadline) {
      clearInterval(tick);
      console.log(running === 0 ? 'drained cleanly' : `stop deadline reached with ${running} running`);
      process.exit(0);
    }
  }, 250);
}

if (require.main === module) {
  process.on('SIGTERM', () => shutdown('SIGTERM'));
  process.on('SIGINT', () => shutdown('SIGINT'));
  server.listen(PORT, HOST, () => {
    console.log(`tsws render worker listening on ${HOST}:${PORT}`);
    console.log(`  work root   ${WORK_ROOT}`);
    console.log(`  job types   ${Object.keys(J.JOBS).length}`);
    console.log(`  concurrency ${CONCURRENCY}`);
  });
}

module.exports = { server, jobs, queue, authorized };
