# Review correction: inventory CLI pagination

Date: 2026-10-21
Review: PR #390, thread PRRT_kwDOTzp8c86usja5 (independent Codex review of 146d6a2f30cd9591a797ffeef2c8e51abe0f2b2e).

The review was reproduced: the inventory CLI rejected --limit and --offset, so an owner with more than the default page could not inspect later projects using the documented command. Two new CLI tests failed before the correction. The inventory subparser now exposes both arguments and forwards them with defaults 20 and 0. All 33 client tests passed after the change. Server authorization, SQL, personal login and source-body restrictions are unchanged.

The full local repository run after this correction returned 5,282 passed, 3 skipped and one failure in the existing test_presence_service.py::test_interrupt_for_another_turn_acks_without_cancelling. It expected the message immediately following interrupt_ack to be state/listening, but received audio. The same unchanged test failed in three isolated probes of a CLEAN parent checkout at 9fbc37e35acc38880e6f0b5a5978a58a6fcb9418, where none of the new Creator Workspace code exists. apps/presence and its tests are unchanged by this PR. Source inspection shows ack and state emitted through separate lock acquisitions while the other turn continues; this is a baseline ordering issue, not evidence that the client pagination change alters the presence service.

No test was modified, skipped, retried by a plugin, or assigned a fabricated status. The local failing result remains recorded. The prior exact candidate had 5,281 passing tests and native CI success, but that is not reported as a passing local run for this correction. Native CI and review must be checked on the new published head before any merge; a red native check is not waived.

Corrected blob identities, compared to the tested local files:
- tools/creator_workspace_reader.py: 58c919830e6295f8f74b9018b1af1ff28ecc7d3f
- test_creator_read_client.py: 45250167edea4924d70f0f2cca6638989fe3622c

Runtime remains default-disabled until the separately authorized deployment and scoped grant have successful production readback. No production key or grant is introduced by this correction.
