"""Unit tests for the BaseAgent action-gate seam (S6).

Verifies the gate hook is default-off (production unchanged) and, when set, fully owns
the tool-execution step in _run_loop via _dispatch_tool_calls.
"""

from unittest.mock import AsyncMock, MagicMock

from pentestagent.agents.base_agent import BaseAgent, ToolResult


class _MinAgent(BaseAgent):
    def get_system_prompt(self, mode: str = "agent") -> str:
        return "sys"


def _runtime():
    rt = MagicMock()
    rt.plan = MagicMock()
    rt.plan.clear = MagicMock()
    rt.plan.is_complete = MagicMock(return_value=True)
    rt.plan.has_failure = MagicMock(return_value=False)
    return rt


def test_action_gate_defaults_none():
    agent = _MinAgent(llm=MagicMock(), tools=[], runtime=_runtime())
    assert agent.action_gate is None


async def test_dispatch_executes_directly_when_no_gate():
    agent = _MinAgent(llm=MagicMock(), tools=[], runtime=_runtime())
    agent._execute_tools = AsyncMock(
        return_value=[
            ToolResult(tool_call_id="x", tool_name="t", result="direct", success=True)
        ]
    )
    results = await agent._dispatch_tool_calls(["rawcall"])
    assert results[0].result == "direct"
    agent._execute_tools.assert_awaited_once()


async def test_dispatch_uses_gate_when_set():
    agent = _MinAgent(llm=MagicMock(), tools=[], runtime=_runtime())
    seen = {}

    async def gate(raw_calls, ag):
        seen["raw"] = raw_calls
        seen["agent"] = ag
        return [
            ToolResult(tool_call_id="x", tool_name="t", result="gated", success=True)
        ]

    agent.action_gate = gate
    # _execute_tools must NOT be called when a gate is installed
    agent._execute_tools = AsyncMock(side_effect=AssertionError("should not run"))
    results = await agent._dispatch_tool_calls(["rawcall"])
    assert results[0].result == "gated"
    assert seen["raw"] == ["rawcall"] and seen["agent"] is agent


def test_action_gate_can_be_passed_via_constructor():
    async def gate(raw_calls, ag):
        return []

    agent = _MinAgent(llm=MagicMock(), tools=[], runtime=_runtime(), action_gate=gate)
    assert agent.action_gate is gate
