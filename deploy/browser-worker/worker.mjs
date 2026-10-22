/** Private DEVON Chromium worker. Network must ALSO be disabled by its container. */
import { createServer } from 'node:http';
import { ChromePipe } from './chrome-pipe.mjs';
import { mkdirSync, writeFileSync, chmodSync, existsSync, readdirSync } from 'node:fs';
import { join } from 'node:path';
import { randomUUID, timingSafeEqual, createHash } from 'node:crypto';
import { DatabaseSync } from 'node:sqlite';
import { pathToFileURL } from 'node:url';

const UUID = /^[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}$/;
const RESPONSE_POLICY = 'deny-all-v1';
const HOST = /^(?=.{1,253}$)(?:[a-z0-9](?:[a-z0-9-]{0,61}[a-z0-9])?\.)+[a-z](?:[a-z0-9-]{0,61}[a-z0-9])?$/;

export class BrowserWorker {
  constructor({ owner, key, root, chromium = '/usr/bin/chromium', browserFactory, maxSessions = 2, proxy = null, allowedHosts = [] }) {
    if (!UUID.test(owner) || typeof key !== 'string' || key.length < 32 || /[\r\n]/.test(key)) throw new Error('worker owner/auth configuration refused');
    if (!Array.isArray(allowedHosts) || allowedHosts.length > 20 || new Set(allowedHosts).size !== allowedHosts.length
      || allowedHosts.some(host => typeof host !== 'string' || !HOST.test(host))) throw new Error('canonical public hosts required');
    if (proxy && !allowedHosts.length) throw new Error('proxy hosts missing');
    this.proxy = proxy; this.allowedHosts = allowedHosts;
    this.owner = owner; this.key = key; this.root = root; this.maxSessions = maxSessions;
    mkdirSync(root, { recursive: true, mode: 0o700 }); chmodSync(root, 0o700);
    this.db = new DatabaseSync(join(root, 'requests.sqlite'));
    this.db.exec('PRAGMA journal_mode=WAL; PRAGMA synchronous=FULL; CREATE TABLE IF NOT EXISTS requests (id TEXT PRIMARY KEY, digest TEXT NOT NULL, response TEXT); CREATE TABLE IF NOT EXISTS sessions (id TEXT PRIMARY KEY, state TEXT NOT NULL)');
    this.sessions = new Map(); this.busy = false;
    this.factory = browserFactory || (profile => new ChromePipe(chromium, profile, { proxy, allowedHosts }));
  }
  authenticated(value) {
    const supplied = Buffer.from(value || ''); const expected = Buffer.from('Bearer ' + this.key);
    return supplied.length === expected.length && timingSafeEqual(supplied, expected);
  }
  async action(payload) {
    if (!payload || typeof payload !== 'object' || Array.isArray(payload)) throw new Error('bad request');
    const allowed = new Set(['protocol','owner_id','request_id','approval_binding','allowed_hosts','action','session_id','url']);
    if (Object.keys(payload).some(k => !allowed.has(k)) || payload.protocol !== 'devon-browser-v1' || payload.owner_id !== this.owner
      || !UUID.test(payload.session_id) || !/^REQ-[A-Z0-9]{1,64}$/.test(payload.request_id)
      || !/^[a-f0-9]{64}$/.test(payload.approval_binding) || !Array.isArray(payload.allowed_hosts)
      || payload.allowed_hosts.length > 100 || payload.allowed_hosts.some(h => typeof h !== 'string' || h.length > 253)
      || !['open','navigate','snapshot','close'].includes(payload.action)
      || (payload.action !== 'navigate' && 'url' in payload)) throw new Error('bad request');
    const canonical = Object.fromEntries(Object.keys(payload).sort().map(k => [k, payload[k]]));
    const digest = createHash('sha256').update(JSON.stringify(canonical)).digest('hex');
    const existing = this.db.prepare('SELECT digest, response FROM requests WHERE id=?').get(payload.request_id);
    if (existing) {
      if (existing.digest !== digest) throw new Error('request binding conflict');
      return existing.response ? JSON.parse(existing.response) : this.receipt(payload, 'unknown');
    }
    if (this.busy) throw new Error('worker busy');
    // Durable claim BEFORE browser action. Crash without response stays unknown;
    // it never replays, even after process restart or a lost HTTP response.
    if (this.db.prepare('SELECT count(*) AS n FROM requests').get().n >= 10000) throw new Error('receipt capacity reached');
    this.db.prepare('INSERT INTO requests(id,digest) VALUES (?,?)').run(payload.request_id, digest);
    this.busy = true;
    let state = 'unknown'; let snapshotReceipt; let page;
    try {
      if (payload.action === 'navigate') {
        const browser = this.sessions.get(payload.session_id);
        if (!this.proxy || !browser || JSON.stringify(payload.allowed_hosts) !== JSON.stringify(this.allowedHosts)) state = 'refused';
        else { const url = await browser.navigate(payload.url); page = { url, scripts_disabled: true }; state = 'completed'; }
      } else if (payload.action === 'open') {
        if ((this.proxy && JSON.stringify(payload.allowed_hosts) !== JSON.stringify(this.allowedHosts)) || this.db.prepare('SELECT count(*) AS n FROM sessions').get().n >= this.maxSessions || this.db.prepare('SELECT id FROM sessions WHERE id=?').get(payload.session_id)) state = 'refused';
        else {
          this.db.prepare('INSERT INTO sessions(id,state) VALUES (?,?)').run(payload.session_id, 'opening');
          const profile = join(this.root, this.owner, payload.session_id, 'profile');
          mkdirSync(profile, { recursive: true, mode: 0o700 });
          const browser = this.factory(profile); this.sessions.set(payload.session_id, browser);
          await browser.open(); state = 'completed';
          this.db.prepare('UPDATE sessions SET state=? WHERE id=?').run('open', payload.session_id);
        }
      } else {
        const browser = this.sessions.get(payload.session_id);
        if (!browser) state = 'refused';
        else if (payload.action === 'snapshot') {
          const directory = join(this.root, this.owner, payload.session_id, 'snapshots');
          if (existsSync(directory) && readdirSync(directory).length >= 20) throw new Error('snapshot capacity reached');
          const png = await browser.snapshot();
          if (this.proxy) page = await browser.describe();
          const receipt = randomUUID(); snapshotReceipt = receipt;
          mkdirSync(directory, { recursive: true, mode: 0o700 });
          writeFileSync(join(directory, receipt + '.png'), png, { flag: 'wx', mode: 0o600 });
          state = 'completed';
        } else {
          await browser.close(); this.sessions.delete(payload.session_id); state = 'completed';
          this.db.prepare('UPDATE sessions SET state=? WHERE id=?').run('closed', payload.session_id);
        }
      }
    } catch {
      const browser = this.sessions.get(payload.session_id);
      try {
        if (payload.action === 'close' && browser) throw new Error('close already attempted; reconcile cleanup');
        if (browser) await browser.close(); this.sessions.delete(payload.session_id);
      }
      catch { /* retain unreachable session; do not claim cleanup succeeded */ }
    } finally { this.busy = false; }
    const response = this.receipt(payload, state);
    if (page && state === 'completed') response.page = page;
    if (snapshotReceipt && state === 'completed') response.receipt_id = snapshotReceipt;
    this.db.prepare('UPDATE requests SET response=? WHERE id=?').run(JSON.stringify(response), payload.request_id);
    return response;
  }
  receipt(p, state) { return { protocol: p.protocol, owner_id: this.owner, request_id: p.request_id, session_id: p.session_id,
    action: p.action, state, receipt_id: randomUUID(), isolation: 'dedicated-owner-context', network_policy: this.proxy ? 'public-proxy-v1' : RESPONSE_POLICY }; }
  async shutdown() { await Promise.allSettled([...this.sessions.values()].map(async browser => browser.close())); this.sessions.clear(); this.db.close(); }
}

export function handlerFor(worker) {
  return async (req, res) => {
    const reply = (status, value) => { res.writeHead(status, { 'Content-Type': 'application/json' }); res.end(JSON.stringify(value)); };
    if (!worker.authenticated(req.headers.authorization)) return reply(401, { error: 'authentication required' });
    if (req.method !== 'POST' || req.url !== '/v1/action') return reply(404, { error: 'not found' });
    try {
      const chunks = []; let bytes = 0;
      for await (const chunk of req) { bytes += chunk.length; if (bytes > 16_384) throw new Error('too large'); chunks.push(chunk); }
      reply(200, await worker.action(JSON.parse(Buffer.concat(chunks).toString())));
    } catch { reply(409, { error: 'browser request refused; reconcile request before retry' }); }
  };
}

export function serve(worker, socket) {
  if (socket !== '/run/devon-browser/worker.sock') throw new Error('private socket required');
  const server = createServer(handlerFor(worker));
  server.requestTimeout = 15000; server.headersTimeout = 10000;
  server.listen(socket, () => chmodSync(socket, 0o600));
  return server;
}

if (process.argv[1] && import.meta.url === pathToFileURL(process.argv[1]).href) {
  if (process.env.DEVON_BROWSER_WORKER_ENABLED !== '1' || process.env.DEVON_BROWSER_NETWORK_MODE !== 'deny-all') throw new Error('worker disabled or network isolation mode missing');
  if (readdirSync('/sys/class/net').some(name => name !== 'lo')) throw new Error('deny-all network namespace required');
  const worker = new BrowserWorker({ owner: process.env.DEVON_BROWSER_SESSION_OWNER_ID, key: process.env.DEVON_BROWSER_SESSION_KEY,
    root: '/var/lib/devon-browser', chromium: '/usr/bin/chromium' });
  const server = serve(worker, '/run/devon-browser/worker.sock');
  server.on('error', async () => {
    console.error('Private browser socket unavailable. Worker remains disabled. With worker stopped, an operator must reconcile owner/type/live-peer and remove only a verified stale owned socket; never unlink files or live peers.');
    await worker.shutdown(); process.exit(1);
  });
  const stop = async () => { server.close(); await worker.shutdown(); process.exit(0); };
  process.on('SIGTERM', stop); process.on('SIGINT', stop);
}
