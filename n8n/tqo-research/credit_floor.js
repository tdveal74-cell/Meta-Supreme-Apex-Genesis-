// Firecrawl bills every search result it scrapes. Read the balance first and
// refuse the whole run below the floor, naming what was seen, rather than
// discovering an empty account halfway through a row.
const FLOOR = 100;
const r = $input.first().json || {};
const d = (r.data && typeof r.data === 'object') ? r.data : r;
const cands = [d.remainingCredits, d.remaining_credits, d.credits, r.remainingCredits, r.remaining_credits];
let remaining = null;
for (const c of cands) { if (c !== undefined && c !== null && c !== '' && !isNaN(Number(c))) { remaining = Number(c); break; } }
if (remaining === null) {
  throw new Error('Refusing to research: could not read the Firecrawl balance. Keys seen: ' + (Object.keys(r).join(', ') || '(none)') + '; data keys: ' + (Object.keys(d).join(', ') || '(none)'));
}
if (remaining < FLOOR) {
  throw new Error('Refusing to research: Firecrawl has ' + remaining + ' credits left, under the floor of ' + FLOOR + '.');
}
return [{ json: { firecrawlCredits: remaining } }];
