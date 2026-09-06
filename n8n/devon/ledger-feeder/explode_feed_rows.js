const first = $input.first().json || {};
const logs = Array.isArray(first.logs) ? first.logs : [];
return logs.map(l => ({ json: l }));