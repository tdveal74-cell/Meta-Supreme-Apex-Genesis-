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
    ledger = _ledger(tmp_path, episode="ep1", script=SCRIPT, voice_sha256="v1")
    found = rs.repeats(SCRIPT, "v2", "ep2", ledger)
    assert found == ["prior.json: script similarity 1.00"]


def test_the_same_voiceover_under_another_episode_is_a_repeat(tmp_path):
    ledger = _ledger(tmp_path, episode="ep1", script="something else entirely here", voice_sha256="v1")
    assert rs.repeats(SCRIPT, "v1", "ep2", ledger) == ["prior.json: the same voiceover file"]


def test_a_re_render_of_the_same_episode_is_not_a_repeat(tmp_path):
    ledger = _ledger(tmp_path, episode="ep1", script=SCRIPT, voice_sha256="v1")
    assert rs.repeats(SCRIPT, "v1", "ep1", ledger) == []


def test_a_different_script_is_not_a_repeat(tmp_path):
    other = "Most people back up their phone the wrong way. Open settings and look for storage."
    ledger = _ledger(tmp_path, episode="ep1", script=other, voice_sha256="v1")
    assert rs.repeats(SCRIPT, "v2", "ep2", ledger) == []


def test_an_unreadable_manifest_is_skipped_and_a_missing_ledger_is_empty(tmp_path):
    ledger = tmp_path / "ledger"
    ledger.mkdir()
    (ledger / "bad.json").write_text("{", encoding="utf-8")
    assert rs.repeats(SCRIPT, "v", "ep", ledger) == []
    assert rs.repeats(SCRIPT, "v", "ep", tmp_path / "absent") == []


def test_agreement_separates_the_right_recording_from_the_wrong_one():
    spoken = "By the end of this short you will know how to check whether an AI tool is worth your time"
    assert rs.agreement(SCRIPT, spoken) >= rs.VOICE_AGREEMENT_MIN
    assert rs.agreement(SCRIPT, "Most people back up their phone the wrong way") < rs.VOICE_AGREEMENT_MIN


def _plan(**over):
    plan = {
        "script": SCRIPT,
        "voice": Path("/v/voice.wav"),
        "clips": [(Path("/c/a.mp4"), {"duration": 12.0}), (Path("/c/b.mp4"), {"duration": 30.4})],
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
