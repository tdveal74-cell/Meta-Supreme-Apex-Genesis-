/** Candidate only. Launcher must install namespace OUTPUT isolation before this starts. */
import {lstatSync,readFileSync,readlinkSync} from 'node:fs';
import {privateProxy} from './chrome-pipe.mjs';
import {BrowserWorker,serve} from './worker.mjs';
if (process.env.DEVON_BROWSER_PROXY_CANDIDATE_ENABLED !== '1' || process.env.DEVON_BROWSER_NETWORK_MODE !== 'public-proxy-v1') throw new Error('proxy candidate disabled');
const receiptPath = '/run/devon-network/isolation.json';
const stat = lstatSync(receiptPath);
if (!stat.isFile() || stat.uid !== 0 || (stat.mode & 0o222)) throw new Error('root isolation receipt required');
const receipt = JSON.parse(readFileSync(receiptPath, 'utf8'));
const proxy = process.env.DEVON_BROWSER_PROXY;
const hosts = (process.env.DEVON_BROWSER_ALLOWED_HOSTS || '').split(',');
if (!privateProxy(proxy) || receipt.policy !== 'public-proxy-v1' || receipt.netns !== readlinkSync('/proc/self/ns/net')
  || receipt.proxy !== proxy || JSON.stringify(receipt.allowed_hosts) !== JSON.stringify(hosts)
  || receipt.output_rules !== 'proxy-tcp3128-only-ipv6-drop' || !Number.isFinite(receipt.verified_at)
  || Date.now() - receipt.verified_at > 300000 || receipt.verified_at > Date.now()) throw new Error('namespace isolation unproven');
const worker = new BrowserWorker({owner:process.env.DEVON_BROWSER_SESSION_OWNER_ID,key:process.env.DEVON_BROWSER_SESSION_KEY,
 root:'/var/lib/devon-browser',proxy:process.env.DEVON_BROWSER_PROXY,allowedHosts:(process.env.DEVON_BROWSER_ALLOWED_HOSTS||'').split(',')});
const server=serve(worker,'/run/devon-browser/worker.sock');
server.on('error',async()=>{await worker.shutdown();process.exit(1);});
const stop=async()=>{server.close();await worker.shutdown();process.exit(0);};process.on('SIGTERM',stop);process.on('SIGINT',stop);
