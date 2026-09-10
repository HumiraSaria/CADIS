"""Unit tests for the CADIS engine scaffold (orchestration; wiring at S4)."""

import pytest

from pentestagent.cadis.config import load_config
from pentestagent.cadis.engine import CadisEngine, ScoreResult
from pentestagent.cadis.signals.failure_history import FAILURE, SUCCESS
from pentestagent.cadis.signals.risk import RiskClassifier


@pytest.fixture()
def engine() -> CadisEngine:
    cfg = load_config()
    clf = RiskClassifier.from_yaml(cfg.taxonomy_path, cfg.unmatched_default)
    return CadisEngine(cfg, clf)


def test_critical_action_forces_level_3(engine):
    # CRITICAL command -> hard floor L3 regardless of USC/FH.
    res = engine.score(
        "sudo su -", outcome_history=[SUCCESS] * 10, sampled_commands=["sudo su -"] * 5
    )
    assert res.rc == 1.0
    assert res.risk_floor == 3
    assert res.final_level == 3


def test_low_risk_consistent_clean_history_is_level_0(engine):
    # LOW command, identical samples (USC=0), empty history (FH=0) -> I~0 -> L0.
    res = engine.score(
        "whois example.com",
        outcome_history=[],
        sampled_commands=["whois example.com"] * 5,
    )
    assert res.usc == pytest.approx(0.0)
    assert res.fh == pytest.approx(0.0)
    assert res.rc == 0.0
    assert res.intervention_score == pytest.approx(0.0)
    assert res.final_level == 0
    assert res.n_samples == 5


def test_failure_history_raises_score(engine):
    # A HIGH command with a failing recent history routes to a blocking level.
    res = engine.score(
        "sqlmap -u http://t/x?id=1",
        outcome_history=[FAILURE] * 10,
        sampled_commands=["sqlmap -u http://t/x?id=1"] * 5,
    )
    assert res.rc == 0.66
    assert res.fh == pytest.approx(1.0)
    assert res.final_level >= 2  # HIGH floor plus failing history


def test_result_is_fully_populated(engine):
    res = engine.score("nmap -sV t", outcome_history=[SUCCESS], sampled_commands=None)
    assert isinstance(res, ScoreResult)
    # sampler not provided -> USC defaults to 0.0, n_samples logged as 0
    assert res.usc == 0.0 and res.n_samples == 0
    assert res.risk_tier == "medium" and res.rc == 0.33
