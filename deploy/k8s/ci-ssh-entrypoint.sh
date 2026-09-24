#!/usr/bin/env bash
set -Eeuo pipefail

readonly DEPLOY_SCRIPT="/opt/mockapi-deploy/deploy-image.sh"
readonly COMMAND_PREFIX="deploy-mockapi "
command="${SSH_ORIGINAL_COMMAND:-}"

if [[ "$command" != "$COMMAND_PREFIX"* ]]; then
  echo "This SSH key may only deploy MockAPI." >&2
  exit 126
fi

image="${command#"$COMMAND_PREFIX"}"
if [[ "$image" == *[[:space:]]* ]]; then
  echo "Invalid image argument." >&2
  exit 64
fi

exec "$DEPLOY_SCRIPT" "$image"
