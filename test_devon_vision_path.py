"""The vision path: contracts, per vendor translation, and the refusals.

The decisive test here is `test_the_two_vendors_get_different_bodies`. On the
text path a block list reaches both vendors untranslated and the two request
bodies come out byte identical, measured 2026-09-16. That is the defect this
package exists to avoid, so the proof that it was avoided is a test rather
than a sentence.
"""

import json

import httpx
import pytest

from services.intelligence.providers import (
    OpenAIProvider,
    ProviderAuthError,
    ProviderConfigError,
    ProviderRateLimitError,
    ProviderResponseError,
    ProviderServerError,
)
from services.vision.base import (
    ALLOWED_MEDIA_TYPES,
    DEFAULT_MAX_IMAGE_BYTES,
    ImageSource,
    VisionRequest,
    VisionUnsupportedError,
)
from services.vision.providers import (
    AnthropicVisionProvider,
    LocalVisionProvider,
    MockVisionProvider,
    OpenAIVisionProvider,
    _raise_for_status,
    create_vision_provider,
)

PNG = b"\x89PNG\r\n\x1a\n" + b"pretend pixels" * 4


def _image() -> ImageSource:
    return ImageSource.from_bytes(PNG, media_type="image/png")


def _request(prompt: str = "What is on this screen?") -> VisionRequest:
    return VisionRequest(image=_image(), prompt=prompt, max_tokens=256)


# ---------------------------------------------------------------------------
# ImageSource refuses before anything is spent
# ---------------------------------------------------------------------------

def test_image_source_records_digest_and_size():
    image = _image()
    assert image.byte_count == len(PNG)
    assert len(image.digest) == 64
    assert image.media_type == "image/png"


def test_image_source_normalises_the_media_type():
    assert ImageSource.from_bytes(PNG, media_type="  IMAGE/PNG ").media_type == "image/png"


@pytest.mark.parametrize(
    "data,media_type,fragment",
    [
        (b"", "image/png", "empty"),
        (PNG, "application/pdf", "unsupported media type"),
        (PNG, "", "unsupported media type"),
    ],
)
def test_image_source_refuses_bad_input(data, media_type, fragment):
    with pytest.raises(ValueError) as exc:
        ImageSource.from_bytes(data, media_type=media_type)
    assert fragment in str(exc.value)


def test_image_source_refuses_over_the_ceiling():
    with pytest.raises(ValueError) as exc:
        ImageSource.from_bytes(b"x" * 11, media_type="image/png", max_bytes=10)
    assert "ceiling is 10" in str(exc.value)


def test_the_ceiling_is_bounded_and_the_allowed_list_is_short():
    # The 017 ledger charges a vision call at the text rate, so an unbounded
    # frame is an unbounded under charge. These two constants are the bound.
    assert DEFAULT_MAX_IMAGE_BYTES == 5 * 1024 * 1024
    assert ALLOWED_MEDIA_TYPES == ("image/jpeg", "image/png", "image/webp", "image/gif")


# ---------------------------------------------------------------------------
# The decisive one
# ---------------------------------------------------------------------------

async def test_the_two_vendors_get_different_bodies():
    """One VisionRequest, two vendors, two genuinely different wire shapes."""
    captured: dict = {}

    def capture(key):
        def handler(request: httpx.Request) -> httpx.Response:
            captured[key] = json.loads(request.content)
            if key == "anthropic":
                return httpx.Response(
                    200,
                    json={
                        "content": [{"type": "text", "text": "a screenshot"}],
                        "model": "claude-sonnet-5",
                        "usage": {"input_tokens": 9, "output_tokens": 3},
                    },
                )
            return httpx.Response(
                200,
                json={
                    "choices": [{"message": {"content": "a screenshot"}}],
                    "model": "gpt-5.2",
                    "usage": {"prompt_tokens": 9, "completion_tokens": 3},
                },
            )

        return handler

    request = _request()

    anthropic = AnthropicVisionProvider(
        api_key="k", transport=httpx.MockTransport(capture("anthropic"))
    )
    openai = OpenAIVisionProvider(
        api_key="k", transport=httpx.MockTransport(capture("openai"))
    )

    assert (await anthropic.describe(request)).text == "a screenshot"
    assert (await openai.describe(request)).text == "a screenshot"

    anthropic_messages = captured["anthropic"]["messages"]
    openai_messages = captured["openai"]["messages"]

    # This is the assertion the text path would fail today.
    assert json.dumps(anthropic_messages) != json.dumps(openai_messages)

    anthropic_blocks = anthropic_messages[0]["content"]
    assert anthropic_blocks[0]["type"] == "image"
    assert anthropic_blocks[0]["source"]["type"] == "base64"
    assert anthropic_blocks[0]["source"]["media_type"] == "image/png"
    assert anthropic_blocks[1]["type"] == "text"

    openai_blocks = openai_messages[0]["content"]
    assert openai_blocks[0]["type"] == "text"
    assert openai_blocks[1]["type"] == "image_url"
    assert openai_blocks[1]["image_url"]["url"].startswith("data:image/png;base64,")

    # And the token budget fields are the vendors' own names, not one guessed.
    assert "max_tokens" in captured["anthropic"]
    assert "max_completion_tokens" in captured["openai"]


async def test_the_image_bytes_actually_reach_the_wire():
    import base64

    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["body"] = json.loads(request.content)
        return httpx.Response(
            200,
            json={
                "content": [{"type": "text", "text": "ok"}],
                "model": "m",
                "usage": {"input_tokens": 1, "output_tokens": 1},
            },
        )

    provider = AnthropicVisionProvider(
        api_key="k", transport=httpx.MockTransport(handler)
    )
    await provider.describe(_request())
    sent = captured["body"]["messages"][0]["content"][0]["source"]["data"]
    assert base64.b64decode(sent) == PNG


# ---------------------------------------------------------------------------
# Refusals and the local seam
# ---------------------------------------------------------------------------

def test_cerebras_is_refused_by_name_and_cites_its_own_flag():
    with pytest.raises(VisionUnsupportedError) as exc:
        create_vision_provider("cerebras")
    assert "SUPPORTS_IMAGES is False" in str(exc.value)


def test_an_unknown_provider_is_refused():
    with pytest.raises(VisionUnsupportedError):
        create_vision_provider("gemini-but-not-wired")


def test_a_keyed_provider_refuses_without_a_key():
    with pytest.raises(ProviderConfigError):
        create_vision_provider("anthropic")
    with pytest.raises(ProviderConfigError):
        create_vision_provider("openai")


async def test_local_posts_to_its_own_url_with_no_authorization_header():
    captured: dict = {}

    def handler(request: httpx.Request) -> httpx.Response:
        captured["url"] = str(request.url)
        captured["headers"] = dict(request.headers)
        return httpx.Response(
            200,
            json={
                "choices": [{"message": {"content": "local answer"}}],
                "model": "local-vision",
                "usage": {},
            },
        )

    provider = LocalVisionProvider(transport=httpx.MockTransport(handler))
    answer = await provider.describe(_request())

    assert answer.text == "local answer"
    assert captured["url"] == "http://127.0.0.1:8080/v1/chat/completions"
    assert "authorization" not in {k.lower() for k in captured["headers"]}


async def test_mock_reports_what_it_was_handed_and_calls_nothing():
    answer = await MockVisionProvider().describe(_request())
    assert str(len(PNG)) in answer.text
    assert "image/png" in answer.text
    assert answer.provider == "mock"


# ---------------------------------------------------------------------------
# The error mapping cannot drift from the text path
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "status,expected",
    [
        (401, ProviderAuthError),
        (429, ProviderRateLimitError),
        (500, ProviderServerError),
        (529, ProviderServerError),
        (400, ProviderResponseError),
    ],
)
def test_the_error_mapping_matches_the_text_path(status, expected):
    response = httpx.Response(status, json={"error": {"message": "nope"}})

    with pytest.raises(expected) as vision_exc:
        _raise_for_status(response, provider="openai", vendor="OpenAI")

    text_provider = OpenAIProvider(api_key="k")
    with pytest.raises(expected) as text_exc:
        text_provider._raise_for_status(response)

    assert vision_exc.value.retryable == text_exc.value.retryable


async def test_an_empty_description_is_a_failure_not_a_success():
    def handler(request: httpx.Request) -> httpx.Response:
        return httpx.Response(
            200, json={"choices": [{"message": {"content": "   "}}], "model": "m"}
        )

    provider = OpenAIVisionProvider(
        api_key="k", transport=httpx.MockTransport(handler)
    )
    with pytest.raises(ProviderResponseError):
        await provider.describe(_request())


# ---------------------------------------------------------------------------
# On demand, structurally. No watcher loop, no frame held between calls.
# ---------------------------------------------------------------------------

def test_no_module_in_the_vision_package_starts_a_loop_or_a_timer():
    import pathlib

    banned = ("create_task", "ensure_future", "while True", "Timer(", "Thread(", "schedule")
    root = pathlib.Path(__file__).parent / "services" / "vision"
    offenders = []
    for path in sorted(root.glob("*.py")):
        body = path.read_text(encoding="utf-8")
        for token in banned:
            if token in body:
                offenders.append(f"{path.name}: {token}")
    assert offenders == [], f"vision must stay on demand: {offenders}"


async def test_the_provider_holds_no_frame_between_calls():
    provider = MockVisionProvider()
    await provider.describe(_request())
    held = [
        name
        for name, value in vars(provider).items()
        if isinstance(value, (bytes, bytearray, ImageSource))
    ]
    assert held == [], f"the provider kept the frame: {held}"


# ---------------------------------------------------------------------------
# The adapter. Every refusal must leave the provider unentered.
# ---------------------------------------------------------------------------

from services.agent_runtime.governance import (  # noqa: E402
    APPROVAL_METADATA_KEY,
    RUNTIME_REQUESTED_BY,
    approval_binding,
    approval_marker,
)
from services.agent_runtime.tools import ToolRegistry, ToolRisk  # noqa: E402
from services.devon.approval import ApprovalQueue  # noqa: E402
from services.vision.agent_adapter import VisionAdapter  # noqa: E402


class _CountingProvider(MockVisionProvider):
    """Records every entry so a refusal can prove it never reached the wire."""

    def __init__(self) -> None:
        super().__init__()
        self.calls = 0

    async def describe(self, request: VisionRequest):
        self.calls += 1
        return await super().describe(request)


def _approved(approvals, args, *, tool="vision.describe"):
    binding = approval_binding(
        task_id="TASK-V", step_id="STEP-1", tool_name=tool, arguments=args
    )
    record, token = approvals.request(
        title="Describe an image",
        what_happens=f"Send one frame off the host. {approval_marker(binding)}",
        requested_by=RUNTIME_REQUESTED_BY,
    )
    assert approvals.decide(record.request_id, token, "approve").approved is True
    return {
        "request_id": record.request_id,
        "binding": binding,
        "task_id": "TASK-V",
        "step_id": "STEP-1",
        "tool_name": tool,
    }


def _registry(tmp_path, provider):
    approvals = ApprovalQueue()
    registry = ToolRegistry()
    VisionAdapter(
        approvals, provider_factory=lambda: provider, image_root=str(tmp_path)
    ).register(registry)
    return approvals, registry


def _write_png(tmp_path, name="shot.png", data=PNG):
    target = tmp_path / name
    target.write_bytes(data)
    return target


def test_the_spec_is_write_and_irreversible():
    registry = ToolRegistry()
    VisionAdapter(None, provider_factory=MockVisionProvider, image_root="/tmp").register(
        registry
    )
    spec = registry.get("vision.describe")
    assert spec.risk is ToolRisk.WRITE
    assert spec.approval_required is True
    assert spec.reversible is False
    assert spec.parameters == ("image_path", "prompt")
    # A provider argument would let the model choose where a private frame goes.
    assert "provider" not in spec.parameters


async def test_it_refuses_without_approval_metadata_and_never_calls_out(tmp_path):
    provider = _CountingProvider()
    _write_png(tmp_path)
    _approvals, registry = _registry(tmp_path, provider)
    result = await registry.execute("vision.describe", {"image_path": "shot.png"})
    assert result.ok is False
    assert provider.calls == 0


async def test_it_refuses_a_replayed_approval(tmp_path):
    provider = _CountingProvider()
    _write_png(tmp_path)
    approvals, registry = _registry(tmp_path, provider)
    args = {"image_path": "shot.png", "prompt": "what is this"}
    metadata = _approved(approvals, args)

    first = await registry.execute(
        "vision.describe", {**args, APPROVAL_METADATA_KEY: metadata}
    )
    assert first.ok is True, first.error
    assert provider.calls == 1

    second = await registry.execute(
        "vision.describe", {**args, APPROVAL_METADATA_KEY: metadata}
    )
    assert second.ok is False
    assert provider.calls == 1, "a replayed approval reached the provider"


async def test_it_refuses_arguments_that_changed_after_the_card(tmp_path):
    provider = _CountingProvider()
    _write_png(tmp_path)
    _write_png(tmp_path, name="other.png")
    approvals, registry = _registry(tmp_path, provider)
    metadata = _approved(approvals, {"image_path": "shot.png", "prompt": "a"})
    result = await registry.execute(
        "vision.describe",
        {"image_path": "other.png", "prompt": "a", APPROVAL_METADATA_KEY: metadata},
    )
    assert result.ok is False
    assert "does not match these arguments" in result.error
    assert provider.calls == 0


@pytest.mark.parametrize(
    "image_path,fragment",
    [
        ("/etc/passwd", "absolute paths are refused"),
        ("../../etc/passwd", "escapes VISION_IMAGE_ROOT"),
        ("", "image_path is required"),
        ("missing.png", "no such image under the root"),
    ],
)
async def test_it_refuses_bad_paths_without_calling_out(tmp_path, image_path, fragment):
    provider = _CountingProvider()
    approvals, registry = _registry(tmp_path, provider)
    args = {"image_path": image_path, "prompt": "p"}
    metadata = _approved(approvals, args)
    result = await registry.execute(
        "vision.describe", {**args, APPROVAL_METADATA_KEY: metadata}
    )
    assert result.ok is False
    assert fragment in result.error
    assert provider.calls == 0


async def test_it_refuses_an_unsupported_extension(tmp_path):
    provider = _CountingProvider()
    (tmp_path / "notes.pdf").write_bytes(b"%PDF-1.4 not an image")
    approvals, registry = _registry(tmp_path, provider)
    args = {"image_path": "notes.pdf", "prompt": "p"}
    metadata = _approved(approvals, args)
    result = await registry.execute(
        "vision.describe", {**args, APPROVAL_METADATA_KEY: metadata}
    )
    assert result.ok is False
    assert "unsupported image extension" in result.error
    assert provider.calls == 0


async def test_it_refuses_over_the_byte_ceiling(tmp_path):
    provider = _CountingProvider()
    _write_png(tmp_path, data=b"\x89PNG" + b"x" * 200)
    approvals = ApprovalQueue()
    registry = ToolRegistry()
    VisionAdapter(
        approvals,
        provider_factory=lambda: provider,
        image_root=str(tmp_path),
        max_image_bytes=32,
    ).register(registry)
    args = {"image_path": "shot.png", "prompt": "p"}
    metadata = _approved(approvals, args)
    result = await registry.execute(
        "vision.describe", {**args, APPROVAL_METADATA_KEY: metadata}
    )
    assert result.ok is False
    assert "ceiling is 32" in result.error
    assert provider.calls == 0


async def test_it_refuses_when_the_image_root_is_unset(tmp_path):
    provider = _CountingProvider()
    _write_png(tmp_path)
    approvals = ApprovalQueue()
    registry = ToolRegistry()
    VisionAdapter(
        approvals, provider_factory=lambda: provider, image_root=""
    ).register(registry)
    args = {"image_path": "shot.png", "prompt": "p"}
    metadata = _approved(approvals, args)
    result = await registry.execute(
        "vision.describe", {**args, APPROVAL_METADATA_KEY: metadata}
    )
    assert result.ok is False
    assert "VISION_IMAGE_ROOT is not set" in result.error
    assert provider.calls == 0


async def test_a_text_only_backend_refuses_rather_than_sending(tmp_path):
    class _TextOnly(_CountingProvider):
        supports_images = False

    provider = _TextOnly()
    _write_png(tmp_path)
    approvals, registry = _registry(tmp_path, provider)
    args = {"image_path": "shot.png", "prompt": "p"}
    metadata = _approved(approvals, args)
    result = await registry.execute(
        "vision.describe", {**args, APPROVAL_METADATA_KEY: metadata}
    )
    assert result.ok is False
    assert "does not accept images" in result.error
    assert provider.calls == 0


async def test_the_happy_path_returns_text_and_a_flat_non_secret_receipt(tmp_path):
    provider = _CountingProvider()
    _write_png(tmp_path)
    approvals, registry = _registry(tmp_path, provider)
    args = {"image_path": "shot.png", "prompt": "what is on this screen"}
    metadata = _approved(approvals, args)
    result = await registry.execute(
        "vision.describe", {**args, APPROVAL_METADATA_KEY: metadata}
    )

    assert result.ok is True, result.error
    assert isinstance(result.output, str) and result.output
    meta = result.metadata or {}
    assert meta["image_sha256"] == _image().digest
    assert meta["image_bytes"] == len(PNG)
    assert meta["provider_receipt_id"] == metadata["request_id"]
    # Flat and free of bytes: sanitize_receipt_payload does not recurse.
    assert all(not isinstance(v, (dict, list, bytes)) for v in meta.values())
    assert not any("base64" in str(v).lower() for v in meta.values())


async def test_the_adapter_holds_no_frame_between_calls(tmp_path):
    provider = _CountingProvider()
    _write_png(tmp_path)
    approvals = ApprovalQueue()
    registry = ToolRegistry()
    adapter = VisionAdapter(
        approvals, provider_factory=lambda: provider, image_root=str(tmp_path)
    )
    adapter.register(registry)
    args = {"image_path": "shot.png", "prompt": "p"}
    await registry.execute(
        "vision.describe", {**args, APPROVAL_METADATA_KEY: _approved(approvals, args)}
    )
    held = [
        name
        for name, value in vars(adapter).items()
        if isinstance(value, (bytes, bytearray, ImageSource))
    ]
    assert held == [], f"the adapter kept the frame: {held}"


async def test_it_reads_the_file_at_call_time_rather_than_caching(tmp_path):
    captured = []

    class _Recorder(MockVisionProvider):
        async def describe(self, request: VisionRequest):
            captured.append(request.image.digest)
            return await super().describe(request)

    provider = _Recorder()
    target = _write_png(tmp_path)
    approvals, registry = _registry(tmp_path, provider)

    args = {"image_path": "shot.png", "prompt": "p"}
    await registry.execute(
        "vision.describe", {**args, APPROVAL_METADATA_KEY: _approved(approvals, args)}
    )
    target.write_bytes(b"\x89PNG\r\n\x1a\n" + b"different pixels entirely")
    await registry.execute(
        "vision.describe", {**args, APPROVAL_METADATA_KEY: _approved(approvals, args)}
    )

    assert len(captured) == 2
    assert captured[0] != captured[1], "the adapter cached the first frame"


# ---------------------------------------------------------------------------
# The risk ruling, made executable
# ---------------------------------------------------------------------------

async def test_the_gate_stops_in_both_presence_lanes():
    """WRITE plus reversible False is what makes this stop, in both lanes.

    READ would not. It returns RUN before the reversibility branch is reached,
    which is the same as no card, no confirm and no effect receipt.
    """
    from services.agent_runtime import presence

    registry = ToolRegistry()
    VisionAdapter(None, provider_factory=MockVisionProvider, image_root="/tmp").register(
        registry
    )
    spec = registry.get("vision.describe")

    assert presence.decide(spec, presence.Caller.human("tee")) is presence.PresenceDecision.CONFIRM
    assert presence.decide(spec, presence.Caller.automated()) is presence.PresenceDecision.CARD
    # The reason a gate gives has to be true, or it teaches him to stop reading it.
    assert presence.confirm_reason(spec) == "cannot be undone"


def test_vision_is_not_listed_in_always_confirm_or_a_guarded_prefix():
    """Deliberately absent from both tripwires, and the reasons are checked.

    `test_devon_presence_authority.py` asserts ALWAYS_CONFIRM_TOOLS is disjoint
    from the live registry, so listing it there would redden CI. The declared
    reversibility is what stops this tool, not a name on a list.
    """
    from services.agent_runtime import presence
    from test_devon_presence_authority import GUARDED_PREFIXES

    assert "vision.describe" not in set(presence.ALWAYS_CONFIRM_TOOLS)
    assert not "vision.describe".startswith(GUARDED_PREFIXES)
