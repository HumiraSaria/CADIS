# HCR Detectability / Power Analysis

> **Status:** EXPLORATORY (newplan.md §11 offline re-analysis, §12 exploratory). **No
> pre-registered definition changed** — the cascade rule (`N=3` consecutive `failure` steps),
> outcome classifier, and endpoint are used exactly as in `benchmark/run/analyse.py`. No new compute.
> Reproduce: `python benchmark/hcr_power_analysis/run_power.py`. Logged in `progress_newplan.md`.

## Question
The primary endpoint returned **HCR = 0 in every condition of every model** (H1/H3 undecidable, 0 vs 0).
Is that an *underpowered* null (too few/short runs) or a *structural* one (the hazard doesn't arise
in this regime)? This turns "we saw zero" into a quantitative answer, from logged data only.

## Cascade rule (unchanged, from `analyse.py`)
A run has a cascade iff it contains **≥ 3 consecutive** steps of `outcome_class == "failure"`
(invalid-command / nonexistent-target). `timeout` and `partial` are **not** cascade-eligible.

## Results

| Model | Classifier | Runs | Exec steps | `failure` steps | Marginal rate *p* | **Max observed consecutive-failure streak** | i.i.d. expected cascades at *p* | *p\** for 80% power |
|---|---|---|---|---|---|---|---|---|
| deepseek-v4-flash | v0.1 | 36 | 495 | 0 | 0.000 | **0** | 0.000 | 0.164 |
| gemini-2.5-flash | v0.2.0 | 36 | 476 | 16 | 0.0336 | **1** | 0.015 | 0.167 |
| gpt-oss-120b | v0.2.0 | 36 | 582 | 6 | 0.0103 | **1** | 0.0006 | 0.154 |

Run-length: mean ≈ 13–16 executed steps. Per-condition failure rates are all ≈ 0–4% (see
`power_summary.json`); no condition approaches the cascade regime.

## Interpretation
1. **Assumption-free:** the longest run of consecutive invalid-command failures that *actually
   occurred* was **1** (deepseek 0). Failures never even doubled up, let alone reached the `N=3`
   the metric requires. HCR = 0 is **structural**, not a sampling accident.
2. **Power (i.i.d. Bernoulli at the observed rate, over the observed run lengths):** the expected
   number of cascades across all 36 runs is ≈ **0.015 (gemini)** and **0.0006 (gpt-oss)** — i.e. this
   design was never expected to see a cascade at these base rates.
3. **What the design *could* have detected:** it would have needed an invalid-command failure rate of
   **≈ 15–17 %** to have 80 % power to see even one cascade. The observed rate (1–3.4 %) is **5–16×
   below** that. So the flash/open models on these tractable single-service/web targets simply do not
   hallucinate invalid commands often enough, or in long enough chains, for the cascade phenomenon to
   arise — a genuine **boundary condition**, reported without changing the pre-registered rule.

## Caveats
- The i.i.d. calculation is a modelling simplification; positive autocorrelation of failures would
  *raise* cascade probability, so it does not fully bound the tail. The **empirical max streak = 1** is
  the decisive, assumption-free statement; the i.i.d. figures are supporting context.
- deepseek's `p = 0` is a v0.1 classifier artifact (all executed steps logged `success`); the real base
  rate is carried by the two v0.2.0 models. `p\*` depends only on run lengths/count, so it is
  classifier-independent.
