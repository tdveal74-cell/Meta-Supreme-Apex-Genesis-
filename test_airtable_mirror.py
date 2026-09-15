"""The Airtable mirror transform, ruled 2026-09-15, stays deterministic."""

import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent / "scripts"))

import airtable_mirror as am  # noqa: E402


def test_table_names_carry_the_base_prefix_and_are_snake_case():
    assert am.table_name("tqo", "NCO Forge Content") == "at_tqo_nco_forge_content"
    assert am.table_name("tsws", "Content") == "at_tsws_content"
    assert am.table_name("fin", "  Ledger ") == "at_fin_ledger"


def test_the_credentials_table_never_moves():
    assert am.is_excluded("Credentials")
    assert am.is_excluded(" credentials ")
    assert not am.is_excluded("Customers")
    assert am.plan_table("tqo", {"id": "t1", "name": "Credentials", "fields": []}, []) is None


def test_column_names_are_legal_unique_and_never_shadow_system_columns():
    fields = [
        {"id": "f1", "name": "Video Title", "type": "singleLineText"},
        {"id": "f2", "name": "video title", "type": "singleLineText"},
        {"id": "f3", "name": "1st Draft", "type": "multilineText"},
        {"id": "f4", "name": "airtable record id", "type": "singleLineText"},
        {"id": "f5", "name": "x" * 90, "type": "singleLineText"},
    ]
    cols = am.column_names(fields)
    names = [c[1] for c in cols]
    assert names[0] == "video_title"
    assert names[1] == "video_title_2"
    assert names[2] == "f_1st_draft"
    assert names[3] == "airtable_record_id_2"
    assert len(names[4]) <= 63
    assert len(set(names)) == len(names)
    for n in names:
        assert am._COLUMN_RE.match(n)


def test_column_types_follow_the_airtable_field_type():
    assert am.column_type("number") == "number"
    assert am.column_type("rating") == "number"
    assert am.column_type("checkbox") == "boolean"
    assert am.column_type("date") == "date"
    assert am.column_type("dateTime") == "date"
    assert am.column_type("singleSelect") == "string"
    assert am.column_type("multipleAttachments") == "string"
    assert am.column_type("formula") == "string"


def test_cells_keep_the_human_readable_part_and_never_fabricate_a_number():
    assert am.cell_value("string", {"id": "selX", "name": "Idea", "color": "blue"}) == "Idea"
    assert am.cell_value("string", [{"id": "selA", "name": "A"}, {"id": "selB", "name": "B"}]) == "A, B"
    assert am.cell_value("string", [{"id": "att1", "url": "https://x/y.png", "filename": "y.png"}]) == "https://x/y.png"
    assert am.cell_value("string", ["recA", "recB"]) == "recA, recB"
    assert am.cell_value("string", {"state": "generated", "value": "Summary text"}) == "Summary text"
    assert am.cell_value("string", {"id": "usr1", "email": "a@b.c", "name": "Tee"}) == "Tee"
    assert am.cell_value("number", "not a number") is None
    assert am.cell_value("number", "12.5") == 12.5
    assert am.cell_value("boolean", "yes") is True
    assert am.cell_value("boolean", None) is None
    assert am.cell_value("date", "2026-09-15") == "2026-09-15"
    assert am.cell_value("string", None) is None


def test_plan_table_is_a_faithful_row_per_record():
    table = {"id": "tblA", "name": "Content", "fields": [
        {"id": "fT", "name": "Topic", "type": "singleLineText"},
        {"id": "fS", "name": "Status", "type": "singleSelect"},
        {"id": "fV", "name": "Virality Score", "type": "number"},
        {"id": "fH", "name": "Human Review", "type": "checkbox"},
    ]}
    records = [
        {"id": "rec1", "createdTime": "2026-08-08T17:58:07.000Z", "cellValuesByFieldId": {
            "fT": "I Gave an AI Agent My Work for 7 Days", "fS": {"id": "s", "name": "Idea"}, "fV": 100}},
        {"id": "rec2", "createdTime": "2026-08-08T17:59:00.000Z", "cellValuesByFieldId": {"fT": "Second", "fH": True}},
    ]
    plan = am.plan_table("tqo", table, records)
    assert plan["table"] == "at_tqo_content"
    assert [c["name"] for c in plan["columns"]] == [
        "airtable_record_id", "airtable_created_time", "topic", "status", "virality_score", "human_review"]
    assert plan["rows"][0] == {
        "airtable_record_id": "rec1", "airtable_created_time": "2026-08-08T17:58:07.000Z",
        "topic": "I Gave an AI Agent My Work for 7 Days", "status": "Idea", "virality_score": 100, "human_review": None}
    assert plan["rows"][1]["human_review"] is True
    assert plan["rows"][1]["status"] is None


def test_plan_base_skips_excluded_tables_and_keeps_order():
    schema = {"tables": [
        {"id": "t1", "name": "Leads", "fields": [{"id": "a", "name": "Name", "type": "singleLineText"}]},
        {"id": "t2", "name": "Credentials", "fields": [{"id": "b", "name": "Secret", "type": "singleLineText"}]},
        {"id": "t3", "name": "Offers", "fields": [{"id": "c", "name": "Price", "type": "currency"}]},
    ]}
    plans = am.plan_base("tqo", schema, {"t1": [{"id": "r", "createdTime": "2026-01-01T00:00:00.000Z", "cellValuesByFieldId": {"a": "x"}}]})
    assert [p["table"] for p in plans] == ["at_tqo_leads", "at_tqo_offers"]
    assert plans[1]["rows"] == []
