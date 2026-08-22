# SYS_OPS_continuity_v1_2026-08-22

## Provenance

Rewritten from current doctrine on 2026-08-22. The predecessor was lost in the
name purge and is not recoverable from any surviving file. Nothing in this
document is a reconstruction of the lost text, and nothing here comes from a
model's memory of it. Every step cites the live source it derives from.

Status: new artifact, version 1. Supersedes nothing. Filed to the repo first;
filing to Drive is Tee's write.

## Why this document exists

The vault's governing documents were violated by threads that had read them.
The naming convention forked twice in one day; the filing laws forked
fourteen seconds apart; five documents forked in two days. Each fork was a
thread starting or ending a session without a ritual. This SOP is the ritual.
Source: `docs/devon/MERGE_MAP.md`, contradictions section, and the one-writer
ruling of 2026-08-22.

## Session start

1. State whether you hold the write. One writer at a time, one Claude thread
   at a time, ruled 2026-08-22. Not confirmed means read and build, never
   write to `_Devon Core`. Source: `docs/devon/MERGE_MAP.md`, "What was not
   written back to Drive".
2. Read the newest context pill before anything else. Current: v16, Drive id
   `1bySPMORLCMlBkNv9YuK2uvuWTiJL6_qS`. If a newer version exists in the
   folder, the newer one wins; that is the whole precedence rule for
   versions of the same artifact. Source: `services/devon/vault.py::SOURCES`
   and `services/devon/precedence.py`, Drive id
   `1EaFyPPAXIX5j75oJ06tvvUuq4Qd73jB4`.
3. Check the watchdog inboxes. The Precedence Guard (`W5rlpAt6hsJAExU6`)
   emails only when it found something; an unread finding is an open wound,
   not background noise.
4. Declare which DEVON files were actually opened. The standard is DEVON,
   not memory: a claim about vault contents needs a file that was read this
   session. Source: `services/devon/persona.py::SOURCE_OF_TRUTH` and the
   receipt's load-bearing `FILES_OPENED` field.

## During the session

5. A contradiction between documents is flagged, never silently resolved.
   Closest to today wins for versions of the same artifact; anything else
   goes to Tee. Rulings beat rules. Source: precedence doctrine v2 and
   Persona Hard Rule 5.
6. A model-supplied Area is never trusted. Validate against the nine,
   discard on no match, decline on a tie, and never add an Area without
   Tee's ruling. Source: `services/devon/areas.py`.
7. Decisions are captured when they happen, not remembered at the end. A
   ruling that lives only in scrollback is a fork waiting to happen.
8. Secrets never touch Drive. A key found in the vault is flagged
   immediately, and moving it is containment, not remediation. Capture
   tokens live in the n8n workflow only. Source: canon, and n8n workflow
   `pPIt2cELH2RVZktS`, Check Token node.

## Session end

9. Post a DEVON RECEIPT to the capture webhook, carrying this poster's
   token as a `token` JSON field or a `TOKEN:` line in the block. The
   webhook strips the token before anything is filed. `OPEN` and `NEXT`
   are the handoff: the next thread starts from those two fields, so an
   empty `NEXT` on an unfinished task is a dropped baton. Source:
   `services/devon/receipts.py` and n8n workflow `pPIt2cELH2RVZktS`.
10. Apply supersede markers before leaving. If this session's work replaced
    a document, the loser gets the `SUPERSEDED_` rename now, by the thread
    that knows it lost, not later by a thread that has to guess. Source:
    Filing Law 6, `services/devon/filing.py::law6_retire`.
11. Nothing marked shipped, approved, or merged by the thread itself. The
    human owns SHIP. Inspect, then hand back. Source: Persona Hard Rules 2
    and 9, and `services/devon/flagship.py`.

## Failure modes

- **Fork detected** (two files sharing a name, or two current versions):
  stop writing. Apply precedence: closest to today wins, future-dated
  loses, protected markers are never auto-superseded, and a trivially
  small file does not beat a full one. Anything the rules do not settle is
  flagged for Tee with both candidates named. Source:
  `services/devon/precedence.py`.
- **Platform off protocol**: a receipt arriving without `FILES_OPENED` or
  `UNVERIFIED` is the tell. The parser flags it; the response echoes the
  warning to the poster. Re-issue that platform's standing instructions.
  Source: `services/devon/receipts.py` and the webhook parser.
- **Untokened or wrong-token capture**: during legacy grace an untokened
  post files flagged UNAUTHENTICATED; a wrong token is refused outright.
  After grace ends, untokened posts are refused too. The flip is one
  constant, `LEGACY_GRACE`, in the Check Token node. Source: n8n workflow
  `pPIt2cELH2RVZktS`, verified by shown runs on 2026-08-22.
- **Write blocked** (quota, permission, no writer confirmation): nothing
  else writes on your behalf. Park the artifact in the repo, say plainly
  what is parked and why, and put it in the receipt's `OPEN` field.
- **Lost document**: it is rewritten from live sources as a new v1 that
  says so in its header, or it stays lost. A model's memory of a lost
  document is not a source, and presenting a reconstruction as a
  restoration is the one failure this vault has promised never to repeat.
  Source: `docs/devon/MERGE_MAP.md`, "Known stale and owed".

## Passing the write

The write passes by an explicit statement from Tee to a named thread, and
by nothing else. It does not pass by silence, by a session ending, or by a
thread asserting it. Until Tee has a mechanism for recording the holder,
the receipt's `DECIDED` field is where a grant is written down, which makes
the Thread Log the audit trail of who held the write and when.
