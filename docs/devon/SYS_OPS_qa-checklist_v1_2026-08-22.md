# SYS_OPS_qa-checklist_v1_2026-08-22

## Provenance

Rewritten from current doctrine on 2026-08-22. The predecessor was lost in the
name purge and is not recoverable from any surviving file. Nothing in this
document is a reconstruction of the lost text, and nothing here comes from a
model's memory of it. Every item below cites the live source it derives from:
a doctrine module in `services/devon/` (each of which declares the Drive id it
was compiled from), a test that executes the check, or an n8n workflow id.

Status: new artifact, version 1. Supersedes nothing. Filed to the repo first;
filing to Drive is Tee's write.

## Part 1. The executable checks

Most of the QA surface is code and runs itself. Run it before trusting
anything else in this list:

```
python -m pytest test_devon_*.py -q        # expect 313 passed
python -m pytest -q                        # full platform, expect 492 passed
ruff check .                               # expect clean
```

Last verified run: 2026-08-22, 492 passed, 0 failed, on merge commit 4fda844.

| Suite | Functions | Proves |
|---|---|---|
| test_devon_areas.py | 14 | nine Areas, model-supplied Area never trusted, tie declines |
| test_devon_naming.py | 20 | naming convention v4 parse, validate, build, disambiguate |
| test_devon_precedence.py | 16 | which draft is current, and when nothing wins |
| test_devon_receipts.py | 19 | DEVON RECEIPT, both formats, load-bearing fields |
| test_devon_filing.py | 32 | the eight filing laws |
| test_devon_commands.py | 21 | command routing, per-intent floors, 0.92 for destructive |
| test_devon_approval.py | 19 | the approval gate, all eight decide paths |
| test_devon_assistant.py | 21 | DEVON plans and gates, never executes |
| test_devon_flagship.py | 21 | the ship gate arithmetic |
| test_devon_integrity.py | 20 | no execution capability, provenance declared, word list |
| test_devon_cerebras.py | 28 | enrichment limits, declines recorded as declines |

## Part 2. The manual checks no test can run

These need a human or a live system. Check each one when the session it
applies to happens, not on a schedule.

### Before any vault write

1. Confirm you hold the write. Canon has one writer at a time, ruled
   2026-08-22. A thread that has not confirmed it reads and builds, never
   writes. Source: `docs/devon/MERGE_MAP.md`, section "What was not written
   back to Drive".
2. List the destination folder and read the newest sibling before writing a
   new version of anything. Source: Filing Law 2,
   `services/devon/filing.py::law2_require_sibling_read`, compiled from
   Drive id `1YxrdXHqlT5kkdzWey5qO_21KbVDQd9ID` (filing laws v3).
3. Validate the filename against naming convention v4 before filing:
   `AREA_TYPE_slug_vN_YYYY-MM-DD`, plain integer versions. Source:
   `services/devon/naming.py::validate_filename`, Drive id
   `1r5-7JCqMDEHcYWj97AxZuWuzb7wdSYCL`.
4. Never let a model assign the Area. Validate any suggestion against the
   nine; discard what does not match; decline on a tie. Source:
   `services/devon/areas.py::resolve_area`, Drive id
   `1UrmxHSkVQjdHdiF2rRUo2lOCIbx1EFjg` (AREAS.md, ACX ruled ninth
   2026-08-20).

### After any vault write

5. Read the file back and confirm the payload landed. A success response is
   a claim; a read-back is a receipt. Source: Filing Law 3,
   `services/devon/filing.py::law3_validate_readback`, and Persona Hard
   Rule 2.
6. If the write superseded something, apply the `SUPERSEDED_` rename to the
   loser. Never delete; retirement is a rename and a move. Source: Filing
   Law 6, `services/devon/filing.py::law6_retire`.

### At session end

7. Post a DEVON RECEIPT to the capture webhook, with this poster's token.
   Both formats are valid; `FILES_OPENED` and `UNVERIFIED` are load-bearing
   and their absence is flagged by the parser. Source:
   `services/devon/receipts.py` (capture protocol
   `1jVAQ6KwhFXoONg3cLYFDfi0zhLMjWAfi`, standing instructions v3
   `1A88Nkf5BpCZysmHP7XYMXBtaEh4Eqj9M`), and n8n workflow
   `pPIt2cELH2RVZktS`, Check Token node, added 2026-08-22.

### Before any effect

8. Any high-impact action goes through the approval queue with a
   `what_happens` the approver can actually read. No description, no
   consent. Source: `services/devon/approval.py`, n8n workflow
   `syRVj0G47mA1b0Xn`, context pill v16 section B11.
9. Nothing publishes without a human watching or listening end to end.
   Source: Persona Hard Rule 9, `services/devon/persona.py`.

### Before any SHIP claim

10. Score against the flagship bar: every dimension at least 3, mean at
    least 4.0, security exactly 5, verification at least 4. A claim of PASS
    without the arithmetic is not a PASS. Source:
    `services/devon/flagship.py`, Drive id
    `1s4l6r9ucGWrtEENqlBqDmFtpl4_85z_m`.
11. Spot-check the deliverable against the hard rules: no em dashes,
    artifacts not claims, unverified said plainly. Source:
    `services/devon/persona.py::HARD_RULES`.

## Part 3. What already watches itself

These n8n workflows run their own checks. The QA task is only to confirm
they are still active and to read what they send:

| Workflow | Id | Cadence |
|---|---|---|
| DEVON Precedence Guard | `W5rlpAt6hsJAExU6` | daily |
| DEVON Capture Nudge | `YHueoBK7TSLdTlfF` | daily, emails only past 48h silence |
| DEVON Duplicate Sweep | `X7OGXWHBx57CIG42` | daily, never deletes outright |
| DEVON Pipeline Watchdog | `wndFo6uJCqVuINaV` | every 4 hours |
| DEVON Monthly Credential Review | `yro0wBRGghMjkZhj` | monthly |

A watchdog email that stops arriving is itself a finding. The Capture Nudge
sends a BLIND alert when its own check fails, so total silence from it means
the checker is down, not that everything is fine.
