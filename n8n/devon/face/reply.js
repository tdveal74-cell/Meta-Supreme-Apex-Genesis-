// The chat widget reads the last node's output field. Memory writes happen before
// this so a failed insert (continueRegularOutput) still lets the reply through.
let rowsOut = [];
try { rowsOut = $('Memory Rows').all().map(i => i.json || {}); } catch (e) { rowsOut = []; }
const a = rowsOut.filter(r => r.role === 'assistant')[0];
return [{ json: { output: a ? a.content : 'DEVON has nothing to say.' } }];
