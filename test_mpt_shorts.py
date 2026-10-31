"""The MoneyPrinterTurbo Shorts wrapper refuses everything but the tailored flow.

These pin the gate logic without MoneyPrinterTurbo, ffmpeg or a network: the
locked config edits, the install audit, the repetition check and the one
command line the wrapper builds. They prove nothing about a render. The render,
the refusal of a mismatched voiceover and the clip order were measured once in
the sandbox on 2026-10-31 and are recorded in the status doc of that day.
"""

import importlib.util
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

FILE = Path(__file__).resolve().parent / "tools" / "mpt_shorts" / "render_short.py"
spec = importlib.util.spec_from_file_location("mpt_render_short_test", FILE)
rs = importlib.util.module_from_spec(spec)
spec.loader.exec_module(rs)

# The shape of the upstream config.example.toml where the locked edits land:
# listen_host at the top level, the inbound api_key under [app], and a
# provider api_key under [elevenlabs] that must stay empty.
EXAMPLE = """\
log_level = "DEBUG"
listen_host = "0.0.0.0"
listen_port = 8080

[app]
api_key = ""
pexels_api_keys = []
subtitle_provider = "edge"
upload_post_enabled = false
upload_post_auto_upload = false

[whisper]
model_size = "large-v3"

[proxy]

[elevenlabs]
api_key = ""
"""


def _install(tmp_path, text=None, model=True):
    root = tmp_path / "mpt"
    root.mkdir()
    (root / "config.toml").write_text(text or rs.lock_config(EXAMPLE, "a" * 48), encoding="utf-8")
    if model:
        (root / "models" / f"whisper-{rs.WHISPER_MODEL}").mkdir(parents=True)
        (root / "models" / f"whisper-{rs.WHISPER_MODEL}" / "model.bin").write_bytes(b"x")
    return root


def test_the_lock_sets_the_inbound_key_and_leaves_provider_keys_empty():
    import tomllib

    cfg = tomllib.loads(rs.lock_config(EXAMPLE, "k" * 48))
    assert cfg["listen_host"] == "127.0.0.1"
    assert cfg["app"]["api_key"] == "k" * 48
    assert cfg["app"]["subtitle_provider"] == "whisper"
    assert cfg["whisper"]["model_size"] == "base.en"
    assert cfg["elevenlabs"]["api_key"] == ""


def test_the_lock_refuses_an_example_that_moved():
    moved = EXAMPLE.replace('subtitle_provider = "edge"\n', "")
    with pytest.raises(rs.Refused, match="subtitle_provider"):
        rs.lock_config(moved, "k" * 48)


def test_a_locked_install_passes_the_audit(tmp_path):
    assert rs.audit_install(_install(tmp_path)) == []


@pytest.mark.parametrize(
    "edit, reason",
    [
        (('pexels_api_keys = []', 'pexels_api_keys = ["abc"]'), "app.pexels_api_keys"),
        (('[elevenlabs]\napi_key = ""', '[elevenlabs]\napi_key = "sk"'), "elevenlabs.api_key"),
        (("upload_post_enabled = false", "upload_post_enabled = true"), "cross-posting"),
        (("upload_post_auto_upload = false", "upload_post_auto_upload = true"), "cross-posting"),
        (('listen_host = "127.0.0.1"', 'listen_host = "0.0.0.0"'), "loopback"),
        (('subtitle_provider = "whisper"', 'subtitle_provider = "edge"'), "no captions"),
        (("[proxy]", '[proxy]\nhttps = "http://u:p@host:1"'), "[proxy]"),
    ],
)
def test_each_unlocked_setting_is_named(tmp_path, edit, reason):
    text = rs.lock_config(EXAMPLE, "a" * 48).replace(*edit)
    reasons = rs.audit_install(_install(tmp_path, text))
    assert any(reason in r for r in reasons), reasons


def test_an_empty_inbound_key_is_named(tmp_path):
    reasons = rs.audit_install(_install(tmp_path, rs.lock_config(EXAMPLE, "")))
    assert any("app.api_key is empty" in r for r in reasons)


def test_a_missing_caption_model_and_a_sign_in_bundle_are_named(tmp_path):
    root = _install(tmp_path, model=False)
    (root / "storage" / "auth").mkdir(parents=True)
    (root / "storage" / "auth" / "openai_codex.bin").write_bytes(b"token")
    reasons = rs.audit_install(root)
    assert any("would download a model" in r for r in reasons)
    assert any("sign-in bundle" in r for r in reasons)


def test_a_config_that_does_not_parse_is_refused(tmp_path):
    assert rs.audit_install(_install(tmp_path, "listen_host = [")) == ["config.toml does not parse"]


def test_no_config_at_all_is_refused(tmp_path):
    assert "missing" in rs.audit_install(tmp_path)[0]


SCRIPT = (
    "By the end of this short you will know how to check whether an AI tool is "
    "worth your time. Step one. Give it a task you already know the answer to."
)


def _ledger(tmp_path, **manifest):
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    (ledger / "prior.json").write_text(json.dumps(manifest), encoding="utf-8")
    return ledger


def test_the_same_script_under_another_episode_is_a_repeat(tmp_path):
    ledger = _ledger(tmp_path, episode="ep1", show="tqo", script=SCRIPT, voice_sha256="v1")
    found = rs.repeats(SCRIPT, "", "v2", "ep2", "tqo", ledger)
    assert found == ["prior.json: script similarity 1.00"]


def test_the_same_voiceover_under_another_episode_is_a_repeat(tmp_path):
    ledger = _ledger(tmp_path, episode="ep1", show="tqo", script="something else entirely here", voice_sha256="v1")
    assert rs.repeats(SCRIPT, "", "v1", "ep2", "tqo", ledger) == ["prior.json: the same voiceover file"]


def test_a_re_encoded_old_voiceover_is_caught_by_what_it_says(tmp_path):
    ledger = _ledger(tmp_path, episode="ep1", show="tqo", script="an unrelated script about phones and backups",
                     spoken=SCRIPT, voice_sha256="v1")
    found = rs.repeats("a reworded script about checking tools for value", SCRIPT, "v9", "ep2", "tqo", ledger)
    assert found == ["prior.json: spoken similarity 1.00"]


def test_an_old_script_inside_a_longer_new_one_is_a_repeat(tmp_path):
    ledger = _ledger(tmp_path, episode="ep1", show="tqo", script=SCRIPT, voice_sha256="v1")
    longer = SCRIPT + " " + " ".join(f"fresh words number {i} about something new" for i in range(20))
    assert rs.repeats(longer, "", "v2", "ep2", "tqo", ledger) == ["prior.json: script similarity 1.00"]


def test_a_re_render_of_the_same_episode_for_the_same_show_is_not_a_repeat(tmp_path):
    ledger = _ledger(tmp_path, episode="ep1", show="tqo", script=SCRIPT, voice_sha256="v1")
    assert rs.repeats(SCRIPT, SCRIPT, "v1", "ep1", "tqo", ledger) == []


def test_the_same_episode_id_on_another_show_is_a_repeat(tmp_path):
    ledger = _ledger(tmp_path, episode="ep1", show="tqo", script=SCRIPT, voice_sha256="v1")
    assert rs.repeats(SCRIPT, "", "v1", "ep1", "nco-forge", ledger)


def test_a_different_script_is_not_a_repeat(tmp_path):
    other = "Most people back up their phone the wrong way. Open settings and look for storage."
    ledger = _ledger(tmp_path, episode="ep1", show="tqo", script=other, voice_sha256="v1")
    assert rs.repeats(SCRIPT, "", "v2", "ep2", "tqo", ledger) == []


@pytest.mark.parametrize("body", ["{", "[1, 2]", "[" * 200000 + "]" * 200000])
def test_an_unreadable_manifest_stops_the_render(tmp_path, body):
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    (ledger / "bad.json").write_text(body, encoding="utf-8")
    with pytest.raises(rs.Refused, match="bad.json cannot be read"):
        rs.repeats(SCRIPT, "", "v", "ep", "tqo", ledger)


def test_a_missing_ledger_stops_the_render(tmp_path):
    with pytest.raises(rs.Refused, match="does not exist"):
        rs.repeats(SCRIPT, "", "v", "ep", "tqo", tmp_path / "absent")


# Measured 2026-10-31 with faster-whisper base.en on a Piper take of the
# fixture script: the transcript writes "Step 1" where the script says "Step one".
FULL_TAKE = (
    "By the end of this short you will know how to check whether an AI tool is "
    "worth your time. Step 1. Give it a task you already know the answer to."
)


def test_coverage_passes_the_full_take_with_digits_for_numbers():
    said, extra = rs.coverage(SCRIPT, FULL_TAKE)
    assert said == extra == 1.0


def test_coverage_refuses_half_a_take_and_a_take_with_other_speech():
    half = "By the end of this short you will know how to check"
    assert rs.coverage(SCRIPT, half)[0] < rs.VOICE_COVERAGE_MIN
    padded = FULL_TAKE + " Most people back up their phone the wrong way and never check it again."
    assert rs.coverage(SCRIPT, padded)[1] < rs.VOICE_COVERAGE_MIN
    assert max(rs.coverage(SCRIPT, "Most people back up their phone the wrong way")) < rs.VOICE_COVERAGE_MIN
    assert rs.coverage(SCRIPT, "") == (0.0, 0.0)


def _plan(**over):
    plan = {
        "script": SCRIPT,
        "voice": Path("/v/voice.wav"),
        "clips": [(Path("/c/a.mp4"), {"duration": 12.0, "video_duration": 12.0}),
                  (Path("/c/b.mp4"), {"duration": 31.0, "video_duration": 30.4})],
        "fit": "contain",
    }
    plan.update(over)
    return plan


def _flags(argv):
    flags, i = {}, 0
    while i < len(argv):
        has_value = i + 1 < len(argv) and not argv[i + 1].startswith("--")
        flags[argv[i]] = argv[i + 1] if has_value else True
        i += 2 if has_value else 1
    return flags


def test_the_only_command_is_the_tailored_one():
    argv = rs.mpt_argv("/mpt/.venv/bin/python", _plan(), "t-1", "mpt-shorts-abc.ttf")
    flags = _flags(argv[4:])
    assert argv[:4] == ["/mpt/.venv/bin/python", "-X", "utf8", "cli.py"]
    assert flags["--video-script"] == SCRIPT
    assert flags["--video-source"] == "local"
    assert flags["--video-materials"] == "/c/a.mp4,/c/b.mp4"
    assert flags["--custom-audio-file"] == "/v/voice.wav"
    assert flags["--video-count"] == "1"
    assert flags["--video-concat-mode"] == "sequential"
    assert flags["--video-clip-duration"] == "32"
    assert flags["--bgm-type"] == "none"
    assert flags["--video-transition-mode"] == "none"
    assert flags["--subtitle-enabled"] is True
    assert flags["--stop-at"] == "video"
    assert flags["--font-name"] == "mpt-shorts-abc.ttf"


def test_the_command_never_names_a_voice_a_provider_a_batch_or_a_charge():
    argv = rs.mpt_argv("py", _plan(), "t-1", "f.ttf")
    for flag in ("--voice-name", "--batch-file", "--video-subject", "--video-terms", "--bgm-file"):
        assert flag not in argv
    assert not [a for a in argv if a.startswith("--confirm-")]


@pytest.mark.parametrize(
    "field, value, message",
    [("episode", "../x", "episode id"), ("show", "TQO", "show must be")],
)
def test_bad_ids_are_refused_before_anything_is_read(field, value, message):
    args = SimpleNamespace(episode="ep1", show="tqo", mpt_root="/nonexistent")
    setattr(args, field, value)
    with pytest.raises(rs.Refused, match=message):
        rs.preflight(args)


def test_srt_text_keeps_only_the_words(tmp_path):
    path = tmp_path / "captions.srt"
    path.write_text(
        "1\n00:00:00,000 --> 00:00:01,000\nStep one\n\n2\n00:00:01,000 --> 00:00:02,000\nStep two\n",
        encoding="utf-8",
    )
    assert rs.srt_text(path) == "Step one Step two"


def test_a_font_with_its_licence_beside_it_is_accepted(tmp_path):
    (tmp_path / "face.ttf").write_bytes(b"f")
    (tmp_path / "OFL-face.txt").write_text("SIL Open Font License", encoding="utf-8")
    assert rs.licensed_font(str(tmp_path / "face.ttf")) == (tmp_path / "face.ttf").resolve()


def test_a_woff2_is_refused_because_mpt_takes_ttf_only(tmp_path):
    (tmp_path / "face.woff2").write_bytes(b"f")
    (tmp_path / "OFL-face.txt").write_text("SIL Open Font License", encoding="utf-8")
    with pytest.raises(rs.Refused, match=".ttf"):
        rs.licensed_font(str(tmp_path / "face.woff2"))


def test_a_font_without_a_licence_is_refused(tmp_path):
    (tmp_path / "STHeitiMedium.ttf").write_bytes(b"f")
    with pytest.raises(rs.Refused, match="no OFL or LICENSE"):
        rs.licensed_font(str(tmp_path / "STHeitiMedium.ttf"))


def test_the_repository_caption_fonts_carry_their_licences():
    root = Path(__file__).resolve().parent
    for face in ("tools/mpt_shorts/fonts/atkinson-hyperlegible-next-latin-bold.ttf",
                 "tools/mpt_shorts/fonts/inter-bold.ttf"):
        assert rs.licensed_font(str(root / face)).is_file()


def test_the_placed_font_name_is_fixed_by_its_content(tmp_path):
    root = tmp_path / "mpt"
    (root / "resource" / "fonts").mkdir(parents=True)
    font = tmp_path / "face.ttf"
    font.write_bytes(b"glyphs")
    name = rs.place_font(root, font)
    assert name == f"mpt-shorts-{rs.sha256(font)[:12]}.ttf"
    assert (root / "resource" / "fonts" / name).read_bytes() == b"glyphs"


def test_a_comma_in_the_folder_is_named_in_the_refusal(tmp_path):
    folder = tmp_path / "dir,x"
    folder.mkdir()
    (folder / "clip.mp4").write_bytes(b"not probed")
    with pytest.raises(rs.Refused, match=r"dir,x/clip\.mp4: a clip path may not contain a comma"):
        rs.local_clips([str(folder / "clip.mp4")])


def _probe_with(monkeypatch, report):
    from types import SimpleNamespace as NS

    monkeypatch.setattr(rs, "_run", lambda argv, **kw: NS(returncode=0, stdout=json.dumps(report), stderr=""))
    return rs.probe(Path("clip.mp4"))


def test_probe_measures_a_clip_by_its_picture_not_its_container(monkeypatch):
    info = _probe_with(monkeypatch, {
        "streams": [{"codec_type": "video", "width": 1920, "height": 1080, "duration": "6.000000"},
                    {"codec_type": "audio", "duration": "12.000000"}],
        "format": {"duration": "12.000000"}})
    assert (info["video_duration"], info["duration"], info["audio"]) == (6.0, 12.0, True)


def test_probe_reads_the_matroska_duration_tag(monkeypatch):
    # The shape ffprobe 6.1.1 reported for a 3 s mkv with opus sound, 2026-10-31.
    info = _probe_with(monkeypatch, {
        "streams": [{"codec_type": "video", "width": 640, "height": 480, "tags": {"DURATION": "00:00:03.000000000"}},
                    {"codec_type": "audio", "tags": {"DURATION": "00:00:03.008000000"}}],
        "format": {"duration": "3.008000"}})
    assert info["video_duration"] == 3.0


def test_probe_will_not_guess_a_picture_length_when_sound_is_there(monkeypatch):
    import math

    info = _probe_with(monkeypatch, {
        "streams": [{"codec_type": "video", "width": 640, "height": 480},
                    {"codec_type": "audio"}],
        "format": {"duration": "12.0"}})
    assert math.isnan(info["video_duration"])


def test_probe_uses_the_container_for_a_picture_only_file(monkeypatch):
    info = _probe_with(monkeypatch, {
        "streams": [{"codec_type": "video", "width": 640, "height": 480}],
        "format": {"duration": "7.5"}})
    assert info["video_duration"] == 7.5 and info["audio"] is False


def test_a_clip_path_with_a_comma_is_refused_before_it_is_probed(tmp_path):
    clip = tmp_path / "demo,cut.mp4"
    clip.write_bytes(b"not probed")
    with pytest.raises(rs.Refused, match="comma"):
        rs.local_clips([str(clip)])


def test_a_clip_that_is_not_a_video_file_is_refused(tmp_path):
    with pytest.raises(rs.Refused, match="not an existing"):
        rs.local_clips([str(tmp_path / "missing.mp4")])
    (tmp_path / "notes.txt").write_text("x", encoding="utf-8")
    with pytest.raises(rs.Refused, match="not an existing"):
        rs.local_clips([str(tmp_path / "notes.txt")])


# A stand-in for MoneyPrinterTurbo's cli.py, run as a real child process with
# the real argv and environment, so preflight and render are exercised whole.
# It records what it was given and writes what the real one writes.
FAKE_CLI = r'''
import json, os, pathlib, sys
args = sys.argv[1:]
flags, i = {}, 0
while i < len(args):
    if i + 1 < len(args) and not args[i + 1].startswith("--"):
        flags[args[i]] = args[i + 1]
        i += 2
    else:
        flags[args[i]] = True
        i += 1
pathlib.Path("seen.json").write_text(json.dumps({"argv": args, "env": dict(os.environ)}))
mode = pathlib.Path("fake_mode.txt").read_text().strip() if pathlib.Path("fake_mode.txt").exists() else ""
task = pathlib.Path("storage/tasks") / flags["--task-id"]
task.mkdir(parents=True, exist_ok=True)
# MPT copies the clips as it starts, before anything can fail (cli.py:1782).
copies = pathlib.Path("storage/local_videos")
copies.mkdir(parents=True, exist_ok=True)
mats = []
for n, _ in enumerate(flags["--video-materials"].split(",")):
    copy = copies / f"cli-material-{flags['--task-id'][:8]}-{n}.mp4"
    copy.write_bytes(b"copy")
    mats.append(str(copy.resolve()))
if mode == "fail":
    sys.exit(3)
if mode == "hang":
    import time
    time.sleep(30)
(task / "final-1.mp4").write_bytes(b"video")
(task / "subtitle.srt").write_text("" if mode == "nosrt" else "1\n00:00:00,000 --> 00:00:01,000\nhello\n")
print(json.dumps({"task_id": flags["--task-id"], "result": {
    "videos": [str((task / "final-1.mp4").resolve())],
    "subtitle_path": str((task / "subtitle.srt").resolve()),
    "materials": mats}}))
'''

ROOT = Path(__file__).resolve().parent
FONT = ROOT / "tools" / "mpt_shorts" / "fonts" / "inter-bold.ttf"
NAN = float("nan")


@pytest.fixture
def fake(tmp_path, monkeypatch):
    import subprocess
    import sys

    root = _install(tmp_path)
    (root / "cli.py").write_text(FAKE_CLI, encoding="utf-8")
    (root / "resource" / "fonts").mkdir(parents=True)
    git = ["git", "-C", str(root), "-c", "user.email=t@t", "-c", "user.name=t"]
    subprocess.run(git + ["init", "-q"], check=True)
    subprocess.run(git + ["commit", "-q", "--allow-empty", "-m", "fake"], check=True)
    head = subprocess.run(git + ["rev-parse", "HEAD"], capture_output=True, text=True, check=True).stdout.strip()
    monkeypatch.setattr(rs, "MPT_COMMIT", head)

    media = tmp_path / "media"
    media.mkdir()
    for name in ("voice.wav", "a.mp4", "b.mp4"):
        (media / name).write_bytes(name.encode())
    (media / "script.txt").write_text(SCRIPT, encoding="utf-8")
    (tmp_path / "ledger").mkdir()

    probes = {
        "voice.wav": {"duration": 20.0, "video_duration": NAN, "width": 0, "height": 0, "video": False, "audio": True},
        "a.mp4": {"duration": 12.0, "video_duration": 12.0, "width": 1920, "height": 1080, "video": True, "audio": False},
        "b.mp4": {"duration": 12.0, "video_duration": 12.0, "width": 1920, "height": 1080, "video": True, "audio": False},
        "final-1.mp4": {"duration": 20.1, "video_duration": 20.1, "width": 1080, "height": 1920, "video": True, "audio": True},
    }
    monkeypatch.setattr(rs, "probe", lambda path: dict(probes[Path(path).name]))
    heard = {"text": FULL_TAKE}
    monkeypatch.setattr(rs, "transcribe", lambda python, root_, voice: heard["text"])
    monkeypatch.setenv("ELEVENLABS_API_KEY", "sk-must-not-reach-mpt")

    args = SimpleNamespace(
        episode="tqo-s001", show="tqo", mpt_root=str(root), mpt_python=sys.executable,
        script=str(media / "script.txt"), voice=str(media / "voice.wav"),
        clips=[str(media / "a.mp4"), str(media / "b.mp4")], font=str(FONT),
        ledger=str(tmp_path / "ledger"), out=str(tmp_path / "out"), fit="contain", timeout=60,
    )
    return SimpleNamespace(root=root, args=args, probes=probes, heard=heard, tmp=tmp_path)


def test_a_clean_run_renders_records_and_cleans_up(fake):
    from datetime import datetime, timezone

    plan = rs.preflight(fake.args)
    manifest = rs.render(fake.args, plan, datetime(2026, 10, 31, tzinfo=timezone.utc))
    seen = json.loads((fake.root / "seen.json").read_text())
    flags = _flags(seen["argv"][1:])
    assert flags["--custom-audio-file"] == str(Path(fake.args.voice).resolve())
    assert flags["--video-source"] == "local"
    assert set(seen["env"]) <= {"PATH", "HOME", "LANG", "LC_CTYPE"}
    assert "ELEVENLABS_API_KEY" not in seen["env"]
    assert (fake.tmp / "out" / "tqo-s001.mp4").read_bytes() == b"video"
    assert (fake.tmp / "out" / "tqo-s001.srt").is_file()
    written = list((fake.tmp / "ledger").glob("*.json"))
    assert [p.name for p in written] == ["tqo-s001-20261031T000000Z.json"]
    assert json.loads(written[0].read_text())["voice_identity_checked"] is False
    assert manifest["clip_rights_checked"] is False and manifest["published"] is False
    assert [c["name"] for c in manifest["clips_supplied"]] == ["a.mp4", "b.mp4"]
    assert not (fake.root / "storage" / "tasks" / manifest["mpt_task_id"]).exists()
    assert not list((fake.root / "storage" / "local_videos").iterdir())


def _refused(fake, match):
    with pytest.raises(rs.Refused, match=match):
        rs.preflight(fake.args)


def test_a_moved_checkout_is_refused(fake, monkeypatch):
    monkeypatch.setattr(rs, "MPT_COMMIT", "0" * 40)
    _refused(fake, "audited commit")


def test_a_key_in_the_install_is_refused(fake):
    cfg = fake.root / "config.toml"
    cfg.write_text(cfg.read_text().replace('[elevenlabs]\napi_key = ""', '[elevenlabs]\napi_key = "sk"'))
    _refused(fake, "install is not locked")


def test_a_short_script_is_refused(fake):
    Path(fake.args.script).write_text("too short to be a script", encoding="utf-8")
    _refused(fake, "under 20 words")


def test_a_voiceover_over_three_minutes_is_refused(fake):
    fake.probes["voice.wav"]["duration"] = 180.5
    _refused(fake, "run 0 to 180")


def test_a_clip_whose_sound_outlasts_its_picture_is_refused(fake):
    fake.probes["a.mp4"].update(duration=12.0, video_duration=6.0, audio=True)
    _refused(fake, "hold the last frame")


def test_pictures_shorter_than_the_voiceover_are_refused(fake):
    fake.probes["a.mp4"].update(duration=6.0, video_duration=6.0)
    fake.probes["b.mp4"].update(duration=6.0, video_duration=6.0)
    _refused(fake, "would loop footage")


def test_a_small_clip_is_refused(fake):
    fake.probes["b.mp4"].update(width=320, height=240)
    _refused(fake, "under 480 px")


def test_half_a_take_is_refused(fake):
    fake.heard["text"] = "By the end of this short you will know how to check"
    _refused(fake, "not this script's full recording")


def test_a_take_carrying_other_speech_is_refused(fake):
    fake.heard["text"] = FULL_TAKE + " Most people back up their phone the wrong way and never check it again."
    _refused(fake, "not this script's full recording")


def test_a_repeat_of_another_episode_is_refused(fake):
    (fake.tmp / "ledger" / "old.json").write_text(
        json.dumps({"episode": "tqo-s000", "show": "tqo", "script": SCRIPT, "voice_sha256": "x"}), encoding="utf-8")
    _refused(fake, "repeats an earlier render")


@pytest.mark.parametrize(
    "mode, final, match",
    [
        ("fail", {}, "exited 3"),
        ("hang", {}, "did not finish inside 2 s"),
        ("nosrt", {}, "no captions"),
        ("", {"width": 1920, "height": 1080}, "expected 1080x1920"),
        ("", {"audio": False}, "expected 1080x1920"),
        ("", {"duration": 21.0}, "against a 20.00s voiceover"),
    ],
)
def test_a_bad_render_keeps_nothing(fake, mode, final, match):
    from datetime import datetime, timezone

    (fake.root / "fake_mode.txt").write_text(mode)
    fake.probes["final-1.mp4"].update(final)
    fake.args.timeout = 2
    plan = rs.preflight(fake.args)
    with pytest.raises(rs.Refused, match=match):
        rs.render(fake.args, plan, datetime(2026, 10, 31, tzinfo=timezone.utc))
    assert not list((fake.tmp / "ledger").glob("*.json"))
    assert not (fake.tmp / "out").exists() or not list((fake.tmp / "out").iterdir())
    assert not list((fake.root / "storage" / "tasks").iterdir())
    assert not list((fake.root / "storage" / "local_videos").glob("cli-material-*"))


def test_cleanup_leaves_copies_that_were_there_before(fake):
    from datetime import datetime, timezone

    older = fake.root / "storage" / "local_videos" / "cli-material-older.mp4"
    older.parent.mkdir(parents=True)
    older.write_bytes(b"not this run's")
    (fake.root / "fake_mode.txt").write_text("fail")
    plan = rs.preflight(fake.args)
    with pytest.raises(rs.Refused):
        rs.render(fake.args, plan, datetime(2026, 10, 31, tzinfo=timezone.utc))
    assert [p.name for p in older.parent.iterdir()] == ["cli-material-older.mp4"]


def test_a_second_render_on_the_same_install_is_refused(fake):
    import fcntl
    from datetime import datetime, timezone

    plan = rs.preflight(fake.args)
    (fake.root / "storage").mkdir(exist_ok=True)
    with open(fake.root / "storage" / "mpt-shorts.lock", "w") as held:
        fcntl.flock(held, fcntl.LOCK_EX)
        with pytest.raises(rs.Refused, match="another render"):
            rs.render(fake.args, plan, datetime(2026, 10, 31, tzinfo=timezone.utc))


def test_a_take_missing_its_last_sentence_is_refused(fake):
    script = (
        "By the end of this short you will know how to check whether an AI tool is worth your time. "
        "Step one. Give it a task you already know the answer to. Step two. Time how long it takes "
        "against doing it yourself. Step three. Check every number it gives you against the source. "
        "If it fails step three, it costs you more than it saves. That is the whole test."
    )
    Path(fake.args.script).write_text(script, encoding="utf-8")
    # Measured 2026-10-31: the fixture take cut at 17.5 s drops the last
    # sentence and said 0.90 of the script, which the overall share passed.
    fake.heard["text"] = script.rsplit(" That is", 1)[0]
    assert rs.coverage(script, fake.heard["text"])[0] >= rs.VOICE_COVERAGE_MIN
    _refused(fake, "weakest third")


def test_lock_config_writes_owner_only_and_will_not_overwrite(tmp_path, capsys):
    root = tmp_path / "mpt"
    root.mkdir()
    (root / "config.example.toml").write_text(EXAMPLE, encoding="utf-8")
    args = SimpleNamespace(mpt_root=str(root), replace=False)
    rs._lock_cmd(args)
    assert (root / "config.toml").stat().st_mode & 0o777 == 0o600
    capsys.readouterr()
    assert rs._lock_cmd(args) == 2
    assert "pass --replace" in capsys.readouterr().out
