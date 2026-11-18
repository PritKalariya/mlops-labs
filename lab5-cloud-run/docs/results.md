# Results

Measured on 2026-11-18 (UTC) against project `boston-resilience-twin`, region `us-east1`. Gate and canary traffic came from one laptop over the internet, so latencies include the network round trip.

## Environment

| Item | Value |
|---|---|
| Google Cloud CLI | 594.0.0 |
| Docker Engine | 29.10.0 |
| Host | Ubuntu 26.04.1 LTS, Python 3.14.4 (tool venv) |
| Image base | `python:3.12-slim` pinned by digest, Python 3.12 |
| Cloud Run execution environment | Default (not set), as shown on the revision's Console page |
| Startup CPU boost | Enabled, as shown on the revision's Console page (this gcloud version sets `run.googleapis.com/startup-cpu-boost: true` on deploy) |
| Memory setting used | 512 Mi on every revision. No revision was OOM-killed, so it was never raised |
| Other service settings | 1 vCPU, concurrency 10, min instances 0 (no `minScale` annotation, the default), max instances 2, label `purpose=lab5`, service account `lab5-run`, no `allUsers` binding |

## Images

| Tag | Model version | Digest (as pushed) | Compressed in Artifact Registry |
|---|---|---|---|
| `v1` | 1.0.0 | `sha256:97c9493089da05a7267a71e52f53e512d80bfa89712736b457a8a5a757ce7054` | 141,503,276 B (141.5 MB) |
| `v2` | 1.1.0 | `sha256:3caa36c034d6fa70c427b70a6f05e74211bbb1b7372baaf7b4b2293c7201ae4e` | 141,503,275 B (141.5 MB) |
| `v4` (skewed) | 1.2.0 | `sha256:0762294cf2e3a078c6f14a1868b557d0f540ed8663ce421f0c687bdbd68f40b0` | 141,503,275 B (141.5 MB) |

`v3` is the `v2` digest with `IRIS_ARTIFACT_VERSION=9.9.9` set at deploy time, so it has no image of its own. The repository held 389.9 MB with these three images (layers are shared).

No unpacked size is reported for these images. `docker image inspect` printed 611,635,966 B on this host's containerd image store, but that figure is unpacked plus compressed content, and no `docker history` layer sizes were recorded for the forecast images. The stock course image is 156.3 MB of layers by `docker history` (see `baseline.md`).

## Latency gate

The gate sends 200 requests at concurrency 5 after 20 warm-up requests and reads p95 of the client-side time.

| Run | p95 |
|---|---|
| v1 at first release (the measurement that sets the limit) | 70.6 ms |
| v1, repeat gate run 1 | 88.9 ms |
| v1, repeat gate run 2 | 64.2 ms |
| v2 at demo 1 | 70.3 ms |

Limit: 2 x 70.6 ms = 141.2 ms, rounded up to the next 10 ms, so `GATE_P95_MS=150`. The two repeat runs show the same service varying from 64 to 89 ms from run to run.

## Release runs

| Step | Revision | Command result | Traffic before | Traffic after |
|---|---|---|---|---|
| v1 first release | `lab5-forecast-00001-64d` | exit 0, gate pass | no service | `00001-64d` 100% |
| Demo 1, good promote (v2) | `lab5-forecast-00003-mac` | exit 0, gate pass, canary pass | `00001-64d` 100% | `00003-mac` 100% |
| Demo 2, refused by Cloud Run (v3) | `lab5-forecast-00007-tex` (never Ready) | exit 2. The loader raised during startup and the container exited with code 3 before serving, so the startup probe never passed (`The user-provided container failed the configured startup probe checks`) | `00003-mac` 100% | `00003-mac` 100% (unchanged) |
| Demo 3, refused by the gate (v4) | `lab5-forecast-00008-qix` | exit 3, 5 of 5 golden cases mismatch, `cand` tag removed | `00003-mac` 100% | `00003-mac` 100% (unchanged) |
| Demo 4, rollback to v1 | `lab5-forecast-00001-64d` | exit 0, readiness on the service URL HTTP 200 | `00003-mac` 100% | `00001-64d` 100% |

Revision numbers skip values (`00002`, `00004` to `00006`) because every `update-traffic` call also advances Cloud Run's name counter.

Demo 3 was first run locally against the v4 container (readiness 200, version 1.2.0): all 5 golden cases mismatched and the gate exited 3. In the cloud the result was identical.

### Demo 2 log evidence (revision `lab5-forecast-00007-tex`)

The model version check raised in the app's startup, so uvicorn exited and the container never served `/health/ready`:

```
04:58:12.529  Starting new instance. Reason: DEPLOYMENT_ROLLOUT
04:58:19.688  model_loader.ModelLoadError: version mismatch: config 9.9.9, artifact 1.1.0
04:58:19.688  ERROR:    Application startup failed. Exiting.
04:58:20.661  Container called exit(3).
04:58:20.780  Ready condition status changed to False for Revision lab5-forecast-00007-tex with message: The user-provided container failed the configured startup probe checks.
```

Deploy to refusal took 19 s (04:58:07 to 04:58:26).

## Startup times (instance start to startup probe pass, from Cloud Logging)

| Revision | Instance started | Probe passed | Elapsed | Attempts |
|---|---|---|---|---|
| v1 `00001-64d` | 04:55:23.360 | 04:55:33.793 | 10.4 s | 6 |
| v2 `00003-mac` | 04:57:05.009 | 04:57:13.166 | 8.2 s | 5 |
| v4 `00008-qix` | 04:59:57.428 | 05:00:07.842 | 10.4 s | 6 |
| v1 again (rollback, autoscaled instance) | 05:00:34.311 | 05:00:42.526 | 8.2 s | 5 |

Stock Flask hello world for comparison: 1.79 s (default TCP probe, 1 attempt).

## Cold start

One call to the service (v1 revision `00001-64d` at 100%) at 05:17:04 UTC, 16 min 27 s after the last request that reached an instance (05:00:37). No instance was running.

| Measure | Value |
|---|---|
| First request, client side | 10.44 s (HTTP 200; connect 0.08 s, first byte 10.44 s) |
| First request, Cloud Run request log latency | 10.09 s |
| Instance start to startup probe pass | 10.24 s (instance started 05:17:05.640, probe passed 05:17:15.878, 6 attempts) |
| Model load inside that window | 0.75 s (`Waiting for application startup` 05:17:14.853 to `loaded model` 05:17:15.605); the rest is instance and container start |

With `--min-instances 0` the first request after idle pays the full startup; the probe period of 2 s adds up to 2 s of that.
