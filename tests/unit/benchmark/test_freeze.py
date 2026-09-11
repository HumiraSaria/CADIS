"""Unit tests for the freeze + pre-registration artifacts (S13)."""

import yaml

from benchmark.run.freeze import (
    frozen_environment,
    pre_benchmark_checklist,
    preregistration,
    write_freeze,
)

_MODEL = "openrouter/deepseek/deepseek-v4-flash"


def test_frozen_environment_pins_everything():
    env = frozen_environment(_MODEL, reps=3)
    assert env["llm_access"]["model"] == _MODEL
    assert env["llm_access"]["no_local_inference"] is True
    assert env["cadis_config"]["weights"] == [0.35, 0.30, 0.35]
    assert env["cadis_config"]["n_samples"] == 5
    assert tuple(env["conditions"]) == (
        "full_autonomy",
        "static_hitl",
        "random",
        "cadis",
    )
    # all targets digest-pinned
    assert all("@sha256:" in t["image"] for t in env["targets"]["manifest"])
    assert len(env["targets"]["manifest"]) == 3
    assert len(env["config_hash"]) == 64  # sha256 hex


def test_preregistration_has_primary_endpoint_and_rules():
    pre = preregistration(reps=3)
    assert "H3" in pre["primary_endpoint"]
    assert pre["cascade_definition"]["n"] == 3
    op = pre["operator_rule_L2"]
    assert "invalid" in op and "unsafe" in op and "inappropriate" in op
    assert pre["statistical_plan"]["multiple_comparison_correction"].startswith("Holm")
    assert set(pre["primary_metrics"]) == {"TCR", "HCR", "HER"}


def test_pre_benchmark_checklist_all_pass():
    env = frozen_environment(_MODEL, reps=3)
    checklist = pre_benchmark_checklist(env)
    assert all(checklist.values()), [k for k, v in checklist.items() if not v]


def test_write_freeze_emits_artifacts(tmp_path):
    result = write_freeze(tmp_path, model=_MODEL, reps=3)
    assert result["checklist_all_pass"] is True
    assert (tmp_path / "frozen_environment.yaml").is_file()
    assert (tmp_path / "preregistration.yaml").is_file()
    assert (tmp_path / "pre_benchmark_checklist.yaml").is_file()
    # round-trips as valid YAML with the pinned model
    env = yaml.safe_load(
        (tmp_path / "frozen_environment.yaml").read_text(encoding="utf-8")
    )
    assert env["llm_access"]["model"] == _MODEL


def test_checklist_fails_on_bad_model():
    env = frozen_environment("gpt-4o", reps=3)  # not openrouter/*
    checklist = pre_benchmark_checklist(env)
    assert checklist["one pinned OpenRouter model"] is False
