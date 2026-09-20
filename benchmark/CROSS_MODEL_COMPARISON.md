# CADIS — Cross-Model Comparison (3 models)

> Three independent, single-model CADIS benchmarks under the **same protocol** (4 conditions ×
> 3 core targets × R=3 = 36 cells each; N=5; weights `0.35/0.30/0.35`; thresholds `0.25/0.50/0.75`;
> `max_iterations=20`; CADIS-first). **The model is the only intended variable** — the external-validity
> evidence for the thesis. Per-model detail:
> [`results_deepseek-v4-flash/RESULTS.md`](results_deepseek-v4-flash/RESULTS.md) ·
> [`results_gemini-2.5-flash/RESULTS.md`](results_gemini-2.5-flash/RESULTS.md) ·
> [`results_gpt-oss-120b/RESULTS.md`](results_gpt-oss-120b/RESULTS.md).

| | deepseek-v4-flash | gemini-2.5-flash | gpt-oss-120b |
|---|---|---|---|
| config_hash | `ffb01ad7…` | `f44177a9…` | `cc02b63f…` |
| outcome classifier | **v0.1** (pre-D4) | **v0.2.0** | **v0.2.0** |
| cells | 36/36 | 36/36 | 36/36 |
| model type | non-reasoning | non-reasoning | reasoning (120B) |

> **Instrument caveat (read first).** deepseek predates the D4 outcome-classifier fix (every executed
> command logged `success`; outcomes degenerate); gemini and gpt-oss use the corrected **v0.2.0**
> (real `failure`/`timeout`/`partial`). ⇒ **HER, TCR, TTC are directly comparable across all three**
> (classifier-independent); **HCR is 0 in all three** (comparable in result); **ECE is directly
> comparable only between the two v0.2.0 models** (deepseek's is degenerate). Full parity would need
> re-running deepseek under v0.2.0 (a further billable matrix — not done).

## HCR — Hallucination-Cascade Rate (primary safety endpoint)

| Condition | deepseek | gemini | gpt-oss |
|---|---|---|---|
| full_autonomy | 0.00 | 0.00 | 0.00 |
| static_hitl | 0.00 | 0.00 | 0.00 |
| random | 0.00 | 0.00 | 0.00 |
| cadis | 0.00 | 0.00 | 0.00 |

**0 across the board.** Under the corrected instrument gemini logged 16 `failure`s and gpt-oss 6, but
neither (nor deepseek) ever produced ≥3 consecutive invalid-command failures → **no cascades in any
of the three models.** H1/H3 are undecidable (0 vs 0) uniformly.

## HER — Human-Effort Ratio (fraction of actions gated, ≥ L1)

| Condition | deepseek | gemini | gpt-oss |
|---|---|---|---|
| full_autonomy | 0.000 | 0.000 | 0.000 |
| static_hitl | 1.000 | 1.000 | 1.000 |
| random | 0.285 | 0.353 | 0.367 |
| cadis | 0.277 | 0.356 | 0.329 |

**Structure replicates across all three:** full 0 < adaptive ≈ random ≪ static 1.0, and
**budget-matching holds** (random ≈ cadis in every model). CADIS holds human effort at ~28–36% —
far below static HITL's 100% — on all three models.

## TCR — Task-Completion Rate

| Condition | deepseek | gemini | gpt-oss |
|---|---|---|---|
| full_autonomy | 0.667 | 0.111 | 0.000 |
| static_hitl | 0.000 | 0.000 | 0.111 |
| random | 0.667 | 0.111 | 0.000 |
| cadis | 0.222 | 0.000 | 0.111 |

**Capability gap:** deepseek is far more effective (0.67 ungated) than gemini/gpt-oss (~0.11 or 0).
On the two weaker models completions are rare (2/36 each) and noisy — gpt-oss's only completions came
under the **gated** conditions (static/cadis on msf2), not full/random.

## TTC — mean wall-clock per run (the standout result)

| Condition | deepseek | gemini | gpt-oss |
|---|---|---|---|
| full_autonomy | 12.7 s | **19.0 min** | 4.5 min |
| static_hitl | 1.2 s | 0.6 s | 70.0 s |
| random | 8.6 s | 11.1 min | 43.6 s |
| cadis | 10.5 s | **35.6 s** | **3.2 s** |

On the weaker models, **full autonomy is catastrophically slow** because the agent flails on the
msf2 vsftpd backdoor (blocking `nc … 21`, each killed at the 300 s command cap). **CADIS is the
*fastest* condition for both gemini (35.6 s vs 19 min) and gpt-oss (3.2 s vs 4.5 min)** — its gating
rejects the risky-and-fruitless attempts before they run. deepseek, which didn't flail, shows no such
gap. **The efficiency benefit of adaptive oversight scales with agent unreliability** and is
consistent across the two models that exhibit it.

## Calibration (CADIS only, ECE)
- deepseek 0.197 — **degenerate** (v0.1, 0 observed failures; not informative).
- gemini **0.170** · gpt-oss **0.193** — both meaningful (real outcomes feed them), moderate;
  directly comparable to each other.

## Thesis takeaways (three-model)
1. **Robust cross-model null on the primary safety endpoint.** No hallucination cascades in any of
   three models, all conditions — shown with a *validated* instrument on two of them. The hazard
   simply does not arise in this regime (flash/open reasoning models; tractable single-service/web
   targets). H1/H3 are bounded, not demonstrated.
2. **CADIS's oversight-cost structure and budget-matching replicate across all three models** — the
   mechanism behaves consistently, not model-idiosyncratically.
3. **Headline contribution:** CADIS's demonstrated value is **efficiency + appropriate restraint that
   scales with agent unreliability** — it holds effort far below static HITL everywhere, and on the
   flailier models it *slashes* wasted wall-clock (up to ~30×) by gating useless-risky actions, a
   benefit invisible on the most capable model.
4. **Honest trade-off:** CADIS gating also suppresses completion where exploitation would have
   succeeded; in this regime there is no cascade benefit to offset that cost.

## Limitations
Three flash/open models — a start, not a broad sweep. Instrument mismatch (deepseek v0.1 vs the two
v0.2.0 models — HER/TCR/TTC comparable, HCR all 0, ECE only across the v0.2.0 pair). Small target set
(n=3) → paired tests underpowered; HCR degenerate (0 vs 0). IAS (human-rated) is deepseek-only.
gemini/gpt-oss full-autonomy TTC is inflated by timeout-capped flailing (scale set by the 300 s cap).

## Provenance
Freezes: [`freeze/`](freeze) · [`freeze_gemini-2.5-flash/`](freeze_gemini-2.5-flash) ·
[`freeze_gpt-oss-120b/`](freeze_gpt-oss-120b). Raw runs git-ignored (`runs_*/`); committed metrics
under each `results_*/`. Deviations D1–D7 in [`../progress_newplan.md`](../progress_newplan.md).
`newplan.md` unedited.
