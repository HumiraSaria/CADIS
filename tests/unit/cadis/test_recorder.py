"""Unit tests for the per-step recorder (newplan.md section 14)."""

import json

import pytest

from pentestagent.cadis.engine import ScoreResult
from pentestagent.cadis.gate import GateRecord
from pentestagent.cadis.recorder import SECTION_14_FIELDS, RunRecorder

_W = (0.35, 0.30, 0.35)
_T = (0.25, 0.50, 0.75)


def _gr(
    action="whois x",
    level=None,
    final_level=0,
    executed=True,
    outcome="success",
    duration_ms=12.0,
    decision=None,
    error=None,
    risk_floor=0,
    rc=0.0,
):
    # applied level (GateRecord.level) defaults to CADIS's computed final_level
    # (applied == computed for CADIS); pass `level` explicitly to make them differ.
    applied = final_level if level is None else level
    score = ScoreResult(
        proposed_action=action,
        usc=0.1,
        fh=0.0,
        rc=rc,
        intervention_score=0.05,
        band_level=final_level,
        risk_floor=risk_floor,
        final_level=final_level,
        risk_tier="low",
        risk_matched=True,
        n_samples=5,
    )
    return GateRecord(
        action=action,
        score=score,
        level=applied,
        executed=executed,
        decision=decision,
        operator_note=None,
        outcome=outcome,
        duration_ms=duration_ms,
        error=error,
    )


def test_final_level_is_applied_not_cadis_computed(tmp_path):
    # HER-bug regression: full_autonomy-style cell where CADIS would compute L2 but the
    # condition applied L0 -> row.final_level must be the APPLIED 0, cadis_level the 2.
    rec = RunRecorder(tmp_path, "full_autonomy", "dvwa-sqli", 1, 0, _W, _T)
    row = rec.record(_gr(level=0, final_level=2))
    assert row.final_level == 0  # applied (what full_autonomy did)
    assert row.cadis_level == 2  # what CADIS would have done
    assert rec.human_effort_ratio() == 0.0  # HER reflects the applied level


def test_empty_steps_file_created_for_zero_action_run(tmp_path):
    # 0-action run must still be discoverable (the Random n=8 fix): steps.jsonl exists.
    rec = RunRecorder(tmp_path, "random", "dvwa-sqli", 2, 1002, _W, _T)
    assert rec.steps_path.is_file()
    assert rec.steps_path.read_text(encoding="utf-8") == ""
    rec.close(completed=False)


def test_records_all_section14_fields(tmp_path):
    rec = RunRecorder(
        tmp_path, "cadis", "dvwa-sqli", 1, seed=7, weights=_W, thresholds=_T
    )
    row = rec.record(_gr())
    d = row.to_dict()
    for field in SECTION_14_FIELDS:
        assert field in d, f"missing section-14 field {field}"

    line = (
        (tmp_path / "raw_runs" / "cadis" / "dvwa-sqli" / "rep_1" / "steps.jsonl")
        .read_text(encoding="utf-8")
        .splitlines()
    )
    assert len(line) == 1
    loaded = json.loads(line[0])
    for field in SECTION_14_FIELDS:
        assert field in loaded


def test_weights_and_thresholds_logged_per_row(tmp_path):
    rec = RunRecorder(tmp_path, "cadis", "t", 1, 0, _W, _T)
    row = rec.record(_gr())
    assert (row.w1, row.w2, row.w3) == _W
    assert (row.tau0, row.tau1, row.tau2) == _T


def test_meta_written(tmp_path):
    rec = RunRecorder(tmp_path, "cadis", "t", 2, 9, _W, _T)
    meta = json.loads((rec.dir / "meta.json").read_text(encoding="utf-8"))
    assert meta["condition"] == "cadis" and meta["seed"] == 9
    assert meta["weights"] == list(_W)


def test_levels_her_and_summary(tmp_path):
    rec = RunRecorder(tmp_path, "cadis", "t", 1, 0, _W, _T)
    rec.record(_gr(final_level=0))
    rec.record(_gr(final_level=2, decision="approve"))
    rec.record(_gr(final_level=3, executed=False, outcome=None, decision="handoff"))
    assert rec.levels() == [0, 2, 3]
    assert rec.human_effort_ratio() == pytest.approx(2 / 3)
    summary = rec.close()
    assert summary["steps"] == 3 and summary["her"] == pytest.approx(2 / 3)
    on_disk = json.loads((rec.dir / "summary.json").read_text(encoding="utf-8"))
    assert on_disk["levels"] == [0, 2, 3]


def test_step_ids_increment_and_are_namespaced(tmp_path):
    rec = RunRecorder(tmp_path, "random", "juice-shop", 3, 1, _W, _T)
    r1 = rec.record(_gr())
    r2 = rec.record(_gr())
    assert r1.step_id == "random:juice-shop:3:1"
    assert r2.step_id == "random:juice-shop:3:2"


async def test_gate_writes_rows_via_recorder(tmp_path):
    from pentestagent.agents.base_agent import ToolCall, ToolResult
    from pentestagent.cadis.config import load_config
    from pentestagent.cadis.engine import CadisEngine
    from pentestagent.cadis.gate import CadisGate
    from pentestagent.cadis.operator import ScriptedOperator
    from pentestagent.cadis.signals.risk import RiskClassifier

    cfg = load_config()
    clf = RiskClassifier.from_yaml(cfg.taxonomy_path, cfg.unmatched_default)
    rec = RunRecorder.from_config(tmp_path, "cadis", "dvwa-sqli", 1, 0, cfg)

    class FakeAgent:
        tools = []

        def get_system_prompt(self, mode="agent"):
            return "sys"

        def _format_messages_for_llm(self):
            return [{"role": "user", "content": "go"}]

        async def _execute_tools(self, calls):
            return [
                ToolResult(
                    tool_call_id=getattr(c, "id", "i"),
                    tool_name="terminal",
                    result="ok",
                    success=True,
                )
                for c in calls
            ]

    gate = CadisGate(
        CadisEngine(cfg, clf), ScriptedOperator(), policy=lambda s: 0, recorder=rec
    )
    await gate(
        [ToolCall(id="c1", name="terminal", arguments={"command": "whois x"})],
        FakeAgent(),
    )
    assert len(rec.rows) == 1
    assert rec.rows[0].final_level == 0 and rec.rows[0].outcome_class == "success"
    assert rec.rows[0].duration_ms >= 0.0
