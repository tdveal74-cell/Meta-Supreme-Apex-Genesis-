// Same closed vocabulary as the row builders, but this value is data read back
// off an existing row rather than a literal, so an odd value is a data problem
// and must not take the pipeline down. Fix the casing and spacing, keep anything
// unrecognized as it stands, and default an untyped row to Flagship.
const ASSET_TYPES = ['Flagship', 'Short'];
function assetType(v) {
  const raw = String(v == null ? '' : v).trim();
  if (!raw) return 'Flagship';
  const hit = ASSET_TYPES.filter(t => t.toLowerCase() === raw.toLowerCase())[0];
  return hit || raw;
}

// A fresh Idea row used to reach OS 30 missing five fields and get held for
// things nobody had told it to fill. The pipeline knows all of them at script
// time, so it fills them here rather than waiting to refuse later.
//
// Human Review is deliberately NOT set. That gate is the one place a human has
// to look at the thing before it goes out, and a pipeline that ticks its own
// approval box is not a gate.
const ctx = $('Show Context: Script').first().json;
const row = $('One Idea at a Time').first().json;
const f   = row.fields || row;
const sc  = $('Originality Scan').first().json;

// The package, when this episode has one, comes from Package: Context and not
// from the row, because the row item was read before the lock was written. A
// locked headline and subject were chosen against the title the audience will
// actually see, so recomputing them from the finished script would throw that
// away. Wrapped, because the packaging lane does not run on every path.
let pkg = { packageLocked: false };
try { pkg = $('Package: Context').first().json || pkg; } catch (e) { /* no packaging lane on this path */ }

const isNCO = ctx.show === 'NCO';
const script = String(sc.script || f.Script || '');
const title  = String(sc.title || f['Video Title'] || f.Topic || '');
let desc     = String(sc.description || f.Description || '');

// 1. Disclosure. Set the flag only after making it true. Quality law 13
// (ruled 2026-09-30): the exact line sits in the first three lines of the
// description. Until 2026-10-17 a looser phrase such as "AI-assisted" anywhere
// stopped the line being added, and the line was never moved up when it sat
// lower down. Now every copy is removed and the line goes first, once.
const DISCLOSURE = 'Presented with a synthetic voice and synthetic likeness of Terrance Veal, used with his consent.';
desc = (DISCLOSURE + '\n\n' + desc.split(DISCLOSURE).join('').trim()).trim();

// 1b. The checklist. Ruled by Tee 2026-10-26 on a card, "Add it in Fill Run
// Fields": Build Script Prompt tells the TQO writer to leave the checklist out
// of the description because the pipeline writes it there from the checklist
// field, and until this block nothing did. The steps follow the writer's
// sentences, numbered in the order the script speaks them. TQO only, because
// only the TQO writer is told this. A copy left by an earlier pass is cut
// first, so the block appears once.
const STEPS_HEAD = 'The checklist from this episode:';
const steps = Array.isArray(sc.checklist) ? sc.checklist.map(s => String(s).trim()).filter(Boolean) : [];
desc = desc.split('\n\n' + STEPS_HEAD)[0].trim();
if (!isNCO && steps.length) desc += '\n\n' + STEPS_HEAD + '\n' + steps.map((s, i) => (i + 1) + '. ' + s).join('\n');

// 2. Claim validity. Anything anchored to a named model, a year or a headline
// goes stale fast. A principle about judgment does not.
const VOLATILE = /(20\d\d|GPT-?\d|Claude \d|Gemini|last (month|quarter|week)|this (month|quarter|year)|recently announced|just released|new model|currently)/i;
const validity = VOLATILE.test(script) ? 'Frequently Changing' : 'Slowly Changing';
const days = validity === 'Frequently Changing' ? 90 : 365;
const recheck = new Date(Date.now() + days * 86400000).toISOString().slice(0, 10);

// 3. Thumbnail backdrop. The broll array is already ordered concrete nouns, so
// its first entry is the most searchable subject the episode has. Only used
// when no package locked a subject first.
let broll = sc.broll;
if (Array.isArray(broll)) broll = broll.join(', ');
const subject = String(broll || '').split(',')[0].trim()
  || (isNCO ? 'soldier briefing room low light' : 'professional desk window evening');

// 4. Thumbnail headline. Word ceiling from the brand spec: TQO 5, NCO Forge 4.
// Same fallback rule: a locked headline wins, this is the unpackaged path.
const cap = isNCO ? 4 : 5;
let head = title.replace(/[—–]/g, ' ').replace(/[^A-Za-z0-9 ]/g, ' ').replace(/\s+/g, ' ').trim();
const STOP = new Set(['the','a','an','of','to','in','on','at','for','with','and','or','your','you','that','this','is','are','what','how','why']);
let words = head.split(' ').filter(Boolean);
if (words.length > cap) {
  const strong = words.filter(w => !STOP.has(w.toLowerCase()));
  words = (strong.length >= 2 ? strong : words).slice(0, cap);
}
head = words.join(' ').toUpperCase();

const locked = pkg && pkg.packageLocked === true;
const finalSubject = (locked && pkg.primarySubject) ? pkg.primarySubject : subject;
const finalHead = (locked && pkg.thumbnailHeadline) ? pkg.thumbnailHeadline : head;

return [{ json: {
  recordId: sc.recordId,
  tableId: ctx.tableId,
  tableRef: ctx.tableRef,
  packageRespected: locked,
  body: { typecast: true, records: [{ id: sc.recordId, fields: {
    'Description': desc,
    'AI Disclosure': 'Disclosed in description',
    'Claim Validity': validity,
    'Recheck By': recheck,
    'Primary Subject': finalSubject,
    'Thumbnail Headline': finalHead,
    'Channel': ctx.channel,
    'Asset Type': assetType(f['Asset Type'])
  } }] }
} }];