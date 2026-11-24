#!/usr/bin/env bash
# usage: scripts/build_push.sh <tag> [build-label]
# Builds the forecast image from lab5-cloud-run/app for linux/amd64, pushes it to the lab6
# repository, and prints the reference by digest as the last line: <image>@sha256:<hex>
# A build-label such as v2 is stored as the image label lab6.build=v2, which changes the
# image config and so gives the same code a new digest.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
app="$here/../../lab5-cloud-run/app"

IMAGE_NAME=us-east1-docker.pkg.dev/boston-resilience-twin/lab6/forecast
tag="${1:?usage: build_push.sh <tag> [build-label]}"
build_label="${2:-}"

label_args=()
[[ -n "$build_label" ]] && label_args=(--label "lab6.build=${build_label}")

docker build --platform linux/amd64 --target runtime --provenance=false --sbom=false \
  "${label_args[@]}" -t "${IMAGE_NAME}:${tag}" "$app" >&2
echo "built ${IMAGE_NAME}:${tag}" >&2

echo "COST: pushing ${IMAGE_NAME}:${tag} adds about 150 MB to repository lab6: free under 0.5 GB, then \$0.10 per GB-month. Teardown: scripts/teardown.sh" >&2
push_log="$(docker push "${IMAGE_NAME}:${tag}" 2>&1)" || { echo "$push_log" >&2; exit 1; }
echo "$push_log" >&2
digest="$(sed -n 's/.*digest: \(sha256:[0-9a-f]\{64\}\).*/\1/p' <<<"$push_log" | tail -1)"
[[ -n "$digest" ]] || { echo "no digest found in push output" >&2; exit 1; }
echo "${IMAGE_NAME}@${digest}"
