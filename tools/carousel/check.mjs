/**
 * The rules a carousel must pass before it is drawn. Measured, never judged.
 *
 * The slide text comes from the packaging model, after the script passed its
 * own gates, so the carousel is held to two things: the shape the packaging
 * prompt asked for, and the script it was cut from. Every numeral on a slide
 * must appear in that row's script, which passed the Sources Gate, so a
 * carousel cannot carry a figure the episode itself was not allowed to state.
 * The dash rule is Tee's, studio wide.
 */

const NUM = /\$?\d[\d,]*(?:\.\d+)?%?/g;
const bare = (t) => t.replace(/[$,%]/g, "").replace(/\.$/, "");

export function checkCarousel(carousel, { show, script }) {
  const problems = [];
  if (!carousel) return ["no CAROUSEL block in platform_packaging"];
  const { slides } = carousel;
  if (slides.length < 7 || slides.length > 9) problems.push(`${slides.length} slides; the packaging prompt asks for 7 to 9`);
  const closer = show === "NCO" ? "Forge Rule" : "Quiet Move";
  if (slides.length && !new RegExp("^(?:The )?" + closer, "i").test(slides[slides.length - 1])) {
    problems.push(`the last slide is not the ${closer}`);
  }
  const scriptNumbers = new Set((String(script || "").match(NUM) || []).map(bare));
  slides.forEach((slide, i) => {
    const words = slide.split(/\s+/).filter(Boolean).length;
    if (words > 12) problems.push(`slide ${i + 1} is ${words} words; at most 12`);
    if (/[–—]/.test(slide)) problems.push(`slide ${i + 1} carries an em or en dash`);
    for (const raw of slide.match(NUM) || []) {
      if (!scriptNumbers.has(bare(raw))) problems.push(`slide ${i + 1} states ${raw}, which the script does not`);
    }
  });
  if (/[–—]/.test(carousel.title)) problems.push("the carousel title carries an em or en dash");
  return problems;
}
