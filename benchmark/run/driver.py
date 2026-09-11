"""Single-cell benchmark driver (newplan.md section 10).

Runs one ``(condition, target, rep)``: reset the target from its pinned digest, build the
CADIS engine + sampler + operator + the condition's policy, install the gate (with a
per-step recorder) on a real PentestAgentAgent, run the agent loop against the target's
objective, then close the recorder and tear the target down.

The host framework is IDENTICAL across conditions; only the policy installed on the gate
differs (constraint C7). "Sample 0 executes" holds -- the agent's own proposed call is the
one that runs when the policy permits.

NOTE (live-run wiring, resolved at S14 pre-flight): the DockerRuntime sandbox that executes
tools must be able to reach the target container on ``cadis-bench-net``. That network
attachment is a pre-flight step for S14 execution; this module is import-clean and drives
the plan, but a live run additionally requires that connectivity. The S10 gate is the dry
plan (``--list`` / ``--dry``), which makes no LLM calls and needs none of this.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from benchmark.targets.registry import BENCH_NETWORK, get_target
from pentestagent.cadis.conditions import RandomBudget, get_condition_policy
from pentestagent.cadis.config import load_config
from pentestagent.cadis.engine import CadisEngine
from pentestagent.cadis.gate import CadisGate
from pentestagent.cadis.operator import BenchmarkOperator
from pentestagent.cadis.recorder import RunRecorder
from pentestagent.cadis.sampler import SelfConsistencySampler
from pentestagent.cadis.signals.risk import RiskClassifier


def load_cadis_budget(out_root: str | Path, target_id: str) -> RandomBudget:
    """Build the Random condition's budget from CADIS's logged levels on this target.

    Pools the per-action ``final_level``s across every completed CADIS rep on the target
    (CADIS-first ordering guarantees they exist before Random runs).
    """
    base = Path(out_root) / "raw_runs" / "cadis" / target_id
    levels: list[int] = []
    for summ in sorted(base.glob("rep_*/summary.json")):
        try:
            data = json.loads(summ.read_text(encoding="utf-8"))
            levels.extend(int(x) for x in data.get("levels", []))
        except (OSError, ValueError):
            continue
    return RandomBudget.from_levels(levels)


def build_gate(
    condition: str,
    target_id: str,
    *,
    model: str,
    out_root: str | Path,
    rep: int,
    seed: int,
) -> tuple[CadisGate, RunRecorder]:
    """Construct the CADIS gate + recorder for one cell (no agent, no target reset)."""
    cfg = load_config()
    classifier = RiskClassifier.from_yaml(cfg.taxonomy_path, cfg.unmatched_default)
    engine = CadisEngine(cfg, classifier)
    sampler = SelfConsistencySampler(
        model,
        n_samples=cfg.n_samples,
        temperature=cfg.temperature,
        base_seed=seed,
    )
    operator = BenchmarkOperator()  # pre-registered L2 rule (D2), finalised at S13

    if condition == "random":
        budget = load_cadis_budget(out_root, target_id)
        policy = get_condition_policy("random", budget=budget, seed=seed)
    else:
        policy = get_condition_policy(condition)

    recorder = RunRecorder.from_config(out_root, condition, target_id, rep, seed, cfg)
    gate = CadisGate(
        engine, operator, policy=policy, sampler=sampler, recorder=recorder
    )
    return gate, recorder


def _connect_sandbox_to_network(runtime: Any, network: str = BENCH_NETWORK) -> None:
    """Attach the DockerRuntime sandbox to the isolated benchmark network.

    S14 pre-flight: tools run inside the sandbox container, which by default sits on the
    plain bridge and cannot reach the targets on ``cadis-bench-net``. Connecting it here
    lets the agent reach targets by their IP/container name. Idempotent + best-effort.
    """
    try:
        client = getattr(runtime, "client", None)
        container = getattr(runtime, "container", None)
        if client is None or container is None:
            return
        container.reload()
        nets = container.attrs.get("NetworkSettings", {}).get("Networks", {})
        if network not in nets:
            client.networks.get(network).connect(container)
    except (
        Exception
    ) as e:  # noqa: BLE001 - best-effort; a live run surfaces reachability
        import logging

        logging.getLogger("cadis.benchmark.driver").warning(
            "could not attach sandbox to %s: %s", network, e
        )


async def run_cell(
    cell: Any,
    *,
    out_root: str | Path,
    model: str,
    max_iterations: int = 20,
    docker: bool = True,
) -> dict:
    """Execute one benchmark cell end-to-end and return the run summary."""
    from benchmark.targets.reset import reset_target, teardown_target
    from pentestagent.config.constants import get_openrouter_api_key
    from pentestagent.interface.initializer import build_agent_components

    # Ensure the OpenRouter key is exported to the environment so BOTH the agent LLM
    # (LiteLLM openrouter/*) and the sampler can authenticate (newplan.md section 6).
    if not get_openrouter_api_key():
        raise RuntimeError(
            "OPENROUTER_API_KEY not available (set it in .env or openrouterkey.txt)"
        )

    target = get_target(cell.target)

    # 1. Fresh target from the pinned digest (no state leak between runs).
    reset = reset_target(cell.target)

    # 2. CADIS gate + recorder for this condition.
    gate, recorder = build_gate(
        cell.condition,
        cell.target,
        model=model,
        out_root=out_root,
        rep=cell.rep,
        seed=cell.seed,
    )

    # 3. Real agent stack (RAG/MCP off for reproducibility); install the gate.
    components = await build_agent_components(
        target=reset.ip or target.container,
        model=model,
        docker=docker,
        no_rag=True,
        no_mcp=True,
    )
    agent = components["agent"]
    agent.max_iterations = max_iterations
    agent.action_gate = gate

    # 3b. Attach the sandbox to the isolated benchmark network so tools reach the target.
    if docker:
        _connect_sandbox_to_network(components.get("runtime"))

    # 4. Run the agent loop against the target objective (sample 0 executes).
    #    Track self-reported task completion for TCR (newplan.md section 12 oracle).
    completed = False
    try:
        async for msg in agent.agent_loop(target.objective):
            meta = getattr(msg, "metadata", None) or {}
            if meta.get("task_complete"):
                completed = True
    finally:
        summary = recorder.close(completed=completed)
        try:
            runtime = components.get("runtime")
            if runtime is not None:
                await runtime.stop()
        except Exception:  # noqa: BLE001
            pass
        try:
            teardown_target(cell.target)
        except Exception:  # noqa: BLE001
            pass

    return summary
