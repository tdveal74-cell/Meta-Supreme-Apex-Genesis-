// Script: Short After Doctor? Ruled by Tee 2026-10-07 after test 2357: the
// expansion reached 1,292 words, the doctor trimmed it to 1,124 and the gate
// failed it under the 1,200 floor, because both expansion checks run before the
// doctor. This node measures the text the doctor and the dash repair left. At or
// over the floor it passes through. Under it, it prepares one expansion of the
// final text, held to the same rules as the two before the doctor: no new
// number, company, person, study, interview, case or example. The Script Gate
// and the Sources Gate still measure whatever comes back.
const FLOOR = 1200;          // the gate's WORD_FLOOR; keep the two equal
const TARGET_LOW = 1400;
const TARGET_HIGH = 1800;

const d = $json;
const script = String(d.script || '');
const words = script.split(/\s+/).filter(Boolean).length;
if (words >= FLOOR) return [{ json: { ...d, needsExpansion3: false } }];

const budget = $('Token Budget: Script').first().json.body || {};
const msgs = Array.isArray(budget.messages) ? budget.messages : [];
const system = msgs.filter(m => m.role === 'system').map(m => String(m.content || '')).join('\n\n');
const brief = msgs.filter(m => m.role === 'user').map(m => String(m.content || '')).join('\n\n');
const draft = { title: d.title || '', script, description: d.description || '', tags: d.tags || '', broll: d.broll || '' };
const sentences = script.trim().match(/[^.!?]+[.!?]+|[^.!?]+$/g) || [];
const last = sentences.length ? sentences[sentences.length - 1].trim() : '';

const user = [
  'The script below has been edited and is ' + words + ' words. The brief requires at least ' + FLOOR + '. Lengthen it to between ' + TARGET_LOW + ' and ' + TARGET_HIGH + ' words. Rules:',
  '- Keep the hook, the first two sentences, exactly as written.',
  ...(last ? ['- Keep the last sentence exactly as written and keep it last. It reads: ' + last] : []),
  ...(d.learningObjective ? ['- Keep the learning objective word for word and inside the first 70 words. It reads: ' + d.learningObjective] : []),
  ...(Array.isArray(d.checklist) && d.checklist.length ? ['- Keep the checklist steps word for word and in order. They read: ' + d.checklist.map((s, i) => (i + 1) + '. ' + s).join(' ')] : []),
  '- Keep every sentence that is already there. Lengthen around them with a mechanism the viewer can follow, a step the viewer can take today, or a closer reading of a figure the script already carries. Never add a number, a company, a person, a study, an interview, a case or an example with figures that the script does not already carry.',
  '- Keep the title, description, tags and broll unchanged.',
  '- Never use an em dash or an en dash anywhere.',
  'Return only a JSON object in exactly this shape: {"title": "...", "script": "...", "description": "...", "tags": "...", "broll": ["...", "..."]}.',
  '',
  'THE ORIGINAL BRIEF:',
  brief,
  '',
  'THE SCRIPT TO LENGTHEN (JSON):',
  JSON.stringify(draft)
].join('\n');

const expandBody = {
  model: budget.model || 'gpt-oss-120b',
  messages: [ ...(system ? [{ role: 'system', content: system }] : []), { role: 'user', content: user } ],
  max_completion_tokens: budget.max_completion_tokens || 10000,
  reasoning_effort: 'medium',
  response_format: { type: 'json_object' }
};
return [{ json: { ...d, shortAfterDoctorWords: words, needsExpansion3: true, expandBody } }];
