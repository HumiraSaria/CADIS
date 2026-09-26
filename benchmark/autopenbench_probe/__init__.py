"""AutoPenBench probe line (isolated) — newplan.md §8/§10, deviation D8.

A *new isolated* probe that adds two AutoPenBench targets as CADIS targets to test whether
the pre-registered hallucination-cascade (HCR) boundary condition is driven by target
difficulty. It reuses the frozen scoring core (engine/gate/recorder/policy) verbatim; it does
NOT import or mutate the frozen S13 target registry, and it writes only to
``benchmark/runs_autopenbench_probe/`` (git-ignored) and
``benchmark/results_autopenbench_probe/``.

Scope (design doc ``benchmark/autopenbench_probe/DESIGN.md``, signed off 2026-09-25):
  - Tasks: ``apb-web-sqli`` (AutoPenBench in-vitro web_security/vm3) and ``apb-heartbleed``
    (AutoPenBench real-world cve/vm10, CVE-2014-0160).
  - Condition: full_autonomy ONLY; R=2; N=5 USC sampler OFF (L0 ignores USC).
  - Success oracle (D8): flag-artifact detection — the planted flag string appears in the
    agent's captured tool output. The pre-registered HCR/cascade rule + outcome classifier
    (v0.2.0) are UNCHANGED.
"""

from __future__ import annotations

__all__ = ["targets", "oracle", "provision", "driver"]
