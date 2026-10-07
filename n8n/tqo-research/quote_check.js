// The mechanical check Tee approved under the doctor. A quote survives only if
// it is found, after whitespace and punctuation normalising and nothing else,
// inside the text Firecrawl fetched from that same URL. Markdown link and
// emphasis syntax is removed from both sides first, because a quote copied
// from rendered text will not carry the asterisks. It also checks provenance:
// the organisation that produced the figure must be named inside the quote,
// unless the publisher produced it, so a blog repeating an unattributed number
// cannot pass however well the model vouches for it.
const prev = $('Build Extract Prompt').first().json;
const pages = prev.pages || [];
const norm = (t) => String(t || '')
  .replace(/!\[[^\]]*\]\([^)]*\)/g, ' ')
  .replace(/\[([^\]]*)\]\([^)]*\)/g, '$1')
  .replace(/[*_`]/g, '')
  .replace(/[#>|]/g, ' ')
  .replace(/[‘’‛′]/g, "'")
  .replace(/[“”‟″]/g, '"')
  .replace(/[–—−]/g, '-')
  .replace(/ /g, ' ')
  .replace(/\s+/g, ' ')
  .trim()
  .toLowerCase();
let parsed = null;
const content = (((($input.first().json || {}).choices || [])[0] || {}).message || {}).content || '';
try { parsed = JSON.parse(content); } catch (e) { parsed = null; }
const offered = (parsed && Array.isArray(parsed.sources)) ? parsed.sources : [];
const checked = [];
const dropped = [];
const seen = new Set();
for (const s of offered) {
  const page = pages.find(p => p.n === Number(s.page));
  const quote = String(s.quote || '').trim();
  const why = (r) => dropped.push({ page: s.page, quote: quote.slice(0, 160), reason: r });
  if (!page) { why('no such page'); continue; }
  if (quote.length < 40 || quote.length > 400) { why('quote length ' + quote.length); continue; }
  if (!String(s.publisher || '').trim()) { why('no publisher'); continue; }
  if (!norm(page.markdown).includes(norm(quote))) { why('quote not found on the page'); continue; }
  const origin = String(s.origin || '').trim();
  if (!origin) { why('no origin named'); continue; }
  const primary = norm(origin) === norm(s.publisher);
  if (!primary && !norm(quote).includes(norm(origin))) { why('origin ' + origin + ' is not named in the quote'); continue; }
  if (!norm(page.markdown).includes(norm(origin))) { why('origin ' + origin + ' not found on the page'); continue; }
  const key = page.url + '|' + norm(quote);
  if (seen.has(key)) { why('duplicate'); continue; }
  seen.add(key);
  const quoteText = quote.replace(/!\[[^\]]*\]\([^)]*\)/g, '').replace(/\[([^\]]*)\]\([^)]*\)/g, '$1').replace(/^[\s>*-]+/, '').replace(/\s+/g, ' ').trim();
  checked.push({ url: page.url, title: page.title, publisher: String(s.publisher).trim(), origin: origin, primary: primary, quote: quote, quote_text: quoteText, claim: String(s.claim || '').trim() });
}
const note = parsed === null
  ? 'No source written: the extraction reply was not JSON.'
  : (checked.length ? '' : 'No source written: ' + offered.length + ' quote(s) offered, none survived the quote check' + (dropped.length ? ' (' + dropped.map(d => d.reason).join('; ') + ')' : '') + '.');
return [{ json: { id: prev.id, checked: checked, dropped: dropped, offered: offered.length, research_note: note } }];
