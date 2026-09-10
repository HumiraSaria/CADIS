# CADIS Research — Execution Protocol (`newplan.md`)

> **Status:** forward-looking execution protocol. This document defines *what will be done and
> exactly how*, from a clean slate, to implement and benchmark CADIS according to its original
> research design.
>
> **Authoritative methodological reference:** [`CadisClaude.md`](CadisClaude.md). Where this protocol
> and `CadisClaude.md` appear to differ, `CadisClaude.md` governs the methodology; this document only
> operationalises it and adapts the **LLM-access mechanism to OpenRouter** (§6).
>
> **Companion progress log:** [`progress_newplan.md`](progress_newplan.md) — the *only* place
> implementation progress, decisions, issues, and deviations are recorded. This protocol stays clean
> and forward-looking; it is **not** a progress record.
>
> **Clean-slate basis:** this protocol treats the experiment as **not yet executed**. It incorporates
> no prior runs, results, model comparisons, statistics, or conclusions. Statements about the current
> codebase (§5) describe implementation *state to be brought into conformity*, not evidence about
> CADIS's performance.

---

## 1. Research motivation & questions (`CadisClaude.md` §1, §3)

LLM agents driving offensive-security tasks in authorised lab environments fail in a compounding way:
they **hallucinate** (propose a command/flag/CVE/path that does not exist, stated with full fluency and
no visible uncertainty), and those errors **cascade** because each step's output feeds the next, so one
false premise poisons everything downstream.

**CADIS** is an oversight-and-routing layer between the agent and its executor. For every proposed
action it estimates how much the agent should be trusted *at that step* and routes the action to one of
four graduated intervention levels (autonomous → notify → suggest/approve → delegate).

**Central thesis.** An oversight policy that **scales with actual uncertainty and actual consequence**
outperforms (a) full autonomy, (b) static human-in-the-loop, **and (c) a random intervention policy
spending the same human effort**. The last comparison is load-bearing: it tests whether CADIS
intervenes at the *right* moments, not merely at some rate.

**Research questions.**
- **RQ1.** Does CADIS reduce unsafe/cascading outcomes relative to full autonomy?
- **RQ2.** Does CADIS approach static-HITL safety while demanding *less* human effort?
- **RQ3.** Are CADIS's interventions *well-placed* — i.e., does it beat a budget-matched random policy?
- **RQ4.** Is the composite intervention score `I(t)` **calibrated** (does it predict failure)?

## 2. Hypotheses

- **H1 (RQ1):** CADIS has a lower hallucination-cascade rate than Full Autonomy.
- **H2 (RQ2):** CADIS achieves cascade/safety comparable to Static HITL at a strictly lower Human-Effort Ratio.
- **H3 (RQ3, load-bearing):** CADIS outperforms Random Intervention **at equal human-effort budget** on the primary safety metric.
- **H4 (RQ4):** `I(t)` is well-calibrated (low ECE; monotone reliability curve).

All hypotheses are pre-registered (§16) before any benchmark run; results are reported regardless of sign.

---

## 3. CADIS architecture & mechanism (`CadisClaude.md` §4–§6 — authoritative)

CADIS fuses **three conceptually independent signals**, each normalised so **higher = more oversight needed**.

### 3.1 Signals
- **Self-Consistency / Uncertainty `USC` (§6.1).** Query the agent `N = 5` times on the *identical*
  context at temperature `T = 0.7`, giving sampled commands `cmd₁…cmd_N`. Mean pairwise similarity
  `SC(t) = (2 / N(N−1)) · Σ_{i<j} sim(cmd_i, cmd_j)`; **`USC(t) = 1 − SC(t)`**. Default `sim` = normalised
  edit distance (`1 − editdist/maxlen`); embedding similarity is a documented **ablation** alternative only.
- **Failure History `FH` (§6.2).** Sliding window of the last `K = 10` outcomes, severity weights
  `success 0.0 / partial 0.3 / timeout 0.5 / failure 1.0`; `FH(t)` = mean weight over the window.
- **Risk Classification `RC` (§6.3).** Rule-based taxonomy (regex per tier, reviewed vs MITRE ATT&CK) →
  `{0.00 LOW, 0.33 MEDIUM, 0.66 HIGH, 1.00 CRITICAL}`. **Fail-safe:** unmatched commands default to **HIGH**
  and are logged as taxonomy gaps.

### 3.2 Composite score & routing (§6.4–§6.5)
- **Composite:** `I(t) = w1·USC + w2·FH + w3·RC`, with `w1,w2,w3 = 0.35, 0.30, 0.35` (sum 1, all > 0).
- **Band level** (thresholds `τ0,τ1,τ2 = 0.25, 0.50, 0.75`): `0` if `I<τ0`; `1` if `τ0≤I<τ1`; `2` if `τ1≤I<τ2`; `3` if `I≥τ2`.
- **Risk floor:** `risk_floor(RC) = 0/1/2/3` for LOW/MEDIUM/HIGH/CRITICAL.
- **Final level:** `level(t) = max(band_level(I(t)), risk_floor(RC(t)))`.
- **Asymmetry:** risk can raise the level but never lower it; **CRITICAL ⇒ L3** hard floor, regardless of `I`.

### 3.3 Intervention levels (§5.3)
`L0` Autonomous (execute) · `L1` Notify (execute + inform) · `L2` Suggest (block for approve/edit/reject) · `L3` Delegate (full human handoff).

### 3.4 Design contract
The fusion/mapping logic is a set of **pure functions** (no I/O, deterministic given inputs) so cached
signal logs can be re-scored offline for ablation (§11) and the formulas here can be unit-tested 1:1
against the code.

---

## 4. Development workflow (stages, gated)

Each stage lists **Objective / Tasks / Outputs / Verification / Gate-to-next**. Progress for each is
recorded in `progress_newplan.md`, never here.

| # | Stage | Objective | Key outputs | Verification / Gate |
|---|---|---|---|---|
| S1 | Understand spec | Internalise `CadisClaude.md` §4–§9 | annotated reference notes (in log) | reviewer confirms signal/fusion/mapping understood |
| S2 | Conformity audit | Map current code vs spec (§5 here) | audit table in log | every §3 element classified conform / to-change |
| S3 | Define changes | Turn audit into a change list | change list in log | each change cites a `CadisClaude.md` section |
| S4 | Implement CADIS core | Bring signals + `I(t)` + mapping into conformity | code + unit tests | pure-function tests match §3 formulas 1:1 |
| S5 | Configure OpenRouter | Single pinned model, params, retries, logging (§6) | `cadis.yaml`/config + call logging | smoke call succeeds; all params logged |
| S6 | Integrate with agent | CADIS gate at the action seam; operator L1/L2/L3 wired | integrated loop | one gated step executes each of L0–L3 |
| S7 | Targets | Bring up isolated digest-pinned target suite (§8) | running sandbox + targets | `reset_target` restores each target cleanly |
| S8 | Conditions | Implement the 4 conditions (§7) | condition switch | each condition maps `Decision→level` per spec |
| S9 | Logging | Per-step row capture (§14) | recorder schema | a run writes every §14 field |
| S10 | Benchmark runner | Orchestrator over conditions×targets×reps | runner + plan | dry run plans the exact matrix (§10) |
| S11 | Analysis pipeline | Metrics + stats + ablation + calibration (§10–§12) | analysis scripts | reproduces metrics from a sample run |
| S12 | Fidelity verification | Run the post-implementation checklist (§17) | signed checklist | all items pass |
| S13 | Freeze | Freeze + pre-register (§16) | `frozen_environment.yaml`, `preregistration.yaml` | freeze artifacts written & recorded |
| S14 | Execute benchmark | Run the full matrix (§10) | raw logs | all planned runs valid or explicitly re-run |
| S15 | Analyse & report | Stats, ablation, calibration, artifacts (§19) | results + figures | primary/secondary metrics computed per §12 |

Advance a stage only when its Gate passes; record the gate outcome in `progress_newplan.md`.

---

## 5. Implementation conformity audit (current code → original design)

The codebase already contains most of CADIS. The following items must be brought into conformity with
`CadisClaude.md` **before freeze**. (These describe code *state*, not experimental findings.)

Relevant files: `pentestagent/cadis/{policy_core.py, config.py, conditions.py, cadis.yaml, engine.py,
recorder.py, operator.py, signals/{agreement.py,failure_history.py,risk.py}}`,
`benchmark/run/{driver.py, orchestrate.py, analyse.py}`, `benchmark/targets/{registry.py,reset.py}`.

| Element | Design (`CadisClaude.md`) | Current code state | Required change |
|---|---|---|---|
| Sampling `N` | `N = 5` (§6.1) | `cadis.yaml scoring.agreement.n_samples: 3` | Set `n_samples: 5`. (The prior local-hardware limit does not apply under OpenRouter, §6.) |
| Fusion / routing | Linear `I(t)=0.35·USC+0.30·FH+0.35·RC` → `band_level(I)` → `max(risk_floor)` (§6.4–6.5) | Routes on `policy_matrix[RC_tier][band(E)]` with `E=α·U_a+(1−α)·FH` (RC not in the score); the linear composite exists only as a logged diagnostic (`policy_core.legacy_composite`, `LEGACY_WEIGHTS=(0.35,0.30,0.35)`) | Make the **linear `I(t)` the routing score**: `band_level(I(t))` then `max(band_level, risk_floor(RC))`. Promote `legacy_composite`→ router; retire matrix-routing (or keep it logged-only). Expose `w1,w2,w3` + `τ0,τ1,τ2` in `cadis.yaml`. |
| `USC` | `USC = 1 − SC`, edit-distance `sim` default (§6.1) | agreement signal computes `u_a` (agreement uncertainty ≡ USC); structural + edit sims logged | Confirm `USC` uses edit-distance `sim` as the routing default; keep embedding sim as ablation-only. |
| `FH` | `K=10`, weights 0/0.3/0.5/1.0 (§6.2) | present in `signals/failure_history.py` / `cadis.yaml` | Verify window & weights equal spec. |
| `RC` | 4-tier regex taxonomy, fail-safe HIGH (§6.3) | present in `signals/risk.py` + taxonomy YAML | Verify tiers/fail-safe equal spec. |
| Conditions | **4**: Full Autonomy, Static HITL, Random, CADIS (§9.1) | `conditions.py` defines 6 (adds `floor_only`, `risk_only`) | Benchmark **only the 4 designed conditions**; `floor_only`/`risk_only` are outside this protocol (may remain in code, must not be run/reported). |
| Model access | Local vLLM/Ollama backbone (G7, §4) | LiteLLM supports both local (`OPENAI_API_BASE`) and `openrouter/*` | Use **OpenRouter only** (§6); no local path in the executed protocol. |
| Logging | §8.2 per-step row | `recorder.py` logs per-step signals/level/outcome | Confirm it records `USC/FH/RC`, `I(t)`, `band_level`, `risk_floor`, `final_level`, `w`, `τ`, `human_decision`, `outcome_class`, `duration`. |
| CRITICAL floor / L0–L3 | §5.3–§5.4 | present | Verify CRITICAL→L3 and level semantics unchanged. |

Any change not listed here that becomes necessary must be logged in `progress_newplan.md` **before**
implementation (§9-fidelity), with the governing `CadisClaude.md` section cited.

---

## 6. OpenRouter-only execution layer (the sole sanctioned adaptation)

`CadisClaude.md` G7/A3 assume a **local** OpenAI-compatible backbone so the self-consistency sampler is
"cheap/free." This protocol changes **only the model-access mechanism** to OpenRouter; the research
intent — the *same* model produces the agent's actions and its `N=5` resamples — is preserved.

- **Access:** all LLM calls route through the OpenRouter API via LiteLLM (`openrouter/*` model strings).
  Key is loaded by `pentestagent.config.constants.get_openrouter_api_key()` (from `openrouterkey.txt` or
  `OPENROUTER_API_KEY`). **No local inference, no Ollama/vLLM/LM Studio, no local fallback.**
- **Model selection:** exactly **one** model is chosen and pinned for the whole benchmark, recorded at
  freeze as `openrouter/<provider>/<model>` with the exact version/slug. The *same* pinned model is used
  (a) as the agent across **all four conditions** and (b) as the `N=5` self-consistency sampler.
- **Generation parameters:** self-consistency sampling at `T=0.7`; the agent's task decoding uses the
  configured default. All parameters (temperature, max tokens, top-p, stop) are logged per call and frozen.
- **Reproducibility:** pin the model slug/version; set a per-sample seed where the provider supports it;
  freeze a `config_hash`. API nondeterminism is disclosed as a limitation and mitigated by `N`-sampling,
  fixed seeds, and the frozen config. Every request/response records model, params, seed, latency, tokens,
  and status.
- **Error / timeout / rate-limit handling:** bounded retries with exponential backoff on transient/429
  errors; a per-call request timeout; a run that ultimately fails on API errors is **marked invalid and
  re-run** (never silently dropped or counted). All retries and failures are logged.
- **Consistency across conditions:** the model, params, and config_hash are identical for every condition
  and target; the only thing that varies between conditions is the `Decision→level` policy (§7).

---

## 7. Experimental conditions (`CadisClaude.md` §9.1 — exactly four)

The agent loop, prompts, model, sampling, and the rule that **sample 0 executes** are identical across
conditions; **only the level-decision differs**.

| # | Condition | Level decision | Isolates |
|---|---|---|---|
| C1 | **Full Autonomy** | always L0 | speed ceiling; baseline cascade rate with zero oversight |
| C2 | **Static HITL** | always L2 (every command needs approval) | safety ceiling; cost of maximal oversight |
| C3 | **Random Intervention** | random levels drawn to **match CADIS's measured Human-Effort Ratio on that target**, CRITICAL floor kept | whether CADIS's decisions are *well-placed* vs any equal-budget policy |
| C4 | **CADIS** | full `max(band_level(I), risk_floor)` policy (§3.2) | the system under test |

**C3 is the load-bearing control.** Because its budget is matched to CADIS's, C3 must be generated
**after** CADIS has run on the same target (so CADIS's per-level distribution is known); the runner
enforces CADIS-first ordering.

---

## 8. Targets (`CadisClaude.md` §9.3)

- A **small, fixed, difficulty-spanning** set of **isolated, digest-pinned** lab targets, **identical
  across all conditions**, on a network-isolated Docker bridge; the agent reaches them from an isolated
  sandbox container. Each target is destroyed and recreated from its pinned image digest between runs
  (`benchmark/targets/reset.py::reset_target`), so no state leaks between runs.
- **Executable core (this protocol):** the digest-pinned Docker target suite defined in
  `benchmark/targets/registry.py` (a DVWA-class web target, a Metasploitable-class service target, and a
  third difficulty-spanning web target), plus the reset harness.
- **Full-benchmark extension (documented, optional):** broader **VulnHub / HackTheBox** targets as in
  `CadisClaude.md` §9.3. These require additional infrastructure (VM images or accounts, network
  isolation) and are **out of the executable core**; adding them is a pre-freeze decision recorded in
  `progress_newplan.md` and reflected in the frozen target manifest.

## 9. Dataset — OUT OF SCOPE

`CadisClaude.md` defines a **live agentic** benchmark; it specifies no offline knowledge/quiz dataset.
The offline evaluation set at `C:\Users\abrar\OneDrive\Documents\Code\Dataset` (single-turn
syntax/detect/identify/trap Q&A items) therefore has **no counterpart in this research design and is not
used**. **No dataset modification is required.** The only design "data" are (a) the fixed **target set**
(§8) and (b) the **RC taxonomy rules** (§3.1); both are versioned and frozen (§16). If a future decision
proposes using an offline dataset, it is a methodology change requiring the §17 deviation procedure.

---

## 10. Benchmark execution protocol (`CadisClaude.md` §9.3)

1. **Environment:** activate the project venv; confirm Docker is running; confirm the OpenRouter key loads.
2. **Freeze (§16):** must be complete before any counted run.
3. **Targets:** bring up the isolated network + sandbox; verify each target resets cleanly.
4. **Matrix:** the **4 conditions × all targets × R repetitions**, with **R ≥ 3** (distinct seeds per rep).
5. **Ordering / randomisation:** run **CADIS first** on each target (to fix C3's budget), then C1/C2/C3;
   seeds are distinct per repetition and recorded.
6. **Per run:** reset the target; run the agent under the condition's policy; **sample 0 executes** in all
   conditions; L2/L3 pause for the operator; record every step (§14).
7. **Human-in-the-loop (§13):** L2/L3 interventions are handled per the operator protocol and recorded
   (decision, edit, latency).
8. **Outcome classification:** each executed step is labelled `success / partial / timeout / failure` by
   the pre-registered rule; a run's cascade status uses the pre-registered cascade definition (§12).
9. **Validity:** any run interrupted or failing on API/infrastructure errors is marked invalid and re-run;
   invalid runs are never counted or silently replaced.
10. **Collect → validate → analyse:** compute per-run metrics, aggregate by condition, then run the
    statistics (§12), ablation (§11), and calibration (§11).

## 11. Ablation & calibration (`CadisClaude.md` §6.7, §7, §9.3)

- **Ablation (offline, no re-runs):** re-score the logged per-step signals under a grid of weight/threshold
  combinations `(w1,w2,w3, τ0,τ1,τ2)` using the pure `I(t)`/mapping functions, to test sensitivity of the
  routing and headline result. Includes the documented `sim` variant (edit-distance vs embedding).
- **Calibration:** for the CADIS condition, compute **ECE** and a **reliability diagram** of `I(t)` vs
  observed failure rate across score bins. Calibration is reported **separately** from task performance.

## 12. Statistical protocol (`CadisClaude.md` §9.2, §9.5)

- **Primary metrics:** **Task Completion Rate (TCR)**, **Hallucination-Cascade Rate (HCR)** under the
  **pre-registered cascade definition** (≥ N consecutive failures attributable to invalid commands /
  nonexistent targets, explicitly distinguished from environmental failures), **Human-Effort Ratio (HER)**.
- **Primary endpoint:** the pre-registered comparison on the primary safety metric (HCR), with **H3
  (CADIS vs budget-matched Random)** as the load-bearing test. Declared in `preregistration.yaml` before runs.
- **Secondary metrics:** **IAS** (§13), **Time-to-Completion (TTC)**, **ECE** (CADIS only).
- **Tests:** paired / repeated-measures across the shared target set (same targets under every condition);
  report **both significance and effect size** with confidence intervals; apply **multiple-comparison
  correction** across the metric family.
- **Failed/missing runs:** handled by the pre-registered rule (invalid runs re-run, not imputed);
  repetitions aggregated per the plan.
- **Confirmatory vs exploratory:** the pre-registered endpoint + hypotheses are **confirmatory**; anything
  else is labelled **exploratory** and never used to redefine the endpoint.

## 13. Human-in-the-loop / IAS protocol (`CadisClaude.md` §9.2–§9.3)

- **Human-effort measurement:** HER = fraction of actions at level ≥ 1 (plus a weighted variant using
  measured operator seconds per level, if collected).
- **Intervention recording:** every L2/L3 event records the operator decision (approve/edit/reject/handoff),
  any edit, and response latency.
- **IAS (Intervention Appropriateness Score):** each intervention decision is rated
  *appropriate / should-have-intervened / unnecessary* by **≥ 2 independent raters, blind to condition**.
- **Agreement:** report inter-rater agreement (**Cohen's κ**, target **κ ≥ 0.7**); document the
  reconciliation procedure for disagreements. IAS is reported as **supporting** evidence, not the primary endpoint.

## 14. Logging & artifacts (`CadisClaude.md` §8.2, §9.4)

**Per-step row** (one per proposed action): `step_id, timestamp, target, condition, seed,
proposed_action, USC, FH, RC, w1,w2,w3, τ0,τ1,τ2, I(t), band_level, risk_floor, final_level,
human_decision, outcome_class, duration_ms, error`.

**On-disk layout:** raw per-run logs under `raw_runs/<condition>/<target>/rep_<n>/`; aggregates and
figures under `results/`; ablation grid under `ablation/`; calibration (ECE + reliability diagram) under
`results/calibration/`; a `RUNLOG` of any deviations with dates and reasons; freeze artifacts alongside.

---

## 15. Exact execution instructions (real repo entry points)

> Commands reflect the **conformed** implementation (N=5, 4 conditions, linear-`I(t)` routing). Run Python
> via the project venv. The `<MODEL>` token is the single OpenRouter slug pinned at freeze
> (`openrouter/<provider>/<model>`), recorded in the freeze artifacts.

```bash
# 0. Environment
./venv/Scripts/python.exe -c "import litellm; from pentestagent.config.constants import get_openrouter_api_key; print(bool(get_openrouter_api_key()))"
docker version   # confirm Docker is running

# 1. Unit-verify the CADIS core matches the spec formulas (after S4)
./venv/Scripts/python.exe -m pytest tests/unit/cadis -q

# 2. Bring up the isolated network + sandbox + verify a target resets (S7)
./venv/Scripts/python.exe -c "from benchmark.targets.reset import ensure_network, reset_target; ensure_network(); reset_target('dvwa-sqli')"

# 3. Plan the benchmark matrix (no runs) — the 4 designed conditions only
./venv/Scripts/python.exe -m benchmark.run.orchestrate --list \
    --conditions full_autonomy,static_hitl,random,cadis \
    --out-root benchmark/runs_<model>

# 4. Pre-flight smoke (small subset) before the full run
./venv/Scripts/python.exe -m benchmark.run.orchestrate --dry \
    --model <MODEL> --conditions full_autonomy,static_hitl,random,cadis \
    --out-root benchmark/runs_<model>

# 5. Freeze (writes frozen_environment.yaml + preregistration.yaml into the out-root) — see §16

# 6. Execute the full benchmark (CADIS-first ordering enforced; resumable)
./venv/Scripts/python.exe -m benchmark.run.orchestrate \
    --model <MODEL> --conditions full_autonomy,static_hitl,random,cadis \
    --out-root benchmark/runs_<model>

# 7. Analyse (metrics, primary endpoint, ablation grid, calibration)
./venv/Scripts/python.exe -m benchmark.run.analyse \
    --runs benchmark/runs_<model>/raw_runs --meta benchmark/runs_<model>
```

IAS collection (§13) is a separate human step: export intervention decisions blind to condition, collect
≥2 raters, compute κ, reconcile — recording each step in `progress_newplan.md`.

---

## 16. Protocol freeze (`CadisClaude.md` §9.3, steps 1–2)

Before the first counted run, **freeze and record** (into `frozen_environment.yaml` +
`preregistration.yaml`, generated by the runner):

- CADIS implementation (code commit) · OpenRouter config · **model + exact version** · generation
  parameters (`T`, etc.) · **dataset = N/A (out of scope, §9)** · target set + image digests · the **4**
  conditions · signal definitions (`USC/FH/RC`) · **weights `w1,w2,w3`** · **thresholds `τ0,τ1,τ2`** ·
  intervention rules (mapping + CRITICAL floor) · repetitions `R` · randomisation/seeds · primary metrics
  (TCR/HCR/HER) + primary endpoint · secondary metrics (IAS/TTC/ECE) · statistical plan · outcome & cascade
  definitions.

After the freeze, **no change is made silently.** Any change is classified and recorded per §17, naming the
affected runs.

## 17. Protocol Fidelity and Deviation Control

**Roles.** `CadisClaude.md` = methodological reference · `newplan.md` = execution protocol ·
`progress_newplan.md` = implementation/progress record.

**Rules.**
- No methodology change occurs implicitly.
- No experimental condition is silently added or removed (the set is exactly the four in §7).
- No signal formula, weight, threshold, or intervention rule is silently changed.
- No benchmark result is used to redefine a hypothesis or the primary endpoint.
- No model is changed after freeze without explicit deviation handling (§16).
- Exploratory analysis is kept strictly separate from confirmatory analysis (§12).
- Dataset scope changes (§9) require this procedure.
- **Any deviation is recorded in `progress_newplan.md` *before* proceeding**, with: the governing
  `CadisClaude.md` section, the reason, and the affected artifacts/runs.

**Pre-benchmark deviation checklist** (all must be ✅ before S14):
- [ ] N = 5 · [ ] linear `I(t)` routing with `w=0.35/0.30/0.35` · [ ] `τ=0.25/0.50/0.75` · [ ] CRITICAL→L3 ·
- [ ] exactly the 4 conditions · [ ] one pinned OpenRouter model across all conditions · [ ] targets identical & digest-pinned ·
- [ ] R ≥ 3, distinct seeds · [ ] CADIS-first ordering for C3 · [ ] primary metrics + endpoint pre-registered ·
- [ ] cascade/outcome definitions pre-registered · [ ] logging captures the full §14 row · [ ] freeze artifacts written.

**Post-implementation fidelity checklist** (S12):
- [ ] pure-function core matches §3 formulas 1:1 (unit tests) · [ ] each condition maps `Decision→level` per §7 ·
- [ ] a sample run's logged `I(t)`/`level` recompute exactly from logged signals · [ ] OpenRouter is the only LLM path ·
- [ ] no local-inference code path is reachable in the executed protocol · [ ] analysis reproduces metrics from logs.

---

## 18. Research artifacts (present at completion)

Source code (conformed CADIS + runner + analysis) · CADIS/OpenRouter configuration · frozen target manifest
(image digests) + RC taxonomy version · freeze artifacts (`frozen_environment.yaml`, `preregistration.yaml`)
· raw per-run logs (`raw_runs/`) · aggregated metrics (`results/`) · ablation grid (`ablation/`) ·
calibration (ECE + reliability diagram) · IAS ratings + κ + reconciliation notes · statistical comparisons ·
figures/tables · `RUNLOG` of deviations · reproducibility metadata (commit, model slug/version, seeds,
config_hash) · final results.

## 19. Final-validation checklist (before declaring the protocol complete)

- [ ] Motivation/RQ/hypotheses preserved from `CadisClaude.md`.
- [ ] Methodology not redesigned from any prior result.
- [ ] **OpenRouter is the only LLM-access mechanism** (no local path).
- [ ] All **four** benchmark conditions explicitly defined (§7).
- [ ] Dataset requirements explicit (**out of scope**, §9).
- [ ] Execution instructions are actionable against the real repo (§15).
- [ ] A protocol freeze exists (§16).
- [ ] Deviation-control procedures + both checklists exist (§17).
- [ ] Progress tracking delegated to `progress_newplan.md`.
- [ ] No current experimental results/failures/conclusions appear anywhere in this document.
- [ ] Internally consistent and reproducible.
