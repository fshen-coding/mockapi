#!/bin/sh
set -eu

KUBECTL=/usr/local/bin/kubectl
"$KUBECTL" -n mockapi scale deployment/gateway --replicas=0
"$KUBECTL" -n mockapi wait --for=delete pod -l app=gateway --timeout=90s
