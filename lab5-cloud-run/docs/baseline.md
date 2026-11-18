# Baseline: the stock course lab, measured

Source: `raminmohammadi/MLOps` at commit `034eb50747db15a5c4c08fe61876f8300d7fd649`, folder `Labs/GCP_Labs/Cloud_Runner_Labs/Begineer_Lab`. The folder last changed in `b267bdd` (2025-03-26); the one before that is `0881765` (2025-01-17).

## Stock image (built unmodified, linux/amd64)

| Fact | Value |
|---|---|
| Base | `python:3.8-slim`, Python 3.8.20 |
| Flask | `pip install flask` with no pin resolved to Flask 3.0.3 (the newest release that still supports Python 3.8) |
| Size | 156.3 MB of layers (sum of `docker history` layer sizes: 85.2 + 10.4 + 46.1 + 14.6 MB, plus about 45 kB of smaller layers). `docker image inspect` reported 208,201,631 B on this host's containerd image store; that figure counts unpacked and compressed content together, so it is not used as an unpacked size |
| Layers (`docker history`, same sizes as above) | Debian base 85.2 MB, apt packages 10.4 MB, Python 3.8 build 46.1 MB, `pip install flask` 14.6 MB, app files 20.5 kB |
| Local check | `curl localhost:18080/` returned `Hello, World!` |
| Server | Flask development server (`app.run`), which logs `WARNING: This is a development server` on Cloud Run |
| Image digest | `sha256:33388e3919001b29de7dffa25e8cb030c473a47ff64ecbc53cc7bf93747162d4` |

## Deploy facts (Cloud Run, `us-east1`, deployed 2026-11-18 04:48 UTC, service `lab5-hello`)

| Fact | Value |
|---|---|
| Image source | Artifact Registry `us-east1-docker.pkg.dev/boston-resilience-twin/lab5/hello`, deployed by digest |
| Settings | the lab's console defaults (port 8080, default runtime identity), except `--no-allow-unauthenticated`; `--min-instances 0 --max-instances 2` and label `purpose=lab5` added |
| Runtime identity | the project's default Compute Engine service account |
| Deploy time | 9 s from command to serving |
| Startup probe | the default TCP probe on port 8080 |
| Instance start to probe pass | 1.79 s (instance start logged 04:48:06.835, `Default STARTUP TCP probe succeeded after 1 attempt` at 04:48:08.622) |
| First request | 200 in 4.1 ms server side (Cloud Logging `httpRequest.latency`), 117 ms measured at the client including TLS setup; the instance was already running from the deploy |
| Unauthenticated request | 403 |
| Authenticated request | 200 with an identity token from `gcloud auth print-identity-token` |

The service and the `hello` image were deleted right after measuring, and a listing of each returned nothing.

## README steps that cannot be followed as written

1. **Step 1 enables the Container Registry API and step 3 pushes to `gcr.io`.** Container Registry is shut down; Artifact Registry (`REGION-docker.pkg.dev`) replaces it. A `gcr.io/PROJECT/hello-world` push was not attempted.
2. **Step 2 pins nothing.** `python:3.8-slim` is end of life (Python 3.8 stopped receiving security fixes in October 2024), and `RUN pip install flask` resolves to whatever is newest for Python 3.8 on the build day, so two builds can differ.
3. **Step 3's `docker tag gcr.io/YOUR_PROJECT_ID/hello-world gcr.io/YOUR_PROJECT_ID/hello-world`** tags an image with its own name and does nothing. `gcloud auth configure-docker` with no argument registers only the default registry hosts (`gcr.io` and its regional variants), not `pkg.dev`.
4. **Step 4 is Console-only and offers public access.** "Allow unauthenticated invocations" makes the service callable by anyone on the internet; nothing in the steps sets a runtime identity, probes, an instance cap or labels, so the deploy cannot be repeated from a script.
5. **Cloud Run ignores a Docker `HEALTHCHECK`.** The stock image has none, and adding one would not change how Cloud Run judges a revision: only the startup, liveness and readiness probes set on the service count.
