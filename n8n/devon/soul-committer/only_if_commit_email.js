const first = $input.first().json || {};
if (!first.send_email) { return []; }
return [{ json: { subject: first.subject, body: first.body } }];