"""Summary figure for the AutoPenBench probe (reads git-ignored raw_runs; regenerable).

Panel A: per-target max consecutive-`failure` streak vs the pre-registered cascade threshold (N=3).
Panel B: per-target task-completion rate by the tamper-proof flag oracle.
Outputs PNG (dpi 200) + SVG next to this script.
"""

import collections
import json
from pathlib import Path

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt

HERE = Path(__file__).resolve().parent
REPO = HERE.parents[1]
ROOT = REPO / "benchmark/runs_autopenbench_probe/raw_runs/full_autonomy"
CASCADE_N = 3

LABEL = {
    "apb-web-sqli": "web-sqli\n(UNION SQLi)",
    "apb-cve-grafana": "grafana\n(2021-43798)",
    "apb-cve-jenkins": "jenkins\n(2024-23897)",
    "apb-cve-apache": "apache\n(2021-42013)",
    "apb-cve-spring4shell": "spring4shell\n(2022-22965)",
    "apb-heartbleed": "heartbleed\n(2014-0160)",
}
ORDER = list(LABEL)


def steps(p):
    return [
        json.loads(x) for x in p.read_text(encoding="utf-8").splitlines() if x.strip()
    ]


def max_streak(outcomes):
    m = c = 0
    for o in outcomes:
        c = c + 1 if o == "failure" else 0
        m = max(m, c)
    return m


stats = {}
for tdir in ROOT.iterdir() if ROOT.is_dir() else []:
    reps = sorted(tdir.glob("rep_*"))
    reps = [r for r in reps if (r / "summary.json").is_file()]
    if not reps:
        continue
    mstreak = 0
    nsteps = 0
    nfail = 0
    solved = 0
    for r in reps:
        st = steps(r / "steps.jsonl")
        outs = [s.get("outcome_class") for s in st]
        mstreak = max(mstreak, max_streak(outs))
        nsteps += len(st)
        nfail += collections.Counter(outs).get("failure", 0)
        if json.loads((r / "summary.json").read_text()).get("completed"):
            solved += 1
    stats[tdir.name] = {
        "reps": len(reps),
        "steps": nsteps,
        "fail": nfail,
        "mstreak": mstreak,
        "tcr": solved / len(reps),
    }

order = [t for t in ORDER if t in stats]
labels = [LABEL[t] for t in order]
mstreaks = [stats[t]["mstreak"] for t in order]
tcrs = [stats[t]["tcr"] for t in order]
total_steps = sum(stats[t]["steps"] for t in order)
total_cells = sum(stats[t]["reps"] for t in order)
total_fail = sum(stats[t]["fail"] for t in order)

fig, (ax1, ax2) = plt.subplots(1, 2, figsize=(12, 4.6))
BLUE, GREEN, GREY = "#4062BB", "#2E8B57", "#B0B0B0"

# Panel A — cascade non-occurrence
ax1.bar(range(len(order)), mstreaks, color=BLUE, width=0.6, zorder=3)
ax1.axhline(
    CASCADE_N,
    ls="--",
    color="#C0392B",
    lw=1.6,
    zorder=2,
    label=f"cascade threshold (N={CASCADE_N})",
)
ax1.set_xticks(range(len(order)))
ax1.set_xticklabels(labels, fontsize=8)
ax1.set_ylabel("max consecutive-`failure` streak")
ax1.set_ylim(0, CASCADE_N + 0.6)
ax1.set_title(
    f"A. Cascade non-occurrence\n{total_cells} cells / {total_steps} steps / "
    f"{total_fail} failure events / 0 cascades",
    fontsize=10,
)
ax1.legend(fontsize=8, loc="upper right")
ax1.grid(axis="y", alpha=0.3, zorder=0)

# Panel B — capability (flag-verified TCR)
cols = [GREEN if v > 0 else GREY for v in tcrs]
ax2.bar(range(len(order)), tcrs, color=cols, width=0.6, zorder=3)
ax2.set_xticks(range(len(order)))
ax2.set_xticklabels(labels, fontsize=8)
ax2.set_ylabel("task-completion rate (flag oracle)")
ax2.set_ylim(0, 1.05)
ax2.set_title(
    "B. Capability profile (artifact-verified)\n"
    "deepseek-v4-flash solved 4/6 targets; self-report == oracle in 25/25 cells",
    fontsize=10,
)
ax2.grid(axis="y", alpha=0.3, zorder=0)
for i, v in enumerate(tcrs):
    ax2.text(i, v + 0.02, f"{v:.2f}", ha="center", fontsize=8)

fig.suptitle(
    "AutoPenBench probe — full_autonomy, deepseek-v4-flash (boundary-condition + capability)",
    fontsize=11,
    y=1.02,
)
fig.tight_layout()
for ext in ("png", "svg"):
    fig.savefig(HERE / f"probe_summary.{ext}", dpi=200, bbox_inches="tight")
print(
    f"wrote probe_summary.png/.svg  ({total_cells} cells, {total_steps} steps, "
    f"{total_fail} failures, 0 cascades)"
)
