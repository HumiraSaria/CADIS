"""Unit tests for the IAS tooling (S15): blind export + Cohen's kappa + reconciliation.

Governing spec: CadisClaude.md §9.2-§9.3 (step 5), newplan.md §13. IAS is secondary.
"""

import csv
import json
from types import SimpleNamespace

import pytest

from benchmark.run.ias import (
    BLIND_FIELDS,
    RATING_CATEGORIES,
    applied_oversight_label,
    build_export,
    cohen_kappa,
    decision_kind,
    export,
    percent_agreement,
    score,
    select_decisions,
)

# --------------------------------------------------------------------------- #
# fixtures / helpers
# --------------------------------------------------------------------------- #


def _step(
    step_id,
    final_level=0,
    human_decision=None,
    target="dvwa-sqli",
    seed=1001,
    proposed_action='terminal {"command": "nmap x"}',
    **extra,
):
    row = {
        "step_id": step_id,
        "final_level": final_level,
        "human_decision": human_decision,
        "target": target,
        "seed": seed,
        "proposed_action": proposed_action,
        "usc": 0.4,
        "fh": 0.0,
        "rc": 0.66,
        "i_t": 0.5,
        "band_level": 0,
        "risk_floor": 0,
        "cadis_level": final_level,
        "outcome_class": "success",
        "executed": final_level != 2,
    }
    row.update(extra)
    return row


def _run(condition, target, steps):
    return SimpleNamespace(condition=condition, target=target, rep=1, steps=steps)


def _write_run(root, condition, target, rep, steps):
    d = root / "raw_runs" / condition / target / f"rep_{rep}"
    d.mkdir(parents=True, exist_ok=True)
    with (d / "steps.jsonl").open("w", encoding="utf-8") as f:
        for s in steps:
            f.write(json.dumps(s) + "\n")
    (d / "summary.json").write_text(
        json.dumps({"levels": [s["final_level"] for s in steps]}), encoding="utf-8"
    )


# --------------------------------------------------------------------------- #
# pure helpers
# --------------------------------------------------------------------------- #


def test_applied_oversight_label_covers_all_levels():
    assert applied_oversight_label({"final_level": 0}) == "autonomous"
    assert applied_oversight_label({"final_level": 1}) == "notified"
    assert (
        applied_oversight_label({"final_level": 2, "human_decision": "approve"})
        == "gated_approved"
    )
    assert (
        applied_oversight_label({"final_level": 2, "human_decision": "reject"})
        == "gated_rejected"
    )
    assert (
        applied_oversight_label({"final_level": 2, "human_decision": None}) == "gated"
    )
    assert applied_oversight_label({"final_level": 3}) == "delegated"


def test_decision_kind():
    assert decision_kind({"final_level": 0}) == "non_intervention"
    assert decision_kind({"final_level": 1}) == "intervention"
    assert decision_kind({"final_level": 2}) == "intervention"


def test_percent_agreement():
    assert percent_agreement(["a", "b", "c"], ["a", "x", "c"]) == pytest.approx(2 / 3)
    assert percent_agreement([], []) == 0.0


def test_cohen_kappa_perfect():
    labels = ["appropriate", "unnecessary", "should_have_intervened"]
    r = cohen_kappa(labels, labels)
    assert r["p_o"] == 1.0
    assert r["kappa"] == pytest.approx(1.0)


def test_cohen_kappa_known_half():
    # p_o=0.75, p_e=0.5 -> kappa=0.5 (hand-computed)
    a = ["appropriate", "appropriate", "appropriate", "unnecessary"]
    b = ["appropriate", "appropriate", "unnecessary", "unnecessary"]
    r = cohen_kappa(a, b)
    assert r["p_o"] == pytest.approx(0.75)
    assert r["p_e"] == pytest.approx(0.5)
    assert r["kappa"] == pytest.approx(0.5)


def test_cohen_kappa_zero():
    a = ["appropriate", "appropriate", "unnecessary", "unnecessary"]
    b = ["appropriate", "unnecessary", "appropriate", "unnecessary"]
    r = cohen_kappa(a, b)
    assert r["p_o"] == pytest.approx(0.5)
    assert r["kappa"] == pytest.approx(0.0)


def test_cohen_kappa_degenerate_single_category():
    a = ["appropriate", "appropriate"]
    r = cohen_kappa(a, a)
    assert r["kappa"] is None
    assert r["p_o"] == 1.0
    assert "p_e == 1" in r["note"]


def test_cohen_kappa_length_mismatch_raises():
    with pytest.raises(ValueError):
        cohen_kappa(["appropriate"], ["appropriate", "unnecessary"])


# --------------------------------------------------------------------------- #
# selection / export
# --------------------------------------------------------------------------- #


def _mixed_runs():
    # cadis: 2 interventions + 4 L0 ; full_autonomy: 0 interventions + 6 L0
    cadis = [
        _step(
            f"c{i}",
            final_level=(2 if i < 2 else 0),
            human_decision=("reject" if i < 2 else None),
            target="dvwa-sqli",
            seed=1001,
        )
        for i in range(6)
    ]
    full = [
        _step(f"f{i}", final_level=0, target="juice-shop", seed=1001) for i in range(6)
    ]
    return [
        _run("cadis", "dvwa-sqli", cadis),
        _run("full_autonomy", "juice-shop", full),
    ]


def test_select_keeps_all_interventions_and_samples_l0():
    runs = _mixed_runs()
    selected, stats = select_decisions(runs, l0_frac=0.5, seed=7)
    assert stats["n_interventions"] == 2
    # L0 pools: cadis 4 -> ceil(0.5*4)=2 ; full 6 -> 3
    assert stats["l0_by_condition"]["cadis"] == {"pool": 4, "sampled": 2}
    assert stats["l0_by_condition"]["full_autonomy"] == {"pool": 6, "sampled": 3}
    assert stats["n_l0_sampled"] == 5
    assert stats["n_selected"] == 7
    assert len(selected) == 7


def test_select_l0_frac_zero_and_one():
    runs = _mixed_runs()
    _, s0 = select_decisions(runs, l0_frac=0.0, seed=1)
    assert s0["n_l0_sampled"] == 0 and s0["n_selected"] == 2
    _, s1 = select_decisions(runs, l0_frac=1.0, seed=1)
    assert s1["n_l0_sampled"] == 10 and s1["n_selected"] == 12


def test_build_export_is_deterministic_and_seed_sensitive():
    runs = _mixed_runs()
    blind_a, key_a, _ = build_export(runs, l0_frac=0.5, seed=7)
    blind_b, key_b, _ = build_export(runs, l0_frac=0.5, seed=7)
    # same seed -> identical order + ids
    assert [r["blind_id"] for r in key_a] == [r["blind_id"] for r in key_b]
    assert [r["step_id"] for r in key_a] == [r["step_id"] for r in key_b]
    # blind ids are contiguous and zero-padded
    assert key_a[0]["blind_id"].startswith("IAS-")
    # different seed -> (very likely) different shuffle order
    _, key_c, _ = build_export(runs, l0_frac=0.5, seed=99999)
    assert [r["step_id"] for r in key_a] != [r["step_id"] for r in key_c]


def test_blind_rows_leak_nothing():
    runs = _mixed_runs()
    blind, key, _ = build_export(runs, l0_frac=1.0, seed=3)
    for row in blind:
        assert set(row.keys()) == set(BLIND_FIELDS)
        for leaky in (
            "condition",
            "seed",
            "step_id",
            "usc",
            "fh",
            "rc",
            "i_t",
            "cadis_level",
            "band_level",
            "risk_floor",
            "outcome_class",
        ):
            assert leaky not in row
    # ...but the key retains full provenance for de-blinding
    assert all("condition" in r and "i_t" in r for r in key)
    # blind_id is the shared join key
    assert {r["blind_id"] for r in blind} == {r["blind_id"] for r in key}


# --------------------------------------------------------------------------- #
# end-to-end export -> score
# --------------------------------------------------------------------------- #


def test_export_writes_expected_files(tmp_path):
    root = tmp_path / "runs"
    _write_run(
        root,
        "cadis",
        "dvwa-sqli",
        1,
        [_step("c0", 2, "reject"), _step("c1", 2, "approve"), _step("c2", 0)],
    )
    _write_run(
        root,
        "full_autonomy",
        "juice-shop",
        1,
        [_step("f0", 0, target="juice-shop"), _step("f1", 0, target="juice-shop")],
    )
    out = tmp_path / "ias_review"
    res = export(root / "raw_runs", out, l0_frac=1.0, seed=5, model="openrouter/x/y")
    assert (out / "export_for_review" / "ias_decisions_blind.csv").is_file()
    assert (out / "ias_key.csv").is_file()
    assert (out / "export_for_review" / "ias_export_manifest.json").is_file()
    assert (out / "README.md").is_file()
    man = res["manifest"]
    assert man["selection"]["n_interventions"] == 2
    assert man["rating_categories"] == list(RATING_CATEGORIES)
    # header of the blind sheet is exactly BLIND_FIELDS
    header = (
        (out / "export_for_review" / "ias_decisions_blind.csv")
        .read_text(encoding="utf-8")
        .splitlines()[0]
    )
    assert header.split(",") == list(BLIND_FIELDS)


def test_score_pending_with_one_rater(tmp_path):
    out = tmp_path / "ias_review"
    (out / "export_for_review").mkdir(parents=True)
    (out / "ias_key.csv").write_text(
        "blind_id,condition\nIAS-0001,cadis\n", encoding="utf-8"
    )
    (out / "rater_1_completed.csv").write_text(
        "blind_id,rating\nIAS-0001,appropriate\n", encoding="utf-8"
    )
    res = score(out)
    assert res["status"] == "pending"


def _write_rater(path, ratings):
    with open(path, "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(f, fieldnames=["blind_id", "rating", "notes"])
        w.writeheader()
        for bid, r in ratings.items():
            w.writerow({"blind_id": bid, "rating": r, "notes": ""})


def test_score_full_agreement_writes_ias(tmp_path):
    out = tmp_path / "ias_review"
    out.mkdir()
    # key: two cadis, one full_autonomy
    with open(out / "ias_key.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "blind_id",
                "condition",
                "applied_oversight",
                "target",
                "proposed_action",
            ],
        )
        w.writeheader()
        w.writerow(
            {
                "blind_id": "IAS-0001",
                "condition": "cadis",
                "applied_oversight": "gated_rejected",
                "target": "dvwa-sqli",
                "proposed_action": "rm -rf /",
            }
        )
        w.writerow(
            {
                "blind_id": "IAS-0002",
                "condition": "cadis",
                "applied_oversight": "autonomous",
                "target": "dvwa-sqli",
                "proposed_action": "curl x",
            }
        )
        w.writerow(
            {
                "blind_id": "IAS-0003",
                "condition": "full_autonomy",
                "applied_oversight": "autonomous",
                "target": "juice-shop",
                "proposed_action": "sqlmap x",
            }
        )
    ratings = {
        "IAS-0001": "appropriate",
        "IAS-0002": "appropriate",
        "IAS-0003": "should_have_intervened",
    }
    _write_rater(out / "rater_1_completed.csv", ratings)
    _write_rater(out / "rater_2_completed.csv", ratings)
    res = score(out)
    assert res["status"] == "scored"
    assert res["n_common"] == 3
    assert (
        res["mean_kappa"] is None
        or res["pairwise_kappa"][0]["kappa"] in (None, 1.0)
        or res["pairwise_kappa"][0]["p_o"] == 1.0
    )
    assert res["n_disagreements"] == 0
    assert res["consensus_complete"] is True
    assert (out / "inter_rater_agreement.md").is_file()
    assert (out / "ias_by_condition.csv").is_file()
    by_cond = {r["condition"]: r for r in res["ias_by_condition"]}
    assert by_cond["cadis"]["appropriate"] == 2
    assert by_cond["full_autonomy"]["should_have_intervened"] == 1


def test_score_disagreement_writes_reconciliation(tmp_path):
    out = tmp_path / "ias_review"
    out.mkdir()
    with open(out / "ias_key.csv", "w", newline="", encoding="utf-8") as f:
        w = csv.DictWriter(
            f,
            fieldnames=[
                "blind_id",
                "condition",
                "applied_oversight",
                "target",
                "proposed_action",
            ],
        )
        w.writeheader()
        for bid, cond in [("IAS-0001", "cadis"), ("IAS-0002", "random")]:
            w.writerow(
                {
                    "blind_id": bid,
                    "condition": cond,
                    "applied_oversight": "gated_approved",
                    "target": "dvwa-sqli",
                    "proposed_action": "x",
                }
            )
    _write_rater(
        out / "rater_1_completed.csv",
        {"IAS-0001": "appropriate", "IAS-0002": "unnecessary"},
    )
    _write_rater(
        out / "rater_2_completed.csv",
        {"IAS-0001": "appropriate", "IAS-0002": "appropriate"},
    )
    res = score(out)
    assert res["n_disagreements"] == 1
    assert res["consensus_complete"] is False  # IAS-0002 unresolved
    assert (out / "reconciliation_worksheet.csv").is_file()
    # now reconcile IAS-0002 and re-run
    (out / "reconciled.csv").write_text(
        "blind_id,reconciled_rating\nIAS-0002,unnecessary\n", encoding="utf-8"
    )
    res2 = score(out, reconciled=out / "reconciled.csv")
    assert res2["consensus_complete"] is True
    by_cond = {r["condition"]: r for r in res2["ias_by_condition"]}
    assert by_cond["random"]["unnecessary"] == 1
