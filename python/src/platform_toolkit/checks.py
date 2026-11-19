"""Pure audit checks.

Each check takes plain dicts (the JSON the Kubernetes API returns) and yields
Findings. No cluster access here, so every check is unit-testable.
"""

from __future__ import annotations

from collections.abc import Iterable, Iterator
from enum import StrEnum

from pydantic import BaseModel

RISKY_SCCS = {"privileged", "anyuid", "hostaccess", "hostmount-anyuid", "hostnetwork"}
SYSTEM_NAMESPACE_PREFIXES = ("openshift", "kube-")


class Severity(StrEnum):
    high = "high"
    medium = "medium"
    low = "low"


class Finding(BaseModel):
    check: str
    severity: Severity
    namespace: str
    name: str
    detail: str


def is_system_namespace(ns: str) -> bool:
    return ns.startswith(SYSTEM_NAMESPACE_PREFIXES) or ns == "default"


def pods_without_limits(pods: Iterable[dict]) -> Iterator[Finding]:
    for pod in pods:
        meta = pod.get("metadata", {})
        ns = meta.get("namespace", "")
        if is_system_namespace(ns):
            continue
        for c in pod.get("spec", {}).get("containers", []):
            limits = (c.get("resources") or {}).get("limits") or {}
            missing = [r for r in ("cpu", "memory") if r not in limits]
            if missing:
                yield Finding(
                    check="pod-without-limits",
                    severity=Severity.medium,
                    namespace=ns,
                    name=meta.get("name", ""),
                    detail=f"container '{c.get('name')}' has no {', '.join(missing)} limit",
                )


def pods_with_risky_scc(pods: Iterable[dict]) -> Iterator[Finding]:
    for pod in pods:
        meta = pod.get("metadata", {})
        ns = meta.get("namespace", "")
        if is_system_namespace(ns):
            continue
        scc = (meta.get("annotations") or {}).get("openshift.io/scc", "")
        if scc in RISKY_SCCS:
            yield Finding(
                check="risky-scc",
                severity=Severity.high,
                namespace=ns,
                name=meta.get("name", ""),
                detail=f"admitted under SCC '{scc}'",
            )


def routes_without_tls(routes: Iterable[dict]) -> Iterator[Finding]:
    for route in routes:
        meta = route.get("metadata", {})
        ns = meta.get("namespace", "")
        if is_system_namespace(ns):
            continue
        tls = route.get("spec", {}).get("tls")
        if not tls:
            yield Finding(
                check="route-without-tls",
                severity=Severity.high,
                namespace=ns,
                name=meta.get("name", ""),
                detail="route serves plain HTTP",
            )
        elif tls.get("insecureEdgeTerminationPolicy") == "Allow":
            yield Finding(
                check="route-allows-http",
                severity=Severity.low,
                namespace=ns,
                name=meta.get("name", ""),
                detail="TLS set but insecureEdgeTerminationPolicy is Allow (use Redirect)",
            )


# TODO(you): add stale_namespaces(namespaces, pods) that flags team namespaces
# with zero running pods, and gpu_allocation(pods) for Phase 2.
