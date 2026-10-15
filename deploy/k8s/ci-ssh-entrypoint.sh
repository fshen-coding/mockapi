#!/usr/bin/env bash
set -Eeuo pipefail

readonly DEPLOY_SCRIPT="/opt/mockapi-deploy/deploy-image.sh"
command="${SSH_ORIGINAL_COMMAND:-}"

case "$command" in
  "deploy-mockapi-sit "*)
    target="sit"
    image="${command#"deploy-mockapi-sit "}"
    ;;
  "deploy-mockapi "*)
    target="production"
    image="${command#"deploy-mockapi "}"
    ;;
  *)
    echo "This SSH key may only deploy MockAPI." >&2
    exit 126
    ;;
esac

if [[ -z "$image" || "$image" == *[[:space:]]* ]]; then
  echo "Invalid image argument." >&2
  exit 64
fi

exec "$DEPLOY_SCRIPT" "$image" "$target"
