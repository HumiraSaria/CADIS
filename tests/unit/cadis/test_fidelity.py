"""S12 fidelity verification — newplan.md section 17 post-implementation checklist.

Each test corresponds to a checklist item; together they establish that the executed
protocol matches the spec. (The 'analysis reproduces metrics from logs' item is covered
by tests/unit/benchmark/test_analyse.py::test_analyse_end_to_end.)
"""

import pytest

from pentestagent.cadis import policy_core as core
from pentestagent.cadis.conditions import (
    RandomBudget,
    RandomPolicy,
    cadis_policy,
    full_autonomy_policy,
    static_hitl_policy,
)
from pentestagent.cadis.engine import ScoreResult
from pentestagent.cadis.gate import GateRecord
from pentestagent.cadis.recorder import RunRecorder
from pentestagent.cadis.sampler import SelfConsistencySampler


def _score(
    usc, fh, rc, weights=core.DEFAULT_WEIGHTS, thresholds=core.DEFAULT_THRESHOLDS
):
    i = core.compute_composite(usc, fh, rc, weights)
    return ScoreResult(
        proposed_action="a",
        usc=usc,
        fh=fh,
        rc=rc,
        intervention_score=i,
        band_level=core.band_level(i, thresholds),
        risk_floor=core.risk_floor(rc),
        final_level=core.map_to_level(i, rc, thresholds),
        risk_tier="high",
        risk_matched=True,
        n_samples=5,
    )


# item: pure-function core matches section 3/6 formulas 1:1 -------------------


def test_pure_core_matches_worked_example():
    i = core.compute_composite(0.40, 0.25, 0.66)
    assert i == pytest.approx(0.446, abs=1e-9)
    assert core.band_level(i) == 1
    assert core.risk_floor(0.66) == 2
    assert core.map_to_level(i, 0.66) == 2
    # CRITICAL hard floor regardless of score
    assert core.map_to_level(0.0, 1.0) == 3


# item: a sample run's I(t)/level recompute EXACTLY from logged signals --------


def test_logged_row_recomputes_from_signals(tmp_path):
    rec = RunRecorder(
        tmp_path,
        "cadis",
        "dvwa-sqli",
        1,
        7,
        core.DEFAULT_WEIGHTS,
        core.DEFAULT_THRESHOLDS,
    )
    score = _score(0.40, 0.25, 0.66)
    gr = GateRecord(
        action="a",
        score=score,
        level=score.final_level,
        executed=True,
        outcome="failure",
        duration_ms=1.0,
        error=None,
    )
    row = rec.record(gr).to_dict()

    # Recompute purely from the row's own logged signal + weight/threshold fields.
    i2 = core.compute_composite(
        row["usc"], row["fh"], row["rc"], (row["w1"], row["w2"], row["w3"])
    )
    band2 = core.band_level(i2, (row["tau0"], row["tau1"], row["tau2"]))
    floor2 = core.risk_floor(row["rc"])
    level2 = core.map_to_level(i2, row["rc"], (row["tau0"], row["tau1"], row["tau2"]))
    assert i2 == pytest.approx(row["i_t"])
    assert band2 == row["band_level"]
    assert floor2 == row["risk_floor"]
    assert level2 == row["final_level"]


# item: each condition maps Decision->level per section 7 ----------------------


def test_conditions_map_decision_to_level():
    crit = _score(0.0, 0.0, 1.0)  # final_level 3
    assert full_autonomy_policy(crit) == 0  # no floor
    assert static_hitl_policy(_score(0.0, 0.0, 0.0)) == 2
    assert cadis_policy(crit) == 3  # full policy = final_level
    rnd = RandomPolicy(RandomBudget(her=0.0, level_probs={}), seed=1)
    assert rnd(crit) == 3  # random keeps CRITICAL floor


# item: OpenRouter is the only LLM path; no local-inference path reachable -----


@pytest.mark.parametrize("bad_model", ["gpt-4o", "ollama/llama3", "vllm/x", "claude-3"])
def test_openrouter_only_guard_rejects_non_openrouter(bad_model):
    with pytest.raises(ValueError):
        SelfConsistencySampler(bad_model)


def test_openrouter_model_is_accepted():
    s = SelfConsistencySampler("openrouter/deepseek/deepseek-v4-flash")
    assert s.model.startswith("openrouter/")
    assert s.temperature == 0.7 and s.n_samples == 5
