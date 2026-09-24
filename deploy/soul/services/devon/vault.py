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

# The one home for bot research, created 2026-09-24 under 3. Resources on
# Tee's ruling that Thoth's archive lives in the vault. Written only by the
# n8n workflow DEVON - Bot Research Filer (jbDzwMVQDkEvkEM3), which creates
# AREA_SOURCE_slug_vN_YYYY-MM-DD.md files, refuses a duplicate slug, and moves
# a superseded piece to 4. Archive as SUPERSEDED_. It never deletes or shares.
RESEARCH_FOLDER = {
    "name": "3. Resources/Research",
    "id": "1Y0Dp4WsrxgFRbLMEIKP6vlmhYeaIlxJb",
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

# Where DEVON's airtable.row executor (Build 17) may write a row, by table. The
# executor (n8n/devon/airtable-row-writer/validate_and_plan.js) carries the same
# map inline because n8n cannot import this file; test_devon_integrity pins the
# two together. Every table here carries the two stamp fields the executor writes
# on every row and reads back before writing again: DEVON key holds the job's
# idempotency key, DEVON job holds the intent id. Both were created on Inbox
# Captures on 2026-09-06 (fldvp5UiTnGhRunAs, fldM2r96swSZsxH8x). The base is
# AIRTABLE["live_base"]. Adding a table or a field is a deliberate act: create the
# two stamp fields on the table first, then change this map and the executor in
# the same change.
AIRTABLE_ROW_TABLES = {
    "Inbox Captures": {
        "id": "tbl4ziFRbl5mnUcKc",
        "key_field": "DEVON key",
        "job_field": "DEVON job",
        "writable": ("Title", "Captured", "Kind", "Source", "Area", "Body", "Notes"),
    },
}

# The training log for a local tag classifier, ruled by Tee 2026-09-23. Written
# on Inbox Captures by iPhone Inbox Capture at capture time. tagged_area is the
# machine's answer and is never edited; label is the field Tee corrects; a row
# counts as a training label only once confirmed is ticked. Train at about 300
# confirmed rows, not before. Triaged belongs to the Duplicate Sweep and is not
# part of this log.
INBOX_TAG_LOG = {
    "table": "tbl4ziFRbl5mnUcKc",
    "tagged_area": "fldUOQIkF333gwofd",
    "tag_source": "fld2m30zLSF7O0iOm",
    "tag_sources": ("cerebras", "keyword", "none"),
    "label": "fldpbMPz2xBcEo0Ia",
    "confirmed": "fldq7Mr38uyGFbnpG",
    "train_at": 300,
}

# Which tools DEVON's zapier.mcp executor (Build 19) may call on the Zapier MCP
# server, each with the blast radius it really has. The executor
# (n8n/devon/zapier-executor/validate_and_plan.js) carries the same map inline
# because n8n cannot import this file; test_devon_integrity pins the two
# together. The executor's ceiling is reversible_write, so a tool that sends,
# posts or deletes cannot be added here without raising that ceiling, which is a
# ruling for Tee. Adding a tool is a deliberate act: attach the action to the
# server in Zapier, then change this map and the executor in the same change.
ZAPIER_MCP_TOOLS = {
    "get_configuration_url": {
        "blast_radius": "read",
        "description": "Returns the URL where the Zapier MCP server is configured. Read only; the proof tool for the lane.",
    },
}


# ---------------------------------------------------------------------------
# n8n
# ---------------------------------------------------------------------------

# Ruled by Tee 2026-09-15: every DEVON organ runs on the VPS, live and published.
# The Cloud instance (thequietoperator.app.n8n.cloud) was the host from the first
# build until that evening; every workflow id and webhook path below is the VPS
# copy's, rebuilt from the Cloud live version that night, and the Cloud copies
# are unpublished. History inside open_ruling strings still names Cloud ids and
# Cloud execution numbers, because that is where those things happened.
N8N_HOST = "https://n8n.editforge.online"

WEBHOOKS = {
    "devon-capture": {
        "job": "cross platform receipts",
        "destination": "Airtable Thread Receipts tblEhgEZoNr2ztbB3",
        "workflow": "Me7DDHBDX28ppvHA",
        # Stays the single checkable phrase. node_auth_for() in the reconciler
        # matches by PREFIX, so any second clause added here is silently
        # discarded. The second layer has its own field and its own checker.
        "auth": "header x-devon-key",
        # The body token gate, checked by the estate reconciler since 2026-09-06
        # (verifier body_gate). It pins a fingerprint of the Check Token node's
        # code rather than the node's presence, because presence is not the
        # gate: the switch is `const LEGACY_GRACE = false;` inside the code, and
        # flipping it reopens the door with the node still there and enabled.
        # Any edit, the grace switch flipped or a single rotated poster token
        # alike, changes the fingerprint and reports DRIFT until a human
        # re-reads the node and re-pins it dated. A rewiring bypass changes no
        # byte of the node, so since the second pass of 2026-09-06 the snapshot
        # also records whether the door feeds Check Token and nothing else, and
        # a trigger wired past it reports DRIFT the same way. The snapshot
        # records only the hash and the wiring, never the code, so obs.json is
        # not a fifth copy of the four tokens.
        # Fingerprint provenance: sha256 over the jsCode with line endings and
        # trailing whitespace normalised (code_fingerprint in the reconciler),
        # taken 2026-09-06 from two independent transcriptions of the MCP read
        # that agreed. The first keyed `snapshot` run is the authoritative
        # confirmation; if it reports DRIFT with the node unchanged, re-pin
        # from that read and note it here.
        "body_gate": {
            "node": "Check Token",
            "type": "n8n-nodes-base.code",
            "sha256": "74fdf22a12cee9c8fede22e02061b82d8348b6cf48ae4ba115d7ae6cae7a38e9",
            "pinned": "2026-09-06",
        },
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
        "workflow": "CEy7WAl4QAzHfG46",
        "auth": "header x-devon-key",
        "open_ruling": None,
    },
    # Registered 2026-09-06 with its workflow. The one GET door in the estate;
    # it reads the ledger and writes nothing.
    "devon-health": {
        "job": "organism health from the ledger: open against terminal, stuck jobs, failure concentration",
        "destination": "the caller, as JSON; nothing is written",
        "workflow": "bsxKtdx1ebMu5hGs",
        "auth": "header x-devon-key",
        "open_ruling": None,
    },
    "devon-approve-request": {
        "job": "raise a high impact action for approval",
        "destination": "n8n data table approval_queue u6wzeN5y9LNxROsN",
        "workflow": "Ia28EHrxtiI8cjeA",
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
        "workflow": "Ia28EHrxtiI8cjeA",
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
        "workflow": "NYcEp03Oqlvq86Mb",
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
        "workflow": "FdQgiX2Thgk38CSa",
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
    "devon-airtable-row": {
        "job": "write one row into an allowlisted Airtable table for an AUTHORIZED job and advance it to EXECUTING",
        "destination": "Airtable base AIRTABLE live_base, the tables AIRTABLE_ROW_TABLES names (Inbox Captures today)",
        "workflow": "glEO2xa4IZmHDbkg",
        "auth": "header x-devon-key",
        "open_ruling": (
            "Build 17, created 2026-09-06 on Tee's ruling (the third executor, first "
            "of the three builds in the recommended order). The second real executor: "
            "called only by the Action Router as action airtable.row at ceiling "
            "reversible_write, and bound by the Job Driver only when the job carries a "
            "structural intent.payload.airtable (table and fields), never from words "
            "in the summary. Same gates as the Drive Draft Writer: a granted, unexpired "
            "approval on every envelope, the single flight lock in the entry report, "
            "nothing written unless the ledger took that report, an existing row found "
            "by DEVON key and DEVON job before writing, the created record read back so "
            "the artifact records key_verified, refusals as data. Never sends typecast, "
            "so an option that does not exist on a select field is refused by Airtable "
            "and the job parks with that reason. Reversible by deleting the row. The "
            "Intake Former passes payload.airtable through since the same day; before "
            "that edit the executor was unreachable from any poster. Live proof, "
            "2026-09-06: Tee approved card REQ-20260906-8kt8Vj at 11:32:16Z; Driver "
            "Poll run 6200, driver pass 6202, executor execution 6208 wrote "
            "recKhlOqdAG0Zju30 into Inbox Captures under DEVON key "
            "build17-proof-20260906-airtable-row for job 01M1V6M3XG0RQR191QFF7W74WJ, "
            "artifact key_verified true, both stamps read back directly from Airtable; "
            "verification card REQ-20260906-vED3ik approved by Tee at 12:04:12Z and "
            "the job closed COMPLETED by driver pass 6238 (poll run 6236) at 12:08:11Z "
            "with human_watched true: the lane has run end to end on a real job once. "
            "Hardened the same hour on a fresh critic's findings (version "
            "486c243d): a Write? guard so a Check Existing refusal answers as data "
            "instead of throwing (pinned 6224, 6225, 6226), whitespace refused in the "
            "key rather than collapsed, and a date must be a calendar date that "
            "exists. The single flight mark is best effort and this entry said lock "
            "until then: the mark lives in the ledger row and a router failure exit "
            "rewrites it away; the Driver Poll's three minute skip and the search by "
            "both stamp fields are what prevent a second row."
        ),
    },
    "devon-zapier-mcp": {
        "job": "call one allowlisted tool on the Zapier MCP server for an AUTHORIZED job and advance it to EXECUTING",
        "destination": "the Zapier MCP server at mcp.zapier.com, the tools ZAPIER_MCP_TOOLS names (get_configuration_url today)",
        "workflow": "MIELNCkP9IyHWVlr",
        "auth": "header x-devon-key",
        "open_ruling": (
            "Build 19, created 2026-09-15 on Tee's rulings (wire the Zapier MCP as the "
            "executor; then everything on the VPS, live and published). The third real "
            "executor: called only by the Action Router as action zapier.mcp at ceiling "
            "reversible_write, and bound by the Job Driver only when the job carries a "
            "structural intent.payload.zapier (tool and arguments), never from words in "
            "the summary. Same gates as the Airtable Row Writer: a granted, unexpired "
            "approval on every envelope, the single flight lock in the entry report, "
            "nothing called unless the ledger took that report, refusals as data. Owns "
            "its idempotency in devon_zapier_call_log: a call that succeeded under this "
            "key, intent id and payload fingerprint is reused, a call in flight or with "
            "an unreadable outcome is refused, and a write whose outcome could not be "
            "read is never retried by a machine. Reaches Zapier by JSON-RPC over "
            "Streamable HTTP on the Zapier MCP credential by id: initialize opens a "
            "session, one tools/call runs the tool, the session is dropped. The tool "
            "allowlist carries each tool's real blast radius under the executor "
            "ceiling; the Zapier server exposed only get_configuration_url until Tee "
            "attached actions to it, so that read is the proof tool. Proven offline on "
            "2026-09-15 by a 49 case harness over the node bodies and a 7 case harness "
            "proving the driver's card fingerprint equals the executor's; the live proof "
            "on a real job is recorded in the status doc of the cutover night."
        ),
    },
    "devon-ledger": {
        "job": "Build 02 state ledger writes, one row per intent",
        "destination": "n8n data table devon_state_ledger VYyno7pDWmY6uxBz",
        "workflow": "hDmTRI5VAZ3a8sTn",
        "auth": "header x-devon-key",
        "open_ruling": None,
    },
    "devon-build12-upstream": {
        "job": "start the Build 12 learning gate for a completed source job",
        "destination": "Candidate Former, then conflict-search receipt, then Learning Gate",
        "workflow": "VzJsSlDswkIJ9wok",
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
        "workflow": "TciVQhWJA0y92x9P",
        "auth": "header x-devon-key",
        "open_ruling": None,
    },
    # Ruled by Tee 2026-09-08 after his phone timed out twice against
    # api.gumroad.com while n8n reached it in half a second: the Gumroad sale
    # check moved off the phone when he repointed the Shortcut to this door on
    # 2026-09-08 (proved from the phone at 13:58 UTC). The
    # token stays in n8n credential K1D8KUvTcWDcdrV0; the caller sends only
    # x-devon-key and a sale_id, and Preflight refuses an implausible id before
    # any request leaves. Proved on executions 6482 (a made-up id: Gumroad
    # answered 200 with success false, the door answered 404) and 6483 (an
    # implausible id: refused 400, no request made), both manual with the body
    # pinned; 6489 and 6490 (pinned Gumroad replies) proved the empty-sale 502
    # and the found-sale 200; probe execution 6494 (a throwaway workflow,
    # archived after its one run) hit the production door twice, 404 with the
    # key and 403 without, so the header check is proved from outside. It
    # reads and writes nothing; it is one more key holder. Since about 14:55
    # UTC the same door also answers {"job": "list"}: the last five sales from
    # GET /v2/sales with no buyer fields, ruled the same day, proved on
    # executions 6501 to 6507.
    "devon-gumroad-sale-check": {
        "job": "read one Gumroad sale back from GET /v2/sales/:id, or the last five sales from GET /v2/sales with no buyer fields, for Tee's phone",
        "destination": "api.gumroad.com through credential K1D8KUvTcWDcdrV0, answered to the caller, nothing written",
        "workflow": "e5H3pk7YNF9jQi1r",
        "auth": "header x-devon-key",
        "open_ruling": None,
    },
    # Build 15, the Face's door. A public hosted chat is a POST endpoint at
    # /webhook/<id>/chat like any other webhook, so it is registered and
    # audited like one. The auth is n8n login: only a signed-in n8n user can
    # open it, and there is no key to leak.
    # The id in this path is the chat trigger's own webhookId, so it is
    # instance specific and did not survive the move. Cloud served
    # 71510ab0-07eb-42d8-9734-c0741b398d49/chat; the VPS copy carries its own
    # from the 2026-08-31 export and kept it through the rebuild, so the live
    # door is the one below. Found by estate_reconcile after the 2026-09-15
    # cutover, which is the only reason anyone noticed: the repointing pass
    # rewrote workflow and webhook id FIELDS and could not see an id embedded
    # in a path string.
    "bf371d93-da93-4e81-b50b-4ffe988aeae5/chat": {
        "job": "the Face: hosted chat where Tee talks to DEVON",
        "destination": "Cerebras, then devon-intake for any job Tee files; memory in devon_chat_log nwnHN8o2dgHjtk7f",
        "workflow": "sPv6Cq7elbjoi5Nw",
        "auth": "n8n user login",
        "open_ruling": None,
    },
    # Registered 2026-09-16 in the same change that created it, per the house
    # rule. Built INACTIVE and it stays that way until Tee publishes it, so it
    # serves nothing today and would the moment it is activated, exactly like
    # devon-capture-file. The path was confirmed unused by listing all 62
    # workflows on the VPS before creation.
    "devon-vision": {
        "job": "describe ONE image and answer in the HTTP response; files nothing",
        "destination": "the caller, plus one row per attempt in n8n data table devon_vision_log lapnGsgr33wcX0Ef",
        "workflow": "WjSNXSsGP8ZCxXMa",
        "auth": "header x-devon-key",
        "open_ruling": (
            "PUBLISHED and proven 2026-09-16, and the lane is correct while no "
            "account behind it can pay. Guarded from outside: a POST with no "
            "x-devon-key answered 403. Proven end to end by three live runs, "
            "each a different provider failure answered as data with the "
            "provider's own words and logged: execution 255, z-ai/glm-5.2:free, "
            "404 'No endpoints found that support image input', so that model "
            "reads no images; execution 257, google/gemma-4-31b-it:free, 404 "
            "zdr-violation-by-account, because the OpenRouter account enforces "
            "Zero Data Retention and the free endpoints cannot meet it; "
            "execution 258, openai/gpt-5-nano, 402 'Insufficient credits. This "
            "account never purchased credits.' So the OpenRouter account is "
            "unfunded, which is the same trap the 2026-09-16c doc recorded for "
            "the Anthropic account, and which does NOT block this lane because a "
            "free endpoint carries it. Corrected the same day: this entry first "
            "read the gemma refusal as ZDR excluding free endpoints as a CLASS. "
            "That was one sample and it was wrong. Eligibility is per endpoint, "
            "and inclusionai/ling-3.0-flash-vl:free clears the guardrail and "
            "answers at cost 0 in about two and a half seconds, proven by "
            "executions 262 and 263, the second sending only an image and taking "
            "the default model and prompt. It is now the lane default. "
            "the Anthropic account. Credential Wan5EWMeQiyrFOuY is bound and "
            "authenticates; the routing metadata in those errors is the proof. "
            "The model id was chosen from the live catalogue, never invented: "
            "443 models, 272 accept image input, 10 of those free. "
            "Tee ruled on 2026-09-16 to host a local model on the VPS instead "
            "of funding a provider. HARDWARE.md section 5 refuses that shape in "
            "general terms, no GPU and inference is a provider's problem, so "
            "the ruling overrides a written standard and the objection is "
            "logged here once. The VPS capacity is UNMEASURED: the Execute "
            "Command node is not available on this n8n instance, so no session "
            "here can read the box. Tee or anyone with shell can, with nproc, "
            "free -m and df -h; Tee read it off the host on 2026-09-16 and it is "
            "2 cores, 7940 MB memory and 96 GB disk with no GPU. Two cores is the "
            "blocker rather than memory, so the ruling is UNEXECUTED: a local model "
            "cannot answer inside the 60 second Describe Image timeout without "
            "starving the 62 workflow estate that shares the host. Going local "
            "would also move the endpoint, since "
            "Describe Image posts to openrouter.ai and a local server is a "
            "different URL, so that is one edit beside the model id."
        ),
    },
    "devon-hears": {
        "job": "one voice note in, what DEVON understood back; does none of it",
        "destination": "the caller, as JSON, plus one row per turn in n8n data table devon_hearing_log Tht7qGrqF66E48EA",
        "workflow": "6KGsMrVCVJe2nYnE",
        "auth": "header x-devon-key",
        "open_ruling": (
            "BUILT 2026-09-16, deliberately inactive that day, and ACTIVE when "
            "the estate was read on 2026-09-17. Item 1 of the ears "
            "build, ruled by Tee on an inline card that same day: a purpose "
            "built door rather than an extension of devon-inbox, and a read "
            "only service parse rather than a lane that logs in as him each "
            "run. "
            "BOTH HALVES OF THE KEY ARE NOW IN PLACE, checked rather than "
            "taken on report. DEVON_SERVICE_KEY appears in the Railway api "
            "service's variable names, and the credential lQOq0PEHosCWqkV1, "
            "httpHeaderAuth, named DEVON_SERVICE_KEY, is attached to Ask What "
            "DEVON Heard. That second step was NOT automatic: n8n skips "
            "credential assignment for HTTP Request nodes, and a credential "
            "existing in the store does not attach it to a node. A read back "
            "after Tee created it showed the node carrying no credentials key "
            "at all, so the lane would have called the door bare and taken a "
            "401. Creating and attaching are two separate actions; check the "
            "node, never the credential list. "
            "The key must be at least 24 characters or the door refuses it the "
            "same way it refuses an unset one; secrets.token_urlsafe(32) gives "
            "43. The node briefly asked for httpTemplatedCustomAuth, which was "
            "wrong and is corrected. The SDK validator refuses to CREATE a new "
            "httpHeaderAuth credential from workflow code and steers to the "
            "templated type, but that is a builder constraint, not a runtime "
            "one. A credential made by hand in the UI has no such limit, and "
            "the validator's own warning says plain generic types are for "
            "reusing an existing credential, which is exactly this path. "
            "THE ENDPOINT IS DEPLOYED, measured on 2026-09-17 rather than "
            "inferred from a merge. An unkeyed POST to "
            "api-production-5644.up.railway.app/api/v1/devon/hear answers 401 "
            "'Invalid or missing service key.', and a made up sibling path "
            "answers 404 'Not Found', so the 401 is this route refusing a "
            "bare caller rather than a catch all. This paragraph read WHAT IS "
            "STILL MISSING IS THE ENDPOINT until then, which was true the day "
            "it was written and stale from the moment PR #252 deployed. "
            "The credential "
            "value itself is unreadable from here, so that the two sides carry "
            "the SAME string is STILL unproven, and manual executions cannot "
            "prove it: manual mode never checks the webhook header. "
            "WHAT THE DOOR CANNOT DO IS STRUCTURAL, NOT A FLAG. It calls "
            "parse, a pure function in the effect free services/devon package, "
            "and never Devon.ask, which is the thing that gates an intent and "
            "raises an approval card. So a spoken EFFECT comes back refused "
            "with its payload blanked rather than queued, and a machine cannot "
            "fill the approval rail with cards nobody spoke for. "
            "test_devon_hear_door.py proves it twice, once by replacing the "
            "gate with a landmine and once by reading the route's own AST, and "
            "both halves were shown failing on a mutation that reintroduced "
            "the call. "
            "THE LANE COULD NOT TRANSCRIBE ANYTHING UNTIL 2026-09-17, and "
            "nothing in the estate knew. Is There Audio To Hear gated on "
            "$binary.data.fileSize, and n8n's fileSize is a HUMAN READABLE "
            "STRING, '38.4 kB'. A number comparison against it does not "
            "answer false, it THROWS: 'Conversion error: the string 38.4 kB "
            "can't be converted to a number'. The run died at node 2 and the "
            "caller got an EMPTY BODY, no status and no reason. typeValidation "
            "loose did not help; the failing node resolved "
            "looseTypeValidation false. The number is on .bytes, 38444, and "
            "the gate reads that now. "
            "WHY IT SURVIVED A BUILD, A MERGE AND A STATUS DOC: the guard and "
            "the guarded path are different code. Every execution ever run "
            "carried NO audio, and that path never reaches the comparison, "
            "because no binary makes the ternary yield a real 0 and 0 > 0 is "
            "an honest false. Testing the refusal proved nothing about the "
            "only case that matters. Measured on a throwaway copy of the same "
            "node over the live webhook: fileSize throws on wav and on m4a, "
            "bytes answers true on both, the no audio refusal is unchanged "
            "either way, and multipart lands on data0 rather than data so it "
            "refuses as if nothing arrived. Post the note as a RAW body. "
            "STILL NOT PROVEN: no AUDIO has been "
            "through this lane. Executions 288 and 335, both success and BOTH "
            "IN MANUAL MODE, plus 390 after the fix, so the "
            "production webhook has never taken a request. 335 and 390 "
            "routed a request carrying no audio to Refuse Before Spending "
            "without reaching the transcriber, which proves that refusal on "
            "the real lane rather than on a copy. ElevenLabs has still never "
            "been called from it. "
            "The transcription model is left unset on purpose because that "
            "node's model picker lists synthesis models only, measured against "
            "the live credential on 2026-09-16. What remains is one keyed POST "
            "carrying audio to the production URL, and that needs Tee's key "
            "from his phone. "
            "THE LOG RESOLVES BY ID. devon_hearing_log is Tht7qGrqF66E48EA and "
            "Log The Turn addresses it in id mode, never by name, because a "
            "name is capturable by any other table name that contains it. The "
            "collision check was run before the table was created and reported "
            "53 names with no containment collisions. The row is written "
            "BEFORE the caller is answered, so the record exists before the "
            "claim does, and a confidence the transcriber did not report is "
            "stored as null rather than as a zero that would read as "
            "certainty. Answer The Phone reads Read The Status Back explicitly "
            "rather than $json, because a write node outputs its own API "
            "response and chaining the insert in front of the responder would "
            "have answered the caller with a row id instead of the result."
        ),
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
# executions can read the key. EIGHTEEN webhook paths take the header as of
# 2026-09-16, when devon-vision was registered. That eighteenth was
# INCREMENTED from the recorded seventeen, NOT recounted from the estate, and
# CLAUDE.md records this exact count being wrong twice in the same direction
# for exactly that reason: recount it from the workflows before trusting it.
# devon-vision is also INACTIVE, so it holds the key without serving anything
# until it is published. Seventeen as of
# 2026-09-15, when Build 19 added devon-zapier-mcp (sixteen as of
# 2026-09-06, when Build 17 added devon-airtable-row (fifteen earlier that day,
# and thirteen recorded here until the same morning). Fourteen belong to this
# lane: devon-capture, devon-inbox, devon-approve-request, devon-action,
# devon-drive-draft, devon-airtable-row, devon-ledger, devon-build12-upstream,
# devon-intake, devon-spine-n8n, devon-runtime, devon-route, devon-event and
# devon-editforge.
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
# guarding an approval decision.) The fourteen lane paths live in fourteen
# workflows, since the Approval Queue serves two paths, and all fourteen now run
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
    "The key is approval equivalent for a write. The four write gates, the Action "
    "Router, the Drive Draft Writer, the Airtable Row Writer and the Zapier Executor, read the envelope "
    "in front of them and nothing about the caller, so whoever holds this header "
    "value can POST an AUTHORIZED envelope and cause a Google Doc or an Airtable "
    "row to be written with no approval card ever raised. Rotating it is a security act, not housekeeping. "
    "Rotating the shared key (credential Devon Capture Key FYRvkRTOcROEYZ9P) is one "
    "edit in n8n and then every holder outside n8n. Order matters: edit the "
    "credential first, because every organ reads the same credential for both its "
    "own webhook auth and its calls to the other organs, so all sixteen cut over "
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
    "The twenty-one paths, so a rotator has a checklist rather than a count: "
    "devon-capture, devon-inbox, devon-intake, devon-approve-request, devon-action, "
    "devon-drive-draft, devon-airtable-row, devon-ledger, devon-event, "
    "devon-spine-n8n, devon-runtime, devon-route, devon-editforge, "
    "devon-build12-upstream, and the two outside this lane, devon-health and "
    "devon-capture-file. Four more joined on 2026-09-07 when TQO FINAL V5 "
    "(gsGJQan7a6ZufhYt) had auth put on its webhooks, which until then had none at "
    "all: run-tqo-pipeline, run-nco-pipeline, system-pause and system-resume. A "
    "twenty-first joined on 2026-09-08: devon-gumroad-sale-check (7bDqKNdMHY8sxoXa), "
    "the sale check Tee's phone could not make directly, ruled the same day. "
    "This number moved twice in one day and the second move is the instructive "
    "one. It went sixteen to twenty-three when all seven V5 webhooks were put on "
    "the header, then back to twenty when Tee ruled the three callers that cannot "
    "physically send a header onto unguessable paths instead. Those three are NOT "
    "key holders and a key rotation does not touch them; they have their own "
    "rotation, which is changing the path, and they are listed under SECRET PATH "
    "WEBHOOKS below. Counting doors and counting key holders are different "
    "questions and this line answers only the second. That workflow was published "
    "2026-09-08, so these four doors are live and a rotation proves them from the "
    "outside like the rest. Eleven of the twenty-one carry an auth field in the WEBHOOKS map "
    "below (eight until devon-health was registered on 2026-09-06, nine until "
    "devon-airtable-row was added later that day, ten until devon-gumroad-sale-check "
    "on 2026-09-08); the rest are recorded in "
    "prose, so working the map alone covers eleven of twenty-one and feels finished. The first version of "
    "this checklist, written 2026-09-06, itself said thirteen and omitted the last "
    "two, which is the failure it was written to prevent: it was built from the "
    "lane's dependency list. The 2026-09-07 jump from sixteen to twenty-three is "
    "the same class of drift caught early: adding auth to a workflow adds holders "
    "of the key, and the checklist has to move with it. Rebuild it by reading every "
    "workflow's webhook node and its bound credential, not by counting organs. "
    "SECRET PATH WEBHOOKS, which are doors but not key holders: TQO FINAL V5 "
    "carries three whose whole protection is an unguessable path, because the "
    "caller cannot send a header. Two run links tapped from Tee's phone and the "
    "Gumroad sale ping. Their paths are run-tqo-<16 hex, elided>, "
    "run-nco-<16 hex, elided> and gumroad-sale-<16 hex, elided>, elided here "
    "because this repository is public, exactly as devon-soul-setup already is. "
    "The live values are in the workflow itself and nowhere in git. Rotating one "
    "means editing the path and repointing its caller, not touching any "
    "credential. The Gumroad one is the door most worth attacking, because "
    "Gumroad signs nothing, so a leaked URL is a forged sale. Since 2026-09-08 "
    "the branch behind it no longer trusts the ping at all. Gumroad: Preflight "
    "Ping refuses a ping whose sale_id is absent or not a plausible id, and "
    "Gumroad: Verify Sale reads the sale back from GET /v2/sales/:id before "
    "Gumroad: Normalise Sale records anything, taking every value from that "
    "response rather than from the ping. The credential is the proof, since "
    "that endpoint is scoped to the token own account. That adds a SECOND "
    "secret to the estate, a Gumroad API token held as an n8n credential, and "
    "it is NOT one of the twenty-one above: it rotates on its own monthly cadence, "
    "ruled 2026-09-08 and filed in the Credentials registry, not with x-devon-key, "
    "and the twenty-one count only x-devon-key holders. Do not "
    "let it inflate that number, which has already been wrong twice. The first "
    "design of this guard compared seller_id against $env.GUMROAD_SELLER_ID "
    "and could never have worked, because this instance is n8n Cloud, which "
    "has no environment to set and blocks $env inside Code nodes. Execution "
    "6398 measured that rather than assuming it. "
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
    "Intelligence Router, Action Router and Event Bus. That is six of the sixteen "
    "proven by execution. The rest are inferred, but the inference was grounded on "
    "2026-09-06 by reading every webhook node and every organ to organ HTTP node "
    "across twenty two workflows: all of them bind credential FYRvkRTOcROEYZ9P by "
    "id, none binds any of the ten unrelated Header Auth account credentials in the "
    "project, so an in place value edit reaches all of them at once. The Airtable "
    "Row Writer, added after that read, binds the same credential by id on its "
    "door and its two bus reports, read back on 2026-09-06 after creation. That is "
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
    # Since 2026-09-23 (active version 881a2a3c) Index Capture also writes the
    # tag decision log: Tagged Area and Tag Source, next to the Area Tee
    # corrects. See INBOX_TAG_LOG above.
    "iPhone Inbox Capture": {"id": "CEy7WAl4QAzHfG46", "state": "active"},
    # Built 2026-09-16. This comment said inactive, with an undeployed endpoint
    # and an empty credential, and every part of that had stopped being true by
    # 2026-09-17. Read from the estate rather than from the record: active is
    # true, executions 288 and 335 both succeeded, and an unkeyed POST to the
    # door answers 401 where a missing route answers 404. Both executions ran
    # in MANUAL mode, so the production webhook has still never taken a
    # request. See the devon-hears entry in WEBHOOKS for the measurements and
    # for what the door structurally cannot do.
    "DEVON Hears": {
        "id": "6KGsMrVCVJe2nYnE",
        "state": "active, audio gate fixed 2026-09-17, no production webhook request yet",
    },
    "Capture Webhook": {"id": "Me7DDHBDX28ppvHA", "state": "active"},
    "Pipeline Watchdog": {"id": "IZBVlXQ8Y5dsGTRS", "state": "active, every 4h, timezone pinned America/New_York 2026-09-07"},
    "Precedence Guard": {"id": "4BXO9CX8MdYYyGMq", "state": "active, daily 07:00 America/New_York, timezone pinned 2026-09-07"},
    "Capture Nudge": {"id": "3B8pGfSklJMte3ut", "state": "active, daily 08:00 America/New_York, timezone pinned 2026-09-07"},
    "Soul Layer Write-Back": {"id": "rZdhFXcsOyBcEkgR", "state": "active, 15 minute poll"},
    "Approval Queue": {"id": "Ia28EHrxtiI8cjeA", "state": "active"},
    "Duplicate Sweep": {"id": "3tY1sJF3brpvdkgi", "state": "active"},
    "OS Error Handler": {"id": "GbeNilHQzjmoWDz3", "state": "active"},
    # Switched on 2026-09-08 by Tee's ruling, after the prune found a policy
    # sensor sitting inactive, which his own rules make an exception path for a
    # compliance item. Its cron was implicit and was pinned the same day.
    # Coverage was FOUR of eight for most of that night, was called eight of
    # eight by the v1 doc, and one of those eight was hollow: Meta Content
    # Monetization captured three policy sections as heading plus lead-in and
    # nothing, fixed the same night with a Firecrawl custom body, see the v2
    # doc. Nine watched since the X successor row was added. The history
    # matters more than the number. The first sweep,
    # execution 6401, reported success and recorded baselines for three sources
    # that fetch 200 and normalise to 79, 75 and 14 characters of readable text,
    # because Meta and TikTok serve JavaScript applications with no server
    # rendered policy text. A fingerprint that short can never move, so all
    # three would have read Stable forever while nothing was watched. The node
    # now refuses anything under 1000 characters. A browser User-Agent and
    # substitute URLs were both tried and reverted, executions 6403 and 6407.
    # What fixed it was a Firecrawl fallback on Gateway credits, which renders
    # JavaScript and also cleared X's 403; it runs ONLY on a source plain HTTP
    # already failed, so roughly five scrapes a sweep and not nine. Assess
    # Materiality runs on a MANAGED anthropicApi credential, so this workflow
    # holds no key: it is not a key holder and never enters the twenty.
    # Machine verdicts write to AI Verdict; the Assessment column is Tee's
    # research and the workflow must never write it again.
    "OS 29 Platform Policy Sensor": {"id": "vpe8TglGmFwz4YRu", "state": "inactive on the VPS as of 2026-09-16: rebuilt from Cloud and verified clean at 22 nodes through scripts/vps_cutover_apply.py, but it cannot be published there. OS 29 was never in the 40 organ cutover list (39 DEVON organs plus the shared OS Error Handler) because it sits in the TQO lane, so the 2026-09-15 cutover left the VPS on an older 14 node build. Installing @mendable/n8n-nodes-firecrawl v2.1.4 on the VPS on 2026-09-16 cleared the unknown node type and exposed the real blocker: Assess Materiality (Claude) and Firecrawl Render run on n8n Gateway credits, a managed credential feature that exists on n8n Cloud and not on the self hosted VPS, whose credential listing carries no gatewayCredits block at all, which is why Cloud holds no anthropicApi or firecrawlApi credential either. Publishing on the VPS needs a real Anthropic key and a real Firecrawl key, a cost decision for Tee. Still active on n8n Cloud as 7WyIarNoJa2irx2r and deliberately left running: unpublishing it first would take the platform policy watcher dark with nothing behind it. What it does when it runs, recorded on Cloud: daily 06:00 America/New_York, nine sources, a failed fetch writes its reason into AI Verdict with no email, the Firecrawl fallback carries a custom body (waitFor 15000, onlyMainContent false, rawHtml dropped, maxAge 0), comparison is a block level diff with a two flip volatile rule, a completeness rule refuses a hollow capture on both paths, AI Verdict is append only"},
    "Live State Ledger": {"id": "hDmTRI5VAZ3a8sTn", "state": "active"},
    # Builds 01, 03, 04, 06 and 07, the organs the driver walks a job through.
    # Live since 2026-08-23 and 08-24 but never registered here until 2026-09-05,
    # which the new allowlist test caught: the Action Router dispatches to the
    # Spine and this map did not know the Spine existed. All five run with
    # successful execution data off since Tee's ruling 2 the same day, because
    # their webhooks take the x-devon-key header.
    "Spine Conformance Executor": {"id": "VUXIyCaur9lejAhL", "state": "active, webhook devon-spine-n8n, advances one legal state, successful executions not saved"},
    "Conscious and Subconscious Runtime": {"id": "ePvPCXVUjygZzvQT", "state": "active, webhook devon-runtime, UNDERSTANDING to PLANNING, successful executions not saved"},
    "Intelligence Router": {"id": "8QiP1xQiB21Ic42Z", "state": "active, webhook devon-route, PLANNING to AUTHORIZED or WAITING_APPROVAL or ESCALATED, successful executions not saved"},
    "Event Bus": {"id": "11weboiKowmLq3d0", "state": "active, webhook devon-event, fourteen event types, persists to the ledger, successful executions not saved"},
    "EditForge Handoff": {"id": "LnbtB81ItUYptbWg", "state": "active, webhook devon-editforge, EXECUTING only, completed maps to VERIFYING, successful executions not saved"},
    "Build 12 Upstream Test": {"id": "VzJsSlDswkIJ9wok", "state": "active"},
    # Recorded as a 15 minute poll until 2026-09-06; the live trigger had been
    # daily (02:00 instance time) since 2026-09-05, found by reading the node
    # for Build 18. Build 18 (2026-09-06, learning capture): the feeder now
    # mirrors its feed log onto the job envelope as one LEARNING_CAPTURED event
    # per fed job through the Event Bus, a same state COMPLETED update, so
    # learning.state reads captured with the feed time and the gate decision.
    "Build 12 Ledger Feeder": {"id": "GEbNoDMBdGqDfZJ2", "state": "active, daily 02:00 America/New_York (timezone pinned 2026-09-07), feeds COMPLETED jobs once each and marks the envelope captured, versions 7bef0e3b"},
    # Sole devon-soul writer, approval gated. First draft Wo7zPxpGH8kiBRy8 was
    # archived unpublished after adversarial review; lANs6wopaK0PkNhN is the
    # rebuild that shipped. Its execution data persistence is off on purpose
    # (approval tokens must not land in stored executions); truth lives in the
    # data tables and digest emails, read via the Table Reader.
    # Ruled by Tee 2026-09-06 ("hourly") once the burn was measured: the 15 minute
    # poll cost 96 executions a day against a commit log holding one row since
    # 2026-08-25. Hourly since version 49007534; one proposal and one commit per
    # poll unchanged, failure alert damping retuned to every 4th attempt.
    "Soul Committer": {"id": "drP96ernQvbrvzIZ", "state": "active, hourly poll (15 minute poll until 2026-09-06), one proposal and one commit per poll"},
    # Found inactive on the live instance 2026-09-01 by the first estate
    # reconcile; recorded active until then, deactivation unrecorded. An n8n
    # error workflow fires when a caller names it whether or not it is
    # active, so the lane likely kept working, but the record was wrong and
    # nobody had said so. Reactivated later the same day on Tee's ruling
    # ("Flip on"): the only version it has ever had (17239190, built
    # 2026-08-25) republished unchanged, read back active.
    "Error Alarm": {"id": "bqcnIS0Qv4RkTCU1", "state": "active, shared error workflow, reactivated 2026-09-01"},
    "Learning Lane Table Reader": {"id": "VGwrZPdZ5se2pr03", "state": "manual, read only"},
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
    "Heartbeat": {"id": "EEDrp2jLlw2Ssd5b", "state": "active, 6 hour pulse, reactivated 2026-09-01"},
    # Daily sweep: any ledger job still non-terminal past 96h is cancelled
    # THROUGH the guarded devon-ledger webhook, never by writing the table
    # directly, so legal-transition rules keep applying (VERIFYING two-steps
    # FAILED then CANCELLED). Envelope history is preserved plus a janitor
    # trace note. Digest email only when it acted; unreadable envelopes are
    # skipped and named, and the Heartbeat keeps alerting on them
    # (stuck_jobs) until repaired by hand.
    "Ledger Janitor": {"id": "V0i8zTw1keMMJmhF", "state": "active, daily 02:30 America/New_York, timezone pinned 2026-09-07, previously mis-documented as UTC"},
    # Weekly read-only export: the four learning-lane tables (state ledger,
    # feed log, soul commit log, heartbeat log) each to CSV, one Gmail with
    # four attachments. approval_queue is EXCLUDED on purpose: its rows carry
    # plaintext decision tokens, and mailing them would let anyone with inbox
    # access approve soul writes. Never add it to this or any export.
    "Weekly Table Backup": {"id": "rVXA5wH5AXW4tCjp", "state": "active, weekly Sun 03:10 America/New_York, timezone pinned 2026-09-07, previously mis-documented as UTC"},
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
    "Action Router": {"id": "NYcEp03Oqlvq86Mb", "state": "active, webhook devon-action, allowlist spine.echo at ceiling read, drive.draft at ceiling reversible_write, airtable.row at ceiling reversible_write and zapier.mcp at ceiling reversible_write, successful executions not saved"},
    # Build 16, the first real executor. One Google Doc draft per job, idempotent
    # by key, folder by Area from DRAFT_FOLDERS. See WEBHOOKS devon-drive-draft.
    "Drive Draft Writer": {"id": "FdQgiX2Thgk38CSa", "state": "active, webhook devon-drive-draft, executor drive.draft at ceiling reversible_write, successful executions not saved"},
    # Build 17, the second real executor. One row per job into a table
    # AIRTABLE_ROW_TABLES permits, idempotent by DEVON key and DEVON job. See
    # WEBHOOKS devon-airtable-row.
    "Airtable Row Writer": {"id": "glEO2xa4IZmHDbkg", "state": "active, webhook devon-airtable-row, executor airtable.row at ceiling reversible_write, successful executions not saved"},
    # Build 19, the third real executor. One tools/call per job on the Zapier MCP
    # server, only a tool ZAPIER_MCP_TOOLS permits, idempotent by the call log
    # devon_zapier_call_log the executor owns. See WEBHOOKS devon-zapier-mcp.
    "Zapier Executor": {"id": "MIELNCkP9IyHWVlr", "state": "active, webhook devon-zapier-mcp, executor zapier.mcp at ceiling reversible_write, successful executions not saved"},
    "Intake Former": {"id": "TciVQhWJA0y92x9P", "state": "active, webhook devon-intake"},
    "Job Driver": {"id": "MfJCYeJqVjBLFrCu", "state": "active, sub-workflow called by the Intake Former and the Driver Poll"},
    "Driver Poll": {"id": "6b4dJasBKcOPQ6oX", "state": "active, hourly poll"},
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
    "Face": {"id": "sPv6Cq7elbjoi5Nw", "state": "active, hosted chat, n8n user auth"},
    "TQO FINAL V5": {"id": "qEkGOUsNyVaRAmm6", "state": "active since 2026-09-08, published on Tee's ruling with all six schedule triggers disabled, each re-enabled as its own named act on his watch; activeVersionId bde7ddec; seven webhooks live: four on header x-devon-key (run-tqo-pipeline, run-nco-pipeline, system-pause, system-resume) and three on secret paths (run-tqo, run-nco, gumroad-sale); the Gumroad guard verifies each ping against GET /v2/sales/:id on credential K1D8KUvTcWDcdrV0, refuses a missing sale on Gumroad's 200 success false, and accepts the two trailing equals signs real ids carry since the same-day fix; view_sales on a real sale still unproven"},
    "DEVON Gumroad Sale Check": {"id": "e5H3pk7YNF9jQi1r", "state": "active since 2026-09-08, activeVersionId 8e26df1d (8c50cbb8 at first publish; e187e828 the same day with an empty-sale guard and successful executions not saved; 8e26df1d at about 14:55 UTC with the list job, ruled, proved on 6501 to 6507); webhook devon-gumroad-sale-check on header x-devon-key, reads one sale from GET /v2/sales/:id or the last five sales from GET /v2/sales with no buyer fields, on credential K1D8KUvTcWDcdrV0, and writes nothing; proved on executions 6482 and 6483 (manual, body pinned) and 6489 and 6490 (pinned Gumroad replies: empty sale 502, found sale 200), and from outside on probe execution 6494 (two production POSTs at the door from inside n8n: 404 with the key, 403 without); Tee's Shortcut was repointed at it on 2026-09-08 and proved from the phone (400 at Preflight at 13:47 UTC, then the 404 end to end at 13:58 UTC), so the Gumroad token is off the phone"},
    "Capture Hook": {"id": "bCZa6KVgjHgRup1Y", "state": "retired 2026-08-22"},
    "DEVON Vision Describe": {"id": "WjSNXSsGP8ZCxXMa", "state": "active since 2026-09-16, published activeVersionId f5222423; webhook devon-vision on header x-devon-key credential MTZXcoob6BtzbJyH; refuses before spending on type, size and a missing model id, and answers every refusal as data with a reason and a status; logs one row per attempt to devon_vision_log lapnGsgr33wcX0Ef, guard refusals included since the Log Refusal node was added; proven from outside by a 403 with no key and end to end by executions 254, 255, 257 and 258, which are rows 1 to 4 of that table; answering for real since 2026-09-16 on default model inclusionai/ling-3.0-flash-vl:free at cost 0, activeVersionId 4fc9069d, proven by execution 263 which sent only an image, took the default model and prompt, returned 200 and wrote row 6"},
    # Registered 2026-09-06, ruled by Tee after the operational report found
    # ten DEVON named workflows on the instance and not in this map, four of
    # them active and unwatched by the reconciler since they were built.
    # Record side only: nothing was activated, deactivated or archived. Each
    # state was read from the workflow's trigger that morning; the six
    # inactive ones are one shots, probes and manual tools, and stay
    # registered so a quiet reactivation reports DRIFT instead of passing.
    "Health and Observability Console": {
        "id": "bsxKtdx1ebMu5hGs",
        "state": "active, webhook devon-health GET, reads the ledger, read only",
    },
    "Monthly Credential Review": {
        "id": "ZKyaYzv7DAGhJSLi",
        "state": "active, monthly on the 1st 08:00 New York",
    },
    "Notion Buffer Drain": {
        "id": "ptAmD28msYTvobgq",
        "state": "active, daily 07:00 New York, Airtable Thread Receipts to the Notion Thread Log",
    },
    "To Delete Auto-Purge": {"id": "2M8CIPebpl1nSLVx", "state": "active, weekly Sunday 10:00 New York"},
    # Both were one shot throwaways that only ever existed on n8n Cloud, and
    # both ran their single job there. After the 2026-09-15 cutover this
    # registry reads the VPS, where neither was ever created, so the ids below
    # resolve nowhere. Kept named rather than deleted because the executions
    # they produced are cited in older status docs, and a reader meeting those
    # names needs to know where they lived and that they are gone.
    "Soul Index Setup": {
        "id": "vYr35jqNNaAztGhQ",
        "state": "retired, Cloud only, absent from the VPS",
    },
    "Build 08 Credential Probe": {
        "id": "pm5hoO4eFpGhlAb4",
        "state": "retired, Cloud only, absent from the VPS",
    },
    "End to End Watch Harness": {"id": "VwSnFY0Qyw03FxKk", "state": "inactive, watch harness"},
    "Master Index": {"id": "aDMJX0I83b1LS5gz", "state": "inactive"},
    "Purge List": {"id": "DxEB0OrDLlkDBrsF", "state": "manual, purge list"},
    "Vault Comparison": {"id": "DjrDKJ5hTYULzGcm", "state": "inactive"},
    # The six active TSWS pipeline workflows, registered 2026-09-06 on Tee's
    # ruling that the map watches every active workflow on the instance, not
    # only the DEVON organs. The 16 inactive seeds, one shots and bootstraps
    # that share the project stay unregistered on the same ruling. Each state
    # was read from the instance that day: 00 and 02 to 05 are sub-workflows
    # called by the master and carry an Execute Workflow trigger, so they have
    # no schedule of their own; 01 describes itself as the drop folder watcher
    # and its trigger node was not read. 01 also had a draft ahead of its
    # active version that day, which the reconciler does not check.
    "TSWS 00 Render Job": {"id": "CX07qa6O1hTSXlpj", "state": "active, sub-workflow called by TSWS 01"},
    "TSWS 01 Post-Production Master": {
        "id": "UoJS8WDZfkVD9AVH",
        "state": "active, drop folder watcher per its description, trigger node not read",
    },
    "TSWS 02 Narration and Sound Bed": {"id": "vqfgphaJUi1OWx5x", "state": "active, sub-workflow called by TSWS 01"},
    "TSWS 03 Visual Assembly": {"id": "s3TE4io4Qzl4DI1Q", "state": "active, sub-workflow called by TSWS 01"},
    "TSWS 04 Detail Recovery": {"id": "khY3wwZt79FQgjAW", "state": "active, sub-workflow called by TSWS 01"},
    "TSWS 05 Conform and Grain": {"id": "klTNudFrz5hXBVy2", "state": "active, sub-workflow called by TSWS 01"},
    # Registered 2026-09-08. A manual only helper in Tee's personal project
    # that reads, previews, publishes or clears the custom landing page on
    # Gumroad product gxcyjr through credential K1D8KUvTcWDcdrV0, built
    # because the container this repository is worked from cannot reach
    # gumroad.com. Its Job node refuses to send a payload whose sha256 prefix
    # and byte length differ from the constants it carries, so the bytes that
    # reach Gumroad are the bytes that were reviewed. It has no trigger but
    # the manual one and has never been published.
    "Gumroad Landing Page Helper (gxcyjr)": {
        "id": "mk6l25xXGoNHhNp7",
        "state": "manual, never published, reads previews publishes or clears the gxcyjr landing page on Tee's word",
    },
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
    "Rakazo": WritePermission(
        platform="Rakazo",
        allowed_folder_id=RESEARCH_FOLDER["id"],
        allowed_folder_name=RESEARCH_FOLDER["name"],
        may_write_canon=False,
        naming_pattern="AREA_SOURCE_slug_vN_YYYY-MM-DD.md",
        note=(
            "Tee's Rakazo bots file research here and nowhere else, only through "
            "EditForge's research_file tool and the Bot Research Filer workflow, "
            "which also retires their own superseded pieces to 4. Archive. Ruled "
            "2026-09-24 when Thoth's archive was placed in the vault."
        ),
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
