// Sources Rule, ruled by Tee 2026-10-07 after row 46: real sources on the row,
// which the writer may cite and nothing else. The sources are approved by TQO
// Research (0zLNB34UOOTq6mck) and read from the row's sources column. TQO only,
// because NCO was not ruled. It is its own node so the measured show blocks in
// Build Script Prompt stay byte for byte. Sources Gate refuses what this allows.
const ctx = $('Show Context: Script').first().json;
const row = $('One Idea at a Time').first().json;
const j = $input.first().json;
if (ctx.show === 'NCO' || !j.body) return [{ json: j }];
let list = [];
try { const l = JSON.parse(String(row.sources || '')); if (Array.isArray(l)) list = l.filter(x => x && x.url && x.quote); } catch (e) { list = []; }
const rule = list.length
  ? '=== SOURCES YOU MAY CITE, APPROVED FOR THIS EPISODE ===\n' + list.map((s, i) => '[S' + (i + 1) + '] ' + (s.origin || s.publisher) + ', reported by ' + s.publisher + ': "' + (s.quote_text || s.quote) + '"').join('\n') + '\n' + [
      'SOURCES RULE: every number, percentage, dollar amount and dated finding in the script comes from the sources above, exactly as the quote gives it, and from nothing else.',
      'Name the origin in the sentence that uses its figure, as in: according to Gallup. Never name any other study, survey, report, tracker or organisation as a source.',
      'Keep the time a figure belongs to. If the quote gives a year or says last year, say so, and never move an old figure into the present.',
      'Call a projection a projection.',
      'Use no other numerals except counts of ten or under and a year the sources or the episode idea name. If a point needs a number the sources do not hold, make the point without a number.'
    ].join(' ')
  : 'SOURCES RULE: no sources were approved for this episode, so the script states no figures, percentages, dollar amounts or named studies at all. Make every point without a number.';
return [{ json: { ...j, body: { ...j.body, system: String(j.body.system || '') + '\n\n' + rule }, sourcesApproved: list.length } }];
