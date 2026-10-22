// Real sandboxed Chromium only, offline blank page; no external provider.
import { mkdtempSync, rmSync } from 'node:fs';
import { tmpdir } from 'node:os';
import { join } from 'node:path';
import { rendererSandboxEvidence } from './sandbox-proof.mjs';
import { ChromePipe } from './chrome-pipe.mjs';
const root = mkdtempSync(join(tmpdir(), 'devon-chrome-'));
const browser = new ChromePipe(process.env.DEVON_TEST_CHROMIUM || '/usr/bin/chromium', root);
try {
  await browser.open(); const png = await browser.snapshot();
  if (png.subarray(0, 8).toString('hex') !== '89504e470d0a1a0a') throw new Error('invalid PNG');
  console.log(JSON.stringify({ blank_open: true, png_bytes: png.length, sandbox_disabled: false, ...rendererSandboxEvidence() }));
} finally { await browser.close(); rmSync(root, { recursive: true, force: true }); }
