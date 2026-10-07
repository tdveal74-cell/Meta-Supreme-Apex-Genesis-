// The script doctor approves or rejects each checked source. It is handed only
// the quotes that already passed the mechanical check, and it can only say yes
// or no to each: Compose Approved Sources keeps the checked text, so nothing the
// doctor writes reaches the row except its verdict and reason.
const row = $('One Row at a Time').first().json;
const list = $input.first().json.checked || [];
const system = [
  'You are the script doctor for The Quiet Operator, a calm, anti-hype channel on AI and careers. You approve the evidence a script may cite.',
  'For each numbered source decide approve or reject.',
  'Approve only when all hold: the origin is a named organisation a viewer can look up (a government agency, a research or analyst firm, a company reporting on itself, a newsroom reporting its own finding); the quote states a specific fact or a named organisation\'s published projection; the fact bears directly on the episode topic; the claim line says no more than the quote, and calls a projection a projection.',
  'Reject when the origin is a vendor, coach or app that sells the thing the figure measures, when the origin is only a blog or social post, when the figure is from an unnamed survey, or when the figure would mislead out of context. When in doubt, reject: a rejected source costs one row a day, an approved bad one goes on air in Tee\'s voice.',
  'Return JSON only: {"verdicts":[{"index":0,"verdict":"approve","reason":"..."}]} with one entry per source, index matching the list.'
].join(' ');
const user = 'EPISODE TOPIC: ' + row.topic + '\nANGLE: ' + row.angle + '\nIDEA: ' + row.idea + '\n\nSOURCES:\n' +
  list.map((s, i) => '[' + i + '] PUBLISHER: ' + s.publisher + '\nORIGIN OF THE FIGURE: ' + s.origin + (s.primary ? ' (the publisher itself)' : '') + '\nURL: ' + s.url + '\nQUOTE: "' + (s.quote_text || s.quote) + '"\nCLAIM: ' + s.claim).join('\n\n');
const body = { model: 'gpt-oss-120b', messages: [{ role: 'system', content: system }, { role: 'user', content: user }], max_completion_tokens: 4000, reasoning_effort: 'medium', response_format: { type: 'json_object' } };
return [{ json: { id: $input.first().json.id, checked: list, dropped: $input.first().json.dropped, body: body } }];
