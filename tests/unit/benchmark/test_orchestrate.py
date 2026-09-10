"""Unit tests for the benchmark orchestrator (matrix planning; the S10 gate)."""

import pytest

from benchmark.run.orchestrate import (
    RUN_ORDER,
    Cell,
    pending_cells,
    plan_matrix,
)

_CONDS = ("full_autonomy", "static_hitl", "random", "cadis")
_TARGETS = ("dvwa-sqli", "msf2-vsftpd", "juice-shop")


def test_matrix_size_is_conditions_x_targets_x_reps():
    cells = plan_matrix(_CONDS, _TARGETS, reps=3)
    assert len(cells) == 4 * 3 * 3


def test_cadis_first_per_target():
    cells = plan_matrix(_CONDS, _TARGETS, reps=2)
    for target in _TARGETS:
        seq = [c.condition for c in cells if c.target == target]
        # the target block starts with all CADIS reps, and random comes after cadis
        assert seq[0] == "cadis"
        assert seq.index("cadis") < seq.index("random")


def test_run_order_is_canonical():
    cells = plan_matrix(_CONDS, ("dvwa-sqli",), reps=1)
    assert [c.condition for c in cells] == list(RUN_ORDER)


def test_seeds_distinct_per_rep_shared_across_conditions():
    cells = plan_matrix(_CONDS, ("dvwa-sqli",), reps=3, base_seed=1000)
    by_rep = {}
    for c in cells:
        by_rep.setdefault(c.rep, set()).add(c.seed)
    # one seed per rep, shared across the 4 conditions
    assert all(len(s) == 1 for s in by_rep.values())
    assert {c.seed for c in cells} == {1001, 1002, 1003}


def test_unknown_condition_rejected():
    with pytest.raises(ValueError):
        plan_matrix(("cadis", "floor_only"), _TARGETS)


def test_random_requires_cadis():
    with pytest.raises(ValueError):
        plan_matrix(("random", "full_autonomy"), _TARGETS)


def test_reps_must_be_positive():
    with pytest.raises(ValueError):
        plan_matrix(_CONDS, _TARGETS, reps=0)


def test_pending_skips_completed(tmp_path):
    cells = plan_matrix(("cadis",), ("dvwa-sqli",), reps=2)
    # mark rep_1 done
    done_dir = cells[0].out_dir(tmp_path)
    done_dir.mkdir(parents=True)
    (done_dir / "summary.json").write_text("{}", encoding="utf-8")
    pending = pending_cells(cells, tmp_path)
    assert cells[0] not in pending
    assert cells[1] in pending


def test_cell_out_dir_layout(tmp_path):
    c = Cell(condition="cadis", target="dvwa-sqli", rep=2, seed=1002)
    d = c.out_dir(tmp_path)
    assert d.as_posix().endswith("raw_runs/cadis/dvwa-sqli/rep_2")
