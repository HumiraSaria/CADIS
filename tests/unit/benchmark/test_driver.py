"""Unit tests for driver helpers (no Docker / no live LLM)."""

import json

import pytest

from benchmark.run.driver import build_gate, load_cadis_budget

_MODEL = "openrouter/deepseek/deepseek-v4-flash"


def _write_cadis_summary(out_root, target, rep, levels):
    d = out_root / "raw_runs" / "cadis" / target / f"rep_{rep}"
    d.mkdir(parents=True, exist_ok=True)
    (d / "summary.json").write_text(json.dumps({"levels": levels}), encoding="utf-8")


def test_load_cadis_budget_pools_levels(tmp_path):
    _write_cadis_summary(tmp_path, "dvwa-sqli", 1, [0, 0, 2])
    _write_cadis_summary(tmp_path, "dvwa-sqli", 2, [3, 1])
    budget = load_cadis_budget(tmp_path, "dvwa-sqli")
    # pooled levels: [0,0,2,3,1] -> her 3/5
    assert budget.her == pytest.approx(3 / 5)


def test_load_cadis_budget_empty_when_no_cadis(tmp_path):
    budget = load_cadis_budget(tmp_path, "juice-shop")
    assert budget.her == 0.0


def test_build_gate_cadis_condition(tmp_path):
    gate, recorder = build_gate(
        "cadis", "dvwa-sqli", model=_MODEL, out_root=tmp_path, rep=1, seed=1001
    )
    assert recorder.condition == "cadis" and recorder.target == "dvwa-sqli"
    assert gate.sampler is not None and gate.recorder is recorder
    # meta.json was written on recorder construction
    assert (recorder.dir / "meta.json").is_file()


def test_build_gate_random_uses_cadis_budget(tmp_path):
    _write_cadis_summary(tmp_path, "dvwa-sqli", 1, [0, 2, 2, 0])
    gate, recorder = build_gate(
        "random", "dvwa-sqli", model=_MODEL, out_root=tmp_path, rep=1, seed=1001
    )
    assert recorder.condition == "random"
    assert callable(gate.policy)  # RandomPolicy instance
