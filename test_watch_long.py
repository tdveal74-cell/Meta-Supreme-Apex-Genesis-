"""The watch-long house skill: window planning, SSE parsing, the length estimate,
the past-the-end tail, and the report, all without a network.

The script lives under .claude/skills/watch-long/scripts so it is loaded from
its path here. Every network call is monkeypatched: these tests prove the
arithmetic and the report's honesty, not Gemini.
"""

import importlib.util
import json
import pathlib
import sys

import pytest

SCRIPT = pathlib.Path(__file__).parent / ".claude" / "skills" / "watch-long" / "scripts" / "watch_long.py"


@pytest.fixture(scope="module")
def wl():
    spec = importlib.util.spec_from_file_location("watch_long", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    sys.modules["watch_long"] = module
    spec.loader.exec_module(module)
    return module


def _sse(*texts, usage=None, finish="STOP"):
    lines = []
    for i, text in enumerate(texts):
        chunk = {"candidates": [{"content": {"parts": [{"text": text}]}}]}
        if i == len(texts) - 1:
            chunk["candidates"][0]["finishReason"] = finish
            if usage:
                chunk["usageMetadata"] = usage
        lines.append("data: " + json.dumps(chunk))
    return "\r\n\r\n".join(lines) + "\r\n"


def test_windows_cover_the_whole_length_and_the_last_one_is_shorter(wl):
    assert wl.plan_windows(2148, 600) == [(0, 600), (600, 1200), (1200, 1800), (1800, 2148)]
    assert wl.plan_windows(600, 600) == [(0, 600)]
    assert wl.plan_windows(1, 600) == [(0, 1)]
    with pytest.raises(ValueError):
        wl.plan_windows(0, 600)
    with pytest.raises(ValueError):
        wl.plan_windows(100, 0)


def test_the_length_estimate_uses_the_measured_token_rate_and_rounds_up(wl):
    # 161,100 VIDEO tokens was a 2,148 s video on 2026-10-28, 75.0 per second.
    assert wl.estimate_duration(161100) == 2148
    assert wl.estimate_duration(161101) == 2149
    assert wl.VIDEO_TOKENS_PER_SECOND == 75.0
    with pytest.raises(ValueError):
        wl.estimate_duration(0)


def test_the_video_count_is_read_from_the_modality_breakdown(wl):
    data = {
        "totalTokens": 225571,
        "promptTokensDetails": [
            {"modality": "TEXT", "tokenCount": 31},
            {"modality": "VIDEO", "tokenCount": 161100},
        ],
    }
    assert wl.video_tokens_from_count(data) == 161100
    assert wl.video_tokens_from_count({"totalTokens": 5}) is None
    assert wl.video_tokens_from_count({"promptTokensDetails": [{"modality": "VIDEO"}]}) is None


def test_sse_parts_join_in_order_and_carry_usage_and_finish(wl):
    body = _sse("Here ", "are the ", "chapters.", usage={"promptTokenCount": 7, "candidatesTokenCount": 3})
    text, usage, finish = wl.parse_sse(body)
    assert text == "Here are the chapters."
    assert usage == {"promptTokenCount": 7, "candidatesTokenCount": 3}
    assert finish == "STOP"
    assert wl.parse_sse("") == ("", {}, None)
    assert wl.parse_sse("data: not json\n") == ("", {}, None)


def test_clock_and_youtube_detection(wl):
    assert wl.clock(0) == "00:00"
    assert wl.clock(2148) == "35:48"
    assert wl.clock(15042) == "4:10:42"
    assert wl.is_youtube("https://www.youtube.com/watch?v=ntDIxaeo3Wg")
    assert wl.is_youtube("https://www.youtube.com/shorts/JXLejkaa79M")
    assert wl.is_youtube("https://youtu.be/ntDIxaeo3Wg")
    assert not wl.is_youtube("https://vimeo.com/12345")
    assert not wl.is_youtube("/tmp/local.mp4")


def test_a_window_past_the_end_is_dropped_and_the_tail_is_read_past_the_estimate(wl, monkeypatch, tmp_path):
    """The estimate says 1,150 s, the video is really 1,300 s. The planned windows
    are 0-600, 600-1150; the extension reads 1150-1750 (clamped by Google) and
    then 1750-2350 answers 400, which ends the run without counting as a failure."""
    calls = []

    def fake_count(source, *, model, key, timeout):
        return 1150 * 75

    def fake_stream(payload, *, model, key, timeout):
        part = payload["contents"][0]["parts"][0]
        if "file_data" in part:
            start = int(part["video_metadata"]["start_offset"].rstrip("s"))
            calls.append(start)
            if start >= 1300:
                raise wl.PastEnd("HTTP 400: Request contains an invalid argument.")
            return f"notes from {start}", {"promptTokenCount": 10, "candidatesTokenCount": 2}, 1.0
        return "final synthesis", {}, 0.5

    monkeypatch.setattr(wl, "count_video_tokens", fake_count)
    monkeypatch.setattr(wl, "stream_generate", fake_stream)
    monkeypatch.setenv("GEMINI_API_KEY", "placeholder")
    out = tmp_path / "report.md"
    args = wl.build_parser().parse_args(
        ["https://www.youtube.com/watch?v=abc123", "--window", "600", "--parallel", "1", "--out", str(out)]
    )
    report = wl.run(args)
    assert calls == [0, 600, 1150, 1750]
    assert [(w.start, w.end) for w in report.windows] == [(0, 600), (600, 1150), (1150, 1750)]
    assert all(w.ok for w in report.windows)
    assert report.synthesis == "final synthesis"
    text = wl.render(report)
    assert "Length: 19:10 (1150s, estimated from 86250 video tokens" in text
    assert "Covered: 29:10 across 3 windows" in text
    assert "Unavailable evidence" not in text
    assert "### 19:10 to 29:10" in text


def test_a_failed_window_is_reported_as_unavailable_not_filled_in(wl, monkeypatch):
    def fake_count(source, *, model, key, timeout):
        return 600 * 75

    def fake_stream(payload, *, model, key, timeout):
        part = payload["contents"][0]["parts"][0]
        if "file_data" in part:
            start = int(part["video_metadata"]["start_offset"].rstrip("s"))
            if start == 0:
                raise RuntimeError("HTTP 502: upstream request failed")
            raise wl.PastEnd("HTTP 400: Request contains an invalid argument.")
        return "synthesis over the notes", {}, 0.5

    monkeypatch.setattr(wl, "count_video_tokens", fake_count)
    monkeypatch.setattr(wl, "stream_generate", fake_stream)
    monkeypatch.setenv("GEMINI_API_KEY", "placeholder")
    args = wl.build_parser().parse_args(["https://youtu.be/abc123", "--parallel", "1"])
    report = wl.run(args)
    assert len(report.windows) == 1
    assert not report.windows[0].ok
    assert report.windows[0].error == "attempt 2: HTTP 502: upstream request failed"
    assert report.synthesis == ""  # nothing readable, so no synthesis was attempted
    text = wl.render(report)
    assert "## Unavailable evidence" in text
    assert "- 00:00 to 10:00: attempt 2: HTTP 502: upstream request failed" in text
    assert "Synthesis unavailable: not run" in text


def test_the_key_must_exist_and_the_source_must_be_youtube(wl, monkeypatch):
    monkeypatch.delenv("GEMINI_API_KEY", raising=False)
    args = wl.build_parser().parse_args(["https://www.youtube.com/watch?v=abc123"])
    with pytest.raises(SystemExit, match="GEMINI_API_KEY is not set"):
        wl.run(args)
    monkeypatch.setenv("GEMINI_API_KEY", "placeholder")
    args = wl.build_parser().parse_args(["/tmp/local.mp4"])
    with pytest.raises(SystemExit, match="YouTube URLs only"):
        wl.run(args)


def test_the_model_defaults_to_the_environment_then_argon(wl, monkeypatch):
    monkeypatch.delenv("WATCH_GEMINI_MODEL", raising=False)
    assert wl.build_parser().parse_args(["u"]).model == "gemini-4-argon"
    monkeypatch.setenv("WATCH_GEMINI_MODEL", "gemini-3.7-flash")
    assert wl.build_parser().parse_args(["u"]).model == "gemini-3.7-flash"
    assert wl.build_parser().parse_args(["u", "--model", "x"]).model == "x"
