"""
The DEVON vault map: Drive, Notion, Airtable, n8n.

Source on Drive: SYS_INDEX_master-directory_v6_2026-08-22
(Drive id 1sSnB7tdXhf7ECAknNgE_tINrmJ1maUg_), plus SYS_SPEC_context-pill_v16
(1bySPMORLCMlBkNv9YuK2uvuWTiJL6_qS) and SYS_SPEC_webhook-paths_v1
(1wKkFGVBXaFZqWvLjSiBrxXWLk8Lwkd8c). All read 2026-08-22.

WHAT THIS MODULE IS AND IS NOT
Data only. No network calls, no credentials, no writes. It answers "where does
this go" and "who is allowed to put it there". The caller performs the effect.
Keeping the map inert means importing it can never touch the vault.

ON STALENESS, STATED RATHER THAN HIDDEN
Identifiers here were read on 2026-08-22 and are correct as of that read. They
are not self updating. The master directory itself shipped a version citing file
ids that had been deleted hours earlier, which is the standing failure class of
this whole system: an artifact is written, reality moves, nothing writes back.
Treat `verify_before_automation` as a real instruction. An id that returns
entity-not-found is a stale map, not a missing file.

Reference by id, never by name. Ids survive rename and move. Renames and moves
are safe, deletions are not.
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Dict, Optional, Tuple

READ_ON = "2026-08-22"
VERIFY_BEFORE_AUTOMATION = (
    "Ids were read on 2026-08-22 and are not self updating. Confirm an id resolves "
    "before an automation depends on it."
)

SOURCES = {
    "directory": {
        "drive_id": "1sSnB7tdXhf7ECAknNgE_tINrmJ1maUg_",
        "title": "SYS_INDEX_master-directory_v6_2026-08-22",
    },
    "context_pill": {
        "drive_id": "1bySPMORLCMlBkNv9YuK2uvuWTiJL6_qS",
        "title": "SYS_SPEC_context-pill_v16_2026-08-22",
    },
    "webhook_paths": {
        "drive_id": "1wKkFGVBXaFZqWvLjSiBrxXWLk8Lwkd8c",
        "title": "SYS_SPEC_webhook-paths_v1_2026-08-21",
    },
}


# ---------------------------------------------------------------------------
# Drive
# ---------------------------------------------------------------------------

VAULT_ROOT = {
    "name": "Devon 2nd Brain",
    "id": "18_ZF2pYi7BgW6KStvAHNMmcCZHVQFGMo",
    "rule": "The only permitted item at Drive root. Anything else at root is a violation.",
}

FOLDERS: Dict[str, str] = {
    "0. Inbox": "1wvKmGuaWQTxOT6Q8XQCU3Zv825VvbgdO",
    "1. Projects": "1E7XUosP3OzAi9tDShcVNbhm-9zzzsMsd",
    "2. Areas": "1efaZ37s3PBjeEFD1HUQnN3QwH3pV0Rbc",
    "3. Resources": "1Ls1zoO_nUyCTnEdZ5d-2Nz8IdbEoYOVU",
    "4. Archive": "1xJuCYDrQdqBGqt0I7GOFkkLHAtdmRab6",
    "_Devon Core": "17chQD2DTfzbnZy2oGwiJxEk7PHvnstBp",
    "_Templates": "12aqJzZRCZWTb8hbEb9mTxf6FPEt46d2c",
    "Mirror Reads": "1ZwE5USNTFHN5Tj2sT97kLOAAzttl7Nj4",
}

# The capture inbox is the only folder non-Claude platforms may write to.
CAPTURE_INBOX = {
    "name": "00_Capture Inbox",
    "id": "1ZusR2B7GWMf2MsCipgb5srZ8mS5z4F0B",
}

# Mirror Reads was created 2026-08-14 and held zero files when listed on
# 2026-08-22. Recorded so that a caller expecting mirror output knows the folder
# is producing nothing rather than assuming a read failure.
KNOWN_EMPTY = ("Mirror Reads",)

# Area folders, keyed by the canonical Area label from services.devon.areas.
AREA_FOLDERS: Dict[str, str] = {
    "ACX": "1a_baNvgH9CBb4biuBCbdNb_4P9fvkO1a",
    "TQO": "1DXDzO_qY17i1ChE-gOqL3oOwBVbaveLH",
    "NCO": "1GhyNDBaBLrcJux9gEVtVpSTnbDK1eJzO",
    "Podcast": "1ZNnbg7bFfcEAM0bMZ96sUnZsr8NXXl6c",
    "Systems": "1La9LZ1zvpnU6-ep-EVStEy33M8cvyUGr",
    "Learning": "1_WWVxVMfhCxMdxXLv6NjSiKPCzZmbQFu",
    "Family": "1LU5mD4reyWwN-D3O_41FCvP1BuUvqlhd",
    "Money": "1PbsQU2VSLSt-e7scjWY83X5k-y27c8OO",
    "Health": "1BkZ0YfANbOS0fQf_2F-e-22LTSeV8xRg",
}

# Every show tree uses the same six folders.
SHOW_TREE_FOLDERS: Tuple[str, ...] = (
    "00_CANON",
    "01_SCRIPTS",
    "02_BRAND",
    "03_OPS",
    "04_SOURCE_MATERIAL",
    "05_RETIRED",
)

SHOW_TREES: Dict[str, Dict[str, str]] = {
    "TSWS": {
        "master": "1qR2TpfRQG5-ACbNNG77srYyiRTbJwlDn",
        "00_CANON": "1IRamTK0jDCgT0W8LMgsUntAsxR4oTERO",
        "01_SCRIPTS": "1gbx4JBnCVwpxS4eTOCy24SDkmH4LrztW",
        "02_BRAND": "1nDaF29PFj6GXQ4l-dCzoneB6cgbaesV5",
        "03_OPS": "1llTgAIW3x6TbqAcWVB_0yq_36x69YvxQ",
        "04_SOURCE_MATERIAL": "1-WsCw49Min5KIIyTbIq_BbGd4zTBngx-",
        "05_RETIRED": "1kl9FZBgVL2HQD8FdCE1w3OJQ3U_sFAG-",
    },
    "TQO": {
        "00_CANON": "1Kb49FhgNUT296J4_xizqbxiAEPScWrNZ",
        "01_SCRIPTS": "1VtnHmKxus3YCJNDk3HbF3wf6Wyh1E-mB",
        "02_BRAND": "1rFy38tz8TYZKLM4BBz1l9AZxTRN054Lq",
        "03_OPS": "1wfxVjSAh9mXNy5x5uosISiYvHXQ3eCgw",
        "04_SOURCE_MATERIAL": "1g2QKo26i_zAwSKffWw_aEGLv-0H_p6Di",
        "05_RETIRED": "1ZzuSHplFjz8svn0b6n2swR2daqItD8ur",
    },
}

# Where DEVON's drive.draft executor (Build 16) may write a draft, by Area: the
# show's scripts folder for the two shows with a tree, the Area folder for the
# rest, the capture inbox for an Area it does not know. Mirrored in the
# executor's Code node because n8n cannot import this file: a change here is a
# change there too. Ruled 2026-09-05 on Tee's "do it"; reversible, the draft
# is one document that can be trashed.
DRAFT_FOLDERS: Dict[str, str] = {
    "TQO": SHOW_TREES["TQO"]["01_SCRIPTS"],
    "Podcast": SHOW_TREES["TSWS"]["01_SCRIPTS"],
    "NCO": AREA_FOLDERS["NCO"],
    "ACX": AREA_FOLDERS["ACX"],
    "Systems": AREA_FOLDERS["Systems"],
    "Learning": AREA_FOLDERS["Learning"],
    "Family": AREA_FOLDERS["Family"],
    "Money": AREA_FOLDERS["Money"],
    "Health": AREA_FOLDERS["Health"],
    "_unknown": CAPTURE_INBOX["id"],
}

# Restricted, untouched by every sweep. Never read, list, or move without a ruling.
RESTRICTED: Dict[str, str] = {
    "TSWS MEMOIR VAULT": "1j88Euvldadd3wouVK2cxHZadaRQZ3p32",
}

# Live doctrine in _Devon Core, with the version each was read at.
DOCTRINE: Dict[str, Dict[str, str]] = {
    "master_directory": {
        "id": "1sSnB7tdXhf7ECAknNgE_tINrmJ1maUg_",
        "version": "6",
        "governs": "the folder map and ids",
    },
    "context_pill": {
        "id": "1bySPMORLCMlBkNv9YuK2uvuWTiJL6_qS",
        "version": "16",
        "governs": "current state",
    },
    "standing_instructions": {
        "id": "1A88Nkf5BpCZysmHP7XYMXBtaEh4Eqj9M",
        "version": "3",
        "governs": "behaviour",
    },
    "filing_laws": {
        "id": "1YxrdXHqlT5kkdzWey5qO_21KbVDQd9ID",
        "version": "3",
        "governs": "filing",
    },
    "naming_convention": {
        "id": "1r5-7JCqMDEHcYWj97AxZuWuzb7wdSYCL",
        "version": "4",
        "governs": "what files are called",
    },
    "voice_standard": {
        "id": "1MpGAI5OGVkw7_EZpLpBba1nJ-YQWwmOt",
        "version": "2",
        "governs": "anything published under Tee's name",
    },
    "flagship_bar": {
        "id": "1s4l6r9ucGWrtEENqlBqDmFtpl4_85z_m",
        "version": "01",
        "governs": "ship quality and the gauntlet",
    },
    "precedence_doctrine": {
        "id": "1EaFyPPAXIX5j75oJ06tvvUuq4Qd73jB4",
        "version": "2",
        "governs": "which version wins and when nothing wins",
    },
    "webhook_paths": {
        "id": "1wKkFGVBXaFZqWvLjSiBrxXWLk8Lwkd8c",
        "version": "1",
        "governs": "one path, one job",
    },
    "areas": {
        "id": "1UrmxHSkVQjdHdiF2rRUo2lOCIbx1EFjg",
        "version": "current",
        "governs": "the nine Area vocabulary",
    },
    "capture_protocol": {
        "id": "1jVAQ6KwhFXoONg3cLYFDfi0zhLMjWAfi",
        "version": "1",
        "governs": "cross platform capture",
    },
}


# ---------------------------------------------------------------------------
# Notion, live state
# ---------------------------------------------------------------------------

NOTION = {
    "parent_page": "3a468ff50db6816db38fc0da8e7edb11",
    "thread_log_database": "e91b0a7b-42c0-405e-bf5b-39975e0d4e38",
    "thread_log_data_source": "a5bcfbf5-ce1d-493b-9992-a11bc2a03dc4",
    "thread_log_properties": (
        "Title",
        "Date",
        "Area",
        "Summary",
        "Decisions",
        "Open threads",
        "Artifacts",
        "Link",
        "Logged",
    ),
    "note": (
        "Notion holds live state. Drive holds durable notes and canon. A note stale "
        "in a week belongs in Notion; a note that gains value with age belongs in Drive."
    ),
    "known_trap": (
        "A Notion integration that authenticates successfully can still see nothing "
        "until the page is shared with it. That cost a 404 and half an hour."
    ),
}


# ---------------------------------------------------------------------------
# Airtable
# ---------------------------------------------------------------------------

AIRTABLE = {
    "live_base": "app28z7XnKzjfTXwc",
    "dead_base": "appKIY47KvzBpZQOQ",
    "podcast_hq_base": "appa7WL221K1DhYnX",
    "tables": {
        "Inbox Captures": "tbl4ziFRbl5mnUcKc",
        "Thread Receipts": "tblEhgEZoNr2ztbB3",
        "Credentials": "tblkLdeuGzdtJMw7D",
        "Content (TQO)": "tblx5CcNguOypBjLI",
        "TSWS Content": "tblVhCXkBp0O0Y2tI",
        "NCO Forge Content": "tblhtxvB7xouDKpww",
        "Strategic Decisions": "tblBVwPprqdJ3m3of",
        "Conflicts": "tblbenoy1QF9KAftn",
    },
    # Closed vocabulary. Do not invent a status.
    "content_status": (
        "Idea",
        "Scripted",
        "Queued",
        "Rendering",
        "Ready",
        "Published",
        "Error",
    ),
    "known_block": (
        "Every write returned HTTP 429 PUBLIC_API_BILLING_LIMIT_EXCEEDED as of "
        "2026-08-22. This is a monthly workspace quota, not a rate limit. Backoff "
        "does nothing, retrying does nothing, switching tools does nothing. Blocked "
        "on money, not on work."
    ),
}


# ---------------------------------------------------------------------------
# n8n
# ---------------------------------------------------------------------------

N8N_HOST = "https://thequietoperator.app.n8n.cloud"

WEBHOOKS = {
    "devon-capture": {
        "job": "cross platform receipts",
        "destination": "Airtable Thread Receipts tblEhgEZoNr2ztbB3",
        "workflow": "pPIt2cELH2RVZktS",
        # Stays the single checkable phrase. node_auth_for() in the reconciler
        # matches by PREFIX, so any second clause added here is silently
        # discarded and the field would assert a layer nothing verifies. The
        # body token gate is recorded below as prose and as an explicitly
        # unverified claim, which is what it is until a check exists for it.
        "auth": "header x-devon-key",
        "auth_unverified_second_layer": (
            "A per poster token in the request body, checked by the Check Token "
            "code node of workflow pPIt2cELH2RVZktS. NOT VERIFIED by the estate "
            "reconciler: webhook_nodes() reads trigger node authentication only "
            "and never looks at a code node, so deleting or disabling Check Token "
            "would leave this entry still reporting healthy. Treat as a claim, "
            "not a fact, until a check covers it."
        ),
        "open_ruling": (
            "Header auth enforced live 2026-08-23, credential Devon Capture Key "
            "FYRvkRTOcROEYZ9P. This entry carried auth None until 2026-08-31, so "
            "anything reasoned from it before that date treated the lane as open. "
            "Posters that cannot attach a custom header now need a shim. "
            "THE SECOND LAYER IS DELIBERATE, AND AN AUDIT HAS ALREADY MIS-FLAGGED "
            "IT ONCE. The Check Token node holds four per poster tokens as "
            "plaintext literals in its JavaScript, one each for ChatGPT, Grok, "
            "Gemini and Claude. Ruled by Tee 2026-09-06: they exist so each of "
            "those platforms can file the work done on it as a receipt, so the "
            "value HAS to be known outside n8n, pasted into that platform's own "
            "custom instruction or project. Moving them into a credential would "
            "not remove the secret from the world; it would only remove one copy "
            "from the workflow JSON. Four separate tokens rather than one shared "
            "value is the point: a single platform can be cut off without "
            "breaking the other three. "
            "Blast radius, worked out rather than assumed: a body token alone "
            "gets nothing, because it sits behind the header key. Someone holding "
            "both could file a false receipt into the Thread Log. That is receipt "
            "pollution, not an approval bypass, and it is a long way from what "
            "the header key can do at the write gates. A 2026-09-06 audit raised "
            "these as a security finding alongside the header key, which was an "
            "over-call, and it was withdrawn. Do not raise it again. The copy "
            "worth worrying about is the one stored on each external platform, "
            "under that platform's retention, not the one in the node."
        ),
    },
    "devon-inbox": {
        "job": "iOS and agent captures, text and binary",
        "destination": "Drive, routed by type",
        "workflow": "5s6CwWWelffqszQe",
        "auth": "header x-devon-key",
        "open_ruling": None,
    },
    "devon-approve-request": {
        "job": "raise a high impact action for approval",
        "destination": "n8n data table approval_queue u6wzeN5y9LNxROsN",
        "workflow": "syRVj0G47mA1b0Xn",
        "auth": "header x-devon-key",
        "open_ruling": (
            "POST half first proven live 2026-08-25 by the Soul Committer smoke. "
            "The signed-shift entropy defect recorded here (ids and tokens "
            "embedding the literal text 'undefined', seen live as "
            "REQ-20260825-Jundef) was FIXED in the live workflow on 2026-08-25. "
            "Build Request now uses >>> for all three shifted indexes, and the "
            "workflow's own sticky note warns against changing them back. This "
            "entry still called the fix pending until 2026-08-31."
        ),
    },
    "devon-approve-decide": {
        "job": "approve or refuse a pending action from an email link",
        "destination": "n8n data table approval_queue u6wzeN5y9LNxROsN",
        "workflow": "syRVj0G47mA1b0Xn",
        "auth": "single use token in the link, 72 hour expiry",
        "open_ruling": (
            "Found blank on 2026-09-05 when Tee tapped APPROVE from the phone: the "
            "first tap and every refusal carry a sentinel request id, the Record "
            "Decision update matched no row and emitted nothing, so the Respond "
            "node never ran and the browser got an empty reply (execution 5800). "
            "Every card since the two tap confirm was added on 2026-08-25 was "
            "undecidable from the email. Fixed the same day, version b598e4a3: a "
            "Decided? gate sends valid decisions through Record Decision then the "
            "response, and everything else straight to the response. Write before "
            "answer still holds on the recorded path. Proven with a fake id "
            "(execution 5801, NOT RECORDED page returned). Tee's real confirm "
            "landed at 18:33Z the same day (executions 5802 and 5803, both "
            "success) and the next poll read the card approved and moved job "
            "01M1SAK59GF0511GR7B78Y06A9 to AUTHORIZED (execution 5807). The "
            "door is proven from the phone end to end."
        ),
    },
    "devon-action": {
        "job": "dispatch one AUTHORIZED envelope to an allowlisted executor",
        "destination": "the executor named by the allowlist, spine.echo today",
        "workflow": "ecLqrxALuLDdF2BN",
        "auth": "header x-devon-key",
        "open_ruling": (
            "Repaired 2026-09-05, version c95d7449 and the critic pass after it: a "
            "gate refusal used to be a thrown error, so the webhook answered with "
            "an empty body and the driver logged http 200 null (execution 5810). "
            "A refusal is now data with the reason, intent id, state, action and "
            "the known actions, HTTP 200, and the dispatch branch requires "
            "refused false plus a target url. The allowlist carries spine.echo "
            "with a read ceiling, so an approved reversible_write job parks at "
            "AUTHORIZED with that reason in devon_driver_log until its grant "
            "decays. drive.draft (Drive Draft Writer J7Ly7riwXEd95D9a) joined the "
            "allowlist the same evening at ceiling reversible_write on Tee's ruling, "
            "was quarantined off it hours later by the fourth critic cycle, and was "
            "restored at 20:45Z once the card named the executor and the executor "
            "required a granted grant on every envelope (router version b2a3bf4b). "
            "A refusal the router itself raised never reaches the bus, so the driver "
            "posts the mark: ACTION_FAILED at the same state with state_reason "
            "Parked at AUTHORIZED, once per distinct reason (Tee's ruling, ruling 1)."
        ),
    },
    "devon-drive-draft": {
        "job": "write one Google Doc draft for an AUTHORIZED job and advance it to EXECUTING",
        "destination": "Google Drive, the folder DRAFT_FOLDERS names for the job's Area",
        "workflow": "J7Ly7riwXEd95D9a",
        "auth": "header x-devon-key",
        "open_ruling": (
            "Build 16, created 2026-09-05 on Tee's ruling (do it, then create it). "
            "The first real executor: called only by the Action Router as action "
            "drive.draft at ceiling reversible_write. Checks the grant again, reports "
            "to the bus twice, finds an existing draft by idempotency key before "
            "writing, and refuses as data. Reversible by trashing the document. "
            "Proven live 2026-09-05 19:34Z on job 01M1SAK59GF0511GR7B78Y06A9: "
            "execution 5881 wrote one Google Doc into TQO/01_SCRIPTS and the job "
            "reached verification card REQ-20260905-0Mq1q1. Hardened at 20:35Z "
            "(version 7ff4d7d4) after the fourth critic cycle: a granted, unexpired "
            "approval is required on every envelope whatever the blast radius label "
            "says, a single flight lock refuses a second pass inside ten minutes, "
            "nothing is written unless the ledger took the entry report, and the "
            "created file is read back under its key so the artifact records whether "
            "the idempotency properties persisted."
        ),
    },
    "devon-ledger": {
        "job": "Build 02 state ledger writes, one row per intent",
        "destination": "n8n data table devon_state_ledger VYyno7pDWmY6uxBz",
        "workflow": "z9j2I8h0RnbDKGBO",
        "auth": "header x-devon-key",
        "open_ruling": None,
    },
    "devon-build12-upstream": {
        "job": "start the Build 12 learning gate for a completed source job",
        "destination": "Candidate Former, then conflict-search receipt, then Learning Gate",
        "workflow": "VznESplSFCs8ldph",
        # Flipped from open to header auth 2026-08-26 (the improvement plan's
        # item 4). The feeder was already sending the key, so nothing in the
        # automatic feed changed; an anonymous POST now gets 403 instead of
        # reaching the Candidate Former.
        "auth": "header x-devon-key",
        "open_ruling": None,
    },
    # Build 14, the mouth of the autonomy lane. One POST forms one v1 job
    # envelope at RECEIVED and hands it to the Job Driver in the same call, so
    # the poster gets back where the job stopped. Free text is tagged by
    # Cerebras and every tag is validated against the closed vocabularies:
    # no Area means refused, never guessed; no blast radius defaults to
    # reversible_write, which sends the job to Tee. dry_run returns the
    # envelope without driving it.
    "devon-intake": {
        "job": "form one v1 job envelope from a capture and drive it through the organs",
        "destination": "Job Driver TT4TfFXyH9O7lfdc, then the Build 02 ledger by way of the organs",
        "workflow": "AEFgXee7IDJarNV7",
        "auth": "header x-devon-key",
        "open_ruling": None,
    },
    # Build 15, the Face's door. A public hosted chat is a POST endpoint at
    # /webhook/<id>/chat like any other webhook, so it is registered and
    # audited like one. The auth is n8n login: only a signed-in n8n user can
    # open it, and there is no key to leak.
    "71510ab0-07eb-42d8-9734-c0741b398d49/chat": {
        "job": "the Face: hosted chat where Tee talks to DEVON",
        "destination": "Cerebras, then devon-intake for any job Tee files; memory in devon_chat_log nwnHN8o2dgHjtk7f",
        "workflow": "LsmfRFMmI5feINs0",
        "auth": "n8n user login",
        "open_ruling": None,
    },
}

WEBHOOK_RULE = (
    "One path, one job. Before creating any new webhook, list existing paths and "
    "confirm the name is unused. A path collision does not error, it silently "
    "routes to whichever workflow was published first."
)

# Ruled by Tee 2026-09-05 (ruling 2, rotate and stop saving). Every workflow whose
# webhook takes the x-devon-key header receives that key inside the request headers,
# and a saved successful execution keeps those headers where anyone who can read
# executions can read the key. FIFTEEN webhook paths take the header, not the
# thirteen recorded here until 2026-09-06. Thirteen belong to this lane:
# devon-capture, devon-inbox, devon-approve-request, devon-action,
# devon-drive-draft, devon-ledger, devon-build12-upstream, devon-intake,
# devon-spine-n8n, devon-runtime, devon-route, devon-event and devon-editforge.
# Two more sit outside it and were missed by a count taken from the lane's own
# dependency list rather than from the estate: devon-health (Health and
# Observability Console M3H2mVPZJpDyIzrl, ACTIVE, GET) and devon-capture-file
# (Capture Hook Cbd24ptTPWch3aZO, INACTIVE, so it serves nothing today and would
# the moment it is activated). This count has now been wrong twice, first as
# eleven and then as thirteen, both times by counting the lane instead of the
# estate. Read it from the workflows before trusting it again.
# (devon-approve-decide is the exception that takes no header at all: its auth is
# the single use token in the emailed link. Confirmed 2026-09-06 by reading the
# node, which carries no credential. Rotating this key does not rotate anything
# guarding an approval decision.) The thirteen lane paths live in thirteen
# workflows, since the Approval Queue serves two paths, and all thirteen now run
# with success execution data OFF, as does the Job Driver, which has no webhook
# of its own. devon-health and devon-capture-file were NOT part of that setting
# change and may still save successful executions carrying the header.
# Error executions are still saved, on purpose: a failure with no body is not
# debuggable, and a failed run is the one a human reads. That means the FIRST
# failed run after a rotation writes the new key back into stored run data, so
# this setting reduces the exposure and does not end it. The rotation itself is
# Tee's hands in the n8n UI; KEY_ROTATION names what has to move with it and why
# it is urgent.
KEY_ROTATION = (
    "The key is approval equivalent for a write. Both write gates, the Action "
    "Router and the Drive Draft Writer, read the envelope in front of them and "
    "nothing about the caller, so whoever holds this header value can POST an "
    "AUTHORIZED envelope and cause a Google Doc to be written with no approval "
    "card ever raised. Rotating it is a security act, not housekeeping. "
    "Rotating the shared key (credential Devon Capture Key FYRvkRTOcROEYZ9P) is one "
    "edit in n8n and then every holder outside n8n. Order matters: edit the "
    "credential first, because every organ reads the same credential for both its "
    "own webhook auth and its calls to the other organs, so all fifteen cut over "
    "together and there is no partial state, then update the outside holders, "
    "which are the only places that break. Known holders: the iPhone Shortcut that "
    "posts to devon-capture and devon-inbox, any Apple Routine or automation that "
    "posts to devon-intake, and any saved curl or HTTP client on a laptop. "
    "Two things do NOT break, and a human mid rotation will go looking for them: "
    "pending approval and verification cards keep working, because devon-approve-"
    "decide authenticates a single use token in the emailed link and never reads "
    "the header, and the Face keeps working because it sits behind an n8n user "
    "login. The Soul service token, Cerebras and the Drive OAuth are separate "
    "credentials and are untouched. "
    "No value is stored in this repository, but two environment variable names "
    "would hold it if either were ever set: app/services/knowledge_loop.py reads "
    "N8N_WEBHOOK_KEY and falls back to DEVON_CAPTURE_KEY. Both were read directly "
    "off Railway production on 2026-09-06 and neither is set, so Railway held no "
    "copy at the 2026-09-06 rotation. Check them again before the next one rather "
    "than trusting this line. "
    "The fifteen paths, so a rotator has a checklist rather than a count: "
    "devon-capture, devon-inbox, devon-intake, devon-approve-request, devon-action, "
    "devon-drive-draft, devon-ledger, devon-event, devon-spine-n8n, devon-runtime, "
    "devon-route, devon-editforge, devon-build12-upstream, and the two outside this "
    "lane, devon-health and devon-capture-file. Only eight of those carry an auth "
    "field in the WEBHOOKS map below; the rest are recorded in prose, so working "
    "the map alone covers eight of fifteen and feels finished. The first version of "
    "this checklist, written 2026-09-06, itself said thirteen and omitted the last "
    "two, which is the failure it was written to prevent: it was built from the "
    "lane's dependency list. Rebuild it by reading every workflow's webhook node "
    "and its bound credential, not by counting organs. "
    "After rotating, prove it THREE ways, and the third is the one a rotation "
    "cannot skip. One, post a capture from the phone with the new key: a 401 means "
    "an outside holder was missed. Two, file one level 0 job with blast radius none "
    "and auto_verify, which completes without a card and makes the organs it "
    "touches perform real authenticated calls. Three, POST THE OLD KEY at any "
    "webhook above and require a 401. One and two prove the new key works. Only "
    "three proves the old one is dead, and until it is run, a credential edit that "
    "silently failed to propagate leaves an approval equivalent secret live with "
    "every positive test still passing. "
    "Last rotated 2026-09-06; update this line on the next rotation. Job "
    "01M1TB5RAJHF0FJEN91QMKYYK7 ran RECEIVED to COMPLETED in one pass of six steps "
    "with the Action Router dispatching to the Spine on execution 6069 and no hop "
    "reporting unclean, which exercised the Intake Former, Spine, Runtime, "
    "Intelligence Router, Action Router and Event Bus. That is six of the fifteen "
    "proven by execution. The rest are inferred, but the inference was grounded on "
    "2026-09-06 by reading every webhook node and every organ to organ HTTP node "
    "across twenty two workflows: all of them bind credential FYRvkRTOcROEYZ9P by "
    "id, none binds any of the ten unrelated Header Auth account credentials in the "
    "project, so an in place value edit reaches all of them at once. That is "
    "structure, not behaviour. The behavioural negative test WAS run, by Tee, on "
    "2026-09-06: he posted the old key and got a 401, then deleted the old value. "
    "That is the proof the credential edit propagated and the old secret is dead, "
    "and it is the one proof neither positive test could give. All three proofs of "
    "this rotation are therefore in hand. Note what it cost to get: the runbook did "
    "not ask for it until after the rotation, so for most of a day the estate had "
    "two passing tests and no evidence the old key had stopped working. Ask for the "
    "401 first next time. "
    "Old successful executions saved before "
    "2026-09-05 still carry the previous key in their headers, so rotate rather "
    "than rely on the setting alone, and error executions still store whatever key "
    "was current when a run failed."
)

WORKFLOWS = {
    "iPhone Inbox Capture": {"id": "5s6CwWWelffqszQe", "state": "active"},
    "Capture Webhook": {"id": "pPIt2cELH2RVZktS", "state": "active"},
    "Pipeline Watchdog": {"id": "wndFo6uJCqVuINaV", "state": "active"},
    "Precedence Guard": {"id": "W5rlpAt6hsJAExU6", "state": "active, daily 07:00"},
    "Capture Nudge": {"id": "YHueoBK7TSLdTlfF", "state": "active, daily 08:00"},
    "Soul Layer Write-Back": {"id": "edIJx7Q3FXTawg9J", "state": "active, 15 minute poll"},
    "Approval Queue": {"id": "syRVj0G47mA1b0Xn", "state": "active"},
    "Duplicate Sweep": {"id": "X7OGXWHBx57CIG42", "state": "active"},
    "OS Error Handler": {"id": "rqYmaQh91iCce8DJ", "state": "active"},
    "Live State Ledger": {"id": "z9j2I8h0RnbDKGBO", "state": "active"},
    # Builds 01, 03, 04, 06 and 07, the organs the driver walks a job through.
    # Live since 2026-08-23 and 08-24 but never registered here until 2026-09-05,
    # which the new allowlist test caught: the Action Router dispatches to the
    # Spine and this map did not know the Spine existed. All five run with
    # successful execution data off since Tee's ruling 2 the same day, because
    # their webhooks take the x-devon-key header.
    "Spine Conformance Executor": {"id": "Oi7o1sTEqhxhOaJL", "state": "active, webhook devon-spine-n8n, advances one legal state, successful executions not saved"},
    "Conscious and Subconscious Runtime": {"id": "5Nc9yh6WSqBJ41ok", "state": "active, webhook devon-runtime, UNDERSTANDING to PLANNING, successful executions not saved"},
    "Intelligence Router": {"id": "xh3EkLmgTDJFhzGH", "state": "active, webhook devon-route, PLANNING to AUTHORIZED or WAITING_APPROVAL or ESCALATED, successful executions not saved"},
    "Event Bus": {"id": "Bvy0grTSIyEmPwFA", "state": "active, webhook devon-event, fourteen event types, persists to the ledger, successful executions not saved"},
    "EditForge Handoff": {"id": "OFIhA7zdFv9UoyCv", "state": "active, webhook devon-editforge, EXECUTING only, completed maps to VERIFYING, successful executions not saved"},
    "Build 12 Upstream Test": {"id": "VznESplSFCs8ldph", "state": "active"},
    "Build 12 Ledger Feeder": {"id": "6hQD8YhiYzR1FFda", "state": "active, 15 minute poll"},
    # Sole devon-soul writer, approval gated. First draft Wo7zPxpGH8kiBRy8 was
    # archived unpublished after adversarial review; lANs6wopaK0PkNhN is the
    # rebuild that shipped. Its execution data persistence is off on purpose
    # (approval tokens must not land in stored executions); truth lives in the
    # data tables and digest emails, read via the Table Reader.
    "Soul Committer": {"id": "lANs6wopaK0PkNhN", "state": "active, 15 minute poll"},
    # Found inactive on the live instance 2026-09-01 by the first estate
    # reconcile; recorded active until then, deactivation unrecorded. An n8n
    # error workflow fires when a caller names it whether or not it is
    # active, so the lane likely kept working, but the record was wrong and
    # nobody had said so. Reactivated later the same day on Tee's ruling
    # ("Flip on"): the only version it has ever had (17239190, built
    # 2026-08-25) republished unchanged, read back active.
    "Error Alarm": {"id": "XDQXwgFkUhYxoEjG", "state": "active, shared error workflow, reactivated 2026-09-01"},
    "Learning Lane Table Reader": {"id": "we45pHkQHRmSRnZx", "state": "manual, read only"},
    # Build 13. The 6-hour pulse reads every organ (never approval_queue, whose
    # rows carry plaintext decision tokens), writes one beat row to
    # devon_heartbeat_log (Adg1Gd9HML7Q4L3U), and emails Tee on new findings or
    # roughly daily. Its partner is a claude.ai Routine (daily Reflection) that
    # writes reflection rows into the same table; the pulse flags its silence.
    # Found inactive on the live instance 2026-09-01 by the first estate
    # reconcile; recorded active until then, deactivation unrecorded, so the
    # pulse was dead and nothing watched the organs. Reactivated the same day
    # on Tee's ruling ("Reactivate"): the same version built 2026-08-26
    # (ac7bdf78) was republished unchanged and the read back confirmed
    # active. Who switched it off between 2026-08-31 and 2026-09-01 remains
    # unrecorded.
    "Heartbeat": {"id": "dRgTNLod2s8BAcPg", "state": "active, 6 hour pulse, reactivated 2026-09-01"},
    # Daily sweep: any ledger job still non-terminal past 96h is cancelled
    # THROUGH the guarded devon-ledger webhook, never by writing the table
    # directly, so legal-transition rules keep applying (VERIFYING two-steps
    # FAILED then CANCELLED). Envelope history is preserved plus a janitor
    # trace note. Digest email only when it acted; unreadable envelopes are
    # skipped and named, and the Heartbeat keeps alerting on them
    # (stuck_jobs) until repaired by hand.
    "Ledger Janitor": {"id": "HKNEDVy7PUKPtsrN", "state": "active, daily 02:30"},
    # Weekly read-only export: the four learning-lane tables (state ledger,
    # feed log, soul commit log, heartbeat log) each to CSV, one Gmail with
    # four attachments. approval_queue is EXCLUDED on purpose: its rows carry
    # plaintext decision tokens, and mailing them would let anyone with inbox
    # access approve soul writes. Never add it to this or any export.
    "Weekly Table Backup": {"id": "qCfGZ1CwmpK9vOta", "state": "active, weekly Sun 03:10"},
    # Build 14, the autonomy lane, built and proven live 2026-09-05. Before it
    # the organs existed but nothing formed jobs, walked them between organs,
    # bridged approval cards back into the ledger, observed EditForge, or
    # owned VERIFYING to COMPLETED; every job needed a hand on every hop.
    # The Job Driver is a sub-workflow, never a trigger of its own: one pass
    # advances one job through the organs as far as it legally can (spine,
    # runtime, router, approval card, action, EditForge, verification card)
    # and stops at every human gate. It reads approval_queue only by the
    # evidence marker "intent <id>; card <kind>", copies only request_id,
    # status and timestamps into memory, never the token column, and its
    # execution data persistence is off for the same reason the Soul
    # Committer's is. It writes one row per pass to devon_driver_log
    # (9VbICTCa4x4yhWZm). Proof: a level 0 job with blast radius none ran
    # RECEIVED to COMPLETED in one pass of 14 seconds with no human card
    # (intent 01M1S81K3WDD0JSKY6KPAY43K1). A job with any wider blast radius
    # stops at WAITING_APPROVAL with a card in Tee's inbox and, once executed,
    # at VERIFYING with a second card; COMPLETED is written only after Tee
    # approves that second card, so human_watched is never claimed by a
    # machine. The Driver Poll resumes every open job hourly and emails only
    # when a job moved or an organ refused.
    # Build 05, n8n lane. Dispatches an AUTHORIZED envelope to an allowlisted
    # executor and reports to the bus twice. Zapier lane never built. Refusals
    # answer as data since 2026-09-05; see WEBHOOKS devon-action.
    "Action Router": {"id": "ecLqrxALuLDdF2BN", "state": "active, webhook devon-action, allowlist spine.echo at ceiling read and drive.draft at ceiling reversible_write, successful executions not saved"},
    # Build 16, the first real executor. One Google Doc draft per job, idempotent
    # by key, folder by Area from DRAFT_FOLDERS. See WEBHOOKS devon-drive-draft.
    "Drive Draft Writer": {"id": "J7Ly7riwXEd95D9a", "state": "active, webhook devon-drive-draft, executor drive.draft at ceiling reversible_write, successful executions not saved"},
    "Intake Former": {"id": "AEFgXee7IDJarNV7", "state": "active, webhook devon-intake"},
    "Job Driver": {"id": "TT4TfFXyH9O7lfdc", "state": "active, sub-workflow called by the Intake Former and the Driver Poll"},
    "Driver Poll": {"id": "mbIKJk4UuB7V27rP", "state": "active, hourly poll"},
    # Build 15, the face. n8n hosted chat behind n8n user auth where Tee talks
    # to DEVON from the phone. Cerebras answers with the live ledger, the last
    # driver passes and the last heartbeat in front of it, plus this session's
    # turns from devon_chat_log (nwnHN8o2dgHjtk7f). Status answers cite only
    # measured context. A request to do something is filed through
    # devon-intake, the same door every poster uses, so the same tags, brief,
    # router, cards and ledger apply; an ambiguous ask becomes a dry run and
    # waits for a plain yes. The face never decides a card and never reads
    # approval_queue. The Cerebras credential is header auth, which the chat
    # model subnodes cannot use, so the lane is an HTTP Request, not an Agent.
    "Face": {"id": "LsmfRFMmI5feINs0", "state": "active, hosted chat, n8n user auth"},
    "TQO FINAL V5": {"id": "gsGJQan7a6ZufhYt", "state": "inactive by ruling"},
    "Capture Hook": {"id": "Cbd24ptTPWch3aZO", "state": "retired 2026-08-22"},
}


# ---------------------------------------------------------------------------
# Write permission model
# ---------------------------------------------------------------------------


@dataclass(frozen=True)
class WritePermission:
    """Where a given platform is allowed to write, and why."""

    platform: str
    allowed_folder_id: Optional[str]
    allowed_folder_name: str
    may_write_canon: bool
    naming_pattern: Optional[str] = None
    note: str = ""


# Structure over instruction where both are available. "Write only when directed"
# has no enforcement and fails the moment a session believes it was directed.
# Where a permission can do the work of a policy, take the permission.
PERMISSIONS: Dict[str, WritePermission] = {
    "Claude": WritePermission(
        platform="Claude",
        allowed_folder_id=None,
        allowed_folder_name="the whole vault",
        may_write_canon=True,
        note=(
            "The only platform that writes canon, and only one Claude thread at a "
            "time. Before writing to _Devon Core a thread confirms it holds the "
            "write. If another thread is working canon, hand the edit over rather "
            "than making it. Ruled 2026-08-22 after five forks in two days."
        ),
    ),
    "ChatGPT": WritePermission(
        platform="ChatGPT",
        allowed_folder_id=CAPTURE_INBOX["id"],
        allowed_folder_name=CAPTURE_INBOX["name"],
        may_write_canon=False,
        naming_pattern="CAPTURE_YYYY-MM-DD_chatgpt_topic.md",
    ),
    "Grok": WritePermission(
        platform="Grok",
        allowed_folder_id=CAPTURE_INBOX["id"],
        allowed_folder_name=CAPTURE_INBOX["name"],
        may_write_canon=False,
        naming_pattern="CAPTURE_YYYY-MM-DD_grok_topic.md",
    ),
    "Gemini": WritePermission(
        platform="Gemini",
        allowed_folder_id=CAPTURE_INBOX["id"],
        allowed_folder_name=CAPTURE_INBOX["name"],
        may_write_canon=False,
        naming_pattern="CAPTURE_YYYY-MM-DD_gemini_topic.md",
    ),
}


def may_write(platform: str, destination_folder_id: str) -> Tuple[bool, str]:
    """Answer whether a platform may write to a destination, with the reason."""
    permission = PERMISSIONS.get(platform)
    if permission is None:
        return False, (
            f"'{platform}' has no recorded write permission. Unknown platforms write "
            f"nowhere. Known: {', '.join(PERMISSIONS)}."
        )
    if destination_folder_id == FOLDERS["_Devon Core"] and not permission.may_write_canon:
        return False, (
            f"{platform} may not write to _Devon Core. Canon has one writer. "
            f"Write to {permission.allowed_folder_name} instead."
        )
    if permission.allowed_folder_id is None:
        return True, f"{platform} may write across the vault."
    if destination_folder_id != permission.allowed_folder_id:
        return False, (
            f"{platform} may write only to {permission.allowed_folder_name} "
            f"({permission.allowed_folder_id})."
        )
    return True, f"{platform} writing to its permitted capture folder."


def area_folder(area_label: str) -> Optional[str]:
    """Drive folder id for an Area label, or None when the Area has no tree yet."""
    return AREA_FOLDERS.get(area_label)


def doctrine_id(name: str) -> Optional[str]:
    """Drive id for a doctrine document by short name."""
    entry = DOCTRINE.get(name)
    return entry["id"] if entry else None


# Routing for inbound captures, mirroring the live iPhone Inbox Capture workflow.
# Unknown types are parked in 0. Inbox with a warning, never guessed at.
CAPTURE_ROUTING: Dict[str, str] = {
    "notes": "3. Resources / iPhone Notes",
    "pdf": "3. Resources / Documents",
    "doc": "3. Resources / Documents",
    "docx": "3. Resources / Documents",
    "txt": "3. Resources / Documents",
    "md": "3. Resources / Documents",
    "rtf": "3. Resources / Documents",
    "epub": "3. Resources / Documents",
    "jpg": "3. Resources / Images",
    "jpeg": "3. Resources / Images",
    "png": "3. Resources / Images",
    "heic": "3. Resources / Images",
    "gif": "3. Resources / Images",
    "webp": "3. Resources / Images",
    "svg": "3. Resources / Images",
    "mp4": "3. Resources / Media",
    "mov": "3. Resources / Media",
    "m4a": "3. Resources / Media",
    "mp3": "3. Resources / Media",
    "wav": "3. Resources / Media",
    "csv": "3. Resources / Data",
    "xlsx": "3. Resources / Data",
    "json": "3. Resources / Data",
    "xml": "3. Resources / Data",
    "zip": "4. Archive / iPhone Downloads",
    "dmg": "4. Archive / iPhone Downloads",
    "7z": "4. Archive / iPhone Downloads",
}

UNROUTED_DESTINATION = "0. Inbox"


def route_capture(extension: str) -> Tuple[str, bool]:
    """Destination for a captured file by extension, and whether it was recognised.

    An unrecognised type parks in 0. Inbox with the flag set false, so the caller
    warns rather than filing it somewhere plausible.
    """
    key = (extension or "").lower().lstrip(".")
    destination = CAPTURE_ROUTING.get(key)
    if destination is None:
        return UNROUTED_DESTINATION, False
    return destination, True
