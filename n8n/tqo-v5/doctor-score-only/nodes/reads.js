// Score Only: Reads. Ruled by Tee 2026-10-24, after the same request to the
// doctor scored 85, 100 and 90 in three runs (executions 4354 to 4356): every
// row is read READS times and Parse Score Only writes the strictest of them, so
// a lucky single read can never clear a row. Each copy of the request is its
// own call to Run Script Doctor (Cerebras), which runs once per item.
const n = $('Run Config').first().json.READS;
const items = $input.all();
if (items.length !== 1) throw new Error('Score Only: Reads expected one request and received ' + items.length + '.');
return Array.from({ length: n }, (_, i) => ({ json: { ...items[0].json, read: i + 1 } }));
