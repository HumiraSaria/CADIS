"""Unit tests for the digest-pinned target registry (pure; no Docker)."""

import re

import pytest

from benchmark.targets.registry import (
    BENCH_NETWORK,
    REGISTRY,
    Target,
    get_target,
    list_targets,
    target_ids,
)

_DIGEST_RE = re.compile(r"^[\w./-]+@sha256:[0-9a-f]{64}$")


def test_executable_core_targets_present():
    # The original digest-pinned core (v1) must always be present; the v2/§17 effort
    # may add further difficulty-spanning targets (e.g. webgoat).
    assert {"dvwa-sqli", "msf2-vsftpd", "juice-shop"} <= set(target_ids())


def test_every_image_is_digest_pinned():
    for t in list_targets():
        assert _DIGEST_RE.match(t.image), f"{t.id} image not digest-pinned: {t.image}"


def test_difficulty_spans_easy_medium_hard():
    assert {t.difficulty for t in list_targets()} == {"easy", "medium", "hard"}


def test_container_names_are_namespaced_and_unique():
    names = [t.container for t in list_targets()]
    assert all(n.startswith("cadis-") for n in names)
    assert len(set(names)) == len(names)


def test_every_target_has_objective_and_valid_protocol():
    for t in list_targets():
        assert t.objective.strip()
        assert t.protocol in ("http", "tcp")
        assert t.port > 0


def test_get_target_and_unknown_raises():
    assert get_target("dvwa-sqli").tag == "vulnerables/web-dvwa:latest"
    with pytest.raises(KeyError):
        get_target("does-not-exist")


def test_registry_values_are_target_instances():
    assert all(isinstance(t, Target) for t in REGISTRY.values())


def test_bench_network_name():
    assert BENCH_NETWORK == "cadis-bench-net"
