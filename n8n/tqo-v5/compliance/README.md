# TQO FINAL V5 compliance checks

These tests run behaviour checks on the LIVE node code, read from
`../exports/qEkGOUsNyVaRAmm6_active.json`. Nothing in this folder is pasted into
n8n. The candidate patches that used to live here (PR #367 and its rebuild) have
been published, and the copies and replacement lists are deleted.

- `compliance.test.mjs` drives OS 28: Publish Gate, Script: Fill Run Fields and
  QC Doctor Gate with synthetic rows: the C4 line in the first three lines, the
  title laws, the 90 floors, the script doctor verdict on the real data table
  shapes, and the universal acceptance contract.
- `rebuild/rebuild.test.mjs` runs the same laws plus Preflight: Can This Clear?,
  including that Preflight agrees with the two gates it mirrors.
- `rebuild/mutants.py` proves `rebuild.test.mjs` can fail: it breaks one rule at
  a time in a temporary copy of the export. Run it after any change to the test.

Since 2026-10-28 (ruled by Tee, "Drop the AI review from the publish gate") the
AI review receipt gates nothing. Authorship is the human approval
`approved:<sha256 of the script>`; the script slot of the QC Doctor Gate is the
script doctor verdict at a floor of 90. The tests assert that behaviour.

After a new export, run both tests. A failure means live code changed a rule
these tests protect: read it before editing the test.
