#!/usr/bin/env bash
# Builds the v4 image from a temporary copy of app/ with two request features swapped
# in the serving code (petal_length and petal_width): a training/serving skew bug.
# The model itself is untouched, so readiness and the version check still pass.
# usage: scripts/make_bad_image.sh  -> builds and prints the local tag; does not push
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/common.sh"
tmp="$(mktemp -d)"
trap 'rm -rf "$tmp"' EXIT
cp -r "$here/../app/." "$tmp/"

python3 - "$tmp/src/main.py" <<'PY'
import sys
path = sys.argv[1]
src = open(path).read()
good = "iris_features.petal_length, iris_features.petal_width]]"
bad = "iris_features.petal_width, iris_features.petal_length]]"
assert src.count(good) == 1, "serving code changed, update the swap"
open(path, "w").write(src.replace(good, bad))
PY

docker build --platform linux/amd64 --target runtime --provenance=false --sbom=false \
  --build-arg MODEL_VERSION=1.2.0 -t "${IMAGE_NAME}:v4" "$tmp" >&2
echo "${IMAGE_NAME}:v4"
