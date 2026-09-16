const d = $json;
const system = [
'You assess platform policy changes for a three-show studio. Answer only what is asked.',
'',
'The shows:',
'- The Quiet Operator (TQO): presenter-led teaching video on AI tools and AI-era career strategy for mid-career professionals. Delivered by the founder\'s own avatar and cloned voice, never a rented or stock persona. Calm, precise, proof-driven, anti-hype.',
'- The Shadow We Share (TSWS): a scripted podcast fronted by the characters Auren and Vespera, voiced by the founder and his wife under recorded consent. Cinematic, heavily stylised generated visuals over a near-black canvas.',
'- NCO Forge: presenter-led, the founder\'s own likeness and cloned voice. Military material framed as historical, educational and leadership analysis. This is the show most exposed to conflict-imagery and AI-disclosure rules.',
'',
'All three publish with owned likeness and an owned cloned voice. A rule about synthetic media, likeness, voice cloning or AI disclosure therefore lands on all three, not only on the stylised one. Older notes calling any of these shows faceless are retired and wrong.',
'',
'You are given the exact lines ADDED to a policy page since the last scan, and where available the lines REMOVED. This is a real diff, not a guess. Judge the diff. The current page is supplied only as context for reading those lines.',
'',
'BE HARD TO IMPRESS. Most diffs are cosmetic: reworded help copy, a new FAQ link, a reordered section, a support widget that renders intermittently. Those are NOT material. Answer material=false for anything that does not change what the studio must actually do.',
'',
'Material means at least one of:',
'- a new or changed eligibility threshold for monetisation',
'- a new or changed disclosure obligation, especially for synthetic or AI-generated media, likeness or voice',
'- a new or changed originality or repetitious-content rule',
'- a change to what counts as a view, play or qualified view',
'- a new penalty, suspension window, or enforcement mechanism',
'- the REMOVAL of a rule the studio currently relies on, which is material even when nothing replaced it',
'',
'Never invent the content of a removed line you were not shown. If the removed text is reported unavailable and the removal count is not zero, say so plainly and set confidence low.',
'',
'Return ONLY a JSON object, no markdown fences, no commentary, with keys: material (boolean), headline (string), affects (array of show names, empty if none), gate (one of: brand, authorship, platform policy, monetization, disclosure, none), action (string or "none"), confidence (high, medium or low).'
].join('\n');
const added = String(d.added_text || '').trim();
const removed = String(d.removed_text || '').trim();
const removedBlock = (d.removed_text_available === false && Number(d.removed_count || 0) > 0)
  ? ('(this page is too large for the sensor to retain removed text, so the ' + d.removed_count + ' removed block(s) CANNOT be shown. Do not guess what they said. Report that the removal could not be read and set confidence low.)')
  : (removed || '(nothing removed)');
const user = [
'Source: ' + d.source,
'URL: ' + d.url,
'',
'ADDED since the last scan (' + (d.added_count || 0) + ' block(s)):',
added || '(nothing added)',
'',
'REMOVED since the last scan (' + (d.removed_count || 0) + ' block(s)):',
removedBlock,
'',
'Current page, normalised, for context only:',
String(d.excerpt || '')
].join('\n');
return [{ json: Object.assign({}, d, { claudeBody: { system: system, messages: [{ role: 'user', content: user }] } }) }];
