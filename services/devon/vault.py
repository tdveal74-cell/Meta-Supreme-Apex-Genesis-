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
        "auth": "header x-devon-key",
        "open_ruling": (
            "Header auth enforced live 2026-08-23, credential Devon Capture Key "
            "FYRvkRTOcROEYZ9P. This entry carried auth None until 2026-08-31, so "
            "anything reasoned from it before that date treated the lane as open. "
            "Posters that cannot attach a custom header now need a shim."
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
        "open_ruling": None,
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
}

WEBHOOK_RULE = (
    "One path, one job. Before creating any new webhook, list existing paths and "
    "confirm the name is unused. A path collision does not error, it silently "
    "routes to whichever workflow was published first."
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
