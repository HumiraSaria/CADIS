"""Unit tests for the analysis pipeline (S11 gate: reproduce metrics from sample runs)."""

import json

import pytest

from benchmark.run.analyse import (
    DEFAULT_THRESHOLD_GRID,
    DEFAULT_WEIGHT_GRID,
    ablate,
    analyse,
    by_condition,
    calibration,
    compare,
    has_cascade,
    holm_correction,
    human_effort_ratio,
    time_to_completion_ms,
)


def _step(
    final_level=0, outcome="success", i_t=0.1, usc=0.0, fh=0.0, rc=0.0, duration_ms=5.0
):
    return {
        "final_level": final_level,
        "outcome_class": outcome,
        "i_t": i_t,
        "usc": usc,
        "fh": fh,
        "rc": rc,
        "duration_ms": duration_ms,
    }


def _write_run(root, condition, target, rep, steps, completed=None):
    d = root / "raw_runs" / condition / target / f"rep_{rep}"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "steps.jsonl").open("w", encoding="utf-8") as f:
        for s in steps:
            f.write(json.dumps(s) + "\n")
    summary = {"levels": [s.get("final_level", 0) for s in steps]}
    if completed is not None:
        summary["completed"] = completed
    (d / "summary.json").write_text(json.dumps(summary), encoding="utf-8")


# --- primitives ---------------------------------------------------------------


def test_human_effort_ratio():
    steps = [
        _step(final_level=0),
        _step(final_level=1),
        _step(final_level=2),
        _step(final_level=0),
    ]
    assert human_effort_ratio(steps) == pytest.approx(0.5)


def test_has_cascade_true_on_three_consecutive_failures():
    assert has_cascade(["failure", "failure", "failure"], n=3) is True


def test_has_cascade_false_when_broken_by_success():
    assert (
        has_cascade(["failure", "failure", "success", "failure", "failure"], n=3)
        is False
    )


def test_has_cascade_ignores_non_failure_outcomes():
    assert has_cascade(["timeout", "partial", "success"], n=3) is False


def test_time_to_completion_sums_durations():
    assert time_to_completion_ms(
        [_step(duration_ms=5), _step(duration_ms=7)]
    ) == pytest.approx(12.0)


# --- calibration --------------------------------------------------------------


def test_calibration_known_ece():
    # scores 0.1 (obs 0) x2 and 0.9 (obs 1) x2 -> ECE = 0.5*0.1 + 0.5*0.1 = 0.1
    scores = [0.1, 0.1, 0.9, 0.9]
    failures = [0, 0, 1, 1]
    ece, bins = calibration(scores, failures, n_bins=10)
    assert ece == pytest.approx(0.1)
    assert sum(b.count for b in bins) == 4


# --- ablation -----------------------------------------------------------------


def test_ablate_grid_size_and_default_row():
    steps = [_step(usc=0.4, fh=0.25, rc=0.66, outcome="failure")]
    rows = ablate(steps)
    assert len(rows) == len(DEFAULT_WEIGHT_GRID) * len(DEFAULT_THRESHOLD_GRID)
    # default (0.35/0.30/0.35, 0.25/0.5/0.75): I=0.446 -> level 2 -> HER 1.0
    default = next(
        r
        for r in rows
        if (r["w1"], r["w2"], r["w3"]) == (0.35, 0.30, 0.35)
        and (r["tau0"], r["tau1"], r["tau2"]) == (0.25, 0.50, 0.75)
    )
    assert default["her"] == pytest.approx(1.0)
    assert default["mean_level"] == pytest.approx(2.0)


# --- aggregation --------------------------------------------------------------


def test_by_condition_hcr_her_tcr():
    per_run = [
        {
            "condition": "cadis",
            "target": "t1",
            "rep": 1,
            "her": 0.5,
            "cascade": 0,
            "completed": 1,
            "ttc_ms": 10,
            "n_steps": 4,
        },
        {
            "condition": "cadis",
            "target": "t2",
            "rep": 1,
            "her": 0.5,
            "cascade": 1,
            "completed": 0,
            "ttc_ms": 20,
            "n_steps": 4,
        },
    ]
    summ = by_condition(per_run)
    assert summ["cadis"]["hcr"] == pytest.approx(0.5)
    assert summ["cadis"]["her"] == pytest.approx(0.5)
    assert summ["cadis"]["tcr"] == pytest.approx(0.5)


# --- statistics ---------------------------------------------------------------


def test_compare_paired_mean_diff():
    per_run = []
    for t in ("t1", "t2", "t3"):
        per_run.append({"condition": "cadis", "target": t, "cascade": 0})
        per_run.append({"condition": "full_autonomy", "target": t, "cascade": 1})
    res = compare(per_run, "cascade", "cadis", "full_autonomy")
    assert res["n_targets"] == 3
    assert res["mean_diff"] == pytest.approx(-1.0)  # CADIS fewer cascades


def test_holm_correction():
    assert holm_correction([0.01, 0.04, 0.03]) == pytest.approx([0.03, 0.06, 0.06])


def test_holm_passes_through_none():
    out = holm_correction([None, 0.01])
    assert out[0] is None and out[1] == pytest.approx(0.01)


# --- end-to-end ---------------------------------------------------------------


def test_analyse_end_to_end(tmp_path):
    # one target, all four conditions; cadis clean, full_autonomy cascades
    cadis_steps = [_step(final_level=2, outcome="success", i_t=0.44, rc=0.66)]
    fa_steps = [
        _step(outcome="failure", i_t=0.1) for _ in range(3)
    ]  # a 3-failure cascade
    _write_run(tmp_path, "cadis", "dvwa-sqli", 1, cadis_steps, completed=True)
    _write_run(tmp_path, "full_autonomy", "dvwa-sqli", 1, fa_steps, completed=False)
    _write_run(tmp_path, "static_hitl", "dvwa-sqli", 1, cadis_steps, completed=True)
    _write_run(tmp_path, "random", "dvwa-sqli", 1, fa_steps, completed=False)

    summary = analyse(tmp_path / "raw_runs", tmp_path)

    assert summary["n_runs"] == 4
    assert summary["by_condition"]["cadis"]["hcr"] == pytest.approx(0.0)
    assert summary["by_condition"]["full_autonomy"]["hcr"] == pytest.approx(1.0)
    # artifacts written
    assert (tmp_path / "results" / "metrics_per_run.csv").is_file()
    assert (tmp_path / "results" / "metrics_by_condition_summary.csv").is_file()
    assert (tmp_path / "results" / "statistical_comparisons.json").is_file()
    assert (tmp_path / "results" / "calibration" / "reliability.json").is_file()
    assert (tmp_path / "results" / "calibration" / "reliability.svg").is_file()
    assert (tmp_path / "ablation" / "weight_threshold_grid.csv").is_file()
