// Drains unsynced Thread Receipts into the Notion Thread Log.
// 16 Oct 2026, ruled by Tee: the buffer is the n8n data table
// at_tqo_thread_receipts (JCwPJ37BmyUW21r1), no longer Airtable, because the
// capture webhook now files there. Notion is still the memory. Only rows whose
// synced_to_notion is not true are shipped, so a rerun does not re-ship a ticked row. A
// row whose page was created and whose tick then failed is re-shipped, and
// since 2026-09-06 (ruled by Tee) that no longer duplicates the page: every
// page carries its source row key in its Source row property, Find Existing
// Page queries the Thread Log for it before anything is created, and a row
// that already has its page goes straight to the tick.
//
// 6 Aug 2026: DB was originally set to the DATA SOURCE id (a5bcfbf5-...),
// which is what the Notion MCP connector uses. The public REST API wants the
// DATABASE id and returns a misleading 404 'make sure it is shared with your
// integration' when given a data source id - the sharing is fine, the id is
// simply the wrong kind of object.
//
// 6 Sep 2026, ruled by Tee after the operational report found this node lossy:
// nine Areas (ACX was ruled the ninth on 2026-08-20 and this list still had
// eight, so an ACX receipt landed with no Area); properties and the title are
// chunked into 2000 character text objects instead of truncated; Canon and
// Verify move to the page body, where the thread log skill files them; Raw
// rides into the body verbatim so a parse error is always recoverable; and
// an Area outside the nine is named in the body instead of dropped silently.
// Nothing here invents a word: every field is the receipt as it was posted.
const AREAS = ['TQO', 'Podcast', 'NCO', 'ACX', 'Health', 'Money', 'Family', 'Learning', 'Systems'];
const DB = 'e91b0a7b-42c0-405e-bf5b-39975e0d4e38';
// Notion caps one text object at 2000 characters, one rich_text array at 100
// objects and one create call at 100 children. A property can never exceed
// its cap in practice (the cap is 200,000 characters); if one ever does, the
// run throws and files nothing rather than truncating a receipt. A body can: Raw, Canon and Verify together can need
// more than 100 blocks, so the body is cut at the cap with a block that says
// so and names the data table row, and the rest of the batch still drains.
const CHUNK = 2000;
const MAX_OBJECTS = 100;
const MAX_CHILDREN = 100;
const NL = String.fromCharCode(10);

function txt(v) {
  return String(v === undefined || v === null ? '' : v).trim();
}

function chunks(s) {
  const out = [];
  for (let i = 0; i < s.length; i += CHUNK) { out.push(s.slice(i, i + CHUNK)); }
  return out;
}

function text(s) {
  return { type: 'text', text: { content: s } };
}

function objects(v) {
  const s = txt(v);
  if (!s) { return []; }
  const parts = chunks(s);
  if (parts.length > MAX_OBJECTS) {
    throw new Error('A receipt field exceeds ' + (CHUNK * MAX_OBJECTS) + ' characters, more than one Notion property holds. Nothing was filed.');
  }
  return parts.map(text);
}

function rich(v) {
  return { rich_text: objects(v) };
}

function paragraph(s) {
  return { object: 'block', type: 'paragraph', paragraph: { rich_text: [text(s)] } };
}

function heading(s) {
  return { object: 'block', type: 'heading_2', heading_2: { rich_text: [text(s)] } };
}

function section(children, title, body) {
  const s = txt(body);
  if (!s || s.toLowerCase() === 'none') { return false; }
  children.push(heading(title));
  chunks(s).forEach(function (c) { children.push(paragraph(c)); });
  return true;
}

function joinParts(pairs) {
  const out = [];
  for (const p of pairs) {
    const v = txt(p[1]);
    if (!v || v.toLowerCase() === 'none') { continue; }
    out.push(p[0] ? p[0] + ': ' + v : v);
  }
  return out.join(NL);
}

const out = [];
for (const it of $input.all()) {
  const j = it.json || {};
  // Data table rows carry lowercase column names; map them onto the field
  // names the rest of this node was written against.
  const f = {
    Title: j.title, Date: j.date, Area: j.area, Platform: j.platform,
    Summary: j.summary, Decided: j.decided, Built: j.built, Open: j.open,
    Next: j.next, Canon: j.canon, Verify: j.verify, Raw: j.raw
  };
  if (j.synced_to_notion === true) { continue; }

  const title = txt(f.Title);
  if (!title) { continue; }

  const dtId = (j.id === undefined || j.id === null) ? '' : String(j.id);
  if (!dtId) { continue; }
  // The dedupe key. A row migrated from Airtable keeps its Airtable record id,
  // so it matches the page the old drain already filed for it; a row filed
  // into the data table directly is keyed dt:<row id>, which cannot collide
  // with a rec... id.
  const rowId = txt(j.airtable_record_id) || ('dt:' + dtId);

  const props = {};
  props.Title = { title: objects(title) };

  const d = txt(f.Date).slice(0, 10);
  if (d.length === 10) { props.Date = { date: { start: d } }; }

  const raw = f.Area;
  const list = Array.isArray(raw) ? raw : (raw ? String(raw).split(',') : []);
  const picked = [];
  const dropped = [];
  for (const a of list) {
    const clean = String(a).trim();
    if (!clean) { continue; }
    if (AREAS.indexOf(clean) === -1) { dropped.push(clean); continue; }
    if (picked.indexOf(clean) === -1) { picked.push(clean); }
  }
  if (picked.length) {
    props.Area = { multi_select: picked.map(function (n) { return { name: n }; }) };
  }

  props.Summary = rich(f.Summary);
  props.Decisions = rich(f.Decided);
  props['Open threads'] = rich(joinParts([['', f.Open], ['Next', f.Next]]));
  props.Artifacts = rich(f.Built);
  // The dedupe key. Find Existing Page queries this before any create.
  props['Source row'] = rich(rowId);

  // The body: provenance first, then Canon and Verify where the thread log
  // skill files them, then the receipt exactly as it was posted.
  const plat = txt(f.Platform) || 'unknown';
  const children = [];
  children.push(paragraph('Platform: ' + plat + '. Filed from n8n data table at_tqo_thread_receipts row ' + dtId + ' (Source row ' + rowId + ')' +
    ' by the Notion Buffer Drain. Nothing below is enriched; it is the receipt as posted.'));
  if (dropped.length) {
    children.push(paragraph('Area not in the nine, so not tagged: ' + dropped.join(', ') +
      '. The Area vocabulary is ruled, not inferred; fix the receipt or rule a new Area.'));
  }
  if (section(children, 'Canon', f.Canon)) {
    children.push(paragraph('Canon present: this also belongs in Strategic Decisions, and only a human files it there.'));
  }
  section(children, 'Verify', f.Verify);
  section(children, 'Raw receipt, verbatim', f.Raw);
  if (children.length > MAX_CHILDREN) {
    const cut = children.length - (MAX_CHILDREN - 1);
    children.length = MAX_CHILDREN - 1;
    children.push(paragraph('Body cut here: ' + cut + ' more block(s) of this receipt did not fit the Notion create limit of ' +
      MAX_CHILDREN + ' blocks. Every property above is complete; the full raw receipt is in n8n data table at_tqo_thread_receipts row ' + dtId + '.'));
  }

  out.push({ json: {
    rowId: rowId,
    dtId: dtId,
    title: title,
    notionBody: { parent: { database_id: DB }, properties: props, children: children }
  } });
}
return out;
