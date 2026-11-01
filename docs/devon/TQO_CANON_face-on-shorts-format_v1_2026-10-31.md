# TQO and NCO Forge Shorts: face on, in the Sisinty format

Ruled by Tee on 2026-10-31, on cards in one session, and measured the same day.
This is the format every TQO and NCO Forge Short is built to. It extends the
2026-09-08 Sisinty benchmark canon
(`docs/devon/TQO_CANON_sisinty-benchmark-refresh_v1_2026-09-08.md`), which
recorded the beats from transcripts and never saw the picture. The evidence is
in `docs/devon/assets/TQO_PROOF_face-on-shorts-reference_v1_2026-10-31.json`.

## The rulings

1. Every Short carries Tee's face. Asked which shows could use voice-only
   Shorts, he answered: "My face needs to be on them and my shorts needs to be
   like https://youtube.com/@vaibhavsisinty". MoneyPrinterTurbo, which cannot
   carry a face, has no role in either show's Shorts.
2. The face comes first from his HeyGen avatar, reading a native Short script
   in his professional clone. The recommendation on the card was clipping his
   long-form masters, which spends no avatar credits; Tee chose HeyGen. The cost
   objection is logged here once: every HeyGen render spends plan credits and
   the account's auto reload can reach his card, so each render checks the
   balance first and goes to him on a card before it bills.
3. The frame splits 50/50 now: proof in the top half, his face in the bottom
   half. The 2026-09-15 stacked layout gave the proof 65 percent.
4. A Short ends on one comment keyword with a real deliverable, delivered
   within 24 hours (canon ruling 8 of 2026-09-08). This wins over the TQO
   skill's old "no like, subscribe or link ask".
5. Voice Lab moved to his professional clone. ElevenLabs lists
   `LLhnFOCTr3y3wrH59DtJ` "T Veal" as category `professional`, his trained
   clone, and `ypnKDQtIhp4N3yn4UnqO` "T Veal 2.1" as category `generated`, a
   voice designed from a written description. Read 2026-10-31 through the
   ElevenLabs connector. The repository's `show_registry.py` still names the
   generated one as his clone; draft PR #460 corrects it.

## The reference Short

Tee sent `youtube.com/shorts/zopfY5ONIjA`, "Elon Musk Just Gave Grok AI Full
Control of Your Phone!", 1:44, as a screenshot and a screen recording. Gemini
read the whole video from YouTube. Claude then checked the first 50 seconds
against Tee's recording at one frame every 2 seconds, not frame by frame. Of the
14 shots Gemini listed in that span, 13 landed on a sampled frame and matched,
about a second early in the recording at 0:04; the "#02 PAGES" card (0:31 to
0:32) fell between samples and was not seen. One correction: in
the split shots he is framed chest up, not waist up. One claim is withdrawn:
Gemini said product names were pasted onto other products' screens, and the
frame it cited shows no font mismatch.

What it does, observed:

- 27 shots in 104 seconds, about 3.9 seconds a shot, tightening to about 2.3
  seconds in the close with punch-in zooms.
- Two layouts alternate. While he explains, a 50/50 split: proof on top (a
  product screen, a phone mockup or a short b-roll clip), him chest up and
  centred below. On each numbered point he goes full frame and a card reads
  "#01 PHONE CONTROL", with a red flash and a whoosh on the cut.
- Captions sit on the seam in short phrases of about 2 to 4 words, bold white
  sans on a black box. The hook alone mixes a small sans word with a large italic serif one.
- Script: a named entity and a claim in the first two seconds, a counted
  promise ("six things"), each item as "before" then "now" with one example, an
  explicit caveat ("Now the honest part. It is still a beta"), a one line
  summary, a comment ask and a free guide behind a link.
- Sound: an upbeat bed under everything, a whoosh on each card, soft clicks on
  the screen inserts.
- YouTube shows its "AI" label on it. Gemini reads him as live footage keyed
  onto a virtual office, so the label more likely covers the set than his face.
  Unverified.

## The house grammar, six benchmark Shorts

Gemini also read six of the Shorts from the 2026-09-08 benchmark
(`6UR-EXqeNW4`, `WmeEd3A64AU`, `fVIfAOJF9xc`, `2vKU3J29FJw`, `KxAGWENTUpw`,
`FZml4h4uXJU`), observations only and not frame checked. Traits in at least
five of the six: captions burned in for the whole Short, white, typically 1 to 5
words at a time with maximums from 3 to 8, key words set apart by type or colour; the face full frame in the upper
centre third as a medium close-up; average shot length 2.4 to 2.9 seconds; the
named tool on screen as a real screen recording with push-ins; a ducked
electronic bed and a whoosh on transitions; a hard ending. All four produced
Shorts end on a comment keyword ("FREE", "printer", "job", "link"); the two
interview clips do not. In three of the six the face stays on screen in the
bottom half of a split while the tool shows above.

## What our Shorts take from it, and what they do not

Taken: the 9:16 frame split 50/50; proof on top as a real screen recording of
the tool being taught, never a staged screen; Tee's face chest up below and full
frame on each numbered beat; seam captions of a few words, at most five, in white on black;
a named, specific hook inside two seconds; a numbered body; one honest caveat;
one comment keyword with a real deliverable; a ducked bed; 45 to 75 seconds,
which is the skills' range and sits inside the benchmark's 33 to 153.

Not taken: staged cold opens with extra actors or props, effects explosions,
AI morphs of real people, and any screen that shows a product doing something
it does not do. Tee's Quiet Operator voice stays calm and specific; the format
is borrowed, the hype is not.

Disclosure does not change: the C4 line, "Presented with a synthetic voice and
synthetic likeness of Terrance Veal, used with his consent.", in the first three
lines of every description, and the YouTube altered or synthetic content label
on any Short with his avatar. His signed likeness consent is
`TQO_NCOFORGE_D9B_CONSENT_TERRANCE_SIGNED_2026-08-19.pdf` in the TQO Drive
folder; no separate consent record for the voice clone is filed.

## What the render worker does now

On the live worker at srv1936193 since 2026-11-01T00:59Z (commit `122bc70`):

- `presenter_composite` takes `split` (0.3 to 0.75, stacked only). At 0.5 the
  seam is at 960 of 1920 and the default caption follows it. Without it the
  layout is the 1250 one, unchanged.
- `caption_srt` turns a `word_timings` file into seam captions of at most five
  words (`max_words` plus one, default four).

The NCO 30 layout test of 2026-11-01 rendered with those on the box and showed
four defects, and Tee ruled the fixes on a card the same day. They are in the
repository from that day and reach the box with the next upgrade:

- `caption_srt` takes `hard_max` (no cue passes `max_words`), `max_chars` (a
  cue longer than it is cut; one line held to 23 characters at FontSize 12 in
  that test) and `bridge` (gaps shorter than it are closed, so the caption box
  stops dropping out for a frame between phrases). Ruled: "3 words max, no
  blinks".
- `presenter_composite` takes a `card` on an emphasis window, laid over the
  full-frame face for that window, and `emphasis_caption_style`, a second
  caption placement used inside the emphasis windows only, so the caption sits
  on his collar and not across his mouth. Ruled: "Number over full-frame face".
- `presenter_composite` takes `loudness` and `true_peak`, one loudnorm pass on
  the finished mix. On the NCO 30 audio, I -14 and TP -1 measured -14.7 LUFS
  and -1.0 dBTP before the AAC encode and -0.9 after it, so a Short asks for
  TP -1.5. Ruled: "Add a loudness stage to the worker". It is opt-in: every
  existing caller keeps the graph it had.

The `word_timings` model matters for captions. On the NCO 30 audio `base.en`
wrote three words that are not in it (checked by three Gemini models with a
spliced positive control) and `small.en` got all 180 words of the window
right, at about three times the time (23 s against 7.7 s for 80 s of audio).
Caption runs pass `model: small.en`.

Not built yet, each a later piece of work: the hook headline and a payload
card generator in the worker (the test cards were drawn by a script outside
it), punch-in zooms, sound effects,
filling the top half with a 16:9 clip instead of letterboxing it, and the n8n
lane that scripts the Short, voices it in his clone, renders the HeyGen avatar
and calls the worker. No portrait Short has rendered end to end. Nothing
publishes before Tee watches the first one through.
