"""Benchmark orchestrator (newplan.md section 10 / section 15).

Plans and drives the matrix **4 conditions x targets x R repetitions**, enforcing
**CADIS-first ordering** on each target (so the budget-matched Random condition can be
built from CADIS's measured levels). Resumable: cells whose ``summary.json`` already
exists are skipped.

    python -m benchmark.run.orchestrate --list  --conditions full_autonomy,static_hitl,random,cadis --out-root benchmark/runs_<model>
    python -m benchmark.run.orchestrate --dry   --model <MODEL> --out-root benchmark/runs_<model>
    python -m benchmark.run.orchestrate         --model <MODEL> --out-root benchmark/runs_<model>

``--list`` and ``--dry`` make **no LLM calls** (planning only); ``--dry`` additionally
checks the environment (Docker + OpenRouter key). Only the full run invokes the driver.
"""

from __future__ import annotations

import argparse
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import List, Optional, Sequence

from benchmark.targets.registry import target_ids
from pentestagent.cadis.conditions import CONDITIONS

# Canonical execution order: CADIS first (fixes the Random budget), Random last.
RUN_ORDER = ("cadis", "full_autonomy", "static_hitl", "random")

DEFAULT_REPS = 3
DEFAULT_BASE_SEED = 1000


@dataclass(frozen=True)
class Cell:
    """One matrix cell = one benchmark run."""

    condition: str
    target: str
    rep: int
    seed: int

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


def _order_conditions(conditions: Sequence[str]) -> List[str]:
    """Order the requested conditions CADIS-first (RUN_ORDER), unknowns rejected."""
    unknown = [c for c in conditions if c not in CONDITIONS]
    if unknown:
        raise ValueError(
            f"unknown condition(s) {unknown}; the benchmark is exactly {CONDITIONS} "
            "(floor_only/risk_only are out of scope, newplan.md section 17)"
        )
    if "random" in conditions and "cadis" not in conditions:
        raise ValueError(
            "the 'random' condition is budget-matched and requires 'cadis' in the same "
            "run (CADIS-first ordering); add 'cadis'"
        )
    return [c for c in RUN_ORDER if c in conditions]


def plan_matrix(
    conditions: Sequence[str],
    targets: Sequence[str],
    reps: int = DEFAULT_REPS,
    base_seed: int = DEFAULT_BASE_SEED,
) -> List[Cell]:
    """Plan the full matrix, CADIS-first per target, distinct seed per rep.

    Iterates target -> condition(CADIS-first) -> rep, so on each target every CADIS rep
    precedes that target's Random rep. The seed is shared across conditions for a given
    rep (paired comparison on the same seed), distinct across reps.
    """
    if reps < 1:
        raise ValueError(f"reps must be >= 1, got {reps}")
    ordered = _order_conditions(conditions)
    cells: List[Cell] = []
    for target in targets:
        for condition in ordered:
            for rep in range(1, reps + 1):
                cells.append(
                    Cell(
                        condition=condition,
                        target=target,
                        rep=rep,
                        seed=base_seed + rep,
                    )
                )
    return cells


def pending_cells(cells: Sequence[Cell], out_root: str | Path) -> List[Cell]:
    """Cells not yet completed (no summary.json) -- for resumable runs."""
    return [c for c in cells if not c.is_done(out_root)]


def _sanitize(model: str) -> str:
    return model.replace("/", "_").replace(":", "_")


def _parse_args(argv: Optional[Sequence[str]] = None) -> argparse.Namespace:
    p = argparse.ArgumentParser(prog="benchmark.run.orchestrate")
    mode = p.add_mutually_exclusive_group()
    mode.add_argument(
        "--list", action="store_true", help="print the plan and exit (no runs)"
    )
    mode.add_argument("--dry", action="store_true", help="plan + env checks, no runs")
    p.add_argument(
        "--conditions",
        default=",".join(RUN_ORDER),
        help="comma-separated subset of the four conditions",
    )
    p.add_argument(
        "--targets",
        default=",".join(target_ids()),
        help="comma-separated target ids (default: all)",
    )
    p.add_argument("--reps", type=int, default=DEFAULT_REPS)
    p.add_argument("--base-seed", type=int, default=DEFAULT_BASE_SEED)
    p.add_argument("--model", default=None, help="pinned openrouter/<provider>/<model>")
    p.add_argument("--out-root", default=None)
    p.add_argument("--max-iterations", type=int, default=20)
    return p.parse_args(argv)


def _print_plan(cells: Sequence[Cell], out_root: str | Path) -> None:
    print(f"Planned {len(cells)} runs (CADIS-first) under {out_root}:")
    for c in cells:
        mark = "done" if c.is_done(out_root) else "todo"
        print(f"  [{mark}] {c.condition:14s} {c.target:14s} rep_{c.rep} seed={c.seed}")
    todo = pending_cells(cells, out_root)
    print(f"{len(todo)} pending, {len(cells) - len(todo)} already complete.")


def _check_env() -> bool:
    ok = True
    try:
        import subprocess

        r = subprocess.run(
            ["docker", "version", "--format", "{{.Server.Version}}"],
            capture_output=True,
            text=True,
            timeout=30,
        )
        if r.returncode == 0:
            print(f"docker daemon: {r.stdout.strip()}")
        else:
            print("docker daemon: NOT available")
            ok = False
    except Exception as e:  # noqa: BLE001
        print(f"docker check failed: {e}")
        ok = False
    try:
        from pentestagent.config.constants import get_openrouter_api_key

        print(f"OpenRouter key: {'present' if get_openrouter_api_key() else 'MISSING'}")
        ok = ok and bool(get_openrouter_api_key())
    except Exception as e:  # noqa: BLE001
        print(f"key check failed: {e}")
        ok = False
    return ok


def main(argv: Optional[Sequence[str]] = None) -> int:
    args = _parse_args(argv)
    conditions = [c.strip() for c in args.conditions.split(",") if c.strip()]
    targets = [t.strip() for t in args.targets.split(",") if t.strip()]

    out_root = args.out_root or (
        f"benchmark/runs_{_sanitize(args.model)}" if args.model else "benchmark/runs"
    )

    try:
        cells = plan_matrix(
            conditions, targets, reps=args.reps, base_seed=args.base_seed
        )
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if args.list:
        _print_plan(cells, out_root)
        return 0

    if args.dry:
        _print_plan(cells, out_root)
        print("--- environment ---")
        env_ok = _check_env()
        if not args.model:
            print("note: no --model given (required for the full run)")
        return 0 if env_ok else 1

    # Full run.
    if not args.model:
        print("error: --model is required for the full run", file=sys.stderr)
        return 2

    import asyncio

    from benchmark.run.driver import run_cell

    todo = pending_cells(cells, out_root)
    print(f"Executing {len(todo)} pending runs under {out_root} (CADIS-first)...")
    for i, cell in enumerate(todo, start=1):
        print(f"[{i}/{len(todo)}] {cell.condition} {cell.target} rep_{cell.rep} ...")
        try:
            asyncio.run(
                run_cell(
                    cell,
                    out_root=out_root,
                    model=args.model,
                    max_iterations=args.max_iterations,
                )
            )
        except Exception as e:  # noqa: BLE001
            print(
                f"  run failed (marked invalid, will re-run next pass): {e}",
                file=sys.stderr,
            )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
