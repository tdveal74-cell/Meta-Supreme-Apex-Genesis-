# The TQO home page, and the episode promises made true in V5

Written 2026-09-23. Tee asked for access to build a website on Hostinger, and
ruled on the day that tqohq.online becomes the TQO home page with one email
signup, built by hand, kept in git under `sites/tqohq`, and deployed later as
static files to his Premium web hosting.

## What the account held

Read through the claude.ai Hostinger connector, which already reaches the whole
account, so no token or terminal config was needed and PR #283, which added one,
was closed on Tee's word. tqohq.online is the only website on the Premium plan,
account `u983658559`, and it is a Website Builder site: `root_directory` null,
and the file listing API answers 404. Static files cannot land on it until it
is replaced by a hosting website. The Reach profile on the domain is active as
a sending domain and holds zero signup forms; the API has no form create
endpoint. editforge.online is not on web hosting at all and points at the VPS.
The "pending setup" domain entry is an unclaimed free domain transfer credit
from the Premium plan, created two seconds after it, with no transfer in flight.

## The page

Three directions were built and rendered from different skill stacks under
Impeccable, and two judges scored them: editorial 73, taste 68, the memo 84.
The memo won. The page reads as a memo addressed to the visitor: To, From, Re
(the h1), a Note carrying the AI disclosure, then the signup. Four critics
found 10 blocker or major items and a fresh verifier re-measured each one.
One font is self hosted under OFL and the page makes no request off its own
origin, which `sites/tqohq/check.mjs` measures in Chromium on every run.

Tee ruled the page's Note uses the pipeline's mandated disclosure verbatim,
"Presented with a synthetic voice and synthetic likeness of Terrance Veal, used
with his consent", so the site and every video description say the same thing
and name him. He first ruled the page anonymous on a claim from this session
that nothing on record used his name publicly; that claim was wrong, because
the C4 disclosure names him in every description, and it was corrected before
the second ruling.

## The lane now does what the page promises

The page promises a Learning Objective inside 30 seconds, a 3 to 5 step
checklist, and a close on one comment question with no like or subscribe ask.
`TQO FINAL V5` did none of the last two: its script prompt closed on the free
audit, its openers included "Do this before it's too late", and no node wrote
a checklist a viewer could see. Tee ruled to keep the promises and fix the lane.

Ten nodes changed in one update: Build Script Prompt, Series Addendum, Parse
Script JSON, both expansion passes, Build Doctor Prompt, Parse Doctor Output,
Script Gate: Quality, Script: Fill Run Fields and one sticky note. The writer
now returns `learning_objective` and `checklist`; the gate lands a TQO draft in
Error with a named reason when the objective is missing or past 70 words, the
checklist has fewer than 3 or more than 5 steps, or the close asks for likes,
subscribes or the audit; the description carries the checklist written out
under "The checklist from this episode:". NCO is byte identical.

The version also carried the unpublished C4 disclosure draft `ab204ec5`, which
a cold critic checked first and passed. Published 2026-09-23 as
`ff090725-5ce1-4a45-89f4-65b4dc26b878` on Tee's ruling "publish both", after the
verifier returned publish with no blocker or major. Read back: `versionId`
equals `activeVersionId`, `activeVersion.sameAsDraft` true, and the live Build
Script Prompt is byte identical to `n8n/tqo-v5/build_script_prompt.js`, sha256
`1b6f978e...b769c1b6`. Rollback: `ab204ec5`, then `d6c0de00`.

Nothing here ran against a real model. Cerebras has answered 402 since
2026-09-19, so the proof is node bodies run in node against fixtures: 15 fill
cases and 23 end to end chain cases passed, and the same fixtures fail 20 times
against the old gate. The canon measurement moved from 805 to 973 words and
`tqo.close.one-quiet-cta` no longer offers the audit.

## Minor gaps the verifier left, graded

The gate checks the checklist field, not that the steps are spoken. It misses
near misses such as "hit the like button" or a second closing question. A model
that numbers its own steps would print "1. 1." in the description. Each is
caught by Tee reading every script before `script_released`. HAS_DISCLOSURE
still matches the words "AI assistance" as topic words and would write the flag
without the line; measured blast radius is zero rows today, and it predates
this change.

## DEVON RECEIPT

AREA: TQO
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_tqohq-home-page-and-the-episode-promises_v1_2026-09-23-1206.md
DATE: 2026-09-23
DECISIONS: Tee ruled tqohq.online the TQO home page with one email signup, hand built in git and deployed later to Hostinger web hosting; the flagship design skills for the build; keep the episode promises and fix the lane; publish the C4 draft with the lane fix; a Reach form for signup; replace the Builder site by API after one more go; link the channel by id; use the mandated disclosure on the page and name him.
FINDINGS: tqohq.online is a Website Builder site with no document root. Reach holds no signup form and the API cannot create one. V5 closed on a retired audit and wrote no viewer checklist. The C4 disclosure fix had sat unpublished since 03:15Z. The session told Tee his name was not public for TQO, which was wrong. Other people use the name The Quiet Operator on YouTube, Spotify and Gumroad, ownership unchecked.
OPEN: Tee creates and activates a Reach signup form, then the embed is read and its third party script is put to him. What the list sends and who sends it: no lane emails subscribers per episode. The privacy notice needs a contact address. Replacing the Builder site waits on his last go. The NCO branch still carries the hype opener and a subscribe close, left alone because the ruling named TQO. Two Ready tqo_content rows carry the old disclosure line mid body.
STATUS: V5 published and read back. Site built and verified in PR #285, not deployed.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
