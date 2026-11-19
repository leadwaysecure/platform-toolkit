from platform_toolkit import checks
from platform_toolkit.audit import run_checks


def pod(ns="team-a", name="web", limits=None, scc=None):
    return {
        "metadata": {
            "namespace": ns,
            "name": name,
            "annotations": {"openshift.io/scc": scc} if scc else {},
        },
        "spec": {"containers": [{"name": "app", "resources": {"limits": limits or {}}}]},
    }


def route(ns="team-a", name="web", tls=None):
    return {"metadata": {"namespace": ns, "name": name}, "spec": {"tls": tls}}


def test_missing_limits_flagged():
    findings = list(checks.pods_without_limits([pod(limits={"cpu": "1"})]))
    assert len(findings) == 1
    assert "memory" in findings[0].detail


def test_full_limits_pass():
    assert not list(checks.pods_without_limits([pod(limits={"cpu": "1", "memory": "1Gi"})]))


def test_system_namespaces_skipped():
    assert not list(checks.pods_without_limits([pod(ns="openshift-dns")]))


def test_risky_scc_flagged_restricted_passes():
    assert len(list(checks.pods_with_risky_scc([pod(scc="anyuid")]))) == 1
    assert not list(checks.pods_with_risky_scc([pod(scc="restricted-v2")]))


def test_routes():
    found = list(checks.routes_without_tls([
        route(name="plain"),
        route(name="allow", tls={"insecureEdgeTerminationPolicy": "Allow"}),
        route(name="good", tls={"insecureEdgeTerminationPolicy": "Redirect"}),
    ]))
    assert [f.check for f in found] == ["route-without-tls", "route-allows-http"]


def test_run_checks_sorts_high_first():
    findings = run_checks([pod(limits={})], [route()])
    assert findings[0].severity.value == "high"
