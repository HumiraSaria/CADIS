"""Unit tests for Signal 3 -- Risk Classification / RC (CadisClaude.md section 6.3)."""

import pytest

from pentestagent.cadis.config import _DEFAULT_TAXONOMY
from pentestagent.cadis.signals.risk import (
    RiskClassifier,
    classify_risk,
    compile_taxonomy,
)


@pytest.fixture()
def classifier() -> RiskClassifier:
    return RiskClassifier.from_yaml(_DEFAULT_TAXONOMY)


# --- tiers via the real frozen taxonomy ---------------------------------------


def test_low_read_only_enumeration(classifier):
    r = classifier.classify("whois example.com")
    assert (r.score, r.tier, r.matched) == (0.0, "low", True)


def test_medium_active_scan(classifier):
    r = classifier.classify("nmap -sV -p- 10.0.0.5")
    assert (r.score, r.tier) == (0.33, "medium")


def test_high_exploitation(classifier):
    r = classifier.classify("sqlmap -u http://t/vuln?id=1 --dbs")
    assert (r.score, r.tier) == (0.66, "high")


def test_critical_privilege_escalation(classifier):
    assert classifier.classify("sudo -l").score == 1.0
    assert classifier.classify("rm -rf /var").score == 1.0


# --- fail-safe: unmatched -> HIGH, logged as a gap (section 6.3, C4) -----------


def test_unmatched_fails_safe_to_high_and_logs_gap(classifier):
    r = classifier.classify("qwerty zxcvbn asdf")
    assert (r.score, r.tier, r.matched) == (0.66, "high", False)
    assert "qwerty zxcvbn asdf" in classifier.gaps


# --- highest-tier precedence (consequence caps trust) -------------------------


def test_highest_tier_wins_when_multiple_match(classifier):
    # matches medium (nmap) AND critical (sudo) -> critical must win
    r = classifier.classify("sudo nmap -sV target")
    assert (r.score, r.tier) == (1.0, "critical")


# --- pure classify_risk over a hand-built taxonomy ----------------------------


def test_pure_classify_risk_is_side_effect_free():
    taxonomy = compile_taxonomy(
        {"low": [r"\bls\b"], "medium": [], "high": [], "critical": [r"\bsudo\b"]}
    )
    assert classify_risk("ls -la", taxonomy).score == 0.0
    assert classify_risk("sudo ls", taxonomy).score == 1.0
    miss = classify_risk("nmap -sV", taxonomy)
    assert miss.matched is False and miss.score == 0.66  # fail-safe HIGH default
