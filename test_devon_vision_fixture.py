"""The one frame allowed into this public repository, and why it stays honest.

`.gitignore` keeps frames out of `var/vision-inbox` because a frame is whatever
was on somebody's screen. `devon-vision-test.png` is the named exception, ruled
2026-09-16, and it earns that only while it is GENERATED rather than captured.

The test that matters here is the byte-identity one: regenerate the frame from
`scripts/make_vision_test_frame.py` and compare. A real screenshot dropped in
under this filename fails it immediately, which is the point. Without that,
"the exception is synthetic" would be a comment rather than a fact.

The fixture exists because a deployed container has no other way to get a frame.
Nothing writes into the inbox at runtime and a Railway disk is wiped each
deploy, so this is what the deployed `vision.describe` reads when proving the
OpenRouter key works.
"""

from __future__ import annotations

import hashlib
import importlib.util
import pathlib
import struct
import subprocess

import pytest

from services.vision.base import ALLOWED_MEDIA_TYPES, DEFAULT_MAX_IMAGE_BYTES

ROOT = pathlib.Path(__file__).resolve().parent
FRAME = ROOT / "var" / "vision-inbox" / "devon-vision-test.png"
GENERATOR = ROOT / "scripts" / "make_vision_test_frame.py"


def _load_generator():
    spec = importlib.util.spec_from_file_location("make_vision_test_frame", GENERATOR)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_the_frame_and_its_generator_both_exist():
    assert FRAME.is_file(), "the deployed vision tool has no frame to read"
    assert GENERATOR.is_file(), ".gitignore names a generator that is not here"


def test_the_frame_is_generated_not_captured():
    """The whole basis of the exception. A screenshot fails this."""
    rendered = _load_generator().render()
    on_disk = FRAME.read_bytes()
    assert hashlib.sha256(rendered).hexdigest() == hashlib.sha256(on_disk).hexdigest(), (
        "var/vision-inbox/devon-vision-test.png is not what the generator "
        "produces. The exception in .gitignore only covers a generated frame, "
        "so either regenerate it or do not commit it."
    )


def test_the_frame_passes_the_guards_vision_describe_applies():
    data = FRAME.read_bytes()
    assert data[:8] == b"\x89PNG\r\n\x1a\n", "not a PNG, so the media type guard refuses it"
    width, height = struct.unpack(">II", data[16:24])
    assert (width, height) == (480, 240)
    assert "image/png" in ALLOWED_MEDIA_TYPES
    assert len(data) < DEFAULT_MAX_IMAGE_BYTES, "over the byte ceiling"
    assert FRAME.suffix == ".png"


def test_the_frame_is_tracked_and_every_other_frame_is_not():
    """The exception is ONE filename, not a hole in the rule."""
    tracked = subprocess.run(
        ["git", "ls-files", "--error-unmatch", str(FRAME.relative_to(ROOT))],
        cwd=ROOT, capture_output=True, text=True,
    )
    if tracked.returncode != 0:
        pytest.skip("frame not committed yet; nothing to assert about tracking")

    ignored = subprocess.run(
        ["git", "check-ignore", "var/vision-inbox/a-real-screenshot.png"],
        cwd=ROOT, capture_output=True, text=True,
    )
    assert ignored.returncode == 0, (
        "a screenshot dropped in the inbox would be committable, and this "
        "repository is public"
    )
