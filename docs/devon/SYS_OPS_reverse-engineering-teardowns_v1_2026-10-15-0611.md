# REA on the VPS, the outward allow rule, and two teardowns

Written 2026-10-15. It covers one session: getting REA (morluto/rea) running on srv1936199, letting Desktop Commander run there without a prompt, stopping before a capture of enhancor.ai, and the business teardowns of Enhancor and Apple Creator Studio.

## Rulings

Tee ruled on inline cards on 2026-10-15:
- Desktop Commander may run every tool on the VPS without a prompt, including `start_process`, which runs as root. He chose this over a read-only subset, with that cost written on the option. It shipped as PR #344, merged as main 0272086.
- The enhancor.ai teardown uses public sources only. The full browser capture he first picked was stopped before it ran, because Enhancor's terms forbid it (see Findings). That fell under his rule that compliance items have no exception path.
- Run the 30-day test of the Enhancor-derived service.
- File these decisions to DEVON. This doc is that filing.
- Keep Chromium on the VPS for future REA browser work.

He also set the founder constraints the teardowns use:
- under $500 at risk, none of it borrowed
- more than 20 hours a week
- a $50/hour floor
- fewer than 1,000 people he can reach today

## Findings

REA is installed on srv1936199 and works.
- `rea --version` reads 6.4.0.
- `rea doctor --client claude_code` reads `aligned` for the Claude Code registration in `/root/.claude.json`, with the skill at version 37 and 170 tools. Codex is not registered.
- `rea analyze /usr/bin/ls` returned a Hopper overview: 5 segments, 412 procedures, 249 strings.
- `rea search` found the `ls` sort-mode strings `none` at 0x1b205 and `extension` at 0x1b290, labelled observed. `rea xrefs` found no code references to either. My guess is that the strings sit in a pointer table; that is unverified.

Two install hazards on that host:
- The interactive `rea setup` picker did not register a toggle from the phone terminal. `rea setup --client claude_code --yes` did.
- Ubuntu's restart checker, needrestart, opened a dialog nothing could answer during a Playwright install. Killing that one process was safe, because it runs after dpkg has finished.

Chromium 131 from Playwright is at `/root/.cache/ms-playwright`, with a copy in `/opt/rea-chromium`. Ubuntu sets `kernel.apparmor_restrict_unprivileged_userns = 1`, so Chromium's own sandbox cannot start there. It runs with `--no-sandbox` as the unprivileged `nobody` user, never as root.

Enhancor's Terms of Service were rendered in Chromium on the VPS: last updated May 20th, 2026, Create Without Limits Technologies Inc. They forbid:
- attempting to derive the source code
- scraping
- accessing the service to build a competitive product
- data mining
- automated use with scripts without authorization

A REA browser capture would have hit several of these. Only the homepage, the terms pages and one terms render were ever loaded from enhancor.ai.

Teardown verdicts, from the `startup-reverse-engineering` skill. The full evidence and sources are in the session's scratchpad file `teardowns_2026-10-15.md`.

Enhancor: BUILD WITH CONDITIONS, as a service. The idea borrowed is selling the fix for a visible flaw in AI output. The offer is a done-for-you presenter video in the client's own consented face and voice, for veteran-owned businesses and military transition coaches, at $300 a video. Tee's own advantage carries much of the case.
- Tool cost of $8 to $48 a video is unverified, so $300 clears $50/hour only at 5 hours or less a video. Real hours are not measured.
- $10K a month is 34 videos at $300, about 31 hours a week at 4 hours a video.
- The founder's revenue claim, "$0 to $350K/month in 6 months", is his own and unverified.

Apple Creator Studio: DON'T BUILD. What made it work is Apple's own distribution and apps, and neither carries over. These were read directly from Apple's pages on 2026-10-15:
- $12.99 a month or $129 a year with a one-month free trial
- sharing with up to five other family members
- a monthly allowance of at least 50 generated images
- generative features running on OpenAI and Google Cloud

Its pages never mention avatar video or voice cloning. That gap makes its subscribers a possible place to find customers for the Enhancor-derived service.

The Genjutsu workflow sends work to Seedance through Enhancor's API. `ENHANCOR_API_KEY` is still unset by choice. The presenter service should not run through Enhancor's API, so the competitive product clause never bears on it.

## The 30-day test

It runs to 2026-11-15, with tools capped at $150:
1. Time one full TQO video first, at no cost.
2. Write one consent form and check YouTube's current label rule for synthetic content before the first paid delivery.
3. Send 40 direct LinkedIn asks.
4. Close three paid pilots at $250, each delivered in 4 hours or less.

Stop on any of these:
- fewer than three paid pilots by the date
- a timed video takes more than 4 hours
- the consent or disclosure check turns up a rule the offer cannot meet

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_reverse-engineering-teardowns_v1_2026-10-15-0611.md
DATE: 2026-10-15
DECISIONS: Tee ruled on cards on 2026-10-15: Desktop Commander runs every VPS tool without a prompt, merged as PR #344 at 0272086. The enhancor.ai teardown uses public sources only, after Enhancor's terms stopped a browser capture. Run the 30-day test of the done-for-you presenter video service. File this record. Keep Chromium on the VPS.
FINDINGS: REA 6.4.0 works on srv1936199, with the Claude Code registration aligned and Hopper analysing /usr/bin/ls. Enhancor's terms forbid deriving source, scraping, competitive building, data mining and unauthorised automation. Enhancor: BUILD WITH CONDITIONS as a service. Apple Creator Studio: DON'T BUILD, with pricing read from apple.com.
OPEN: Time one TQO video; write the consent form and check the YouTube label rule; build the 40-ask list; confirm in a fresh session that the Desktop Commander allow rule skips the prompt; read the Codex review that was still running when PR #344 merged; every UNVERIFIED figure in the teardown.
STATUS: REA is live on the VPS, the allow rule is merged, and the 30-day test is approved and not started.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
