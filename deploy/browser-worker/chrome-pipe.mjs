import { spawn } from 'node:child_process';
import { isIP } from 'node:net';
export function privateProxy(value) {
  try { const url = new URL(value); const ip = url.hostname; const parts = ip.split('.').map(Number);
    return url.protocol === 'http:' && url.port === '3128' && !url.username && !url.password && url.pathname === '/' && !url.search && !url.hash
      && isIP(ip) === 4 && (parts[0] === 10 || (parts[0] === 172 && parts[1] >= 16 && parts[1] <= 31) || (parts[0] === 192 && parts[1] === 168));
  } catch { return false; }
}

export class ChromePipe {
  constructor(executable, profile, { proxy = null, allowedHosts = [] } = {}) {
    this.allowedHosts = allowedHosts; this.events = new Map(); this.proxy = proxy;
    if (proxy && !privateProxy(proxy)) throw new Error('fixed private proxy required');
    this.sequence = 0; this.pending = new Map(); this.buffer = ''; this.closed = false;
    this.process = spawn(executable, ['--headless=new', '--remote-debugging-pipe',
      '--no-first-run', '--no-default-browser-check', '--disable-background-networking',
      '--disable-component-update', '--disable-sync', '--disable-extensions',
      '--disable-domain-reliability', '--disable-client-side-phishing-detection',
      '--metrics-recording-only', `--host-resolver-rules=MAP * ~NOTFOUND${proxy ? ',EXCLUDE ' + new URL(proxy).hostname : ''}`,
      `--proxy-server=${proxy || 'http://127.0.0.1:9'}`, '--proxy-bypass-list=<-loopback>',
      '--force-webrtc-ip-handling-policy=disable_non_proxied_udp', '--disable-quic',
      `--user-data-dir=${profile}`, 'about:blank'],
      { detached: true, stdio: ['ignore', 'ignore', 'ignore', 'pipe', 'pipe'], env: { PATH: '/usr/bin:/bin', HOME: profile, LANG: 'C.UTF-8' } });
    this.process.stdio[4].on('data', data => {
      this.buffer += data.toString();
      if (this.buffer.length > 12_000_000) return void this.close().catch(() => {});
      let end;
      while ((end = this.buffer.indexOf('\0')) !== -1) {
        const raw = this.buffer.slice(0, end); this.buffer = this.buffer.slice(end + 1);
        try {
          const response = JSON.parse(raw);
          if (response.method) {
            const key = response.sessionId + ':' + response.method;
            for (const listener of this.events.get(key) || []) listener(response.params);
            if (response.method === 'Fetch.requestPaused' && response.sessionId === this.sessionId) {
              const allowed = this.permittedURL(response.params?.request?.url);
              void this.command(allowed ? 'Fetch.continueRequest' : 'Fetch.failRequest',
                { requestId: response.params.requestId, ...(allowed ? {} : { errorReason: 'BlockedByClient' }) }, this.sessionId).catch(() => {});
            }
          }
          const pending = this.pending.get(response.id);
          if (pending) { this.pending.delete(response.id); clearTimeout(pending.timer);
            response.error ? pending.reject(new Error('browser command refused')) : pending.resolve(response.result); }
        } catch { void this.close().catch(() => {}); }
      }
    });
    const stopped = () => { this.closed = true; for (const p of this.pending.values()) { clearTimeout(p.timer); p.reject(new Error('browser stopped')); } this.pending.clear(); };
    this.process.stdio[3].on('error', stopped); this.process.stdio[4].on('error', stopped);
    this.process.on('exit', stopped); this.process.on('error', stopped);
  }
  command(method, params = {}, sessionId) {
    if (this.closed) return Promise.reject(new Error('browser stopped'));
    const id = ++this.sequence;
    return new Promise((resolve, reject) => {
      const timer = setTimeout(() => { this.pending.delete(id); void this.close().catch(() => {}); reject(new Error('browser timeout')); }, 8000);
      this.pending.set(id, { resolve, reject, timer });
      this.process.stdio[3].write(JSON.stringify({ id, method, params, ...(sessionId ? { sessionId } : {}) }) + '\0');
    });
  }
  async open() {
    const { targetInfos } = await this.command('Target.getTargets');
    const target = targetInfos.find(t => t.type === 'page' && t.url === 'about:blank');
    if (!target) throw new Error('blank page missing');
    const { sessionId } = await this.command('Target.attachToTarget', { targetId: target.targetId, flatten: true });
    this.sessionId = sessionId;
    await this.command('Network.enable', {}, sessionId);
    await this.command('Network.setBlockedURLs', { urls: this.proxy ? [] : ['*'] }, sessionId);
    if (this.proxy) {
      await this.command('Network.setBypassServiceWorker', { bypass: true }, sessionId);
      await this.command('Emulation.setScriptExecutionDisabled', { value: true }, sessionId);
      await this.command('Fetch.enable', { patterns: [{ urlPattern: '*', requestStage: 'Request' }] }, sessionId);
    }
    await this.command('Page.enable', {}, sessionId);
  }
  permittedURL(value) {
    try { const url = new URL(value); return url.protocol === 'https:' && !url.username && !url.password
      && (!url.port || url.port === '443') && this.allowedHosts.includes(url.hostname)
      && !url.hostname.endsWith('.') && !/[\r\n]/.test(value); } catch { return false; }
  }
  waitEvent(method) {
    const key = this.sessionId + ':' + method;
    return new Promise((resolve, reject) => {
      const listener = value => { clearTimeout(timer); this.events.delete(key); resolve(value); };
      const timer = setTimeout(() => { this.events.delete(key); reject(new Error('browser navigation unproven')); }, 8000);
      this.events.set(key, [listener]);
    });
  }
  async navigate(url) {
    if (!this.proxy || !this.permittedURL(url)) throw new Error('navigation refused');
    const loaded = this.waitEvent('Page.loadEventFired');
    // Attach rejection immediately; no lost-event or unhandled timeout window.
    const both = Promise.all([this.command('Page.navigate', { url }, this.sessionId), loaded]);
    const [result] = await both;
    if (result.errorText) throw new Error('navigation refused');
    const { frameTree } = await this.command('Page.getFrameTree', {}, this.sessionId);
    if (!this.permittedURL(frameTree.frame.url)) throw new Error('redirect refused');
    return frameTree.frame.url;
  }
  async describe() {
    const { frameTree } = await this.command('Page.getFrameTree', {}, this.sessionId);
    const url = frameTree.frame.url;
    if (url !== 'about:blank' && !this.permittedURL(url)) throw new Error('page refused');
    const result = await this.command('Runtime.evaluate', { expression: "document.body ? document.body.innerText.slice(0, 8000) : ''", returnByValue: true }, this.sessionId);
    return { url, text: typeof result.result?.value === 'string' ? result.result.value.slice(0, 8000) : '', untrusted_page_content: true, scripts_disabled: true };
  }
  async snapshot() {
    const result = await this.command('Page.captureScreenshot', { format: 'png', captureBeyondViewport: false }, this.sessionId);
    if (typeof result.data !== 'string' || result.data.length > 8_000_000) throw new Error('snapshot oversized');
    return Buffer.from(result.data, 'base64');
  }
  close() {
    if (!this.closing) this.closing = this._closeGroup();
    return this.closing;
  }
  groupAlive() {
    const pid = this.process.pid;
    if (!Number.isInteger(pid) || pid <= 1) return false;
    try { process.kill(-pid, 0); return true; }
    catch (error) { if (error.code === 'ESRCH') return false; throw error; }
  }
  async _closeGroup() {
    // detached:true created this group from OUR spawn; no caller-supplied PID.
    // Container --init reaps orphaned descendants, including killed renderers.
    if (this.groupAlive()) {
      try { process.kill(-this.process.pid, 'SIGKILL'); }
      catch (error) { if (error.code !== 'ESRCH') throw error; }
    }
    const deadline = Date.now() + 2000;
    while (Date.now() < deadline) {
      const mainExited = this.process.exitCode !== null || this.process.signalCode !== null || !this.process.pid;
      if (mainExited && !this.groupAlive()) { this.closed = true; return; }
      await new Promise(resolve => setTimeout(resolve, 25));
    }
    throw new Error('browser process group termination unproven');
  }
}

