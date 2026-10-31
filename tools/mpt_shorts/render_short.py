"""Render one vertical Short with MoneyPrinterTurbo as an assembler only.

MoneyPrinterTurbo (harry0703/MoneyPrinterTurbo, audited at MPT_COMMIT) can turn a
keyword into a finished video: an LLM writes the script, a stock voice reads it,
stock clips are matched to it and a random song goes under it. That flow is the
template YouTube's inauthentic content policy refuses to monetize, and its voice
breaks the owned-voice rule. This wrapper allows exactly one other flow: our own
script, our own voiceover file and our own local clips, assembled in the order
given, captioned on the box by a local Whisper model, one video per run.

It refuses before anything renders when the install carries a provider
credential, can cross-post, listens beyond loopback or would download a caption
model; when the voiceover, the clips or the script are missing or unusable; when
the clips are shorter than the voiceover, which would make MoneyPrinterTurbo
loop footage; and when the script repeats an earlier render of another episode.
After the render it checks the file it got and writes a manifest. It never
publishes anything: a human watches the result end to end before it goes out.

Run with the python of this repository; it only calls MoneyPrinterTurbo's own
python as a child process, under an environment holding nothing but PATH, HOME
and LANG, so no provider key in the caller's environment reaches it.
"""

from __future__ import annotations

import argparse
import difflib
import fcntl
import hashlib
import json
import math
import os
import re
import secrets
import shutil
import subprocess
import sys
import tomllib
import uuid
from datetime import datetime, timezone
from pathlib import Path

MPT_COMMIT = "27843a994bfa29c43c02150861d51490a6ca4bd2"
WHISPER_MODEL = "base.en"
MAX_VOICE_S = 180.0  # YouTube Shorts run to three minutes
DURATION_TOLERANCE_S = 0.35
MIN_SIDE_PX = 480  # MoneyPrinterTurbo drops smaller sources
REPEAT_THRESHOLD = 0.5  # starting value, set from the ledger once real renders exist
# Both shares of matched words must clear this. Measured 2026-10-31 on a Piper
# fixture: the full take 0.944 and 0.944, the first 62 percent of it 0.606 of
# the script, the take plus another script's speech 0.563 of what was said.
VOICE_COVERAGE_MIN = 0.85
SCRUBBED_PATH = "/usr/local/bin:/usr/bin:/bin"
# Whisper writes small numbers as digits, a TTS-ready script spells them out.
NUMBER_WORDS = {w: str(i) for i, w in enumerate(
    "zero one two three four five six seven eight nine ten eleven twelve thirteen "
    "fourteen fifteen sixteen seventeen eighteen nineteen twenty".split())}

# MoneyPrinterTurbo's subtitle.correct() rewrites Whisper's text with the
# script's lines, so its captions always read as the script even over the wrong
# voiceover. The voiceover is therefore transcribed here, before the render,
# with the same local model, and compared with the script.
TRANSCRIBE = (
    "import json, sys\n"
    "from faster_whisper import WhisperModel\n"
    "model = WhisperModel(sys.argv[1], device='cpu', compute_type='int8')\n"
    "segments, _ = model.transcribe(sys.argv[2], language='en')\n"
    "print(json.dumps(' '.join(s.text.strip() for s in segments)))\n"
)
EPISODE = re.compile(r"[A-Za-z0-9][A-Za-z0-9._-]{0,63}")
SHOW = re.compile(r"[a-z0-9][a-z0-9-]{1,31}")
CREDENTIAL = re.compile(r"(^|_)(api_keys?|api_token|key|keys|secret|token|password)$")
LOOPBACK = frozenset(("127.0.0.1", "::1", "localhost"))
AUDIO_EXT = frozenset((".mp3", ".wav", ".m4a", ".aac", ".flac", ".ogg"))
VIDEO_EXT = frozenset((".mp4", ".mov", ".mkv", ".webm"))
FONT_EXT = frozenset((".ttf",))  # cli.py accepts .ttf or .ttc only
# The bundled caption fonts carry no licence and two are named after Apple and
# Microsoft system fonts, so captions use a font whose licence sits beside it.
FONT_LICENCE = re.compile(r"(OFL|LICEN[CS]E)[^/]*\.(txt|md)", re.IGNORECASE)

# Section-aware edits that turn config.example.toml into the locked config.
# The top level is the empty section name.
LOCKED_SETTINGS = (
    ("", "listen_host", '"127.0.0.1"'),
    ("app", "subtitle_provider", '"whisper"'),
    ("whisper", "model_size", f'"{WHISPER_MODEL}"'),
)


class Refused(Exception):
    """A named reason the render did not start or its result was not kept."""


def _run(argv, *, env=None, cwd=None, timeout=1800):
    return subprocess.run(
        argv, capture_output=True, text=True, env=env, cwd=cwd, timeout=timeout, check=False
    )


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        for block in iter(lambda: handle.read(1 << 20), b""):
            digest.update(block)
    return digest.hexdigest()


def _seconds(value) -> float:
    try:
        return float(value)
    except (TypeError, ValueError):
        return math.nan


def _tag_seconds(stream: dict) -> float:
    """Matroska and WebM keep a stream's length in a DURATION tag, HH:MM:SS.fraction."""
    match = re.fullmatch(r"(\d+):(\d{2}):(\d{2}(?:\.\d+)?)", str((stream.get("tags") or {}).get("DURATION", "")))
    if not match:
        return math.nan
    hours, minutes, seconds = match.groups()
    return int(hours) * 3600 + int(minutes) * 60 + float(seconds)


def probe(path: Path) -> dict:
    """ffprobe a file into {duration, video_duration, width, height, video, audio}.

    duration is the container's, which is the longest stream. video_duration is
    the picture's own: a clip whose sound outlasts its picture has a container
    duration MoneyPrinterTurbo trusts and fills with a frozen frame."""
    out = _run(
        ["ffprobe", "-v", "error", "-show_entries",
         "format=duration:stream=codec_type,width,height,duration:stream_tags=DURATION",
         "-of", "json", str(path)],
        timeout=120,
    )
    if out.returncode != 0:
        raise Refused(f"ffprobe could not read {path.name}")
    data = json.loads(out.stdout or "{}")
    streams = data.get("streams", [])
    video = [s for s in streams if s.get("codec_type") == "video"]
    audio = any(s.get("codec_type") == "audio" for s in streams)
    duration = _seconds(data.get("format", {}).get("duration"))
    video_duration = _seconds(video[0].get("duration")) if video else math.nan
    if video and not math.isfinite(video_duration):
        video_duration = _tag_seconds(video[0])
    if video and not math.isfinite(video_duration) and not audio:
        video_duration = duration  # a picture-only file: the container length is the picture's
    return {
        "duration": duration,
        "video_duration": video_duration,
        "width": int(video[0].get("width", 0)) if video else 0,
        "height": int(video[0].get("height", 0)) if video else 0,
        "video": bool(video),
        "audio": audio,
    }


def lock_config(example: str, api_key: str) -> str:
    """Return config.example.toml with the locked settings and an inbound API key.

    Every edit must find its line in its own section, so an upstream change to
    the example fails here rather than shipping an unlocked config."""
    wanted = {(sec, key): value for sec, key, value in LOCKED_SETTINGS}
    wanted[("app", "api_key")] = json.dumps(api_key)
    done, section, lines = set(), "", []
    for line in example.splitlines():
        header = re.fullmatch(r"\[([A-Za-z0-9_.-]+)\]\s*", line)
        if header:
            section = header.group(1)
        match = re.fullmatch(r"([A-Za-z0-9_]+)\s*=.*", line)
        if match and (section, match.group(1)) in wanted and (section, match.group(1)) not in done:
            key = match.group(1)
            line = f"{key} = {wanted[(section, key)]}"
            done.add((section, key))
        lines.append(line)
    missing = sorted(set(wanted) - done)
    if missing:
        raise Refused(f"config.example.toml no longer carries {missing}; re-audit before locking")
    return "\n".join(lines) + "\n"


def _credentials(table: dict, prefix: str = ""):
    for name, value in table.items():
        dotted = f"{prefix}{name}"
        if isinstance(value, dict):
            yield from _credentials(value, dotted + ".")
        elif CREDENTIAL.search(name.lower()) and dotted != "app.api_key":
            if (isinstance(value, str) and value.strip()) or (
                isinstance(value, list) and any(str(item).strip() for item in value)
            ):
                yield dotted


def audit_install(root: Path) -> list[str]:
    """Every reason this MoneyPrinterTurbo install is not the locked one."""
    reasons = []
    config_path = root / "config.toml"
    if not config_path.is_file():
        return ["config.toml is missing; run install.sh, which writes the locked one"]
    try:
        cfg = tomllib.loads(config_path.read_text(encoding="utf-8"))
    except (tomllib.TOMLDecodeError, UnicodeDecodeError):
        return ["config.toml does not parse"]
    app = cfg.get("app", {})
    reasons += [f"provider credential set: {name}" for name in _credentials(cfg)]
    if any(str(v).strip() for v in cfg.get("proxy", {}).values()):
        reasons.append("an outbound [proxy] is set")
    if app.get("upload_post_enabled") or app.get("upload_post_auto_upload"):
        reasons.append("Upload-Post cross-posting is switched on")
    if str(cfg.get("listen_host", "0.0.0.0")) not in LOOPBACK:
        reasons.append("listen_host is not loopback")
    if not str(app.get("api_key", "")).strip():
        reasons.append("app.api_key is empty, so the HTTP API would answer anyone who reaches it")
    if app.get("subtitle_provider") != "whisper":
        reasons.append('app.subtitle_provider is not "whisper"; the supplied voiceover would get no captions')
    model = cfg.get("whisper", {}).get("model_size", "")
    if not (root / "models" / f"whisper-{model}" / "model.bin").is_file():
        reasons.append(f"models/whisper-{model} is not on disk, so captions would download a model")
    auth = root / "storage" / "auth"
    if auth.is_dir() and any(auth.iterdir()):
        reasons.append("storage/auth holds a sign-in bundle")
    return reasons


def _tokens(text: str) -> list[str]:
    return [NUMBER_WORDS.get(w, w) for w in re.findall(r"[a-z0-9']+", text.lower())]


def shingles(text: str, n: int = 3) -> set[tuple[str, ...]]:
    words = _tokens(text)
    return {tuple(words[i:i + n]) for i in range(max(len(words) - n + 1, 1))} if words else set()


def similarity(a: str, b: str) -> float:
    """Shared 3 word shingles over the smaller set, so an old script inside a
    longer new one still scores as the share of it that was reused."""
    left, right = shingles(a), shingles(b)
    return len(left & right) / min(len(left), len(right)) if left and right else 0.0


def repeats(script: str, spoken: str, voice_sha: str, episode: str, show: str, ledger: Path) -> list[str]:
    """Earlier renders that this one repeats.

    It compares the script, what the voiceover actually says (so a re-encoded
    copy of an old voiceover still matches) and the voiceover's bytes. It does
    not compare clips: reusing our own b-roll across episodes is normal. Only a
    re-render of the same episode for the same show is exempt, so one render
    cannot go out on two channels. A manifest it cannot read stops the render
    rather than being skipped, because a skipped one is a repeat nobody saw."""
    if not ledger.is_dir():
        raise Refused(f"ledger {ledger} does not exist; create it once and keep it")
    found = []
    for path in sorted(ledger.glob("*.json")):
        try:
            prior = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError, RecursionError):
            prior = None
        if not isinstance(prior, dict):
            raise Refused(f"ledger manifest {path.name} cannot be read; repair or move it")
        if prior.get("episode") == episode and prior.get("show") == show:
            continue
        if prior.get("voice_sha256") == voice_sha:
            found.append(f"{path.name}: the same voiceover file")
        score = similarity(script, str(prior.get("script", "")))
        if score >= REPEAT_THRESHOLD:
            found.append(f"{path.name}: script similarity {score:.2f}")
        heard = similarity(spoken, str(prior.get("spoken", "")))
        if heard >= REPEAT_THRESHOLD:
            found.append(f"{path.name}: spoken similarity {heard:.2f}")
    return found


def scrubbed_env(root: Path) -> dict:
    """PATH, HOME and LANG only, so no key in the caller's environment reaches MPT."""
    return {"PATH": SCRUBBED_PATH, "HOME": str(root), "LANG": "C.UTF-8"}


def transcribe(python: str, root: Path, voice: Path) -> str:
    cfg = tomllib.loads((root / "config.toml").read_text(encoding="utf-8"))
    model = root / "models" / f"whisper-{cfg.get('whisper', {}).get('model_size', '')}"
    done = _run([python, "-c", TRANSCRIBE, str(model), str(voice)],
                env=scrubbed_env(root), cwd=root, timeout=600)
    if done.returncode != 0:
        raise Refused("the voiceover could not be transcribed with the local caption model")
    return json.loads(done.stdout.strip().splitlines()[-1])


def coverage(script: str, spoken: str) -> tuple[float, float]:
    """Share of the script that was said, and share of what was said that is
    the script. A take of half the script fails the first, a take carrying
    other speech fails the second."""
    a, b = _tokens(script), _tokens(spoken)
    if not a or not b:
        return 0.0, 0.0
    matched = sum(block.size for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks())
    return matched / len(a), matched / len(b)


def weakest_third(script: str, spoken: str) -> float:
    """The lowest share said of the script's first, middle and last third.

    A take that drops one closing sentence still says 0.90 of a 70 word
    script, and MPT would caption the missing sentence anyway. Each third
    has to clear the bar on its own, so a gap anywhere shows."""
    a, b = _tokens(script), _tokens(spoken)
    if len(a) < 3 or not b:
        return 0.0
    hit = [False] * len(a)
    for block in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for i in range(block.a, block.a + block.size):
            hit[i] = True
    cuts = [0, len(a) // 3, 2 * len(a) // 3, len(a)]
    return min(sum(hit[lo:hi]) / (hi - lo) for lo, hi in zip(cuts, cuts[1:], strict=False))


def srt_text(path: Path) -> str:
    keep = []
    for line in path.read_text(encoding="utf-8", errors="replace").splitlines():
        line = line.strip()
        if line and not line.isdigit() and "-->" not in line:
            keep.append(line)
    return " ".join(keep)


def licensed_font(path: str) -> Path:
    font = Path(path).resolve()
    if font.suffix.lower() not in FONT_EXT or not font.is_file():
        raise Refused("caption font must be an existing .ttf file")
    if not any(FONT_LICENCE.fullmatch(p.name) for p in font.parent.iterdir()):
        raise Refused(f"no OFL or LICENSE text beside {font.name}; captions need a font we have the right to burn in")
    return font


def local_clips(raws: list[str]) -> list[tuple[Path, dict]]:
    clips = []
    for raw in raws:
        clip = Path(raw).resolve()
        if "," in str(clip):
            # --video-materials is one comma separated argument.
            raise Refused(f"{clip}: a clip path may not contain a comma")
        if clip.suffix.lower() not in VIDEO_EXT or not clip.is_file():
            raise Refused(f"{clip.name} is not an existing mp4, mov, mkv or webm file")
        info = probe(clip)
        if not info["video"] or not math.isfinite(info["video_duration"]) or info["video_duration"] <= 0:
            raise Refused(f"{clip.name} has no measurable picture length; remux it without sound")
        if info["duration"] - info["video_duration"] > DURATION_TOLERANCE_S:
            raise Refused(
                f"{clip.name}: its sound runs {info['duration']:.2f}s and its picture {info['video_duration']:.2f}s; "
                "MoneyPrinterTurbo would hold the last frame for the difference"
            )
        if min(info["width"], info["height"]) < MIN_SIDE_PX:
            raise Refused(f"{clip.name} is under {MIN_SIDE_PX} px on a side")
        clips.append((clip, info))
    return clips


def preflight(args) -> dict:
    """Check every input and the install; return what the render needs."""
    if not EPISODE.fullmatch(args.episode):
        raise Refused("episode id must be letters, digits, dot, dash or underscore, 64 at most")
    if not SHOW.fullmatch(args.show):
        raise Refused("show must be a lower case slug such as tqo or nco-forge")
    root = Path(args.mpt_root).resolve()
    if not (root / "cli.py").is_file():
        raise Refused(f"{root} is not a MoneyPrinterTurbo checkout")
    head = _run(["git", "-C", str(root), "rev-parse", "HEAD"], timeout=30).stdout.strip()
    if head != MPT_COMMIT:
        raise Refused(f"MoneyPrinterTurbo is at {head or 'an unknown commit'}, audited commit is {MPT_COMMIT}")
    reasons = audit_install(root)
    if reasons:
        raise Refused("install is not locked: " + "; ".join(reasons))

    script = Path(args.script).read_text(encoding="utf-8").strip()
    if len(_tokens(script)) < 20:
        raise Refused("script is under 20 words; supply the finished script")

    voice = Path(args.voice).resolve()
    if voice.suffix.lower() not in AUDIO_EXT or not voice.is_file():
        raise Refused("voiceover must be an existing mp3, wav, m4a, aac, flac or ogg file")
    voice_info = probe(voice)
    if not voice_info["audio"] or not 0 < voice_info["duration"] <= MAX_VOICE_S:
        raise Refused(f"voiceover must hold audio and run 0 to {MAX_VOICE_S:.0f} seconds")

    clips = local_clips(args.clips)
    total = sum(info["video_duration"] for _, info in clips)
    if total < voice_info["duration"]:
        raise Refused(
            f"clips run {total:.2f}s and the voiceover {voice_info['duration']:.2f}s; "
            "MoneyPrinterTurbo would loop footage to fill the gap"
        )

    font = licensed_font(args.font)
    voice_sha = sha256(voice)
    ledger = Path(args.ledger)
    spoken = transcribe(args.mpt_python, root, voice)
    said, extra = coverage(script, spoken)
    third = weakest_third(script, spoken)
    # Every third clearing the bar means the whole script does, so the share
    # said overall is reported and not tested.
    if min(third, extra) < VOICE_COVERAGE_MIN:
        raise Refused(
            f"the voiceover says {said:.2f} of the script, {third:.2f} of its weakest third, "
            f"and {extra:.2f} of it is the script; it is not this script's full recording"
        )
    found = repeats(script, spoken, voice_sha, args.episode, args.show, ledger)
    if found:
        raise Refused("repeats an earlier render: " + "; ".join(found))
    return {"root": root, "script": script, "voice": voice, "voice_info": voice_info,
            "voice_sha": voice_sha, "clips": clips, "ledger": ledger, "coverage": (said, extra), "third": third,
            "spoken": spoken, "fit": args.fit, "font": font}


def place_font(root: Path, font: Path) -> str:
    """Copy the caption font into resource/fonts, where MPT resolves font names."""
    name = f"mpt-shorts-{sha256(font)[:12]}{font.suffix.lower()}"
    target = root / "resource" / "fonts" / name
    if not target.is_file():
        shutil.copyfile(font, target)
    return name


def mpt_argv(python: str, plan: dict, task_id: str, font_name: str) -> list[str]:
    """The only MoneyPrinterTurbo invocation this wrapper makes."""
    longest = max(info["video_duration"] for _, info in plan["clips"])
    return [
        python, "-X", "utf8", "cli.py",
        "--task-id", task_id,
        "--video-script", plan["script"],
        "--video-source", "local",
        "--video-materials", ",".join(str(clip) for clip, _ in plan["clips"]),
        "--custom-audio-file", str(plan["voice"]),
        "--video-count", "1",
        "--video-aspect", "9:16",
        "--video-fit-mode", plan["fit"],
        # Sequential with a clip length above the longest source keeps every
        # clip whole and in the order given; a shorter length would keep only
        # the first slice of each file.
        "--video-concat-mode", "sequential",
        "--video-clip-duration", str(math.ceil(longest) + 1),
        "--video-clip-speed", "1",
        "--video-transition-mode", "none",
        "--bgm-type", "none",
        "--subtitle-enabled",
        "--font-name", font_name,
        "--stop-at", "video",
    ]


def _copies(root: Path) -> set[str]:
    folder = root / "storage" / "local_videos"
    return {p.name for p in folder.glob("cli-material-*")} if folder.is_dir() else set()


def _clean(root: Path, task_id: str, before: set[str]) -> None:
    """Remove this render's task folder and every clip copy MPT made during it.

    MPT copies the clips as it starts, before it can fail, and names the copies
    only in the JSON of a run that succeeds, so the copies are found by what
    appeared during this run. The lock in render() makes that this run's."""
    shutil.rmtree(root / "storage" / "tasks" / task_id, ignore_errors=True)
    for name in _copies(root) - before:
        (root / "storage" / "local_videos" / name).unlink(missing_ok=True)


def render(args, plan: dict, now: datetime) -> dict:
    root = plan["root"]
    (root / "storage").mkdir(exist_ok=True)
    with open(root / "storage" / "mpt-shorts.lock", "w") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except OSError:
            raise Refused("another render is running on this install; run one at a time") from None
        task_id, before = str(uuid.uuid4()), _copies(root)
        try:
            return _render(args, plan, now, task_id)
        finally:
            _clean(root, task_id, before)


def _render(args, plan: dict, now: datetime, task_id: str) -> dict:
    font_name = place_font(plan["root"], plan["font"])
    try:
        done = _run(mpt_argv(args.mpt_python, plan, task_id, font_name),
                    env=scrubbed_env(plan["root"]), cwd=plan["root"], timeout=args.timeout)
    except subprocess.TimeoutExpired:
        raise Refused(f"MoneyPrinterTurbo did not finish inside {args.timeout} s") from None
    if done.returncode != 0:
        tail = " | ".join(done.stderr.strip().splitlines()[-3:])
        raise Refused(f"MoneyPrinterTurbo exited {done.returncode}: {tail[-600:]}")
    result = json.loads(done.stdout).get("result", {})
    videos = result.get("videos") or []
    if len(videos) != 1:
        raise Refused(f"expected one video, MoneyPrinterTurbo returned {len(videos)}")
    video, srt = Path(videos[0]), Path(result.get("subtitle_path") or "")

    info = probe(video)
    if (info["width"], info["height"]) != (1080, 1920) or not info["audio"]:
        raise Refused(f"output is {info['width']}x{info['height']}, audio {info['audio']}; expected 1080x1920 with audio")
    drift = abs(info["duration"] - plan["voice_info"]["duration"])
    if drift > DURATION_TOLERANCE_S:
        raise Refused(f"output runs {info['duration']:.2f}s against a {plan['voice_info']['duration']:.2f}s voiceover")
    if not srt.is_file() or not srt_text(srt):
        raise Refused("no captions were written")

    out = Path(args.out)
    out.mkdir(parents=True, exist_ok=True)
    final, captions = out / f"{args.episode}.mp4", out / f"{args.episode}.srt"
    shutil.copyfile(video, final)
    shutil.copyfile(srt, captions)
    manifest = {
        "episode": args.episode,
        "show": args.show,
        "rendered_at": now.isoformat(),
        "mpt_commit": MPT_COMMIT,
        "mpt_task_id": task_id,
        "script": plan["script"],
        "script_sha256": hashlib.sha256(plan["script"].encode("utf-8")).hexdigest(),
        "voice_sha256": plan["voice_sha"],
        "voice_seconds": round(plan["voice_info"]["duration"], 3),
        # MPT stops taking clips once the picture covers the voiceover, so a
        # late clip in this list may not appear in the output.
        "clips_supplied": [{"name": clip.name, "sha256": sha256(clip), "seconds": round(info["video_duration"], 3)}
                           for clip, info in plan["clips"]],
        "output": final.name,
        "output_sha256": sha256(final),
        "output_seconds": round(info["duration"], 3),
        "spoken": plan["spoken"],
        "script_said": round(plan["coverage"][0], 3),
        "weakest_third_said": round(plan["third"], 3),
        "said_is_script": round(plan["coverage"][1], 3),
        "fit": plan["fit"],
        "font": {"source": plan["font"].name, "sha256": sha256(plan["font"])},
        "argv": mpt_argv("<mpt-python>", plan, task_id, font_name)[1:],
        "published": False,
        # Neither of these can be read from the files, so the code records that
        # it did not check them and leaves both to the person who reviews.
        "voice_identity_checked": False,
        "clip_rights_checked": False,
        "human_review": "pending: watch end to end, confirm the voice is Tee's own and every clip is ours or licensed",
    }
    ledger = plan["ledger"]
    ledger.mkdir(parents=True, exist_ok=True)
    stamp = now.strftime("%Y%m%dT%H%M%SZ")
    (ledger / f"{args.episode}-{stamp}.json").write_text(json.dumps(manifest, indent=2) + "\n", encoding="utf-8")
    return manifest


def _render_cmd(args) -> int:
    try:
        plan = preflight(args)
        manifest = render(args, plan, datetime.now(timezone.utc))
    except (Refused, OSError, ValueError, RecursionError, subprocess.TimeoutExpired) as exc:
        print(json.dumps({"ok": False, "refused": str(exc)}))
        return 2
    print(json.dumps({"ok": True, "output": str(Path(args.out) / manifest["output"]),
                      "seconds": manifest["output_seconds"],
                      "script_said": manifest["script_said"],
                      "said_is_script": manifest["said_is_script"]}))
    return 0


def _lock_cmd(args) -> int:
    root = Path(args.mpt_root)
    target = root / "config.toml"
    if target.exists() and not args.replace:
        print(json.dumps({"ok": False, "refused": "config.toml exists; pass --replace to overwrite it"}))
        return 2
    try:
        text = lock_config((root / "config.example.toml").read_text(encoding="utf-8"), secrets.token_hex(24))
    except Refused as exc:
        print(json.dumps({"ok": False, "refused": str(exc)}))
        return 2
    fd = os.open(target, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(fd, "w", encoding="utf-8") as handle:
        handle.write(text)
    target.chmod(0o600)
    reasons = audit_install(root)
    print(json.dumps({"ok": not reasons, "audit": reasons}))
    return 0 if not reasons else 2


def _audit_cmd(args) -> int:
    reasons = audit_install(Path(args.mpt_root))
    print(json.dumps({"ok": not reasons, "audit": reasons}))
    return 0 if not reasons else 2


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    sub = parser.add_subparsers(dest="cmd", required=True)

    lock = sub.add_parser("lock-config", help="write the locked config.toml from config.example.toml")
    lock.add_argument("--mpt-root", required=True)
    lock.add_argument("--replace", action="store_true")
    lock.set_defaults(func=_lock_cmd)

    audit = sub.add_parser("audit", help="list every reason the install is not locked")
    audit.add_argument("--mpt-root", required=True)
    audit.set_defaults(func=_audit_cmd)

    run = sub.add_parser("render", help="render one Short from supplied script, voiceover and clips")
    run.add_argument("--mpt-root", required=True)
    run.add_argument("--mpt-python", required=True, help="the python of MoneyPrinterTurbo's own environment")
    run.add_argument("--episode", required=True)
    run.add_argument("--show", required=True)
    run.add_argument("--script", required=True, help="UTF-8 text file holding the finished script")
    run.add_argument("--voice", required=True,
                     help="finished voiceover; the code checks that it reads this script, not whose voice it is")
    run.add_argument("--clips", required=True, nargs="+", help="local clips, in playing order")
    run.add_argument("--out", required=True)
    run.add_argument("--ledger", required=True, help="directory of earlier render manifests")
    run.add_argument("--font", required=True,
                     help="caption .ttf with its licence beside it, e.g. tools/mpt_shorts/fonts/inter-bold.ttf")
    run.add_argument("--fit", choices=("contain", "cover"), default="contain",
                     help="contain keeps the whole frame of a screen recording; cover fills and crops")
    run.add_argument("--timeout", type=int, default=1800)
    run.set_defaults(func=_render_cmd)

    args = parser.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
