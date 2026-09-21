"""Build the 6 thesis exhibits from committed results + raw logs (EXPLORATORY; no new compute,
no LLM calls, no pre-registered definition changed). Outputs PNG+SVG under benchmark/figures/.

Colours: per-model Okabe-Ito palette (colourblind-safe); verdicts blue/vermillion/grey.
Run:  ./venv/Scripts/python.exe benchmark/figures/make_figures.py
"""
import csv, glob, json, os, collections
import numpy as np
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.patches import Patch

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
OUT = HERE

MODELS = ["deepseek-v4-flash", "gemini-2.5-flash", "gpt-oss-120b"]
CORRECTED = ["gemini-2.5-flash", "gpt-oss-120b"]  # v0.2.0 (failure-comparable)
COLOR = {"deepseek-v4-flash": "#0072B2", "gemini-2.5-flash": "#E69F00", "gpt-oss-120b": "#009E73"}
CONDITIONS = ["full_autonomy", "static_hitl", "random", "cadis"]
COND_LABEL = {"full_autonomy": "full\nautonomy", "static_hitl": "static\nHITL",
              "random": "random", "cadis": "CADIS"}
VERDICT_COLOR = {"VIABLE": "#0072B2", "DOOMED": "#D55E00", "OTHER": "#999999"}
TARGETS = ["dvwa-sqli", "juice-shop", "msf2-vsftpd"]
plt.rcParams.update({"font.size": 11, "axes.grid": True, "grid.alpha": 0.3,
                     "axes.axisbelow": True, "figure.dpi": 120})

def save(fig, name):
    for ext in ("png", "svg"):
        fig.savefig(os.path.join(OUT, f"{name}.{ext}"), bbox_inches="tight",
                    dpi=200 if ext == "png" else None)
    plt.close(fig)
    print("wrote", name + ".png / .svg")

def load_json(p):
    return json.load(open(os.path.join(REPO, p), encoding="utf-8"))

def per_run_rows():
    rows = []
    for m in MODELS:
        p = os.path.join(REPO, f"benchmark/results_{m}/metrics_per_run.csv")
        for r in csv.DictReader(open(p, encoding="utf-8")):
            r["model"] = m
            rows.append(r)
    return rows

def by_condition():
    d = {}
    for m in MODELS:
        p = os.path.join(REPO, f"benchmark/results_{m}/metrics_by_condition_summary.csv")
        d[m] = {r["condition"]: r for r in csv.DictReader(open(p, encoding="utf-8"))}
    return d

# ---- cascade-DP for the detectability curve --------------------------------
def p_no_run(L, p, n=3):
    if L <= 0:
        return 1.0
    dp = [0.0] * n; dp[0] = 1.0
    for _ in range(L):
        ndp = [0.0] * n
        ndp[0] += sum(dp) * (1 - p)
        for k in range(n):
            if k + 1 < n:
                ndp[k + 1] += dp[k] * p
        dp = ndp
    return sum(dp)

def prob_ge1(lengths, p, n=3):
    prod = 1.0
    for L in lengths:
        prod *= p_no_run(L, p, n)
    return 1 - prod

def run_lengths(model):
    root = os.path.join(REPO, f"benchmark/runs_{model}/raw_runs")
    lens = []
    for f in glob.glob(os.path.join(root, "*", "*", "rep_*", "steps.jsonl")):
        n = 0
        for ln in open(f, encoding="utf-8"):
            ln = ln.strip()
            if ln and json.loads(ln).get("outcome_class") is not None:
                n += 1
        lens.append(n)
    return lens

# ============================ FIG 1 ========================================= #
def fig1():
    power = load_json("benchmark/hcr_power_analysis/power_summary.json")["models"]
    fig, (axa, axb) = plt.subplots(1, 2, figsize=(12.5, 4.6))
    # (a) max-streak histogram (corrected models only)
    cats = [0, 1, 2, 3]; xlab = ["0", "1", "2", "≥3"]
    x = np.arange(len(cats)); w = 0.38
    for i, m in enumerate(CORRECTED):
        hist = power[m]["runs_by_max_streak"]
        vals = [hist.get(str(c), 0) if c < 3 else sum(v for k, v in hist.items() if int(k) >= 3)
                for c in cats]
        axa.bar(x + (i - 0.5) * w, vals, w, label=m, color=COLOR[m], edgecolor="black", linewidth=0.4)
    axa.axvline(2.5, color="#D55E00", ls="--", lw=1.8)
    axa.text(2.52, axa.get_ylim()[1] * 0.9, "cascade threshold (N=3)", color="#D55E00",
             rotation=90, va="top", fontsize=9)
    axa.set_xticks(x); axa.set_xticklabels(xlab)
    axa.set_xlabel("longest run of consecutive invalid-command failures")
    axa.set_ylabel("number of runs (of 36)")
    axa.set_title("(a) Observed cascade streaks never reach N=3")
    axa.legend(fontsize=9, title="model (v0.2.0)")
    # (b) detectability curve
    ps = np.linspace(0, 0.30, 121)
    for m in CORRECTED:
        L = run_lengths(m)
        y = [prob_ge1(L, p) for p in ps]
        axb.plot(ps, y, color=COLOR[m], lw=2, label=m)
        obs = power[m]["marginal_failure_rate_p"]
        axb.axvline(obs, color=COLOR[m], ls=":", lw=1.5)
        axb.scatter([obs], [prob_ge1(L, obs)], color=COLOR[m], zorder=5, s=35,
                    edgecolor="black", linewidth=0.5)
    axb.axhline(0.8, color="grey", ls="--", lw=1)
    axb.text(0.005, 0.82, "80% power", color="grey", fontsize=9)
    axb.annotate("observed rates\n(1.0-3.4%)", xy=(0.03, 0.05), xytext=(0.09, 0.25),
                 fontsize=9, arrowprops=dict(arrowstyle="->", color="black"))
    axb.annotate("p* ≈ 15-17%\nfor 80% power", xy=(0.16, 0.8), xytext=(0.17, 0.45),
                 fontsize=9, arrowprops=dict(arrowstyle="->", color="black"))
    axb.set_xlabel("invalid-command failure rate  p  (per executed step)")
    axb.set_ylabel("P(≥1 cascade across 36 runs)")
    axb.set_title("(b) Failure rate needed to detect a cascade")
    axb.set_xlim(0, 0.30); axb.set_ylim(0, 1.02); axb.legend(fontsize=9)
    fig.suptitle("Fig 1 — Hallucination cascades are structurally absent in this regime "
                 "(HCR = 0 is a boundary condition, not underpowered luck)", fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.95))
    save(fig, "fig1_cascade_nonoccurrence")

# ============================ FIG 2 ========================================= #
def fig2():
    summ = by_condition(); runs = per_run_rows()
    fig, ax = plt.subplots(figsize=(9, 5))
    x = np.arange(len(CONDITIONS)); w = 0.26
    for i, m in enumerate(MODELS):
        vals = [float(summ[m][c]["her"]) for c in CONDITIONS]
        ax.bar(x + (i - 1) * w, vals, w, color=COLOR[m], label=m, edgecolor="black", linewidth=0.4)
        # overlay per-run her dots
        for j, c in enumerate(CONDITIONS):
            pts = [float(r["her"]) for r in runs if r["model"] == m and r["condition"] == c]
            jit = (np.random.default_rng(1).uniform(-0.06, 0.06, len(pts)))
            ax.scatter(np.full(len(pts), x[j] + (i - 1) * w) + jit, pts, s=12,
                       color="black", alpha=0.5, zorder=5)
    ax.axhline(1.0, color="#D55E00", ls="--", lw=1)
    ax.set_xticks(x); ax.set_xticklabels([COND_LABEL[c] for c in CONDITIONS])
    ax.set_ylabel("Human-Effort Ratio  (fraction of actions gated, ≥L1)")
    ax.set_ylim(0, 1.08)
    ax.set_title("Fig 2 — CADIS ≈ Random ≪ Static-HITL: budget-matching holds across all 3 models\n"
                 "(bars = condition mean; dots = individual runs, n=9 per bar)", fontsize=11)
    ax.legend(fontsize=9, ncol=3, loc="upper center")
    save(fig, "fig2_human_effort_by_condition")

# ============================ FIG 3 ========================================= #
def fig3():
    agg = collections.defaultdict(lambda: collections.Counter())  # (model,target)->verdict counts
    p = os.path.join(REPO, "benchmark/gated_action_audit/blocked_action_classification.csv")
    for r in csv.DictReader(open(p, encoding="utf-8")):
        agg[(r["model"], r["target"])][r["verdict"]] += int(r["blocked_by_cadis"])
    fig, axes = plt.subplots(1, 3, figsize=(13, 4.4), sharey=True)
    order = ["VIABLE", "DOOMED", "OTHER"]
    x = np.arange(len(TARGETS))
    for ax, m in zip(axes, MODELS):
        bottoms = np.zeros(len(TARGETS))
        for v in order:
            vals = [agg[(m, t)].get(v, 0) for t in TARGETS]
            ax.bar(x, vals, 0.6, bottom=bottoms, color=VERDICT_COLOR[v],
                   edgecolor="black", linewidth=0.4, label=v)
            for xi, (val, bot) in enumerate(zip(vals, bottoms)):
                if val:
                    ax.text(xi, bot + val / 2, str(val), ha="center", va="center",
                            fontsize=9, color="white", fontweight="bold")
            bottoms += np.array(vals)
        ax.set_xticks(x); ax.set_xticklabels(["dvwa", "juice-shop", "msf2"], fontsize=9)
        ax.set_title(m, fontsize=10)
    axes[0].set_ylabel("CADIS-blocked actions (count)")
    handles = [Patch(facecolor=VERDICT_COLOR[v], edgecolor="black",
                     label={"VIABLE": "VIABLE (real exploit suppressed)",
                            "DOOMED": "DOOMED (never works — pruned)",
                            "OTHER": "OTHER (recon / noise)"}[v]) for v in order]
    fig.legend(handles=handles, loc="lower center", ncol=3, fontsize=9, frameon=False,
               bbox_to_anchor=(0.5, -0.04))
    fig.suptitle("Fig 3 — Same policy, two regimes: CADIS prunes DOOMED flailing on msf2 but "
                 "suppresses VIABLE exploits on juice-shop", fontsize=11.5)
    fig.tight_layout(rect=(0, 0.02, 1, 0.94))
    save(fig, "fig3_blocked_action_two_regime")

# ============================ FIG 4 ========================================= #
def fig4():
    dec = load_json("benchmark/signal_decomposition/decomposition_summary.json")["models"]
    fig, (axa, axb) = plt.subplots(1, 2, figsize=(12.5, 4.6))
    # (a) leave-one-out gate(>=2)
    variants = [("full", "full_gate_ge2", None), ("no RC", "ablation_no_RC", "gate_ge2"),
                ("no USC", "ablation_no_USC", "gate_ge2"), ("no FH", "ablation_no_FH", "gate_ge2")]
    x = np.arange(len(variants)); w = 0.26
    for i, m in enumerate(MODELS):
        vals = []
        for _, key, sub in variants:
            vals.append(dec[m][key] if sub is None else dec[m][key][sub])
        axa.bar(x + (i - 1) * w, vals, w, color=COLOR[m], label=m, edgecolor="black", linewidth=0.4)
    axa.set_xticks(x); axa.set_xticklabels([v[0] for v in variants])
    axa.set_ylabel("gate rate  (fraction of actions at ≥L2, blocking)")
    axa.set_title("(a) Remove RC → blocking collapses to ~0;\nremove USC/FH → unchanged")
    axa.legend(fontsize=9)
    # (b) L2 attribution floor vs band
    xb = np.arange(len(MODELS))
    floor = [dec[m]["attribution_L2(eq2)"]["floor_driven"] for m in MODELS]
    band = [dec[m]["attribution_L2(eq2)"]["band_driven"] for m in MODELS]
    axb.bar(xb, floor, 0.55, color="#CC79A7", edgecolor="black", linewidth=0.4,
            label="RC risk-floor driven")
    axb.bar(xb, band, 0.55, bottom=floor, color="#56B4E9", edgecolor="black", linewidth=0.4,
            label="composite band driven")
    for xi, fv in enumerate(floor):
        axb.text(xi, fv / 2, f"{fv*100:.0f}%", ha="center", va="center", color="white",
                 fontweight="bold", fontsize=10)
    axb.set_xticks(xb); axb.set_xticklabels([m.split("-")[0] for m in MODELS])
    axb.set_ylim(0, 1.05); axb.set_ylabel("share of L2 (blocking) decisions")
    axb.set_title("(b) L2 blocking is 94-100% set by the RC floor")
    axb.legend(fontsize=9, loc="lower center")
    fig.suptitle("Fig 4 — In this regime the three-signal fusion collapses to its rule-based RC term",
                 fontsize=12)
    fig.tight_layout(rect=(0, 0, 1, 0.94))
    save(fig, "fig4_rc_dominance")

# ============================ FIG 5 ========================================= #
def fig5():
    runs = per_run_rows()
    fig, ax = plt.subplots(figsize=(9.5, 5))
    group_w = 0.8; box_w = group_w / len(MODELS)
    for i, m in enumerate(MODELS):
        for j, c in enumerate(CONDITIONS):
            ttc = [float(r["ttc_ms"]) / 1000.0 for r in runs
                   if r["model"] == m and r["condition"] == c]
            pos = j + (i - 1) * box_w
            bp = ax.boxplot([ttc], positions=[pos], widths=box_w * 0.9, patch_artist=True,
                            manage_ticks=False, showfliers=False,
                            medianprops=dict(color="black"))
            for b in bp["boxes"]:
                b.set(facecolor=COLOR[m], alpha=0.65, edgecolor="black", linewidth=0.5)
            jit = np.random.default_rng(2).uniform(-box_w * 0.28, box_w * 0.28, len(ttc))
            ax.scatter(np.full(len(ttc), pos) + jit, ttc, s=12, color=COLOR[m],
                       edgecolor="black", linewidth=0.3, zorder=5)
            if ttc:  # mean marker (this is the quantity Table 1 reports)
                ax.scatter([pos], [np.mean(ttc)], marker="D", s=42, color="white",
                           edgecolor="black", linewidth=1.1, zorder=6)
    ax.set_yscale("log")
    ax.set_xticks(range(len(CONDITIONS)))
    ax.set_xticklabels([COND_LABEL[c] for c in CONDITIONS])
    ax.set_ylabel("time-to-completion per run  (s, log scale)")
    handles = [Patch(facecolor=COLOR[m], alpha=0.65, edgecolor="black", label=m) for m in MODELS]
    handles.append(plt.Line2D([0], [0], marker="D", color="white", markerfacecolor="white",
                              markeredgecolor="black", markersize=7, label="mean (Table 1)", lw=0))
    ax.legend(handles=handles, fontsize=9, ncol=4, loc="upper center")
    ax.set_title("Fig 5 — CADIS eliminates the catastrophic flailing tail on the weaker models\n"
                 "(full/random reach ~10³ s on msf2); deepseek shows no gap. Box+dots+mean, "
                 "n=9 runs each.", fontsize=10.5)
    save(fig, "fig5_ttc_distribution")

# ============================ TABLE 1 ======================================= #
def table1():
    summ = by_condition()
    metrics = [("HCR", "hcr", "{:.3f}"), ("HER", "her", "{:.3f}"),
               ("TCR", "tcr", "{:.3f}"), ("TTC (s)", "ttc_ms", "{:.1f}")]
    lines = ["# Table 1 — Master results (condition x metric x model)", "",
             "> HCR=Hallucination-Cascade Rate, HER=Human-Effort Ratio, TCR=Task-Completion Rate, "
             "TTC=mean Time-to-Completion. n=9 runs per cell (3 targets x R=3). "
             "deepseek uses classifier v0.1 (HCR degenerate); gemini/gpt-oss v0.2.0.", ""]
    header = "| Metric | Condition | " + " | ".join(MODELS) + " |"
    sep = "|" + "---|" * (len(MODELS) + 2)
    lines += [header, sep]
    csv_rows = []
    for mlabel, key, fmt in metrics:
        for c in CONDITIONS:
            cells = []
            for m in MODELS:
                v = float(summ[m][c][key])
                if key == "ttc_ms":
                    v /= 1000.0
                cells.append(fmt.format(v))
            lines.append(f"| {mlabel} | {c} | " + " | ".join(cells) + " |")
            csv_rows.append([mlabel, c] + cells)
    open(os.path.join(OUT, "table1_master_results.md"), "w", encoding="utf-8").write("\n".join(lines) + "\n")
    with open(os.path.join(OUT, "table1_master_results.csv"), "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f); w.writerow(["metric", "condition"] + MODELS); w.writerows(csv_rows)
    print("wrote table1_master_results.md / .csv")

if __name__ == "__main__":
    fig1(); fig2(); fig3(); fig4(); fig5(); table1()
    print("\nAll exhibits written to", os.path.relpath(OUT, REPO))
