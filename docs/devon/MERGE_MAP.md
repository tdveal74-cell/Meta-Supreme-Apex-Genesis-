# Merge map: where every part of DEVON came from

Compiled 2026-08-22. Two sources merged: the DEVON second brain on Google Drive,
and the Jarvis assistant at `github.com/Vannu07/jarvis` (commit `21b9d63`).

This file exists so that a later reader can check the copy against the original.
Reference by Drive id, never by name: ids survive rename and move.

## Provenance

| Module here | Compiled from | Drive id | Version read |
|---|---|---|---|
| `services/devon/areas.py` | `AREAS.md` | `1UrmxHSkVQjdHdiF2rRUo2lOCIbx1EFjg` | ruled 2026-08-20 |
| `services/devon/naming.py` | `SYS_SPEC_naming-convention` | `1r5-7JCqMDEHcYWj97AxZuWuzb7wdSYCL` | v4 |
| `services/devon/precedence.py` | `SYS_SPEC_precedence-doctrine` | `1EaFyPPAXIX5j75oJ06tvvUuq4Qd73jB4` | v2 |
| `services/devon/filing.py` | `SYS_SPEC_filing-laws-for-llms` | `1YxrdXHqlT5kkdzWey5qO_21KbVDQd9ID` | v3 |
| `services/devon/receipts.py` | Cross-Platform Capture Protocol | `1jVAQ6KwhFXoONg3cLYFDfi0zhLMjWAfi` | v1 |
| `services/devon/receipts.py` | `SYS_SPEC_llm-standing-instructions` | `1A88Nkf5BpCZysmHP7XYMXBtaEh4Eqj9M` | v3 |
| `services/devon/vault.py` | `SYS_INDEX_master-directory` | `1sSnB7tdXhf7ECAknNgE_tINrmJ1maUg_` | v6 |
| `services/devon/vault.py` | `SYS_SPEC_context-pill` | `1bySPMORLCMlBkNv9YuK2uvuWTiJL6_qS` | v16 |
| `services/devon/vault.py` | `SYS_SPEC_webhook-paths` | `1wKkFGVBXaFZqWvLjSiBrxXWLk8Lwkd8c` | v1 |
| `services/devon/flagship.py` | `SYS_SPEC_flagship-bar` | `1s4l6r9ucGWrtEENqlBqDmFtpl4_85z_m` | v01 |
| `services/devon/persona.py` | Devon Persona | `1iFhjVvb_IrsEC0Xfjda_tzIxTCCTIv-f` | 2026-07-27 |
| `services/devon/persona.py` | `SYS_SPEC_voice-standard` | `1MpGAI5OGVkw7_EZpLpBba1nJ-YQWwmOt` | v2 |
| `services/devon/commands.py` | Devon Command Language | `1aqct4_UZqlI11IDdRpPS4kbpiaHxoqph` | 2026-07-27 |
| `services/devon/commands.py` | upstream `backend/nlp/command_parser.py` | Jarvis `21b9d63` | device intents |
| `services/devon/approval.py` | n8n Approval Queue `syRVj0G47mA1b0Xn` | via context pill v16 B11 | verified 2026-08-22 |
| `services/intelligence/providers/cerebras_provider.py` | context pill v16 B11 | `1bySPMORLCMlBkNv9YuK2uvuWTiJL6_qS` | verified 2026-08-22 |

Every module also declares its own source in a `SOURCE` or `SOURCES` constant,
checked by `test_devon_integrity.py::test_doctrine_modules_declare_their_provenance`.

## Contradictions found in the vault, and how each was resolved

The vault contains documents that disagree. Precedence doctrine v2 governs:
closest to today wins for versions of the same artifact, and a contradiction is
flagged rather than silently resolved. These were version drift, not
contradictions, and were resolved by date. Recorded here because a corrected
claim with no history is how a fork starts.

**1. How many Areas: seven, eight or nine.**

- `Area Vocabulary.md` (`1840Xotl0xDlssWjrz4XwQiU65TlyR1UX`, 2026-07-27) says
  seven and predates NCO Forge.
- `CAPTURE-QUICKCARD.md` (2026-08-05) and `CLAUDE-COWORK-INSTRUCTIONS.md` say
  eight, "never a ninth".
- `AREAS.md` (`1UrmxHSkVQjdHdiF2rRUo2lOCIbx1EFjg`, updated 2026-08-20),
  naming convention v4, master directory v6 and context pill v16 all say nine.

Resolved: **nine**. The four newest documents agree, ACX was ruled the ninth on
2026-08-20 on the batch-4 ruling card, and the older files went stale the day
that ruling landed. `Area Vocabulary.md` and the two "never a ninth" documents
should be marked stale in the vault. That is a Drive side write and was not made
from here.

**2. Notion select values name retired Areas.**

`Notion Schema Reference.md` records `Business` and `Personal` as select options
on Projects and Goals. Both are retired: TQO replaced Business, Systems replaced
Personal. Whether Notion itself was reconfigured is recorded nowhere. Carried as
a known gap rather than assumed fixed.

**3. `Area Taxonomy Mismatch.md` proposes the opposite of what was decided.**

It still reads status "Open" and proposes making Notion canonical and renaming
the vault's TQO folder to Business. `Area Vocabulary.md` decided the reverse. A
reader hitting the mismatch note first implements the wrong plan. Flagged, not
resolved from here: it needs a Drive side retirement per Filing Law 6.

**4. Three databases or four.**

The Operating Manual and Notion Memory Layer both say three. The Conversations
Thread Log is a fourth under the same parent page and is referenced by Area
Vocabulary. Resolved: **four**. The two older documents were never updated.

**5. Where receipts land, and how often the buffer drains.**

The quick card says Claude writes to Notion directly and the drain happens on
request. The Cowork instructions say Airtable is a buffer that drains daily. Two
cadences for one buffer. Left as an open question for Tee: it is a real
operational choice, not version drift, so precedence doctrine says a human
rules.

**6. The webhook collision.**

Context pill A7 says two workflows claim `/devon-capture` and Tee ruled it
correct as is. Part C1 of the same document records that the collision was
already cleared earlier that day and Capture Hook was retired. C1 is the later
measurement. `vault.py` records the current state: `/devon-capture` belongs to
receipts `pPIt2cELH2RVZktS`, `/devon-inbox` to the capture lane
`5s6CwWWelffqszQe`, and Capture Hook `Cbd24ptTPWch3aZO` is retired.

## Known stale and owed, carried forward

Recorded so the next reader does not rediscover them.

- Context pill v11 (`1r7nsvx_axtE7KcRGFxIS18V4u4jexEzH`) still carries a retired
  name and returns permission denied to the connector. Remove by hand.
- The `/devon-capture` receipts endpoint is still unauthenticated. Deliberate,
  because the posters are ChatGPT and Grok and most chat platforms cannot attach
  a custom header. Needs a ruling.
- QA checklists and the continuity SOP were deleted in the name purge and are
  not recoverable from any surviving file. They must be rewritten from scratch.
  **Do not let a model reconstruct them from memory and present them as
  restored.**
- The Airtable base is under `PUBLIC_API_BILLING_LIMIT_EXCEEDED`, a monthly
  workspace quota. Blocked on money, not on work.
- `Mirror Reads` (`1ZwE5USNTFHN5Tj2sT97kLOAAzttl7Nj4`) held zero files when
  listed on 2026-08-22. Anything expecting mirror output is getting none.

## What was not written back to Drive

Nothing. This session made no write to the vault.

Canon has one writer at a time, ruled 2026-08-22 after five documents forked in
two days. A thread must confirm it holds the write before touching
`_Devon Core`, and this thread did not confirm that. Filing Law 2 also requires
listing a folder and reading the newest sibling before writing any new version,
and the safe way to honour both from here was to read and to build, not to
write.

The Drive side writes this merge implies are listed above under contradictions 1
and 3. They are Tee's to make or to delegate to a thread that holds the write.

## Addendum, 2026-08-22, later the same day

Two owed items moved. Recorded here rather than edited into the sections
above, because a corrected claim with no history is how a fork starts.

- **The `/devon-capture` endpoint is no longer unauthenticated.** Tee ruled;
  per-poster capture tokens went live in n8n workflow `pPIt2cELH2RVZktS`
  (Check Token and Apply Token Identity nodes, version
  `43bbbe10-8ede-4bb0-979f-b25061453c1f`). A valid token files and stamps
  the platform, a wrong token is refused, and an untokened post files
  flagged UNAUTHENTICATED while legacy grace holds. Grace ends when Tee
  flips `LEGACY_GRACE` to false after adding each poster's token to its
  connector. Verified by shown runs: 17 local checks on the stored node
  code, and n8n executions 3134 (valid token, success), 3135 (untokened,
  success under grace), 3136 (wrong token, refused). Tokens live only in
  n8n, never in Drive.
- **The QA checklist and continuity SOP are rewritten**, as new v1
  artifacts that say so in their headers:
  `SYS_OPS_qa-checklist_v1_2026-08-22.md` and
  `SYS_OPS_continuity_v1_2026-08-22.md`, both in `docs/devon/`. Derived
  from live sources only; neither reconstructs the lost text. Filing them
  to Drive remains Tee's write.

## Addendum, 2026-08-22, evening

The remaining owed items closed today, recorded with receipts:

- **The two SOPs are filed to Drive.** Tee granted the write in so many
  words ("file the SOPs on my drive"); the filing followed the laws:
  destination confirmed and listed (Laws 1 and 2, no SYS_OPS siblings in
  `_Devon Core`), then written, then read back byte-exact (Law 3, sizes
  5720 and 5732 matching the repo files, head and tail verified against a
  raw download). Drive ids:
  `SYS_OPS_qa-checklist_v1_2026-08-22.md` = `1JzPZqVB_DUuTghMlx13cNYFndO1Uv-bG`,
  `SYS_OPS_continuity_v1_2026-08-22.md` = `1VYy7vldP-je4VHsFjJ6NBHyPC6ZprBUu`.
- **The stale Area documents are deleted.** Tee did the retirements by
  hand and said so. Contradictions 1 and 3 above are closed.
- **Context pill v11 is gone.** Id `1r7nsvx_axtE7KcRGFxIS18V4u4jexEzH` now
  returns not-found (previously permission denied). Nothing to remove.
- **Airtable quota resets 2026-08-25.** The owed session receipt posts
  then, through the token-gated webhook, with the Claude token. A check is
  scheduled. `QUEUE_airtable_pending_2026-08.md`
  (`1HDGzS8TNJBxVrmwmwRK3q3uuU1arHACY`) gets reviewed at the same time.

Still open after today: Tee updates the four poster connectors with their
tokens and flips `LEGACY_GRACE`; the Notion select values still name
retired Areas (contradiction 2); Mirror Reads still holds zero files.
