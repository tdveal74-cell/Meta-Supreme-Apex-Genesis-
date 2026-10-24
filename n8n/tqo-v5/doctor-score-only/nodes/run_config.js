// Run Config for the score-only script doctor. Ruled by Tee 2026-10-24: score
// the hand-loaded Scripted rows, never rewrite them. This workflow runs only
// when a person starts it; it has no schedule and no webhook.
// FIRST_RUN_LIMIT applies until one score-only doctor line has been written to
// either table, so the first run scores a single row and proves the provider
// and the recall before the rest are spent. A run with no recall stops at
// Recall Required and writes nothing, so a written line always had the recall.
// ROW_LIMIT applies to every run after that one. Each run is still started by
// hand.
// ONLY_ROWS, when it is not empty, limits the run to the rows it names, written
// as 'TQO:49' or 'NCO:30'. A name that is not an eligible row stops the run.
// WRITE false makes a measurement run, ruled by Tee 2026-10-24 to see how far
// one row's score moves between runs: every step runs and the doctor is paid,
// and nothing is written to either table. The run report lists each score.
return [{ json: { FIRST_RUN_LIMIT: 1, ROW_LIMIT: 20, ONLY_ROWS: [], WRITE: true } }];
