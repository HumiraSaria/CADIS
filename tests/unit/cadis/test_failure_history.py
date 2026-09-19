"""Unit tests for Signal 2 -- Failure History / FH (CadisClaude.md section 6.2)."""

import pytest

from pentestagent.cadis.signals import failure_history as fh
from pentestagent.cadis.signals.failure_history import (
    FAILURE,
    PARTIAL,
    SUCCESS,
    TIMEOUT,
    FailureHistoryWindow,
)

# --- severity weights ---------------------------------------------------------


def test_outcome_weights_match_spec():
    assert fh.outcome_weight(SUCCESS) == 0.0
    assert fh.outcome_weight(PARTIAL) == 0.3
    assert fh.outcome_weight(TIMEOUT) == 0.5
    assert fh.outcome_weight(FAILURE) == 1.0


def test_unknown_outcome_raises():
    with pytest.raises(ValueError):
        fh.outcome_weight("exploded")


# --- FH(t) mean over the window -----------------------------------------------


def test_empty_history_is_zero():
    assert fh.failure_history([]) == 0.0


def test_all_success_is_zero():
    assert fh.failure_history([SUCCESS] * 10) == 0.0


def test_all_failure_is_one():
    assert fh.failure_history([FAILURE] * 10) == 1.0


def test_worked_example_two_failures_one_timeout_over_ten():
    # CadisClaude.md section 6.6: 2 failures + 1 timeout + 7 success over K=10
    # FH = (2*1.0 + 1*0.5 + 7*0.0) / 10 = 0.25
    window = [FAILURE, FAILURE, TIMEOUT] + [SUCCESS] * 7
    assert fh.failure_history(window, k=10) == pytest.approx(0.25)


def test_window_uses_last_k_only():
    # k=3 -> only the 3 most recent count
    outcomes = [FAILURE, FAILURE, SUCCESS, SUCCESS, SUCCESS]
    assert fh.failure_history(outcomes, k=3) == pytest.approx(0.0)


def test_fewer_than_k_averages_over_available():
    assert fh.failure_history([FAILURE], k=10) == pytest.approx(1.0)
    assert fh.failure_history([FAILURE, SUCCESS], k=10) == pytest.approx(0.5)


# --- outcome classification (section 6.2, Q1) ---------------------------------


def test_classify_timeout():
    assert fh.classify_outcome(success=False, timed_out=True) == TIMEOUT


def test_classify_failure_on_not_success_or_error():
    assert fh.classify_outcome(success=False) == FAILURE
    assert fh.classify_outcome(success=True, error="boom") == FAILURE


def test_classify_partial_when_no_useful_output():
    assert fh.classify_outcome(success=True, has_useful_output=False) == PARTIAL


def test_classify_success():
    assert fh.classify_outcome(success=True, has_useful_output=True) == SUCCESS


# --- live sliding window ------------------------------------------------------


def test_window_value_and_maxlen():
    w = FailureHistoryWindow(k=3)
    for o in [SUCCESS, FAILURE, FAILURE, FAILURE]:  # oldest SUCCESS evicted
        w.record(o)
    assert len(w) == 3
    assert w.value() == pytest.approx(1.0)


# --- classify_terminal_outcome (D4, v0.2.0) -----------------------------------


def test_terminal_timeout():
    assert fh.classify_terminal_outcome(124, "", "") == TIMEOUT
    assert fh.classify_terminal_outcome(1, "", "command timed out after 5s") == TIMEOUT


def test_terminal_success_and_partial_on_zero_exit():
    assert fh.classify_terminal_outcome(0, "PORT 80 open", "") == SUCCESS
    assert fh.classify_terminal_outcome(0, "   ", "") == PARTIAL  # ran clean, no output


def test_terminal_failure_invalid_command():
    assert (
        fh.classify_terminal_outcome(127, "", "bash: foobar: command not found")
        == FAILURE
    )
    assert (
        fh.classify_terminal_outcome(2, "", "nmap: unrecognized option '--frobnicate'")
        == FAILURE
    )
    assert fh.classify_terminal_outcome(1, "", "Usage: curl [options] url") == FAILURE


def test_terminal_failure_nonexistent_path_or_target():
    assert (
        fh.classify_terminal_outcome(1, "", "cat: /nope: No such file or directory")
        == FAILURE
    )
    assert (
        fh.classify_terminal_outcome(
            6, "", "curl: (6) Could not resolve host: nope.invalid"
        )
        == FAILURE
    )


def test_terminal_environmental_is_partial_not_failure():
    assert (
        fh.classify_terminal_outcome(7, "", "curl: (7) Connection refused") == PARTIAL
    )
    assert fh.classify_terminal_outcome(1, "", "Permission denied") == PARTIAL


def test_terminal_unrecognised_nonzero_is_conservative_partial():
    assert fh.classify_terminal_outcome(3, "some output", "weird error") == PARTIAL


def test_terminal_success_output_mentioning_refused_stays_success():
    # exit 0 with useful output -> SUCCESS even if the text contains an env keyword
    # (e.g. an nmap scan reporting a refused port). FAILURE requires exit_code != 0.
    out = "PORT   STATE  SERVICE\n21/tcp closed ftp (connection refused)"
    assert fh.classify_terminal_outcome(0, out, "") == SUCCESS
