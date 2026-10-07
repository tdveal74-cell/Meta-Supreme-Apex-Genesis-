// Search results arrive with each page's own text, fetched by Firecrawl. The
// model is handed that text and asked to copy quotes out of it. Nothing it
// returns is trusted: Quote Check below matches every quote against the same
// text character for character.
const row = $('One Row at a Time').first().json;
const r = $input.first().json || {};
const raw = Array.isArray(r.data) ? r.data : (r.data && Array.isArray(r.data.web) ? r.data.web : (Array.isArray(r.web) ? r.web : []));
const PAGE_CHARS = 8000;
const pages = [];
for (const p of raw) {
  const url = String(p.url || (p.metadata && (p.metadata.sourceURL || p.metadata.url)) || '').trim();
  const md = String(p.markdown || '').trim();
  if (!url || md.length < 200) continue;
  pages.push({ n: pages.length + 1, url: url, title: String(p.title || (p.metadata && p.metadata.title) || '').trim(), markdown: md });
}
const searchNote = r.error ? ('search error: ' + String(r.error.message || r.error).slice(0, 300)) : '';
if (!pages.length) {
  return [{ json: { id: row.id, hasPages: false, pages: [], research_note: 'No source written: the search returned no readable pages' + (searchNote ? ' (' + searchNote + ')' : '') + '. Query: ' + row.searchQuery } }];
}
const system = [
  'You extract evidence for a factual video script. You copy, you never write.',
  'From the numbered pages below, pick up to six passages that state a specific, checkable fact about the episode topic: a number, a date, a named finding or a named organisation\'s stated result.',
  'Each quote must be copied character for character from the page text, one or two sentences, between 40 and 400 characters. Do not fix typos, do not join sentences from different places, do not add or drop words.',
  'Skip any passage that cites an unnamed study, firm, survey or expert. Skip opinion, prediction and marketing copy.',
  'publisher is the organisation or person that published the page, as the page names it. If the page does not name one, skip that page.',
  'origin is the organisation that produced the figure or finding (the survey, dataset, filing or report), named exactly as the page names it. The quote must name the origin in its own words, unless the publisher itself produced the figure, in which case origin equals publisher. If the page repeats a figure without naming who produced it, skip that passage.',
  'claim is one plain sentence saying what the quote shows, adding nothing the quote does not say.',
  'Return JSON only: {"sources":[{"page":1,"publisher":"...","origin":"...","quote":"...","claim":"..."}]}. Return {"sources":[]} if nothing qualifies.'
].join(' ');
const user = 'EPISODE TOPIC: ' + row.topic + '\nANGLE: ' + row.angle + '\nIDEA: ' + row.idea + '\n\n' +
  pages.map(p => '=== PAGE ' + p.n + ' ===\nURL: ' + p.url + '\nTITLE: ' + p.title + '\nTEXT:\n' + p.markdown.slice(0, PAGE_CHARS)).join('\n\n');
const body = { model: 'gpt-oss-120b', messages: [{ role: 'system', content: system }, { role: 'user', content: user }], max_completion_tokens: 8000, reasoning_effort: 'medium', response_format: { type: 'json_object' } };
return [{ json: { id: row.id, hasPages: true, pages: pages, body: body } }];
