#!/usr/bin/env bash
set -Eeuo pipefail

readonly NAMESPACE="mockapi"
readonly DEPLOYMENT="mockapi"
readonly CONTAINER="mockapi"
readonly ROLLOUT_TIMEOUT="1200s"
readonly ROLLBACK_TIMEOUT="300s"

image="${1:-}"
if [[ ! "$image" =~ ^ghcr\.io/fshen1999/mockapi:sha-[0-9a-f]{40}$ ]]; then
  echo "Refusing unexpected image: $image" >&2
  exit 64
fi

previous_image="$(kubectl -n "$NAMESPACE" get deployment "$DEPLOYMENT" -o jsonpath="{.spec.template.spec.containers[?(@.name=='$CONTAINER')].image}")"
previous_pull_policy="$(kubectl -n "$NAMESPACE" get deployment "$DEPLOYMENT" -o jsonpath="{.spec.template.spec.containers[?(@.name=='$CONTAINER')].imagePullPolicy}")"
if [[ -z "$previous_image" ]]; then
  echo "Unable to read the currently deployed image." >&2
  exit 65
fi

patch_image() {
  local next_image="$1"
  local next_pull_policy="$2"
  kubectl -n "$NAMESPACE" patch "deployment/$DEPLOYMENT" --type=strategic -p \
    "{\"spec\":{\"template\":{\"spec\":{\"containers\":[{\"name\":\"$CONTAINER\",\"image\":\"$next_image\",\"imagePullPolicy\":\"$next_pull_policy\"}]}}}}"
}

print_rollout_diagnostics() {
  echo "--- deployment ---" >&2
  kubectl -n "$NAMESPACE" get deployment "$DEPLOYMENT" -o wide >&2 || true
  echo "--- pods ---" >&2
  kubectl -n "$NAMESPACE" get pods -l app=mockapi -o wide >&2 || true
  echo "--- recent events ---" >&2
  kubectl -n "$NAMESPACE" get events --sort-by=.lastTimestamp | tail -40 >&2 || true
  echo "--- container logs ---" >&2
  kubectl -n "$NAMESPACE" logs -l app=mockapi --all-containers=true --tail=200 >&2 || true
}

echo "Deploying $image (current: $previous_image)"
patch_image "$image" "IfNotPresent"

if kubectl -n "$NAMESPACE" rollout status "deployment/$DEPLOYMENT" --timeout="$ROLLOUT_TIMEOUT"; then
  kubectl -n "$NAMESPACE" get pods -l app=mockapi -o wide
  exit 0
fi

echo "Rollout failed; collecting diagnostics before restoring $previous_image" >&2
print_rollout_diagnostics
echo "Restoring $previous_image" >&2
patch_image "$previous_image" "${previous_pull_policy:-IfNotPresent}"
if ! kubectl -n "$NAMESPACE" rollout status "deployment/$DEPLOYMENT" --timeout="$ROLLBACK_TIMEOUT"; then
  echo "Rollback did not become ready." >&2
  print_rollout_diagnostics
  exit 1
fi
exit 1
