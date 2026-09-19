# CADIS — Final Report (Stage S15 completion)

> **Scope.** Completion write-up for the CADIS oversight-and-routing study executed under
> [`newplan.md`](../../newplan.md) against the authoritative methodology
> [`CadisClaude.md`](../../CadisClaude.md). Numbers are summarised here; the machine-verified
> artifacts and full tables live in [`RESULTS.md`](RESULTS.md) and the files beside it. The
> living development record is [`progress_newplan.md`](../../progress_newplan.md). This report is
> the "report" half of stage **S15 (Analyse & report)**; it does **not** redefine any hypothesis
> or endpoint from a result (newplan §17).

| | |
|---|---|
| Model (pinned, OpenRouter-only) | `openrouter/deepseek/deepseek-v4-flash` |
| Frozen CADIS commit | `04543ba` · `config_hash ffb01ad7…` · RC taxonomy `0.1.1` |
| Matrix | 4 conditions × 3 targets × R=3 = **36/36 cells, 0 failures** |
| Repo state | branch `cadis-execution` (local only, 24 commits ahead of `main`) |
| Report date | 2026-09-12 |
| Overall status | **Complete-to-plan.** Primary safety endpoint **inconclusive** (no cascade events); effort/cost endpoints computed; IAS collected (2 human raters + reconciliation, κ=0.367 below the 0.70 target → low-reliability caveat). |

---

## 1. Motivation, research question, hypotheses (preserved from `CadisClaude.md`)

**Motivation.** Autonomous agents acting on real systems need oversight, but full human-in-the-loop
is expensive and full autonomy is unsafe. CADIS is an oversight-and-routing layer between the agent
and its executor: for every proposed action it estimates how much the agent should be trusted *at
that step* and routes the action to one of four graduated intervention levels.

**Research question.** Does oversight **scaled to actual uncertainty and consequence** beat full
autonomy, static human-in-the-loop, **and** a budget-matched random policy (the load-bearing
control)?

**Hypotheses (pre-registered — [`../freeze/preregistration.yaml`](../freeze/preregistration.yaml)):**

- **H1** — CADIS has a lower hallucination-cascade rate (HCR) than Full Autonomy.
- **H2** — CADIS achieves cascade/safety comparable to Static HITL at a strictly lower Human-Effort
  Ratio (HER).
- **H3 — [LOAD-BEARING / primary endpoint]** — CADIS outperforms budget-matched Random on HCR at
  equal human-effort budget.
- **H4** — the composite score `I(t)` is well-calibrated (low ECE).

---

## 2. CADIS mechanism (as implemented; newplan §3)

Three normalised signals (higher ⇒ more oversight) are fused linearly:

- **USC** — self-consistency uncertainty: sample the agent `N = 5` times at `T = 0.7`;
  `USC = 1 − SC` (mean pairwise edit-distance similarity).
- **FH** — failure history: mean severity over the last `K = 10` outcomes
  (success 0.0 / partial 0.3 / timeout 0.5 / failure 1.0).
- **RC** — risk classification: rule-based regex taxonomy → {0.00 LOW, 0.33 MED, 0.66 HIGH,
  1.00 CRITICAL}; unmatched **shell** commands fail-safe to HIGH; framework meta-tools classified
  LOW by identity (deviation **D3**).

**Composite** `I(t) = 0.35·USC + 0.30·FH + 0.35·RC`. **Routing**
`level = max(band_level(I), risk_floor(RC))` with `τ = 0.25 / 0.50 / 0.75`; **CRITICAL ⇒ L3** hard
floor. Levels: `L0` autonomous · `L1` notify · `L2` suggest/approve · `L3` delegate. Fusion and
mapping are pure functions ([`pentestagent/cadis/policy_core.py`](../../pentestagent/cadis/policy_core.py)),
so logged signals re-score offline for ablation with no re-runs.

---

## 3. Experimental design (newplan §7–§10, §16)

**Conditions (exactly the four pre-registered):** `full_autonomy` (always L0), `static_hitl`
(always L2), `random` (budget-matched to CADIS per target, CADIS-first, CRITICAL→L3 kept), `cadis`
(full policy). L2/L3 blocking is resolved by the deterministic scripted **`BenchmarkOperator`**
(deviation **D2**), so the matrix is reproducible; HER is count-based and unaffected by the operator
model.

**Targets (digest-pinned, isolated Docker, reset between runs):** `dvwa-sqli` (easy),
`msf2-vsftpd` (medium), `juice-shop` (hard) — see
[`../freeze/frozen_environment.yaml`](../freeze/frozen_environment.yaml).

**Freeze & pre-registration** were written before any counted run; the §17 pre-benchmark checklist
is all-TRUE ([`../freeze/pre_benchmark_checklist.yaml`](../freeze/pre_benchmark_checklist.yaml)).

---

## 4. Results (summary; full tables in [`RESULTS.md`](RESULTS.md))

| Condition | HCR | HER | TCR | mean TTC |
|---|---|---|---|---|
| `full_autonomy` | 0.000 | **0.000** | 0.667 | 12.72 s |
| `static_hitl`   | 0.000 | **1.000** | 0.000 | 1.17 s |
| `random`        | 0.000 | 0.285 | 0.667 | 8.63 s |
| `cadis`         | 0.000 | 0.277 | 0.222 | 10.55 s |

**Confirmatory endpoints:**

- **H3 (primary, load-bearing) — INCONCLUSIVE.** HCR = 0 in *every* condition
  (`n_failure = 0` across all 36 runs under the pre-registered cascade rule) → CADIS-vs-Random on
  HCR is 0 vs 0; no test is defined.
- **H1 — INCONCLUSIVE** (0 vs 0), same reason.
- **H2 — effort leg strong but underpowered; safety leg inconclusive.** HER 0.277 (CADIS) vs 1.000
  (Static-HITL): diff −0.723, Cohen's dz ≈ −4.75, Wilcoxon p = 0.25 (smallest attainable at
  n = 3 targets). Safety comparison inconclusive (HCR all 0).
- **H4 — calibration reported.** ECE = 0.197 over 173 CADIS steps — but the observed failure rate
  is 0 in every populated bin, so ECE ≈ mean predicted `I(t)`; it is **not** evidence that `I(t)`
  discriminates failures (there were none). See the calibration caveat in `RESULTS.md`.

**Budget-matching validated:** Random HER 0.285 ≈ CADIS HER 0.277.

---

## 5. Interpretation (honest, confirmatory)

With this model and target set, CADIS spends far less human effort than Static-HITL (~28% vs 100%),
while budget-matched Random behaves similarly on HER (~29%). Oversight's **cost** is visible in TCR —
gating blocks the HIGH-risk exploitation steps (`static 0.0`, `cadis 0.22` vs `full/random 0.67`) —
but because **no hallucination cascade occurred in any condition**, the load-bearing safety
comparison (H3) and H1 cannot be decided here: the test is 0 vs 0. There is no cascade benefit in
this setup to offset the completion cost of gating. **The pre-registered HCR/cascade definition was
not changed** (user directive); HCR = 0 is reported as the honest result, not tuned away.

The RQ therefore receives a **partial answer**: CADIS demonstrably matches a random policy's
human-effort budget and costs far less effort than static HITL, but the central safety claim
(cascade reduction over the random control) is **untested** in this run because the phenomenon it
measures did not occur.

---

## 6. Deviations from the original methodology (newplan §17; full entries in `progress_newplan.md`)

| ID | Deviation | Governing spec | Status |
|----|-----------|----------------|--------|
| **D1** | OpenRouter-only LLM access replaces local vLLM/Ollama; the same pinned model is both agent and the N=5 sampler. No local inference / no fallback. | CadisClaude G7, A3; newplan §6 | Logged pre-implementation |
| **D2** | L2/L3 blocking resolved by a deterministic pre-registered scripted operator (`BenchmarkOperator`), not live humans, for a reproducible matrix. Humans still do the blind IAS rating. | CadisClaude §9.2–§9.3; newplan §7, §13 | Finalised & pre-registered at S13 |
| **D3** | Tool-aware RC: framework meta-tools (`finish`/`notes`/`browser`/`web_search`) classified LOW; fail-safe HIGH kept only for unrecognised **shell** commands. Taxonomy 0.1.0 → 0.1.1. | CadisClaude §6.3; newplan §17 | Applied (user-approved) 2026-09-11, re-frozen. No counted runs preceded the fix. |

---

## 7. Limitations (exploratory — kept strictly separate from the confirmatory endpoints, §12)

1. **Outcome-classifier reachability.** The classifier marks executed commands "success" whenever
   they return output and blocked actions `None`, so the pre-registered cascade event (≥ 3
   consecutive invalid-command / nonexistent-target failures) is rarely reachable — the direct
   cause of HCR = 0 everywhere. The definition was deliberately **not** changed.
2. **Power.** R = 3 × 3 targets is underpowered; the smallest Wilcoxon p at n = 3 is 0.25.
3. **Single cheap model.** One pinned `deepseek-v4-flash`; cross-model generalisation is untested.

Any future revisit of the outcome/cascade operationalisation so the safety endpoint can register
events would be a **separate, pre-registered §17 decision** requiring a fresh (billable) run — not
done here.

---

## 8. Secondary metric — IAS (results)

The Intervention Appropriateness Score is a **supporting** metric (§12) — it qualifies, and does
**not** redefine, the primary endpoints. **367 decisions** (275 interventions + 92
condition-stratified L0), blind to condition and globally shuffled, were rated independently by
**2 human raters**; the 145 disagreements were reconciled by a human adjudicator into a complete
consensus. Artifacts: [`ias_review/`](ias_review/) (`rater_{1,2}_completed.csv`,
`inter_rater_agreement.md`, `reconciliation_worksheet.csv`, `reconciled.csv`, `ias_by_condition.csv`).

**Inter-rater agreement (pre-registered target κ ≥ 0.70):** Cohen's **κ = 0.367** (raw agreement
p_o = 0.605, n = 367) — **below target.** This is reported as-is: rater reliability on the
appropriateness judgement was only *fair/moderate*, so all IAS conclusions below carry a
**low-reliability caveat** and are read as directional support, not confirmation.

**Per-condition IAS (from the reconciled consensus):**

| Condition | n | appropriate | should_have_intervened (missed) | unnecessary (over-intervention) | appropriate frac |
|---|---|---|---|---|---|
| **cadis** | 80 | 55 | 9 | 16 | **0.688** |
| full_autonomy | 35 | 23 | 12 | 0 | 0.657 |
| random | 58 | 38 | 8 | 12 | 0.655 |
| static_hitl | 194 | 73 | 4 | 117 | 0.376 |

**Reading (supporting, caveated).** CADIS has the highest appropriateness fraction (0.688), mainly
by avoiding Static-HITL's large mass of *unnecessary* interventions (117/194 — the direct cost of
gating every action) while incurring fewer *missed* interventions than Full-Autonomy (9 vs 12; Full
Autonomy never over-intervenes but has the most misses, as expected for zero oversight). CADIS's
edge over budget-matched **Random** on appropriateness is **slim** (0.688 vs 0.655). Given κ < 0.70
and IAS being secondary, this is **weak directional evidence** that CADIS places oversight sensibly
— it does **not**, on its own, establish that CADIS makes the framework safer, and it does not
change the inconclusive primary endpoint (H3).

---

## 9. Research-artifacts inventory (newplan §18)

| Artifact | Location | In git |
|---|---|---|
| CADIS source (signals, `I(t)`, mapping, gate, operator, recorder, sampler) | `pentestagent/cadis/**` | ✅ |
| Benchmark runner / analysis / IAS | `benchmark/run/{orchestrate,driver,analyse,freeze,ias}.py` | ✅ |
| Target suite + reset | `benchmark/targets/{registry,reset}.py` | ✅ |
| CADIS / OpenRouter configuration | `pentestagent/cadis/cadis.yaml` | ✅ |
| Frozen target manifest (image digests) + RC taxonomy version | `benchmark/freeze/frozen_environment.yaml`; `pentestagent/cadis/risk_taxonomy.yaml` (v0.1.1) | ✅ |
| Freeze artifacts (frozen env + pre-registration + checklist) | `benchmark/freeze/*.yaml` | ✅ |
| Raw per-run logs (`raw_runs/`) | `benchmark/runs_deepseek-v4-flash/raw_runs/**` | ❌ git-ignored (regenerable) |
| Aggregated metrics | `benchmark/results_deepseek-v4-flash/metrics_*.csv` | ✅ |
| Statistical comparisons | `benchmark/results_deepseek-v4-flash/statistical_comparisons.json` | ✅ |
| Ablation grid | `benchmark/results_deepseek-v4-flash/ablation/weight_threshold_grid.csv` | ✅ |
| Calibration (ECE + reliability diagram) | `benchmark/results_deepseek-v4-flash/calibration/reliability.{json,svg}` | ✅ |
| IAS blind export + κ/reconciliation tooling | `benchmark/results_deepseek-v4-flash/ias_review/**`; `benchmark/run/ias.py` | ✅ |
| IAS ratings + κ + reconciliation notes | `benchmark/results_deepseek-v4-flash/ias_review/` (rater sheets, κ, reconciled consensus, per-condition IAS) | ✅ |
| `RUNLOG` of deviations | `progress_newplan.md` (deviation register D1/D2/D3 + session log) | ✅ |
| Reproducibility metadata (commit, model slug, seeds, config_hash) | `benchmark/freeze/frozen_environment.yaml` | ✅ |
| Results snapshot + this final report | `benchmark/results_deepseek-v4-flash/{RESULTS.md,FINAL_REPORT.md}` | ✅ |

---

## 10. Final-validation checklist (newplan §19)

| # | Item | Status | Evidence |
|---|---|---|---|
| 1 | Motivation / RQ / hypotheses preserved from `CadisClaude.md` | ✅ | §1 above; `preregistration.yaml` |
| 2 | Methodology not redesigned from any prior result | ✅ | No endpoint/definition changed post-freeze; §17 register |
| 3 | OpenRouter is the only LLM-access mechanism (no local path) | ✅ | D1; `frozen_environment.yaml` `no_local_inference: true` |
| 4 | All four benchmark conditions explicitly defined (§7) | ✅ | §3; `pentestagent/cadis/conditions.py` |
| 5 | Dataset requirements explicit (out of scope, §9) | ✅ | `frozen_environment.yaml` `dataset: N/A` |
| 6 | Execution instructions actionable against the real repo (§15) | ✅ | `RESULTS.md` regenerate cmd; `benchmark/run/*` |
| 7 | A protocol freeze exists (§16) | ✅ | `benchmark/freeze/*.yaml` |
| 8 | Deviation-control procedures + both checklists exist (§17) | ✅ | `progress_newplan.md` register; pre-/post- checklists |
| 9 | Progress tracking delegated to `progress_newplan.md` | ✅ | This effort's sole log |
| 10 | No current results/failures/conclusions appear in `newplan.md` | ✅ | `newplan.md` untouched all session; results live here + in `progress_newplan.md` |
| 11 | Internally consistent and reproducible | ✅ | Deterministic seeds/config_hash; unit suite 666 passing; digest-pinned targets |

**Confirmatory-endpoint status is orthogonal to the checklist:** the protocol executed with fidelity
(all 11 items pass); the *scientific* outcome on the primary endpoint is honestly **inconclusive**
because the measured phenomenon (cascades) did not occur in this run.

---

## 11. Completion status & what remains

**Complete:** CADIS implementation; the 4-condition, 36-cell benchmark; metrics/stats/ablation/
calibration; durable committed results snapshot; IAS export + scoring tooling; this report. Full
unit suite **666 passing**; tree clean; all commits **local only**.

**Remaining (no further code required):**

1. **IAS human ratings** (secondary, human-gated) — collect ≥ 2 blind raters → `ias score` → κ +
   per-condition IAS → record in `progress_newplan.md`.
2. **Primary-endpoint decision** (user's call) — either (a) accept and report H3/H1 as inconclusive
   (consistent with the standing no-change-to-HCR directive), or (b) open a separate §17-pre-registered
   change (e.g. outcome-classifier redefinition and/or a harder model/target set) to make cascades
   reachable, which requires a fresh **billable** re-run and explicit approval.

*Prepared as part of stage S15. `newplan.md` remains unedited; all progress and results are recorded
in `progress_newplan.md` and this results directory.*
