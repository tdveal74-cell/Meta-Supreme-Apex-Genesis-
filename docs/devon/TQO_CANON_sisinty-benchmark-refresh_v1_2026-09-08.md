---
title: Sisinty benchmark refresh, the top performers read as the model for TQO and NCO content
type: TQO_CANON
version: 1
date: 2026-09-08
area: TQO (NCO and Systems cross reference)
status: benchmark-pulled-and-read-rulings-filed-to-thread-log-soul-write-pending-proof
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base: 17e1ce5
branch: claude/youtube-content-analysis-2z323s
extends: aaa-flagship-canon 1.0.0 (compiled 2026-08-11, Tee's ruling recJJGTnSNzF5U395)
supersedes: none
---

# Sisinty benchmark refresh v1

## Verdict in one paragraph

Tee sent a link to one video (`6OmqsFrRv4I`, this week's roundup on the
Vaibhav Sisinty channel, `UClXAalunTPaX1YV185DWUeg`) and asked for his top
performing videos and Shorts to be read as the model for Tee's own content,
and for the result to reach the Pinecone index DEVON recalls from. The channel
is already the AAA Flagship benchmark by Tee's 2026-08-11 ruling, so this is
the first refresh of that canon rather than a new standard. Everything below
came from vidIQ on 2026-09-08: channel stats, the fifty most popular long
forms, the fifty most popular Shorts, and fifteen transcripts. The raw pull is
saved beside this file as
`assets/TQO_PROOF_sisinty-benchmark-pull_v1_2026-09-08.json`, and every
count in this document was computed from that file by script, not remembered.
Twelve rulings for TQO and NCO were derived from the read and filed to the
Notion Thread Log as numbered Decisions, which is the only sanctioned path
into `tee-soul-layer`: the Soul Layer Write-Back polls that log and embeds one
record per numbered ruling. The Pinecone write is therefore automatic and
proven only by the workflow's execution record and the console, and section 9
says which of those this session could read.

## 1. What was pulled, and what was not

| Read | Tool | Result |
|---|---|---|
| The linked video | vidIQ `get_videos_by_ids` | `6OmqsFrRv4I`, "GPT-6 Astra Just Did What Claude Fable 5.1 Couldn't (+14 AI Updates)", published 2026-09-08 13:33 UTC, 11:57 long, 2,648 views at pull time (about ninety minutes old) |
| Channel | vidIQ `channel_stats` | 835,000 subscribers, 65,737,476 views, 728 videos; thirty days 2026-08-09 to 2026-09-08: +41,000 subscribers, +3,814,279 views, 27 uploads |
| Long form, most popular | vidIQ `channel_videos(long, popular)` | 50 rows, 45 of them published in 2026 |
| Shorts, most popular | vidIQ `channel_videos(short, popular)` | 50 rows |
| Transcripts | vidIQ `video_transcript`, language en | 15 of 15 returned: 8 long form, 6 Shorts, plus the linked video |
| Credits | vidIQ `balance` | 172 read before the transcripts, 102 read after them, so the meter charged 70; fifteen transcript calls at the listed 5 each would be 75, and the 5 credit gap is unexplained and left as measured |

Not pulled: Instagram, LinkedIn, view-duration or retention curves (not
exposed to a third party), thumbnails as images (the URLs are in the JSON),
and frame walkthroughs. The 2026-08-11 canon carries three frame-accurate
walkthroughs already and nothing here contradicts them.

## 2. The top performers

### 2a. Long form, ranked by views, 2025 to 2026 uploads

The list excludes two guest podcasts from 2023 and 2024 (`uVVri3khsco`
881,604 views, `tx8b5P5T2io` 219,723) because the format is not one Tee
would copy. Like rate is likes divided by views.

| Rank | ID | Title | Published | Views | Like rate | Comments | Length | Format |
|---|---|---|---|---|---|---|---|---|
| 1 | `YYAMwM-F30o` | China Just Dropped A Free AI That Beats Claude Fable 5 (Here's How To Use It +21 AI Updates) | 2026-08-30 | 692,849 | 0.8% | 237 | 22:53 | weekly roundup, transcript read |
| 2 | `KjNsnE_vsyc` | Forget Prompt Engineering, This Is What Actually Matters in AI | 2026-05-02 | 551,246 | 2.6% | 416 | 16:32 | framework (ADAPT), transcript read |
| 3 | `HJN3husu1oM` | This New AI Agent Turns You Into a One-Person Company | 2026-05-24 | 497,640 | 1.5% | 168 | 16:03 | sponsored tool demo, transcript read |
| 4 | `ROmtgqTefAw` | Google Just Changed AI Forever, 7 FREE Tools No One Knows About Yet | 2025-11-12 | 478,544 | 3.8% | 795 | 13:12 | free tools list, transcript read |
| 5 | `QucgvbO5gsM` | Free AI Tools So Good They're Making Paid Versions Obsolete | 2026-07-22 | 440,555 | 3.8% | 574 | 18:34 | free tools list |
| 6 | `CpDM2ZXapBs` | The Top 5 Claude Co-work Features You Need to Know | 2026-03-05 | 409,655 | 1.6% | 246 | 12:46 | feature list |
| 7 | `-dwLbaCB-_I` | Google Antigravity 2.0 Tutorial: Full Masterclass Plus Antigravity vs Claude Code vs Codex | 2026-05-22 | 391,930 | 2.1% | 339 | 16:06 | tutorial |
| 8 | `_0xa6RVqTC8` | How to Use Claude Code in 2026: Full Course From Install to First Build (Step by Step) | 2026-01-18 | 381,284 | 1.6% | 209 | 14:23 | tutorial, transcript read |
| 9 | `O2HgyToWu9Q` | China Just Dropped A Free AI GLM 5.2 That Beats Claude (+16 AI Updates) | 2026-06-21 | 374,515 | 2.4% | 530 | 22:52 | weekly roundup |
| 10 | `L110osBj5Kk` | Google's FREE AI Just Replaced LinkedIn, Naukri, and Indeed (Complete Job Hunt Stack) | 2026-05-07 | 337,717 | 3.4% | 279 | 14:03 | career workflow, transcript read |
| 11 | `wj8sGbKhNtU` | Google Flow Free Tutorial: How To Make Cinematic AI Videos With No Editing Skills | 2026-05-26 | 337,338 | 2.8% | 332 | 27:00 | tutorial |
| 12 | `A-2WKQxhI_8` | Why You Should Switch to DeepSeek V4 Flash Right Now (+14 AI Updates) | 2026-08-09 | 328,454 | 2.2% | 339 | 21:47 | weekly roundup |
| 13 | `WJtnH0G8G1g` | How To Use NotebookLM Free: Complete Beginner Guide With 6 Live Use Case Demos | 2025-12-23 | 309,480 | 2.8% | 416 | 16:26 | tutorial |
| 14 | `btLZQzynfoA` | If I Had to Start Over in 2026, I'd Learn Only This (5-Level AI Roadmap) | 2026-02-17 | 250,428 | 3.4% | 315 | 16:28 | career roadmap, transcript read |

Shape of the fifty, computed: median length 16.8 minutes among the 46 under
an hour (range 8.8 to 31.6); 14 titles carry a "(+N AI Updates)" suffix and
one more is the "(20+ Free Updates)" variant, so the weekly roundup is 15 of
his 50 most popular long forms; 17 of 50 titles contain the word FREE; 41 of
50 titles name a company, model or person (Google, Claude, Anthropic, OpenAI,
ChatGPT, China, Elon, Sam Altman, Nvidia, Zuckerberg, Gemini, DeepSeek,
Codex, Higgsfield, Hermes, Kimi, Pomelli, NotebookLM, GLM). The two free
tools lists (`ROmtgqTefAw`, `QucgvbO5gsM`) carry the highest like rate of
anything over 300,000 views, 3.8% each; the roundup at rank 1 carries the
lowest, 0.8%, and got there on velocity (vidIQ views per hour 473 and
breakout score 5.81 at pull time, the highest of the fifty).

### 2b. Shorts, ranked by views

| Rank | ID | Title | Published | Views | Comments | Length | Note |
|---|---|---|---|---|---|---|---|
| 1 | `zF5DzNSKBI0` | You can Buy this HOUSE for just 85 Rupees | 2025-01-13 | 3,092,392 | 943 | 1:26 | canon EX-01 |
| 2 | `FZml4h4uXJU` | Free tools you don't know yet | 2025-10-02 | 2,391,754 | 152 | 1:09 | canon EX-02, teaching clip with loop |
| 3 | `KxAGWENTUpw` | Use any AI Model for FREE | 2025-09-20 | 1,365,790 | 230 | 0:44 | interview clip, transcript read |
| 4 | `tYnuf6-kXT8` | AI runs on GPUs. And whoever controls GPUs controls the future. | 2025-08-22 | 1,001,843 | 211 | 0:52 | transcript not pulled |
| 5 | `4uLBG43dL-g` | Google just launched Gemini 2.5 Flash Image and it's completely FREE | 2025-08-28 | 823,297 | 131 | 2:14 | |
| 8 | `01hUKhzYL5Q` | Secret AI Perks You Already Own (But Aren't Using) | 2026-01-07 | 594,488 | 138 | 0:41 | the same clip as rank 3, re-posted; transcript identical after its first four words; vidIQ breakout 15.65 |
| 10 | `nq8qpjroHm8` | Elon Musk vs. India: The Scary Truth About GPUs | 2025-12-19 | 526,927 | 160 | 0:36 | interview clip, transcript read; breakout 16.96 |
| 12 | `6UR-EXqeNW4` | Stop Paying For Claude Code! Run It FREE Now | 2026-06-27 | 447,742 | 5,806 | 0:44 | canon EX-03, comment gated |
| 28 | `2vKU3J29FJw` | One guy automated his entire job search with Claude Code | 2026-04-26 | 256,501 | 2,379 | 1:45 | gated on "job", transcript read |
| 29 | `fVIfAOJF9xc` | 3 Free AI tools that feel illegal to use | 2026-05-05 | 269,597 | 2,105 | 0:45 | gated on "link", transcript read |
| 37 | `WmeEd3A64AU` | This 1 Free Tool Replaced My Entire Video Production Team! | 2026-06-28 | 243,773 | 3,426 | 1:06 | gated on "printer", transcript read |

Shape of the fifty, computed: median length 74.5 seconds, range 33 to 153.
Six Shorts carry 1,000 comments or more (`6UR-EXqeNW4` 5,806, `WmeEd3A64AU`
3,426, `2vKU3J29FJw` 2,379, `fVIfAOJF9xc` 2,105, `fCEpoioDzQA` 1,580,
`jIPIy5XbYb0` 1,225); the other 44 run from 10 to 943 with a median of 78.
Four of the six are transcript-verified comment gates (this pull plus the
canon's PL-08); the last two are assumed gated from their titles and counts
and are marked unverified in section 10. Ten of the 50 Short titles contain
FREE. Every Short above 500,000 views was published in 2025 or the first week
of 2026; the best 2026 upload after the re-post is `FK9_03Mg9Gs` at 475,575.

## 3. What the top long forms do, in order

Positions are given by sequence in the transcript. No timestamps are claimed
because the transcripts carry none; the canon's walkthrough timings (PL-09,
PL-10) remain the only timed evidence in the estate.

### 3a. The weekly roundup (`YYAMwM-F30o`, `6OmqsFrRv4I`)

1. Cold open stacks four teased items, each with a named entity and a number
   ("a mysterious free AI model ... already beating Claude Fable 5", "12
   months of Gemini's paid version completely free", "one prediction with a
   real date attached", "Usain Bolt ... stopped being that"), then names the
   count: "those are just two of the 21 things".
2. A hands-on test is promised for the end ("at the end of the video, we try
   Ox Alpha ourselves"), which is the retention anchor for a 23 minute piece.
3. A permission-to-skip line: "if any section gets too technical, just jump
   to the next update you care about", with timestamps in the description.
4. Community link, then "let's get into the video".
5. Items in a fixed pattern: who shipped what, what it does narrated over
   screen, one line of implication ("So OpenAI isn't just building AI models
   anymore. It's now building the chips that run them too"). A comment
   question and a subscribe ask each land once in the middle.
6. The test itself, with numbers per step (22 slides, "only around 6% of its
   1 million token context window", "3 million free tokens", "7 cents per
   million input tokens"), and one limitation line ("The design and gameplay
   still needs some improvement").
7. Close: community, subscribe, next video, then "70% of the people watching
   this are not subscribed yet. So, YouTube will not show you the next AI
   updates video we drop", then subscribe again.

The linked video follows the same skeleton item for item (four teases, "five
of the 12 biggest AI updates", test at the end, skip line, timestamps,
community, close with the 70% line). Its description carries a disclosure
block worth copying in substance: "This video was created with the assistance
of AI tools. The script, voiceover, visuals and some editing elements were
generated or enhanced using AI, with human oversight applied to fact-check
and structure the content."

### 3b. The framework and career pieces (`KjNsnE_vsyc`, `btLZQzynfoA`, `L110osBj5Kk`)

1. Hook is a reframe with stakes: "You're not losing because you're
   underqualified. You're losing because the system was never designed to
   find the best person." Or a single word teased then named: "There's a
   five-letter word that's going to decide your paycheck for the next
   decade ... It's adapt."
2. A story or a viral artefact as proof the stakes are real (a friend who
   "couldn't understand half the words his own team was using"; a post with
   50 million views).
3. The whole framework is listed inside the open (five stages, five levels,
   four stages) with a promise of what the viewer will know at the end and an
   open loop held to the back ("the one stage where 94 out of every 100
   people quit forever").
4. Credibility beat, one breath: "I run three AI companies and train people
   across 150 plus countries." In `btLZQzynfoA`: Uber, three startups, "raised
   5 million from Sequoia", "I use AI 8 to 10 hours a day."
5. Each stage carries a plain-English definition, a tool list, or a
   vocabulary lesson with an analogy per term (system prompt is a new-hire
   briefing, RAG is your own documents, MCP is "a USB port for AI",
   fine-tuning is a cardiac surgeon).
6. Worked problems with numbered steps and measured results (a clinic voice
   agent: "1,000 plus calls handled per day, 70% fully resolved", "pick up the
   phone in 0.8 seconds"). The exact prompt is shown and the viewer is told to
   copy it.
7. Honest limitation beat: "AI is 80% the final output ... 20% will have to be
   human intervention"; Klarna replaced 700 support staff and "hired humans
   back".
8. Close: three rules or a recap, one share or comment ask, next video, the
   70% line (68% in `btLZQzynfoA`), and in two of the three a corporate
   training pitch and a "when we hit 500,000 subscribers I'll reveal" gate.

### 3c. The free tools list (`ROmtgqTefAw`)

Hook: "Stop paying for AI. I mean it." Six tools, each staged as a scenario
before the tool is named ("it's 10 p.m. Your exam is tomorrow"), then a live
prompt, then the result, then "think about what just happened". One fictional
coffee brand threads through all six so the outputs chain (image to video to
app to UI to campaign). A "pro tip 99% of people miss" beat, two limitation
lines ("Although this comes with a price tag", "not going to replace a
$50,000 design agency"), a recap of the stack, and one ask: links in the
description. No credibility beat, no community plug, no subscribe line. This
is the cleanest close in the sample and carries the highest like rate.

### 3d. The tutorial (`_0xa6RVqTC8`)

Hook is three concrete outcomes ("building 3D models in Blender just by
typing. Filing taxes automatically. Scraping Instagram"), then relatability
("I'm not technical at all. I avoided this for months"), then the promise as a
numbered list: "By the end of this video, you'll have one, a personal AI
assistant ... Two, your first AI agent ... Three, a full content army ... All
with just three commands." One analogy scaffold (Iron Man suit, Jarvis,
protocols, the Iron Legion) carries every concept. Objection handled up front
("Why should I even switch?"), price stated ("$20 per month", Cowork "$100 ...
only available on Mac"), permission prompts left on screen, files opened after
each step. Recap of the three commands, a comment ask for the next topic, and
"go build your AI army." No 70% line.

### 3e. The sponsored demo (`HJN3husu1oM`)

Test framing before any feature: "We're running two real experiments ... If
it can do that, it can literally change how someone starts a company." Test
one uses a brand he invested in, with the reason stated ("with a real company,
you can tell immediately when advice is generic"). He pushes the tool three
times, quotes its output, compares the cost to a named consultancy, discloses
the one manual step ("like 3 minutes of setup"), and shows a failure the tool
caught. The sponsorship is disclosed after the demo, in the last minute. That
placement is the anti-pattern in section 6.

## 4. What the top Shorts do

| Beat | `WmeEd3A64AU` (66s, 3,426 comments) | `2vKU3J29FJw` (105s, 2,379) | `fVIfAOJF9xc` (45s, 2,105) | `KxAGWENTUpw` (44s, 1,365,790 views) |
|---|---|---|---|---|
| Hook | "One Chinese developer replaced an entire video production team with one free tool" | "This guy just landed a head of AI role by vibe coding an AI system that evaluated 700 jobs" | "This is how you can use Claude, GPT and Gemini for free in one place" | Interviewer: "how much money do I need to spend per month to get started?" Answer: "Zero." |
| Proof | "I tested it by giving it just one word, health, and within minutes it dropped me a 60-second video", output played | "740 plus. That's how many jobs this system evaluated ... 7,000 people have already grabbed it in 2 days" | three tools, one line each on what they do | three concrete free routes (Ollama on "a 50,000 laptop", student ID for a year of Gemini, Perplexity model settings) |
| Compression | setup in four steps, "literally takes 10 seconds" | series marker: "crazy AI update of the day, and today is day 16" | none needed | pushback dialogue ("No." "How?") carries the pace |
| Ask | "Comment printer and I'll share the complete setup guide", follow, community | "send them this reel. Comment job and I will send you the link" | "Comment link and I'll send you all three links directly" | none; cut mid-sentence so it loops |

Two findings the 2026-08-11 canon did not have:

- **The re-post is live practice.** `KxAGWENTUpw` (2025-09-20, 1,365,790
  views) and `01hUKhzYL5Q` (2026-01-07, 594,488 views) are the same clip;
  their transcripts are identical from the fifth word on. The second run is
  his best 2026 Short by views and vidIQ's second highest breakout score in
  the fifty.
- **Interview clips out-view produced Shorts.** The three transcript-verified
  interview clips (`KxAGWENTUpw`, `01hUKhzYL5Q`, `nq8qpjroHm8`) sit at ranks
  3, 8 and 10 by views; every produced 2026 news Short sits below 480,000.
  Interview clips carry dialogue markers in the auto-captions, so the claim
  is checkable in the transcript, not inferred from the thumbnail.

## 5. Mechanics that hold across formats

Each row names the transcripts it was verified in. Three or more is the bar
for calling it a house mechanic; fewer is noted as a format trait.

| Mechanic | Verified in | Count of 8 long forms |
|---|---|---|
| Deliverable promised as a numbered list or a named count inside the open | `_0xa6RVqTC8`, `KjNsnE_vsyc`, `L110osBj5Kk`, `btLZQzynfoA`, `ROmtgqTefAw`, `YYAMwM-F30o` | 6 |
| Close carries the "70% of you are not subscribed, so YouTube will not show you the next one" line | `YYAMwM-F30o`, `KjNsnE_vsyc`, `HJN3husu1oM`, `L110osBj5Kk`, `6OmqsFrRv4I`, `btLZQzynfoA` (68%) | 6 |
| Community link inside the open, before the body | `YYAMwM-F30o`, `KjNsnE_vsyc`, `HJN3husu1oM`, `L110osBj5Kk`, `6OmqsFrRv4I` | 5 |
| Pointer to a named next video at the close | `YYAMwM-F30o`, `HJN3husu1oM`, `L110osBj5Kk`, `btLZQzynfoA`, `6OmqsFrRv4I` | 5 |
| Credibility beat after the hook ("I run three AI companies ...") | `KjNsnE_vsyc`, `HJN3husu1oM`, `L110osBj5Kk`, `btLZQzynfoA` | 4 |
| Honest limitation beat inside the body | `ROmtgqTefAw`, `L110osBj5Kk`, `YYAMwM-F30o`, `_0xa6RVqTC8`, `btLZQzynfoA` | 5 |
| Plain-English term plus one analogy | `KjNsnE_vsyc`, `btLZQzynfoA`, `_0xa6RVqTC8` | 3 |
| Comment question placed mid-piece, not only at the close | `YYAMwM-F30o`, `6OmqsFrRv4I`, `btLZQzynfoA` | 3 |
| Hands-on test held to the end and promised in the open | `YYAMwM-F30o`, `6OmqsFrRv4I` | 2 of 2 roundups |
| Permission-to-skip line with timestamps | `YYAMwM-F30o`, `6OmqsFrRv4I` | 2 of 2 roundups |
| Milestone gate ("when we hit 500,000 subscribers I'll reveal") | `btLZQzynfoA`, `L110osBj5Kk` | 2 |
| Corporate training pitch mid or late | `KjNsnE_vsyc`, `L110osBj5Kk` | 2 |

## 6. Anti-patterns Tee's gates hold out

Recorded as benchmark fact, not licensed. The precedence in the canon stands:
truth gates, then tee-voice, then this canon on mechanics.

| His practice | Where seen | Why it fails here |
|---|---|---|
| Sponsor disclosed after the demo | `HJN3husu1oM`, "This video was sponsored by them" in the last minute | Compliance is a no-exception path. Disclosure lands in the first 30 seconds and in the description. |
| Unsourced figures as hooks | "MIT published a study. 11.7% of every job", "56% more money", "94 out of every 100 people quit", "50 million views" (`KjNsnE_vsyc`, `btLZQzynfoA`) | fact-check owns every shown number; unverified is a hard veto (content-system section 5). None of these were verified here and they are not to be reused. |
| Content gated on a subscriber milestone | `btLZQzynfoA`, `L110osBj5Kk` | Withholding a deliverable to farm subscribes reads as bait under tee-voice; the checklist ships in the episode. |
| Stacked asks | `YYAMwM-F30o`: community twice, subscribe three times, comment once, next video once | Canon standard 4: one primary CTA, one soft rider. |
| Hype vocabulary and the exploding-head signature | Titles and Short captions throughout | tee-voice; the translation table in the canon's exemplar library still governs. |
| Rented presenter | The canon records an AI clone fronting long form (PL-13) | Voice and identity owned: Tee's own likeness and cloned voice only. His AI disclosure block is the one thing to copy from this row. |

## 7. Rulings filed for TQO and NCO

These twelve lines are what went into the Thread Log Decisions field, one
numbered ruling per line, which is the shape the Soul Layer Write-Back splits
on. They were derived by Claude from sections 2 to 6 on Tee's instruction to
use the top performers as the model; Tee's literal instruction is ruling 1,
the rest are adopted standards he can overrule with one word.

1. Benchmark refreshed on 2026-09-08: Vaibhav Sisinty's top performing videos
   and Shorts (evidence file
   `docs/devon/assets/TQO_PROOF_sisinty-benchmark-pull_v1_2026-09-08.json`)
   are the working exemplars for TQO and NCO episodes and Shorts, extending
   the 2026-08-11 AAA Flagship canon. tee-voice owns every published word and
   fact-check owns every shown number.
2. Long form cold open: stack three or four teased items, each carrying a
   named entity and a number, name the count, then state the Learning
   Objective as a numbered deliverable list, all inside the first 30 seconds.
   The benchmark lands its promise at roughly 40 to 90 seconds in; Tee's
   30-second rule stands and is the tighter one.
3. Credibility beat: one line after the hook and before the body, specific
   and checkable (rank, years served, what was built), never before the hook,
   never longer than 15 seconds.
4. TQO weekly roundup format: 10 to 20 items at 30 to 90 seconds each in the
   pattern who shipped what, what it does on screen, one line of implication;
   a permission-to-skip line with timestamps in the description; one
   hands-on test held to the end and promised in the open.
5. Every teaching episode carries at least one real-stakes test with the pass
   criteria stated before the test and an honest limitation beat after it;
   the numbers the test produces are annotated on screen.
6. Every new term in an episode gets a plain-English definition and one
   analogy.
7. Close formula: recap the checklist (the three to five steps every episode
   already carries), one primary ask, one pointer to the next episode. The
   benchmark's line that 70% of viewers are not subscribed is a mechanic,
   naming the cost of not subscribing; its wording belongs to tee-voice and
   the figure must be Tee's own, read from Studio, or it is not said.
8. Shorts carry one comment keyword, stated once after the proof beat, with
   the deliverable real and delivered within 24 hours. On the benchmark,
   gated Shorts run 1,225 to 5,806 comments against a median of 78 on the 44
   ungated Shorts in his top fifty.
9. Shorts supply: clip TQO and NCO long form conversations and interviews
   first, since the benchmark's top raw-view Shorts are interview clips, and
   re-post a proven clip after 90 days as a variant cell (verified on the
   benchmark: identical transcript, 594,488 views on the second run).
10. Titles: a named entity plus a number or FREE plus a consequence; the
    roundup carries a series suffix in the shape "(+N AI Updates)", which
    appears on 14 of his 50 most popular long forms.
11. Held out by Tee's gates: sponsor disclosure in the first 30 seconds and
    in the description, never at the end; no unsourced figure in a hook; no
    content gated on a subscriber milestone; no stacked asks; an AI-assist
    disclosure in every description in the substance of his disclaimer block;
    the presenter is Tee's own likeness and cloned voice, never a rented one.
12. Filing: this analysis lives in the repo doc and its evidence JSON; the
    rulings reach `tee-soul-layer` only through the Thread Log Write-Back;
    `devon-soul` and `devon-subconscious` are not written by this work.

## 8. What moved since the 2026-08-11 compile

| Item | 2026-08-11 (canon) | 2026-09-08 (this pull) |
|---|---|---|
| Subscribers | 800K (PL-01) | 835,000 |
| Videos | 703 | 728 |
| EX-01 `zF5DzNSKBI0` | 3,091,641 views | 3,092,392 |
| EX-02 `FZml4h4uXJU` | 2,374,400 views | 2,391,754 |
| EX-03 `6UR-EXqeNW4` | 370,713 views, 4,907 comments | 447,742 views, 5,806 comments |
| Gated comment set | 4,907 / 2,719 / 2,349 / 1,945 / 1,499 / 1,187 | 5,806 / 3,426 / 2,379 / 2,105 / 1,580 / 1,225, same six IDs |
| Biggest long form of the year | not recorded | `YYAMwM-F30o`, 692,849 views in nine days |
| Re-post practice | not recorded | `KxAGWENTUpw` re-posted as `01hUKhzYL5Q` |

Nothing here crosses the canon's refresh trigger (a tracked piece
five-times-outperforming an exemplar), so the canon bundle is extended by this
record rather than superseded. The canon lives in the account-level skill
store, which a web session cannot edit durably; merging sections 4 and 5 into
its exemplar library as 1.1.0 is a Tee-owned step named in section 10.

## 9. Where it is filed and what is proven

| Destination | State | Proof |
|---|---|---|
| This document and the evidence JSON | committed on the designated branch, draft PR | commit and PR in the receipt |
| Notion Thread Log page | created by this session with the twelve numbered Decisions, Area TQO, NCO, Systems | page URL in the receipt |
| `tee-soul-layer`, namespace `rulings` | written by workflow `edIJx7Q3FXTawg9J` on its next quarter-hour poll, twelve records with ids `<pageId>-d1` to `-d12` | the workflow's execution record (status, HTTP code, count) is read back in this session and stated in the receipt; the Pinecone console is the only proof a record exists, and only Tee can open it |
| `devon-soul`, `devon-subconscious` | untouched | by design: the committer is approval-gated and the subconscious takes only the learning lane |

Boundary note. The Write-Back's sticky note records the 2026-08-20 ruling
that only Tee-shaped knowledge enters the soul layer and world knowledge stays
in pgvector. The twelve rulings are Tee's content standard, so they qualify;
the view counts and transcript reads are world knowledge and stay in this
document, which is not embedded. If Tee wants the analysis itself recalled by
vector, that is a different index and a different lane, and this session did
not open either.

## 10. Unverified, open, and what the next session does

- Whether the twelve records exist in Pinecone is proven by the console, not
  by the workflow's 200. Tee opens the console once and counts.
- `fCEpoioDzQA` and `jIPIy5XbYb0` are assumed comment-gated from title and
  count; their transcripts were not pulled.
- `tYnuf6-kXT8` is assumed to be an interview clip from its title and its
  neighbours; not pulled.
- The vidIQ meter charged 70 credits for fifteen transcript calls listed at 5
  each; which call was not charged is unknown.
- The benchmark's own figures (11.7%, 56%, 94%, 50 million, 700 Klarna
  staff) were not checked and are recorded only as things he says.
- Retention curves, thumbnails as images, and Instagram were outside this
  pull.
- Canon merge: the account-level `aaa-flagship-canon` skill should take
  sections 4 and 5 and the section 8 delta as a 1.1.0, supersede-not-overwrite
  per its own keeping-current rule. Tee-owned, because the skill store is not
  writable from a web session.
- The devon-thread-log skill still lists eight Areas while the Notion
  schema now carries nine (ACX); already an open thread on the 2026-09-08
  sensor page and left there.

## 11. Provenance

| ID | Claim | Source | Confidence |
|---|---|---|---|
| R-01 | Linked video resolves to channel `UClXAalunTPaX1YV185DWUeg`, Vaibhav Sisinty | vidIQ `get_videos_by_ids("6OmqsFrRv4I")` 2026-09-08 | TOOL_VERIFIED |
| R-02 | Channel stats and 30-day growth in section 1 | vidIQ `channel_stats` 2026-09-08, saved in the evidence JSON under `channel` | TOOL_VERIFIED |
| R-03 | Every view, like, comment, duration, publish date, breakout and VPH figure in sections 2, 4 and 8 | vidIQ `channel_videos` long and short, popular, 2026-09-08, saved verbatim in the evidence JSON | TOOL_VERIFIED |
| R-04 | Every computed count (14 roundup suffixes, 17 and 10 FREE titles, 41 named-entity titles, medians, ranges, like rates, the six gated Shorts, the median of 78) | `scratchpad/sisinty_pull.py` run against the evidence JSON in this session | COMPUTED from R-03 |
| R-05 | Every quoted line in sections 3 and 4 | vidIQ `video_transcript`, language en, for the fifteen IDs named; quotes are verbatim auto-captions, which mishear names ("Vibhav", "Chad GPT", "Riplet") and were not corrected | TOOL_VERIFIED |
| R-06 | `KxAGWENTUpw` and `01hUKhzYL5Q` are the same clip | the two transcripts compared in this session: identical from the fifth word | TOOL_VERIFIED |
| R-07 | The AI disclosure block on the linked video | its description as returned by `get_videos_by_ids` | TOOL_VERIFIED |
| R-08 | The Write-Back's mechanics: polls the Thread Log every 15 minutes, reads only Decisions, splits on numbered lines, caps 6,000 characters, upserts to `tee-soul-layer` namespace `rulings` on credential `3XjKfxbS7zFWEa48` | n8n `get_workflow_details("edIJx7Q3FXTawg9J")` 2026-09-08, active version `a760bbc2` | TOOL_VERIFIED |
| R-09 | Recent Write-Back executions succeed in about four seconds at the quarter hour (6473 at 10:15:59Z, 6446, 6445 today) | n8n `search_workflow_executions` 2026-09-08 | TOOL_VERIFIED |
| R-10 | Canon figures in section 8's left column | `aaa-flagship-canon/provenance-ledger.md` rows PL-01, PL-06 | SOURCE_VERIFIED (read this session) |
| R-11 | Format labels, the mechanic table, and the rulings | Claude's reading of R-03 and R-05 | INFERRED, labelled |
