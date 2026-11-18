#!/usr/bin/env bash
# usage: scripts/build_push.sh <tag> [model_version]
# Builds the runtime image for linux/amd64, pushes it, prints the reference by digest
# as the last line: <image>@sha256:<hex>
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/common.sh"
tag="${1:?usage: build_push.sh <tag> [model_version]}"
version="${2:-1.0.0}"

docker build --platform linux/amd64 --target runtime --provenance=false --sbom=false \
  --build-arg "MODEL_VERSION=${version}" -t "${IMAGE_NAME}:${tag}" "$here/../app" >&2
echo "built ${IMAGE_NAME}:${tag} model ${version}" >&2

echo "COST: pushing ${IMAGE_NAME}:${tag} adds ~150 MB to repo '${REPO}': free under 0.5 GB, then \$0.10 per GB-month. Teardown: scripts/teardown.sh" >&2
digest="$(docker push "${IMAGE_NAME}:${tag}" | tee /dev/stderr | sed -n 's/.*digest: \(sha256:[0-9a-f]\{64\}\).*/\1/p' | tail -1)"
[[ -n "$digest" ]] || { echo "no digest found in push output" >&2; exit 1; }
echo "${IMAGE_NAME}@${digest}"
