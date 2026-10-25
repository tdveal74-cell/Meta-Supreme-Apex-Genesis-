// Score Only: Final Word. Token Budget: Doctor, copied from the live lane, ends
// the system message with output rules written for the full pass, and one of
// them, "write the full length the brief asks for, never shorter", says it
// overrides anything above. In a score-only pass that reads as a request for a
// rewrite. This line comes last and says which of those rules still stands.
//
// Ruled by Tee 2026-10-24 after execution 4300. The doctor held row 49 for a
// learning objective that "appears after several sentences instead of within
// the first 30 seconds", when it starts at word 31, and asked for "the second
// occurrence" of it to be removed, when the script speaks it once: it had read
// the LEARNING OBJECTIVE field line as script. Its reasoning guessed the
// position ("Probably not before 30 seconds") rather than counting it. So two
// things go into the user message, just above SCRIPT:. The first is where the
// learning objective is spoken, measured by the Script Gate's own rule in TQO
// FINAL V5: word for word, ignoring case and punctuation, inside the first 70
// words, which the gate counts as the first 30 seconds. The doctor is told the
// fact instead of being left to guess it. The second says which lines are the
// brief and which are the script. NCO has no learning objective line, so it
// gets the second only.
//
// Ruled by Tee 2026-10-24 on a card: first person that only addresses the
// viewer and claims no deed, sight or advice is allowed in his voice. Row 49's
// only first person sentence, "I am talking to the person who has spent years
// handling problems other people never even saw.", was flagged as an invented
// first person claim in three of five runs and passed in two, and the Script
// Gate's first person patterns pass it. VOICE says so in the system message,
// for both shows, just before FINAL. Nothing else in the request changes.
// Sharpened by Tee the next day, after execution 4364: one read of three still
// marked the line down, reading "the person who has spent years" as Terrance.
// VOICE now says that person is the viewer.
const VOICE = '\n\nRuled by Tee: first person that only addresses the viewer and claims no deed, sight, hearing or advice, as in "I am talking to the person who has spent years handling problems other people never even saw.", is his voice and stands. In that line, the person who has spent years handling problems other people never even saw is the viewer being addressed, not Terrance, so the line says nothing about what he has done. It is not a first person claim and is never marked down. The rule against invented experience still applies to everything Terrance is said to have done, seen, heard or advised.';
const FINAL = '\n\nScore only, and this overrides the full-length rule above: return only the JSON object the score-only contract names, with no script, title, description or b-roll field. Keep each note to a few sentences that describe a repair without writing it out. The rule against em and en dashes still stands.';
// The Script Gate's window and its normaliser, copied from Script Gate: Quality.
// Keep the two equal; score_only.test.mjs checks them against the export.
const LO_WINDOW = 70;
const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(Boolean).join(' ');
const MARK = '\n\nSCRIPT:\n';

const j = { ...$json };
const b = j.claudeBody;
if (!b || !Array.isArray(b.messages) || !b.messages.length || b.messages[0].role !== 'system') {
  throw new Error('Score Only: Final Word expected the request to open with a system message, and it does not.');
}
if (b.messages.length !== 2 || b.messages[1].role !== 'user') {
  throw new Error('Score Only: Final Word expected one system message and one user message, and the request carries ' + b.messages.map((m) => m && m.role).join(', ') + '.');
}
const d = $('Build Doctor Prompt').first().json.original || {};
const script = String(d.script || '');
const content = String(b.messages[1].content);
const at = content.indexOf(MARK);
if (at === -1 || content.slice(at + MARK.length) !== script) {
  throw new Error('Score Only: Final Word could not find the script after SCRIPT: in the user message, so the measured facts were not added and the doctor was not called.');
}
const nco = $('Show Context: Script').first().json.show === 'NCO';

const facts = [];
if (!nco) {
  const tokens = script.split(/\s+/).filter(Boolean);
  const lo = norm(d.learningObjective);
  if (!lo) {
    facts.push('MEASURED BEFORE THIS PASS: no learning objective is stored for this row.');
  } else {
    // The gate's own test, character for character.
    const inside = (' ' + norm(tokens.slice(0, LO_WINDOW).join(' ')) + ' ').includes(' ' + lo + ' ');
    // Where it is spoken: the normalised words of the script, each carrying the
    // number of the script word it came from.
    const flat = [];
    tokens.forEach((t, i) => { for (const w of norm(t).split(' ').filter(Boolean)) flat.push({ w, i }); });
    const want = lo.split(' ');
    const hits = [];
    for (let k = 0; k + want.length <= flat.length; k++) {
      if (want.every((w, x) => flat[k + x].w === w)) hits.push({ from: flat[k].i + 1, to: flat[k + want.length - 1].i + 1 });
    }
    const first = hits[0];
    if (inside !== Boolean(first && first.to <= LO_WINDOW)) {
      throw new Error('Score Only: Final Word measured the learning objective two ways and they disagree, so the doctor was not called.');
    }
    const rule = 'by the rule the Script Gate in TQO FINAL V5 applies (word for word, ignoring case and punctuation, inside the first ' + LO_WINDOW + ' words, which the gate counts as the first 30 seconds)';
    if (!first) {
      facts.push('MEASURED BEFORE THIS PASS, ' + rule + ': the learning objective is not spoken word for word anywhere in the script.');
    } else {
      facts.push('MEASURED BEFORE THIS PASS, ' + rule + ': the learning objective is spoken word for word from word ' + first.from + ' to word ' + first.to + ' of ' + tokens.length + ', '
        + (inside ? 'inside the first ' + LO_WINDOW + ' words. Its position meets the brief; do not mark it down for where it sits.' : 'which is past the first ' + LO_WINDOW + ' words, so its position does not meet the brief.')
        + ' The script speaks it ' + (hits.length === 1 ? 'once' : hits.length + ' times') + '.');
    }
  }
}
facts.push('Every line above SCRIPT: is the brief: the channel, show and editorial direction, the TITLE, DESCRIPTION and BROLL fields, '
  + (nco ? '' : 'the LEARNING OBJECTIVE and CHECKLIST lines, ')
  + 'the APPROVED SOURCES and TEE\'S RECORD. None of those lines is part of the script, and none is a second copy of a script sentence. Only the text after SCRIPT: is the script.');

j.claudeBody = { ...b, messages: [
  { ...b.messages[0], content: String(b.messages[0].content) + VOICE + FINAL },
  { ...b.messages[1], content: content.slice(0, at) + '\n\n' + facts.join('\n') + MARK + script }
] };
return [{ json: j }];
