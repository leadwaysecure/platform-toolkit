"""platform-audit: run the checks against a live cluster.

    platform-audit                 # table output, exit 1 on any high finding
    platform-audit --output json   # for pipelines
    platform-audit --fail-on medium
"""

from __future__ import annotations

import json
from enum import StrEnum
from typing import Annotated

import typer
from kubernetes import client, config

from platform_toolkit import checks
from platform_toolkit.checks import Finding, Severity

app = typer.Typer(add_completion=False, help="Audit an OpenShift cluster for common risks.")

ORDER = {Severity.low: 0, Severity.medium: 1, Severity.high: 2}


class Output(StrEnum):
    table = "table"
    json = "json"


def load_kube() -> client.ApiClient:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.ApiClient()


def fetch(api: client.ApiClient) -> tuple[list[dict], list[dict]]:
    core = client.CoreV1Api(api)
    pods = api.sanitize_for_serialization(core.list_pod_for_all_namespaces().items)
    custom = client.CustomObjectsApi(api)
    try:
        routes = custom.list_cluster_custom_object("route.openshift.io", "v1", "routes")["items"]
    except client.ApiException as exc:
        if exc.status != 404:
            raise
        routes = []  # plain Kubernetes, no Routes
    return pods, routes


def run_checks(pods: list[dict], routes: list[dict]) -> list[Finding]:
    findings: list[Finding] = []
    findings += checks.pods_without_limits(pods)
    findings += checks.pods_with_risky_scc(pods)
    findings += checks.routes_without_tls(routes)
    return sorted(findings, key=lambda f: (-ORDER[f.severity], f.namespace, f.name))


def print_table(findings: list[Finding]) -> None:
    if not findings:
        typer.echo("No findings.")
        return
    typer.echo(f"{'SEVERITY':<8}  {'CHECK':<20}  {'NAMESPACE/NAME':<45}  DETAIL")
    for f in findings:
        target = f"{f.namespace}/{f.name}"
        typer.echo(f"{f.severity.value:<8}  {f.check:<20}  {target:<45}  {f.detail}")


@app.command()
def main(
    output: Annotated[Output, typer.Option("--output", "-o")] = Output.table,
    fail_on: Annotated[
        Severity, typer.Option(help="exit 1 if any finding is at or above this")
    ] = Severity.high,
) -> None:
    pods, routes = fetch(load_kube())
    findings = run_checks(pods, routes)

    if output is Output.json:
        typer.echo(json.dumps([f.model_dump(mode="json") for f in findings], indent=2))
    else:
        print_table(findings)

    if any(ORDER[f.severity] >= ORDER[fail_on] for f in findings):
        raise typer.Exit(code=1)


if __name__ == "__main__":
    app()
