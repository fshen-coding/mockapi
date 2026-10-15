#!/bin/sh
set -eu

KUBECTL=/usr/local/bin/kubectl
CERT_DIR=/etc/mockapi-certs

test -s "$CERT_DIR/fullchain.pem"
test -s "$CERT_DIR/privkey.pem"

"$KUBECTL" -n mockapi create secret tls gateway-tls \
  --cert="$CERT_DIR/fullchain.pem" \
  --key="$CERT_DIR/privkey.pem" \
  --dry-run=client -o yaml | "$KUBECTL" apply -f -
"$KUBECTL" -n mockapi rollout restart deployment/gateway
"$KUBECTL" -n mockapi rollout status deployment/gateway --timeout=120s
