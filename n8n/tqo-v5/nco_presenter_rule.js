// NCO Presenter Rule, ruled by Tee 2026-10-07: NCO Forge is presenter led, the
// same as TQO. Terrance Veal presents it in his own likeness and his own cloned
// voice. The NCO block in Build Script Prompt still says single narrator and is
// measured by the canon, so the correction is appended here instead.
const ctx = $('Show Context: Script').first().json;
const j = $input.first().json;
if (ctx.show !== 'NCO' || !j.body) return [{ json: j }];
const rule = 'PRESENTER: Terrance Veal presents every NCO Forge episode himself, on camera, in his own likeness and his own cloned voice. Where anything above says narrator, it means him speaking to camera. Never write a line that only works as voiceover over stock footage of a stranger.';
return [{ json: { ...j, body: { ...j.body, system: String(j.body.system || '') + '\n\n' + rule } } }];
