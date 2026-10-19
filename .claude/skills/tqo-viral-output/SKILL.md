---
name: tqo-viral-output
description: The Quiet Operator short and long-form drafting skill. Applies the working hook and structure patterns of the mid-career AI income niche in TQO's calm, precise, anti-hype voice. Use when drafting YouTube Shorts, Reels, TikToks or long-form episodes for The Quiet Operator, or similar professional AI content in Tee's own voice.
---

# TQO viral output

Drafts content shaped to the patterns that tend to earn views in the AI for
professionals niche, while staying inside Quiet Operator constraints: calm,
specific, anti-hype, proof first. Tee presents every episode himself, in his own
likeness and his own cloned voice, so every line has to work spoken by him on
camera. Never write a line that only works as voiceover over a stranger.

## Niche

Mid-career professionals who feel AI moving toward their job and want to
quietly build income or a skill edge before they need it. No shouting and no
"get rich". Documented experiments and clear mechanisms.

## Working patterns

These are house hypotheses taken from watching the niche. They are not
measured on our channel. Treat them as defaults to test, and replace one the
day a channel number disagrees with it.

Patterns that tend to work:

- A specific before and after with a number: time saved, steps removed, one concrete output
- One tool or one process per piece, never a list of ten
- Framing that says you can do this while keeping the job
- A hook that names the result in the first 3 seconds
- On-screen text that repeats the key claim
- A visible review step that keeps the human in control

Patterns that tend to fail:

- Vague motivation or mindset talk
- Generic career advice with no mechanism
- Pure theory
- Stacked lists with no single worked example
- Hype words: game-changer, unlock, seamless, cutting-edge, and "leverage" used as filler

## Voice rules

- Short sentences next to longer ones
- Concrete nouns and verbs
- Claims that could be checked
- No em dashes, no en dashes, no semicolons, straight quotes only
- No empty intensifiers
- Teacher stance, calibrated confidence
- Where this skill and `tee-voice` disagree, `tee-voice` wins

## Short format (Short, Reel or TikTok, 45 to 75 seconds)

1. Hook, 0 to 3 seconds: the result plus a time or a number
2. Setup, 3 to 12 seconds: what most people do instead
3. Mechanism, 12 to 40 seconds: the exact narrow job the agent or process does
4. Boundary, 40 to 55 seconds: what the human still does
5. Test, 55 to 70 seconds: one way the viewer can try it this week
6. Close: one sentence restating the system, with no like, subscribe or link ask

Write the on-screen text lines beside the spoken lines, one per beat, each
repeating the claim that beat makes.

## Long-form format

Long-form follows the live TQO episode canon, which is mirrored in
`n8n/tqo-v5/build_script_prompt.js` and split into rules in
`services/devon/tqo_canon.py`. Read the mirror before drafting a long-form
script, because it is the version the pipeline actually sends and this list is
a summary of it.

- 1,200 to 2,000 words of spoken narration, target 1,600, TTS ready, no headings or stage directions
- Hook in the first 10 to 15 seconds, opening on the same specific result as the Short
- Learning Objective inside the first 30 seconds: one sentence saying what the viewer will be able to do by the end
- 8 to 12 sections, each carrying one point backed by a mechanism, a step or a sourced figure
- Show the source files or data, and a side by side of manual and agent output, redacted as needed
- Name the one change that made it usable
- A 3 to 5 step checklist spoken in order inside the body, as step one, step two and so on
- At least one action the viewer can take today, which is the one-week test
- Close on one question for the comments, specific to the episode, with the word comments in the last spoken sentence and nothing after it
- B-roll is cutaways of objects, screens, documents or places, never a stranger standing in for Tee

## Hook templates

The numbers below are placeholders showing shape. Every number in a delivered
hook comes from Tee's own measurement of that task. If he has none, the hook
names the result without a number rather than borrowing one of these.

- "I stopped writing the Monday report by hand. An agent does it now. Review takes four minutes."
- "One recurring task. One agent. Three hours back on Monday."
- "I gave the agent the last good version of the report and the three source files. That was the whole setup."

## Process

1. Ask Tee for the single recurring task or result.
2. Ask for the number: time, steps or percentage. If he has none, draft without one and say the slot is open.
3. Draft the Short first.
4. Strip AI tells against `tee-voice`.
5. Add the on-screen text lines that match each spoken claim.
6. Offer the long-form expansion only after the Short is solid.

## Constraints

- Never claim a piece will go viral, and never promise a view count.
- Never invent a metric, a result or a source. "Unverified" beats a plausible figure.
- Keep the human review step visible in every piece.
- Stay inside Quiet Operator voice and the hard rules in the user preferences.
- Platform policy and AI disclosure are compliance items with no exception path. If a draft touches either, flag it for Tee rather than deciding.
