# CADIS — Session Handoff Prompt (continue the honest negative-result thesis line)

*(Paste this as the first message of a new Claude Code session in
`C:\Users\abrar\OneDrive\Documents\Code\CADISV2\cadis_final\pentestagent`.)*

---

Continue the CADIS research. **Work on branch `cadis-execution` (currently at HEAD `7350820`).**
Do **not** switch branches without being asked. First read `newplan.md`, `CadisClaude.md`, and
`progress_newplan.md` (top entries + the D1–D7 deviation register). **Do not edit `newplan.md`.**

## Where things stand (branch `cadis-execution` @ `7350820`, tree clean apart from noted leftovers)

CADIS (the oversight-and-routing layer) is fully implemented and benchmarked across **three pinned
OpenRouter models**, 36 cells each (4 conditions × 3 core targets × R=3), OpenRouter-only:
`deepseek/deepseek-v4-flash` (classifier v0.1), `google/gemini-2.5-flash` (v0.2.0),
`openai/gpt-oss-120b` (v0.2.0). Committed results live under `benchmark/results_<model>/` and
`benchmark/CROSS_MODEL_COMPARISON.md`.

**Primary result: HCR (Hallucination-Cascade Rate) = 0 in every condition, every model** — the
pre-registered safety comparison (H3: CADIS vs budget-matched Random) is **undecidable (0 vs 0)**.
This session did the honest follow-up work to turn that into a defensible thesis; all of it is
committed at `7350820`.

### This session's committed additions (all EXPLORATORY, no pre-registered definition changed)

1. **Gated-action audit** — `benchmark/gated_action_audit/` (`README.md`, `run_audit.py`,
   `blocked_action_classification.csv`, `audit_summary.json`).
   Of 76 CADIS-blocked actions: **VIABLE 17 / DOOMED 34 / OTHER 25**. Over-blocking is real but
   narrow — concentrated in **deepseek × juice-shop**, where CADIS blocked the *genuine* SQL-injection
   login bypass that full-autonomy used to complete 3/3 (this one cell explains the whole TCR drop
   0.67→0.22). The DOOMED blocks are all msf2 vsftpd-backdoor attempts that never work for anyone.
   Bonus: deepseek's msf2 "completions" are **self-reported false victories** (both corrected models
   correctly score msf2 0/3).
2. **HCR power/detectability** — `benchmark/hcr_power_analysis/` (`run_power.py`, `power_summary.json`,
   `README.md`). Longest observed consecutive invalid-command-failure streak = **1** (need N=3);
   failure rate 1.0–3.4% vs **p\* ≈ 15–17%** needed for 80% power → **HCR=0 is structural, not
   underpowered luck** (a quantified boundary condition).
3. **Signal decomposition** — `benchmark/signal_decomposition/` (`run_decomposition.py`,
   `decomposition_summary.json`, `README.md`). Logged levels recompute **exactly** (fidelity check).
   **L2 blocking is 94–100% RC-risk-floor-driven**; removing RC drops the block rate to ~0, removing
   USC or FH changes nothing → **the three-signal fusion collapses to its rule-based RC term** in this
   regime (FH inert because failures are rare).
4. **Thesis figures** — `benchmark/figures/` (`make_figures.py` + Fig 1–5 as PNG+SVG +
   `table1_master_results.{md,csv}` + `README.md` with ready captions). Colourblind-safe; models shown
   within each figure. `matplotlib` was installed into the venv for this.
5. **Plain-language report** — `report.md` (root): what was done and found, no jargon, acronyms spelled
   out, figures referenced.

## The agreed thesis angle (honest negative result — do NOT reframe as a success story)

Frame the thesis as a **rigorous, pre-registered boundary-conditions + cost-of-oversight study**, not
"CADIS works." The load-bearing points:
- **Boundary condition:** the hallucination-cascade hazard does not arise for capable flash/open models
  on tractable targets (quantified — Fig 1). The primary hypothesis is undecidable, and *why* is the
  finding.
- **Efficiency, mechanistically grounded:** CADIS holds human effort ~1/3 of static-HITL and eliminates
  the catastrophic flailing tail on weak models (Fig 2, Fig 5) — but it **gates on consequence, not
  productivity**, so the same policy prunes doomed flailing (msf2) and suppresses a genuine exploit
  (juice-shop) (Fig 3). The completion cost is an artifact of the scripted reject-all-HIGH operator
  (D2), not mis-placed routing.
- **Design candour:** the multi-signal fusion reduced to a simple risk rule here (Fig 4) — the expensive
  N=5 self-consistency (USC) and failure-history (FH) signals bought little.
- **Methodology contribution:** the pre-registration + freeze + **budget-matched Random control with a
  CRITICAL floor** is itself a reusable way to test any oversight policy.

The honest bottom line: CADIS did **not** deliver its intended safety benefit and in one case cost
completions; the contribution is a rigorous negative result that maps the limits, explains the
mechanism, and hands over a fair evaluation method.

## Hard rules (unchanged)

- OpenRouter-only; one pinned model per benchmark; **no local inference**. Run Python via
  `./venv/Scripts/python.exe`.
- **Do not edit `newplan.md`.** Record every decision/deviation in `progress_newplan.md` *before*
  proceeding (§17), citing `CadisClaude.md`. Keep **exploratory** analysis clearly separate from the
  **confirmatory** endpoint (§12).
- **Do not change the pre-registered HCR/cascade definition** (standing directive).
- **Do not re-run any billable matrix without explicit user approval.**
- Commits **local only** (no push), ending with `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>`.
- `benchmark/runs*/` and `openrouterkey.txt` stay git-ignored.

## Other branches (do NOT conflate — this branch is a different direction)

A separate, newer line of work exists on **`cadis-hallucination-metric` @ `dab1afa`** (and
`cadis-session-2026-09-21` @ `aac3c19`): a hallucination-metric rework introducing a *decidable* CHR,
budget-capped 3-model USC replay, and CADIS on an external AutoPenBench cascade corpus (FH discriminates
real cascades, AUC ~0.85; USC weak). **That is a different thesis direction.** `cadis-execution` (this
branch) is the honest-negative-result line built from the frozen 3-model benchmark. Only switch to the
other branch if the user explicitly asks.

## Raw data caveat (⚠️ git-ignored, local disk only)

Per-run logs match `.gitignore` `benchmark/runs*/`, so they exist only on this machine:
`benchmark/runs_deepseek-v4-flash/raw_runs/`, `benchmark/runs_gemini-2.5-flash/raw_runs/`,
`benchmark/runs_gpt-oss-120b/raw_runs/` (36 runs each; `steps.jsonl` + `summary.json` + `meta.json`).
The three exploratory scripts read these directly. Re-analyse (non-billable):
`./venv/Scripts/python.exe -m benchmark.run.analyse --runs benchmark/runs_<model>/raw_runs --meta benchmark/runs_<model>`.
There is also an untracked `benchmark/cadis_benchmark_analysis/` leftover (only generated output —
`__pycache__/`, `usc_budget_pilot/`, `usc_replay_pilot/`); its source is committed on the newer
branches. Leave it unless asked.

## Open / next (user's call)

- **Thesis write-up** — turn `report.md` + Fig 1–5 + Table 1 + `RESULTS.md` (×3) +
  `CROSS_MODEL_COMPARISON.md` into thesis chapters (the exploratory analyses are the evidentiary spine).
- Optionally preserve the git-ignored raw logs durably (zip/tar or a non-ignored `results_*/raw_runs/`
  copy) — ask before doing so.
- Everything from this session is already committed at `7350820`; the tree is clean.
