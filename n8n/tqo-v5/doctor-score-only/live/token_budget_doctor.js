// Output ceiling for the script doctor.
// This is the largest output in the script lane: on a REPAIRED verdict it
// returns the whole script again, plus the preservation list, the diagnosis and
// the notes. Truncation here does not throw. Parse Doctor Verdict passes the
// original draft through unedited and marks it UNCHECKED, which means you lose
// the audit silently rather than loudly.
const MAX_TOKENS = 12000;

const j = { ...$json };
if (j.body) j.body = { ...j.body, max_tokens: MAX_TOKENS };
if (j.claudeBody) j.claudeBody = { ...j.claudeBody, max_tokens: MAX_TOKENS };
// Cerebras gpt-oss-120b carries this call from 15 Sep 2026, on Tee's ruling that
// every model call in this workflow moves off Anthropic. The prompt builder still
// emits the Anthropic shape, so the whole swap is this conversion here and one
// extraction line in the parser downstream. max_completion_tokens on Cerebras
// INCLUDES the model's reasoning tokens, which is why the ceiling above stays
// generous rather than trimmed to the prose.
const SUFFIX = '\n\nOutput rules that override anything above: never use an em dash or an en dash anywhere in any field, use a comma, a full stop or the word to instead; write the full length the brief asks for, never shorter.';
const toCerebras = (b) => {
  if (!b || !Array.isArray(b.messages)) return b;
  const sys = (typeof b.system === 'string' && b.system) ? [{ role: 'system', content: b.system + SUFFIX }] : [];
  return { model: 'gpt-oss-120b', messages: [...sys, ...b.messages], max_completion_tokens: MAX_TOKENS, reasoning_effort: 'medium', response_format: { type: 'json_object' } };
};
if (j.body) j.body = toCerebras(j.body);
if (j.claudeBody) j.claudeBody = toCerebras(j.claudeBody);
return [{ json: j }];