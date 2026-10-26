# Overruling a soul layer record

Ruled by Tee on 2026-10-25 on a card, "Overrule it", and then "Re-write it as
overruled".

A ruling dated 2026-09-08, "TQO and NCO content rule, adopted 2026-09-08 from
the Sisinty benchmark refresh (Claude derived, Tee to overrule)", said a long
form cold open stacks three or four teased items, each carrying a named entity
and a number. It lives in the `tee-soul-layer` Pinecone index, namespace
`rulings`, as record `3d568ff5-0db6-81ac-b2e4-f817cc57a833-d2`, written by the
`DEVON Soul Layer Write-Back` workflow from a thread log page. The recall served
it to NCO 31 alone in the score-only run of 2026-10-25, and the read that held
NCO 31 at 45 cited it.

The soul recall (`deploy/soul/main.py`, `_is_active`) withholds any record whose
`status` is set and is not `active`, and serves any record with no status. A new
ruling filed beside this one would not have stopped it. So the record itself was
re-written: `record.json` is the record exactly as the recall returned it, all
ten fields, plus `status: overruled`, `overruled_on` and `overruled_by`.

`workflow.json` is the one-off n8n workflow that wrote it, using the Write-Back's
own Pinecone credential and endpoint: build the record, upsert it, refuse any
answer that is not 2xx, fetch it back, and refuse unless the read back carries
`status: overruled` and the same text. It ran once as execution 4472 on
2026-10-25T23:31Z on workflow `5Z7HqAiFxfXf3yHG`: the upsert answered 201, and
the read back carried status overruled, the unchanged text, and twelve metadata
keys, the original nine plus the three new ones. The workflow was archived the
same minute.

To restore the record, upsert `record.json` without the three status keys.
