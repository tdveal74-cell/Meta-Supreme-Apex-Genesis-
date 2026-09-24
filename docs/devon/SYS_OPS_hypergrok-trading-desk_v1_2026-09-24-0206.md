# HyperGrok trading desk on Rakazo: stood up read-only

Filed 2026-09-24 at 02:06Z. Tee asked for the HyperGrok Trading Desk
(galleonlabs/hypergrok-trading-desk) set up by its `SETUP.md`, top to bottom.
It was written for Grok Bot; it now runs on Rakazo. Setup stayed read-only:
no key requested, no order placed.

## Rulings

All from Tee on cards, 2026-09-24.

- Engagement level: testnet. The desk record says so. Status stays
  research-only until an API wallet exists.
- Account address: Tee posts it later. Recorded as pending.
- Risk limits: the Risk Manager runs the `desk-risk-limits` interview with Tee.
- Standing approval for a protective stop: no. Chase 15 minutes, then Tee fixes
  it in the Hyperliquid app.
- Approval gate: "no key is the gate". Rakazo approval rules match tool names
  only (`packages/core/src/action-approval.ts`, `ruleMatches`), exchange sends
  run through `shell`, and `shell` is in `APPROVAL_EXEMPT_TOOLS`. So Rakazo
  cannot express SETUP.md section 7's rule. The only exact rule available,
  approval on every shell command, would stop every bot in the space. Tee
  chose to keep the desk keyless and to design the key setup before testnet.

## What exists

| piece | where | proof |
|---|---|---|
| release | `/home/rakazo/shared/hypergrok`, v1.4.4, `bae4c70` | sha256 over all 100 files `2d457164...71e7` matches a separate clone where `check.sh` passed in full |
| desk folders | `/home/rakazo/shared/trading-desk` | desk doctor: desk folders PASS |
| path map | `/home/rakazo/shared/DESK_PATHS.md` | `/workspace` is not writable on the Rakazo computer |
| bots | Desk Lead `cmuev267q009n2kp41uvmn6rp`, Market Analyst `cmuev2s9y009v2kp491d04t9o`, Research Analyst `cmuev36ay009z2kp4a7syzunx`, Strategist `cmuev3kiq00a32kp4nhou8pvr`, Risk Manager `cmuev42iq00a72kp4akp0o13v`, Execution Trader `cmuev4lyt00ab2kp4hwu9k96g`, Trade Reviewer `cmuev51hr00af2kp4n9om7duw` | created through the connector, profile verbatim, full system prompt as instructions plus a labelled Rakazo note; none has EditForge |
| skills | 17 shared skills, status pointer | each `skill_read` returns it; pointer to the verified file on disk |
| group | Trading Floor `cmuevp3w800ar2kp422g1zqot`, six members | membership read back by bot id; Tee created and named it |
| desk record | `trading-desk/desk.md` | doctor: desk record PASS, no key-like field |
| receipt | `trading-desk/SETUP_RECEIPT.md` | written by the Desk Lead at 02:07Z, sha256 `4a5c1346...6869`; desk.md sha256 `40395db3...5126` |

## Where Rakazo differs from Grok Bot, and what was done

- No `git` and no `pip` on the Rakazo computer. The Desk Lead stopped at
  SETUP.md's gate, as the runbook says to. It had fetched the tag's archive
  over HTTPS. SETUP.md refuses an unverified archive, so the archive was
  proven byte-identical to the reviewed commit by the digest above before
  anything ran. On that computer `check.sh` passes everything except its git
  fixture test. The Opening Bell and the doctor use the standard library only.
  The Python SDK is not installed, and nothing read-only needs it.
- Skills are pointers, not full copies. Rakazo can store a skill of this length
  (`CreateAgentSkillInput`, 100,000 characters), but no tool available here
  could copy 17 files byte for byte, and a model retyping 161 KB is the
  mismatch SETUP.md warns about. The pointed-to files are the verified copies.
- `write_file` on the team computer resolves a path starting
  `/home/rakazo/...` under the bot's home. It happened twice. The Desk Lead
  caught it from the doctor's output both times and moved the file with shell.
  Absolute paths go through shell on this desk.

## Verification, SETUP.md section 9

Desk-wide checks:

- Doctor: 9 passed, 1 warning (risk limits not written), 0 failed.
- Opening Bell on mainnet, ETH and BTC. Each says "This snapshot is not a
  trading signal."
- The testnet public read answered through the Opening Bell's `--base-url`.

The five checks:

1. Market Analyst BTC brief: timestamped, sources named, facts kept apart
   from calculations and interpretation, and the 25 bps depth marked as a
   floor. Pass.
2. Risk Manager: REJECT, because `risk-limits.md` does not exist. Asked for
   the arithmetic as an illustration, it sized against the desk ceiling of
   2%: stressed distance 1,000.0383, size 0.19999 BTC, worst case $200, all
   labelled NOT A TICKET. Recomputed here, the arithmetic holds. The stop
   trigger 83,231.082 carries more precision than Hyperliquid prices allow;
   the Execution Trader's rounding step exists for that. Pass.
3. Execution Trader: went through the pre-send checklist item by item and
   refused. No proposal file, no account, no key, and `HYPERLIQUID_NETWORK`
   unset. It also noticed the illustration used mainnet data on a desk
   recorded as testnet. Pass.
4. Trade Reviewer, by DM: opened `journal/2026-09-24.md` with a setup entry.
   Pass.
5. Research Analyst: HyperBFT and the HyperCore and HyperEVM split, from the
   official docs, read at 02:06Z, with the page's undated edit time marked
   unknown. Pass.

## Before testnet

- Key storage. A Rakazo space secret becomes an environment variable in every
  bot's shell (`agent-environment.ts`), and the team computer's files are
  shared. A testnet API wallet key stored either way would be readable by the
  TQO producers, Thoth and every other bot. The design has to confine it to
  the Execution Trader. The Execution Trader's instructions already refuse a
  space-wide key.
- The Python SDK needs `pip`, which the computer lacks.
- The account address, and the Risk Manager's limits interview.

## DEVON RECEIPT

AREA: Money
TYPE: SYS_OPS
ARTIFACT: docs/devon/SYS_OPS_hypergrok-trading-desk_v1_2026-09-24-0206.md
DATE: 2026-09-24
DECISIONS: Tee set up the HyperGrok desk on Rakazo at engagement level testnet, account pending, risk limits by the Risk Manager's interview, no standing approval for protective stops, and ruled that no key is the gate because Rakazo approval rules cannot match exchange commands.
FINDINGS: Seven bots, 17 pointer skills and the six member Trading Floor exist, on v1.4.4 verified byte-identical by digest. Doctor 9 passed, 0 failed. All five verification checks passed read-only. The Rakazo computer has no git or pip, write_file misplaces absolute paths, and space secrets reach every bot's shell.
OPEN: Key storage design confined to the Execution Trader before testnet. SDK install without pip. Account address and risk limits interview with Tee.
STATUS: Desk live in research mode; no key, no order.
TOKEN: dcp_claude_f18d1fd0d3e6a354456d28bfbbe62973b702de8f
