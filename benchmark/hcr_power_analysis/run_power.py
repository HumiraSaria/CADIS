"""HCR detectability / power analysis (EXPLORATORY; newplan.md section 11/12).

Turns the primary null "HCR = 0 everywhere" into a quantitative statement about what this
design *could* have detected. The pre-registered cascade rule (analyse.py, unchanged) is:
a run has a cascade iff it contains >= N=3 CONSECUTIVE steps of outcome_class 'failure'
(invalid-command / nonexistent-target; 'timeout'/'partial' do NOT count).

Two questions, both answered from logged data only (no new compute):
  (1) OBSERVED: what is the longest consecutive-'failure' streak that actually occurred?
      If it never reaches N=3, the phenomenon simply did not occur at the granularity the
      metric requires -- an assumption-free detectability statement.
  (2) POWER: at the observed marginal failure rate p (fraction of executed steps that are
      'failure'), and the observed run-length distribution, how many cascades would an i.i.d.
      Bernoulli(p) process be expected to produce? And what failure rate p* would this design
      have needed to have 80% power to see >=1 cascade? (i.i.d. is a lower bound on clustering,
      so this is conservative w.r.t. the empirical streak in (1).)
"""
import glob, json, os, collections, sys

HERE = os.path.dirname(os.path.abspath(__file__))
REPO = os.path.abspath(os.path.join(HERE, "..", ".."))
N = 3  # DEFAULT_CASCADE_N (analyse.py)
FAILURE = "failure"
MODELS = {
    "deepseek-v4-flash": ("benchmark/runs_deepseek-v4-flash/raw_runs", "v0.1 (degenerate)"),
    "gemini-2.5-flash":  ("benchmark/runs_gemini-2.5-flash/raw_runs",  "v0.2.0"),
    "gpt-oss-120b":      ("benchmark/runs_gpt-oss-120b/raw_runs",      "v0.2.0"),
}

def rows(p):
    out = []
    with open(p, encoding="utf-8") as f:
        for ln in f:
            ln = ln.strip()
            if ln:
                out.append(json.loads(ln))
    return out

def max_streak(outcomes, cls=FAILURE):
    best = cur = 0
    for o in outcomes:
        cur = cur + 1 if o == cls else 0
        best = max(best, cur)
    return best

def p_no_run(L, p, n=N):
    """P(no run of >= n consecutive failures) in L i.i.d. Bernoulli(p) trials (DP over
    current-streak states 0..n-1; state n is absorbing 'cascade happened')."""
    if L <= 0:
        return 1.0
    # dp[k] = prob of being in 'current consecutive-failure = k' with no absorption yet
    dp = [0.0] * n
    dp[0] = 1.0
    absorbed = 0.0
    for _ in range(L):
        ndp = [0.0] * n
        # success (prob 1-p) resets streak to 0
        s = sum(dp) * (1.0 - p)
        ndp[0] += s
        # failure (prob p) advances streak
        for k in range(n):
            if k + 1 >= n:
                absorbed += dp[k] * p
            else:
                ndp[k + 1] += dp[k] * p
        dp = ndp
    return sum(dp)  # prob never absorbed

def expected_cascades(lengths, p, n=N):
    return sum(1.0 - p_no_run(L, p, n) for L in lengths)

def prob_ge1_cascade(lengths, p, n=N):
    prod = 1.0
    for L in lengths:
        prod *= p_no_run(L, p, n)
    return 1.0 - prod

def solve_pstar(lengths, target_power=0.8, n=N):
    lo, hi = 0.0, 1.0
    for _ in range(60):
        mid = (lo + hi) / 2
        if prob_ge1_cascade(lengths, mid, n) < target_power:
            lo = mid
        else:
            hi = mid
    return (lo + hi) / 2

def main():
    report = {"cascade_N": N, "failure_classes": [FAILURE], "models": {}}
    for model, (rel, clf) in MODELS.items():
        root = os.path.join(REPO, rel)
        if not os.path.isdir(root):
            print(f"[skip] {model}", file=sys.stderr); continue
        run_lengths, exec_steps, fail_steps = [], 0, 0
        streak_hist = collections.Counter()
        observed_cascades = 0
        by_cond_fail = collections.Counter(); by_cond_exec = collections.Counter()
        for f in glob.glob(os.path.join(root, "*", "*", "rep_*", "steps.jsonl")):
            cond = f.split(os.sep)[-4]
            rs = rows(f)
            outs = [r.get("outcome_class") for r in rs]  # None for blocked, breaks streaks
            ex = [o for o in outs if o is not None]
            run_lengths.append(len(ex))
            exec_steps += len(ex)
            nfail = sum(1 for o in outs if o == FAILURE)
            fail_steps += nfail
            by_cond_fail[cond] += nfail; by_cond_exec[cond] += len(ex)
            ms = max_streak(outs)
            streak_hist[ms] += 1
            if ms >= N:
                observed_cascades += 1
        p = fail_steps / exec_steps if exec_steps else 0.0
        exp_casc = expected_cascades(run_lengths, p) if p > 0 else 0.0
        pstar = solve_pstar(run_lengths, 0.8)
        report["models"][model] = {
            "classifier": clf,
            "n_runs": len(run_lengths),
            "total_executed_steps": exec_steps,
            "total_failure_steps": fail_steps,
            "marginal_failure_rate_p": round(p, 5),
            "observed_max_consec_failure_streak": max(streak_hist) if streak_hist else 0,
            "runs_by_max_streak": dict(sorted(streak_hist.items())),
            "observed_cascades_ge3": observed_cascades,
            "expected_cascades_iid_at_p": round(exp_casc, 4),
            "p_star_for_80pct_power": round(pstar, 4),
            "failure_rate_by_condition": {c: round(by_cond_fail[c] / by_cond_exec[c], 4)
                                          for c in sorted(by_cond_exec) if by_cond_exec[c]},
            "mean_run_length": round(sum(run_lengths) / len(run_lengths), 2) if run_lengths else 0,
        }
    out = os.path.join(HERE, "power_summary.json")
    json.dump(report, open(out, "w", encoding="utf-8"), indent=2)
    print(f"HCR detectability / power  (cascade rule: >= {N} consecutive 'failure' steps)\n")
    for m, d in report["models"].items():
        print(f"### {m}  [{d['classifier']}]")
        print(f"    runs={d['n_runs']}  exec_steps={d['total_executed_steps']}  "
              f"failures={d['total_failure_steps']}  p={d['marginal_failure_rate_p']}  "
              f"mean_len={d['mean_run_length']}")
        print(f"    OBSERVED max consecutive-failure streak = "
              f"{d['observed_max_consec_failure_streak']}  (need >= {N} for a cascade)  "
              f"-> observed cascades = {d['observed_cascades_ge3']}")
        print(f"    runs by max-streak: {d['runs_by_max_streak']}")
        print(f"    i.i.d. expected cascades at observed p = {d['expected_cascades_iid_at_p']}")
        print(f"    failure rate p* needed for 80% power to see >=1 cascade = "
              f"{d['p_star_for_80pct_power']}  (observed p = {d['marginal_failure_rate_p']})")
        print(f"    per-condition failure rate: {d['failure_rate_by_condition']}\n")
    print(f"wrote {os.path.relpath(out, REPO)}")

if __name__ == "__main__":
    main()
