"""
The wager, tested against the ways a prediction gets quoted as a result.

The two that matter: `test_an_open_wager_cannot_be_read_as_a_result` drives
every derived property of an unsettled wager and asserts each one refuses, and
`test_calibration_over_nothing_is_none_not_zero` pins the difference between a
bias of zero measured over forty wagers and a bias of zero measured over none,
which print the same and mean opposite things.
"""

from __future__ import annotations

import pytest

from services.devon.wager import (
    Measurement,
    Wager,
    WagerBook,
    WagerError,
    open_wager,
)


def cycle_time() -> Wager:
    """The teardown's own example: nobody had measured the render cycle."""
    return open_wager(
        subject="index scoped prompt on the TQO script lane",
        metric="script doctor score",
        baseline=71.0,
        baseline_receipt="ten monolith scripts, mean 71.0, run 2026-09-17",
        predicted=78.0,
        rationale="Scoping should raise proof density without touching voice fidelity.",
    )


def test_a_measurement_with_no_receipt_is_refused():
    with pytest.raises(WagerError) as caught:
        Measurement(value=42.0, receipt="")
    assert "carries no receipt" in str(caught.value)


def test_a_measurement_that_is_not_a_number_is_refused():
    with pytest.raises(WagerError):
        Measurement(value="lots", receipt="the log")
    with pytest.raises(WagerError):
        Measurement(value=True, receipt="the log")


def test_a_wager_with_no_metric_is_refused():
    """'It will be better' cannot later be shown wrong, so it is not a prediction."""
    with pytest.raises(WagerError) as caught:
        Wager(
            subject="the new prompt",
            metric="   ",
            baseline=Measurement(value=1.0, receipt="run 1"),
            predicted=2.0,
        )
    assert "not a prediction" in str(caught.value)


def test_the_baseline_receipt_is_forced_through_the_convenience_constructor():
    with pytest.raises(WagerError):
        open_wager(
            subject="s",
            metric="m",
            baseline=10.0,
            baseline_receipt="",
            predicted=12.0,
        )


def test_an_open_wager_cannot_be_read_as_a_result():
    wager = cycle_time()
    assert wager.settled is False
    assert wager.predicted_delta == 7.0

    for name in ("actual_delta", "miss", "absolute_miss", "direction_held"):
        with pytest.raises(WagerError) as caught:
            getattr(wager, name)
        assert "is open" in str(caught.value)

    assert "OPEN" in wager.render()
    assert "Not evidence" in wager.render()


def test_settling_records_the_miss_and_the_direction():
    settled = cycle_time().settle(
        Measurement(value=74.0, receipt="ten scoped scripts, mean 74.0, run 2026-09-17")
    )
    assert settled.settled is True
    assert settled.actual_delta == 3.0
    assert settled.predicted_delta == 7.0
    assert settled.miss == -4.0
    assert settled.absolute_miss == 4.0
    assert settled.direction_held is True
    assert settled.within(4.0) is True
    assert settled.within(3.9) is False
    assert "miss: -4" in settled.render()


def test_a_bad_estimate_and_a_wrong_theory_are_told_apart():
    """Predicting a gain and getting a smaller gain is not the same failure as
    predicting a gain and getting a loss, and only one is a reason to stop."""
    small = cycle_time().settle(Measurement(value=72.0, receipt="run a"))
    assert small.direction_held is True

    backwards = cycle_time().settle(Measurement(value=68.0, receipt="run b"))
    assert backwards.direction_held is False
    assert "WRONG WAY" in backwards.render()

    flat = cycle_time().settle(Measurement(value=71.0, receipt="run c"))
    assert flat.direction_held is False


def test_a_prediction_of_no_change_holds_only_when_nothing_changed():
    steady = open_wager(
        subject="no op refactor",
        metric="latency ms",
        baseline=200.0,
        baseline_receipt="p50 over 1000 requests",
        predicted=200.0,
    )
    assert steady.settle(Measurement(value=200.0, receipt="rerun")).direction_held is True
    assert steady.settle(Measurement(value=205.0, receipt="rerun")).direction_held is False


def test_settling_twice_is_refused():
    settled = cycle_time().settle(Measurement(value=74.0, receipt="run a"))
    with pytest.raises(WagerError) as caught:
        settled.settle(Measurement(value=79.0, receipt="run b"))
    assert "already settled" in str(caught.value)


def test_settling_with_a_bare_number_is_refused():
    """The outcome carries its receipt or it is not an outcome."""
    with pytest.raises(WagerError) as caught:
        cycle_time().settle(74.0)
    assert "takes a Measurement" in str(caught.value)


def test_the_original_wager_is_not_mutated_by_settling():
    original = cycle_time()
    settled = original.settle(Measurement(value=74.0, receipt="run a"))
    assert original.settled is False
    assert settled is not original


def test_calibration_over_nothing_is_none_not_zero():
    book = WagerBook()
    assert book.calibration("script doctor score") is None
    book.add(cycle_time())
    assert book.calibration("script doctor score") is None, "an open wager is not data"


def test_calibration_reports_bias_and_direction_over_settled_wagers():
    book = WagerBook()
    book.add(cycle_time().settle(Measurement(value=74.0, receipt="a")))
    book.add(cycle_time().settle(Measurement(value=72.0, receipt="b")))
    book.add(cycle_time().settle(Measurement(value=68.0, receipt="c")))

    calibration = book.calibration("script doctor score")
    assert calibration is not None
    assert calibration.count == 3
    assert calibration.bias == pytest.approx((-4.0 + -6.0 + -10.0) / 3)
    assert calibration.mean_absolute_miss == pytest.approx((4.0 + 6.0 + 10.0) / 3)
    assert calibration.direction_hits == 2
    assert calibration.direction_rate == pytest.approx(2 / 3)
    assert "3 settled" in calibration.render()


def test_the_miss_is_carried_into_the_next_prediction():
    """Consistently optimistic by five points means the next one starts five lower."""
    book = WagerBook()
    for actual in (95.0, 95.0):
        book.add(
            open_wager(
                subject="s",
                metric="throughput",
                baseline=80.0,
                baseline_receipt="measured",
                predicted=100.0,
            ).settle(Measurement(value=actual, receipt="measured after"))
        )

    adjusted = book.adjust(raw=100.0, metric="throughput")
    assert adjusted.applied is True
    assert adjusted.adjusted == pytest.approx(95.0)
    assert "ran -5" in adjusted.reason
    assert "adjusted to 95" in adjusted.render()


def test_an_unadjusted_prediction_says_it_is_a_guess():
    book = WagerBook()
    adjusted = book.adjust(raw=100.0, metric="throughput")
    assert adjusted.applied is False
    assert adjusted.adjusted == 100.0
    assert "it is a guess" in adjusted.reason
    assert "unadjusted" in adjusted.render()


def test_calibration_does_not_mix_metrics():
    book = WagerBook()
    book.add(
        open_wager(
            subject="s",
            metric="throughput",
            baseline=80.0,
            baseline_receipt="m",
            predicted=100.0,
        ).settle(Measurement(value=90.0, receipt="m"))
    )
    book.add(cycle_time().settle(Measurement(value=74.0, receipt="m")))

    throughput = book.calibration("throughput")
    score = book.calibration("script doctor score")
    assert throughput is not None and score is not None
    assert throughput.bias == pytest.approx(-10.0)
    assert score.bias == pytest.approx(-4.0)
    assert book.adjust(raw=50.0, metric="throughput").adjusted == pytest.approx(40.0)


def test_the_book_separates_open_from_settled():
    book = WagerBook()
    book.add(cycle_time())
    book.add(cycle_time().settle(Measurement(value=74.0, receipt="m")))
    assert len(book.open()) == 1
    assert len(book.settled()) == 1
    rendered = book.render()
    assert "2 wager(s), 1 settled, 1 open" in rendered
    assert "CALIBRATION (script doctor score)" in rendered


def test_a_negative_tolerance_is_refused():
    settled = cycle_time().settle(Measurement(value=74.0, receipt="m"))
    with pytest.raises(WagerError):
        settled.within(-1.0)
