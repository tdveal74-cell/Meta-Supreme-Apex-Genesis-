"""Tests for the naming convention, including the real filenames in the vault."""

import pytest

from services.devon import areas, naming


def test_area_codes_match_the_areas_module():
    """Drift between the two vocabularies fails here rather than in production.

    The naming module deliberately holds its own copy of the codes so that a
    change to one without the other is caught by a test instead of passing
    silently through a shared constant.
    """
    assert set(naming.AREA_CODES) == set(areas.canonical_codes())


def test_parses_a_conforming_name():
    parsed = naming.parse_filename("TSWS_CANON_rulings-d17-d18_v1_2026-08-22.md")
    assert parsed.area == "TSWS"
    assert parsed.type_code == "CANON"
    assert parsed.slug == "rulings-d17-d18"
    assert parsed.version == 1
    assert parsed.date == "2026-08-22"
    assert parsed.extension == "md"
    assert parsed.conforms


def test_parses_the_master_directory_name():
    parsed = naming.parse_filename("SYS_INDEX_master-directory_v6_2026-08-22.md")
    assert parsed.area == "SYS"
    assert parsed.type_code == "INDEX"
    assert parsed.version == 6
    assert parsed.conforms


def test_superseded_prefix_is_read_as_a_prefix():
    parsed = naming.parse_filename(
        "SUPERSEDED_SYS_INDEX_master-directory_v4_2026-08-21--merged-into-v5.md"
    )
    assert parsed.prefix_marker == "SUPERSEDED"
    assert parsed.area == "SYS"
    assert parsed.version == 4
    assert parsed.date == "2026-08-21"
    assert parsed.is_superseded


def test_legacy_decimal_version_parses_but_is_flagged():
    parsed = naming.parse_filename("TSWS_SKILL_ultra-script-doctor_v2.1_2026-07-30.md")
    assert parsed.version == 2
    assert parsed.version_is_decimal
    warnings = [v for v in parsed.violations if v.rule == "version"]
    assert warnings and "grandfathered" in warnings[0].message


def test_building_a_decimal_version_is_refused():
    """Grandfathering covers names already written. It is not a licence for another."""
    with pytest.raises(naming.NamingError, match="plain integer"):
        naming.build_filename("SYS", "SPEC", "test", 2.1, "2026-08-22")


@pytest.mark.parametrize("generic", ["SKILL.md", "README.md", "Untitled.md", "File_000"])
def test_bare_generic_names_are_errors(generic):
    violations = naming.validate_filename(generic)
    assert any(v.rule == "rule-1" and v.severity == "error" for v in violations)


def test_em_dash_in_a_filename_is_an_error():
    violations = naming.validate_filename("SYS_DOC_a—b_v1_2026-08-22.md")
    assert any(v.rule == "rule-7" for v in violations)


def test_build_filename_produces_the_pattern():
    name = naming.build_filename(
        area="SYS", type_code="SPEC", slug="Devon Merge Plan", version=1, on_date="2026-08-22"
    )
    assert name == "SYS_SPEC_devon-merge-plan_v1_2026-08-22.md"


def test_build_filename_refuses_an_unknown_area():
    with pytest.raises(naming.NamingError, match="not a valid Area code"):
        naming.build_filename("BUSINESS", "DOC", "x", 1, "2026-08-22")


def test_build_filename_refuses_an_unknown_type():
    with pytest.raises(naming.NamingError, match="not a valid type code"):
        naming.build_filename("SYS", "MEMO", "x", 1, "2026-08-22")


def test_build_filename_refuses_a_non_iso_date():
    with pytest.raises(naming.NamingError, match="ISO date"):
        naming.build_filename("SYS", "DOC", "x", 1, "22-08-2026")


def test_superseded_flag_prefixes_the_name():
    name = naming.build_filename(
        "SYS", "SPEC", "old thing", 1, "2026-08-22", superseded=True
    )
    assert name.startswith("SUPERSEDED_SYS_SPEC_")


def test_protective_markers_mark_a_file_protected():
    parsed = naming.parse_filename("SYS_PROOF_evidence-bundle_v1_2026-08-22_KEEP.md")
    assert parsed.is_protected
    assert "KEEP" in [m.upper() for m in parsed.markers]


def test_warning_markers_are_surfaced():
    parsed = naming.parse_filename("SYS_DOC_thing_v1_2026-08-22_ruling-owed.md")
    assert "ruling-owed" in parsed.warnings_in_name


def test_status_words_in_the_slug_warn():
    violations = naming.validate_filename("SYS_DOC_report-final_v1_2026-08-22.md")
    assert any(v.rule == "rule-5" for v in violations)


def test_missing_date_is_an_error():
    violations = naming.validate_filename("SYS_DOC_thing_v1.md")
    assert any(v.rule == "rule-2" and v.severity == "error" for v in violations)


def test_parse_never_raises_on_junk():
    """The vault is full of names written before the convention. Reading must not crash."""
    for junk in ["", "   ", "a", "...", "hacktober.txt", "news_log.txt", "_" * 40]:
        parsed = naming.parse_filename(junk)
        assert isinstance(parsed, naming.ParsedName)


def test_slugify_uses_hyphens_inside_the_slug():
    assert naming.slugify("Devon Merge Plan v2!") == "devon-merge-plan-v2"


def test_disambiguation_by_measurement():
    measured = naming.disambiguate_by_measurement(
        "TEE_MEMORY_CANONICAL.md", 71385, "2026-08-13T105518"
    )
    assert measured == "TEE_MEMORY_CANONICAL_71385bytes_2026-08-13T105518.md"
