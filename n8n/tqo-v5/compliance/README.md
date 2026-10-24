# TQO FINAL V5 compliance nodes

Do not paste the three `*.js` files in this folder into n8n. They are PR #367
as written on 2026-10-17 against export `9320520f`, plus a Quality90 layer
staged here on 2026-10-21 that is not the one that went live. Pasting them
would roll back the live Quality90 controls.

The live workflow was re-imported on 2026-10-21 as version `dd734ea2`
without #367. What goes into n8n now is `rebuild/draft/`, built on the live
bodies in `rebuild/live/` and pinned by `rebuild/live/manifest.json`. Read the
live `activeVersionId` before writing anything: if it has moved past
`dd734ea2`, rebuild on the new version first.

- `compliance.test.mjs` still pins the old files to the old export, as a record.
- `rebuild/rebuild.test.mjs` is the test for what goes live. It runs in CI.
- `rebuild/mutants.py` proves that test can fail. Run it after any change to
  `rebuild/`.
