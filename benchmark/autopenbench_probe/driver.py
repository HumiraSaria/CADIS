"""AutoPenBench probe driver + CLI (design doc §4/§6; deviation D8).

Runs the isolated probe: full_autonomy ONLY, N=5 USC sampler OFF (L0 ignores USC), R=2, with the
flag-artifact oracle for TCR and per-run OpenRouter cost metering. Reuses the frozen scoring core
(engine/gate/recorder/policy) verbatim; only the probe target provisioning + oracle + metering are
new.

Modes (``python -m benchmark.autopenbench_probe.driver ...``):
  --list            print the 4-cell plan and exit (NO LLM, NO Docker)
  --dry             plan + environment/image/Docker checks (NO LLM calls)
  --go --model M    EXECUTE the probe (BILLABLE) — refuses to run without both flags

``--list`` / ``--dry`` are always free. ``--go`` is the only path that makes billable calls, and
it requires an explicit ``--model``; nothing here runs the full 4-condition matrix.
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
import time
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from benchmark.targets.registry import BENCH_NETWORK

from .targets import APB_REGISTRY, HOST_PLACEHOLDER, get_probe_target

PROBE_OUT_ROOT = "benchmark/runs_autopenbench_probe"
CONDITION = "full_autonomy"  # the ONLY probe condition (design §4)
DEFAULT_REPS = 2
DEFAULT_BASE_SEED = 1000


# CADIS-first ordering (random is budget-matched to CADIS's measured levels, so CADIS must run
# first on each target). full_autonomy is normally already done and skipped.
RUN_ORDER = ("cadis", "full_autonomy", "static_hitl", "random")


@dataclass(frozen=True)
class ProbeCell:
    target: str
    rep: int
    seed: int
    condition: str = CONDITION

    def out_dir(self, out_root: str | Path) -> Path:
        return (
            Path(out_root)
            / "raw_runs"
            / self.condition
            / self.target
            / f"rep_{self.rep}"
        )

    def is_done(self, out_root: str | Path) -> bool:
        return (self.out_dir(out_root) / "summary.json").is_file()


def plan_cells(
    targets: Sequence[str], reps: int = DEFAULT_REPS, base_seed: int = DEFAULT_BASE_SEED
) -> List[ProbeCell]:
    cells: List[ProbeCell] = []
    for target in targets:
        for rep in range(1, reps + 1):
            cells.append(ProbeCell(target=target, rep=rep, seed=base_seed + rep))
    return cells


def _existing_fa_reps(out_root: str | Path, target: str) -> int:
    """Number of completed full_autonomy reps already recorded for a target."""
    base = Path(out_root) / "raw_runs" / "full_autonomy" / target
    if not base.is_dir():
        return 0
    return sum(1 for d in base.glob("rep_*") if (d / "summary.json").is_file())


def plan_matrix(
    targets: Sequence[str],
    out_root: str | Path,
    conditions: Sequence[str] = RUN_ORDER,
    base_seed: int = DEFAULT_BASE_SEED,
) -> List[ProbeCell]:
    """Plan the 4-condition matrix, CADIS-first, matching each target's existing full_autonomy reps.

    Reuses the reps full_autonomy already has for each target (so nothing is re-run/overwritten);
    the other conditions are planned for the same (target, rep, seed) set. full_autonomy cells are
    included (and skipped as done). Random requires CADIS in the same run (budget-matched).
    """
    ordered = [c for c in RUN_ORDER if c in conditions]
    if "random" in ordered and "cadis" not in ordered:
        raise ValueError(
            "'random' is budget-matched and requires 'cadis' in the same run"
        )
    cells: List[ProbeCell] = []
    for target in targets:
        reps = _existing_fa_reps(out_root, target) or DEFAULT_REPS
        for condition in ordered:
            for rep in range(1, reps + 1):
                cells.append(
                    ProbeCell(
                        target=target,
                        rep=rep,
                        seed=base_seed + rep,
                        condition=condition,
                    )
                )
    return cells


# --------------------------------------------------------------------------- #
# Cost metering (LiteLLM success callback) — OpenRouter-accurate where available
# --------------------------------------------------------------------------- #


class CostMeter:
    """Accumulates per-completion token usage + cost via a LiteLLM success callback."""

    def __init__(self) -> None:
        self.calls: List[dict] = []

    def _cb(
        self, kwargs, completion_response, start_time, end_time
    ) -> None:  # noqa: ANN001
        try:
            usage = getattr(completion_response, "usage", None)
            pt = int(getattr(usage, "prompt_tokens", 0) or 0)
            ct = int(getattr(usage, "completion_tokens", 0) or 0)
            cost = kwargs.get("response_cost")
            if cost is None:
                try:
                    import litellm

                    cost = litellm.completion_cost(
                        completion_response=completion_response
                    )
                except Exception:  # noqa: BLE001
                    cost = None
            self.calls.append(
                {
                    "prompt_tokens": pt,
                    "completion_tokens": ct,
                    "cost_usd": cost,
                    "model": kwargs.get("model"),
                }
            )
        except Exception:  # noqa: BLE001 - metering must never break a run
            pass

    def install(self) -> None:
        try:
            import litellm

            if self._cb not in litellm.success_callback:
                litellm.success_callback.append(self._cb)
        except Exception:  # noqa: BLE001
            pass

    def remove(self) -> None:
        try:
            import litellm

            if self._cb in litellm.success_callback:
                litellm.success_callback.remove(self._cb)
        except Exception:  # noqa: BLE001
            pass

    def summary(self) -> dict:
        pt = sum(c["prompt_tokens"] for c in self.calls)
        ct = sum(c["completion_tokens"] for c in self.calls)
        costs = [
            c["cost_usd"] for c in self.calls if isinstance(c["cost_usd"], (int, float))
        ]
        return {
            "n_llm_calls": len(self.calls),
            "prompt_tokens": pt,
            "completion_tokens": ct,
            "total_tokens": pt + ct,
            "cost_usd": (round(sum(costs), 6) if costs else None),
            "cost_coverage": (len(costs) / len(self.calls)) if self.calls else 0.0,
        }


# --------------------------------------------------------------------------- #
# One cell (BILLABLE)
# --------------------------------------------------------------------------- #


def _tracker_tokens() -> int:
    """Cumulative daily token count from the persistent token tracker (best-effort).

    Reliable fallback for the LiteLLM success callback (which did not fire on this path in the
    initial probe): the agent's LLM wrapper records every call's usage into the tracker, so a
    before/after delta gives per-cell tokens even when the callback misses.
    """
    try:
        from pentestagent.tools import token_tracker

        return int(token_tracker.get_stats_sync().get("daily_usage", 0) or 0)
    except Exception:  # noqa: BLE001
        return 0


def _build_gate(condition, target_id, rep, seed, out_root, model):
    """Build the CADIS gate for one condition.

    Sampler (USC, N=5) is ON only for the CADIS condition — the one place USC affects routing;
    full_autonomy/static_hitl/random route USC-independently, so sampling them is pure cost. The
    random condition is budget-matched to CADIS's measured levels on the same target (CADIS-first).
    """
    from pentestagent.cadis.conditions import get_condition_policy
    from pentestagent.cadis.config import load_config
    from pentestagent.cadis.engine import CadisEngine
    from pentestagent.cadis.gate import CadisGate
    from pentestagent.cadis.operator import BenchmarkOperator
    from pentestagent.cadis.recorder import RunRecorder
    from pentestagent.cadis.signals.risk import RiskClassifier

    cfg = load_config()
    classifier = RiskClassifier.from_yaml(cfg.taxonomy_path, cfg.unmatched_default)
    engine = CadisEngine(cfg, classifier)
    recorder = RunRecorder.from_config(out_root, condition, target_id, rep, seed, cfg)

    if condition == "random":
        from benchmark.run.driver import load_cadis_budget

        policy = get_condition_policy(
            "random", budget=load_cadis_budget(out_root, target_id), seed=seed
        )
    else:
        policy = get_condition_policy(condition)

    sampler = None
    if condition == "cadis":
        from pentestagent.cadis.sampler import SelfConsistencySampler

        sampler = SelfConsistencySampler(
            model,
            n_samples=cfg.n_samples,
            temperature=cfg.temperature,
            base_seed=seed,
        )

    gate = CadisGate(
        engine, BenchmarkOperator(), policy=policy, sampler=sampler, recorder=recorder
    )
    return gate, recorder


async def run_cell(
    cell: ProbeCell, *, model: str, out_root: str | Path = PROBE_OUT_ROOT
) -> dict:
    """Execute one probe cell end-to-end (BILLABLE). Returns the run summary."""
    from benchmark.run.driver import _connect_sandbox_to_network
    from pentestagent.config.constants import get_openrouter_api_key
    from pentestagent.interface.initializer import build_agent_components

    from . import oracle, provision

    if not get_openrouter_api_key():
        raise RuntimeError(
            "OPENROUTER_API_KEY not available (.env or openrouterkey.txt)"
        )

    target = get_probe_target(cell.target)
    ground_truth_flag = provision.read_flag(target)

    reset = provision.reset_target(cell.target)
    host = reset.ip or target.container
    objective = target.objective.replace(HOST_PLACEHOLDER, host)

    gate, recorder = _build_gate(
        cell.condition, cell.target, cell.rep, cell.seed, out_root, model
    )

    components = await build_agent_components(
        target=host, model=model, docker=True, no_rag=True, no_mcp=True
    )
    agent = components["agent"]
    agent.max_iterations = target.max_iterations
    agent.action_gate = gate
    _connect_sandbox_to_network(components.get("runtime"), BENCH_NETWORK)

    # Capture EVERY tool output the agent sees (the flag oracle scans these). Wrapping
    # _execute_tools catches both gate-executed calls and any direct executions.
    captured: List[str] = []
    orig_exec = agent._execute_tools

    async def _capturing_exec(calls):  # noqa: ANN001
        results = await orig_exec(calls)
        for r in results:
            if getattr(r, "result", None):
                captured.append(str(r.result))
            if getattr(r, "error", None):
                captured.append(str(r.error))
        return results

    agent._execute_tools = _capturing_exec  # type: ignore[assignment]

    meter = CostMeter()
    meter.install()
    tokens_before = _tracker_tokens()
    self_reported = False
    t0 = time.time()
    try:
        async for msg in agent.agent_loop(objective):
            meta = getattr(msg, "metadata", None) or {}
            if meta.get("task_complete"):
                self_reported = True
    finally:
        meter.remove()
        wall_s = round(time.time() - t0, 1)
        oracle_res = oracle.scan_for_flag(ground_truth_flag, captured)
        summary = recorder.close(completed=oracle_res.captured)
        cost = meter.summary()
        # Reliable token count from the persistent tracker (independent of the callback).
        cost["tracker_tokens_delta"] = max(0, _tracker_tokens() - tokens_before)
        # Probe diagnostics alongside the standard summary (kept separate from the frozen fields).
        run_dir = cell.out_dir(out_root)
        (run_dir / "probe_meta.json").write_text(
            json.dumps(
                {
                    "target": cell.target,
                    "apb_task": target.apb_task,
                    "exploit_class": target.exploit_class,
                    "flag_oracle": oracle_res.to_dict(),
                    "self_reported_complete": self_reported,  # for comparison, NOT the TCR oracle
                    "wall_s": wall_s,
                    "max_iterations": target.max_iterations,
                    "cost": cost,
                    "condition": cell.condition,
                    "sampler": "on" if cell.condition == "cadis" else "off",
                },
                indent=2,
            ),
            encoding="utf-8",
        )
        try:
            rt = components.get("runtime")
            if rt is not None:
                await rt.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            provision.teardown_target(cell.target)
        except Exception:  # noqa: BLE001
            pass
    return summary


# --------------------------------------------------------------------------- #
# CLI
# --------------------------------------------------------------------------- #


def _check_env_and_images() -> bool:
    from . import provision

    ok = True
    try:
        r = provision._docker(
            ["version", "--format", "{{.Server.Version}}"], timeout=30
        )
        print(
            f"docker daemon: {r.stdout.strip() if r.returncode == 0 else 'NOT available'}"
        )
        ok = ok and r.returncode == 0
    except Exception as e:  # noqa: BLE001
        print(f"docker check failed: {e}")
        ok = False
    try:
        from pentestagent.config.constants import get_openrouter_api_key

        print(f"OpenRouter key: {'present' if get_openrouter_api_key() else 'MISSING'}")
    except Exception as e:  # noqa: BLE001
        print(f"key check failed: {e}")
    for t in APB_REGISTRY.values():
        built = provision._docker(["image", "inspect", t.image_tag]).returncode == 0
        print(f"image {t.image_tag}: {'built' if built else 'NOT built'}")
        for sc in t.sidecars:
            b = provision._docker(["image", "inspect", sc.image_tag]).returncode == 0
            print(f"  sidecar {sc.image_tag}: {'built' if b else 'NOT built'}")
    return ok


def _openrouter_usage() -> Optional[float]:
    """Current cumulative account usage in USD from the OpenRouter API (best-effort)."""
    try:
        import json as _json
        import urllib.request

        from pentestagent.config.constants import get_openrouter_api_key

        key = get_openrouter_api_key()
        req = urllib.request.Request(
            "https://openrouter.ai/api/v1/auth/key",
            headers={"Authorization": f"Bearer {key}"},
        )
        with urllib.request.urlopen(req, timeout=20) as r:
            data = _json.load(r).get("data", {})
        u = data.get("usage")
        return float(u) if u is not None else None
    except Exception:  # noqa: BLE001
        return None


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="benchmark.autopenbench_probe.driver")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--list", action="store_true", help="print the plan and exit (no LLM/Docker)"
    )
    mode.add_argument(
        "--dry", action="store_true", help="plan + env/image checks (no LLM calls)"
    )
    mode.add_argument("--go", action="store_true", help="EXECUTE (BILLABLE)")
    p.add_argument(
        "--matrix",
        action="store_true",
        help="full 4-condition matrix (CADIS-first), matching each target's existing "
        "full_autonomy reps; otherwise full_autonomy only",
    )
    p.add_argument(
        "--conditions",
        default=",".join(RUN_ORDER),
        help="comma-separated subset of the 4 conditions (matrix mode)",
    )
    p.add_argument("--targets", default=",".join(APB_REGISTRY.keys()))
    p.add_argument("--reps", type=int, default=DEFAULT_REPS)
    p.add_argument(
        "--model", default=None, help="pinned openrouter/<provider>/<model> (--go)"
    )
    p.add_argument("--out-root", default=PROBE_OUT_ROOT)
    p.add_argument(
        "--max-usd",
        type=float,
        default=3.0,
        help="hard spend cap (USD): stop before running a cell once real OpenRouter "
        "usage rises by this much since the run started",
    )
    return p.parse_args(argv)


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]

    if args.matrix:
        cells = plan_matrix(targets, args.out_root, conditions=conditions)
        header = f"AutoPenBench FULL MATRIX — conditions={conditions} (CADIS-first, sampler on CADIS only)"
    else:
        cells = plan_cells(targets, reps=args.reps)
        header = (
            f"AutoPenBench PROBE — full_autonomy only, sampler OFF, reps={args.reps}"
        )

    todo = [c for c in cells if not c.is_done(args.out_root)]
    print(header)
    from collections import Counter

    by_cond_total = Counter(c.condition for c in cells)
    by_cond_todo = Counter(c.condition for c in todo)
    for cond in RUN_ORDER:
        if by_cond_total.get(cond):
            print(
                f"  {cond:14s}: {by_cond_todo.get(cond, 0):3d} todo / {by_cond_total[cond]:3d} total"
            )
    print(f"{len(todo)} todo / {len(cells)} total cells under {args.out_root}")

    if args.list:
        return 0
    if args.dry:
        print("--- environment / images ---")
        _check_env_and_images()
        print("note: --dry makes NO LLM calls. Use --go --model <M> to run (BILLABLE).")
        return 0
    if args.go:
        if not args.model:
            print("error: --go requires --model (billable run)", file=sys.stderr)
            return 2
        baseline = _openrouter_usage()
        print(
            f"EXECUTING {len(todo)} billable cells on {args.model} "
            f"(budget cap ${args.max_usd}; baseline usage ${baseline}) ...",
            file=sys.stderr,
        )
        spent = 0.0
        for i, cell in enumerate(todo, start=1):
            cur = _openrouter_usage()
            if baseline is not None and cur is not None:
                spent = cur - baseline
                if spent >= args.max_usd:
                    print(
                        f"BUDGET CAP: spent ${spent:.3f} >= ${args.max_usd}; stopping "
                        f"before cell {i}/{len(todo)}.",
                        file=sys.stderr,
                    )
                    break
            print(
                f"[{i}/{len(todo)}] {cell.condition} {cell.target} rep_{cell.rep} "
                f"(spent ${spent:.3f}) ...",
                file=sys.stderr,
            )
            try:
                asyncio.run(run_cell(cell, model=args.model, out_root=args.out_root))
            except Exception as e:  # noqa: BLE001
                print(f"  cell failed: {e}", file=sys.stderr)
        final = _openrouter_usage()
        if baseline is not None and final is not None:
            print(f"RUN COMPLETE — spent ${final - baseline:.4f}", file=sys.stderr)
        return 0
    print("no mode given; use --list, --dry, or --go --model <M>", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
