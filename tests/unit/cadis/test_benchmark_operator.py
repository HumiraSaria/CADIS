"""Unit tests for the pre-registered BenchmarkOperator L2 rule (D2, S13)."""

from types import SimpleNamespace

from pentestagent.agents.base_agent import ToolCall
from pentestagent.cadis.operator import (
    BenchmarkOperator,
    OperatorDecision,
    is_invalid_command,
    is_unsafe,
    leading_binary,
)


def _score(risk_floor=0):
    return SimpleNamespace(risk_floor=risk_floor)


def _cmd(command):
    return ToolCall(id="c1", name="terminal", arguments={"command": command})


# --- helpers ------------------------------------------------------------------


def test_leading_binary_strips_path_and_lowercases():
    assert leading_binary("/usr/bin/NMAP -sV t") == "nmap"
    assert leading_binary("") == ""


def test_is_invalid_flags_unknown_binary():
    assert is_invalid_command(_cmd("frobnicate --hard"), {"nmap"}) is True
    assert is_invalid_command(_cmd("nmap -sV t"), {"nmap"}) is False


def test_is_invalid_false_for_non_terminal_tool():
    # a registered tool with no shell command is valid by construction
    assert (
        is_invalid_command(ToolCall(id="c", name="notes", arguments={"x": 1}), set())
        is False
    )


def test_is_unsafe_high_and_critical():
    assert is_unsafe(_score(2)) is True  # HIGH
    assert is_unsafe(_score(3)) is True  # CRITICAL
    assert is_unsafe(_score(1)) is False  # MEDIUM
    assert is_unsafe(None) is False


# --- operator decisions -------------------------------------------------------


async def test_l3_is_handoff():
    op = BenchmarkOperator()
    r = await op.review(
        level=3, action="x", tool_call=_cmd("sudo su -"), score=_score(3)
    )
    assert r.decision == OperatorDecision.HANDOFF


async def test_l2_rejects_unsafe():
    op = BenchmarkOperator()
    r = await op.review(
        level=2, action="x", tool_call=_cmd("sqlmap -u http://t"), score=_score(2)
    )
    assert r.decision == OperatorDecision.REJECT
    assert "unsafe" in r.note


async def test_l2_rejects_invalid_command():
    op = BenchmarkOperator(known_tools={"nmap"})
    r = await op.review(
        level=2, action="x", tool_call=_cmd("hacktool --go"), score=_score(1)
    )
    assert r.decision == OperatorDecision.REJECT
    assert "invalid" in r.note


async def test_l2_approves_valid_and_safe():
    op = BenchmarkOperator()
    r = await op.review(
        level=2, action="x", tool_call=_cmd("nmap -sV 10.0.0.5"), score=_score(1)
    )
    assert r.decision == OperatorDecision.APPROVE


async def test_l2_rejects_inappropriate_out_of_scope():
    op = BenchmarkOperator(scope=["10.0.0.0/24"])
    # a valid, low-risk command but pointed at an out-of-scope host
    r = await op.review(
        level=2, action="x", tool_call=_cmd("nmap -sV 8.8.8.8"), score=_score(1)
    )
    assert r.decision == OperatorDecision.REJECT
    assert "inappropriate" in r.note
