"""The model cannot use an allowlist it is never shown.

Written on 2026-08-27 after Tee screenshotted DEVON asking him which GitHub
repository to read. There was exactly one on the allowlist, and DEVON had no way
to know it: the catalog the model reads carries name, description, risk,
parameters and blast radius, while the allowlist lives in the separate
tool_catalog() structure that only the Command Center's Capability Dock reads.

So `repository` was a required argument with no discoverable legal value. Asking
was correct behaviour on the information available, which is exactly what made
it worth fixing rather than scolding: the estate knew the answer and had not
told him.

The tests below pin all three allowlist states, because the empty one is what CI
runs under and the single-repository one is what production runs under, and a
fix that only works in the state you developed in is not a fix.
"""

from __future__ import annotations

from services.agent_runtime.tools import ToolRegistry
from services.devon.approval import ApprovalQueue, InMemoryApprovalStore
from services.github.agent_adapter import GitHubCapabilityAdapter

ONE = "tdveal74-cell/Meta-Supreme-Apex-Genesis-"
TWO = "tdveal74-cell/EditForge"


class StubClient:
    """Only the surface register() reads."""

    configured = True

    def __init__(self, allowed):
        self.allowed_repositories = list(allowed)


def described(allowed):
    registry = ToolRegistry()
    adapter = GitHubCapabilityAdapter(
        StubClient(allowed), ApprovalQueue(InMemoryApprovalStore())
    )
    adapter.register(registry)
    return {d["name"]: d for d in registry.describe()}


GITHUB_TOOLS = (
    "github.repo_status",
    "github.read_file",
    "github.pull_request",
    "github.create_branch",
    "github.write_file",
    "github.create_pull_request",
    "github.merge_pull_request",
)


# ---------------------------------------------------------------------------
# One repository: production, and the exchange that prompted this
# ---------------------------------------------------------------------------


def test_a_single_allowlisted_repository_is_named_in_the_description() -> None:
    catalog = described([ONE])
    assert ONE in catalog["github.read_file"]["description"]


def test_the_model_is_told_to_just_use_it_rather_than_ask() -> None:
    """Naming the repo is not enough on its own.

    A catalog that lists a repository without saying it is the one to use still
    leaves "which repository did you mean" as a reasonable question.
    """
    text = described([ONE])["github.read_file"]["description"]
    assert "use it as the repository" in text


def test_every_repository_taking_tool_carries_the_scope() -> None:
    """A model that learns the repo from read_file and then guesses at
    write_file has learned nothing useful."""
    catalog = described([ONE])
    for name in GITHUB_TOOLS:
        assert ONE in catalog[name]["description"], name


# ---------------------------------------------------------------------------
# Several: it has to choose, so it has to see the choices
# ---------------------------------------------------------------------------


def test_several_repositories_are_all_listed() -> None:
    text = described([ONE, TWO])["github.read_file"]["description"]
    assert ONE in text and TWO in text


def test_several_repositories_do_not_get_the_use_it_instruction() -> None:
    """With a choice to make, "just use it" would be a licence to guess.

    Compared case-insensitively on purpose: the first version of this assertion
    matched the exact lowercase phrase and sailed straight past a deliberately
    broken build whose only difference was a capital U.
    """
    text = described([ONE, TWO])["github.read_file"]["description"].lower()
    assert "use it as the repository" not in text
    assert "any other value is refused" in text


# ---------------------------------------------------------------------------
# None: what CI runs under, and what an unconfigured deployment looks like
# ---------------------------------------------------------------------------


def test_an_empty_allowlist_says_calls_will_be_refused() -> None:
    text = described([])["github.read_file"]["description"]
    assert "No repository is allowlisted" in text
    assert "DEVON_GITHUB_ALLOWED_REPOS" in text


def test_an_empty_allowlist_names_no_repository() -> None:
    """Fail closed in the description too. A catalog that invents a plausible
    repository name would send the model to a guaranteed refusal."""
    text = described([])["github.read_file"]["description"]
    assert ONE not in text
    assert "tdveal74-cell/" not in text


# ---------------------------------------------------------------------------
# What the scope must not cost
# ---------------------------------------------------------------------------


def test_the_original_description_survives_the_addition() -> None:
    """The scope is additive. Losing what the tool does to say where it does it
    trades one missing fact for another."""
    text = described([ONE])["github.read_file"]["description"]
    assert "Read one UTF-8 file up to 1 MB" in text
    assert "next_offset" in text


def test_the_declared_parameters_are_untouched() -> None:
    catalog = described([ONE])
    assert catalog["github.read_file"]["parameters"] == [
        "repository",
        "path",
        "ref",
        "offset",
    ]


def test_risk_and_blast_radius_are_untouched() -> None:
    """Descriptions feed the model; these feed the presence ruling. Editing one
    must not disturb the other."""
    catalog = described([ONE])
    assert catalog["github.merge_pull_request"]["risk"] == "high_impact"
    assert catalog["github.read_file"]["risk"] == "read"
    assert "blast_radius" in catalog["github.read_file"]
