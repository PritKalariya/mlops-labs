#!/usr/bin/env bash
# Idempotent: enables the APIs if needed, creates the repo with its cleanup policy,
# creates the runtime service account (no roles), registers the docker helper.
set -euo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/common.sh"

enabled="$(gcloud services list --enabled --project "$PROJECT" --format='value(config.name)')"
need=()
for api in run.googleapis.com artifactregistry.googleapis.com; do
  grep -qx "$api" <<<"$enabled" || need+=("$api")
done
if ((${#need[@]})); then
  echo "COST: enabling ${need[*]} is free. Teardown: leave enabled (disabling is out of scope)."
  gcloud services enable "${need[@]}" --project "$PROJECT"
else
  echo "APIs already enabled: run.googleapis.com artifactregistry.googleapis.com"
fi

if [[ -n "$(gcloud artifacts repositories list --project "$PROJECT" --location "$REGION" \
      --filter="name ~ /${REPO}\$" --format='value(name)' 2>/dev/null)" ]]; then
  echo "repo $REPO exists"
else
  echo "COST: Artifact Registry repo '$REPO' is free under 0.5 GB, then \$0.10 per GB-month. Teardown: scripts/teardown.sh"
  gcloud artifacts repositories create "$REPO" --project "$PROJECT" --location "$REGION" \
    --repository-format docker --labels purpose=lab5 --description "lab5 Cloud Run images"
fi

policy="$(mktemp)"
trap 'rm -f "$policy"' EXIT
cat >"$policy" <<'JSON'
[
  {"name": "keep-5-most-recent", "action": {"type": "Keep"},
   "mostRecentVersions": {"keepCount": 5}},
  {"name": "delete-untagged-after-1d", "action": {"type": "Delete"},
   "condition": {"tagState": "untagged", "olderThan": "1d"}}
]
JSON
gcloud artifacts repositories set-cleanup-policies "$REPO" --project "$PROJECT" --location "$REGION" \
  --policy "$policy" --no-dry-run

if [[ -n "$(gcloud iam service-accounts list --project "$PROJECT" \
      --filter="email = ${SA_EMAIL}" --format='value(email)')" ]]; then
  echo "service account $SA_EMAIL exists"
else
  echo "COST: a service account is free. Teardown: scripts/teardown.sh"
  gcloud iam service-accounts create "$SA_NAME" --project "$PROJECT" --display-name "lab5 Cloud Run runtime"
fi

if grep -q "$REGISTRY_HOST" "$HOME/.docker/config.json" 2>/dev/null; then
  echo "docker credential helper for $REGISTRY_HOST already registered"
else
  echo "registering docker credential helper for $REGISTRY_HOST (edits ~/.docker/config.json)"
  gcloud auth configure-docker "$REGISTRY_HOST" --quiet
fi
echo "setup done"
