"""Probe target provisioning + reset (design doc §2; deviation D8).

Builds the two AutoPenBench machine images locally from the git-ignored ``vendor/`` build
contexts, pins each by its LOCAL image id (these images are never pushed, so there is no
registry manifest digest — the same local-digest caveat the frozen ``registry.py`` records),
extracts each machine's ground-truth flag, and resets targets between reps by destroying +
recreating them from the pinned image on the isolated ``cadis-bench-net`` bridge (reusing the
frozen network; the sandbox is already attached there by ``benchmark/run/driver``).

All Docker interaction is via the ``docker`` CLI (subprocess) — infrastructure, not scoring core.
Nothing here is imported by the frozen benchmark; it only ADDS containers/images.
"""

from __future__ import annotations

import json
import logging
import subprocess
import time
from dataclasses import dataclass
from hashlib import sha256
from pathlib import Path
from typing import List, Optional, Sequence, Tuple

from benchmark.targets.registry import BENCH_NETWORK

from .targets import APB_REGISTRY, ProbeTarget, Sidecar, get_probe_target

log = logging.getLogger("cadis.benchmark.autopenbench_probe")

PKG_DIR = Path(__file__).resolve().parent
_PROBE_IMAGE = (
    "curlimages/curl:latest"  # throwaway readiness prober (same as frozen reset.py)
)
_CURL_CONNECT_FAIL = {6, 7}
_MYSQL_SIDECAR_IMAGE = "mysql:5.7"


class ProbeProvisionError(RuntimeError):
    """Raised when a probe image/container could not be built, started, or made ready."""


def _docker(args: Sequence[str], timeout: int = 180) -> subprocess.CompletedProcess:
    return subprocess.run(
        ["docker", *args], capture_output=True, text=True, timeout=timeout
    )


def ensure_network(name: str = BENCH_NETWORK) -> str:
    if _docker(["network", "inspect", name]).returncode == 0:
        return name
    created = _docker(["network", "create", "--driver", "bridge", name])
    if created.returncode != 0:
        raise ProbeProvisionError(
            f"failed to create network {name!r}: {created.stderr.strip()}"
        )
    return name


# --------------------------------------------------------------------------- #
# Build + pin + flag extraction
# --------------------------------------------------------------------------- #


def _context_path(rel: str) -> Path:
    p = (PKG_DIR / rel).resolve()
    if not p.is_dir():
        raise ProbeProvisionError(
            f"missing build context {rel!r} at {p} — run the vendor copy step "
            "(clone AutoPenBench and copy the vm3/vm10 contexts into vendor/)"
        )
    return p


def _generate_db_context() -> Path:
    """Create the vm3 MySQL sidecar build context (FROM mysql:5.7 + baked init.sql).

    Baking init.sql into the image (rather than bind-mounting) keeps the sidecar self-contained
    and avoids host-path mount quirks on Windows.
    """
    src_sql = _context_path("vendor/web_sqli") / "init.sql"
    if not src_sql.is_file():
        raise ProbeProvisionError(f"init.sql not found at {src_sql}")
    ctx = PKG_DIR / "vendor" / "web_sqli_db"
    ctx.mkdir(parents=True, exist_ok=True)
    (ctx / "init.sql").write_text(src_sql.read_text(encoding="utf-8"), encoding="utf-8")
    (ctx / "Dockerfile").write_text(
        f"FROM {_MYSQL_SIDECAR_IMAGE}\n"
        "COPY init.sql /docker-entrypoint-initdb.d/init.sql\n",
        encoding="utf-8",
    )
    return ctx


def build_image(build_context: str, tag: str, timeout: int = 1800) -> str:
    """docker build a context to ``tag``; return the local image id (sha256:...)."""
    ctx = _context_path(build_context)
    log.info("building %s from %s", tag, ctx)
    res = _docker(["build", "-t", tag, str(ctx)], timeout=timeout)
    if res.returncode != 0:
        raise ProbeProvisionError(
            f"docker build {tag} failed:\n{res.stdout[-2000:]}\n{res.stderr[-2000:]}"
        )
    return image_id(tag)


def image_id(tag: str) -> str:
    res = _docker(["inspect", "-f", "{{.Id}}", tag])
    if res.returncode != 0:
        raise ProbeProvisionError(
            f"could not inspect image {tag!r}: {res.stderr.strip()}"
        )
    return res.stdout.strip()


def read_flag(target: ProbeTarget) -> str:
    """Ground-truth flag for a target, read from its vendor build context."""
    p = _context_path(target.build_context) / target.flag_file
    if not p.is_file():
        raise ProbeProvisionError(f"flag file {p} missing for {target.id}")
    return p.read_text(encoding="utf-8").strip()


@dataclass
class BuildRecord:
    target_id: str
    image_tag: str
    image_id: str
    flag_sha256: str
    sidecar_images: Tuple[Tuple[str, str], ...]  # (tag, image_id)


def build_all(write_manifest: bool = True) -> List[BuildRecord]:
    """Build every probe target's image (+ sidecars) and pin ids; optionally write a manifest.

    The manifest records image ids + flag *hashes* (not plaintext) so it is safe to commit;
    the plaintext flag is read on demand from the git-ignored vendor context at run time.
    """
    records: List[BuildRecord] = []
    for target in APB_REGISTRY.values():
        img = build_image(target.build_context, target.image_tag)
        sidecar_imgs: List[Tuple[str, str]] = []
        for sc in target.sidecars:
            ctx = sc.build_context
            if sc.image_tag == "cadis-apb-web-sqli-db:probe":
                _generate_db_context()  # ensure the generated context exists
            sidecar_imgs.append((sc.image_tag, build_image(ctx, sc.image_tag)))
        flag = read_flag(target)
        records.append(
            BuildRecord(
                target_id=target.id,
                image_tag=target.image_tag,
                image_id=img,
                flag_sha256=sha256(flag.encode()).hexdigest(),
                sidecar_images=tuple(sidecar_imgs),
            )
        )
    if write_manifest:
        out = Path("benchmark/results_autopenbench_probe")
        out.mkdir(parents=True, exist_ok=True)
        (out / "provision_manifest.json").write_text(
            json.dumps(
                {
                    "note": "local image ids (built, never pushed); flags stored as sha256 only",
                    "targets": [
                        {
                            "target": r.target_id,
                            "image_tag": r.image_tag,
                            "image_id": r.image_id,
                            "flag_sha256": r.flag_sha256,
                            "sidecars": [
                                {"image_tag": t, "image_id": i}
                                for t, i in r.sidecar_images
                            ],
                        }
                        for r in records
                    ],
                },
                indent=2,
            ),
            encoding="utf-8",
        )
    return records


# --------------------------------------------------------------------------- #
# Reset (bring up sidecars + target, wait ready) / teardown
# --------------------------------------------------------------------------- #


@dataclass
class ProbeResetResult:
    target: ProbeTarget
    container: str
    ip: Optional[str]
    ready: bool
    elapsed_s: float


def _container_ip(container: str, network: str = BENCH_NETWORK) -> Optional[str]:
    res = _docker(
        [
            "inspect",
            "-f",
            '{{index .NetworkSettings.Networks "' + network + '" "IPAddress"}}',
            container,
        ]
    )
    return res.stdout.strip() or None


def _running(container: str) -> bool:
    res = _docker(["inspect", "-f", "{{.State.Running}}", container])
    return res.returncode == 0 and res.stdout.strip() == "true"


def _probe_ready(spec: str, host: str, network: str = BENCH_NETWORK) -> bool:
    """One readiness probe. ``spec`` = 'tcp:PORT' | 'http:PORT/path' | 'exec:<cmd>' | 'sleep:SEC'."""
    kind, _, rest = spec.partition(":")
    if kind == "sleep":
        time.sleep(float(rest or 1))
        return True
    if kind == "exec":
        # Runs inside the (already-named) container `host`.
        res = _docker(["exec", host, "sh", "-lc", rest], timeout=30)
        return res.returncode == 0
    if kind == "http":
        port, _, path = rest.partition("/")
        url = f"http://{host}:{port}/{path}"
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
    if kind == "tcp":
        url = f"telnet://{host}:{rest}"
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
    raise ProbeProvisionError(f"unknown readiness spec {spec!r}")


def _wait_ready(spec: str, host: str, timeout: int, interval: float = 3.0) -> bool:
    deadline = time.time() + timeout
    while time.time() < deadline:
        if _running(host) and _probe_ready(spec, host):
            return True
        time.sleep(interval)
    return False


def _run_container(
    name: str,
    image: str,
    network: str,
    env: Sequence[Tuple[str, str]] = (),
    cmd: Sequence[str] = (),
) -> None:
    _docker(["rm", "-f", name])  # idempotent
    args = [
        "run",
        "-d",
        "-i",
        "-t",
        "--name",
        name,
        "--network",
        network,
        "--label",
        "cadis-apb-probe=1",
    ]
    for k, v in env:
        args += ["-e", f"{k}={v}"]
    args += [image, *cmd]
    res = _docker(args)
    if res.returncode != 0:
        raise ProbeProvisionError(
            f"failed to start {name!r} from {image}: {res.stderr.strip()}"
        )


def _place_flag(target) -> None:
    """Copy the ground-truth flag into a running container (for vms that don't bake it in)."""
    dest = getattr(target, "flag_mount", "")
    if not dest:
        return
    src = _context_path(target.build_context) / target.flag_file
    cp = _docker(["cp", str(src), f"{target.container}:{dest}"])
    if cp.returncode != 0:
        raise ProbeProvisionError(
            f"failed to place flag into {target.container}:{dest}: {cp.stderr.strip()}"
        )
    # make the flag world-readable and its directory traversable (exploit reads it as the web user)
    _docker(
        [
            "exec",
            target.container,
            "sh",
            "-lc",
            f"chmod 644 '{dest}' 2>/dev/null || true; "
            f"chmod o+rx \"$(dirname '{dest}')\" 2>/dev/null || true",
        ]
    )


def _start_sidecar(sc: Sidecar, network: str) -> None:
    _run_container(sc.name, sc.image_tag, network, sc.env)
    if not _wait_ready(sc.ready, sc.name, timeout=sc.timeout):
        raise ProbeProvisionError(
            f"sidecar {sc.name!r} never became ready ({sc.ready})"
        )


def reset_target(
    target_id: str, *, network: str = BENCH_NETWORK, timeout: int = 180
) -> ProbeResetResult:
    """Destroy + recreate a probe target (and its sidecars) from pinned images; wait ready."""
    target = get_probe_target(target_id)
    ensure_network(network)
    started = time.time()

    # Sidecars first (the app resolves them by name), then the target.
    for sc in target.sidecars:
        _start_sidecar(sc, network)

    _run_container(
        target.container,
        target.image_tag,
        network,
        cmd=getattr(target, "run_cmd", ()),
    )
    _place_flag(target)  # no-op unless the target declares flag_mount
    ready_spec = (
        f"http:{target.port}{target.health_path}"
        if target.protocol == "http"
        else f"tcp:{target.port}"
    )
    ready = _wait_ready(ready_spec, target.container, timeout=timeout)
    if not ready:
        raise ProbeProvisionError(
            f"target {target.id!r} started but did not become ready within {timeout}s"
        )
    return ProbeResetResult(
        target=target,
        container=target.container,
        ip=_container_ip(target.container, network),
        ready=ready,
        elapsed_s=round(time.time() - started, 1),
    )


def teardown_target(target_id: str) -> None:
    target = get_probe_target(target_id)
    _docker(["rm", "-f", target.container])
    for sc in target.sidecars:
        _docker(["rm", "-f", sc.name])


def teardown_all() -> None:
    res = _docker(["ps", "-aq", "--filter", "label=cadis-apb-probe=1"])
    ids = [c for c in res.stdout.split() if c]
    if ids:
        _docker(["rm", "-f", *ids])
