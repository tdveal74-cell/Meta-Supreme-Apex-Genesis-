// Output ceiling for the materiality assessment.
//
// The answer is one small JSON object, a few hundred tokens at most. The ceiling
// sits far above that because max_completion_tokens on Cerebras INCLUDES the
// model's reasoning tokens, and a truncated response fails closed to
// CHANGE DETECTED, ASSESSMENT FAILED, which is safe but costs a human read.
const MAX_TOKENS = 8000;

// Cerebras gpt-oss-120b carries this call from 16 Sep 2026, on Tee's ruling
// after the Anthropic key returned HTTP 400 whose body read "Your credit balance
// is too low to access the Anthropic API" (request req_011Cf6L2vyK6pRVWS2LtvRJC,
// probe execution 216). The key authenticates; the account behind it is empty.
// n8n printed that 400 as "Bad request - please check your parameters", which is
// n8n's wording, not Anthropic's, and reads like a parameter bug when it is not.
// Build Assessment Prompt still emits the Anthropic shape, so the whole swap is
// this conversion plus one extraction line in Parse Assessment downstream.
const SUFFIX = '\n\nOutput rules that override anything above: return only the JSON object, with no markdown fences and no commentary; never use an em dash or an en dash in any field, use a comma, a full stop or the word to instead; use plain ASCII hyphens, never a typographic hyphen or a minus sign.';
const toCerebras = (b) => {
  if (!b || !Array.isArray(b.messages)) return b;
  const sys = (typeof b.system === 'string' && b.system) ? [{ role: 'system', content: b.system + SUFFIX }] : [];
  return { model: 'gpt-oss-120b', messages: [...sys, ...b.messages], max_completion_tokens: MAX_TOKENS, reasoning_effort: 'medium', response_format: { type: 'json_object' } };
};
const j = { ...$json };
if (j.claudeBody) j.claudeBody = toCerebras(j.claudeBody);
return [{ json: j }];
