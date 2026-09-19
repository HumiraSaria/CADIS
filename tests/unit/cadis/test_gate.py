"""Unit tests for the CADIS action gate: L0-L3 routing at the seam.

Forced policies demonstrate each level; the default CADIS policy is checked against the
real engine (CRITICAL -> L3). A fake agent stands in for BaseAgent's execution path.
"""

import pytest

from pentestagent.agents.base_agent import ToolCall, ToolResult
from pentestagent.cadis.config import load_config
from pentestagent.cadis.engine import CadisEngine
from pentestagent.cadis.gate import CadisGate, cadis_policy
from pentestagent.cadis.operator import (
    Operator,
    OperatorDecision,
    OperatorResponse,
    ScriptedOperator,
)
from pentestagent.cadis.sampler import SampleBatch
from pentestagent.cadis.signals.risk import RiskClassifier


class FakeAgent:
    """Minimal stand-in exposing the surface CadisGate touches."""

    def __init__(self):
        self.tools = []
        self.executed = []

    def get_system_prompt(self, mode="agent"):
        return "sys"

    def _format_messages_for_llm(self):
        return [{"role": "user", "content": "go"}]

    async def _execute_tools(self, calls):
        self.executed.extend(calls)
        return [
            ToolResult(
                tool_call_id=getattr(c, "id", "id0"),
                tool_name=getattr(c, "name", None) or "terminal",
                result="ran ok",
                success=True,
            )
            for c in calls
        ]


class EditOperator(Operator):
    async def review(self, *, level, action, tool_call, score=None):
        return OperatorResponse(
            OperatorDecision.EDIT, edited_arguments={"command": "whoami"}
        )


class StubSampler:
    def __init__(self, commands):
        self.commands = commands
        self.called = 0

    async def sample(self, messages, tools=None):
        self.called += 1
        return SampleBatch(
            commands=list(self.commands), calls=[], model="m", temperature=0.7
        )


def _engine() -> CadisEngine:
    cfg = load_config()
    clf = RiskClassifier.from_yaml(cfg.taxonomy_path, cfg.unmatched_default)
    return CadisEngine(cfg, clf)


def _call(command="whois example.com"):
    return ToolCall(id="c1", name="terminal", arguments={"command": command})


# --- forced-level routing -----------------------------------------------------


async def test_l0_executes():
    agent = FakeAgent()
    gate = CadisGate(_engine(), ScriptedOperator(), policy=lambda s: 0)
    results = await gate([_call()], agent)
    assert results[0].success and results[0].result == "ran ok"
    assert len(agent.executed) == 1
    assert gate.records[0].level == 0 and gate.records[0].executed
    assert gate.records[0].outcome == "success"


async def test_l1_notifies_and_executes():
    agent = FakeAgent()
    notes = []
    gate = CadisGate(
        _engine(),
        ScriptedOperator(),
        policy=lambda s: 1,
        notify_fn=lambda level, msg: notes.append((level, msg)),
    )
    results = await gate([_call()], agent)
    assert results[0].success and len(agent.executed) == 1
    assert notes and "L1" in notes[0][1]


async def test_l2_approve_executes():
    agent = FakeAgent()
    gate = CadisGate(
        _engine(), ScriptedOperator(should_approve=lambda a: True), policy=lambda s: 2
    )
    results = await gate([_call()], agent)
    assert results[0].success and len(agent.executed) == 1
    assert gate.records[0].decision == "approve"


async def test_l2_reject_blocks_execution():
    agent = FakeAgent()
    gate = CadisGate(
        _engine(), ScriptedOperator(should_approve=lambda a: False), policy=lambda s: 2
    )
    results = await gate([_call()], agent)
    assert not results[0].success
    assert "rejected by operator" in results[0].error
    assert len(agent.executed) == 0
    assert gate.records[0].executed is False and gate.records[0].decision == "reject"


async def test_l2_edit_executes_edited_arguments():
    agent = FakeAgent()
    gate = CadisGate(_engine(), EditOperator(), policy=lambda s: 2)
    results = await gate([_call(command="rm -rf /")], agent)
    assert results[0].success and len(agent.executed) == 1
    executed_call = agent.executed[0]
    assert getattr(executed_call, "arguments", {}).get("command") == "whoami"
    assert gate.records[0].decision == "edit"


async def test_l3_delegate_blocks_execution():
    agent = FakeAgent()
    gate = CadisGate(_engine(), ScriptedOperator(), policy=lambda s: 3)
    results = await gate([_call(command="sudo su -")], agent)
    assert not results[0].success
    assert "delegated to human" in results[0].error
    assert len(agent.executed) == 0
    assert gate.records[0].level == 3 and gate.records[0].decision == "handoff"


# --- default CADIS policy against the real engine -----------------------------


async def test_default_policy_routes_critical_to_l3():
    agent = FakeAgent()
    gate = CadisGate(_engine(), ScriptedOperator())  # default cadis_policy
    results = await gate([_call(command="sudo su -")], agent)
    rec = gate.records[0]
    assert rec.score.rc == 1.0 and rec.level == 3
    assert not results[0].success  # delegated, not executed
    assert len(agent.executed) == 0


async def test_default_policy_routes_low_risk_to_l0():
    agent = FakeAgent()
    gate = CadisGate(_engine(), ScriptedOperator())
    results = await gate([_call(command="whois example.com")], agent)
    rec = gate.records[0]
    assert rec.score.rc == 0.0 and rec.level == 0
    assert results[0].success and len(agent.executed) == 1


# --- FH history + sampler wiring ----------------------------------------------


async def test_history_updates_only_on_executed():
    agent = FakeAgent()
    executed_gate = CadisGate(_engine(), ScriptedOperator(), policy=lambda s: 0)
    await executed_gate([_call()], agent)
    assert executed_gate._history == ["success"]

    blocked_gate = CadisGate(_engine(), ScriptedOperator(), policy=lambda s: 3)
    await blocked_gate([_call()], agent)
    assert blocked_gate._history == []


async def test_gate_uses_sampler_for_usc():
    agent = FakeAgent()
    stub = StubSampler(["whois x", "whois x", "whois x"])
    gate = CadisGate(_engine(), ScriptedOperator(), policy=cadis_policy, sampler=stub)
    await gate([_call(command="whois x")], agent)
    assert stub.called == 1
    rec = gate.records[0]
    assert rec.score.n_samples == 3
    assert rec.score.usc == pytest.approx(0.0)


# --- D4: terminal outcome parsing in _classify --------------------------------


def _terminal_result(exit_code, stdout="", stderr=""):
    parts = ["Command: x", f"Exit Code: {exit_code}"]
    if stdout:
        parts.append(f"\n--- stdout ---\n{stdout}")
    if stderr:
        parts.append(f"\n--- stderr ---\n{stderr}")
    return ToolResult(
        tool_call_id="c1", tool_name="terminal", result="\n".join(parts), success=True
    )


def test_classify_parses_terminal_failure_and_success():
    assert (
        CadisGate._classify(
            _terminal_result(127, stderr="sh: nmapp: command not found")
        )
        == "failure"
    )
    assert (
        CadisGate._classify(_terminal_result(0, stdout="22/tcp open ssh")) == "success"
    )
    assert (
        CadisGate._classify(_terminal_result(7, stderr="curl: (7) Connection refused"))
        == "partial"
    )


def test_classify_falls_back_when_no_exit_line():
    # non-terminal, or terminal without a parseable "Exit Code:" line -> generic path
    r = ToolResult(
        tool_call_id="c1", tool_name="terminal", result="ran ok", success=True
    )
    assert CadisGate._classify(r) == "success"
    r2 = ToolResult(tool_call_id="c2", tool_name="notes", result="saved", success=True)
    assert CadisGate._classify(r2) == "success"
