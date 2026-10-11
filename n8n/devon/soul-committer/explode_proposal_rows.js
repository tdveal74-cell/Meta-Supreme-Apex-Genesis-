const first = $input.first().json || {};
const rows = Array.isArray(first.rows) ? first.rows : [];
return rows.map(r => ({ json: r }));