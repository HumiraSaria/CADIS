# CADIS Clean-Slate Implementation — Progress Log (`progress_newplan.md`)

> **What this is.** The living development log for the CADIS research executed under
> [`newplan.md`](newplan.md). This is the **only** place progress, decisions, issues, resolutions,
> deviations, and validation are recorded. `newplan.md` stays clean and forward-looking — do not add
> progress or results to it.
>
> **Separate from** the repo's older `progress.md` (a different effort's journal), which is left
> untouched.
>
> **Entry template** (append newest-first, one per meaningful step):
> ```
> ### YYYY-MM-DD HH:MM — [Stage Sx] <task>
> - Completed: <what was done>
> - Files/components changed: <paths>
> - Decisions: <decision + the CadisClaude.md section that governs it>
> - Deviations/ambiguities discovered: <none | describe>
> - Resolution: <how resolved; if a methodology deviation, note it was logged BEFORE proceeding (newplan §17)>
> - Tests/checks performed: <commands + outcomes>
> - Current status: <stage state>
> - Next planned step: <next>
> ```

---

## Deviation register (quick index)

Record every post-freeze or methodology deviation here (summary), with a full entry below.

| ID | Date | Deviation | Governing spec section | Affected runs/artifacts | Status |
|----|------|-----------|------------------------|-------------------------|--------|
| D1 | 2026-09-10 | OpenRouter-only LLM access replaces the local vLLM/Ollama backbone; the *same* pinned `openrouter/*` model is both the agent and the `N=5` self-consistency sampler. No local inference / no fallback. | CadisClaude.md G7, A3 (§3, §4, §10); **sanctioned by** newplan.md §6 | All LLM calls; freeze artifacts; S5 onward | Logged (pre-implementation) |
| D2 | 2026-09-10 | L2/L3 blocking interventions are resolved by a **deterministic, pre-registered scripted operator policy** instead of live human operators, so the 4×3×R matrix is reproducible/tractable. Humans still perform the **blind IAS rating** (§13) on the logged CADIS routing decisions. HER is measured count-based (fraction of actions at level ≥1), unaffected by the operator model. | CadisClaude.md §9.2–§9.3 (step 5), §5.3; newplan.md §7, §13 | Conditions C2 (static_hitl) & C4 (cadis); S8, S14; HER; IAS | Logged (pre-implementation, before S8) |

---

## Session log (newest first)

### 2026-09-10 — [Stage S5] OpenRouter execution layer: key loader + N=5/T=0.7 self-consistency sampler (live smoke deferred)

- **Completed:** built the OpenRouter-only execution layer (newplan.md §6), except the
  live smoke call (deferred per user — option "a": code + mocked tests now).
  - `pentestagent/config/constants.py` — added `get_openrouter_api_key()`. Resolution
    order: `OPENROUTER_API_KEY` env var (loaded from `.env` via the existing
    `load_dotenv()`) first, then a git-ignored `openrouterkey.txt` fallback (CWD, then
    project root), which is exported into `os.environ` so LiteLLM picks it up. **No key
    is hardcoded or logged** (user directive: use `.env`, don't hardcode).
  - `pentestagent/cadis/sampler.py` — `SelfConsistencySampler`: queries the pinned
    OpenRouter model N times on identical context at **T=0.7 set explicitly** (bypasses
    the "claude"/"anthropic" temperature-drop in `llm/llm.py`), returns N command
    strings via `canonical_action()` (tool-call name + sorted-JSON args, or text) that
    feed `agreement.usc()`. Enforces **OpenRouter-only** (`model` must start with
    `openrouter/`; no local path). Per-call `CallLog` (model, params, seed, latency,
    tokens, status, attempts); bounded exponential backoff on 429/transient; per-call
    `asyncio.wait_for` timeout; a batch that fails on API errors is `ok=False` so the run
    can be marked invalid and re-run (never silently dropped). `completion_fn` is
    injectable so unit tests run with no live API.
- **Files/components changed:** modified `pentestagent/config/constants.py`
  (+`get_openrouter_api_key`, +`pathlib.Path` import); new `pentestagent/cadis/sampler.py`;
  new tests `tests/unit/cadis/test_sampler.py`, `tests/unit/config/test_openrouter_key.py`.
  No other source touched. `newplan.md` untouched.
- **Decisions (with governing section):**
  1. Key source = `.env`/`OPENROUTER_API_KEY` (user directive), with `openrouterkey.txt`
     as the newplan.md §6 fallback. Satisfies §6's `OPENROUTER_API_KEY` path exactly.
  2. Sampler sets `temperature` explicitly and calls `litellm.acompletion` directly
     rather than via `LLM.generate`, so `openrouter/anthropic/*` still samples at T=0.7
     (CadisClaude.md §6.1; newplan.md §6 — the temperature-drop caveat noted at S1).
  3. OpenRouter-only hard guard on the model string enforces "no local path / no
     fallback" (newplan.md §6; §17 fidelity item).
- **Deviations/ambiguities discovered:** `OPENROUTER_API_KEY` is **not present in `.env`**
  (keys there: OPENAI/ANTHROPIC/GEMINI/TAVILY/PENTESTAGENT_MODEL). The loader currently
  resolves the key from the git-ignored `openrouterkey.txt` fallback (verified present,
  len 73) — so a live call is technically possible, but the live smoke was **deferred at
  user request**. No methodology deviation.
- **Resolution:** n/a. `.gitignore` updated earlier to exclude `openrouterkey.txt` so the
  secret can never be committed; the key value is never printed (tests assert on length only).
- **Tests/checks performed:**
  - `pytest tests/unit/cadis/test_sampler.py tests/unit/config/test_openrouter_key.py -q`
    → **18 passed** (canonical extraction, OpenRouter-only guard, identical-samples⇒USC=0,
    explicit-temperature + seed propagation, transient retry, non-transient error⇒not-ok,
    transient classification; env-priority / strip / file-fallback for the loader).
  - `pytest tests/unit/cadis tests/unit/config -q` → **136 passed** (no regressions).
  - `ruff check` clean; `black` clean.
  - Import smoke: `get_openrouter_api_key()` resolves; `SelfConsistencySampler('gpt-4o')`
    raises (OpenRouter-only guard). **No live API call made.**
- **Current status:** **S5 code complete; gate PARTIALLY met.** Mocked-path verified; the
  live-smoke portion of the gate is **deferred** until the user adds `OPENROUTER_API_KEY`
  to `.env` (or authorises using the `openrouterkey.txt` fallback) and a model is chosen.
  Model pin stays `null` in `cadis.yaml` until freeze (S13).
- **Next planned step:** **S6 — integrate the CADIS gate at the action seam.** Add an
  optional `action_gate` callback to `BaseAgent` (default `None` = unchanged production);
  invoke it per proposed action in `_run_loop` between `llm.generate(...)` and
  `_execute_tools(...)`. Wire `cadis/operator.py` (L1 notify via `interface/notifier.py`;
  L2/L3 via scripted operator in benchmark / `WAITING_INPUT` interactive). This modifies
  shared production code (`base_agent.py`) — confirm approach with user before editing.

---

### 2026-09-10 — [Stage S4] CADIS core implemented (signals + pure fusion/mapping core + config); unit tests green

- **Completed:** built the CADIS package from scratch, directly into the conformed shape (N=5,
  linear-`I(t)` routing), transcribing `CadisClaude.md` §6 1:1.
  - `policy_core.py` — pure functions `compute_composite` (`I=w1·USC+w2·FH+w3·RC`), `band_level`
    (τ=0.25/0.50/0.75), `risk_floor` (LOW/MED/HIGH/CRIT→0/1/2/3), `map_to_level`
    (`max(band_level, risk_floor)`) + `validate_weights`/`validate_thresholds`. Shared tier
    constants (`RC_LOW..RC_CRITICAL`, `RISK_SCORES`) so risk.py and the core never drift.
  - `signals/agreement.py` — USC: pure Levenshtein, `normalized_edit_similarity` (edit default),
    `self_consistency` (mean pairwise over unordered pairs; N<2⇒SC=1.0), `usc=1−SC`;
    `embedding_similarity` present but ablation-only (raises `NotImplementedError`).
  - `signals/failure_history.py` — FH: `OUTCOME_WEIGHTS` (0.0/0.3/0.5/1.0), `failure_history`
    (mean over last K), `classify_outcome` (pre-registered success/partial/timeout/failure rule),
    `FailureHistoryWindow` live deque helper.
  - `signals/risk.py` + `risk_taxonomy.yaml` — RC: regex-per-tier taxonomy (reviewed vs MITRE
    ATT&CK), highest-tier-wins precedence, fail-safe HIGH on unmatched with gap logging.
  - `config.py` + `cadis.yaml` — all knobs exposed (w, τ, N=5, T=0.7, sim, K=10, taxonomy path,
    model slug=null until freeze); `load_config` validates.
  - `engine.py` — `CadisEngine.score()` scaffold fusing signals→`I(t)`→level into a `ScoreResult`
    with every §14 field. Performs no LLM I/O (sampler wired at S5); USC defaults to 0.0 with
    `n_samples=0` when samples not yet provided.
- **Files/components changed (new):** `pentestagent/cadis/{__init__.py, policy_core.py, config.py,
  cadis.yaml, engine.py, risk_taxonomy.yaml, signals/{__init__.py, agreement.py,
  failure_history.py, risk.py}}`; `tests/unit/cadis/{__init__.py, test_policy_core.py,
  test_agreement.py, test_failure_history.py, test_risk.py, test_engine.py}`. No existing source
  modified. `newplan.md` untouched.
- **Decisions (with governing section):**
  1. Pure-function core with no I/O, so logs re-score offline for ablation (CadisClaude.md §6.7;
     newplan.md §3.4). Design contract met: signal computation and fusion/mapping are separable.
  2. `risk_floor` uses a monotone `>=` ladder against canonical tier scores — robust to float RC
     values, never returns below the correct floor (CadisClaude.md §6.5).
  3. RC precedence = highest matching tier wins (consequence caps trust) (CadisClaude.md §5.4, §6.3).
  4. Initial RC taxonomy authored per the S3 defaults; `risk_taxonomy.yaml` carries `version: 0.1.0`
     and is a frozen artifact at S13 (CadisClaude.md §6.3; newplan.md §16).
- **Deviations/ambiguities discovered:** none new. (RC regexes/outcome classifier are the S3
  pre-registered defaults, already recorded; no methodology change.)
- **Resolution:** n/a — no deviation. B904 lint (raise-from) cleaned in the two signal modules.
- **Tests/checks performed:**
  - `./venv/Scripts/python.exe -m pytest tests/unit/cadis -q` → **58 passed**. Includes the §6.6
    worked example end-to-end: `USC=0.40, FH=0.25, RC=0.66 ⇒ I=0.446, band=1, floor=2, level=2`;
    the FH worked example `2 fail + 1 timeout + 7 success / 10 = 0.25`; CRITICAL⇒L3 hard floor;
    risk-raises-never-lowers; fail-safe HIGH + gap logging; highest-tier precedence.
  - `ruff check` → all checks passed; `black --check` → 14 files clean.
  - `pytest --collect-only` across the whole suite → **688 tests collected**, no import regressions.
- **Current status:** **S4 complete — gate passed** (pure-function core matches §3/§6 1:1; tests green).
- **Next planned step:** **S5 — OpenRouter execution layer.** Add `get_openrouter_api_key()` to
  `pentestagent/config/constants.py` reading `OPENROUTER_API_KEY` from the environment (loaded from
  `.env` via the existing `load_dotenv()` — user preference; satisfies newplan.md §6's env path).
  Build the N=5 / T=0.7 self-consistency sampler that sets `temperature` explicitly (bypassing the
  "claude"/"anthropic" temperature-drop in `llm/llm.py`), with per-call logging + bounded backoff.
  **Note:** `OPENROUTER_API_KEY` is **not yet present in `.env`** (current keys: OPENAI/ANTHROPIC/
  GEMINI/TAVILY/PENTESTAGENT_MODEL) — the user needs to add it before the S5 smoke call.

---

### 2026-09-10 — [Stage S0→S3] Execution plan authored & recorded; spec internalised; conformity audit; change list

- **Completed:**
  - Authored the **execution-phase plan** (integration of CADIS with the framework → benchmarking),
    strictly following `newplan.md` and grounded in the authoritative `CadisClaude.md` (now present
    locally) plus a direct read of the real codebase. Plan recorded here in full (below) and mirrored
    at `C:\Users\abrar\.claude\plans\as-per-newplan-md-prepare-glimmering-castle.md`.
  - **S1 (spec internalisation):** read `CadisClaude.md` §1–§14 and reconciled with `newplan.md` §3.
    Confirmed the operative mechanism 1:1 — three signals `USC/FH/RC`, composite
    `I(t)=0.35·USC+0.30·FH+0.35·RC`, `band_level` thresholds `τ=0.25/0.50/0.75`, `risk_floor`, the
    canonical `max(band_level, risk_floor)` mapping, hard `CRITICAL⇒L3`, and the §6.6 worked example
    (`SC=0.60→USC=0.40`, `FH=0.25`, `RC=0.66` ⇒ `I=0.446`, `band=1`, `floor=2`, `level=2`).
  - **S2 (conformity audit):** searched the working directory — **no CADIS or benchmark code exists**
    (`pentestagent/cadis/`, `benchmark/`, `tests/unit/cadis/` all absent; no reference copy in-repo).
    Conclusion: `newplan.md` §5's "current code state" column is an *intended target state*, not
    present reality. Audit result for every §3/§6 element = **to-build (build-from-scratch, directly
    into the conformed shape)**: N=5, linear-`I(t)` routing, exactly the 4 conditions, OpenRouter-only.
  - **S3 (change/build list):** turned the audit into the concrete build list in the plan below; the
    items `CadisClaude.md` leaves open are fixed as pre-registered defaults (RC regex taxonomy,
    outcome classifier, cascade N=3, 3-target digest-pinned set) — each citing its `CadisClaude.md`
    section, to be frozen at S13.
  - Verified real integration surfaces: action seam between `response.tool_calls` and
    `_execute_tools()` in `pentestagent/agents/base_agent.py::_run_loop`; `ExecutionResult` in
    `pentestagent/tools/executor.py` as the outcome source; `LLM.generate` in `pentestagent/llm/llm.py`
    (LiteLLM path, drops `temperature` for "claude"/"anthropic" model names — sampler must set it
    explicitly); `get_openrouter_api_key()` is **absent** from `pentestagent/config/constants.py`
    (only `get_openai_api_base()` exists) and must be added at S5.
- **Files/components changed:** `progress_newplan.md` (this entry + deviation register D1/D2).
  **No source code changed.** `newplan.md` untouched.
- **Decisions (with governing section):**
  1. Build CADIS from scratch directly into the conformed shape (CadisClaude.md §4–§6; newplan.md §5).
  2. `CadisClaude.md` is the authoritative methodology; where it and `newplan.md` differ, CadisClaude
     governs (newplan.md preamble). **All git commits stay local — no push to origin** (user directive).
  3. **D1** — OpenRouter-only access (CadisClaude.md G7/A3 → newplan.md §6). Logged before S5.
  4. **D2** — scripted operator policy for L2/L3 (CadisClaude.md §9.2–§9.3/§5.3; newplan.md §13).
     Logged before S8.
  5. Pre-registered defaults set at S3, to be frozen at S13: RC 4-tier regex taxonomy w/ fail-safe
     HIGH (§6.3); outcome classifier success/partial/timeout/failure (§6.2, Q1); cascade **N=3**
     consecutive invalid-command/nonexistent-target failures distinguished from environmental (§9, Q2);
     target core = 3 digest-pinned Docker targets (DVWA-class, Metasploitable-class, third web),
     VulnHub/HTB out of executable core (§9.3; newplan.md §8).
- **Deviations/ambiguities discovered:**
  - `newplan.md` §5 describes CADIS code as already existing; it does not. Reconciled by treating §5
    as target-state (recorded above, not a methodology change).
  - `CadisClaude.md` assumes a local backbone (G7/A3) — superseded by OpenRouter via newplan.md §6 (D1).
  - `newplan.md` §13 implies live human operators for L2/L3 — resolved to a scripted operator (D2).
- **Resolution:** D1 and D2 recorded in the deviation register **before** proceeding to the stages
  they affect (S5 and S8 respectively), per newplan.md §17. Target/RC/cascade/outcome specifics are
  design decisions scheduled into S3/S13 (freeze + pre-registration), not silent changes.
- **Tests/checks performed:** repository inspection only (no code yet). Confirmed absence of
  `pentestagent/cadis/`, `benchmark/`, `tests/unit/cadis/`; confirmed `CadisClaude.md` and
  `openrouterkey.txt` present in the working directory; read agent loop, executor, LLM layer, config,
  settings, pyproject (pytest `asyncio_mode=auto`, `testpaths=["tests"]`).
- **Current status:** **S0 complete; S1–S3 complete (recorded).** Execution plan is frozen as the
  build roadmap. No gate blocks passed for build stages yet.
- **Next planned step:** **S4 — implement CADIS core** (`pentestagent/cadis/policy_core.py` pure
  functions + `signals/{agreement,failure_history,risk}.py` + `config.py`/`cadis.yaml` +
  `risk_taxonomy.yaml`), with `tests/unit/cadis/` transcribing §6 formulas 1:1 incl. the §6.6 worked
  example. Gate: `pytest tests/unit/cadis -q` green.

---

#### Recorded execution plan (Integration → Benchmark)

> Full plan as approved this session. Mirror: `~/.claude/plans/as-per-newplan-md-prepare-glimmering-castle.md`.
> `newplan.md` is the execution protocol (never edited); `CadisClaude.md` is the authoritative
> methodology; this log is the sole progress record.

**Non-negotiable constraints** (newplan.md §17 / CadisClaude.md): pure-function fusion/mapping core
(no I/O, deterministic, re-scorable offline); `N=5`, `T=0.7`; `I(t)=0.35·USC+0.30·FH+0.35·RC`;
`τ=0.25/0.50/0.75`; `CRITICAL⇒L3` hard floor; exactly **4 conditions** (full_autonomy=L0,
static_hitl=L2, random=budget-matched to CADIS HER w/ CRITICAL floor & CADIS-first, cadis=full
policy) — `floor_only`/`risk_only` never run/reported; **OpenRouter-only**, one pinned model, no
local path; host framework **identical across all 4 conditions** (C7 — only `Decision→level` varies);
every deviation logged before proceeding.

**Stages (gated — one log entry + gate outcome each):**

- **S1 Spec internalisation** — reconcile CadisClaude §4–§9 with newplan §3. *Gate:* signal/fusion/
  mapping understood. **(done — above)**
- **S2 Conformity audit** — classify every §3/§6 element. Result: all to-build. *Gate:* every element
  classified. **(done — above)**
- **S3 Change/build list** — concrete build list, each citing a CadisClaude section; open items fixed
  as pre-registered defaults (RC taxonomy, outcome classifier, cascade N=3, 3 targets). *Gate:* each
  change cites a section. **(done — above)**
- **S4 Implement CADIS core** — `pentestagent/cadis/`: `policy_core.py` (pure `compute_composite`,
  `band_level`, `risk_floor`, `map_to_level`); `signals/agreement.py` (USC, N-sample, edit-distance
  `sim` default, embedding ablation-only), `signals/failure_history.py` (K=10, weights 0/0.3/0.5/1.0),
  `signals/risk.py` (regex taxonomy + fail-safe HIGH, loads `risk_taxonomy.yaml`); `config.py`+
  `cadis.yaml` (exposes w, τ, N, K, T, sim, model); `engine.py` (scaffold). `tests/unit/cadis/`
  transcribe §6 1:1 incl. §6.6 worked example. *Gate:* `pytest tests/unit/cadis -q` green.
- **S5 Configure OpenRouter** — add `get_openrouter_api_key()` to `config/constants.py` (reads
  `openrouterkey.txt` then `OPENROUTER_API_KEY`; exports into `os.environ`). Sampler issues N=5 at
  T=0.7 on identical context, setting `temperature` explicitly to bypass the anthropic-temperature
  drop in `llm.py`. Per-call logging (model, params, seed, latency, tokens, status); bounded backoff
  on 429/transient; per-call timeout; API-failed runs marked invalid. *Gate:* smoke call succeeds.
- **S6 Integrate at action seam** — add optional `action_gate` callback to `BaseAgent` (default None
  = unchanged production); invoke per proposed action in `_run_loop` between proposal and
  `_execute_tools`. Benchmark driver binds the gate to the active condition's policy (same gated loop
  all 4 conditions → C7). `cadis/operator.py`: L1 notify via `interface/notifier.py`; L2/L3 via
  scripted operator (benchmark) or `WAITING_INPUT` (interactive). Sample 0 always executes. *Gate:*
  one run executes each of L0–L3.
- **S7 Targets** — `benchmark/targets/{registry.py,reset.py}`: `ensure_network()` (isolated bridge +
  sandbox container), `reset_target(name)` (destroy+recreate from pinned image digest). 3 targets;
  VulnHub/HTB out of core. *Gate:* `reset_target('dvwa-sqli')` restores cleanly.
- **S8 Conditions** — `cadis/conditions.py`: the 4 conditions mapping `Decision→level`; random
  budget-matched to CADIS HER (CADIS-first). Scripted operator in `operator.py` (per D2). *Gate:* each
  condition maps per §7.
- **S9 Logging** — `cadis/recorder.py`: one row/action with the full §14 field set; on-disk
  `raw_runs/<condition>/<target>/rep_<n>/`. *Gate:* a run writes every §14 field.
- **S10 Benchmark runner** — `benchmark/run/{driver.py,orchestrate.py,analyse.py}`: orchestrate plans
  4×3×R≥3 (distinct seeds), CADIS-first, resumable, `--list`/`--dry`/full; driver runs one
  (condition,target,rep). *Gate:* dry run plans the exact matrix.
- **S11 Analysis** — TCR, HCR (pre-registered cascade), HER; IAS export, TTC, ECE (CADIS only); paired
  stats + effect size + CI + multiple-comparison correction; ablation = offline re-score over
  `(w,τ,sim)` grid via pure functions; calibration = ECE + reliability diagram. *Gate:* reproduces
  metrics from a sample run.
- **S12 Fidelity verification** — run newplan §17 post-implementation checklist. *Gate:* all pass.
- **S13 Freeze + pre-register** — write `frozen_environment.yaml` + `preregistration.yaml` (pinned
  model+version, params, target digests, 4 conditions, signal defs, w, τ, CRITICAL floor, R, seeds,
  primary metrics TCR/HCR/HER + endpoint H3 CADIS-vs-Random on HCR, secondary IAS/TTC/ECE, stat plan,
  cascade + outcome defs); complete §17 pre-benchmark checklist. *Gate:* freeze artifacts written.
- **S14 Execute benchmark** — full matrix; reset each run; CADIS-first; sample 0 executes; scripted
  operator resolves L2/L3; record every step; API/infra-failed runs invalid → re-run. *Gate:* all
  planned runs valid or explicitly re-run.
- **S15 Analyse & report** — per-run→by-condition metrics; stats (H1–H3 + effects/CI + correction),
  ablation, calibration; IAS export blind → ≥2 raters → Cohen's κ (≥0.7) → reconcile; emit `results/`
  + figures + `RUNLOG`. *Gate:* primary/secondary metrics computed per §12.

**Critical files.** New `pentestagent/cadis/` (`policy_core.py`, `config.py`, `cadis.yaml`,
`engine.py`, `recorder.py`, `operator.py`, `conditions.py`, `risk_taxonomy.yaml`,
`signals/{agreement,failure_history,risk}.py`); new `benchmark/` (`run/{driver,orchestrate,analyse}.py`,
`targets/{registry,reset}.py`, generated `raw_runs/`, `results/`, `ablation/`, freeze artifacts); new
`tests/unit/cadis/`. Surgical edits: `config/constants.py` (+`get_openrouter_api_key()`),
`agents/base_agent.py` (optional `action_gate` hook, default off). Reused as-is:
`tools/executor.py`, `runtime/docker_runtime.py`, `interface/notifier.py`, `WAITING_INPUT`, `llm/llm.py`.
Never edited: `newplan.md`.

---

### 2026-09-10 — [Stage S0] Protocol authored; implementation not started
- Completed: `newplan.md` created as the forward-looking execution protocol from `CadisClaude.md`,
  adapted for OpenRouter-only access; this log initialised.
- Files/components changed: `newplan.md` (new), `progress_newplan.md` (new). **No source code changed.**
- Decisions: (1) live-agentic benchmark only — offline `Dataset/` is out of scope (no counterpart in
  `CadisClaude.md`); (2) fixed digest-pinned isolated Docker target core now, VulnHub/HTB documented as
  an optional extension; (3) this log is the sole progress record.
- Deviations/ambiguities discovered: none (protocol phase).
- Tests/checks performed: none yet.
- Current status: **S0 complete — awaiting go-ahead to begin S1/S2 (spec internalisation + conformity audit).**
- Next planned step: S2 — audit the current codebase against `CadisClaude.md` §3–§9 and populate the
  conformity change list (the candidate changes are pre-identified in `newplan.md` §5: N=5, linear-`I(t)`
  routing, restrict to the 4 conditions, OpenRouter-only, logging fields).
