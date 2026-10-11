const first = $input.first().json || {};
if (!first.failed_count) { return []; }
return [{ json: { subject: first.subject, body: first.body } }];