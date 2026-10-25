// Script: Hydrate from Row. Tee ruling 2026-10-01: the pipeline must USE a
// script that already exists on the row instead of rewriting it. This node
// shapes the row's stored script into the same d-shape Build Doctor Prompt
// expects from Parse Script JSON, so an existing script enters the chain at
// the doctor, not at the writer. Nothing here invents content: the title,
// description, b-roll, learning objective and checklist come from the row
// where they exist, empty where they do not.
const row = $('One Idea at a Time').first().json;
const f = row.fields || row;
const script = String(f.Script ?? f.script ?? '').trim();
if (!script) {
  throw new Error('Script: Hydrate from Row reached with an empty script. This node only runs for rows that already carry one.');
}
const list = (v) => Array.isArray(v) ? v.map(s => String(s).trim()).filter(Boolean) : [];
const tags = String(f.Tags ?? f.tags ?? '').trim();
const broll = String(f['B-Roll Keywords'] ?? f.broll_keywords ?? '').trim();
return [{
  json: {
    recordId: row.id,
    title: String(f['Video Title'] ?? f.video_title ?? f.Topic ?? '').trim(),
    script,
    description: String(f.Description ?? f.description ?? '').trim(),
    tags,
    broll,
    learningObjective: String(f.learning_objective ?? '').trim(),
    checklist: list(f.checklist),
    __source: 'existing-row-script',
  }
}];