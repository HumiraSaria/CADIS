"""Unit tests for the pure fusion/mapping core (CadisClaude.md section 6).

These transcribe the spec formulas 1:1, including the section 6.6 worked example.
"""

import pytest

from pentestagent.cadis import policy_core as core

# --- Composite score I(t) (section 6.4) ---------------------------------------


def test_worked_example_composite_is_0446():
    # CadisClaude.md section 6.6: USC=0.40, FH=0.25, RC=0.66, default weights.
    # I = 0.35*0.40 + 0.30*0.25 + 0.35*0.66 = 0.140 + 0.075 + 0.231 = 0.446
    i = core.compute_composite(0.40, 0.25, 0.66)
    assert i == pytest.approx(0.446, abs=1e-9)


def test_composite_bounds_zero_and_one():
    assert core.compute_composite(0.0, 0.0, 0.0) == pytest.approx(0.0)
    assert core.compute_composite(1.0, 1.0, 1.0) == pytest.approx(1.0)


def test_composite_respects_custom_weights():
    assert core.compute_composite(1.0, 0.0, 0.0, (0.5, 0.3, 0.2)) == pytest.approx(0.5)


# --- band_level (section 6.5, step 1; tau = 0.25/0.50/0.75) --------------------


@pytest.mark.parametrize(
    "score,expected",
    [
        (0.0, 0),
        (0.2499, 0),
        (0.25, 1),
        (0.4999, 1),
        (0.50, 2),
        (0.7499, 2),
        (0.75, 3),
        (1.0, 3),
    ],
)
def test_band_level_boundaries(score, expected):
    assert core.band_level(score) == expected


# --- risk_floor (section 6.5, step 2) -----------------------------------------


@pytest.mark.parametrize(
    "rc,expected",
    [(0.0, 0), (0.33, 1), (0.66, 2), (1.0, 3)],
)
def test_risk_floor_tiers(rc, expected):
    assert core.risk_floor(rc) == expected


# --- map_to_level = max(band_level, risk_floor) (section 6.5, step 3) ----------


def test_worked_example_maps_to_level_2():
    # I=0.446 -> band 1; RC=0.66 -> floor 2; level = max(1,2) = 2 (Suggest).
    i = core.compute_composite(0.40, 0.25, 0.66)
    assert core.band_level(i) == 1
    assert core.risk_floor(0.66) == 2
    assert core.map_to_level(i, 0.66) == 2


def test_critical_is_hard_floor_L3_regardless_of_score():
    # RC=1.0 -> level 3 even when the composite score is 0.
    assert core.map_to_level(0.0, 1.0) == 3


def test_risk_raises_but_never_lowers():
    # High score (band 3) with LOW risk stays 3 (risk cannot lower it).
    assert core.map_to_level(0.9, 0.0) == 3
    # Low score (band 0) with HIGH risk is pulled up to the floor (2).
    assert core.map_to_level(0.1, 0.66) == 2


# --- validation ---------------------------------------------------------------


def test_validate_weights_rejects_non_unit_sum():
    with pytest.raises(ValueError):
        core.validate_weights((0.5, 0.3, 0.3))


def test_validate_weights_rejects_nonpositive():
    with pytest.raises(ValueError):
        core.validate_weights((0.7, 0.3, 0.0))


def test_default_weights_and_thresholds_are_valid():
    core.validate_weights(core.DEFAULT_WEIGHTS)
    core.validate_thresholds(core.DEFAULT_THRESHOLDS)


def test_validate_thresholds_rejects_unordered():
    with pytest.raises(ValueError):
        core.validate_thresholds((0.5, 0.25, 0.75))
