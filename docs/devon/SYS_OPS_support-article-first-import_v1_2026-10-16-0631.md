# Support: the first approved article, staged for import, and the critic results

Newer than `SYS_OPS_company-layer-rulings-and-readback_v1_2026-10-14-2334.md` on the Support knowledge base, the critic work and the open list. That doc stays as written.

## What is true now, claim by claim

Content approved: yes. Tee approved `how-we-answer-video-questions-v1`, titled "How we answer questions about our videos", on 2026-10-16. The record is his handoff file `CLAUDE_Support_Article_Operations_Handoff.md` in his Drive root, which carries the text.

Stored in production: no. I did not create it. The article routes act as the signed-in account, so the owner and the recorded decider are whoever signs in, and I do not hold Tee's sign-in. Registering a new account would have put the article under the wrong owner. The production API serves no docs page (`/docs` and `/openapi.json` return 404 on api-production-5644), and the web app has no Support articles panel.

Approved in the production API: no, for the same reason. Nothing in production was written, so no read of the live inventory exists. I did not list it either, since that also needs the sign-in.

Wording preserved: the repo copy `support_articles/how-we-answer-video-questions-v1.md` is the fenced block of the handoff, 2,062 characters, ASCII only, sha256 `73ed2b8c966e88c084f4c0a712635f747119f71a4f14080b1b62112b94434276`. The repo's own `create_article` accepts it. The second Drive file, `SUPPORT_001_..._APPROVED.md`, reads the same on my read; I did not byte-compare it.

## What was built

`scripts/support_article_import.py` signs in as the account, lists its articles, and then does only what the flag says. With no flag it writes nothing. `--create` stores a draft when the id is absent, reuses identical text and stops on different text. `--approve` records the decision only after the id is typed back, then reads the article again and exits 1 unless the status reads approved. The password is read hidden and neither it nor the token is printed. It refuses a base URL that is not https. The article and its hash live in `support_articles/`, and the README there records the workflow: roles, the worker's return package, versioning by a new id.

Run it from any machine with Python 3:

    python3 scripts/support_article_import.py how-we-answer-video-questions-v1
    python3 scripts/support_article_import.py how-we-answer-video-questions-v1 --create
    python3 scripts/support_article_import.py how-we-answer-video-questions-v1 --approve

The last line of the approve run starts with VERIFIED and carries the body hash, status and decider. That line is the approval evidence to keep.

Tests: 18 in `test_support_article_import.py`, no network. Five mutations were each caught: skip the hash check, skip the create flag, skip the typed id, skip the conflict check, skip the readback.

## The Rakazo worker

Specified only. The Drive file `RAKAZO_DEVON_Support_Article_Bot_Prompt.md` is a prompt. The bot roster in Rakazo, read on 2026-10-16, has 28 bots and none named DEVON Support Editor. Tee's request to Chief to build it is the preview on that thread, and Chief's last run reads failed. I could read Chief's thread only to message 279 of 321, because the tool output cuts off there, so what Chief did after that is unread. Nothing has been connected or tested.

## The next three articles

None can be named from evidence yet. Drive holds only draft TQO scripts (`TQO_12_Video_Scripts_v06_DRAFT.md` and the S01E01 drafts), none marked approved, and the repo and Drive hold no real viewer comments. Demand is not invented. The smallest source set that unblocks the worker is one approved episode script, or ten to twenty real viewer comments with their video and timestamp.

## Critic results

Two isolated critics ran in their own worktrees, on their own databases. Each finding was reproduced before it was acted on.

Support knowledge base (PR #345) and the import script, on 8e5557b: PASS-WITH-CONDITIONS. No path stored a reply citing a missing, drafted, rejected or other-owner article. Eleven malformed ids were refused. No article was decided twice. Migration 028 upgraded, downgraded and re-upgraded on a fresh database.
- The import script printed VERIFIED and exited 0 after a failed approval. Real, fixed in 5a91d88, test added.
- A dead host gave a traceback and a plain http base would have sent the password in clear. Fixed in 5a91d88.
- The SQL `AND status = 'drafted'` guard in `decide_article` is covered by no test, because the test client does not interleave. Open. The Python guard is covered and approved is terminal, so no wrong state is reachable.
- The database does not enforce that a cited article is approved, only that it exists for the owner. The rule lives in `insert_comment_draft`. Not reachable through the API.
- The automated-actor check never matches, because the decider is an email. Any automated process holding a valid owner token could approve. The same design as the Marketing and Support draft queues. Open, a design question for Tee.

PRs #338, #341 and #342, on c549a38: #338 PASS, #341 and #342 PASS-WITH-CONDITIONS.
- #341: a surrogate sent as raw UTF-8 bytes or in a UTF-16 body returned 500 on login and register. Real, and it made "fixed app-wide" too strong. Fixed in PR #357 with tests, eight of which fail without the fix. Bodies over 8 MiB are still unchecked.
- #342: a charge with `captured=false` counted as revenue. Fixed in PR #357. A 200 that is not a JSON object raised on the scoreboard. Fixed in PR #357.
- #338: other dash-like characters outside the ruled list still pass (U+2053, U+1400, U+2E5D, U+207B, U+208B). That list is the ruling. Open if Tee wants it wider.

The critic reports are the agents' words, and PR #357 carries only the findings I reproduced.

## Other items, rechecked on 2026-10-16

STRIPE_READ_KEY is not among the Railway api service's variable names. Names only; values are redacted by the tool.

Newest READY Vercel production deploys: web dpl_ANkydEhRbxQcEh94pP7eiTjaMmDk on f559094 (PR #351), soul dpl_BPGT3USBMxz9DiTeTdKXQ17gd9ud on f559094. The old pointers ac9bb36 and e8a72b7 are history. This supersedes the "unverified" in the 2026-10-14 doc.

TQO Leads: a Gmail search on that label returned no threads. An empty label and a failed search read the same, so this is unverified.

## Not closed

The wider arc stays open. Open: the article is not in production; the worker is not built; the SQL guard test gap and the automated-actor design; PR #357 awaiting CI; Stripe key creation and the Railway variable; a real lead for the label; Blotato and vidIQ. Nothing is filed to DEVON, because the `devon-capture` door needs an `x-devon-key` that this environment does not hold.

## DEVON RECEIPT

AREA: Systems
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_support-article-first-import_v1_2026-10-16-0631.md
DATE: 2026-10-16
DECISIONS: Tee approved the content of how-we-answer-video-questions-v1 on 2026-10-16 in his handoff file. No production approval was recorded by anyone. A new account was not registered to get around the sign-in.
FINDINGS: The article passes the repo rules, sha256 73ed2b8c966e88c084f4c0a712635f747119f71a4f14080b1b62112b94434276. An import script was built and tested, 18 tests, five mutations caught. Two critics found a script defect, fixed, and three product gaps in PRs 341 and 342, reproduced and fixed in PR 357. Newest READY Vercel production deploys read back on f559094.
OPEN: Production create and approval need Tee's sign-in. Rakazo worker not built and Chief's last run failed. No evidence for the next three articles. SQL drafted guard untested. Automated-actor check design. Stripe key and Railway variable. TQO Leads label unverified. Not filed to DEVON.
STATUS: Content approved. Not stored in production. Not approved in the production API. Arc open.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
