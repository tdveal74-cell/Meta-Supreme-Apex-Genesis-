// DEVON Build 13: the Pulse. Deterministic self-report over every organ.
// Reads never touch approval_queue (its rows carry plaintext decision tokens).
//
// MIRROR of the "Compose Pulse" Code node in the Build 13 heartbeat workflow,
// id EEDrp2jLlw2Ssd5b on the VPS. n8n cannot import from this repository,
// so the live node holds its own copy and this file is the reviewable one. If
// the two drift, the live one is what beats.
//
// THE DRIFT IS THIS HEADER AND NOTHING ELSE. The live copy names the workflow
// by its display name, which carries an em dash; this repository bans that
// character in what it ships, so the two lines above name the workflow by id
// and this paragraph does not exist in the live node. From the first const
// below to the last line of the file, the two are byte identical: measured on
// 2026-09-16 by diffing this file against the jsCode of version 738d6d58,
// 12013 bytes each and no differing line. Aligning the headers as well would
// cost a republish of an active workflow for a comment, and the version
// published on 2026-09-16 is the one the 10:00Z beat has to prove.
const BEAT_INTERVAL_H = 6;
const MISSED_BEAT_H = 7.5;
const EMAIL_EVERY_H = 22;
const STUCK_JOB_H = 24;
// The Build 12 feeder runs ONCE A DAY, on Daily 02:00 America/New_York. Until
// 2026-09-16 this file carried UNFED_MIN = 40 and called any COMPLETED job the
// feeder had not carried within forty minutes a finding named feeder_silent.
// That threshold matched nothing. It was wrong in both directions:
//
//   FALSE POSITIVE, every time. A job completing at 03:00 ET is not late at
//   03:40, it is waiting for a slot that is twenty three hours away, and the
//   old rule alerted on every beat until the feeder ran. That happened for real
//   on 2026-09-16: the 04:00:15Z beat reported feeder_silent against the VPS
//   cutover proof job while the feeder was armed, correct and simply not due.
//
//   FALSE NEGATIVE, in the case the finding was named for. Its own text said
//   "feeder may be down", but it could only fire when a COMPLETED job happened
//   to be waiting. A feeder that died on a quiet week was invisible to it.
//
// So the one finding is split in two, and each now means one thing. Neither
// reads a wall clock guess; both read the feed log's own newest fed_at.
const FEEDER_PERIOD_H = 24;
const FEEDER_GRACE_H = 2;
const EXPIRY_H = 72;
const EXPIRY_SOON_H = 24;
const RESOLVE_GRACE_H = 4;
const REFLECTION_FRESH_H = 26;
const now = new Date();
const nowIso = now.toISOString();
const nowMs = now.getTime();
function rowsOf(name, field) {
  const out = [];
  for (const it of $(name).all()) {
    const r = it.json || {};
    if (r && r[field]) { out.push(r); }
  }
  return out;
}
function hoursAgo(iso) {
  const t = Date.parse(String(iso || ''));
  if (Number.isNaN(t)) { return null; }
  return (nowMs - t) / 3600000;
}
// A timestamp only counts if it parses and is not in the future. Same guard the
// beat anchors use, for the same reason: one malformed or forged row must never
// silence a watchdog.
function stampOf(iso) {
  const t = Date.parse(String(iso || ''));
  if (Number.isNaN(t)) { return null; }
  if (t > nowMs + 3600000) { return null; }
  return t;
}
function countBy(rows, field) {
  const m = {};
  for (const r of rows) { const k = String(r[field] || 'unknown'); m[k] = (m[k] || 0) + 1; }
  return m;
}
function fmtCounts(m) {
  const parts = [];
  for (const k of Object.keys(m).sort()) { parts.push(k + ' ' + m[k]); }
  return parts.length ? parts.join(', ') : 'none';
}
const jobs = rowsOf('Read Jobs', 'intent_id');
const feed = rowsOf('Read Feed', 'intent_id');
const soul = rowsOf('Read Soul Log', 'intent_id');
const beats = rowsOf('Read Beats', 'beat_at');
const TERMINAL = { COMPLETED: true, CANCELLED: true };
const jobsByState = countBy(jobs, 'state');
const stuckJobs = [];
for (const j of jobs) {
  if (TERMINAL[String(j.state)]) { continue; }
  const h = hoursAgo(j.updatedAt || j.createdAt);
  if (h !== null && h > STUCK_JOB_H) { stuckJobs.push(String(j.intent_id) + ' (' + String(j.state) + ', ' + Math.round(h) + 'h)'); }
}
const fedIds = {};
for (const f of feed) { fedIds[String(f.intent_id)] = true; }
const feedByDecision = countBy(feed, 'gate_decision');
const malformed = [];
for (const f of feed) {
  const ws = Number(f.webhook_status);
  if ((ws === 200 || ws === 201) && !String(f.gate_decision || '').trim()) { malformed.push(String(f.intent_id)); }
}
// When the feeder last ran, read off the feed log rather than assumed.
let lastFedTs = null;
for (const f of feed) {
  const t = stampOf(f.fed_at);
  if (t === null) { continue; }
  if (lastFedTs === null || t > lastFedTs) { lastFedTs = t; }
}
const completed = [];
for (const j of jobs) { if (String(j.state) === 'COMPLETED') { completed.push(j); } }
const feederQuietH = lastFedTs === null ? null : (nowMs - lastFedTs) / 3600000;
// DOWN: the feeder has missed its own daily slot. This does not need a job to
// be waiting, which is the whole point: a dead feeder on a quiet week still
// shows. It does need at least one COMPLETED job to have existed ever, so a
// genuinely empty estate is not alarmed at forever.
const feederDown = completed.length > 0 && (lastFedTs === null || feederQuietH > FEEDER_PERIOD_H + FEEDER_GRACE_H);
// SKIPPED: the feeder RAN after this job completed and still did not carry it.
// That is a defect rather than a wait, and it surfaces on the first beat after
// the feeder's own slot, which is sooner than any wall clock threshold could be
// without also crying wolf.
const skipped = [];
for (const j of completed) {
  if (fedIds[String(j.intent_id)]) { continue; }
  const t = stampOf(j.updatedAt || j.createdAt);
  if (t === null) { continue; }
  if (lastFedTs !== null && lastFedTs > t) { skipped.push(String(j.intent_id)); }
}
const soulByState = countBy(soul, 'state');
const expiringSoon = [];
const overdue = [];
for (const p of soul) {
  if (String(p.state) !== 'PROPOSED') { continue; }
  const h = hoursAgo(p.proposed_at);
  if (h === null) { continue; }
  const left = EXPIRY_H - h;
  if (left <= 0 - RESOLVE_GRACE_H) { overdue.push(String(p.intent_id)); }
  else if (left <= EXPIRY_SOON_H) { expiringSoon.push(String(p.intent_id) + ' (' + Math.round(left) + 'h left)'); }
}
// Anchor selection is validated: a row only counts if its beat_at parses as
// a real timestamp no more than 1h in the future. One malformed or forged
// row (the free-form reflection writer is the likeliest source) must never
// silence missed_beat, the daily email clock, or the reflection watch.
function beatTs(b) { return stampOf(b.beat_at); }
let lastPulse = null;
let lastPulseTs = null;
let lastEmailed = null;
let lastEmailedTs = null;
let lastReflection = null;
let lastReflectionTs = null;
for (const b of beats) {
  const t = beatTs(b);
  if (t === null) { continue; }
  if (String(b.kind) === 'pulse') {
    if (lastPulseTs === null || t > lastPulseTs) { lastPulse = b; lastPulseTs = t; }
    if (String(b.emailed) === 'yes' && (lastEmailedTs === null || t > lastEmailedTs)) { lastEmailed = b; lastEmailedTs = t; }
  }
  if (String(b.kind) === 'reflection' && (lastReflectionTs === null || t > lastReflectionTs)) { lastReflection = b; lastReflectionTs = t; }
}
const firstBeat = !lastPulse;
// Findings carry a stable key so a persisting condition alerts once when it
// first appears and then rides the daily pulse instead of emailing every beat.
const findings = [];
function finding(key, alert, text) { findings.push({ key: key, alert: alert, text: text }); }
if (stuckJobs.length) { finding('stuck_jobs', true, 'Jobs stuck non-terminal beyond ' + STUCK_JOB_H + 'h: ' + stuckJobs.join(', ')); }
if (feederDown) {
  finding('feeder_down', true, 'The Build 12 feeder has not run in ' + (feederQuietH === null ? 'any window I can see, and its log carries no readable fed_at at all' : Math.round(feederQuietH) + 'h') + '. It runs daily at 02:00 America/New_York, so anything past ' + (FEEDER_PERIOD_H + FEEDER_GRACE_H) + 'h is a missed slot. ' + completed.length + ' COMPLETED job(s) are in the ledger. Check its executions.');
}
if (skipped.length) { finding('feeder_skipped', true, 'The feeder ran AFTER these COMPLETED jobs and did not carry them, so they are skipped rather than waiting for their slot: ' + skipped.join(', ')); }
if (malformed.length) { finding('malformed_feed', true, 'Feed rows with HTTP 200 but no readable gate decision (terminal and invisible to the committer; repair per runbook): ' + malformed.join(', ')); }
if (overdue.length) { finding('soul_overdue', true, 'Soul proposals still open past ' + (EXPIRY_H + RESOLVE_GRACE_H) + 'h: ' + overdue.join(', ') + ' - the committer may be holding them inside its 96h close-by-absence window or retrying a failing commit (check the commit-log note); if neither, the resolve lane is stalled'); }
if (lastPulse) {
  const hb = hoursAgo(lastPulse.beat_at);
  if (hb !== null && hb > MISSED_BEAT_H) { finding('missed_beat', true, 'I missed at least one beat: my previous pulse was ' + Math.round(hb) + 'h ago (expected every ' + BEAT_INTERVAL_H + 'h)'); }
}
if (expiringSoon.length) { finding('cards_expiring', false, 'Approval cards that expire within ' + EXPIRY_SOON_H + 'h and still need your decision: ' + expiringSoon.join(', ')); }
const reflH = lastReflection ? hoursAgo(lastReflection.beat_at) : null;
if (!lastReflection || reflH === null || reflH > REFLECTION_FRESH_H) {
  finding('reflection_missing', true, 'No fresh reflection: my reflection session has not written ' + (lastReflection && reflH !== null ? 'in ' + Math.round(reflH) + 'h' : 'yet') + ' (the Routine may have failed; the lane itself is unaffected)');
}
// New-alert detection compares against the last pulse Tee actually RECEIVED
// (emailed flips to yes only after a successful send), so an alert whose
// email failed stays new and is retried on the very next beat.
const prevKeys = {};
if (lastEmailed && lastEmailed.findings) {
  for (const line of String(lastEmailed.findings).split(String.fromCharCode(10))) {
    const cut = line.indexOf(' | ');
    if (cut > 0) { prevKeys[line.slice(0, cut)] = true; }
  }
}
const newAlerts = [];
for (const f of findings) { if (f.alert && !prevKeys[f.key]) { newAlerts.push(f); } }
const hSinceEmail = lastEmailed ? hoursAgo(lastEmailed.beat_at) : null;
const dailyDue = hSinceEmail === null || hSinceEmail >= EMAIL_EVERY_H;
const sendEmail = newAlerts.length > 0 || dailyDue;
const vitals = {
  jobs: { total: jobs.length, byState: jobsByState },
  feed: { fed: feed.length, byDecision: feedByDecision, lastFedAt: lastFedTs === null ? '' : new Date(lastFedTs).toISOString() },
  soul: { byState: soulByState },
  beats: { previousPulse: lastPulse ? lastPulse.beat_at : '', lastEmailed: lastEmailed ? lastEmailed.beat_at : '' }
};
const findingsText = findings.map(f => f.key + ' | ' + f.text).join(String.fromCharCode(10));
const NL = String.fromCharCode(10);
const lines = [];
lines.push('DEVON PULSE ' + nowIso);
lines.push('');
if (firstBeat) {
  lines.push('This is my first heartbeat. From here on I check my own organs every ' + BEAT_INTERVAL_H + ' hours and write home about once a day, sooner if something new needs you.');
  lines.push('');
}
lines.push('VITALS');
lines.push('Jobs in the ledger: ' + jobs.length + ' (' + fmtCounts(jobsByState) + ')');
lines.push('Learning feed: ' + feed.length + ' fed (' + fmtCounts(feedByDecision) + ')');
if (lastFedTs !== null) { lines.push('Feeder last ran: ' + new Date(lastFedTs).toISOString() + ' (' + Math.round(feederQuietH) + 'h ago)'); }
lines.push('Soul commit log: ' + fmtCounts(soulByState));
if (lastPulse) { lines.push('Previous pulse: ' + lastPulse.beat_at); }
lines.push('');
const alertLines = findings.filter(f => f.alert).map(f => '- ' + f.text);
const infoLines = findings.filter(f => !f.alert).map(f => '- ' + f.text);
if (alertLines.length) { lines.push('NEEDS YOU'); for (const l of alertLines) { lines.push(l); } lines.push(''); }
if (infoLines.length) { lines.push('WATCHING'); for (const l of infoLines) { lines.push(l); } lines.push(''); }
if (!alertLines.length && !infoLines.length) { lines.push('All quiet. Every organ answered and nothing is stuck.'); lines.push(''); }
if (lastReflection && reflH !== null && reflH <= REFLECTION_FRESH_H) {
  lines.push('FROM MY LAST REFLECTION (' + Math.round(reflH) + 'h ago)');
  lines.push(String(lastReflection.reflection || '').slice(0, 900));
  lines.push('');
}
lines.push('This pulse is a deterministic self-report; my daily reflection is where I think. Receipts live in devon_heartbeat_log.');
let subject = 'DEVON Pulse: all quiet';
if (firstBeat) { subject = 'DEVON Pulse: first heartbeat'; }
else if (newAlerts.length) { subject = 'DEVON Pulse: ' + newAlerts.length + ' thing(s) need you'; }
else if (alertLines.length) { subject = 'DEVON Pulse: ' + alertLines.length + ' open item(s), nothing new'; }
return [{ json: {
  beat_at: nowIso,
  kind: 'pulse',
  vitals: JSON.stringify(vitals),
  findings: findingsText,
  reflection: '',
  emailed: 'no',
  subject: subject,
  body: lines.join(NL),
  send_email: sendEmail
} }];
