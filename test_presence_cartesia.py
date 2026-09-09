"""Cartesia speech: the vendor contract, and a face driven by real audio.

`CartesiaSpeech` was a stub that raised by name until 2026-09-09. It is now a
real SSE client, and this file holds the two halves of that apart.

WHAT IS PROVEN HERE

The request this estate sends: URL, headers, and every field of the body,
checked against the vendor's own generated client (`cartesia==4.2.0` from PyPI,
read 2026-09-09) rather than against a recollection. The arithmetic that turns
returned audio into face frames: root mean square on little endian PCM, the
envelope curve, the 60 frames per second slicing and its drift, and the word
clock. And every refusal, including the owned voice rule, which is a compliance
item rather than a default anyone may fill in.

WHAT IS NOT PROVEN HERE, AND CANNOT BE

Every byte in this file comes from an httpx MockTransport. A mock transport is
not a key. Nothing here says Cartesia accepts this request, that the model id is
one the account may use, or that the audio sounds like Tee. The remaining
evidence is a human listening to a real reply end to end.

The interleaving of `timestamps` and `chunk` events on the wire is also
unverified, which is why the face is built on amplitude rather than on word
timings. `test_a_stream_with_no_timestamps_still_moves_the_mouth` is that design
decision written down as a test: pull every timing event out of the stream and
the mouth still tracks the voice.
"""

from __future__ import annotations

import json
import math
import struct

import httpx
import pytest

from apps.presence.protocol import (
    AUDIO_RATE,
    PRIORITY_EXPRESSION,
    PRIORITY_LIP_SYNC,
    validate_frame,
)
from apps.presence.settings import CARTESIA_VOICE_RULE, PresenceConfigError, PresenceSettings
from apps.presence.speech import (
    CARTESIA_OUTPUT_FORMAT,
    CARTESIA_TTS_URL,
    CARTESIA_VERSION,
    CHUNK_AUDIO,
    CHUNK_FRAME,
    CHUNK_STATE,
    SPEECH_CEILING,
    SPEECH_FLOOR,
    STATE_DONE,
    STATE_SPEAKING,
    CartesiaSpeech,
    MockSpeech,
    SpeechNotConfigured,
    WordClock,
    blink_weight,
    build_speech,
    envelope_from_rms,
    rms_of,
    sse_payloads,
)

KEY = "sk-test-not-a-real-key"
VOICE = "voice-id-owned-by-tee"


def pcm(*samples: int) -> bytes:
    """Little endian signed 16 bit, written out rather than assumed native."""
    return struct.pack("<" + "h" * len(samples), *samples)


def tone(amplitude: int, samples: int) -> bytes:
    """A full scale square wave at `amplitude`, so its RMS is exactly amplitude."""
    return pcm(*[amplitude if index % 2 == 0 else -amplitude for index in range(samples)])


def sse(events: list) -> bytes:
    return ("".join(f"data: {json.dumps(event)}\n\n" for event in events)).encode()


def chunk_event(audio: bytes) -> dict:
    import base64

    return {
        "type": "chunk",
        "data": base64.b64encode(audio).decode(),
        "done": False,
        "status_code": 206,
        "step_time": 4.2,
    }


def timestamps_event(words, starts, ends) -> dict:
    return {
        "type": "timestamps",
        "done": False,
        "status_code": 206,
        "word_timestamps": {"words": words, "start": starts, "end": ends},
    }


DONE_EVENT = {"type": "done", "done": True, "status_code": 200}


def speaker(body: bytes, *, status: int = 200, seen: list | None = None) -> CartesiaSpeech:
    def handler(request: httpx.Request) -> httpx.Response:
        if seen is not None:
            seen.append(request)
        return httpx.Response(
            status, content=body, headers={"content-type": "text/event-stream"}
        )

    return CartesiaSpeech(
        KEY, VOICE, transport=httpx.MockTransport(handler)
    )


async def collect(synth, text="hello", turn="t1"):
    return [chunk async for chunk in synth.synthesize(text, turn)]


# -- the vendor contract ---------------------------------------------------


def test_the_endpoint_and_headers_match_the_vendor_client():
    """Read from `cartesia==4.2.0`: _client.py:130, :236, :244."""
    assert CARTESIA_TTS_URL == "https://api.cartesia.ai/tts/sse"
    assert CARTESIA_VERSION == "2026-08-14"
    headers = CartesiaSpeech(KEY, VOICE).headers()
    assert headers["Authorization"] == f"Bearer {KEY}"
    assert headers["Cartesia-Version"] == CARTESIA_VERSION
    assert headers["Accept"] == "text/event-stream"


def test_the_body_asks_for_audio_this_protocol_can_send_unchanged():
    """`raw` + `pcm_s16le` + AUDIO_RATE means nothing resamples anywhere."""
    assert CARTESIA_OUTPUT_FORMAT == {
        "container": "raw",
        "encoding": "pcm_s16le",
        "sample_rate": AUDIO_RATE,
    }
    body = CartesiaSpeech(KEY, VOICE, model="sonic-3", language="en").request_body("hi", "t9")
    assert body["model_id"] == "sonic-3"
    assert body["transcript"] == "hi"
    assert body["voice"] == {"id": VOICE}
    assert body["output_format"] == CARTESIA_OUTPUT_FORMAT
    assert body["add_timestamps"] is True
    assert body["context_id"] == "t9"


@pytest.mark.asyncio
async def test_the_request_actually_sent_is_the_one_the_body_describes():
    """The body above is only a claim until a request carries it."""
    seen: list = []
    synth = speaker(sse([chunk_event(tone(6000, 320)), DONE_EVENT]), seen=seen)
    await collect(synth)
    assert len(seen) == 1
    request = seen[0]
    assert str(request.url) == CARTESIA_TTS_URL
    assert request.headers["cartesia-version"] == CARTESIA_VERSION
    assert json.loads(request.content)["voice"] == {"id": VOICE}


# -- the arithmetic that turns audio into a face ---------------------------


def test_rms_reads_little_endian_whatever_the_host_is():
    assert rms_of(b"") == 0.0
    assert rms_of(pcm(0, 0, 0, 0)) == 0.0
    assert rms_of(tone(1000, 8)) == pytest.approx(1000.0)
    # One byte is not a sample and must not be read as one.
    assert rms_of(b"\x01") == 0.0
    # A negative sample must not read as a huge positive one, which is what an
    # unsigned or byte swapped read would do.
    assert rms_of(pcm(-1000, -1000)) == pytest.approx(1000.0)


def test_the_envelope_closes_on_quiet_and_saturates_on_loud():
    assert envelope_from_rms(0.0) == 0.0
    assert envelope_from_rms(SPEECH_FLOOR * 32768.0) == 0.0
    assert envelope_from_rms(SPEECH_CEILING * 32768.0) == pytest.approx(1.0)
    assert envelope_from_rms(32768.0) == pytest.approx(1.0)
    middle = envelope_from_rms((SPEECH_FLOOR + SPEECH_CEILING) / 2 * 32768.0)
    assert 0.0 < middle < 1.0


def test_the_envelope_never_falls_as_the_audio_gets_louder():
    levels = [envelope_from_rms(step * 1000.0) for step in range(0, 34)]
    assert levels == sorted(levels)


def test_frames_land_on_a_sixty_per_second_grid_without_drifting():
    """266.67 samples a frame truncated to 266 would run a frame fast a minute in."""
    synth = CartesiaSpeech(KEY, VOICE)
    one_minute = AUDIO_RATE * 60
    frames = synth.frames_for(tone(6000, one_minute), 0, WordClock())
    lip = [f for f in frames if f.priority == PRIORITY_LIP_SYNC]
    assert len(lip) == 3600, len(lip)
    # The ideal position of frame 3599 is 3599 * 1000/60 = 59983.33 ms. Frames
    # sit on real sample boundaries, so the measured value is a fifth of a
    # sample early and that is correct rather than drift.
    assert lip[-1].at_ms == pytest.approx(59983.33, abs=0.05)
    # What the truncating version would have given, so the test states the bug
    # it prevents rather than only a number: 266 samples a frame instead of
    # 266.67 puts the last frame of a minute 150 ms early.
    truncated = 3599 * 266 / AUDIO_RATE * 1000.0
    assert truncated == pytest.approx(59833.4, abs=0.1)
    assert lip[-1].at_ms - truncated > 100.0


def test_a_chunk_that_starts_late_is_placed_late():
    synth = CartesiaSpeech(KEY, VOICE)
    frames = synth.frames_for(tone(6000, 1600), AUDIO_RATE, WordClock())
    assert frames[0].at_ms == pytest.approx(1000.0)


def test_silence_shuts_the_mouth_and_speech_opens_it():
    synth = CartesiaSpeech(KEY, VOICE)
    quiet = synth.frames_for(pcm(*([0] * 1600)), 0, WordClock())
    assert all(frame.weights.get("jawOpen", 0.0) == 0.0 for frame in quiet)
    loud = synth.frames_for(tone(12000, 1600), 0, WordClock())
    assert max(frame.weights.get("jawOpen", 0.0) for frame in loud) > 0.3


def test_every_frame_is_one_this_protocol_will_carry():
    """A blendshape name the protocol refuses fails the turn, not the frame."""
    synth = CartesiaSpeech(KEY, VOICE)
    clock = WordClock()
    clock.extend({"words": ["mabufo"], "start": [0.0], "end": [0.4]})
    for frame in synth.frames_for(tone(9000, 8000), 0, clock):
        validate_frame(frame.weights)
        assert frame.at_ms >= 0.0
        assert math.isfinite(frame.at_ms)


# -- the word clock --------------------------------------------------------


def test_a_word_chooses_the_shape_and_a_gap_chooses_none():
    clock = WordClock()
    clock.extend({"words": ["ma"], "start": [1.0], "end": [1.2]})
    assert clock.shape_at(999.0) is None
    assert clock.shape_at(1200.0) is None, "the end of a word is exclusive"
    assert clock.shape_at(1010.0) == {"jawOpen": 0.0, "mouthClose": 0.8,
                                      "mouthPressLeft": 0.5, "mouthPressRight": 0.5}
    assert clock.shape_at(1190.0) == {"jawOpen": 0.7}


def test_a_malformed_timing_block_is_ignored_rather_than_fatal():
    clock = WordClock()
    for junk in (None, "words", {"words": "ma"}, {"words": ["a"], "start": [0.0]}):
        clock.extend(junk)
    assert clock.words == []
    # Ragged lists truncate to the shortest rather than raising.
    clock.extend({"words": ["a", "b"], "start": [0.0, 1.0], "end": [0.5]})
    assert clock.words == ["a"]


def test_a_word_that_arrives_out_of_order_is_dropped():
    """The lookup bisects, so an unsorted list would corrupt every later frame."""
    clock = WordClock()
    clock.extend({"words": ["one", "two"], "start": [1.0, 0.0], "end": [1.5, 0.5]})
    assert clock.words == ["one"]


def test_a_zero_length_or_infinite_word_is_dropped():
    clock = WordClock()
    clock.extend({"words": ["a", "b"], "start": [0.0, 1.0], "end": [0.0, float("inf")]})
    assert clock.words == []


# -- the SSE reader --------------------------------------------------------


def test_sse_payloads_reads_one_event_per_blank_line():
    assert sse_payloads(["data: {}", "", "data: {\"a\": 1}", ""]) == ["{}", '{"a": 1}']


def test_sse_payloads_joins_a_payload_split_across_lines():
    assert sse_payloads(["data: {\"a\":", "data: 1}", ""]) == ['{"a":\n1}']


def test_sse_payloads_skips_comments_and_other_fields():
    assert sse_payloads([": keep alive", "event: chunk", "data: {}", ""]) == ["{}"]


# -- the stream end to end -------------------------------------------------


@pytest.mark.asyncio
async def test_audio_is_placed_end_to_end_on_the_timeline():
    """Chunk two starts where chunk one ended, in milliseconds of real audio."""
    first = tone(8000, 1600)      # 100 ms
    second = tone(8000, 3200)     # 200 ms
    synth = speaker(sse([chunk_event(first), chunk_event(second), DONE_EVENT]))
    chunks = await collect(synth)

    audio = [c for c in chunks if c.kind == CHUNK_AUDIO]
    assert [c.at_ms for c in audio] == [0.0, 100.0]
    assert audio[0].pcm == first and audio[1].pcm == second

    states = [c for c in chunks if c.kind == CHUNK_STATE]
    assert states[0].state == STATE_SPEAKING and states[0].at_ms == 0.0
    assert states[-1].state == STATE_DONE
    assert states[-1].at_ms == pytest.approx(300.0)


@pytest.mark.asyncio
async def test_word_timings_choose_the_shape_when_they_arrive_in_time():
    """The timestamps event precedes the audio it describes in this stream."""
    synth = speaker(
        sse([
            timestamps_event(["ma"], [0.0], [0.1]),
            chunk_event(tone(9000, 1600)),
            DONE_EVENT,
        ])
    )
    frames = [c for c in await collect(synth) if c.kind == CHUNK_FRAME]
    lip = [f for f in frames if f.priority == PRIORITY_LIP_SYNC]
    assert lip, "no lip frames were produced"
    # "m" closes the lips, which the neutral fallback shape never does.
    assert any(f.weights.get("mouthClose", 0.0) > 0.0 for f in lip)


@pytest.mark.asyncio
async def test_a_stream_with_no_timestamps_still_moves_the_mouth():
    """The design decision, written down.

    The interleaving of timestamps and audio on the live wire is unverified, so
    the face must not depend on it. Strip every timing event and the jaw still
    tracks the amplitude of the voice.
    """
    synth = speaker(sse([chunk_event(tone(11000, 4800)), DONE_EVENT]))
    frames = [c for c in await collect(synth) if c.kind == CHUNK_FRAME]
    lip = [f for f in frames if f.priority == PRIORITY_LIP_SYNC]
    assert len(lip) >= 17
    assert max(f.weights.get("jawOpen", 0.0) for f in lip) > 0.3


@pytest.mark.asyncio
async def test_timings_that_arrive_late_never_produce_a_wrong_frame():
    """Frames already sent were less articulate, not misplaced.

    The same audio with the timing block after it must land on exactly the same
    timeline as the audio with the timing block before it.
    """
    audio = tone(9000, 1600)
    early = speaker(sse([timestamps_event(["ma"], [0.0], [0.1]), chunk_event(audio), DONE_EVENT]))
    late = speaker(sse([chunk_event(audio), timestamps_event(["ma"], [0.0], [0.1]), DONE_EVENT]))
    early_frames = [c for c in await collect(early) if c.kind == CHUNK_FRAME]
    late_frames = [c for c in await collect(late) if c.kind == CHUNK_FRAME]

    # The timeline is identical either way. That is the load bearing half.
    assert [f.at_ms for f in early_frames] == [f.at_ms for f in late_frames]

    # And the cost of arriving late is articulation, nothing else: the early
    # stream forms the "m" and the late one holds the neutral shape.
    assert any(f.weights.get("mouthClose", 0.0) > 0.0 for f in early_frames)
    assert all(f.weights.get("mouthClose", 0.0) == 0.0 for f in late_frames)


@pytest.mark.asyncio
async def test_the_face_blinks_on_the_same_envelope_as_the_mock():
    """Two copies of a blink curve would drift and only feel wrong."""
    assert MockSpeech().blink_weight(1500.0) == blink_weight(1500.0)
    synth = speaker(sse([chunk_event(tone(9000, AUDIO_RATE * 2)), DONE_EVENT]))
    frames = [c for c in await collect(synth) if c.kind == CHUNK_FRAME]
    assert any(f.priority == PRIORITY_EXPRESSION for f in frames)


@pytest.mark.asyncio
async def test_an_empty_reply_says_nothing_and_calls_nobody():
    seen: list = []
    synth = speaker(sse([DONE_EVENT]), seen=seen)
    chunks = await collect(synth, text="   ")
    assert [c.state for c in chunks] == [STATE_SPEAKING, STATE_DONE]
    assert seen == [], "an empty reply must not spend a vendor call"


@pytest.mark.asyncio
async def test_a_malformed_event_does_not_kill_a_reply_that_is_speaking():
    body = b"data: not json\n\n" + sse([chunk_event(tone(8000, 1600)), DONE_EVENT])
    synth = speaker(body)
    audio = [c for c in await collect(synth) if c.kind == CHUNK_AUDIO]
    assert len(audio) == 1


@pytest.mark.asyncio
async def test_an_unknown_event_type_is_passed_over():
    """phoneme_timestamps today, whatever a later API version adds tomorrow."""
    body = sse([
        {"type": "phoneme_timestamps", "done": False, "status_code": 206,
         "phoneme_timestamps": {"phonemes": ["m"], "start": [0.0], "end": [0.1]}},
        chunk_event(tone(8000, 1600)),
        DONE_EVENT,
    ])
    audio = [c for c in await collect(speaker(body)) if c.kind == CHUNK_AUDIO]
    assert len(audio) == 1


# -- the refusals ----------------------------------------------------------


@pytest.mark.asyncio
async def test_an_http_refusal_names_the_status_and_the_body():
    synth = speaker(b'{"error":"bad key"}', status=401)
    with pytest.raises(SpeechNotConfigured) as raised:
        await collect(synth)
    assert "401" in str(raised.value)
    assert "bad key" in str(raised.value)


@pytest.mark.asyncio
async def test_an_error_event_stops_the_turn_by_name():
    body = sse([{
        "type": "error", "done": True, "status_code": 402,
        "title": "Insufficient credits", "message": "top up the account",
        "request_id": "req-1",
    }])
    with pytest.raises(SpeechNotConfigured) as raised:
        await collect(speaker(body))
    assert "Insufficient credits" in str(raised.value)


def test_a_missing_key_refuses_at_construction():
    with pytest.raises(SpeechNotConfigured):
        CartesiaSpeech("", VOICE)


def test_a_missing_voice_refuses_and_names_the_owned_voice_rule():
    """Compliance item, not a default. There is no exception path for this one."""
    with pytest.raises(SpeechNotConfigured) as raised:
        CartesiaSpeech(KEY, "")
    assert "owned and never rented" in str(raised.value)


# -- configuration ---------------------------------------------------------


def _env(**overrides) -> dict:
    base = {
        "ENVIRONMENT": "test",
        "PRESENCE_SPEECH": "cartesia",
        "CARTESIA_API_KEY": KEY,
        "CARTESIA_VOICE_ID": VOICE,
    }
    base.update(overrides)
    return base


def test_the_cartesia_lane_needs_a_key_and_a_voice_to_start():
    PresenceSettings.from_env(_env())
    with pytest.raises(PresenceConfigError) as no_key:
        PresenceSettings.from_env(_env(CARTESIA_API_KEY=""))
    assert "CARTESIA_API_KEY" in str(no_key.value)
    with pytest.raises(PresenceConfigError) as no_voice:
        PresenceSettings.from_env(_env(CARTESIA_VOICE_ID=""))
    assert str(no_voice.value) == CARTESIA_VOICE_RULE


def test_the_mock_lane_needs_neither():
    settings = PresenceSettings.from_env({"ENVIRONMENT": "test", "PRESENCE_SPEECH": "mock"})
    assert build_speech(settings).name == "mock"


def test_build_speech_hands_back_a_configured_cartesia():
    synth = build_speech(PresenceSettings.from_env(_env(CARTESIA_MODEL="sonic-3.5")))
    assert synth.name == "cartesia"
    assert synth.configured is True
    assert synth.model == "sonic-3.5"
    assert synth.voice_id == VOICE


def test_no_stock_voice_id_is_written_into_this_repository():
    """The rule is that identity is owned. A default here would rent one.

    A voice id in a settings default would be a stock voice by construction:
    Tee's own clone is account scoped and is never a value this repository can
    know. So the default must stay empty and this test is the guard.
    """
    assert PresenceSettings().CARTESIA_VOICE_ID == ""
    assert PresenceSettings.from_env({"ENVIRONMENT": "test"}).CARTESIA_VOICE_ID == ""
