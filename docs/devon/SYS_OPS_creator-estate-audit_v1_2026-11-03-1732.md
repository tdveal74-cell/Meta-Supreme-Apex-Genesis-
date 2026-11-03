---
title: Creator estate audit, every tool scored on opens, published output and cost
type: SYS_OPS
version: 1
date: 2026-11-03
area: Systems
status: audit-complete-kill-list-awaits-ruling
repo: tdveal74-cell/Meta-Supreme-Apex-Genesis-
base: 22f249c
supersedes: none
---

# Creator estate audit

Tee asked on 2026-11-03: inventory every platform, studio, editor, template library, stock asset pack, AI tool and subscription tied to making videos and YouTube Shorts; score each on how often it is opened, whether it produces published output, and what it costs a month; rank them; say which to kill and which to keep; name the most efficient path from idea to a published Short or long-form video. Be blunt.

Everything below was read from the live systems on 2026-11-03 between 16:45Z and 17:35Z, by seventeen read-only readers over the platform connectors, the n8n VPS, Gmail, Notion and this repository, plus the vendor pricing pages. Nothing was generated, posted, rendered or bought. Where a number could not be read it says unverified. The window for "90 days" is 2026-08-05 to 2026-11-03. The receipts window is 95 days on the Stripe and wallet rails and 120 days on the vendor-by-vendor sweep.

## The answer

Four videos were published in the last ninety days, every one uploaded by hand: "The Middle Is the Target" (2026-10-29) and "Automate One Task. Measure the Whole Cost." (2026-11-02) long-form, "n8n Exposes 40 Ideas Before I Ask AI for More" (2026-11-02) as a Short, all on The Quiet Operator, and "Three Leadership Failures Every NCO Should Audit" on NCO Forge, recorded published between 2026-10-28 and 2026-11-03. Before 2026-10-29 the last upload was 2026-07-20. The Quiet Operator channel has 12 public videos, 4 subscribers and 14 lifetime views. No source in the estate records a dollar of revenue.

Three paid tools made those four videos: HeyGen rendered the presenter, ChatCut cut and captioned the masters, and the clone voice came from ElevenLabs or HeyGen's own voice. Everything else in the estate either produced assets that never reached a published video, produced nothing, or is dead and still trying to bill a card that keeps declining.

The automation that was built to publish has published nothing. TQO FINAL V5 has 304 nodes and 12 triggers, its retained 68 executions since 2026-10-21 ran 0.3 to 3.1 seconds each and reached no model, no voice, no render and no upload, its three published rows carry the status "published by hand upload", and 67 packaged Idea rows sit waiting for a human pick that has not happened since row 46 locked on 2026-10-05.

The estate is being pruned by a declining Venmo debit card, not by a plan. In the window, Runway Pro, Canva Pro, vidIQ Boost, Blotato, Zapier, n8n Cloud, Artlist, Leonardo, Notion Business and Vercel Pro all lapsed on failed payments, HeyGen refused two renders for lack of credits, Google One was suspended for a day, Railway paused the DEVON services for unpaid invoice, and Airtable is one declined charge from auto-downgrade. The decisions below make that pruning deliberate.

## How each tool was scored

Opens is the newest activity the platform itself exposes plus how many distinct days carried activity in the window. 5 is active in the last 7 days and on 10 or more days in 90. 4 is active in the last 30 days across several days. 3 is several days in 90 and none in the last 30. 2 is one or two days in 90. 1 is connected with no activity in 90 days. 0 is empty, expired or dead.

Output is whether the tool's work reached a video published on YouTube in the window. 5 is in a published video. 4 is a finished master or clip in the chain of a published or watch-ready video. 3 is assets used in work in progress with nothing published. 2 is tests and probes only. 1 is nothing produced. 0 is empty.

Cost is the monthly figure a receipt or the vendor's own billing read gives. Where only a list price is known it is marked list. Where neither is known it says unverified. A tool that bills nothing today but will bill the moment the card clears is marked attempting.

## The inventory, ranked

Rank is by Output, then Opens, then cost. The verdict column is the recommendation; the ruling is Tee's.

| Rank | Tool | Role | Opens | Output | Cost a month | Verdict |
|---|---|---|---|---|---|---|
| 1 | HeyGen | presenter face, digital twin, Avatar V | 5 | 5 | $29 Creator, receipt 2026-08-26, renewals unverified; API reads plan "pro" | keep, the bottleneck |
| 2 | ChatCut | cut, captions, master export | 5 | 5 | $25 list, Plus 100 monthly, active to 2026-11-08, charge unverified | keep, stop generating in it |
| 3 | YouTube | 4 channels: TQO, NCO Forge, TSWS, Ascension Caudex | 4 | 5 | $0 | keep |
| 4 | Google Drive on Google One AI Pro 5 TB | every master, every DEVON file, Gemini access | 5 | 5 | $19.99 paid 2026-11-01 | keep |
| 5 | ElevenLabs | owned professional voice clone LLhnFOCTr3y3wrH59DtJ | 4 | 3 | $22 Creator from 2026-11-30, $11 paid 2026-10-31 | keep |
| 6 | Hostinger VPS pair, srv1936193 and srv1936199 | n8n engine, render worker, EditForge, ComfyUI, Postiz, Rakazo | 5 | 2 | $24.49 plus $13.99 per Venmo, cadence unverified | keep, but see the V5 finding |
| 7 | Runpod | TSWS LTX 2.3 takes on an A100, presenter pipeline L40S | 4 | 3 | $37.59 in October; idle storage now bills about $1.63 a day, about $49 a month, with nothing running | keep the account, kill the idle storage |
| 8 | OpenArt | owned b-roll libraries, 61 clips | 3 | 3 | $14 paid 2026-09-01; $59.92 declined 2026-10-30 and 2026-11-01, attempting; 0 credits on Pro | kill |
| 9 | Runway | TSWS plates, foley beds, identity stills | 3 | 3 | $0 now; Free plan, 202 credits, video models gated; $131 spent 2026-07-31 to 2026-08-28; Pro renewal failed nine times | dead, do not revive |
| 10 | WaveSpeed | TSWS SH020 stills, one minimax clip | 2 | 3 | $0.28, pay as you go, $0.17 balance | keep, costs nothing idle |
| 11 | Higgsfield | TSWS trailer segments, TQO character sheets | 2 | 2 | Starter $19 list; 70 subscription credits granted 2026-10-12, no receipt found; 0.38 credits left | kill |
| 12 | Google Media Runner and Gemini API | Veo 3.1 lane dead on 404, one image run; V5's script writer since 2026-11-02 | 2 | 2 | inside Google One AI Pro; API spend unverified | keep Gemini, stop expecting Veo |
| 13 | EditForge, self-hosted | studio OS: 42 jobs, 1 completed, 27 unreviewed for 37 days, 0 edits | 3 | 2 | inside the VPS bill | park |
| 14 | Hugging Face MuseTalk avatar lane | free ZeroGPU presenter lip sync, 2 private Spaces | 2 | 2 | $0 | park |
| 15 | HyperFrames local | free HTML render, 17 jobs, 14 unreviewed | 3 | 2 | $0 | park |
| 16 | TQO FINAL V5 automated render and publish half | Pexels b-roll, render adapter, YouTube upload nodes | 5 | 1 | inside the VPS bill | retire the render half |
| 17 | Postiz, self-hosted | 4 YouTube channels connected, 0 posts ever | 1 | 1 | $0 | park |
| 18 | Canva | 27 stills, 4 edits in September, no video | 2 | 1 | $0; Pro ended 2026-08-07 on failed payment | leave on Free |
| 19 | vidIQ | knows 1 of 4 channels; 60 of 150 credits | 1 | 1 | $0; Boost cancelled 2026-08-23 | leave on Free |
| 20 | Adobe Creative Cloud | one TSWS opener upload on 2026-08-05, zero Firefly | 1 | 1 | unverified, no receipt | disconnect |
| 21 | Speechify | V5 fallback voice canon says must never stand in for him | 1 | 1 | $139 a year paid 2026-07-28, half refunded, auto-renew on | kill the renewal, remove the node |
| 22 | Descript | zero projects ever | 0 | 0 | $0, no receipt | disconnect |
| 23 | OpusClip AI Producer | zero projects ever | 0 | 0 | $0 | disconnect |
| 24 | Blotato | subscription expired, never wired to n8n | 0 | 0 | $0; $97 declined twice in July | kill, remove connector |
| 25 | HyperFrames hosted, Figma, Miro, tldraw, Linear, Lovable, Replit, Make, Supabase, Cloudflare | empty or idle, none in the video path | 0 to 1 | 0 | $0 | disconnect |
| 26 | MoneyPrinterTurbo on srv1936199 | ruled out 2026-10-31, cannot carry a face | 1 | 1 | disk only | remove from the box |
| 27 | Airtable | 29 nodes in 8 active workflows still write to a base ruled retired 2026-10-21 | 2 | 1 | $24 Team, declined 2026-09-26 and 2026-10-26, downgrades to Free 2026-11-26 | let it lapse, migrate the nodes |

Below the content tools sit the AI and infrastructure subscriptions that make them run. Anthropic Max 20x at $200 a month was paid 2026-07-27 and 2026-08-27 with no later receipt in the mailbox, and it is the engine every workflow, script and this audit were built with. ChatGPT Plus at $20 was paid 2026-09-01 and three $100 charges were declined on 2026-10-30 and 2026-11-02. xAI took $16 on 2026-08-02 and $20 of prepaid API tokens on 2026-10-31. Railway bills $5 plus usage, $11.19 last cycle, for the DEVON api, presence and scheduler, and paused them on 2026-10-31 until the invoice cleared the same day. Vercel's Pro licence stopped billing on 2026-10-14 after fourteen failed $20 charges and the account now runs on the free tier, which is why 66 of the 83 deployments read on 2026-11-01 to 2026-11-03 were cancelled. Google Workspace for tqohq.online debits $6.50 on 2026-11-05.

What bills today if nothing changes, counting only lines that are active or attempting and tied to video: HeyGen $29, ChatCut $25, ElevenLabs $22, OpenArt $59.92, Higgsfield $19, Google One $19.99, Workspace $6.50, Hostinger about $38, Runpod storage about $49, Airtable $24. That is about $292 a month, with Speechify's $139 a year on top, before the $240 AI layer and Railway. Against four hand-uploaded videos and 14 lifetime views.

## What the readers found, tool by tool

HeyGen. 39 videos in the library, 34 since 2026-08-05 across 9 render days, 14 of them in the 72 hours to 2026-11-02. The ones that read as finished output are the two TQO46 parts of 2026-10-26 (204.8 s and 372.9 s), "Leadership Audit Insights" of 2026-10-27 (475.2 s, the NCO 30 presenter source), and "TSWS S01E01 THE MASK v10" of 2026-09-04. The digital twin group holds 11 looks, not the 8 the record says; consent accepted. Plan reads "pro" with 2 premium credits left and a reset on 2026-11-26, so the pool is spent. Two 2026-10-26 renders failed with "Insufficient credit. This operation requires 'api' credits". 8 private avatar groups and 13 private voices, 8 of them Tee clones by name. The Creator plan is 600 credits a month. HeyGen's help centre lists Avatar V at 48 credits a minute and Avatar IV photo looks at 16; the twin test render measured 17 credits for 19.5 seconds, about 52 a minute, and part 2 of the TQO46 render cost 299 credits for 372.9 seconds, about 48. On the Avatar V twin that Tee ruled the TQO face, the plan buys about 12 minutes of presenter a month: one eight minute episode and three or four Shorts, not four episodes.

ChatCut. Plus Plan 100 credits monthly, active, 0 credits since 2026-10-25, period ends 2026-11-08. 19 projects, 36 completed exports, 331 billing rows between 2026-10-07 and 2026-10-28. The TQO 46 project carries two 1080p masters completed 2026-10-27 and consumed zero credits; the NCO 30 v4 master rendered 2026-10-28. 30.59 of the 105 credits ever granted went to seven Seedance generations on the TSWS rough cut, which has no master. Captions and masters are free in it; generation is what spends.

ElevenLabs. The professional clone LLhnFOCTr3y3wrH59DtJ "T Veal" is real and in the same workspace as the flows. A second voice named "T Veal" (NSXFHN6nIewAIPGaUMq7) is an instant clone, so any pick by name is ambiguous; V5 picks by id. Six flows, all touched between 2026-10-31 and 2026-11-02, two of them named "TQO - Presenter Narration Master" and "NCO Forge - Presenter Narration Master". Creator plan $22 a month, first month $11, paid 2026-10-31 after one decline. One conversational agent from June, never used.

YouTube. Four channels are connected in Postiz: @thequietoperator-l3i, @ncoforge, @theshadowweshare and @ascensioncaudex. vidIQ sees only the first. The n8n content tables record three published URLs, all written on 2026-11-03 from a card, none by the pipeline. The channel holds 12 public videos against 2 recorded for it, so the pipeline does not know what is on its own channel.

The automation. TQO FINAL V5 is active with 304 nodes. Its 68 retained executions since 2026-10-21 are 66 success and 2 error; the 64 scheduled runs each lasted 0.3 to 3.1 seconds; execution 5431, the 2026-11-03 writer slot, exited at "Package: Plan Batch" having called no model. Execution 5220, the one manual run, generated 37 seconds of ElevenLabs audio and died at "Presenter: Attach Clips" with "Nothing rendered" because no presenter clip was registered. On 2026-11-02 at 06:23Z every writer, packaging, QC and doctor node in V5 and in seven DEVON lanes was switched from Cerebras to Gemini (gemini-3.8-flash on credential "Gemini Chat Compatibility - Existing Google Key"); no record in this repository, Notion or Drive names who ruled it, and the standing record still says Cerebras. The render path is a self-hosted adapter at 172.16.2.1:8081, not json2video. The Pexels b-roll it would render was rejected by Tee on sight on 2026-09-16. The Speechify fallback node is wired off the ElevenLabs error output while the Voice Lab sticky note says a stopgap voice must never stand in for him. Fifteen nodes still read and write Airtable base app28z7XnKzjfTXwc, ruled retired on 2026-10-21, and 29 Airtable nodes exist across eight active workflows.

OpenArt. Pro plan, 0 credits. 61 items between 2026-09-23 and 2026-10-10, 59 of them video clips, in brand-named projects for all four shows; nothing for 24 days. No field shows any clip reached a published video. $14 charged 2026-09-01; $59.92 declined on 2026-10-30 and 2026-11-01, so the plan renews the day the card has funds.

Runpod. Three pods, all EXITED. October cost $37.59, $27.52 of it GPU, 65 percent on one pod that no longer exists. Since 2026-11-01 the bill is storage only: a stopped A100 pod's 140 GB volume at about $0.93 a day and three network volumes totalling 285 GB at about $0.90 a day, two of which no pod mounts. The LTX takes the pods made were copied to Drive by Tee on 2026-10-31 and are unwatched.

Runway. Free plan, 202 purchased credits, every video model gated. 46 assets between 2026-08-31 and 2026-10-20, all TSWS inputs. $131 spent between 2026-07-31 and 2026-08-28; the $35 Pro renewal failed nine times from 2026-08-31.

Higgsfield. "basic" per the API, 0.38 credits. 12 jobs between 2026-10-12 and 2026-10-22: six Kling 3.0 trailer segments for TSWS, two failed and two refunded, two realm stills, three TQO presenter character sheets. A 70 credit subscription grant on 2026-10-12 means a plan is billing somewhere; no receipt or decline for it exists in Gmail, so where it bills is unverified. The vendor page today has no Basic tier; the cheapest is Starter at $19.

WaveSpeed. Six predictions on one afternoon, 2026-10-30, $0.83 total in 90 days. Retired for TSWS motion by the 2026-10-31 ruling.

EditForge. 42 jobs between 2026-09-20 and 2026-10-29, one completed, 27 waiting for human review including 14 TQO b-roll proofs from one session on 2026-09-27, 10 failed, 0 edit commands ever. Its ElevenLabs credential holds the key id in place of the key, so its voice lane has never made a sound. Its Veo provider 404s.

Hugging Face. Free account, two private Spaces last touched 2026-10-21, one of them the MuseTalk presenter lane. No render is readable.

Descript, OpusClip, HyperFrames hosted, Miro, Linear, Replit, Cloudflare: empty. Lovable: three projects, idle since 2026-07-14, free plan. Make: no licence, paused, zero scenarios. Figma: starter tier, view seat. Canva: Pro lapsed 2026-08-07, 27 stills, no brand kit. Adobe: one 557 MB TSWS opener uploaded 2026-08-05, nothing since, zero Firefly generations. Blotato: every read refused with "Subscription expired".

Dead by non-payment in the window, no action beyond confirming no retry: Runway Pro, Canva Pro, vidIQ Boost ($29 failed four times, cancelled 2026-08-23), Blotato ($97 failed twice), Zapier paid (cancelled 2026-08-04), n8n Cloud Starter ($24 failed from 2026-08-29; Tee ruled the cloud instance deactivated 2026-09-24), Notion Business ($24 failing from 2026-07-14, current state unverified), Artlist ($69.99 failing from 2026-07-26; the TSWS Auren and Vespera clone voices were built on that account per the 2026-08-05 Thread Log), Leonardo ($60 failed eight times), Digital Maker AI ($49 failed ten times), Manus ($40), Syllaby, Pictory, Magai ($20), Web3Forms, Zoom, DigitalOcean ($0, droplet deleted 2026-08-08).

Apple. The App Store took $37.98 on 2026-08-30 and $6.99 on 2026-09-01, then declined $30.00, $6.99, $20.99, $39.95, $19.99 and $6.99 between 2026-09-07 and 2026-09-11. No itemised Apple receipt reaches Gmail, so which apps those are is unverified. One of them may be a video app.

n8n credentials wired into nothing active, counted across 63 of the 68 active workflows (five refuse MCP reads): Anthropic (three credentials), Cerebras, Groq, OpenAI, json2video, mailerlite, both HeyGen header credentials, and four unnamed ElevenLabs duplicates from July. Credentials wired and live: Gemini (20 nodes in 8 workflows), ElevenLabs, Pexels, Jev, Postiz, Gumroad, Hostinger Reach, Pinecone, Firecrawl, Google Drive, YouTube (two), Airtable (29 nodes), SMTP, the render worker and the ComfyUI worker.

## Kill, keep, park

Kill now, each one a cancellation or a deletion Tee makes or authorises:

1. OpenArt Pro. Cancel before the $59.92 retry succeeds. Nothing it made reached a video, the face-on ruling of 2026-10-31 retires b-roll for TQO and NCO Forge, and TSWS is parked until 2026-11-15.
2. Higgsfield. Cancel the plan. 0.38 credits, nothing since 2026-10-22, two of six Kling jobs failed.
3. Runpod idle storage. Confirm the nine LTX files in the Drive folder TSWS_S01E01_LTX23_TAKES_2026-10-31 are the takes, then delete the two unmounted network volumes (video-render-workspace-ca2, tsws-nv-100gb) and the stopped A100 pod with its 140 GB volume. Saves about $40 of the $49 a month. Keep the account and the render-l40s volume until the presenter pipeline ruling below.
4. Speechify. Turn off auto-renew on the $139 annual plan and remove the "Speechify TTS (Fallback)" node from V5. The canon already forbids the voice.
5. Airtable Team. Do not fix the card. Let the 2026-11-26 downgrade happen and move or disable the 29 nodes before it does, because a Free base caps records and the writes will start failing quietly.
6. Blotato. Remove the connector. It is expired, never wired, and the Thread Log left restore-or-kill open since 2026-09-01.
7. MoneyPrinterTurbo. Remove /opt/mpt-shorts from srv1936199. Ruled out 2026-10-31.
8. Dead connectors: Descript, OpusClip AI Producer, HyperFrames hosted, Figma, Miro, tldraw, Linear, Lovable, Replit, Make, Supabase, Cloudflare, Adobe. None is in the video path; each is a surface the gate and the Jev router have to reason about.
9. n8n credentials wired to nothing: Anthropic x3, Cerebras, Groq, OpenAI, json2video, mailerlite, HeyGen x2, the four unnamed xi-api-key duplicates. Delete after a read of the five MCP-blocked workflows confirms none of them uses one.

Keep, with the condition that makes it earn its line:

1. HeyGen Creator, $29. Every render goes to a card with its cost first. The pool is 600 credits and Avatar V on the twin costs about 48 to 52 a minute, so a 60 second Short at about 50 credits and an eight minute episode at about 400 are the two units to plan in. Four episodes a month on Avatar V needs Pro at $49 for 1,000 credits, or the Avatar IV photo look at 16 a minute, which Tee judged a lesser likeness on 2026-11-01.
2. ChatCut Plus 100, $25. Captions and masters are free; stop spending its credits on Seedance generation.
3. ElevenLabs Creator, $22. 121k credits is about 121 minutes of speech a month, roughly fifteen long-form scripts. Re-voice the twin test in the professional clone before anything with the generated voice ships.
4. Google One AI Pro, $19.99. It is the Drive that holds every master and the Gemini access the writer now uses.
5. Hostinger VPS pair, about $38. The n8n engine and the render worker live there. The condition is the V5 ruling below.
6. WaveSpeed, Pexels, vidIQ Free, Canva Free, Hugging Face Free, Gemini: cost nothing idle, leave them.

Park, no spend, no attention until a lane needs them: EditForge, the HF MuseTalk lane, HyperFrames local, Postiz, OpenMontage, the render worker's Short compositor, the TSWS n8n post block (zero runs in the retained window, scheduler disabled), the five SH070 drafts, Rakazo's 32 bots.

Three things are rulings, not cleanups, and they go on the card:

1. The V5 render and publish half. It has never published a video, its b-roll look was rejected on sight, and it carries the Speechify and Airtable wiring above. Recommendation: retire that half and keep V5 as the idea, packaging and script ledger only, or retire V5 outright and write scripts in a session against the canon, which is how the four published videos were actually made.
2. The presenter pipeline on Runpod (MuseTalk and Chatterbox, ruled 2026-10-15 "own the whole stack") against the HeyGen twin (ruled the face 2026-10-31 and the only lane that has rendered). Recommendation: HeyGen is the face until the owned pipeline has a render Tee has watched; stop the L40S volume billing meanwhile.
3. The Gemini swap of 2026-11-02. Either it was ruled and the record is missing, or a workflow changed the writer of every lane without a ruling. Recommendation: record it, then test one script through it before the next card asks Tee to pick a package.

## The path from idea to published video

The only chain that has produced a published video in the estate is this one, and it ran twice in the last week.

1. Script. Write it in a Claude session against the TQO canon in n8n/tqo-v5/build_script_prompt.js, 1,200 to 2,000 words, Learning Objective in the first 30 seconds, the 3 to 5 step checklist, the one question close. V5's writer has not produced a script since the Gemini swap; the quality90 reviewer scored row 46 at 91 on 2026-10-28 and that is the gate that matters.
2. Voice. ElevenLabs text to speech on voice LLhnFOCTr3y3wrH59DtJ only. A 56 word take cost 268 credits, so a 1,500 word script is about 7,200 credits, about 6 percent of the Creator month.
3. Face. HeyGen Avatar V on look c89667ba7c474e2694bf18ffc035c604 with reference_look_id 56da7b2dced54d1082eecd2a16b54335, the filmed twin, audio uploaded as a WAV, through the connector on plan credits, one card per render with the credit cost and the balance. Eight minutes is about 400 credits at the measured 48 to 52 a minute.
4. Cut. ChatCut: import the HeyGen render with the clean caption band (the Drive copy of NCO 30 carried HeyGen's burned captions and double-captioned two masters), Inter captions, lower thirds, master export at 1080p. Zero credits.
5. Publish. Hand upload to the channel with the C4 line "Presented with a synthetic voice and synthetic likeness of Terrance Veal, used with his consent." in the first three lines of the description and YouTube's altered or synthetic content label, after Tee watches it end to end. Write the URL into tqo_content or nco_content by hand or by card.

For a Short the same chain runs on the portrait twin look (720 by 1280) reading a 45 to 75 second native script, about 40 to 60 HeyGen credits, cut in ChatCut at 9:16 with the proof screen recording in the top half and his face in the bottom half per the 2026-10-31 canon. No portrait Short has rendered end to end yet; the render worker's presenter_composite job exists for the split and is untested on a real Short. The option that spends no HeyGen credits, clipping the long-form master, was recommended on 2026-10-31 and Tee chose HeyGen; it stays the fallback for the three weeks the pool is empty.

Cost per long-form episode on this path is about $1.30 of ElevenLabs credit and about two thirds of the HeyGen Creator month, with ChatCut and YouTube at zero. One Avatar V episode plus a handful of Shorts a month is what $29 buys; the second episode in a month is a $49 Pro plan or a photo look.

## Unverified, and who can settle it

- Whether HeyGen has billed since 2026-08-26 and which plan it is on. The API says "pro", the receipt says Creator at $29, the credit pool behaves like Creator. Tee's HeyGen billing page.
- The current Anthropic plan. Last receipt 2026-08-27. Tee's Anthropic billing page.
- Which App Store subscriptions the $37.98 and the six declines were. Settings, Subscriptions, on the phone.
- Where Higgsfield bills. No receipt or decline in Gmail.
- Whether the ChatCut $25 is charged monthly or the $21 annual rate. Its billing page.
- Which voice narrated the two published TQO videos. The ChatCut project says "R2_H voice"; nothing names the provider.
- The five n8n workflows that refuse MCP reads (TswsMicroRender26, TswsMicroQueue26, TswsMicroAssets26, TswsMicroWorker26, TSWS_Continuity_V6_Gate_20261021) and whether they use any credential marked wired to nothing.
- Who moved the writers to Gemini on 2026-11-02T06:23Z.
- The n8n execution store holds nothing before 2026-10-20, so every pipeline count above is a count since then, not since 2026-08-05.

## Receipts read

| date | vendor | amount | what the receipt says |
|---|---|---|---|
| 2026-07-27 | Anthropic | $181.13 | Claude Max 20x, Jul 27 to Aug 27, less Pro credit |
| 2026-07-28 | Speechify | $139.00 | Premium annual to 2027-06-30, then $69.50 refunded the same day |
| 2026-07-28 | n8n Cloud | $24.00 | Starter, Paddle; every renewal from 2026-08-29 failed |
| 2026-07-31 | Runway | $35.00 | Pro, Jul 31 to Aug 31 |
| 2026-07-31 | Runway | $30.00 | 3,000 credits in two receipts |
| 2026-07-31 to 2026-08-02 | Anthropic | $114.00 | six prepaid extra usage top-ups |
| 2026-08-02 | xAI | $16.00 | no plan named |
| 2026-08-14 | Google One | $1.99 | AI Plus 400 GB intro |
| 2026-08-21 | Railway | $5.00 | Hobby, Aug 21 to Sep 21 |
| 2026-08-26 | Airtable | $24.00 | Team, Quiet Operator OS workspace |
| 2026-08-26 | HeyGen | $29.00 | Creator, Aug 26 to Sep 26 |
| 2026-08-26 | Runway | $50.00 | 5,000 credits |
| 2026-08-27 | Anthropic | $200.00 | Max 20x, Aug 27 to Sep 27 |
| 2026-08-27 | Hostinger | $27.98 | two $13.99 receipts seven minutes apart |
| 2026-08-28 | Runway | $16.00 | 2,000 credits, 20 percent off |
| 2026-08-28 to 2026-09-10 | Vercel | $5.00 | ten $0.50 charges |
| 2026-08-30 | Apple | $37.98 | item unknown |
| 2026-09-01 | Apple | $6.99 | item unknown |
| 2026-09-01 | OpenAI | $20.00 | ChatGPT Plus |
| 2026-09-01 | OpenArt | $14.00 | plan not named |
| 2026-09-28 | Hostinger | $24.49 | |
| 2026-10-05 | Railway | $3.76 | $18.76 usage less $15 balance |
| 2026-10-31 | Railway | $11.19 | Sep 21 to Oct 21 usage plus Hobby |
| 2026-10-31 | ElevenLabs | $11.00 | Creator, first month half price |
| 2026-10-31 | xAI | $20.00 | prepaid API tokens |
| 2026-11-01 | Google One | $19.99 | AI Pro 5 TB, after a suspension the same day |
| 2026-11-01 | fal.ai | $3.39 | invoice issued, due Nov 7, payment unverified |
| 2026-11-05 | Google Workspace | $6.50 | upcoming bank debit |

Runpod's own billing API, not Gmail: September $0.90, October $37.59, November 1 to 3 $4.89. WaveSpeed's: $0.83 in the window. Vercel's: a Pro licence billed daily until 2026-10-14 and nothing after.

## Gauntlet verdict

Filled in after the verifiers and the critic ran; see the section at the end of this document.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_creator-estate-audit_v1_2026-11-03-1732.md
DATE: 2026-11-03
DECISIONS: None taken by the session. The kill list, the V5 render half, the presenter pipeline against the HeyGen twin, and the unrecorded Gemini swap are handed to Tee on a card.
FINDINGS: Four videos published in 90 days, all by hand, from HeyGen, ChatCut and ElevenLabs; the 304 node automation has published nothing and 67 packaged ideas wait for a pick; about $292 a month bills or attempts to bill for video tools against 14 lifetime views; OpenArt is attempting a $59.92 renewal with nothing published from it; Runpod bills about $49 a month for storage with nothing running; Speechify's $139 annual auto-renews for a voice canon forbids; the writers moved to Gemini on 2026-11-02 with no ruling on record; the debit card, not a decision, has been doing the pruning.
OPEN: Tee's rulings on the card; the nine unverified items above; the five MCP-blocked workflows; the HeyGen plan and the Anthropic plan status.
STATUS: Audit complete, read only, nothing changed on any platform.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
