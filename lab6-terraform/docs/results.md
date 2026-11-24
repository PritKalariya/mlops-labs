# Results

Project `boston-resilience-twin`, region `us-east1`. Run date 2026-11-24. All times are UTC.

## Versions

| Item | Version |
|---|---|
| Terraform | 1.17.2 (roots pin `= 1.17.2`; modules require `>= 1.7`) |
| `hashicorp/google` provider | 8.12.0 (roots pin `= 8.12.0`; modules require `>= 6.0`) |
| Ubuntu | 26.04.1 LTS |
| Docker | 29.10.0 |
| gcloud | 594.0.0 |

## Static and offline checks

| Check | Result |
|---|---|
| `terraform fmt -check -recursive` | exit 0 |
| `terraform validate`, `stacks/registry` and `stacks/serving` | pass |
| `terraform test` in `modules/serving`, credentials hidden | 8 passed, 0 failed |

The 8 runs are: one valid plan (probes, paths, concurrency, caps, request-based CPU, labels, service account, no public member, uptime and alert settings), one warm-instances-allowed plan, and six `expect_failures` runs (image tag, `max_instances` above 3, `concurrency` above 80, `min_instances` above 0 without `allow_warm`, labels without `purpose`, public invoker).

## Plans and apply times

| Stack | Plan | Apply | Wall time |
|---|---|---|---|
| `registry` | 1 add, 0 change, 0 destroy | 1 added | 11 s |
| `serving`, first apply | 6 add, 0 change, 0 destroy | stopped after 3 resources (channel, service account 19 s, Cloud Run service 41 s) | 62 s |
| `serving`, completed over the next runs | 3 add, 0 change, 0 destroy | 3 added | under 10 s |
| `serving`, demo 2 apply | 0 add, 1 change, 0 destroy | 1 changed | 23 s |
| `serving`, request-based CPU apply | 0 add, 1 change, 0 destroy | 1 changed | 23 s |

The first `serving` apply stopped because the Monitoring service agent does not exist until an OIDC uptime check has been created. The module now creates the uptime check first and binds the invoker role after it.

## Images and revisions

| Item | Value |
|---|---|
| v1 digest | `us-east1-docker.pkg.dev/boston-resilience-twin/lab6/forecast@sha256:97c9493089da05a7267a71e52f53e512d80bfa89712736b457a8a5a757ce7054` |
| v2 digest (same code, `--label lab6.build=v2`) | `us-east1-docker.pkg.dev/boston-resilience-twin/lab6/forecast@sha256:ebe049aeef9ffb48299de2345602a8d9ca7f7284b857a65b6a59889964270639` |
| Revision 1 | `lab6-forecast-00001-bkm`, from Terraform, serves v1 |
| Revision 2 | `lab6-forecast-00002-t6n`, from `gcloud run deploy`, serves v2 |
| Revision 3 | `lab6-forecast-00003-wpp`, from `gcloud run services update --max-instances 3` |
| Revision 4 | `lab6-forecast-00004-5p8`, from the Terraform apply that restored max 2 |
| Revision 5 | `lab6-forecast-00005-5v8`, from the Terraform apply that set request-based CPU |

## Service settings (`gcloud run services describe`)

| Setting | Value |
|---|---|
| Image | pinned by digest |
| Startup probe | `GET /health/ready`, period 2 s, timeout 1 s, failure threshold 30 |
| Liveness probe | `GET /health/live`, period 10 s, timeout 1 s, failure threshold 3 |
| Concurrency | 10 |
| Scale | min 0, max 2 |
| CPU and memory | 1 CPU, 512Mi, request-based CPU (`cpu-throttling=true`) |
| Port | 8080 |
| Runtime service account | `lab6-run@boston-resilience-twin.iam.gserviceaccount.com` |
| Label | `purpose=lab6` |
| IAM policy | one binding: `roles/run.invoker` for the Monitoring service agent; no `allUsers` or `allAuthenticatedUsers` |
| Unauthenticated `curl` | 403 |
| `curl` with an identity token, `/health/ready` | 200, `{"status":"ready","model_version":"1.0.0"}` |

## Demos

| Demo | Command | Result |
|---|---|---|
| 1. Ownership split | `gcloud run deploy lab6-forecast --image <v2 digest>`, then `terraform plan -detailed-exitcode` | plan exit **0**; revision 2 serves v2 |
| 1, counterfactual | same plan in a copy with `ignore_changes` removed (never applied) | exit 2, would revert the image |
| 2. Drift | `gcloud run services update lab6-forecast --max-instances 3`, then plan | plan exit **2**: `max_instance_count = 3 -> 2`; after apply, plan exit **0** |
| 3. Validation | plans with a tag image, `max_instances = 10`, and `invoker_members = ["allUsers"]` | each exit **1** with its message; no resources changed; a clean plan after exits 0 |
| 4. Alert | see below | incident opened and closed |

The image line from the counterfactual plan (`ignore_changes` removed, v2 serving, configuration still on v1):

```
~ image            = "us-east1-docker.pkg.dev/boston-resilience-twin/lab6/forecast@sha256:ebe049aeef9ffb48299de2345602a8d9ca7f7284b857a65b6a59889964270639" -> "us-east1-docker.pkg.dev/boston-resilience-twin/lab6/forecast@sha256:97c9493089da05a7267a71e52f53e512d80bfa89712736b457a8a5a757ce7054"
```

The same counterfactual plan also showed `client = "gcloud" -> null` and `client_version = "594.0.0" -> null` (2 more lines, 1 resource changed).

### Demo 3 messages

| Input | Message |
|---|---|
| tag image | `image must be pinned by digest, as <registry>/<path>@sha256:<64 hex characters>. A tag can move; build_push.sh prints the digest reference to use.` |
| `max_instances = 10` | `max_instances must be between 1 and 3 to keep the cost bounded. Lower it, or change this rule in the module if a higher cap is intended.` |
| `allUsers` invoker | `invoker_members must not include allUsers or allAuthenticatedUsers: the service is private. Name the user, group or service account that needs access.` |

### Demo 4 timeline (`uptime_path = "/does-not-exist"`)

| Event | Time |
|---|---|
| Broken path applied | 21:30:14 |
| First `check_passed = False` datapoint | 21:32:20 (2 min 6 s after the apply) |
| Alert filter corrected and applied | 21:42:43 |
| Incident opened (`ViolationOpenEventv1`) | 21:44:32 (1 min 49 s after the corrected policy was applied) |
| Path restored and applied | 21:50:46 |
| First `check_passed = True` datapoint | 21:53:20 |
| Incident closed (`ViolationAutoResolveEventv1`) | 21:54:38 (3 min 52 s after the restore apply) |

The first alert policy filtered on `resource.type="uptime_url"` while the check writes `cloud_run_revision` series, so no incident opened between 21:32 and 21:42 although all three regions were failing. The filter now takes the type from the check itself, and a test asserts it.

Incident times come from Cloud Logging (`monitoring.googleapis.com/ViolationOpenEventv1` and `ViolationAutoResolveEventv1`, `violation_id` `0.ofegly9yu63q`); Cloud Monitoring's v3 API does not list incidents.

## Cleanup policy (`gcloud artifacts repositories list-cleanup-policies lab6 --location us-east1`)

```
Dry run is disabled.
[
  {"action": {"type": "DELETE"}, "condition": {"olderThan": "86400s", "tagState": "UNTAGGED"}, "name": "delete-untagged-after-1d"},
  {"action": {"type": "KEEP"}, "mostRecentVersions": {"keepCount": 5}, "name": "keep-5-most-recent"}
]
```

## Costs

| Resource | Cost while it exists |
|---|---|
| Artifact Registry repository `lab6` (about 300 MB with two images) | free under 0.5 GB |
| Cloud Run service `lab6-forecast` (min 0, request-based CPU) | billed only during requests; uptime pings cost cents a day |
| Uptime check (3 regions, every 60 s, about 130,000 executions a month) | free under 1,000,000 executions a month, then $0.30 per 1,000 |
| Alert policy | no charge today; Google's pricing page states alerting charges start no sooner than 2027-09-01 |
| Service account, notification channel | free |

## Clean-copy run

Run from a copy of the committed files (plus `terraform.tfvars` and the Lab 5 app source), following only the README.

| Step | Result |
|---|---|
| `terraform test` (credentials hidden) | 8 passed, 0 failed |
| `registry` apply | 1 added, 12 s |
| v1 and v2 digests | identical to the first run (the build is reproducible) |
| `serving` apply | 6 added, 0 changed, 0 destroyed, 41 s, in one pass |
| Unauthenticated `curl` / identity-token `curl` | 403 / 200 |
| Demo 1 | `gcloud run deploy` created `lab6-forecast-00002-7rb` (v2); plan exit 0 |
| Demo 2 | max 3 gave plan exit 2 (`3 -> 2`); apply 22 s; plan exit 0 afterwards |
| Demo 3 | tag image, `max_instances = 10`, `allUsers`: three plans exit 1; clean plan exit 0; 4 revisions before and after |
| Demo 4, broken path applied | 22:10:03 |
| Demo 4, first `check_passed = False` datapoint | 22:12:00 (1 min 57 s after the apply) |
| Demo 4, incident opened (`ViolationOpenEventv1`, `0.ofehatk8p2bs`) | 22:14:47 (2 min 47 s after the first failure); alert email received at 17:14 EST |
| Demo 4, path restore | not run; the teardown destroyed the check |
| Teardown | `serving` 6 destroyed (19 s), `registry` 1 destroyed (1 s); both states empty |

The first run's teardown took 18 s for `serving` and 1 s for `registry`.
