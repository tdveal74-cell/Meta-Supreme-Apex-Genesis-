'use strict';
/**
 * The negative control, as a runnable check rather than a claim.
 *
 * "The tests detect the defects rather than merely agreeing with the fix" is the
 * load bearing sentence in DEPLOY.md, and until this script existed it was
 * testimony: the unfixed engine lived only on Drive, so nobody reading this
 * repository could reproduce it.
 *
 * reference/jobs.drive-2026-08-07.js is the file as recovered from Drive, byte
 * for byte. This runs the same jobs.test.js against it and requires that it
 * FAILS. A suite that passes against known-defective code is worth nothing, and
 * that is not a hypothetical here: the first version of the scan_drop test did
 * exactly that, because the harness never awaited it.
 *
 *   node negative-control.js
 */
const assert = require('assert');
const crypto = require('crypto');
const { execFileSync } = require('child_process');
const fs = require('fs');
const os = require('os');
const path = require('path');

// The sha256 as downloaded from Drive file 1LhJi3m8vYPTpRmgeYvnDjPYBHZF1H5ts on
// 2026-09-11, matching Drive's own reported size of 42,848 bytes.
const EXPECTED_SHA = '6ed3109ab220cb986e7c33040e90fda4c103cf8afa5ee48137c7185ca55ecdae';
const EXPECTED_BYTES = 42848;

// Defects the fixture is known to carry, so the control is checked against a
// floor rather than against "some tests failed".
const MIN_FAILURES = 10;

const fixture = path.join(__dirname, 'reference', 'jobs.drive-2026-08-07.js');
const bytes = fs.readFileSync(fixture);
const sha = crypto.createHash('sha256').update(bytes).digest('hex');

console.log('fixture : reference/jobs.drive-2026-08-07.js');
console.log('bytes   :', bytes.length, bytes.length === EXPECTED_BYTES ? 'OK' : 'MISMATCH');
console.log('sha256  :', sha);
assert.strictEqual(bytes.length, EXPECTED_BYTES, 'the fixture is not the recovered file');
assert.strictEqual(sha, EXPECTED_SHA, 'the fixture is not the recovered file');

// Prove the fixture really is pre-audit, independently of running anything.
const src = bytes.toString('utf8');
const absent = ['normalizeChain', 'force_original_aspect_ratio', 'setsar',
                'scanned_depth', 'skipped_done', 'normalized_to'];
for (const marker of absent) {
  assert.strictEqual(src.includes(marker), false,
    `the fixture unexpectedly contains ${marker}; it is not the pre-audit copy`);
}
assert.ok(src.includes('afade=t=out:st='), 'the fixture should still carry the afade pair');
console.log('markers :', absent.length, 'audit markers absent, afade pair present. Pre-audit copy confirmed.');

const tmp = fs.mkdtempSync(path.join(os.tmpdir(), 'tsws-negative-control-'));
try {
  // The pre-audit file exports no test surface. Shim only the missing names, so
  // the graph tests can run and fail on their assertions rather than on a
  // require error, which would prove nothing about the code.
  fs.writeFileSync(path.join(tmp, 'jobs.js'), src.replace(
    'module.exports = { JOBS, BadJob, safePath, existingPath, num, oneOf, setRoot, getRoot, PRESETS };',
    'function gainEnvelope(){ return null; }\n' +
    'function normalizeChain(){ return \'\'; }\n' +
    'function isStill(){ return false; }\n' +
    'module.exports = { JOBS, BadJob, safePath, existingPath, num, oneOf, setRoot, getRoot,\n' +
    '                   PRESETS, gainEnvelope, normalizeChain, isStill };'));
  fs.copyFileSync(path.join(__dirname, 'jobs.test.js'), path.join(tmp, 'jobs.test.js'));

  let out = '', failed = false;
  try {
    out = execFileSync(process.execPath, ['jobs.test.js'],
      { cwd: tmp, encoding: 'utf8', stdio: ['ignore', 'pipe', 'pipe'] });
  } catch (e) {
    failed = true;
    out = String(e.stdout || '') + String(e.stderr || '');
  }

  const m = /(\d+) passed, (\d+) failed/.exec(out);
  const passed = m ? Number(m[1]) : 0;
  const failures = m ? Number(m[2]) : 0;
  console.log(`control : ${passed} passed, ${failures} failed against the unfixed engine`);

  assert.ok(failed, 'THE SUITE PASSED AGAINST THE KNOWN-DEFECTIVE ENGINE. The tests prove nothing.');
  assert.ok(failures >= MIN_FAILURES,
    `only ${failures} tests failed against the unfixed engine; expected at least ${MIN_FAILURES}`);

  console.log('\nNEGATIVE CONTROL PASSED: the suite detects the defects.');
} finally {
  fs.rmSync(tmp, { recursive: true, force: true });
}
