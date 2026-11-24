#!/usr/bin/env bash
# usage: scripts/teardown.sh
# Destroys the serving stack, then the registry stack (the order matters: serving uses the
# registry's images). Safe to run again: a stack with nothing in its state is skipped.
# Terraform asks for confirmation on each destroy; pipe `yes` to skip the prompts.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# The image variable is validated but not used by destroy, so a placeholder digest is enough.
placeholder="example/image@sha256:$(printf '0%.0s' {1..64})"

destroy_stack() {
  local name="$1"; shift
  local dir="$here/../stacks/$name"
  cd "$dir"
  terraform init -input=false >/dev/null
  if [[ -z "$(terraform state list 2>/dev/null)" ]]; then
    echo "$name: nothing in state, skipping"
    return 0
  fi
  echo "$name: destroying"
  terraform destroy -input=false "$@"
}

destroy_stack serving -var "image=${placeholder}"
destroy_stack registry
echo "teardown finished"
