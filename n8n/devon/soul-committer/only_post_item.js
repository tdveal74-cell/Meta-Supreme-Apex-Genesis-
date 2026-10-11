const out = [];
for (const it of $input.all()) {
  const j = it.json || {};
  if (j.mode === 'post') { out.push({ json: j }); }
}
return out;