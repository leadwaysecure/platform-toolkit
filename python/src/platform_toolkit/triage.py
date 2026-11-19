"""triage: AI-assisted diagnosis of a broken workload.

    triage web -n kubelings              # collect, redact, ask the model
    triage web -n kubelings --dry-run    # print the prompt, send nothing

Reads only. Needs ANTHROPIC_API_KEY unless --dry-run. Model is set by
TRIAGE_MODEL (default below).
"""

from __future__ import annotations

import os
from typing import Annotated

import typer
from kubernetes import client, config

from platform_toolkit.redact import redact

app = typer.Typer(add_completion=False, help="Diagnose a broken workload with an LLM.")

DEFAULT_MODEL = "claude-sonnet-5-5"
LOG_LINES = 80

MASTER_FLOW = """You are a senior OpenShift platform engineer. Diagnose by walking this chain
in order and stop at the first broken link:
1. DNS: does the name resolve to the Service?
2. Service: does it exist, right port and targetPort?
3. Selector: do the Service selector labels match the pod labels?
4. Endpoints: does the EndpointSlice list ready pod IPs?
5. Pod: is it Running and Ready? If not, why (image, scheduling, crash, probe)?
6. Port: is the app listening on the containerPort?
7. App: what do the logs say?
8. Policy: is a NetworkPolicy or SCC blocking it?
Answer in this format:
FAILING LINK: <number and name>
EVIDENCE: <the exact lines from the input that prove it>
FIX: <the command or manifest change>
CONFIDENCE: <high, medium or low, and what you would check next>"""


def load_kube() -> client.ApiClient:
    try:
        config.load_incluster_config()
    except config.ConfigException:
        config.load_kube_config()
    return client.ApiClient()


def collect(api: client.ApiClient, deployment: str, namespace: str) -> str:
    apps, core = client.AppsV1Api(api), client.CoreV1Api(api)
    parts: list[str] = []

    dep = apps.read_namespaced_deployment(deployment, namespace)
    selector = dep.spec.selector.match_labels or {}
    label_sel = ",".join(f"{k}={v}" for k, v in selector.items())
    parts.append(f"## Deployment {namespace}/{deployment}\nselector: {selector}\n"
                 f"replicas: {dep.status.ready_replicas or 0}/{dep.spec.replicas}")

    for svc in core.list_namespaced_service(namespace).items:
        parts.append(f"## Service {svc.metadata.name}\nselector: {svc.spec.selector}\n"
                     f"ports: {[(p.port, p.target_port) for p in svc.spec.ports or []]}")

    pods = core.list_namespaced_pod(namespace, label_selector=label_sel).items
    for pod in pods:
        name = pod.metadata.name
        statuses = [
            (cs.name, cs.ready, cs.restart_count, cs.state.to_dict())
            for cs in pod.status.container_statuses or []
        ]
        parts.append(f"## Pod {name}\nlabels: {pod.metadata.labels}\nphase: {pod.status.phase}\n"
                     f"containers: {statuses}")
        try:
            logs = core.read_namespaced_pod_log(name, namespace, tail_lines=LOG_LINES)
            parts.append(f"### Logs {name} (last {LOG_LINES} lines)\n{logs}")
        except client.ApiException as exc:
            parts.append(f"### Logs {name}: unavailable ({exc.reason})")

    events = core.list_namespaced_event(namespace).items[-30:]
    parts.append("## Recent events\n" + "\n".join(
        f"{e.type} {e.reason} {e.involved_object.kind}/{e.involved_object.name}: {e.message}"
        for e in events
    ))
    # TODO(you): add EndpointSlices and NetworkPolicies to the evidence.
    return "\n\n".join(parts)


def ask_model(evidence: str) -> str:
    import anthropic  # imported here so --dry-run works without the SDK configured

    resp = anthropic.Anthropic().messages.create(
        model=os.environ.get("TRIAGE_MODEL", DEFAULT_MODEL),
        max_tokens=1024,
        system=MASTER_FLOW,
        messages=[{"role": "user", "content": evidence}],
    )
    return "".join(block.text for block in resp.content if block.type == "text")


@app.command()
def main(
    deployment: Annotated[str, typer.Argument(help="deployment name")],
    namespace: Annotated[str, typer.Option("--namespace", "-n")],
    dry_run: Annotated[
        bool, typer.Option("--dry-run", help="print the prompt, send nothing")
    ] = False,
) -> None:
    evidence = redact(collect(load_kube(), deployment, namespace))
    if dry_run:
        typer.echo(f"--- SYSTEM ---\n{MASTER_FLOW}\n\n--- EVIDENCE ---\n{evidence}")
        return
    typer.echo(ask_model(evidence))


if __name__ == "__main__":
    app()
