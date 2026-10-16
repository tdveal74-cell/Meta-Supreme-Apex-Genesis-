# Support articles: how one gets from a question to a citable source

Each article here is a file pair: `<id>.md` holds the reader-facing body and nothing else, and `<id>.json` holds the title, the sha256 of the body, and Tee's content decision. A change to the approved title or body is a new article with a new id (`-v2`), never an edit. `scripts/support_article_import.py` refuses a body whose hash no longer matches.

## Who does what

Tee approves content and records the production approval himself. Claude picks the next question from real material, writes the brief, reviews the draft against its sources, runs the import check and keeps the status record. The DEVON Support Editor in Rakazo researches and drafts. It never approves its own work and never posts a reply. The Support API stores the article and refuses a reply that cites anything not approved.

Three states stay separate on every article: the content decision (Tee), the stored state (drafted, approved or rejected in the production API, read back), and publication. An approved article gives Support a source. It does not approve any reply.

## What Claude hands the worker

One audience question, tied to a real source: an approved episode script, a transcript with timestamps, or actual viewer comments. The brand or show. The source files the worker can open, as Drive ids it has been given access to. The facts and policy limits to keep. The proposed id and version. The acceptance checks below. A brief with no real source is not sent.

## What the worker returns

1. The article as Markdown, body only.
2. Create JSON with only `article_id`, `title` and `body`.
3. A claim table: each claim, its source, the exact location, the date checked.
4. Unverified facts and at most one focused question.
5. Validation output from `services.company.knowledge.create_article`.
6. The proposed version, content decision `pending`, stored state `not checked`.

## What Claude checks before Tee sees it

Every claim has a source that covers its scope. No invented price, refund term, response time, feature or step. No dash or look-alike, no password, key, payment detail or private link. The article answers one question and says what it does not cover. Fix routine problems without sending Tee between agents.

## Import

Tee runs `python3 scripts/support_article_import.py <id>` to read, `--create` to store the draft, then `--approve` to record his decision. The sign-in is his, so the owner and the recorded decider are his. The output ends with a VERIFIED line carrying the body hash, status and decider. Keep that line as the approval evidence.
