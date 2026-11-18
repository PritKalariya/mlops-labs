#!/usr/bin/env bash
# Idempotent. Deletes everything the lab created, then prints the proof commands.
set -uo pipefail
here="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
source "$here/common.sh"

main() {
  for svc in "$SERVICE" "$BASELINE_SERVICE"; do
    if [[ -n "$(gcloud run services list --project "$PROJECT" --region "$REGION" \
          --filter="metadata.name = ${svc}" --format='value(metadata.name)')" ]]; then
      echo "deleting service $svc (its revisions go with it)"
      gcloud run services delete "$svc" --project "$PROJECT" --region "$REGION" --quiet
    fi
  done

  if [[ -n "$(gcloud artifacts repositories list --project "$PROJECT" --location "$REGION" \
        --filter="name ~ /${REPO}\$" --format='value(name)')" ]]; then
    echo "deleting repo $REPO (its images go with it)"
    gcloud artifacts repositories delete "$REPO" --project "$PROJECT" --location "$REGION" --quiet
  fi

  if [[ -n "$(gcloud iam service-accounts list --project "$PROJECT" \
        --filter="email = ${SA_EMAIL}" --format='value(email)')" ]]; then
    echo "keys on $SA_EMAIL (only SYSTEM_MANAGED expected):"
    keys="$(gcloud iam service-accounts keys list --iam-account "$SA_EMAIL" --project "$PROJECT" \
            --format='value(name.basename(),keyType)')"
    echo "$keys"
    if grep -q USER_MANAGED <<<"$keys"; then
      echo "user-managed key found on $SA_EMAIL, not deleting the service account" >&2
      return 1
    fi
    echo "deleting service account $SA_EMAIL"
    gcloud iam service-accounts delete "$SA_EMAIL" --project "$PROJECT" --quiet
  fi

  # Local containers are always started with these fixed names.
  docker rm -f lab5-local lab5-bad lab5-baseline-test >/dev/null 2>&1 || true
  imgs="$(docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -E '^lab5|pkg\.dev/boston-resilience-twin/lab5' || true)"
  [[ -z "$imgs" ]] || docker image rm $imgs

  rm -rf /tmp/lab5-clean /tmp/lab5-baseline

  echo
  echo "== proof: each of these prints nothing =="
  gcloud run services list --project "$PROJECT" --region "$REGION" --filter='metadata.name ~ ^lab5-' --format='value(metadata.name)' 2>/dev/null
  gcloud artifacts repositories list --project "$PROJECT" --location "$REGION" --filter='name ~ /lab5$' --format='value(name)' 2>/dev/null
  gcloud iam service-accounts list --project "$PROJECT" --filter='email ~ ^lab5-' --format='value(email)' 2>/dev/null
  docker image ls --format '{{.Repository}}:{{.Tag}}' | grep -E 'lab5|pkg.dev/boston-resilience-twin/lab5' || true
  echo "== end of proof =="
}

main "$@"
exit $?
