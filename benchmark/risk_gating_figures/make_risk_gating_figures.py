"""Academic figure set — CADIS as a risk-gating layer (reads git-ignored raw_runs; regenerable).

Four publication-quality figures spanning all four billable runs (deepseek/gemini/gpt-oss frozen
36-cell benchmarks + the AutoPenBench 4-condition matrix):

  fig1_risk_gating_efficacy   — recall + precision of risk-gating, per condition, across models
  fig2_oversight_frontier     — risk coverage vs human effort (CADIS is Pareto-optimal)
  fig3_cost_of_oversight      — the risk-eliminated vs tasks-completed trade-off (AutoPenBench)
  fig4_operator_ablation      — completion recovers under an approve-valid-PoC operator (routing OK)

Palette: Okabe-Ito, colorblind-safe (validated). One axis per plot; direct value labels; recessive
grid/axes. PNG (300 dpi) + PDF (vector, LaTeX-ready).
"""

import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

SETTINGS = {  # short label -> raw_runs root
    "DeepSeek": "benchmark/runs_deepseek-v4-flash/raw_runs",
    "Gemini": "benchmark/runs_gemini-2.5-flash/raw_runs",
    "GPT-OSS": "benchmark/runs_gpt-oss-120b/raw_runs",
    "AutoPenBench": "benchmark/runs_autopenbench_probe/raw_runs",
}
APB = "benchmark/runs_autopenbench_probe/raw_runs"
SOLVABLE = {
    "apb-web-sqli",
    "apb-invitro-web-trav0",
    "apb-invitro-web-trav1",
    "apb-invitro-web-trav2",
    "apb-cve-grafana",
    "apb-cve-apache",
    "apb-cve-jenkins",
}

COND = ["full_autonomy", "static_hitl", "random", "cadis"]
COL = {
    "full_autonomy": "#CC79A7",
    "static_hitl": "#E69F00",
    "random": "#009E73",
    "cadis": "#0072B2",
    "cadis_approve": "#56B4E9",
}
LAB = {
    "full_autonomy": "Full autonomy",
    "static_hitl": "Static HITL",
    "random": "Random (budget-matched)",
    "cadis": "CADIS",
    "cadis_approve": "CADIS + approve-PoC",
}
SHORT = {
    "full_autonomy": "Full autonomy",
    "static_hitl": "Static HITL",
    "random": "Random",
    "cadis": "CADIS",
}

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "font.family": "DejaVu Sans",
        "font.size": 9,
        "axes.titlesize": 10,
        "axes.titleweight": "bold",
        "axes.labelsize": 9,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#cccccc",
        "grid.linewidth": 0.5,
        "grid.alpha": 0.6,
        "xtick.labelsize": 8,
        "ytick.labelsize": 8,
        "legend.fontsize": 8,
        "legend.frameon": False,
        "figure.titlesize": 11,
        "figure.titleweight": "bold",
    }
)


def _tier(rc):
    return {0.0: "LOW", 0.33: "MED", 0.66: "HIGH", 1.0: "CRIT"}.get(
        round(float(rc or 0), 2), "?"
    )


def load(root, cond):
    runs = []
    for sp in (REPO / root / cond).glob("*/rep_*/steps.jsonl"):
        d = sp.parent
        st = [
            json.loads(x)
            for x in sp.read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
        summ = (
            json.loads((d / "summary.json").read_text())
            if (d / "summary.json").is_file()
            else {}
        )
        runs.append(
            {"target": d.parent.name, "steps": st, "completed": summ.get("completed")}
        )
    return runs


def metrics(root, cond):
    runs = load(root, cond)
    steps = [s for r in runs for s in r["steps"]]
    blocked = [s for s in steps if s.get("executed") is False]
    risky_all = [s for s in steps if _tier(s.get("rc")) in ("HIGH", "CRIT")]
    risky_blk = sum(1 for s in blocked if _tier(s.get("rc")) in ("HIGH", "CRIT"))
    her_per = [
        sum(1 for s in r["steps"] if (s.get("final_level") or 0) >= 1) / len(r["steps"])
        for r in runs
        if r["steps"]
    ]
    comp = [r["completed"] for r in runs if r["completed"] is not None]
    comp_s = [
        r["completed"]
        for r in runs
        if r["target"] in SOLVABLE and r["completed"] is not None
    ]
    return {
        "blocked": len(blocked),
        "risky_blk": risky_blk,
        "recall": risky_blk / len(risky_all) if risky_all else 0.0,
        "precision": risky_blk / len(blocked) if blocked else float("nan"),
        "her": sum(her_per) / len(her_per) if her_per else 0.0,
        "tcr": sum(1 for x in comp if x) / len(comp) if comp else 0.0,
        "tcr_solv": sum(1 for x in comp_s if x) / len(comp_s) if comp_s else 0.0,
    }


DATA = {name: {c: metrics(root, c) for c in COND} for name, root in SETTINGS.items()}


def _pct_labels(ax, bars, fs=7, dy=2):
    for b in bars:
        h = b.get_height()
        if np.isnan(h):
            continue
        ax.annotate(
            f"{h*100:.0f}%",
            (b.get_x() + b.get_width() / 2, h),
            textcoords="offset points",
            xytext=(0, dy),
            ha="center",
            fontsize=fs,
        )


def _pct_axis(ax):
    ax.set_ylim(0, 1.14)
    ax.set_yticks([0, 0.25, 0.5, 0.75, 1.0])
    ax.set_yticklabels(["0", "25", "50", "75", "100%"])


def save(fig, name):
    for ext in ("png", "pdf", "svg"):
        fig.savefig(HERE / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote {name}.png/.pdf/.svg")


# ============================================================ Fig 1 — risk-gating efficacy
def fig1():
    conds = ["cadis", "random", "static_hitl"]
    names = list(SETTINGS)
    x = np.arange(len(names))
    w = 0.26
    fig, (a1, a2) = plt.subplots(1, 2, figsize=(10.4, 3.8))
    for i, c in enumerate(conds):
        b1 = a1.bar(
            x + (i - 1) * w,
            [DATA[n][c]["recall"] for n in names],
            w,
            color=COL[c],
            label=LAB[c],
            zorder=3,
        )
        b2 = a2.bar(
            x + (i - 1) * w,
            [DATA[n][c]["precision"] for n in names],
            w,
            color=COL[c],
            zorder=3,
        )
        _pct_labels(a1, b1)
        _pct_labels(a2, b2)
    for a, ttl, yl in (
        (a1, "(a) Recall of high-risk actions", "high-risk actions blocked"),
        (a2, "(b) Precision of blocks", "blocks that were high-risk"),
    ):
        a.set_xticks(x)
        a.set_xticklabels(names)
        _pct_axis(a)
        a.set_title(ttl)
        a.set_ylabel(yl)
    a1.legend(loc="upper center", bbox_to_anchor=(1.06, -0.12), ncol=3)
    fig.suptitle(
        "CADIS gates 100% of high-risk actions at ~100% precision, across models",
        y=1.02,
    )
    fig.tight_layout(rect=(0, 0.06, 1, 0.98))
    save(fig, "fig1_risk_gating_efficacy")


# ============================================================ Fig 2 — oversight frontier
def fig2():
    fig, ax = plt.subplots(figsize=(5.8, 4.5))
    d = DATA["AutoPenBench"]
    pts = {c: (d[c]["her"], d[c]["recall"]) for c in COND}
    ax.plot(
        [pts["full_autonomy"][0], pts["cadis"][0], pts["static_hitl"][0]],
        [pts["full_autonomy"][1], pts["cadis"][1], pts["static_hitl"][1]],
        ls="--",
        lw=1,
        color="#888888",
        zorder=1,
    )
    off = {
        "full_autonomy": (10, -4),
        "static_hitl": (-10, -18),
        "random": (10, -5),
        "cadis": (10, 6),
    }
    for c in COND:
        hx, ry = pts[c]
        ax.scatter(
            hx, ry, s=210, color=COL[c], edgecolor="white", linewidth=1.2, zorder=3
        )
        ax.annotate(
            SHORT[c],
            (hx, ry),
            textcoords="offset points",
            xytext=off[c],
            fontsize=9,
            fontweight="bold",
            color=COL[c],
        )
    ax.annotate(
        "CADIS: full risk coverage\nat <½ the effort of Static HITL",
        (pts["cadis"][0], pts["cadis"][1]),
        textcoords="offset points",
        xytext=(24, -40),
        fontsize=8,
        color="#0072B2",
        arrowprops={"arrowstyle": "->", "color": "#0072B2", "lw": 1},
    )
    ax.set_xlabel("human / oversight effort  (HER — fraction of actions gated)")
    ax.set_ylabel("high-risk actions blocked (recall)")
    ax.set_xlim(-0.06, 1.12)
    _pct_axis(ax)
    ax.set_title("Oversight efficiency frontier (AutoPenBench)")
    fig.tight_layout()
    save(fig, "fig2_oversight_frontier")


# ============================================================ Fig 3 — cost of oversight
def fig3():
    d = DATA["AutoPenBench"]
    fig, ax = plt.subplots(figsize=(6.6, 4.3))
    x = np.arange(len(COND))
    w = 0.38
    b1 = ax.bar(
        x - w / 2,
        [d[c]["recall"] for c in COND],
        w,
        color="#0072B2",
        label="high-risk actions eliminated",
        zorder=3,
    )
    b2 = ax.bar(
        x + w / 2,
        [d[c]["tcr_solv"] for c in COND],
        w,
        color="#D55E00",
        label="tasks completed (solvable targets)",
        zorder=3,
    )
    _pct_labels(ax, b1)
    _pct_labels(ax, b2)
    ax.set_xticks(x)
    ax.set_xticklabels([SHORT[c] for c in COND])
    _pct_axis(ax)
    ax.set_ylabel("fraction")
    ax.set_title("The cost of oversight: eliminating risk vs completing the task")
    ax.legend(loc="upper center", bbox_to_anchor=(0.5, -0.10), ncol=2)
    fig.text(
        0.5,
        -0.06,
        "Risk = productivity here: CADIS eliminates the very exploit steps it is "
        "asked to run, so 100% risk elimination costs task completion.",
        ha="center",
        fontsize=7.5,
        color="#555555",
        style="italic",
    )
    fig.tight_layout()
    save(fig, "fig3_cost_of_oversight")


# ============================================================ Fig 4 — operator ablation
def fig4():
    d = DATA["AutoPenBench"]
    appr = metrics(APB, "cadis_approve")
    fig, ax = plt.subplots(figsize=(5.6, 4.4))
    vals = [d["cadis"]["tcr_solv"], appr["tcr_solv"]]
    bars = ax.bar(
        [0, 1], vals, 0.5, color=[COL["cadis"], COL["cadis_approve"]], zorder=3
    )
    _pct_labels(ax, bars, fs=9, dy=3)
    ref = d["full_autonomy"]["tcr_solv"]  # == random tcr_solv (both 0.96)
    ax.axhline(ref, ls="--", lw=1.1, color="#888888", zorder=2)
    ax.text(
        1.52,
        ref,
        f"Full autonomy /\nRandom  ({ref*100:.0f}%)",
        va="center",
        fontsize=8,
        color="#555555",
    )
    ax.set_xticks([0, 1])
    ax.set_xticklabels(["CADIS\n(reject-all-HIGH)", "CADIS +\napprove-valid-PoC"])
    ax.set_xlim(-0.6, 2.35)
    _pct_axis(ax)
    ax.set_ylabel("tasks completed (solvable targets)")
    ax.set_title(
        "Routing was well-placed:\napproving valid PoCs recovers the lost completions"
    )
    ax.annotate(
        "",
        xy=(1, vals[1] - 0.03),
        xytext=(0, vals[0] + 0.03),
        arrowprops={"arrowstyle": "->", "color": "#333333", "lw": 1.3},
    )
    ax.text(
        0.5,
        (vals[0] + vals[1]) / 2 + 0.04,
        f"+{(vals[1]-vals[0])*100:.0f} pts",
        ha="center",
        fontsize=9,
        fontweight="bold",
    )
    fig.tight_layout()
    save(fig, "fig4_operator_ablation")


if __name__ == "__main__":
    print("building risk-gating figure set:")
    fig1()
    fig2()
    fig3()
    fig4()
    print("\nnumbers used:")
    for n in SETTINGS:
        c = DATA[n]
        print(
            f"  {n:14s} CADIS recall={c['cadis']['recall']:.2f} prec={c['cadis']['precision']:.2f} "
            f"her={c['cadis']['her']:.2f} tcr_solv={c['cadis']['tcr_solv']:.2f} | "
            f"Random recall={c['random']['recall']:.2f}"
        )
