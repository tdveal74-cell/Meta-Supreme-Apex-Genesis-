"""Sliding window buffer: ordering, the window, compression order, counters.

No database, no clock. ``frame_ms`` is pinned to 10 so the budget arithmetic
in the compression tests is exact rather than a float ceiling.
"""

import pytest

from apps.presence.buffer import SlidingWindowBuffer


def _push_run(buffer: SlidingWindowBuffer, count: int, priority: int, start_ms: float = 0.0):
    weights = {"jawOpen": 0.5} if priority == 0 else {"eyeBlinkLeft": 1.0}
    for index in range(count):
        buffer.push(start_ms + index * 10.0, weights, priority)


def test_drain_returns_frames_within_the_window_in_timeline_order():
    buffer = SlidingWindowBuffer(window_ms=250)
    buffer.push(300, {"jawOpen": 0.1}, 0)  # pushed out of order on purpose
    buffer.push(0, {"jawOpen": 0.2}, 0)
    buffer.push(250, {"jawOpen": 0.3}, 0)
    buffer.push(100, {"eyeBlinkLeft": 1.0}, 1)

    due = buffer.drain(audio_ms=0)

    assert [frame.at_ms for frame in due] == [0, 100, 250]
    assert [frame.priority for frame in due] == [0, 1, 0]
    assert len(buffer) == 1
    assert buffer.pushed == 4 and buffer.sent == 3 and buffer.dropped_total == 0

    later = buffer.drain(audio_ms=100)
    assert [frame.at_ms for frame in later] == [300]
    assert len(buffer) == 0


def test_sequence_numbers_follow_push_order_not_timeline_order():
    buffer = SlidingWindowBuffer(window_ms=100)
    first = buffer.push(50, {"jawOpen": 0.1}, 0)
    second = buffer.push(0, {"jawOpen": 0.2}, 0)
    assert (first, second) == (0, 1)
    assert [frame.seq for frame in buffer.drain(0)] == [1, 0]


def test_frames_already_in_the_past_are_still_returned():
    buffer = SlidingWindowBuffer(window_ms=250)
    buffer.push(0, {"jawOpen": 0.9}, 0)
    due = buffer.drain(audio_ms=2000)
    assert len(due) == 1 and due[0].weights == {"jawOpen": 0.9}


def test_no_compression_while_behind_is_within_the_window():
    buffer = SlidingWindowBuffer(window_ms=100, frame_ms=10)
    _push_run(buffer, 10, 0)
    _push_run(buffer, 5, 1)
    _push_run(buffer, 5, 2)
    due = buffer.drain(audio_ms=10_000, behind_ms=100)
    assert len(due) == 20
    assert buffer.dropped_total == 0 and buffer.compressions == 0


def test_stage_one_drops_only_priority_two_when_that_is_enough():
    buffer = SlidingWindowBuffer(window_ms=100, frame_ms=10)
    _push_run(buffer, 10, 0)
    _push_run(buffer, 5, 1)
    _push_run(buffer, 5, 2)
    # 50 ms over the window at 10 ms per frame: shed 5, budget 15 of 20.
    due = buffer.drain(audio_ms=10_000, behind_ms=150)
    assert len(due) == 15
    assert all(frame.priority != 2 for frame in due)
    assert buffer.dropped_by_priority == {0: 0, 1: 0, 2: 5}
    assert buffer.compressions == 1


def test_stage_two_drops_priority_one_after_priority_two():
    buffer = SlidingWindowBuffer(window_ms=100, frame_ms=10)
    _push_run(buffer, 10, 0)
    _push_run(buffer, 5, 1)
    _push_run(buffer, 5, 2)
    # 100 ms over: shed 10, budget 10. Priority 2 alone (5) is not enough.
    due = buffer.drain(audio_ms=10_000, behind_ms=200)
    assert len(due) == 10
    assert all(frame.priority == 0 for frame in due)
    assert buffer.dropped_by_priority == {0: 0, 1: 5, 2: 5}


def test_stage_three_thins_priority_zero_to_every_other_and_keeps_the_last():
    buffer = SlidingWindowBuffer(window_ms=100, frame_ms=10)
    _push_run(buffer, 10, 0)
    _push_run(buffer, 5, 1)
    _push_run(buffer, 5, 2)
    # 140 ms over: shed 14, budget 6. After 2 and 1 go, ten lip sync frames
    # thin to every other, and the last one is kept whatever its position.
    due = buffer.drain(audio_ms=10_000, behind_ms=240)
    assert [frame.at_ms for frame in due] == [0, 20, 40, 60, 80, 90]
    assert buffer.dropped_by_priority == {0: 4, 1: 5, 2: 5}


def test_thinning_repeats_until_the_backlog_fits():
    buffer = SlidingWindowBuffer(window_ms=100, frame_ms=10)
    _push_run(buffer, 20, 0)
    # 170 ms over: shed 17, budget 3. Passes: 20 -> 11 -> 6 -> 4 -> 3.
    due = buffer.drain(audio_ms=10_000, behind_ms=270)
    assert len(due) == 3
    assert due[-1].at_ms == 190.0
    assert buffer.dropped_by_priority == {0: 17, 1: 0, 2: 0}
    assert buffer.sent == 3 and buffer.pushed == 20


def test_thinning_floor_is_the_first_and_last_lip_sync_frame():
    buffer = SlidingWindowBuffer(window_ms=100, frame_ms=10)
    _push_run(buffer, 4, 0)
    assert buffer.budget_for(behind_ms=100_000) == 1
    # Every pass keeps position 0 and the last frame, so however far behind
    # the renderer is, the mouth still gets its opening and its final pose.
    due = buffer.drain(audio_ms=10_000, behind_ms=100_000)
    assert [frame.at_ms for frame in due] == [0.0, 30.0]
    assert buffer.dropped_by_priority == {0: 2, 1: 0, 2: 0}


def test_flush_empties_and_counts_by_priority():
    buffer = SlidingWindowBuffer(window_ms=100)
    _push_run(buffer, 3, 0)
    _push_run(buffer, 2, 1)
    _push_run(buffer, 1, 2)
    assert buffer.flush() == 6
    assert len(buffer) == 0
    assert buffer.dropped_by_priority == {0: 3, 1: 2, 2: 1}
    assert buffer.flush() == 0


def test_refuses_bad_priority_negative_time_and_bad_window():
    buffer = SlidingWindowBuffer(window_ms=100)
    with pytest.raises(ValueError):
        buffer.push(0, {"jawOpen": 0.1}, 3)
    with pytest.raises(ValueError):
        buffer.push(-1, {"jawOpen": 0.1}, 0)
    with pytest.raises(ValueError):
        SlidingWindowBuffer(window_ms=0)


def test_snapshot_reports_the_counters():
    buffer = SlidingWindowBuffer(window_ms=100, frame_ms=10)
    _push_run(buffer, 2, 0)
    _push_run(buffer, 1, 2)
    buffer.drain(audio_ms=10_000, behind_ms=120)
    snapshot = buffer.snapshot()
    assert snapshot["pushed"] == 3
    assert snapshot["sent"] == 2
    assert snapshot["dropped_by_priority"] == {0: 0, 1: 0, 2: 1}
    assert snapshot["dropped_total"] == 1
    assert snapshot["queued"] == 0
    assert snapshot["window_ms"] == 100.0
