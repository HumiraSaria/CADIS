# CADIS — Cross-Model Comparison (deepseek-v4-flash vs gemini-2.5-flash)

> Two independent, single-model CADIS benchmarks run under the **same protocol** (4 conditions ×
> 3 core targets × R=3 = 36 cells each; N=5; weights `0.35/0.30/0.35`; thresholds `0.25/0.50/0.75`;
> `max_iterations=20`; CADIS-first). **The model is the only intended variable.** This is the
> external-validity comparison for the thesis. Per-model detail:
> [`results_deepseek-v4-flash/RESULTS.md`](results_deepseek-v4-flash/RESULTS.md) ·
> [`results_gemini-2.5-flash/RESULTS.md`](results_gemini-2.5-flash/RESULTS.md).

| | deepseek | gemini |
|---|---|---|
| Model | `openrouter/deepseek/deepseek-v4-flash` | `openrouter/google/gemini-2.5-flash` |
| Freeze config_hash | `ffb01ad7…` | `f44177a9…` |
| Outcome classifier | **v0.1** (pre-D4) | **v0.2.0** (corrected, D4) |
| Cells | 36/36 | 36/36 |

> **Instrument caveat (read first).** The two runs use **different outcome classifiers**: deepseek
> predates the D4 fix (every executed command logged `success`; outcomes degenerate), gemini uses the
> corrected v0.2.0 (real `failure`/`timeout`/`partial`). So **HER, TCR, TTC are directly comparable**
> (classifier-independent), **HCR is 0 in both** (comparable in result), and **ECE is *not* directly
> comparable** (deepseek's was degenerate). A fully classifier-matched comparison would require
> re-running deepseek under v0.2.0 (a further billable matrix — not done).

## Headline metrics (mean per condition, n=9 runs each)

| Condition | HCR (ds / gm) | HER (ds / gm) | TCR (ds / gm) | mean TTC (ds / gm) |
|---|---|---|---|---|
| full_autonomy | 0.00 / 0.00 | **0.00 / 0.00** | **0.67 / 0.11** | 12.7 s / **19.0 min** |
| static_hitl | 0.00 / 0.00 | **1.00 / 1.00** | 0.00 / 0.00 | 1.2 s / 0.6 s |
| random | 0.00 / 0.00 | 0.285 / 0.353 | **0.67 / 0.11** | 8.6 s / 11.1 min |
| cadis | 0.00 / 0.00 | 0.277 / 0.356 | 0.22 / 0.00 | 10.5 s / **35.6 s** |

*(ds = deepseek-v4-flash, gm = gemini-2.5-flash.)*

## Cross-model findings

1. **Primary safety endpoint (HCR) is a robust cross-model null.** HCR = 0 for **both** models in
   **all** conditions. Crucially, gemini ran under the *corrected* classifier and still produced no
   cascades: its 36 runs logged **16 `failure` + 55 `timeout` + 57 `partial`** outcomes, but never
   ≥3 consecutive `failure`s. So "no cascades" is not an instrument artefact — **neither model
   hallucinate-cascades on these targets.** H1/H3 remain undecidable (0 vs 0) across both models.

2. **Oversight-cost structure replicates.** Both models show the same HER ordering
   (full 0 < adaptive ≈ random ≪ static 1.0) and **budget-matching holds** (random ≈ cadis:
   0.285≈0.277 deepseek, 0.353≈0.356 gemini). Gemini trips slightly more interventions
   (CADIS HER 0.356 vs 0.277) — it proposes more risky/uncertain actions.

3. **Capability gap (TCR).** deepseek completes far more objectives (full/random 0.67, cadis 0.22)
   than gemini (full/random **0.11**, cadis/static **0**). On this suite gemini is the weaker,
   flailier agent — only 2 completions in 36 runs, both on juice-shop.

4. **The striking result — TTC and where CADIS earns its keep.** Under **full autonomy**, gemini
   burns **~19 min/run** (individual msf2 runs hit 20, 60, **90 min**) because it repeatedly issues
   the vsftpd-backdoor `nc … 21` command with no `-w` flag — each blocks and is killed at the 300 s
   command cap (`timeout`). **CADIS gating cuts that to ~36 s** (and static-HITL to 0.6 s) by
   rejecting the HIGH-risk-and-useless backdoor attempts before they run. deepseek, which didn't
   flail, shows no such gap (~9–13 s across conditions). **Adaptive oversight's benefit is larger for
   the less-reliable model:** CADIS prevented gemini from wasting ~30× the wall-clock on
   risky-and-fruitless actions.

## Thesis takeaways

- **The cascade-safety claim is neither confirmed nor refuted for either model** — the hazard simply
  does not occur in this regime (competent-enough models, tractable single-service/web targets),
  now shown with a *validated* instrument on gemini. That is a stronger, cross-model version of the
  single-model null.
- **CADIS's demonstrated value is efficiency + appropriate restraint, and it scales with agent
  unreliability:** it holds human effort well below static HITL (both models) and, for the flailier
  agent (gemini), avoids catastrophic wall-clock waste by gating useless-risky actions — a benefit
  invisible on the more capable model. This is the comparison's headline contribution.
- **Trade-off stated honestly:** CADIS's gating also lowers completion (gemini cadis TCR 0 vs full
  0.11; deepseek cadis 0.22 vs full 0.67) — it blocks exploitation steps, useless *and* useful
  alike. Oversight cost is real; in this regime there is no cascade benefit to offset it.

## Calibration (CADIS only)

- deepseek ECE 0.197 (112–173 steps) — **degenerate** (0 observed failures under v0.1; not
  informative).
- gemini ECE **0.170** over 112 CADIS steps — **meaningful** for the first time (real failures feed
  it), though still moderate. Reported per model; not cross-compared due to the instrument difference.

## Limitations (carry into the thesis)

- Two models is a start, not a broad sweep; both are cheap/fast flash-class models.
- Instrument mismatch (deepseek v0.1 vs gemini v0.2.0) — HER/TCR/TTC comparable, HCR both 0, ECE not.
- Small target set (n=3) → paired tests underpowered (Wilcoxon floor p=0.25); HCR 0-vs-0 is degenerate.
- IAS (human-rated) exists for **deepseek only**; gemini IAS would need a separate human pass.
- gemini's msf2 TTC is inflated by timeout-capped flailing — a *real* behaviour, but note the 300 s
  command cap sets its scale.

## Provenance
Freezes: [`freeze/`](freeze) (deepseek) · [`freeze_gemini-2.5-flash/`](freeze_gemini-2.5-flash).
Raw runs are git-ignored (`runs_*/`); committed metrics under each `results_*/`. Deviations D1–D6 in
[`../progress_newplan.md`](../progress_newplan.md). `newplan.md` unedited.
