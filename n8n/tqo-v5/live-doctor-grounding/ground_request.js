// Doctor: Ground the Request. Runs in TQO FINAL V5 between Token Budget: Doctor
// and Run Script Doctor (Cerebras). Ruled by Tee 2026-10-25 on a card, "Both
// shows, live too": the live doctor gets the two things the score-only doctor
// was given on 2026-10-24 and 2026-10-25, for both shows.
//
// The first is Tee's ruling on first person that only addresses the viewer,
// added to the system message. Row 49's line, "I am talking to the person who
// has spent years handling problems other people never even saw.", was flagged
// as an invented first person claim in three of five score-only runs; the
// ruling says it stands and that the person in it is the viewer.
//
// The second goes into the user message, just above SCRIPT:. For TQO, where
// the learning objective is spoken, measured by the Script Gate's own rule:
// word for word, ignoring case and punctuation, inside the first 70 words. For
// both shows, which lines are the brief and which are the script. Execution
// 4300 held a row for an objective it guessed sat late, when it started at
// word 31, and asked for a second copy to be removed that was the brief's own
// LEARNING OBJECTIVE line.
//
// This is Score Only: Final Word in n8n/tqo-v5/doctor-score-only without the
// score-only clause. grounding.test.mjs runs both on the same requests and
// fails if they differ in anything but that clause.
const VOICE = '\n\nRuled by Tee: first person that only addresses the viewer and claims no deed, sight, hearing or advice, as in "I am talking to the person who has spent years handling problems other people never even saw.", is his voice and stands. In that line, the person who has spent years handling problems other people never even saw is the viewer being addressed, not Terrance, so the line says nothing about what he has done. It is not a first person claim and is never marked down. The rule against invented experience still applies to everything Terrance is said to have done, seen, heard or advised.';
// The Script Gate's window and its normaliser, copied from Script Gate: Quality.
// Keep the two equal; score_only.test.mjs checks them against the export.
const LO_WINDOW = 70;
const norm = (s) => String(s || '').toLowerCase().replace(/[^a-z0-9\s]/g, ' ').split(/\s+/).filter(Boolean).join(' ');
const MARK = '\n\nSCRIPT:\n';

const j = { ...$json };
const b = j.claudeBody;
if (!b || !Array.isArray(b.messages) || !b.messages.length || b.messages[0].role !== 'system') {
  throw new Error('Doctor: Ground the Request expected the request to open with a system message, and it does not.');
}
if (b.messages.length !== 2 || b.messages[1].role !== 'user') {
  throw new Error('Doctor: Ground the Request expected one system message and one user message, and the request carries ' + b.messages.map((m) => m && m.role).join(', ') + '.');
}
const d = $('Build Doctor Prompt').first().json.original || {};
const script = String(d.script || '');
const content = String(b.messages[1].content);
const at = content.indexOf(MARK);
if (at === -1 || content.slice(at + MARK.length) !== script) {
  throw new Error('Doctor: Ground the Request could not find the script after SCRIPT: in the user message, so the measured facts were not added and the doctor was not called.');
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
      throw new Error('Doctor: Ground the Request measured the learning objective two ways and they disagree, so the doctor was not called.');
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
  { ...b.messages[0], content: String(b.messages[0].content) + VOICE },
  { ...b.messages[1], content: content.slice(0, at) + '\n\n' + facts.join('\n') + MARK + script }
] };
return [{ json: j }];
