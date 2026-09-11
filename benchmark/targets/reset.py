"""Target reset harness (newplan.md section 8 / CadisClaude.md section 9.3).

Brings up an isolated Docker bridge, and destroys + recreates each target from its
pinned image digest between runs so no state leaks. Readiness is probed from *inside*
the isolated network with a throwaway ``curlimages/curl`` container (targets are not
published to the host, preserving isolation).

All Docker interaction is via the ``docker`` CLI (subprocess); this module is
infrastructure, not part of the pure scoring core.
"""

from __future__ import annotations

import logging
import subprocess
import time
from dataclasses import dataclass
from typing import List, Optional, Sequence

from .registry import BENCH_NETWORK, Target, get_target

log = logging.getLogger("cadis.benchmark.targets")

# Throwaway image used to probe readiness from within the isolated network.
_PROBE_IMAGE = "curlimages/curl:latest"

# curl exit codes meaning "could not connect" (host unreachable / connection refused).
_CURL_CONNECT_FAIL = {6, 7}


class TargetResetError(RuntimeError):
    """Raised when a target could not be reset/started."""


@dataclass
class ResetResult:
    """Outcome of resetting one target."""

    target: Target
    container: str
    ip: Optional[str]
    ready: bool
    elapsed_s: float


def _docker(args: Sequence[str], timeout: int = 120) -> subprocess.CompletedProcess:
    """Run a docker CLI command, capturing output (never raises on nonzero)."""
    return subprocess.run(
        ["docker", *args],
        capture_output=True,
        text=True,
        timeout=timeout,
    )


def ensure_network(name: str = BENCH_NETWORK) -> str:
    """Create the isolated benchmark bridge if it does not already exist."""
    inspect = _docker(["network", "inspect", name])
    if inspect.returncode == 0:
        return name
    created = _docker(["network", "create", "--driver", "bridge", name])
    if created.returncode != 0:
        raise TargetResetError(
            f"failed to create network {name!r}: {created.stderr.strip()}"
        )
    log.info("created isolated benchmark network %s", name)
    return name


def _container_running(container: str) -> bool:
    res = _docker(["inspect", "-f", "{{.State.Running}}", container])
    return res.returncode == 0 and res.stdout.strip() == "true"


def target_ip(container: str, network: str = BENCH_NETWORK) -> Optional[str]:
    """Return the container's IP on the benchmark network, or None."""
    res = _docker(
        [
            "inspect",
            "-f",
            '{{index .NetworkSettings.Networks "' + network + '" "IPAddress"}}',
            container,
        ]
    )
    ip = res.stdout.strip()
    return ip or None


def _probe(target: Target, network: str = BENCH_NETWORK) -> bool:
    """One readiness probe from inside the network via a throwaway curl container."""
    host = target.container
    if target.protocol == "http":
        url = f"http://{host}:{target.port}{target.health_path}"
        res = _docker(
            [
                "run",
                "--rm",
                "--network",
                network,
                _PROBE_IMAGE,
                "-s",
                "-o",
                "/dev/null",
                "-w",
                "%{http_code}",
                "--max-time",
                "5",
                url,
            ],
            timeout=30,
        )
        code = res.stdout.strip()
        return code.isdigit() and int(code) >= 100
    # tcp: a bare connect probe; "connected" (even if it then times out reading) = ready.
    url = f"telnet://{host}:{target.port}"
    res = _docker(
        [
            "run",
            "--rm",
            "--network",
            network,
            _PROBE_IMAGE,
            "-s",
            "-o",
            "/dev/null",
            "--max-time",
            "5",
            url,
        ],
        timeout=30,
    )
    return res.returncode not in _CURL_CONNECT_FAIL


def wait_ready(target: Target, timeout: int = 120, interval: float = 3.0) -> bool:
    """Poll readiness until the target answers or the timeout elapses."""
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _container_running(target.container) and _probe(target):
            return True
        time.sleep(interval)
    return False


def teardown_target(target_id: str) -> None:
    """Force-remove a target's benchmark container (no-op if absent)."""
    target = get_target(target_id)
    _docker(["rm", "-f", target.container])


def reset_target(
    target_id: str,
    *,
    network: str = BENCH_NETWORK,
    wait: bool = True,
    timeout: int = 120,
) -> ResetResult:
    """Destroy and recreate a target from its pinned image digest, then wait ready.

    newplan.md section 8: each target is recreated from its pinned digest between runs
    so no state leaks. Raises TargetResetError if the container fails to start or (when
    ``wait``) never becomes ready.
    """
    target = get_target(target_id)
    ensure_network(network)
    started = time.time()

    # Destroy any prior instance (idempotent).
    _docker(["rm", "-f", target.container])

    run = _docker(
        [
            "run",
            "-d",
            # -i -t keep containers whose CMD ends in an interactive shell alive
            # (e.g. Metasploitable2's `services.sh && bash`); harmless for the
            # foreground-server images (DVWA/Juice-Shop).
            "-i",
            "-t",
            "--name",
            target.container,
            "--network",
            network,
            "--label",
            "cadis-bench=1",
            "--label",
            f"cadis-target={target.id}",
            target.image,
        ]
    )
    if run.returncode != 0:
        raise TargetResetError(
            f"failed to start {target.container!r} from {target.image}: "
            f"{run.stderr.strip()}"
        )

    ready = True
    if wait:
        ready = wait_ready(target, timeout=timeout)
        if not ready:
            raise TargetResetError(
                f"target {target.id!r} started but did not become ready within "
                f"{timeout}s"
            )

    return ResetResult(
        target=target,
        container=target.container,
        ip=target_ip(target.container, network),
        ready=ready,
        elapsed_s=round(time.time() - started, 1),
    )


def reset_all(**kwargs) -> List[ResetResult]:
    """Reset every registered target (used by the runner between matrix cells)."""
    from .registry import target_ids

    return [reset_target(tid, **kwargs) for tid in target_ids()]


def teardown_all(remove_network: bool = False) -> None:
    """Remove all benchmark containers (label cadis-bench=1); optionally the network."""
    res = _docker(["ps", "-aq", "--filter", "label=cadis-bench=1"])
    ids = [c for c in res.stdout.split() if c]
    if ids:
        _docker(["rm", "-f", *ids])
    if remove_network:
        _docker(["network", "rm", BENCH_NETWORK])
