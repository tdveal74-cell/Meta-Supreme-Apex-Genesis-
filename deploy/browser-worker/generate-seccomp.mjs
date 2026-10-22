// Pinned current Moby default plus documented namespace and Chromium chroot rules.
import { readFileSync, writeFileSync } from 'node:fs';
import { createHash } from 'node:crypto';
const baseURL = new URL('./seccomp-moby-base.json', import.meta.url);
const bytes = readFileSync(baseURL);
const expected = '6416b47770785a41ac59073cdc77d9fe98517df2799dc83ef207e622de3053f6';
if (createHash('sha256').update(bytes).digest('hex') !== expected) throw new Error('pinned Moby profile changed');
const profile = JSON.parse(bytes);
profile.syscalls.push({ comment: 'Allow create user namespaces (official Playwright Docker recommendation)',
  names: ['clone', 'setns', 'unshare'], action: 'SCMP_ACT_ALLOW', args: [], includes: {}, excludes: {} });
profile.syscalls.push({ comment: 'Chromium ChrootToSelfFdinfo sandbox confinement; no initial CAP_SYS_CHROOT granted',
  names: ['chroot'], action: 'SCMP_ACT_ALLOW', args: [], includes: {}, excludes: {} });
writeFileSync(new URL('./seccomp-browser.json', import.meta.url), JSON.stringify(profile, null, 2) + '\n');
