"""'CADIS worked' figure set — one plot per image, distributional, no flat-100% bars.

Two themes, each on the 3-model (36-cell) runs and on AutoPenBench:
  * flailing tail  — time-to-completion per run (box + dots + mean, log): CADIS cuts the
                     catastrophic tail that full-autonomy / random suffer on doomed high-risk work.
  * risk containment — number of high-risk actions that EXECUTED WITHOUT oversight: CADIS drives it
                     to ~0, while a budget-matched random policy lets most through.

Outputs (PNG 300 dpi + PDF vector + SVG), regenerable from the git-ignored raw_runs.
"""

import json
from pathlib import Path

import matplotlib
import numpy as np

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.lines import Line2D
from matplotlib.patches import Patch

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]

FROZEN = {
    "DeepSeek-v4-flash": "benchmark/runs_deepseek-v4-flash/raw_runs",
    "Gemini-2.5-flash": "benchmark/runs_gemini-2.5-flash/raw_runs",
    "GPT-OSS-120B": "benchmark/runs_gpt-oss-120b/raw_runs",
}
APB = "benchmark/runs_autopenbench_probe/raw_runs"
COND = ["full_autonomy", "static_hitl", "random", "cadis"]
CLAB = {
    "full_autonomy": "Full\nautonomy",
    "static_hitl": "Static\nHITL",
    "random": "Random",
    "cadis": "CADIS",
}
MODEL_COL = {
    "DeepSeek-v4-flash": "#0072B2",
    "Gemini-2.5-flash": "#E69F00",
    "GPT-OSS-120B": "#009E73",
}
CCOL = {
    "full_autonomy": "#CC79A7",
    "static_hitl": "#E69F00",
    "random": "#009E73",
    "cadis": "#0072B2",
}

plt.rcParams.update(
    {
        "figure.dpi": 150,
        "savefig.dpi": 300,
        "savefig.bbox": "tight",
        "font.family": "DejaVu Sans",
        "font.size": 10,
        "axes.titlesize": 12,
        "axes.titleweight": "bold",
        "axes.labelsize": 10.5,
        "axes.linewidth": 0.8,
        "axes.spines.top": False,
        "axes.spines.right": False,
        "axes.grid": True,
        "axes.axisbelow": True,
        "grid.color": "#cfcfcf",
        "grid.linewidth": 0.5,
        "grid.alpha": 0.7,
        "xtick.labelsize": 10,
        "ytick.labelsize": 9,
        "legend.fontsize": 9,
        "legend.frameon": False,
    }
)


def _tier(rc):
    return {0.0: "LOW", 0.33: "MED", 0.66: "HIGH", 1.0: "CRIT"}.get(
        round(float(rc or 0), 2), "?"
    )


def runs(root, cond):
    out = []
    for sp in (REPO / root / cond).glob("*/rep_*/steps.jsonl"):
        st = [
            json.loads(x)
            for x in sp.read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
        out.append(st)
    return out


def ttc_seconds(root, cond):
    """Time-to-completion per run (s) = sum of executed-step durations."""
    vals = []
    for st in runs(root, cond):
        ms = sum(float(s.get("duration_ms") or 0) for s in st)
        vals.append(max(ms / 1000.0, 5e-4))  # floor so it plots on log axis
    return vals


def ungated_highrisk(root, cond):
    """Count of HIGH/CRIT actions that EXECUTED without being gated, per run (list)."""
    per = []
    for st in runs(root, cond):
        per.append(
            sum(
                1
                for s in st
                if s.get("executed") is True and _tier(s.get("rc")) in ("HIGH", "CRIT")
            )
        )
    return per


def save(fig, name):
    for ext in ("png", "pdf", "svg"):
        fig.savefig(HERE / f"{name}.{ext}")
    plt.close(fig)
    print(f"  wrote {name}")


# --------------------------------------------------------------- box helper (dots + mean diamond)
def _boxes(ax, groups, positions, color, width=0.22):
    bp = ax.boxplot(
        groups,
        positions=positions,
        widths=width,
        patch_artist=True,
        showfliers=False,
        medianprops={"color": "#222222", "lw": 1.2},
        whiskerprops={"color": color, "lw": 1},
        capprops={"color": color, "lw": 1},
        boxprops={"facecolor": color, "edgecolor": color, "alpha": 0.35, "lw": 1},
    )
    rng = np.random.default_rng(0)
    for g, p in zip(groups, positions, strict=False):
        if not g:
            continue
        ax.scatter(
            p + rng.uniform(-width * 0.32, width * 0.32, len(g)),
            g,
            s=16,
            color=color,
            alpha=0.8,
            edgecolor="white",
            linewidth=0.3,
            zorder=4,
        )
        ax.scatter(
            [p],
            [np.mean(g)],
            marker="D",
            s=55,
            facecolor="white",
            edgecolor=color,
            linewidth=1.6,
            zorder=5,
        )
    return bp


# =============================================================== Fig: TTC tail, 3 models
def fig_ttc_3model():
    fig, ax = plt.subplots(figsize=(8.6, 5.0))
    models = list(FROZEN)
    nm = len(models)
    w = 0.24
    centers = np.arange(len(COND))
    for mi, m in enumerate(models):
        pos = centers + (mi - (nm - 1) / 2) * (w + 0.03)
        groups = [ttc_seconds(FROZEN[m], c) for c in COND]
        _boxes(ax, groups, pos, MODEL_COL[m], width=w)
    ax.set_yscale("log")
    ax.set_xticks(centers)
    ax.set_xticklabels([CLAB[c] for c in COND])
    ax.set_ylabel("time-to-completion per run  (s, log scale)")
    ax.set_title(
        "CADIS collapses the catastrophic flailing tail (36-cell runs, 3 models)"
    )
    ax.set_ylim(2e-4, 2e4)
    handles = [Patch(facecolor=MODEL_COL[m], alpha=0.6, label=m) for m in models]
    handles.append(
        Line2D(
            [0],
            [0],
            marker="D",
            color="w",
            markerfacecolor="w",
            markeredgecolor="#444",
            markersize=8,
            label="mean",
        )
    )
    ax.legend(handles=handles, loc="upper center", bbox_to_anchor=(0.5, -0.12), ncol=4)
    ax.annotate(
        "full autonomy & random flail ~10³ s\non doomed high-risk work (msf2 backdoor)",
        (2.0, 7e2),
        (0.32, 4.5e3),
        fontsize=9,
        color="#555555",
        arrowprops={"arrowstyle": "->", "color": "#555555", "lw": 1},
    )
    ax.annotate(
        "CADIS gates it early:\nmean ~10³ s → ~30 s",
        (3.0, 35),
        (2.5, 1.4e3),
        fontsize=9,
        color="#0072B2",
        ha="center",
        arrowprops={"arrowstyle": "->", "color": "#0072B2", "lw": 1},
    )
    fig.tight_layout()
    save(fig, "show1_flailing_tail_3models")


# =============================================================== Fig: risk containment, 3 models
def fig_ungated_3model():
    fig, ax = plt.subplots(figsize=(8.4, 5.0))
    models = list(FROZEN)
    nm = len(models)
    w = 0.25
    centers = np.arange(len(COND))
    for mi, m in enumerate(models):
        pos = centers + (mi - (nm - 1) / 2) * (w + 0.02)
        vals = [sum(ungated_highrisk(FROZEN[m], c)) for c in COND]
        bars = ax.bar(pos, vals, w, color=MODEL_COL[m], label=m, zorder=3)
        for b, v in zip(bars, vals, strict=False):
            ax.annotate(
                str(v),
                (b.get_x() + b.get_width() / 2, v),
                textcoords="offset points",
                xytext=(0, 2),
                ha="center",
                fontsize=8,
            )
    ax.set_xticks(centers)
    ax.set_xticklabels([CLAB[c] for c in COND])
    ax.set_ylabel("high-risk actions that executed WITHOUT oversight  (count)")
    ax.set_title(
        "CADIS contains every high-risk action; a budget-matched random\n"
        "policy lets most through (36-cell runs, 3 models)"
    )
    ax.legend(loc="upper right")
    ax.annotate(
        "CADIS & Static HITL → 0\n(complete containment)",
        (3, 0),
        (2.3, 18),
        fontsize=8.5,
        color="#0072B2",
        arrowprops={"arrowstyle": "->", "color": "#0072B2", "lw": 1},
    )
    fig.tight_layout()
    save(fig, "show2_risk_containment_3models")


# =============================================================== Fig: risk containment, AutoPenBench
# NOTE: an AutoPenBench TTC figure was deliberately dropped — unlike the frozen msf2 case, CADIS does
# not trim a flailing tail on these targets (comparable distributions; the N=5 sampler even adds time),
# so a "CADIS trims the tail" claim would be unsupported here. Containment (below) is the honest win.
def fig_ungated_apb():
    fig, ax = plt.subplots(figsize=(7.4, 5.0))
    centers = np.arange(len(COND))
    vals = [sum(ungated_highrisk(APB, c)) for c in COND]
    bars = ax.bar(centers, vals, 0.6, color=[CCOL[c] for c in COND], zorder=3)
    for b, v in zip(bars, vals, strict=False):
        ax.annotate(
            str(v),
            (b.get_x() + b.get_width() / 2, v),
            textcoords="offset points",
            xytext=(0, 2),
            ha="center",
            fontsize=10,
        )
    ax.set_xticks(centers)
    ax.set_xticklabels([CLAB[c] for c in COND])
    ax.set_ylabel("high-risk actions that executed WITHOUT oversight  (count)")
    ax.set_title(
        "AutoPenBench: CADIS lets 0 high-risk actions run unchecked\n"
        "(budget-matched random lets most through)"
    )
    top = max(vals)
    ax.set_ylim(0, top * 1.15)
    ax.annotate(
        "complete containment",
        (3, vals[3]),
        (2.15, top * 0.55),
        fontsize=9,
        color="#0072B2",
        arrowprops={"arrowstyle": "->", "color": "#0072B2", "lw": 1.2},
    )
    fig.tight_layout()
    save(fig, "show3_risk_containment_autopenbench")


if __name__ == "__main__":
    print("building 'CADIS worked' showcase figures:")
    fig_ttc_3model()
    fig_ungated_3model()
    fig_ungated_apb()
    print("\nun-gated high-risk (executed w/o oversight) — AutoPenBench:")
    for c in COND:
        print(f"  {c:14s} {sum(ungated_highrisk(APB, c))}")
