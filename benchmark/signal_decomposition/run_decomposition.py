"""CADIS signal-decomposition (EXPLORATORY; newplan.md section 11/12).

Question (LLM-council review): within CADIS's routing, is the RC HIGH fail-safe doing all the
work, while USC and FH contribute little? Answered by re-scoring the *logged* per-step signals
with the repo's own pure routing functions (policy_core.py) -- no new compute, no LLM calls,
no pre-registered weight/threshold/definition changed.

For CADIS steps we report:
  1. Fidelity: recompute final_level from logged usc/fh/rc/w/tau; must equal the logged value.
  2. Signal profile: mean of each signal; how often FH>0; RC tier mix.
  3. Attribution: for each gated step, is the level set by the RC risk_floor or by the
     composite band (USC/FH pushing I above a threshold)?
  4. Leave-one-signal-out (renormalised weights; dropping RC also drops its risk_floor):
     how much does HER / gate-rate / the routing decision change when each signal is removed?
     The signal whose removal changes routing most is the load-bearing one.
"""
import glob, json, os, sys
from pentestagent.cadis.policy_core import (
    compute_composite, band_level, risk_floor, map_to_level,
    DEFAULT_WEIGHTS, DEFAULT_THRESHOLDS,
)

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
TAU = DEFAULT_THRESHOLDS
MODELS = {
    "deepseek-v4-flash": "benchmark/runs_deepseek-v4-flash/raw_runs",
    "gemini-2.5-flash":  "benchmark/runs_gemini-2.5-flash/raw_runs",
    "gpt-oss-120b":      "benchmark/runs_gpt-oss-120b/raw_runs",
}

def rows(p):
    out = []
    with open(p, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out

def renorm_level(pairs, rc=None):
    """Composite over a subset of (weight, value) pairs, renormalised; level = max(band, floor).
    If rc is None the RC signal (and its floor) is excluded."""
    wsum = sum(w for w, _ in pairs)
    I = sum(w * v for w, v in pairs) / wsum
    b = band_level(I, TAU)
    return b if rc is None else max(b, risk_floor(rc))

def frac(xs, pred):
    return sum(1 for x in xs if pred(x)) / len(xs) if xs else 0.0

def main():
    report = {"weights": list(DEFAULT_WEIGHTS), "thresholds": list(TAU), "models": {}}
    for model, rel in MODELS.items():
        root = os.path.join(REPO, rel)
        if not os.path.isdir(root):
            print(f"[skip] {model}", file=sys.stderr); continue
        steps = []
        for f in glob.glob(os.path.join(root, "cadis", "*", "rep_*", "steps.jsonl")):
            steps += rows(f)
        w1, w2, w3 = DEFAULT_WEIGHTS
        fidelity_ok = 0
        recs = []
        for r in steps:
            usc, fh, rc = r.get("usc") or 0.0, r.get("fh") or 0.0, r.get("rc") or 0.0
            I = compute_composite(usc, fh, rc, DEFAULT_WEIGHTS)
            full = map_to_level(I, rc, TAU)
            if full == r.get("final_level"):
                fidelity_ok += 1
            b, fl = band_level(I, TAU), risk_floor(rc)
            recs.append({
                "usc": usc, "fh": fh, "rc": rc, "I": I, "band": b, "floor": fl, "full": full,
                "no_RC":  renorm_level([(w1, usc), (w2, fh)], rc=None),
                "no_USC": renorm_level([(w2, fh), (w3, rc)], rc=rc),
                "no_FH":  renorm_level([(w1, usc), (w3, rc)], rc=rc),
            })
        n = len(recs)
        gated = [r for r in recs if r["full"] >= 1]
        l2 = [r for r in recs if r["full"] == 2]
        def attrib(subset):
            if not subset:
                return {"floor_driven": 0.0, "band_driven": 0.0}
            return {
                "floor_driven": frac(subset, lambda r: r["floor"] >= r["band"] and r["floor"] >= 1),
                "band_driven":  frac(subset, lambda r: r["band"] > r["floor"]),
            }
        def stats(key):
            return {
                "HER_ge1": round(frac(recs, lambda r: r[key] >= 1), 4),
                "gate_ge2": round(frac(recs, lambda r: r[key] >= 2), 4),
                "changed_vs_full": round(frac(recs, lambda r: r[key] != r["full"]), 4),
            }
        report["models"][model] = {
            "n_cadis_steps": n,
            "fidelity_recompute_match": f"{fidelity_ok}/{n}",
            "signal_means": {"usc": round(sum(r['usc'] for r in recs)/n, 4),
                              "fh": round(sum(r['fh'] for r in recs)/n, 4),
                              "rc": round(sum(r['rc'] for r in recs)/n, 4)},
            "frac_FH_gt0": round(frac(recs, lambda r: r["fh"] > 0), 4),
            "rc_tier_mix": {
                "LOW": round(frac(recs, lambda r: r["floor"] == 0), 4),
                "MED": round(frac(recs, lambda r: r["floor"] == 1), 4),
                "HIGH": round(frac(recs, lambda r: r["floor"] == 2), 4),
                "CRIT": round(frac(recs, lambda r: r["floor"] == 3), 4)},
            "full_HER_ge1": round(frac(recs, lambda r: r["full"] >= 1), 4),
            "full_gate_ge2": round(frac(recs, lambda r: r["full"] >= 2), 4),
            "attribution_gated(ge1)": attrib(gated),
            "attribution_L2(eq2)": attrib(l2),
            "ablation_no_RC": stats("no_RC"),
            "ablation_no_USC": stats("no_USC"),
            "ablation_no_FH": stats("no_FH"),
        }
    out = os.path.join(HERE, "decomposition_summary.json")
    json.dump(report, open(out, "w", encoding="utf-8"), indent=2)
    print(f"CADIS signal decomposition (weights {DEFAULT_WEIGHTS}, thresholds {TAU})\n")
    for m, d in report["models"].items():
        print(f"### {m}  (CADIS steps={d['n_cadis_steps']}, fidelity {d['fidelity_recompute_match']})")
        print(f"    signal means: {d['signal_means']}   FH>0 in {d['frac_FH_gt0']*100:.1f}% of steps")
        print(f"    RC tier mix : {d['rc_tier_mix']}")
        print(f"    FULL policy : HER(>=1)={d['full_HER_ge1']}  gate(>=2)={d['full_gate_ge2']}")
        print(f"    attribution among gated(>=1): {d['attribution_gated(ge1)']}")
        print(f"    attribution among L2 (==2)  : {d['attribution_L2(eq2)']}")
        print(f"    ablation no_RC : {d['ablation_no_RC']}")
        print(f"    ablation no_USC: {d['ablation_no_USC']}")
        print(f"    ablation no_FH : {d['ablation_no_FH']}\n")
    print(f"wrote {os.path.relpath(out, REPO)}")

if __name__ == "__main__":
    main()
