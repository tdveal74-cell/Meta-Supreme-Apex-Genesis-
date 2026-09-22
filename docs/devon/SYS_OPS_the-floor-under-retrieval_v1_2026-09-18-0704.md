# The floor under retrieval, and the read-back that caught my own stale sentence

Closes the arc that began as a grill for retrieval labels and ended as a code
change. PR #269 merged as `ab2cc64` on Tee's explicit authorization, 2026-09-18
at 06:53Z. Five commits, five files, 558 insertions and 20 deletions.

## What the grill was for, and what it found instead

`scripts/measure_retrieval.py` refuses to run without labelled questions: a
question Tee would really ask, paired with the note that should answer it. Only
he can supply that pairing. He ruled on a card to be grilled for the labels
rather than have them written cold, because a list written from memory skews
toward questions whose answers share their vocabulary, which is the exact bias
that made the synthetic twelve document corpus worthless for the embedding
funding decision.

Answer 1 gave three query shapes. One of them worked with no vendor at all. The
other two failed, and chasing why found that `hybrid_retrieve` could not return
zero candidates for any non empty query.

The grill therefore produced one labelled answer and one defect, and the defect
outranked the six remaining questions. The label set is still six short.

## The defect, measured before and after

Four signals fused at k=60. Two of them never read the query:

- `rarity` read `metadata->>'rarity'`, which nothing in this repository has ever
  written, so it scored 0.0 on every row. `rank_map_from_scores` breaks equal
  scores on `doc_id`, a UUID, so a signal carrying weight 0.35 was ordering
  documents by their identifier. Proven rather than argued: six seeded rows,
  every rarity value 0.0, and the resulting order identical to a plain sort of
  the ids.
- `age` is a real signal, but `_rarity_and_age_pool` was
  `ORDER BY created_at DESC LIMIT 30` and took no query at all.

Between them those two supplied a full ranked pool for everything, so nothing
could ever come back empty. That made `synthesize_with_cross_encoder`'s own
documented rule, "No candidates, explicit refusal, never fabricate", unreachable,
because its only refusal path is an empty pool.

Run end to end through the real pipeline on a real corpus:

```
before   "how do I recover from burnout"    cleared=True   3 citations
before   "xylophone quagmire zeppelin"      cleared=True   3 citations, the same 3

after    "how do I recover from burnout"    cleared=True   3 citations
after    "xylophone quagmire zeppelin"      cleared=False  0 citations
                                            refusal_reason='no_candidates'
```

## What shipped

Three parts, each on a ruling Tee delegated to the session's recommendation:

- `rarity` deleted. It was dead at every call site.
  `_rarity_and_age_pool` is now `_recent_pool`, with the column dropped from its
  SELECT.
- `age` demoted to a tie-breaker. It scores only rows a query reading signal has
  already introduced, through an `introduced` set, so it can reorder an answer
  and can no longer invent one.
- `dense_is_trusted` defaults to False, set by the caller from
  `dense_signal_is_trusted(provider.name)` and backed by
  `TRUSTED_FOR_RETRIEVAL = ("openai",)`. This reuses the allowlist posture Tee
  already ruled on 2026-09-16 for `TRUSTED_FOR_COVERAGE` rather than inventing a
  second trust mechanism. It fails closed on anything unrecognised, including
  None and the empty string, so a mock provider's distances cannot introduce a
  candidate.

`docs/devon/CAPTURE_retrieval-labels_2026-09-17.md` is the first `CAPTURE_` file
in the estate. It was committed empty, before the first question, per the
`devon-grill` rule that a session which dies halfway must leave what it got on
disk rather than buffer a transcript that vanishes with the container.

Answer 1 is recorded as query shape and not as the incident. The verbatim
account named a vendor tied to an account and a financial record, and the
harness refused the write. That refusal was correct and is recorded as a
finding rather than worked around.

## Validation before the push

```
ruff check .                                clean
standalone import, no PYTHONPATH            clean
test_retrieval_floor.py                     14 passed
full api suite                              3018 passed
```

Three mutations of the load bearing guards, each reverted with a byte identical
restore:

```
remove the introduced-set floor        killed by 4 tests
trust dense by default                 killed by 3 tests
allowlist inverted to a denylist       killed by 3 tests
```

Two tests in this arc passed under mutation on their first writing and were
rewritten. One rode a tie-break rather than the operator it claimed to test; the
other searched a whole SQL file where the orphan fallback statement genuinely
carries the content only expression. Neither would have been caught by reading
them.

## The deployment read-back, 07:04Z on ab2cc64

```
Railway api        LIVE   044e8ac8 SUCCESS 07:03:12Z on ab2cc64
                          held WAITING from 06:53:31Z until CI completed at
                          07:00:08Z, then built; /api/v1/health 200 healthy
Railway presence   LIVE   823a0c99 SUCCESS 06:54:17Z on ab2cc64
                          /health eleven keys, speech cartesia, ears mock,
                          protocols [1,2], livekit_configured true with
                          audio_over_websocket false, breaker closed, zero
                          breaches
Railway scheduler  LIVE   e31aac27 SUCCESS 06:55:21Z on ab2cc64
meta-supreme-apex-genesis-web  LIVE  dpl_F89tEYKtgLgFSMkG7j8BV8CssYua READY
                          target production on 53b3f48, 2026-09-17 22:47Z;
                          the ab2cc64 production build CANCELED, skip verified
devon-soul         LIVE   dpl_EqbcffbHERX1URRkjY4o4suApUrZ READY
                          target production on d8d7144, 2026-09-17 22:56Z;
                          the ab2cc64 production build CANCELED, skip verified
```

`livekit_configured: true` with `audio_over_websocket: false` is the working
state rather than the silent one, because `apps/presence/livekit_publisher.py`
is present at `ab2cc64`, checked with `git ls-tree` rather than assumed.

Both Vercel skips were verified by hand from the commit each surface actually
serves, using each project's own `ignoreCommand` read out of its own
`vercel.json`:

```
git diff --stat 53b3f48 ab2cc64 -- :/apps/web :/packages/ui \
  :/pnpm-lock.yaml :/pnpm-workspace.yaml      empty, exit 0
git diff --stat d8d7144 ab2cc64 -- :/deploy/soul    empty, exit 0
```

Nothing is owed to either surface. Vercel reads `plan: hobby` and the account
carries nine projects, two of them from this repository.

## The finding this read-back produced, which is mine

Every check-in this session carried the sentence "web is on f0f1e7e4 and owes
the push to talk build; devon-soul is on 94de84be, both ship on the next merge
to main." It was true when first written and false from 2026-09-17 at 22:48:27Z,
when `53b3f48` built the web surface READY and `d8d7144` built devon-soul
forty nine minutes before this session's first check-in. PR #271's own merge
commit, which landed at 01:52Z, says so in plain text, and the sentence was
carried forward through three check-ins after that anyway, because it was copied
from the previous check-in rather than re-read.

This is the third stale sentence about deployment state recorded in two days,
and the first one whose source was a check-in prompt rather than a status doc.
A carried forward note is a claim with no timestamp attached, and it survives
exactly as long as nobody checks it. The remedy applied here is the one the
`deploy-readback` skill already prescribes and this arc did not follow until the
end: read the surface immediately before repeating any claim about it.

`_rarity_and_age_pool` deserves the same reading. It was renamed rather than
left, because a name asserting a column the SELECT no longer carries is the same
defect in miniature.

## Open after this merge

The label set is six questions short and the embedding vendor decision still has
no measurement on Tee's real corpus behind it. No measurement in this arc says
the floor improves an answer he would keep; it says retrieval can decline, which
it could not before.

`hybrid_retrieve` still requires `query_vec` even when `dense_is_trusted` is
False, so every query pays for an embedding call whose result is discarded. Found
and noted, not built.

`ELEVENLABS_API_KEY` is absent from the Railway presence service, so `ears` reads
mock. Tee ruled `PRESENCE_EARS` to elevenlabs, and `build_hearing` runs inside
`create_app`, so setting the flag before the key exists stops the service booting
rather than degrading it. The flag stays on mock until he says the key is on.

The Cerebras outage was live at the last reading in PR #272, ten consecutive
scheduled refusals across twenty four hours. This arc did not touch it.

## DEVON RECEIPT

```
AREA: Systems
TYPE: SYS_OPS
ARTIFACT: SYS_OPS_the-floor-under-retrieval_v1_2026-09-18-0704
DATE: 2026-09-18
DECISIONS: Tee ruled merge on 2026-09-18 and delegated both design calls to the session's recommendation, a floor built as tie-breakers only and rarity deleted outright rather than repaired; the dense gate reuses his 2026-09-16 TRUSTED_FOR_COVERAGE allowlist rather than a second trust mechanism or a score threshold; answer 1 is captured as query shape after the harness refused the verbatim account, and the refusal is recorded rather than worked around; the capture was committed empty before the first question per the devon-grill rule
FINDINGS: hybrid_retrieve could not refuse any non empty query, because two of its four signals never read the query and between them always supplied a pool, which made synthesize_with_cross_encoder's own no-candidates refusal unreachable; rarity was dead at every call site and was ranking documents by UUID at weight 0.35 through the tie-break in rank_map_from_scores; two tests in this arc passed under mutation on first writing and were rewritten, one riding a tie-break and one searching a SQL file where the orphan fallback carries the content only expression; a title-in-fts recommendation was made on one unseeded run and withdrawn when twelve seeded trials read +0.000; the check-in prompt carried a stale production sentence through three firings after PR #271 had already recorded it false
OPEN: the label set is six questions short and the embedding vendor decision has no corpus measurement; no measurement says the floor improves an answer Tee would keep; hybrid_retrieve still requires query_vec when dense is untrusted so every query pays for a discarded embedding call; ELEVENLABS_API_KEY is absent so presence ears reads mock and PRESENCE_EARS stays on mock until Tee says the key is on; the Cerebras outage was live at the last reading
STATUS: merged as ab2cc64 at 06:53Z, CI run 920 green on all five jobs at 07:00:10Z; before the push ruff clean, standalone import clean with no PYTHONPATH, test_retrieval_floor.py 14 passed, full api suite 3018 passed, three mutations each killed by three or four tests with byte identical restores; all five production surfaces read back at 07:04Z, api 044e8ac8 SUCCESS and healthy, presence 823a0c99 SUCCESS with eleven keys, scheduler-cron e31aac27 SUCCESS, both Vercel surfaces current with their skips on ab2cc64 verified by hand from the commit each one serves; the designated branch is restarted on ab2cc64
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
```
