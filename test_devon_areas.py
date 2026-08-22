"""Tests for the nine Area vocabulary and the trust ladder around it."""

import pytest

from services.devon import areas


def test_there_are_exactly_nine_areas():
    assert len(areas.AREAS) == areas.AREA_COUNT == 9


def test_canonical_labels_match_canon():
    assert areas.canonical_labels() == [
        "TQO",
        "Podcast",
        "NCO",
        "ACX",
        "Health",
        "Money",
        "Family",
        "Learning",
        "Systems",
    ]


def test_acx_is_the_ninth_and_ruled():
    acx = areas.get_area("ACX")
    assert acx is not None
    assert acx.ruled == "2026-08-20"


def test_podcast_files_as_tsws_and_systems_files_as_sys():
    """The only two places the prose vocabulary and the filename codes diverge."""
    assert areas.normalize_code("Podcast") == "TSWS"
    assert areas.normalize_label("TSWS") == "Podcast"
    assert areas.normalize_code("Systems") == "SYS"
    assert areas.normalize_label("SYS") == "Systems"


def test_lookup_accepts_label_code_and_short_form():
    assert areas.get_area("money").label == "Money"
    assert areas.get_area("MONEY").label == "Money"
    assert areas.get_area("mon").label == "Money"
    assert areas.get_area("lrn").label == "Learning"


@pytest.mark.parametrize("invented", ["Business", "Personal", "Work", "Misc", "General", ""])
def test_invented_areas_are_refused(invented):
    assert areas.get_area(invented) is None
    assert not areas.is_valid_area(invented)


def test_require_area_raises_loudly_rather_than_defaulting():
    with pytest.raises(areas.AreaError) as excinfo:
        areas.require_area("Business")
    message = str(excinfo.value)
    assert "not one of the nine" in message
    assert "Never invent a tenth" in message


def test_classify_finds_the_obvious_area():
    assert areas.classify("the vespera cold open for the podcast").label == "Podcast"
    assert areas.classify("ascension caudex folio pipeline").label == "ACX"
    assert areas.classify("n8n workflow and the airtable base").label == "Systems"


def test_classify_declines_when_nothing_matches():
    assert areas.classify("a plain sentence about nothing in particular") is None


def test_classify_declines_on_a_tie_rather_than_flipping_a_coin():
    """A tie carries no information, and a wrong tag is permanent."""
    tied = "podcast money"
    scored = areas.classify_with_scores(tied)
    assert scored[0][1] == scored[1][1]
    assert areas.classify(tied) is None


def test_resolve_area_honours_a_valid_supplied_area():
    area, provenance = areas.resolve_area("Health", "unrelated text")
    assert area.label == "Health"
    assert provenance == "supplied and validated"


def test_resolve_area_discards_an_invalid_supplied_area_and_falls_back():
    """A model supplied Area is never trusted. Validate, discard, then classify."""
    area, provenance = areas.resolve_area("Business", "the tqo channel monetization plan")
    assert area.label == "TQO"
    assert "rejected" in provenance
    assert "keyword fallback" in provenance


def test_resolve_area_declines_when_supplied_is_bad_and_text_is_silent():
    area, provenance = areas.resolve_area("Business", "nothing identifiable here")
    assert area is None
    assert "declined" in provenance


def test_acx_keywords_are_canon_and_the_rest_are_derived():
    """Only ACX had its keyword hints ruled into live workflows."""
    canon = [a.label for a in areas.AREAS if a.keywords_are_canon]
    assert canon == ["ACX"]
