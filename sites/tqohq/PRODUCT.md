# Product

<!-- impeccable:product-schema 1 -->

Where these answers come from: the DESIGN BRIEF that Tee answered in the orchestrating session, and the BRAND and PUBLIC FACTS packets. No interview ran in this folder, because this subagent has no question tool. The brief took the interview's place, as the job instructed. Items marked (inferred) or (open) are not settled facts.

## Platform

web

## Stack

Static HTML and CSS with one inline script, for Hostinger shared hosting. The page makes no third-party requests at runtime: no CDN, no analytics, no remote fonts. Fonts are open licensed and self-hosted as woff2 files beside the page.

## Users

Mid-career professionals who sense AI moving toward their jobs. Source: n8n/tqo-v5/build_script_prompt.js:48 gives the age range as 35 to 50. Most arrive from a YouTube video on a phone. The owner's own device is an iPhone 15 Pro, so 390x844 is the first viewport that matters.

## Product Purpose

The Quiet Operator (TQO) is a presenter-led YouTube channel that teaches AI tools and AI-era career strategy. The home page at tqohq.online has one job: a visitor enters their email in the one signup form.

## Positioning

Calm is the difference. Other channels on this subject are loud (build_script_prompt.js:55). Every episode states a learning objective, one sentence on what the viewer can do after watching, inside the first 30 seconds. Every episode also carries a checklist of 3 to 5 repeatable steps. Sources: Tee's stated profile of 2026-09-23, studio-qa tqo-checklist.md section 2, and validate_and_plan.js:94. (open) The live V5 script prompt writes no checklist, its descriptions are 2 to 3 sentences plus the audit line, and its close asks a comment question and points to the audit (build_script_prompt.js:79 to 82). So the page claims neither where the checklist appears nor that an episode closes on it, and every episode giving "at least one specific action the viewer can take today" (build_script_prompt.js:79) carries the close.

## Operating Context

Visitors come straight from a video, often mid-scroll on a phone. They are wary of hype and of course funnels.

## Capabilities and Constraints

- (2026-09-23) Tee ruled that the signup form is the Hostinger Reach form "TQO home page", framed on the page without Hostinger's script, so this page's own code sends no beacons and uses no browser storage. This supersedes the native form, `SIGNUP_ENDPOINT` and the endpoint deploy blocker described below. It also supersedes the Stack line: this page's own code now makes one third-party request, the frame, and Chromium makes it as soon as the home page opens. The framed Reach page is Hostinger's and makes its own requests, at least to cdn-reach.hostinger.com for its badge image, which sets a Hostinger cookie. It may also use cookies and storage of its own under its own origin. Signups go straight to Reach, tagged "form:TQO home page".
- One primary call to action, the email form. At most one soft rider.
- The form takes email (required) and first name (optional). It shows one consent line and links to privacy.html. The endpoint is read from `SIGNUP_ENDPOINT` in the inline script, which is empty today. While it is empty, submitting says signup is not open yet and stores nothing. With an endpoint set, the page reports success only on a 2xx answer.
- (open, inferred) What the list sends is not on record. The page proposes an email each time a new episode is published, and marks that offer `data-unconfirmed`. Tee must confirm it before deploy.
- (open) Undecided: whether Tee's name or rank may appear, which brand line leads, whether the audit page is live, the channel handle or URL, and whether the internal name "The Quiet Move" may be used in public.
- Deploy is blocked until tqohq.online has a hosting website with a document root and `SIGNUP_ENDPOINT` is set. See README.md.

## Brand Commitments

- Voice: calm, precise, anti-hype, proof-driven, quietly confident. He explains; he does not perform (build_qc_prompt.js:17, tee-voice).
- House rules: no em or en dashes, no exclamation marks, no hype vocabulary, sentence case headings, no invented numbers, no "experts say".
- The AI disclosure has no exception path (TQO canon ruling 11). Any presenter on screen is Tee's own AI avatar speaking in his own cloned voice. Nothing is rented as a persona (deploy/lipsync/README.md). As of 2026-09-16 the presenter was not built, so the page states this as a rule, never as a description of current episodes. Ruled by Tee 2026-09-23: the page's Note uses the pipeline's mandated disclosure verbatim, "Presented with a synthetic voice and synthetic likeness of Terrance Veal, used with his consent", so the site and every video description say the same thing and name him.
- Imagery: never a stranger standing in for him, no stock people, no robots or brains (build_script_prompt.js:84).
- TQO must not borrow the TSWS brand or the Meta Supreme ecosystem site's palette or fonts (SYS_SPEC_devon-ecosystem, lines 161 to 163).

## Evidence on Hand

- The episode format: learning objective inside 30 seconds, and a checklist of 3 to 5 steps.
- The QC gate's hard blockers, which hold an episode that states an outside statistic without a named source, including the "experts say" pattern (build_qc_prompt.js:40 to 46). Its voice line "Says what he does not know" (build_qc_prompt.js:17) is one descriptor in a score, not a gate, so the page does not promise it.
- The human publish gate: a rendered episode stops at Ready, and "nothing publishes until that box is ticked by hand" (SYS_OPS_the-tqo-render-lane-and-two-content-stores_v1_2026-09-10.md:61 to 66).
- The verified channel id UCZ58HLffFc3VJJ_RfvOLteQ. No URL built from it has been loaded, so the page does not link it.
- Absent, and never to be made up: subscriber counts, testimonials, results, logos, episode titles, dates, statistics.

## Product Principles

- Show the format. Do not describe the teacher.
- One ask, asked once, quietly.
- Disclose the machine before asking for anything.
- Say what is not known.

## Accessibility & Inclusion

WCAG 2.2 AA. Light and dark via prefers-color-scheme. Reduced motion honored. No horizontal scroll at 320px. The page reads correctly with JavaScript off.
