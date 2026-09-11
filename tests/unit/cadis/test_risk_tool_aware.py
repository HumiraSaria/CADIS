"""Tool-aware RC classification (deviation D3, taxonomy v0.1.1).

Framework/meta tools are LOW by identity; the fail-safe HIGH applies only to unrecognised
shell commands (the `terminal` tool).
"""

import pytest

from pentestagent.cadis.config import _DEFAULT_TAXONOMY
from pentestagent.cadis.signals.risk import RiskClassifier


@pytest.fixture()
def clf() -> RiskClassifier:
    return RiskClassifier.from_yaml(_DEFAULT_TAXONOMY)


@pytest.mark.parametrize(
    "tool", ["finish", "notes", "browser", "web_search", "create_plan"]
)
def test_framework_tools_are_low(clf, tool):
    r = clf.classify_for_tool(tool, None, f"{tool} {{}}")
    assert r.score == 0.0 and r.tier == "low" and r.matched


def test_notes_with_scary_content_stays_low(clf):
    # a notes action whose text merely mentions "sudo" must NOT escalate
    r = clf.classify_for_tool(
        "notes", None, 'notes {"content": "found a sudo backdoor on the host"}'
    )
    assert r.score == 0.0


def test_terminal_classifies_the_shell_command(clf):
    assert (
        clf.classify_for_tool("terminal", "nmap -sV t", "terminal {...}").score == 0.33
    )
    assert clf.classify_for_tool("terminal", "sudo su -", "terminal {...}").score == 1.0
    assert clf.classify_for_tool("terminal", "whois x", "terminal {...}").score == 0.0


def test_terminal_unknown_binary_failsafe_high(clf):
    r = clf.classify_for_tool("terminal", "frobnicate --go", "terminal {...}")
    assert r.score == 0.66 and r.matched is False  # fail-safe HIGH preserved
