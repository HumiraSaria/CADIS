"""Full 4-condition matrix figure (reads git-ignored raw_runs; regenerable).

Panel A: the oversight cost/benefit frontier — HER (oversight effort) vs TCR (flag-verified
completion) per condition; the budget-matched Random vs CADIS contrast is the load-bearing point.
Panel B: per-target TCR for full_autonomy / random / cadis, showing CADIS's completion loss.
"""

import collections
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / "benchmark/runs_autopenbench_probe/raw_runs"
CONDS = ["full_autonomy", "static_hitl", "random", "cadis"]
CLABEL = {
    "full_autonomy": "full autonomy",
    "static_hitl": "static HITL",
    "random": "random\n(budget-matched)",
    "cadis": "CADIS",
}
CCOL = {
    "full_autonomy": "#B0B0B0",
    "static_hitl": "#E69F00",
    "random": "#2E8B57",
    "cadis": "#4062BB",
}


def load(cond):
    rows = []
    for sp in (ROOT / cond).glob("*/rep_*/steps.jsonl"):
        d = sp.parent
        summ = (
            json.loads((d / "summary.json").read_text())
            if (d / "summary.json").is_file()
            else {}
        )
        steps = [
            json.loads(x)
            for x in sp.read_text(encoding="utf-8").splitlines()
            if x.strip()
        ]
        her = (
            (sum(1 for s in steps if (s.get("final_level") or 0) >= 1) / len(steps))
            if steps
            else 0.0
        )
        rows.append(
            {"target": d.parent.name, "completed": summ.get("completed"), "her": her}
        )
    return rows


data = {c: load(c) for c in CONDS}
her = {
    c: (sum(r["her"] for r in data[c]) / len(data[c])) if data[c] else 0 for c in CONDS
}
tcr = {
    c: (sum(1 for r in data[c] if r["completed"]) / len(data[c])) if data[c] else 0
    for c in CONDS
}
targets = sorted({r["target"] for c in CONDS for r in data[c]})


def tcr_t(cond, t):
    v = [
        r["completed"]
        for r in data[cond]
        if r["target"] == t and r["completed"] is not None
    ]
    return sum(v) / len(v) if v else 0.0


fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(13, 5))

# Panel A: HER vs TCR frontier
for c in CONDS:
    ax1.scatter(
        her[c],
        tcr[c],
        s=260,
        color=CCOL[c],
        edgecolor="black",
        zorder=3,
        label=CLABEL[c].replace("\n", " "),
    )
    ax1.annotate(
        CLABEL[c].replace("\n", " "),
        (her[c], tcr[c]),
        textcoords="offset points",
        xytext=(10, 6),
        fontsize=9,
    )
# highlight the equal-budget random-vs-cadis contrast
ax1.annotate(
    "",
    xy=(her["cadis"], tcr["cadis"]),
    xytext=(her["random"], tcr["random"]),
    arrowprops=dict(arrowstyle="->", color="#C0392B", lw=1.8),
)
ax1.text(
    (her["cadis"] + her["random"]) / 2,
    (tcr["cadis"] + tcr["random"]) / 2 - 0.06,
    "same oversight budget,\nCADIS completes fewer",
    color="#C0392B",
    fontsize=8.5,
    ha="center",
)
ax1.set_xlabel("HER — human/oversight effort (fraction of actions gated)")
ax1.set_ylabel("TCR — task completion (flag-verified)")
ax1.set_title(
    "A. Oversight cost vs benefit\nHCR = 0 in ALL conditions → no safety benefit to offset the cost",
    fontsize=10,
)
ax1.set_xlim(-0.08, 1.12)
ax1.set_ylim(0, 1.02)
ax1.grid(alpha=0.3, zorder=0)

# Panel B: per-target TCR for full/random/cadis
import numpy as np

show = ["full_autonomy", "random", "cadis"]
x = np.arange(len(targets))
w = 0.26
for i, c in enumerate(show):
    ax2.bar(
        x + (i - 1) * w,
        [tcr_t(c, t) for t in targets],
        w,
        color=CCOL[c],
        label=CLABEL[c].replace("\n", " "),
        zorder=3,
    )
ax2.set_xticks(x)
ax2.set_xticklabels(
    [t.replace("apb-", "").replace("invitro-web-", "") for t in targets],
    rotation=40,
    ha="right",
    fontsize=8,
)
ax2.set_ylabel("TCR (flag oracle)")
ax2.set_ylim(0, 1.05)
ax2.set_title(
    "B. Per-target completion — CADIS gates the productive exploits\n"
    "solved: full 25 / random 26 / CADIS 17 (of 31); CADIS vs Random dz=-0.90, p=0.0625",
    fontsize=10,
)
ax2.legend(fontsize=8, loc="lower left")
ax2.grid(axis="y", alpha=0.3, zorder=0)

fig.suptitle(
    "AutoPenBench full 4-condition CADIS matrix — deepseek-v4-flash (9 targets, 124 cells)",
    fontsize=11,
    y=1.02,
)
fig.tight_layout()
for ext in ("png", "svg"):
    fig.savefig(HERE / f"matrix_summary.{ext}", dpi=200, bbox_inches="tight")
print("HER:", {c: round(her[c], 3) for c in CONDS})
print("TCR:", {c: round(tcr[c], 3) for c in CONDS})
print("wrote matrix_summary.png/.svg")
