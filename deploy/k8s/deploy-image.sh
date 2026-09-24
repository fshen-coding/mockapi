#!/usr/bin/env bash
set -Eeuo pipefail

readonly NAMESPACE="mockapi"
readonly DEPLOYMENT="mockapi"
readonly CONTAINER="mockapi"

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

echo "Deploying $image (current: $previous_image)"
patch_image "$image" "IfNotPresent"

if kubectl -n "$NAMESPACE" rollout status "deployment/$DEPLOYMENT" --timeout=300s; then
  kubectl -n "$NAMESPACE" get pods -l app=mockapi -o wide
  exit 0
fi

echo "Rollout failed; restoring $previous_image" >&2
patch_image "$previous_image" "${previous_pull_policy:-IfNotPresent}"
kubectl -n "$NAMESPACE" rollout status "deployment/$DEPLOYMENT" --timeout=300s
exit 1
