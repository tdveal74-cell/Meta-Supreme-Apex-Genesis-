"""A truncated result must say so, and there must be a way to read the rest.

Found on 2026-08-27 in Tee's own screenshots, minutes after the GitHub adapter
first worked end to end in production. He asked DEVON to read the README. DEVON
called github.read_file three times in one turn, announcing "fetch the rest of
the README content" and then "to get the full README content", and every call
returned an identical body ending mid-token at "```bash\npip".

Nothing was broken in the adapter. Observation.from_result cut every successful
result to 1000 characters and said nothing about having done it, so the model
saw content stopping mid-word, correctly concluded it was missing the rest, and
asked again. The retry was the right instinct served by the wrong information.

Two things were wrong and both are needed: the cut was silent, and there was no
argument that could have made a second call return anything different. A note
without an offset is an apology; an offset without a note is a feature nobody
knows about.
"""

from __future__ import annotations

import pytest

from services.agent_runtime.agent_turn import (
    FAILURE_OBSERVATION_LIMIT,
    OBSERVATION_LIMIT,
    Observation,
)
from services.github.agent_adapter import READ_WINDOW_CHARS, GitHubCapabilityAdapter

# ---------------------------------------------------------------------------
# The cut says so
# ---------------------------------------------------------------------------


def test_a_short_result_is_passed_through_untouched() -> None:
    """No note on output that was never cut, or every observation carries noise."""
    observation = Observation.from_result("github.read_file", True, "short body")
    assert observation.outcome == "short body"


def test_a_result_exactly_at_the_limit_is_not_annotated() -> None:
    """The boundary case, because off by one here mislabels a complete read."""
    body = "x" * OBSERVATION_LIMIT
    assert Observation.from_result("t", True, body).outcome == body


def test_one_character_over_the_limit_is_annotated() -> None:
    body = "x" * (OBSERVATION_LIMIT + 1)
    outcome = Observation.from_result("t", True, body).outcome
    assert "withheld 1" in outcome


def test_the_note_names_the_size_of_what_was_withheld() -> None:
    body = "x" * 5000
    outcome = Observation.from_result("github.read_file", True, body).outcome

    assert f"first {OBSERVATION_LIMIT} of 5000 characters" in outcome
    assert f"withheld {5000 - OBSERVATION_LIMIT}" in outcome


def test_the_note_says_repeating_the_call_changes_nothing() -> None:
    """The sentence that would have ended the loop in the screenshots."""
    outcome = Observation.from_result("github.read_file", True, "y" * 5000).outcome
    assert "same arguments returns the same first" in outcome


def test_the_note_points_at_the_way_out() -> None:
    outcome = Observation.from_result("github.read_file", True, "y" * 5000).outcome
    assert "offset" in outcome


def test_the_content_itself_still_survives_intact() -> None:
    """The note must be additive. Losing a character of payload to make room
    would trade one silent truncation for another."""
    body = "abcdefghij" * 500
    outcome = Observation.from_result("t", True, body).outcome
    assert outcome.startswith(body[:OBSERVATION_LIMIT])


def test_a_failure_is_still_cut_shorter_and_keeps_its_prefix() -> None:
    """Unchanged behaviour, pinned so the new branch cannot swallow it."""
    outcome = Observation.from_result("t", False, "e" * 5000).outcome
    assert outcome.startswith("FAILED: ")
    assert len(outcome) == len("FAILED: ") + FAILURE_OBSERVATION_LIMIT


# ---------------------------------------------------------------------------
# The way out actually exists
# ---------------------------------------------------------------------------


def window(content: str, offset: int) -> dict:
    return GitHubCapabilityAdapter._window(
        {"repository": "o/r", "path": "README.md", "content": content}, offset
    )


def test_a_file_shorter_than_the_window_is_complete_and_says_so() -> None:
    result = window("# short readme", 0)
    assert result["content"] == "# short readme"
    assert result["next_offset"] is None
    assert result["remaining_characters"] == 0


def test_a_long_file_reports_where_the_next_read_starts() -> None:
    content = "z" * (READ_WINDOW_CHARS * 2)
    result = window(content, 0)

    assert result["content"] == content[:READ_WINDOW_CHARS]
    assert result["next_offset"] == READ_WINDOW_CHARS
    assert result["remaining_characters"] == READ_WINDOW_CHARS
    assert result["total_characters"] == READ_WINDOW_CHARS * 2


def test_following_next_offset_returns_different_content() -> None:
    """The whole point. Three identical calls become three that make progress."""
    # Every position distinguishable. A repeating pattern whose period divides
    # the window makes three different slices compare equal and the test passes
    # or fails for reasons that have nothing to do with the offset arithmetic.
    content = "".join(f"{i:07d}" for i in range(2000))[: READ_WINDOW_CHARS * 3]

    first = window(content, 0)
    second = window(content, first["next_offset"])
    third = window(content, second["next_offset"])

    assert first["content"] != second["content"] != third["content"]
    assert first["content"] + second["content"] + third["content"] == content
    assert third["next_offset"] is None


def test_an_offset_past_the_end_returns_empty_rather_than_wrapping() -> None:
    result = window("short", 10_000)
    assert result["content"] == ""
    assert result["next_offset"] is None
    assert result["remaining_characters"] == 0


def test_a_response_without_content_is_left_alone() -> None:
    """repo_status and pull_request share the renderer; only files have windows."""
    data = {"repository": "o/r", "number": 7}
    assert GitHubCapabilityAdapter._window(data, 0) == data


# ---------------------------------------------------------------------------
# A bad offset is refused, not silently rounded to the opening window
# ---------------------------------------------------------------------------


@pytest.mark.parametrize("bad", ["soon", "the rest", {}, [1]])
def test_a_non_numeric_offset_is_refused(bad) -> None:
    """A model that invents `offset: "the rest"` must be told, not handed page one.

    Clamping to zero would return the same opening window the note just told it
    not to expect, which is the original bug wearing a new argument.
    """
    with pytest.raises(ValueError, match="whole number"):
        GitHubCapabilityAdapter._offset(bad)


def test_a_negative_offset_is_refused() -> None:
    with pytest.raises(ValueError, match="negative"):
        GitHubCapabilityAdapter._offset(-1)


@pytest.mark.parametrize("blank", [None, ""])
def test_an_absent_offset_means_the_beginning(blank) -> None:
    assert GitHubCapabilityAdapter._offset(blank) == 0


def test_a_numeric_string_offset_is_accepted() -> None:
    """Models emit JSON; a quoted integer is ordinary, not an error."""
    assert GitHubCapabilityAdapter._offset("4000") == 4000


# ---------------------------------------------------------------------------
# The argument is declared, or PR #82's guard refuses the very call that fixes this
# ---------------------------------------------------------------------------


def test_offset_is_declared_so_the_guard_admits_it() -> None:
    """Since PR #82 an undeclared argument is refused at the boundary.

    Adding the parameter to the handler without adding it to `parameters` would
    make every continuation attempt fail with "does not accept: offset", which
    reads exactly like the tool refusing to do the thing it was just told to do.
    """
    from app.services.agent_tasks import build_tool_registry

    described = {d["name"]: d for d in build_tool_registry().describe()}
    assert "offset" in described["github.read_file"]["parameters"]


def test_the_model_is_told_how_to_continue() -> None:
    """The description is where the model learns the argument exists at all."""
    from app.services.agent_tasks import build_tool_registry

    described = {d["name"]: d for d in build_tool_registry().describe()}
    assert "next_offset" in described["github.read_file"]["description"]


# ---------------------------------------------------------------------------
# The wiring, because testing the helper is not testing the tool
# ---------------------------------------------------------------------------


class StubClient:
    """Enough GitHubRESTClient to drive the handler without a network."""

    configured = True

    def __init__(self, content: str) -> None:
        self.content = content
        self.calls: list = []

    def require_repository(self, repository):
        # Allowlisting is the real client's job and has its own tests; here it
        # only needs to not be the thing under examination.
        return repository

    async def read_file(self, repository, path, *, ref=None):
        self.calls.append((repository, path, ref))
        return {
            "repository": repository,
            "path": path,
            "ref": ref,
            "sha": "deadbeef",
            "size": len(self.content),
            "content": self.content,
        }


def adapter_for(content: str):
    from services.devon.approval import ApprovalQueue, InMemoryApprovalStore

    client = StubClient(content)
    return GitHubCapabilityAdapter(client, ApprovalQueue(InMemoryApprovalStore())), client


@pytest.mark.asyncio
async def test_the_handler_actually_windows_what_it_returns() -> None:
    """Removing the _window call from _read_file must fail something.

    The helper tests above all pass against a handler that ignores the helper
    entirely, which is how a fix gets quietly reverted a month later.
    """
    import json

    long_file = "".join(f"{i:07d}" for i in range(2000))
    adapter, _client = adapter_for(long_file)

    result = await adapter._read_file({"repository": "o/r", "path": "README.md"})

    assert result.ok
    body = json.loads(result.output)
    assert body["content"] == long_file[:READ_WINDOW_CHARS]
    assert body["next_offset"] == READ_WINDOW_CHARS
    assert len(body["content"]) < len(long_file)


@pytest.mark.asyncio
async def test_the_handler_honours_the_offset_it_was_given() -> None:
    import json

    long_file = "".join(f"{i:07d}" for i in range(2000))
    adapter, _client = adapter_for(long_file)

    first = json.loads(
        (await adapter._read_file({"repository": "o/r", "path": "README.md"})).output
    )
    second = json.loads(
        (
            await adapter._read_file(
                {"repository": "o/r", "path": "README.md", "offset": first["next_offset"]}
            )
        ).output
    )

    assert second["content"] == long_file[READ_WINDOW_CHARS : READ_WINDOW_CHARS * 2]
    assert second["content"] != first["content"]


@pytest.mark.asyncio
async def test_a_bad_offset_fails_the_call_rather_than_re_reading_page_one() -> None:
    adapter, client = adapter_for("some content")

    result = await adapter._read_file(
        {"repository": "o/r", "path": "README.md", "offset": "the rest"}
    )

    assert result.ok is False
    assert "whole number" in result.error
    assert client.calls == [], "a bad offset should not spend a GitHub request"
