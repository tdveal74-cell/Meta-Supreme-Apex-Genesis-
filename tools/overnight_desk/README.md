# Overnight Desk, paper engine

The rules of a published trading prompt, "Claude Overnight Desk 3.0", rebuilt
as deterministic Python that touches no trading venue.

## Read this first

This desk has no source of data. Nothing here fetches a price, a holder count
or anything else. It runs on a timeline someone hands it, and the only
timeline in the repository is synthetic: coins and prices written to exercise
the rules. No real night has been recorded or replayed, so no number this
package prints says anything about a real market.

It cannot trade. The only executor fills orders on paper.

## Why it exists

Tee attached the prompt on 2026-11-26. An audit recommended leaving it unbuilt
as written. Asked on a card, Tee picked "Build toward the full desk". This
package is the first piece: everything in the prompt that can be built and
tested without an account, a browser or an order. The status record is
`docs/devon/SYS_OPS_overnight-desk-paper-engine_v1_2026-11-26-0632.md`.

## What it does

- Reads recorded snapshots of coins and of the market from a timeline file.
- Applies the prompt's five bots. Risk runs first in every tick, because sells
  go before buys. Then scanner, analyst, brain and the entry rule.
- Fills orders on paper, with every cost named: a venue fee, a pool fee, a
  flat fee and the price impact of the order on a constant-product pool. A
  sale into a pool with nothing left in it is recorded as a total loss.
- Writes a lesson after most losses (`SPEC.md` says when it does not). A
  lesson can only block a later trade.
- Prints a morning report that answers the four tests in the prompt's line
  94. Each reads pass, FAIL or n/a. A check the night gave nothing to
  test reads n/a and never pass.

## What it does not do

- It sends no order.
- It reads nothing from FOMO and acts on nothing there. No browser lane, no
  session token, no private interface.
- It does not choose your risk. Six numbers the prompt never states have no
  default: the largest ticket, the most open positions, the most total
  exposure, and three fee rates. The desk refuses to start until they are set.
- It makes no claim that the strategy has an edge. A paper night would measure
  coin selection against modelled prices. It would not measure execution.
- It does not see price drift between deciding and ordering. The desk gets one
  reading per coin per tick. The morning report says so every night.

Nothing in this package is a buy, sell or hold call, and none of it is
financial advice.

## Three things to know before trusting a result

1. One loss can quiet the desk. The lesson rule is invented, and a typical
   loser writes a check on its liquidity. A loss on a coin with $40,000 of
   liquidity then blocks every later coin at or under $40,000. The fixture
   night shows it happen.
2. A stop is not a guarantee, and the prompt's sizing leaves out costs. The
   prompt sizes a ticket so a stop at exactly 25% loses exactly 3% of cash.
   Fees and price impact come on top, so a stop-out at full size loses a
   little more than 3%. A price that gaps through the stop, or a drained
   pool, takes far more, up to the whole ticket. The desk reports each of
   these as a rule violation.
3. When an exit cannot be carried out, the desk says so and keeps going. It
   records a violation, leaves the position as it was and tries again on the
   next reading.

## Read these before trusting a number

- `SPEC.md`: every rule, the source line it came from, the reading taken where
  the prompt contradicts itself, a list of every definition this build chose,
  and a label on everything that had to be invented. The invented rules and
  defaults are what the code runs on today. Tee has not ruled on them.
- `STEPS.md`: the prompt defines steps 1 to 3 and gates live trading on
  "STEP 15 tests" it never states. That file proposes the missing steps.
- `settings.py`: every setting with its origin (`doc:N`, `invented` or
  `owner`) and its allowed range. Every range is invented, because the prompt
  promises ranges and gives none.

The prompt itself is a third party's published text and is not copied here.
`SPEC.md` records its SHA-256. A line reference can be checked by someone who
holds the file, and by nothing in this repository.

## Run the replay

From the repository root:

```bash
PYTHONPATH=tools python3 -m overnight_desk.replay \
  --timeline tools/overnight_desk/fixtures/synthetic_night.jsonl \
  --settings tools/overnight_desk/fixtures/settings.test-placeholders.json \
  --cash 1000
```

The fixture night is synthetic. The settings file holds placeholders for the
six owner numbers so the demo can run. They are no recommendation.

## Tests

```bash
env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python3 -m pytest -q test_overnight_desk_*.py
```

Offline, no database. What two of the guard tests do and do not show:

- `test_overnight_desk_base.py` fails if a file in this package imports any
  module outside a written list of twelve standard library modules, or calls
  `eval`, `exec`, `compile`, `__import__`, `open`, `input` or `breakpoint`, or
  calls a method on its list of banned methods (`write_text`, `write_bytes`,
  `open`, `unlink`, `mkdir`, `rmdir`, `touch`, `rename`, `symlink_to`,
  `hardlink_to`, `chmod`, `system`, `popen`), or if a `.py` file holds one of
  eight banned words (the venue's name, `prod-api`, `session token`,
  `bearer `, `private key`, `seed phrase`, `http://`, `https://`). It guards
  against drift and is no sandbox.
- `test_overnight_desk_paper_gate.py` fails if any class in the package but
  the paper executor defines `execute`, or if anything sets a `kind` to live.

## The gate on anything live

`ExecutorKind.LIVE` exists so the gate can be tested. Nothing constructs a
live executor. The desk itself refuses to hand an order to any executor that
is not the paper one unless it was given an approval for that one order that
names a person and carries a time. "The paper one" is decided by the
executor's class and never by what it calls itself. That is the default and
it is not a setting.

The desk's executor is fixed when the desk is built. `desk.executor` is read
only, and assigning to it raises `AttributeError`. Whether the executor is the
paper one is read from the executor object each time an order is handed over,
so no stored answer can go stale.

The gate does not stop code that writes to the desk's private attributes. A
test replaced the approval callback after the desk was built, and an executor
that is not the paper one then received its order. It does not stop code that
replaces functions in the paper module either: with `paper.require_approval`
replaced by a function that returns at once, the same executor received its
order with no approval. Both are ordinary Python and out of its reach.

The gate covers refusals. It does not cover an executor that fails after
sending an order. What a live desk does then is undecided, and it has to be
ruled on before one is built.

The approval is a record. It does not prove a person gave it, because any
code can build one. A real approval path would have to prove who gave it, and
nothing here does.

One consequence to rule on before anything live is built: with that gate, a
stop cannot fire unattended. Either a person approves each sell or the stop
waits.
