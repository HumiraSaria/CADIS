"""Unit tests for the CADIS operator protocol (L2/L3 handling)."""

from pentestagent.cadis.operator import (
    InteractiveOperator,
    OperatorDecision,
    OperatorResponse,
    ScriptedOperator,
)

# --- ScriptedOperator (benchmark, deterministic) ------------------------------


async def test_scripted_l2_approves_by_default():
    op = ScriptedOperator()
    r = await op.review(level=2, action="nmap -sV t", tool_call=None)
    assert r.decision == OperatorDecision.APPROVE


async def test_scripted_l2_rejects_via_predicate():
    op = ScriptedOperator(should_approve=lambda a: "sqlmap" not in a)
    r = await op.review(level=2, action="sqlmap -u http://x", tool_call=None)
    assert r.decision == OperatorDecision.REJECT


async def test_scripted_l3_handoff():
    op = ScriptedOperator()
    r = await op.review(level=3, action="sudo su -", tool_call=None)
    assert r.decision == OperatorDecision.HANDOFF


# --- InteractiveOperator (TUI; fail-safe without a human) ---------------------


async def test_interactive_failsafe_reject_at_l2():
    op = InteractiveOperator()
    r = await op.review(level=2, action="x", tool_call=None)
    assert r.decision == OperatorDecision.REJECT


async def test_interactive_failsafe_handoff_at_l3():
    op = InteractiveOperator()
    r = await op.review(level=3, action="x", tool_call=None)
    assert r.decision == OperatorDecision.HANDOFF


async def test_interactive_uses_human_decision_fn():
    async def human(*, level, action, tool_call):
        return OperatorResponse(
            OperatorDecision.EDIT, edited_arguments={"command": "safe"}
        )

    op = InteractiveOperator(decision_fn=human)
    r = await op.review(level=2, action="x", tool_call=None)
    assert r.decision == OperatorDecision.EDIT
    assert r.edited_arguments == {"command": "safe"}
