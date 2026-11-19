#!/usr/bin/env bash
# onboard-team.sh: create a tenant project with quota, limits, default-deny
# network policy and an admin RoleBinding for the team's group.
#
# Usage:
#   ./onboard-team.sh -t payments -g payments-devs [-c 4] [-m 8Gi] [--dry-run]
#
# Idempotent: every object goes through `oc apply`, so a second run changes nothing.

set -euo pipefail
IFS=$'\n\t'

readonly SCRIPT_NAME="${0##*/}"

TEAM=""
GROUP=""
CPU="4"
MEMORY="8Gi"
DRY_RUN="false"

usage() {
  cat <<EOF
Usage: ${SCRIPT_NAME} -t TEAM -g GROUP [-c CPU] [-m MEMORY] [--dry-run]

  -t TEAM      team name, becomes the project name (lowercase, a-z0-9-)
  -g GROUP     identity provider group that gets admin on the project
  -c CPU       CPU quota (default: ${CPU})
  -m MEMORY    memory quota (default: ${MEMORY})
  --dry-run    print the manifests instead of applying them
  -h           show this help
EOF
}

log()  { printf '[%s] %s\n' "${SCRIPT_NAME}" "$*" >&2; }
die()  { log "ERROR: $*"; exit 1; }

parse_args() {
  # getopts has no long options, so peel off --dry-run first.
  local args=()
  for arg in "$@"; do
    case "${arg}" in
      --dry-run) DRY_RUN="true" ;;
      *) args+=("${arg}") ;;
    esac
  done
  set -- "${args[@]+"${args[@]}"}"

  while getopts ":t:g:c:m:h" opt; do
    case "${opt}" in
      t) TEAM="${OPTARG}" ;;
      g) GROUP="${OPTARG}" ;;
      c) CPU="${OPTARG}" ;;
      m) MEMORY="${OPTARG}" ;;
      h) usage; exit 0 ;;
      :) die "-${OPTARG} needs a value" ;;
      \?) die "unknown option -${OPTARG}" ;;
    esac
  done

  [[ -n "${TEAM}" ]]  || { usage; die "-t TEAM is required"; }
  [[ -n "${GROUP}" ]] || { usage; die "-g GROUP is required"; }
  [[ "${TEAM}" =~ ^[a-z0-9]([-a-z0-9]*[a-z0-9])?$ ]] || die "invalid team name: ${TEAM}"
}

preflight() {
  [[ "${DRY_RUN}" == "true" ]] && return 0
  command -v oc >/dev/null || die "oc not found in PATH"
  oc whoami >/dev/null 2>&1 || die "not logged in, run: oc login"
}

manifests() {
  cat <<EOF
apiVersion: v1
kind: Namespace
metadata:
  name: ${TEAM}
  labels:
    team: ${TEAM}
    onboarded-by: onboard-team
---
apiVersion: v1
kind: ResourceQuota
metadata:
  name: ${TEAM}-quota
  namespace: ${TEAM}
spec:
  hard:
    requests.cpu: "${CPU}"
    requests.memory: ${MEMORY}
    limits.cpu: "${CPU}"
    limits.memory: ${MEMORY}
---
apiVersion: v1
kind: LimitRange
metadata:
  name: ${TEAM}-limits
  namespace: ${TEAM}
spec:
  limits:
    - type: Container
      default:        { cpu: 500m, memory: 512Mi }
      defaultRequest: { cpu: 100m, memory: 128Mi }
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: default-deny-ingress
  namespace: ${TEAM}
spec:
  podSelector: {}
  policyTypes: [Ingress]
---
apiVersion: networking.k8s.io/v1
kind: NetworkPolicy
metadata:
  name: allow-same-namespace-and-router
  namespace: ${TEAM}
spec:
  podSelector: {}
  ingress:
    - from:
        - podSelector: {}
        - namespaceSelector:
            matchLabels:
              policy-group.network.openshift.io/ingress: ""
---
apiVersion: rbac.authorization.k8s.io/v1
kind: RoleBinding
metadata:
  name: ${TEAM}-admins
  namespace: ${TEAM}
roleRef:
  apiGroup: rbac.authorization.k8s.io
  kind: ClusterRole
  name: admin
subjects:
  - apiGroup: rbac.authorization.k8s.io
    kind: Group
    name: ${GROUP}
EOF
}

main() {
  parse_args "$@"
  preflight

  if [[ "${DRY_RUN}" == "true" ]]; then
    log "dry run: manifests for team '${TEAM}'"
    manifests
    return 0
  fi

  log "applying manifests for team '${TEAM}'"
  manifests | oc apply -f -
  # TODO(you): print a summary with jq, e.g.
  #   oc get resourcequota -n "${TEAM}" -o json | jq '.items[].status'
  log "done. ${GROUP} is admin on project ${TEAM}"
}

main "$@"
