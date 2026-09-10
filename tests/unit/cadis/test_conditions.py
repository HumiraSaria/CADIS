"""Unit tests for the four benchmark conditions (newplan.md section 7)."""

import pytest

from pentestagent.cadis.conditions import (
    CONDITIONS,
    RandomBudget,
    RandomPolicy,
    cadis_policy,
    full_autonomy_policy,
    get_condition_policy,
    static_hitl_policy,
)
from pentestagent.cadis.engine import ScoreResult


def _score(final_level=0, risk_floor=0, rc=0.0) -> ScoreResult:
    return ScoreResult(
        proposed_action="a",
        usc=0.0,
        fh=0.0,
        rc=rc,
        intervention_score=0.0,
        band_level=final_level,
        risk_floor=risk_floor,
        final_level=final_level,
        risk_tier="low",
        risk_matched=True,
        n_samples=0,
    )


# --- fixed-level baselines ----------------------------------------------------


def test_full_autonomy_always_l0_even_for_critical():
    assert full_autonomy_policy(_score(final_level=3, risk_floor=3, rc=1.0)) == 0


def test_static_hitl_always_l2():
    assert static_hitl_policy(_score(final_level=0)) == 2
    assert static_hitl_policy(_score(final_level=3, risk_floor=3, rc=1.0)) == 2


def test_cadis_returns_final_level():
    assert cadis_policy(_score(final_level=2)) == 2
    assert cadis_policy(_score(final_level=3, risk_floor=3, rc=1.0)) == 3


# --- RandomBudget derivation --------------------------------------------------


def test_random_budget_from_levels():
    b = RandomBudget.from_levels([0, 0, 2, 3, 1])
    assert b.her == pytest.approx(3 / 5)
    assert b.level_probs == {
        1: pytest.approx(1 / 3),
        2: pytest.approx(1 / 3),
        3: pytest.approx(1 / 3),
    }


def test_random_budget_empty():
    b = RandomBudget.from_levels([])
    assert b.her == 0.0


# --- RandomPolicy -------------------------------------------------------------


def test_random_policy_is_deterministic_given_seed():
    budget = RandomBudget.from_levels([0, 1, 2, 3, 2, 0, 2])
    a = RandomPolicy(budget, seed=42)
    b = RandomPolicy(budget, seed=42)
    scores = [_score() for _ in range(30)]
    assert [a(s) for s in scores] == [b(s) for s in scores]


def test_random_policy_keeps_critical_floor():
    budget = RandomBudget(her=0.0, level_probs={1: 0.0, 2: 0.0, 3: 0.0})
    pol = RandomPolicy(budget, seed=1)
    assert pol(_score(risk_floor=3, rc=1.0)) == 3


def test_random_policy_her_zero_never_intervenes_noncritical():
    budget = RandomBudget(her=0.0, level_probs={1: 0.0, 2: 0.0, 3: 0.0})
    pol = RandomPolicy(budget, seed=7)
    assert all(pol(_score()) == 0 for _ in range(50))


def test_random_policy_her_one_always_intervenes():
    budget = RandomBudget(her=1.0, level_probs={2: 1.0})
    pol = RandomPolicy(budget, seed=7)
    assert all(pol(_score()) == 2 for _ in range(50))


def test_random_policy_matches_target_her_rate():
    budget = RandomBudget(her=0.6, level_probs={1: 0.3, 2: 0.5, 3: 0.2})
    pol = RandomPolicy(budget, seed=123)
    draws = [pol(_score()) for _ in range(2000)]
    rate = sum(1 for d in draws if d >= 1) / len(draws)
    assert 0.55 < rate < 0.65  # matched to CADIS's HER within sampling noise


# --- dispatch -----------------------------------------------------------------


def test_get_condition_policy_dispatch():
    assert get_condition_policy("full_autonomy")(_score(final_level=3)) == 0
    assert get_condition_policy("static_hitl")(_score()) == 2
    assert get_condition_policy("cadis")(_score(final_level=1)) == 1


def test_random_condition_requires_budget():
    with pytest.raises(ValueError):
        get_condition_policy("random")


def test_unknown_condition_raises():
    with pytest.raises(ValueError):
        get_condition_policy("floor_only")  # out of scope, must not be selectable


def test_conditions_tuple_is_exactly_the_four():
    assert CONDITIONS == ("full_autonomy", "static_hitl", "random", "cadis")
