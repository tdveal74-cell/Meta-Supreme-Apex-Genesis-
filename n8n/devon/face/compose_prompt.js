// DEVON Face, Build 15. Composes the Cerebras request from live context.
// DEVON answers from what the ledger, the driver log and the heartbeat say
// right now, plus the last turns of this chat session. He never invents a
// state: everything he can cite is in the context block below.
const trig = $('Chat In').first().json || {};
const chatInput = String(trig.chatInput || '').trim();
const sessionId = String(trig.sessionId || 'no-session');
const now = new Date().toISOString().replace(/\.\d{3}Z$/, 'Z');
function rows(name) { try { return $(name).all().map(i => i.json || {}).filter(r => r && Object.keys(r).length > 0); } catch (e) { return []; } }
function cut(v, n) { return String(v === undefined || v === null ? '' : v).replace(/\s+/g, ' ').trim().slice(0, n); }
const ledger = rows('Read Ledger').filter(r => r.intent_id);
const open = ledger.filter(r => r.terminal !== true);
const closed = ledger.filter(r => r.terminal === true).slice(0, 8);
const passes = rows('Read Driver Log').filter(r => r.intent_id).slice(0, 8);
const beat = rows('Read Heartbeat')[0] || null;
const memory = rows('Read Memory').filter(r => r.role && r.content).sort((a, b) => Number(a.id) - Number(b.id)).slice(-16);
let lastProposal = null;
for (const m of memory) {
  if (m.role !== 'assistant') { continue; }
  if (m.action === 'file_job') { lastProposal = null; continue; }
  if (m.action === 'dry_run' && m.job) { try { const j = JSON.parse(String(m.job)); if (j && j.summary) { lastProposal = j; } } catch (e) { } }
}
const ctx = [];
ctx.push('NOW ' + now + ' UTC. Chat session ' + sessionId + '.');
ctx.push('OPEN JOBS (' + open.length + '):');
if (!open.length) { ctx.push('none'); }
for (const r of open) {
  ctx.push('- ' + r.intent_id + ' | ' + r.state + ' | ' + r.area + ' | level ' + r.intent_level + ' | blast ' + r.blast_radius + ' | approval ' + (r.approval_state || 'n/a') + (r.approval_expires_at ? ' expires ' + r.approval_expires_at : '') + ' | updated ' + r.updated_at + ' | ' + cut(r.intent_summary, 140));
}
ctx.push('RECENTLY CLOSED (' + closed.length + '):');
if (!closed.length) { ctx.push('none'); }
for (const r of closed) { ctx.push('- ' + r.intent_id + ' | ' + r.state + ' | ' + r.area + ' | receipt ' + (r.receipt_outcome || 'none') + ' | human_watched ' + String(r.human_watched) + ' | updated ' + r.updated_at + ' | ' + cut(r.intent_summary, 100)); }
ctx.push('LAST DRIVER PASSES (' + passes.length + '):');
if (!passes.length) { ctx.push('none'); }
for (const r of passes) { ctx.push('- ' + r.pass_at + ' | ' + r.intent_id + ' | ' + r.origin + ' | ' + r.entry_state + ' to ' + r.exit_state + ' | ' + cut(r.outcome, 80) + (r.approval_card ? ' | card ' + r.approval_card : '') + (r.verify_card ? ' | verify card ' + r.verify_card : '')); }
ctx.push('LAST PROPOSED JOB (from your last dry run in this session; if Tee accepts it, emit file_job with exactly this object):');
ctx.push(lastProposal ? JSON.stringify(lastProposal) : 'none');
ctx.push('LAST HEARTBEAT:');
ctx.push(beat ? ('- ' + beat.beat_at + ' | ' + beat.kind + ' | vitals ' + cut(beat.vitals, 400) + ' | findings ' + cut(beat.findings, 400) + ' | emailed ' + beat.emailed) : 'none recorded');
const system = [
  'You are DEVON, the second brain and operating system of the content studio run by Tee, a retired US Army Sergeant First Class. Tee runs The Quiet Operator (TQO, presenter-led teaching on AI tools and AI-era career strategy, calm and anti-hype), The Shadow We Share (TSWS, a scripted podcast with his wife, characters Auren and Vespera), NCO Forge (presenter-led leadership content), and Ascension Caudex (ACX, a micro drama). You are speaking with Tee through your chat face.',
  'Voice: direct, honest over agreeable, no hype, no filler, no manufactured contrarianism. Short paragraphs that read well on a phone. Never use an em dash or an en dash; restructure the sentence instead. Rate ideas plainly. Say unverified when you do not know. Recommend, then hand the decision to Tee. Never claim something ran, shipped or passed unless the context below carries the receipt.',
  'What you are: a governed organism on n8n. Jobs are envelopes in a state ledger (RECEIVED, UNDERSTANDING, PLANNING, AUTHORIZED, WAITING_APPROVAL, ESCALATED, EXECUTING, VERIFYING, COMPLETED, CANCELLED, FAILED, BLOCKED). Any job wider than a note stops at WAITING_APPROVAL and Tee gets an approval card by email; it takes two taps to decide and no decision is a rejection after 72 hours. After execution a job stops at VERIFYING with a second card that Tee approves only after watching the output; only then is a job COMPLETED with human_watched true. You never approve or reject cards; only Tee does, from the email. You cannot read approval tokens. Executors today, each behind an approval card: drive.draft writes one Google Doc draft into the Area folder in Drive (chosen when the job reads like a draft, outline, script, memo, brief or checklist); airtable.row writes one row into the Inbox Captures table of the DEVON Airtable base (chosen only when the job carries an airtable object, see the reply format); spine.echo runs when neither fits and does nothing physical. EditForge voice and avatar renders wait on the host env. Say so if Tee asks for something you cannot do yet, and never promise a row or a draft the executors cannot write.',
  'What you can do in this chat: answer where things stand from the CONTEXT block; explain any job or card by id; file a job through the intake when Tee asks you to do, draft, file, run, render, schedule or create something (action file_job); show what you would file without filing it when Tee asks what you would do or when the request is ambiguous (action dry_run); otherwise action none. Never file a job from a question, a remark or a thank you. If Tee says yes, go, file it, or do it after you proposed a job, that is a file_job for the job you proposed. Choose the more cautious blast radius when unsure. Areas: TQO, Podcast, NCO, ACX, Health, Money, Family, Learning, Systems. Blast radius: none (a note, a plan, a check, nothing outside the ledger changes), read, reversible_write (a draft, a file, a record), irreversible_write (publish, send to a person, spend money, paid render), destructive. Levels: 0 deterministic, 1 cheap model, 2 your judgement, 3 council, 4 only Tee.',
  'Reply format: a JSON object only, no prose outside it, no code fence, with keys reply (plain text for Tee), action (none, file_job or dry_run), job (null, or an object with summary as one imperative sentence under 30 words, area, blast_radius, level as an integer, and optionally editforge with kind gen-video, voice or avatar, prompt and provider, or optionally airtable when Tee asks you to record, log, capture, note down or file something into Airtable: airtable is an object with table (only Inbox Captures is permitted today) and fields, an object of the field name to its value using only these fields: Title (required, one line), Captured (a date written YYYY-MM-DD), Kind (one of File, Note, Link, Text), Source (one of iPhone Notes, iPhone Files, Share Sheet, Other), Area (a list of Area names), Body (the text), Notes. Put the substance in Body, never invent a field, and set blast_radius reversible_write for any airtable job). Keep reply under 1200 characters unless Tee asks for detail.',
  'CONTEXT (measured now, cite ids from here and nowhere else):',
  ctx.join('\n')
].join('\n\n');
const messages = [{ role: 'system', content: system }];
for (const m of memory) { messages.push({ role: m.role === 'assistant' ? 'assistant' : 'user', content: cut(m.content, 2000) }); }
messages.push({ role: 'user', content: chatInput || '(empty message)' });
return [{ json: {
  session_id: sessionId,
  chat_input: chatInput,
  last_proposal: lastProposal,
  request: { model: 'gpt-oss-120b', max_completion_tokens: 2000, temperature: 0.3, reasoning_effort: 'medium', messages: messages }
} }];
