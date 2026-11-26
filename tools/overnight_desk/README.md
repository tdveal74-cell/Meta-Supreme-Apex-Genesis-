# Overnight Desk, paper engine

The rules of a published trading prompt, "Claude Overnight Desk 3.0", rebuilt
as deterministic Python that touches no trading venue.

## Why it exists

Tee attached the prompt on 2026-11-26. An audit recommended leaving it
unbuilt as written. Tee ruled, on a card, to build toward the full desk. This
package is the first piece: everything in the prompt that can be built and
tested without an account, a browser or an order.

## What it does

- Reads recorded snapshots of coins and of the market.
- Applies the prompt's five bots in order: scanner, analyst, brain, entry
  rule, risk.
- Fills orders on paper, with every cost named: a venue fee, a pool fee, a
  flat fee and the price impact of the order on a constant-product pool.
- Writes a lesson after every loss. A lesson can only block a later trade.
- Prints a morning report that answers the four tests in the prompt's last
  paragraph, and says so when one of them fails.

## What it does not do

- It sends no order. The only executor is the paper one.
- It reads nothing from FOMO and acts on nothing there. No browser lane, no
  session token, no private interface. Each of those returns to Tee on its own
  card before any code is written.
- It does not choose your risk. Six numbers the prompt never states have no
  default: the largest ticket, the most open positions, the most total
  exposure, and three fee rates. The desk refuses to start until they are set.
- It makes no claim that the strategy has an edge. A paper night measures coin
  selection against modelled prices. It does not measure execution.

Nothing in this package is a buy, sell or hold call, and none of it is
financial advice.

## Read these before trusting a number

- `SPEC.md`: every rule, the source line it came from, the stricter reading
  taken where the prompt contradicts itself, and a label on everything that
  had to be invented. The invented parts wait on Tee's review.
- `settings.py`: every setting with its origin (`doc:N`, `invented` or
  `owner`) and its allowed range. Every range is invented, because the prompt
  promises ranges and gives none.

## Run the replay

From the repository root:

```bash
PYTHONPATH=tools python3 -m overnight_desk.replay \
  --timeline tools/overnight_desk/fixtures/synthetic_night.jsonl \
  --settings tools/overnight_desk/fixtures/settings.test-placeholders.json \
  --cash 1000
```

The fixture night is synthetic. Its coins and prices were written to exercise
the rules and describe no real market. The settings file holds placeholders
for the six owner numbers so the demo can run. They are no recommendation.

## Tests

```bash
env -u PYTHONPATH -u DATABASE_URL -u TEST_DATABASE_URL python3 -m pytest -q test_overnight_desk_*.py
```

Offline, no database. `test_overnight_desk_base.py` also fails if any file
here imports a network or process library, steps outside the standard
library, or names the venue.

## The gate on anything live

`ExecutorKind.LIVE` exists so the gate can be tested. Nothing constructs a
live executor. The desk itself refuses to hand an order to any executor that
is not the paper one unless a named person has approved that one order. That
is the default and it is not a setting.
