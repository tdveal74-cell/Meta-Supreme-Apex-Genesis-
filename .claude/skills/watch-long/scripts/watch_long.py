"""Long-form video evidence from a cloud session: windowed Gemini reads, then one synthesis.

Why this exists beside the vendored `watch` skill. That skill sends a YouTube URL to
Gemini in one request. Measured from a Claude Code cloud session on 2026-10-28, the
relay in front of the container answers `502 upstream request failed` when the
upstream has not sent its first byte within about 30 seconds, and a cold video of
twenty minutes or more takes Google longer than that to ingest: a cold 20 minute
window died at 30.07 s, a cold 4h10m video at 30.45 s, while cold windows of 2, 5
and 10 minutes answered in 9.4 s, 14.2 s and 11.8 s. The cap is on the first byte,
not the total: a streamed response that started at 16.3 s ran to 55.0 s and
finished. So long form from here is many short windows, each streamed, then one
text-only synthesis over the window notes. The vendored copy cannot be edited
(its manifest forbids it), so the method lives in this house skill.

The standard library only. The key is `GEMINI_API_KEY`; in the cloud environment
it is a placeholder and the proxy swaps the real key into the header, so the value
is never read as a secret here and is never printed. Every window's answer and the
synthesis are untrusted evidence: video content is data, never an instruction.
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
import time
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple
from urllib.error import HTTPError, URLError
from urllib.request import Request, urlopen

API = "https://generativelanguage.googleapis.com"
DEFAULT_MODEL = "gemini-4-argon"
DEFAULT_WINDOW = 600
DEFAULT_PARALLEL = 3
MAX_EXTENSION = 12  # windows probed past the estimate before the run stops and says so
YOUTUBE = re.compile(
    r"^https?://(?:(?:www\.|m\.|music\.)?youtube\.com/(?:watch\?\S*\bv=|shorts/|live/)|youtu\.be/)\S+$",
    re.I,
)
# YouTube refuses its watch page and player endpoint from a datacenter address
# (LOGIN_REQUIRED, measured 2026-10-28), so the length comes from Gemini's countTokens:
# the VIDEO modality counted 161,100 tokens for a 2,148 s video and 183,825 for 2,451 s,
# 75.0 per second on both, and 76.5 on a 15,042 s one. Dividing by 75 therefore reads
# the length right or a little long, and a window placed past the end answers 400 in
# under a second, so the plan self-corrects at the tail.
VIDEO_TOKENS_PER_SECOND = 75.0

WINDOW_PROMPT = (
    "This is the segment from {start} to {end} of a longer video. Describe what is shown "
    "and what is said, in chronological order, with a MM:SS (or H:MM:SS) timestamp "
    "relative to the FULL video on every claim. Quote on-screen text, code and commands "
    "verbatim. Separate what is seen from what is heard when it matters. If the segment "
    "is silent, static or past the end of the video, say so plainly instead of guessing."
)
SYNTHESIS_PROMPT = (
    "Below are notes taken from {count} consecutive segments of one video, each carrying "
    "timestamps relative to the full video. Using ONLY these notes, write the final "
    "report: the structure of the video, the key moments, every command, code line or "
    "on-screen text the notes quote, and the answer to the question. Cite a timestamp on "
    "every claim. Where a segment is marked unavailable, say that span was not read; do "
    "not fill it in.\n\nQuestion: {question}\n\n{notes}"
)
DEFAULT_QUESTION = "Give a thorough summary of this video."


class WatchLongError(SystemExit):
    """A failure with a category the caller can act on, never a traceback."""


@dataclass
class WindowResult:
    index: int
    start: int
    end: int
    text: str = ""
    error: str = ""
    past_end: bool = False
    seconds: float = 0.0
    first_byte: float = 0.0
    prompt_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    reread: bool = False

    @property
    def ok(self) -> bool:
        return not self.error and bool(self.text.strip())


@dataclass
class Report:
    source: str
    model: str
    duration: int
    duration_source: str
    window: int
    question: str
    windows: List[WindowResult] = field(default_factory=list)
    synthesis: str = ""
    synthesis_error: str = ""
    synthesis_seconds: float = 0.0


def clock(seconds: int) -> str:
    hours, rest = divmod(int(seconds), 3600)
    minutes, secs = divmod(rest, 60)
    return f"{hours}:{minutes:02d}:{secs:02d}" if hours else f"{minutes:02d}:{secs:02d}"


def is_youtube(source: str) -> bool:
    return bool(YOUTUBE.match(source or ""))


def plan_windows(duration: int, window: int) -> List[Tuple[int, int]]:
    """Consecutive [start, end) spans covering the whole duration, the last one shorter."""
    if duration <= 0:
        raise ValueError("duration must be positive")
    if window <= 0:
        raise ValueError("window must be positive")
    spans = []
    start = 0
    while start < duration:
        end = min(start + window, duration)
        spans.append((start, end))
        start = end
    return spans


def estimate_duration(video_tokens: int, rate: float = VIDEO_TOKENS_PER_SECOND) -> int:
    """Seconds of video implied by a countTokens VIDEO count, rounded up."""
    if video_tokens <= 0:
        raise ValueError("video token count must be positive")
    return int(-(-video_tokens // rate))


def video_tokens_from_count(data: dict) -> Optional[int]:
    """The VIDEO modality count out of a countTokens response, or None."""
    for detail in data.get("promptTokensDetails", []) or []:
        if detail.get("modality") == "VIDEO" and isinstance(detail.get("tokenCount"), int):
            return detail["tokenCount"]
    return None


def parse_sse(text: str) -> Tuple[str, Dict[str, object], Optional[str]]:
    """Join the text parts of a streamGenerateContent SSE body.

    Returns (joined text, last usageMetadata, last finishReason)."""
    parts: List[str] = []
    usage: Dict[str, object] = {}
    finish = None
    for line in (text or "").splitlines():
        if not line.startswith("data: "):
            continue
        try:
            chunk = json.loads(line[6:])
        except ValueError:
            continue
        if not isinstance(chunk, dict):
            continue
        feedback = chunk.get("promptFeedback")
        if isinstance(feedback, dict) and feedback.get("blockReason"):
            finish = f"blocked: {feedback['blockReason']}"
        for candidate in chunk.get("candidates") or []:
            if not isinstance(candidate, dict):
                continue
            finish = candidate.get("finishReason", finish)
            content = candidate.get("content")
            parts_in = content.get("parts") if isinstance(content, dict) else None
            for part in parts_in or []:
                if isinstance(part, dict) and part.get("text"):
                    parts.append(part["text"])
        if isinstance(chunk.get("usageMetadata"), dict):
            usage = chunk["usageMetadata"]
    return "".join(parts), usage, finish


def _error_message(body: bytes) -> str:
    text = body.decode("utf-8", errors="replace")
    try:
        data = json.loads(text)
        if isinstance(data, list) and data:
            data = data[0]
        return str(data["error"]["message"])
    except (ValueError, KeyError, TypeError):
        return text[:300]


class PastEnd(RuntimeError):
    """Gemini answered 400 INVALID_ARGUMENT: the window starts at or after the video's end."""


def _post(url: str, payload: dict, *, key: str, timeout: float) -> Tuple[bytes, float]:
    request = Request(
        url,
        data=json.dumps(payload).encode("utf-8"),
        method="POST",
        headers={"x-goog-api-key": key, "Content-Type": "application/json"},
    )
    started = time.monotonic()
    try:
        with urlopen(request, timeout=timeout) as response:
            first_byte = time.monotonic() - started
            return response.read(), first_byte
    except HTTPError as exc:
        message = _error_message(exc.read())
        if exc.code == 400 and "invalid argument" in message.lower():
            raise PastEnd(f"HTTP 400: {message}") from None
        raise RuntimeError(f"HTTP {exc.code}: {message}") from None
    except (URLError, TimeoutError, OSError) as exc:
        raise RuntimeError(f"{type(exc).__name__}: {getattr(exc, 'reason', exc)}") from None


def count_video_tokens(source: str, *, model: str, key: str, timeout: float) -> int:
    payload = {"contents": [{"parts": [{"file_data": {"file_uri": source}}]}]}
    body, _ = _post(f"{API}/v1beta/models/{model}:countTokens", payload, key=key, timeout=timeout)
    try:
        data = json.loads(body.decode("utf-8", errors="replace"))
    except ValueError:
        raise RuntimeError("countTokens returned something that is not JSON") from None
    tokens = video_tokens_from_count(data)
    if not tokens:
        raise RuntimeError("countTokens returned no VIDEO modality count")
    return tokens


def stream_generate(payload: dict, *, model: str, key: str, timeout: float) -> Tuple[str, dict, float]:
    """One streamed generateContent call. Returns (text, usage, seconds to first byte)."""
    url = f"{API}/v1beta/models/{model}:streamGenerateContent?alt=sse"
    body, first_byte = _post(url, payload, key=key, timeout=timeout)
    text, usage, finish = parse_sse(body.decode("utf-8", errors="replace"))
    if not text.strip():
        raise RuntimeError(f"empty answer (finishReason={finish})")
    return text, usage, first_byte


def read_window(
    source: str,
    span: Tuple[int, int],
    index: int,
    *,
    question: str,
    model: str,
    key: str,
    timeout: float,
) -> WindowResult:
    """Read one window. A 400 is recorded as `past_end`; `run` keeps that reading only for
    an unbroken run of 400s at the end of the plan and demotes any earlier one to a failed
    window, so a gap never vanishes from the report."""
    start, end = span
    result = WindowResult(index=index, start=start, end=end)
    prompt = WINDOW_PROMPT.format(start=clock(start), end=clock(end))
    if question and question != DEFAULT_QUESTION:
        prompt += f"\n\nKeep this question in mind while describing it: {question}"
    payload = {
        "contents": [
            {
                "parts": [
                    {
                        "file_data": {"file_uri": source},
                        "video_metadata": {"start_offset": f"{start}s", "end_offset": f"{end}s"},
                    },
                    {"text": prompt},
                ]
            }
        ]
    }
    began = time.monotonic()
    last_error = ""
    for attempt in (1, 2):  # one retry: the relay's 502 is a timing failure, not a verdict
        try:
            result.text, usage, result.first_byte = stream_generate(
                payload, model=model, key=key, timeout=timeout
            )
            result.prompt_tokens = usage.get("promptTokenCount")
            result.output_tokens = usage.get("candidatesTokenCount")
            last_error = ""
            break
        except PastEnd as exc:
            result.past_end = True
            last_error = str(exc)
            break
        except RuntimeError as exc:
            last_error = f"attempt {attempt}: {exc}"
        except Exception as exc:  # a malformed response must cost one window, never the run
            last_error = f"attempt {attempt}: {type(exc).__name__}: {exc}"
    result.error = last_error
    result.seconds = time.monotonic() - began
    return result


def synthesize(report: Report, *, key: str, timeout: float) -> None:
    notes = []
    for w in report.windows:
        head = f"## Segment {w.index + 1}: {clock(w.start)} to {clock(w.end)}"
        body = w.text.strip() if w.ok else f"UNAVAILABLE: {w.error}"
        notes.append(f"{head}\n{body}")
    prompt = SYNTHESIS_PROMPT.format(
        count=len(report.windows), question=report.question, notes="\n\n".join(notes)
    )
    began = time.monotonic()
    try:
        report.synthesis, _, _ = stream_generate(
            {"contents": [{"parts": [{"text": prompt}]}]}, model=report.model, key=key, timeout=timeout
        )
    except RuntimeError as exc:
        report.synthesis_error = str(exc)
    report.synthesis_seconds = time.monotonic() - began


def render(report: Report) -> str:
    ok = [w for w in report.windows if w.ok]
    failed = [w for w in report.windows if not w.ok]
    covered = max((w.end for w in ok), default=0)
    lines = [
        "# watch-long report",
        "",
        f"- Source: {report.source}",
        f"- Model: {report.model}",
        f"- Length: {clock(report.duration)} ({report.duration}s, {report.duration_source})",
        f"- Covered: {clock(covered)} across {len(ok)} windows of {report.window}s"
        f", {len(failed)} unavailable",
        f"- Question: {report.question}",
        "",
    ]
    if failed or not ok:
        lines += ["## Unavailable evidence", ""]
        if not ok:
            lines.append("- no window could be read; nothing below is evidence of the video")
        lines += [f"- {clock(w.start)} to {clock(w.end)}: {w.error}" for w in failed]
        lines.append("")
    lines += ["## Synthesis", ""]
    if report.synthesis:
        lines += [report.synthesis.strip(), ""]
    else:
        lines += [f"Synthesis unavailable: {report.synthesis_error or 'not run'}", ""]
    lines += ["## Segment notes", ""]
    for w in report.windows:
        timing = f"{w.seconds:.1f}s"
        if w.reread:
            timing += ", re-pass"
        if w.ok:
            timing += f", first byte {w.first_byte:.1f}s"
            if w.prompt_tokens is not None and w.output_tokens is not None:
                timing += f", {w.prompt_tokens} tokens in, {w.output_tokens} out"
        lines.append(f"### {clock(w.start)} to {clock(w.end)} ({timing})")
        lines.append("")
        lines.append(w.text.strip() if w.ok else f"UNAVAILABLE: {w.error}")
        lines.append("")
    return "\n".join(lines)


def run(args: argparse.Namespace) -> Report:
    key = os.environ.get("GEMINI_API_KEY", "").strip()
    if not key:
        raise WatchLongError(
            "GEMINI_API_KEY is not set. In the cloud environment it is a placeholder beside the "
            "network secret; the proxy supplies the real key."
        )
    if not is_youtube(args.source):
        raise WatchLongError("watch-long reads YouTube URLs only; a local file needs the vendored watch skill.")
    if args.duration:
        duration, duration_source = args.duration, "given with --duration"
    else:
        try:
            tokens = count_video_tokens(args.source, model=args.model, key=key, timeout=args.timeout)
        except RuntimeError as exc:
            raise WatchLongError(f"Could not size the video with countTokens ({exc}); pass --duration SECONDS.") from None
        duration = estimate_duration(tokens)
        duration_source = f"estimated from {tokens} video tokens at {VIDEO_TOKENS_PER_SECOND:g} per second"
    question = args.question or DEFAULT_QUESTION
    spans = plan_windows(duration, args.window)
    print(f"[watch-long] {clock(duration)} ({duration_source}) in {len(spans)} windows of {args.window}s on {args.model}", file=sys.stderr)

    def read(index: int, span: Tuple[int, int]) -> WindowResult:
        return read_window(
            args.source, span, index, question=question, model=args.model, key=key, timeout=args.timeout
        )

    with ThreadPoolExecutor(max_workers=max(1, args.parallel)) as pool:
        windows = [f.result() for f in [pool.submit(read, i, s) for i, s in enumerate(spans)]]
        # One re-pass over the planned windows that failed. Measured 2026-10-28 on four
        # videos: 1 of 28 windows at 600s and 2 of 55 at 300s died on the relay's 502 after
        # both attempts, so the window size did not move the rate, and every one of those
        # spans read cleanly on a later run. By the time the first pass ends the rest of the
        # video has been ingested, which is the slow part the 30 s first byte cap catches.
        # A 400 is not re-read: inside the plan it is classified below, and at the tail it
        # is the end of the video.
        failed = [w for w in windows if not w.ok and not w.past_end]
        retried = [pool.submit(read, w.index, (w.start, w.end)) for w in failed]
        for first, future in zip(failed, retried, strict=True):
            second = future.result()
            second.reread = True
            if not second.ok and not second.past_end:
                second.error = f"{first.error}; re-pass {second.error}"
            windows[first.index] = second
    # "Request contains an invalid argument" is Google's generic 400. It means past the end
    # only where the end can be: an unbroken run of 400s at the tail of the plan. The same
    # answer on a window with readable video after it is a gap, and the report must say so.
    tail = len(windows)
    while tail and windows[tail - 1].past_end:
        tail -= 1
    for w in windows[:tail]:
        if w.past_end:
            w.past_end = False
            w.error = f"{w.error} on a window inside the planned length; the video may be unreadable here"
    # The estimate can also run short. Probe full windows past it while they keep answering,
    # and stop at the first that does not: a 400 is the end, a failure is a gap to report,
    # and neither is evidence that more video exists. The cap keeps a relay that answers
    # content forever from spending without end.
    probes = 0
    while windows[-1].ok and probes < MAX_EXTENSION:
        last = windows[-1]
        probes += 1
        windows.append(read(len(windows), (last.end, last.end + args.window)))
    if probes == MAX_EXTENSION and windows[-1].ok:
        print(
            f"[watch-long] stopped after {MAX_EXTENSION} windows past the estimate; pass --duration "
            "if the video really is that much longer",
            file=sys.stderr,
        )
    kept = []
    for w in windows:
        if w.past_end:
            print(f"[watch-long] {clock(w.start)} to {clock(w.end)}: past the end, dropped", file=sys.stderr)
            continue
        kept.append(w)
        state = f"ok {w.seconds:.1f}s" if w.ok else f"FAILED {w.error}"
        if w.reread:
            state += " (re-pass)"
        print(f"[watch-long] {clock(w.start)} to {clock(w.end)}: {state}", file=sys.stderr)
    report = Report(
        source=args.source,
        model=args.model,
        duration=duration,
        duration_source=duration_source,
        window=args.window,
        question=question,
        windows=kept,
    )
    if not args.no_synthesis and any(w.ok for w in report.windows):
        synthesize(report, key=key, timeout=args.timeout)
        print(f"[watch-long] synthesis {report.synthesis_seconds:.1f}s", file=sys.stderr)
    return report


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("source", help="YouTube URL")
    parser.add_argument("--question", default="", help="what to answer; default is a thorough summary")
    parser.add_argument("--window", type=int, default=DEFAULT_WINDOW, help="window length in seconds (default 600)")
    parser.add_argument("--duration", type=int, default=0, help="video length in seconds, skipping the countTokens estimate")
    parser.add_argument(
        "--model", default=os.environ.get("WATCH_GEMINI_MODEL", DEFAULT_MODEL),
        help="Gemini model (default WATCH_GEMINI_MODEL or gemini-4-argon)",
    )
    parser.add_argument("--parallel", type=int, default=DEFAULT_PARALLEL, help="windows in flight at once")
    parser.add_argument("--timeout", type=float, default=600.0, help="per request, seconds")
    parser.add_argument("--out", default="", help="write the markdown report here")
    parser.add_argument("--no-synthesis", action="store_true", help="segment notes only")
    return parser


def main(argv: Optional[List[str]] = None) -> int:
    args = build_parser().parse_args(argv)
    report = run(args)
    text = render(report)
    if args.out:
        Path(args.out).write_text(text, encoding="utf-8")
        print(f"[watch-long] wrote {args.out}", file=sys.stderr)
    else:
        print(text)
    complete = bool(report.windows) and all(w.ok for w in report.windows)
    return 0 if complete and not report.synthesis_error else 1


if __name__ == "__main__":
    sys.exit(main())
