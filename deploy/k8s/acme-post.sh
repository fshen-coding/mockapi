#!/bin/sh
set -eu

KUBECTL=/usr/local/bin/kubectl
"$KUBECTL" -n mockapi scale deployment/gateway --replicas=1
"$KUBECTL" -n mockapi rollout status deployment/gateway --timeout=120s
