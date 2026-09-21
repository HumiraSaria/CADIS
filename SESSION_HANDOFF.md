# CADIS — Session Handoff Prompt

*(Paste this as the first message of a new Claude Code session in
`C:\Users\abrar\OneDrive\Documents\Code\CADISV2\cadis_final\pentestagent`, branch `cadis-execution`.)*

---

Continue the CADIS research in this repo. **First read `newplan.md`, `CadisClaude.md`, and
`progress_newplan.md`** (top entries + the D1–D7 deviation register). **Do not edit `newplan.md`.**

## Current state (as of HEAD `80d7584`, branch `cadis-execution`, commits LOCAL only, tree clean)

CADIS is fully implemented and benchmarked across **three pinned models**, 36 cells each
(4 conditions × 3 core targets × R=3), OpenRouter-only:

- `openrouter/deepseek/deepseek-v4-flash` — original run (outcome-classifier **v0.1**, pre-D4)
- `openrouter/google/gemini-2.5-flash` — corrected classifier **v0.2.0**
- `openrouter/openai/gpt-oss-120b` — corrected classifier **v0.2.0**

Headline: **HCR = 0 for all three models, all conditions** (no hallucination cascades — robust
cross-model null; primary endpoint H3/H1 undecidable, 0 vs 0). HER budget-matching holds; CADIS is
the *fastest* condition on the two weaker models (gating avoids flailing). IAS collected for
**deepseek only** (Cohen's κ = 0.367, below the 0.70 target). Full detail in the results below.

## WHERE THE RESULTS ARE (committed, in git)

- **Per-model results snapshots** (each has `RESULTS.md` + `metrics_per_run.csv`,
  `metrics_by_condition_summary.csv`, `statistical_comparisons.json`,
  `calibration/reliability.{json,svg}`, `ablation/weight_threshold_grid.csv`):
  - `benchmark/results_deepseek-v4-flash/`  (also has `FINAL_REPORT.md` and `ias_review/`)
  - `benchmark/results_gemini-2.5-flash/`
  - `benchmark/results_gpt-oss-120b/`
- **Cross-model side-by-side:** `benchmark/CROSS_MODEL_COMPARISON.md` (three models)
- **Graphs (calibration reliability diagrams, SVG):**
  `benchmark/results_<model>/calibration/reliability.svg`
- **Freeze / provenance (config_hash, cadis_commit, model, targets, pre-registration):**
  `benchmark/freeze/` (deepseek), `benchmark/freeze_gemini-2.5-flash/`, `benchmark/freeze_gpt-oss-120b/`
- **IAS human data (committed):** `benchmark/results_deepseek-v4-flash/ias_review/`
  (`rater_1_completed.csv`, `rater_2_completed.csv`, `reconciled.csv`, `ias_key.csv`,
  `ias_by_condition.csv`, `inter_rater_agreement.md`)
- **Progress log / deviation register (D1–D7):** `progress_newplan.md`

## WHERE THE RAW DATA IS — ⚠️ git-ignored, LOCAL DISK ONLY (not in any commit)

The raw per-run logs match `.gitignore` rule `benchmark/runs*/`, so they exist **only on this
machine** and are **not** in the repo/commits:

- `benchmark/runs_deepseek-v4-flash/raw_runs/`  (36 runs)
- `benchmark/runs_gemini-2.5-flash/raw_runs/`  (36 runs)
- `benchmark/runs_gpt-oss-120b/raw_runs/`  (36 runs)
- `benchmark/runs_deepseek-v4-flash_v2_pilot/raw_runs/`  (6-run pilot)
- `benchmark/runs_deepseek-v4-flash_v1_provisional/raw_runs/`  (discarded first deepseek run)

Layout: `raw_runs/<condition>/<target>/rep_<n>/` with three files per run:
- **`steps.jsonl`** — **the raw data**: one JSON object per proposed action (newplan §14 row:
  `proposed_action`, `usc`/`fh`/`rc`, `i_t`, `band_level`/`risk_floor`/`final_level`,
  `human_decision`, `outcome_class`, `duration_ms`, `error`, `seed`, `timestamp`, …)
- `summary.json` — per-run summary (levels, `completed` flag)
- `meta.json` — run metadata (model, seed)

Re-analyse raw → metrics (non-billable):
`./venv/Scripts/python.exe -m benchmark.run.analyse --runs benchmark/runs_<model>/raw_runs --meta benchmark/runs_<model>`

> **These raw logs are not backed up in git.** If they matter for the thesis (appendix /
> reproducibility), preserve them: commit a non-ignored copy under `results_*/raw_runs/`, or archive
> to a `.zip`/`.tar.gz`. Ask the user before doing so.

## Hard rules (unchanged)

- **OpenRouter-only**; one pinned model per benchmark; no local inference.
- **Do not edit `newplan.md`.** Record every decision/deviation in `progress_newplan.md` **before
  acting** (newplan §17), citing the governing `CadisClaude.md` section.
- **Do not re-run any billable matrix without explicit user approval.**
- Do **not** change the pre-registered HCR/cascade definition (standing user directive).
- Run Python via `./venv/Scripts/python.exe`. Use the Write tool for files with unicode/complex quoting.
- Commits **local only** (no push), ending with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- `benchmark/runs*/` and `openrouterkey.txt` stay git-ignored.

## Open / next (all optional — user's call)

- **Thesis write-up** from `RESULTS.md` (×3) + `CROSS_MODEL_COMPARISON.md` + `FINAL_REPORT.md`.
- Optional further work (billable/human, unstarted): a 4th model; re-run deepseek under classifier
  v0.2.0 for perfect all-metric parity; collect IAS for gemini/gpt-oss; preserve the raw logs durably.

*The unit suite is 675 passing; `ruff`/`black` clean. Corrected outcome classifier
`classify_terminal_outcome` (v0.2.0) lives in `pentestagent/cadis/signals/failure_history.py`,
wired via `pentestagent/cadis/gate.py`.*
