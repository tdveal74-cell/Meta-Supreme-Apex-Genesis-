/**
 * Reads the carousel out of a content row.
 *
 * TQO FINAL V5's Parse Packaging node writes every episode's packaging into
 * the row's platform_packaging column as plain text, and the carousel is one
 * block of it:
 *
 *   CAROUSEL - The Quiet Move Framework <P10>
 *     1. The Quiet Move: Make every green check count
 *     2. Capability: It did the work on real files
 *
 * ending at the first blank line. The packaging prompt asks for 7 to 9 slides,
 * the hook first and the Quiet Move (TQO) or Forge Rule (NCO) last, each one
 * line of at most 12 words. Those rules are checked in check.mjs, not here: a
 * parser that silently dropped a bad slide would hide the fault it should show.
 */

export function parseCarousel(packaging) {
  const lines = String(packaging || "").split(/\r?\n/);
  const start = lines.findIndex((line) => /^CAROUSEL - /.test(line));
  if (start < 0) return null;
  const head = lines[start].replace(/^CAROUSEL - /, "");
  const from = (head.match(/<([^>]*)>\s*$/) || [])[1] || "";
  const title = head.replace(/\s*<[^>]*>\s*$/, "").trim();
  const slides = [];
  for (let i = start + 1; i < lines.length; i += 1) {
    const line = lines[i];
    if (!line.trim()) break;
    const m = line.match(/^\s*(\d+)\.\s+(.*)$/);
    if (!m) break;
    slides.push(m[2].trim());
  }
  return { title, from, slides };
}

/** "Capability: It did the work" becomes a label and a line; a slide with no
 *  label before a colon is all line. Only a short leading phrase counts as a
 *  label, so a colon inside a sentence is left alone. */
export function splitSlide(text) {
  const m = String(text).match(/^([A-Z][\w' ]{0,28}):\s+(.+)$/);
  return m ? { label: m[1].trim(), line: m[2].trim() } : { label: "", line: String(text).trim() };
}
