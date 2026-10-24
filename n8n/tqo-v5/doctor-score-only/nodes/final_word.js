// Score Only: Final Word. Token Budget: Doctor, copied from the live lane, ends
// the system message with output rules written for the full pass, and one of
// them, "write the full length the brief asks for, never shorter", says it
// overrides anything above. In a score-only pass that reads as a request for a
// rewrite. This line comes last and says which of those rules still stands.
const FINAL = '\n\nScore only, and this overrides the full-length rule above: return only the JSON object the score-only contract names, with no script, title, description or b-roll field. Keep each note to a few sentences that describe a repair without writing it out. The rule against em and en dashes still stands.';
const j = { ...$json };
const b = j.claudeBody;
if (!b || !Array.isArray(b.messages) || !b.messages.length || b.messages[0].role !== 'system') {
  throw new Error('Score Only: Final Word expected the request to open with a system message, and it does not.');
}
j.claudeBody = { ...b, messages: [{ ...b.messages[0], content: String(b.messages[0].content) + FINAL }, ...b.messages.slice(1)] };
return [{ json: j }];
