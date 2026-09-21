# CADIS Signal-Decomposition

> **Status:** EXPLORATORY (newplan.md §11 offline re-scoring, §12 exploratory). Re-scores the
> **logged** per-step signals with the repo's own pure functions
> (`pentestagent/cadis/policy_core.py`). **No weight/threshold/definition changed.** No new compute.
> Reproduce: `python benchmark/signal_decomposition/run_decomposition.py`. Logged in `progress_newplan.md`.

## Question
Within CADIS's composite `I(t) = 0.35·USC + 0.30·FH + 0.35·RC` → `level = max(band_level(I),
risk_floor(RC))`, is the **RC HIGH fail-safe doing all the routing** while USC and FH contribute little?

## Fidelity check (bonus, newplan §17 post-implementation)
Recomputing `final_level` from the logged `usc/fh/rc/w/τ` via the pure functions reproduces the logged
level **exactly**: deepseek **173/173**, gemini **112/112**, gpt-oss **138/138**. The logged routing is
faithful to the spec formulas.

## Results (CADIS steps)

**Signal profile**

| Model | mean USC | mean FH | mean RC | FH>0 in | RC tier mix (LOW/MED/HIGH/CRIT) |
|---|---|---|---|---|---|
| deepseek | 0.400 | 0.000 | 0.164 | 0.0 % | 75 / 0 / 25 / 0 % |
| gemini | 0.381 | 0.087 | 0.091 | 36.6 % | 86 / 1 / 13 / 0 % |
| gpt-oss | 0.465 | 0.018 | 0.091 | 8.0 % | 86 / 1 / 13 / 0 % |

**Who sets the level?** (share of decisions set by the RC risk-floor vs the composite band)

| Model | gated (≥L1): floor / band | **L2 blocks (=2): floor / band** |
|---|---|---|
| deepseek | 90 % / 10 % | **100 % / 0 %** |
| gemini | 43 % / 57 % | **94 % / 6 %** |
| gpt-oss | 57 % / 43 % | **100 % / 0 %** |

**Leave-one-signal-out** (renormalised weights; dropping RC also drops its risk-floor). Key column is
`gate(≥2)` — the consequential *blocking* rate:

| Model | full gate(≥2) | no-RC gate(≥2) | no-USC gate(≥2) | no-FH gate(≥2) |
|---|---|---|---|---|
| deepseek | 0.249 | **0.000** | 0.249 | 0.249 |
| gemini | 0.143 | **0.063** | 0.134 | 0.134 |
| gpt-oss | 0.130 | **0.000** | 0.130 | 0.130 |

(Full per-signal HER and changed-decision fractions in `decomposition_summary.json`. HER *rises* under
no-RC only because renormalising inflates USC/FH into more low-stakes L1 notifications — the
meaningful blocking rate collapses.)

## Interpretation
1. **The consequential L2 gating is 94–100 % driven by the RC risk-floor** (RC = HIGH → floor 2 → L2).
   The composite band almost never reaches L2 on its own.
2. **Remove RC and the block rate collapses to ≈ 0**; remove USC or FH and it is essentially unchanged.
   So in this regime **the three-signal fusion effectively reduces to its rule-based RC component** for
   every decision that actually blocks or delegates.
3. **USC and FH are near-inert for gating.** They only nudge some actions into L1 *notify*. **FH is
   inert because failures are so rare** (mean FH ≈ 0; ties directly to the HCR power analysis — no
   failure history to accumulate). **USC** has real magnitude (mean ≈ 0.4) but rarely crosses the band
   thresholds relative to the RC floor, so it seldom changes the level.
4. **Design implication (honest):** the expensive `N=5` self-consistency sampling (USC) and the failure
   window (FH) bought almost nothing over the rule-based risk classifier *in this regime*. Whether they
   matter is a function of failure base-rate and the weight/threshold choice — exactly what the offline
   weight/threshold ablation grid (`results_*/ablation/weight_threshold_grid.csv`) sweeps. This bounds
   *when* fusion adds value rather than claiming it always does.
