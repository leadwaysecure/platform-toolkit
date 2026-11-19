# platform-toolkit

Four tools for running an OpenShift platform, built in Phase 1 of the blueprint.

| Tool | Language | What it does |
| --- | --- | --- |
| `bash/onboard-team.sh` | Bash | One command creates a team project with quota, LimitRange, default-deny NetworkPolicy and an admin RoleBinding. Idempotent, `--dry-run`. |
| `platform-audit` | Python | Flags pods without limits, pods on risky SCCs and Routes without TLS. Table or JSON, nonzero exit for pipelines, runs nightly as a CronJob. |
| `triage` | Python + LLM | Collects a broken workload's evidence, redacts secrets, and asks a model to walk the troubleshooting chain and name the failing link. Read-only. |
| `developer-hub/templates/new-service` | Backstage template | Golden path: scaffolds a repo with Dockerfile, Helm chart and catalog entry, then registers it in Developer Hub. |

Every `TODO(you)` marks an extension to build yourself. The starter code works; the TODOs are where the learning is.

## Quick start

```bash
make setup          # install the Python package and dev tools
make check          # shellcheck, ruff, pytest, dry-run smoke test
```

Log in to your cluster first (Developer Sandbox or OpenShift Local), then:

```bash
./bash/onboard-team.sh -t payments -g payments-devs --dry-run   # look first
./bash/onboard-team.sh -t payments -g payments-devs             # apply

platform-audit                    # table, exit 1 on any high finding
platform-audit -o json --fail-on medium

triage web -n kubelings --dry-run # see exactly what would be sent
export ANTHROPIC_API_KEY=...      # then ask for real
triage web -n kubelings
```

On Developer Sandbox you are not cluster-admin, so `onboard-team.sh` and the cluster-wide audit need OpenShift Local. `triage` works in your own Sandbox project.

## Run the audit in-cluster

```bash
make image && podman push quay.io/YOUR_ORG/platform-toolkit:0.1.0
oc apply -f deploy/audit-cronjob.yaml
oc create job --from=cronjob/platform-audit audit-now -n platform-tools
oc logs -n platform-tools job/audit-now
```

## Working with an AI assistant

Use Claude Code or Copilot to draft each TODO, then before you commit:

1. Read every line and explain it out loud. If you can't, ask the assistant to explain, then rewrite it yourself.
2. Break it on purpose (wrong label, missing permission) and check the error is clear.
3. Add a test in `python/tests/` for every new check.
4. Run `make check`. CI runs the same thing on every push.

## Suggested TODO order

1. `onboard-team.sh`: print a jq summary of the quota after apply.
2. `checks.py`: `stale_namespaces`, then `gpu_allocation` (for Phase 2).
3. `triage.py`: add EndpointSlices and NetworkPolicies to the evidence.
4. `template.yaml`: open a pull request against your Argo CD repo.
5. Add a `--namespace` filter to `platform-audit`.
