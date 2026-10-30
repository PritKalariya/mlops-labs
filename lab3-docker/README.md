# Lab 3: Docker

## What I changed
| Area | Original | Mine | Why |
|---|---|---|---|
| Stage layout | Two stages, `model_training` then `serving`, both on full `python:3.10`. The serve stage reinstalls the full requirements, TensorFlow included (`dockerfile:22`) | Four stages. `builder` installs the pinned app deps into `/opt/venv` and ends with `pip check`; `train` uses that venv to run the Lab 2 training script, writing the model and its metadata; `smoke` uses the same base and holds only `requirements-smoke.txt` and `loadtest.py`; `runtime` is last, so it is the default target, and gets only `/opt/venv`, the model and metadata, and the app code | One install feeds both training and serving, so the model's scikit-learn version always matches the runtime's and the loader's version check passes. Training code, pip's cache, and the load test never ship |
| Health check | None | `HEALTHCHECK` calling `/health/ready` with Python `urllib` (slim has no curl), reading `PORT` from the environment. Interval 10 s, timeout 3 s, retries 3, start period 20 s | "Healthy" means the model is loaded and the loader's version and sha256 checks passed, not just that the process is up. Compose reads it (next row). Cloud Run and Kubernetes ignore it and use their own probes |
| Compose gating | Two services on bare `python:3.10-slim` that pip-install TensorFlow on every `up`. The model passes through the named volume `model_exchange`, gated by `service_completed_successfully` | Top-level `name: lab3-docker`. `api` is built from target `runtime` and published as `127.0.0.1:${HOST_PORT:-8000}:8080`. `smoke` is built from target `smoke`, with `depends_on: api: condition: service_healthy`, and runs the load test against `http://api:8080`. No volumes: the model is baked into the image, and `IRIS_ARTIFACT_URI` is passed through Compose with the real path as its default | The image under test is the image that ships. `service_healthy` is a stricter gate than "started". Baking the model ties it to the image tag, so rolling back a revision rolls back the model |
| Port and PID 1 | Flask hard-coded to port 4000 (`src/main.py:45`), `EXPOSE 80`, Compose maps `80:80`, so the app is unreachable at the mapped port | `ENV PORT=8080`, `EXPOSE 8080`, and `CMD ["sh", "-c", "exec uvicorn main:app --host 0.0.0.0 --port ${PORT}"]` | Cloud Run injects `PORT`. 8080 is above 1024, so a non-root user can bind it. `exec` makes uvicorn PID 1 so SIGTERM reaches it. With `sh` as PID 1 the signal is ignored, and every stop waits out the 10 s grace period for SIGKILL |
| Non-root user | Runs as root: `docker run --rm lab3-original:local id -u` prints `0` | System user UID 10001 created with `useradd`, then `USER 10001`. App, model, and venv are owned by root and read-only to that user. `PYTHONDONTWRITEBYTECODE=1` | A compromised process cannot rewrite the model or the code. Kubernetes' restricted Pod Security profile requires `runAsNonRoot` |
| Image size | 3.72 GB unpacked, 1.64 GB compressed (`lab3-original:local`) | 470 MB unpacked, 142 MB compressed: 7.9x smaller unpacked and 11.6x smaller to pull. The 400 MB target was set from an estimate before measuring and was not reachable with this stack: the slim base (134 MB) plus numpy, scipy, and scikit-learn (253 MB) is already 387 MB, leaving 13 MB for FastAPI, pydantic, uvicorn, and their dependencies, which measured 83 MB. | Faster CI push and pull, fewer packages to carry CVEs, and less registry storage |
| Base image | `python:3.10`, full Debian | `python:3.12-slim`, pinned by digest `sha256:aa943ce411423c7582288f18707ff66eddcbaeb510502d747a72aeb34f30d159` (Python 3.12.16) | Matches the Python version my team project's Cloud Run images use, and digest pinning makes rebuilds reproducible |
| Build context | No `.dockerignore` | A `.dockerignore` excluding `.venv`, `.git`, `__pycache__`, `.env`, model artifacts, and `README.md` | A smaller build context, and `.env` can never land in a layer |
| Dependencies | `tensorflow==2.15.0` pinned, the other four (`scikit-learn`, `keras`, `Flask`, `requests`) unpinned, plus `--trusted-host pypi.python.org` on the serve stage's install (`dockerfile:22`) and in the Compose serving command | Every package pinned with `==`, transitive deps included. Requirements are copied and installed before the code. `pip check` is the builder's last step | Reproducible builds, and a code edit does not reinstall dependencies |

The image serves my Lab 2 FastAPI app instead of the original Keras and Flask app.


## Overview
Containerizes a model-serving API as a multi-stage Docker build with a Compose stack that trains, serves, and load-tests it. Based on the course lab [`Labs/Docker_Labs/Lab2`](https://github.com/raminmohammadi/MLOps/tree/main/Labs/Docker_Labs/Lab2). The concept is that the artifact is the unit of deployment: the image carries the model, the dependency set is pinned, the container declares when it is ready, and Compose does not start the load test until the API reports healthy.

## Prerequisites
- Ubuntu 26.04.1 LTS
- Docker Engine 29.9.2
- Docker Compose v5.6.1
- `git`, `curl`
- No host Python needed: every Python step runs inside a container
- No accounts or credentials needed

## Setup
```bash
git clone https://github.com/PritKalariya/mlops-labs.git
cd mlops-labs/lab3-docker
cp .env.example .env
```

`.env` sets `HOST_PORT` (default 8000). Change it if 8000 is taken on your machine; nothing else needs setting.

## Run
Build both images. The `api` image trains the model at build time and bakes it in:
```bash
docker compose build
```

Start the API and wait for its health check to pass:
```bash
docker compose up -d --wait api
```

Interactive docs at http://127.0.0.1:8000/docs. Check it by hand:
```bash
curl -s http://127.0.0.1:8000/health/live; echo
curl -s http://127.0.0.1:8000/health/ready; echo
curl -s -X POST http://127.0.0.1:8000/v1/predict -H 'Content-Type: application/json' \
  -d '{"sepal_length":5.1,"sepal_width":3.5,"petal_length":1.4,"petal_width":0.2}'; echo
```

Run the gated load test. `smoke` does not start until `api` reports healthy:
```bash
docker compose down
docker compose up --build --exit-code-from smoke
```

To see the gate refuse, point the model variable at a path that does not exist:
```bash
IRIS_ARTIFACT_URI=file:///app/model/9.9.9/model.pkl docker compose up -d --wait
```

## Expected result
Health and prediction:
```
{"status":"alive"}
{"status":"ready","model_version":"1.0.0"}
{"species_id":0,"species":"setosa","model_version":"1.0.0"}
```

The gated load test exits 0, with `smoke` reaching `api` over the Compose network:
```
target http://api:8080/v1/predict
|   c | client p50 | client p95 | handler p50 | handler p95 | p95 gap |
|---|---|---|---|---|---|
|   5 |    5.29 |   17.20 |    0.84 |    4.12 |   13.07 |
requests=220 failures=0
smoke-1 exited with code 0
```

`docker inspect --format '{{.State.Health.Status}}' lab3-docker-api-1` prints `healthy`.

Two failure cases, both of which stop the stack before the load test runs.

**Bad model path.** The loader raises inside `lifespan`, so the container exits with code 3 at startup, before any health check runs; there is no unhealthy state to observe. `smoke` stays in `Created` and `up` exits 1 in about 3 s:
```
dependency failed to start: container lab3-docker-api-1 exited (3)
```

**Failing health check.** Forcing the probe to fail, with a throwaway override setting `test: ["CMD", "false"]`, produces the opposite shape: the process stays up and still answers `/health/ready` with 200 from inside the container, but Docker marks the container unhealthy after 40.7 s and `--wait` exits 1. Measured with a 20 s start period, a 10 s interval, and 3 retries.
```
container lab3-docker-api-1 is unhealthy
State.Status=running  State.Health.Status=unhealthy
```
This is the case the gate exists for: a process that is alive but not serving never receives the load test.

Measurements on a ROG Zephyrus G14, Docker Engine 29.9.2:

| Measurement | Value |
|---|---|
| Original image size (`lab3-original:local`) | 3.72 GB unpacked, 1.64 GB compressed |
| My image size (`lab3-api:local`) | 470 MB unpacked, 142 MB compressed |
| Smoke image size (`lab3-smoke:local`) | 152 MB unpacked, 48 MB compressed |
| Original build time | 206.5 s |
| My cold build time (`--no-cache`) | 38.9 s |
| My warm rebuild after a comment edit | 1.0 s |
| Start to `healthy` | 6.0 s |
| `docker compose stop api` | 0.6 s |

Unpacked size is the sum of the `docker history` layer sizes; compressed size is what a registry stores and a `docker pull` downloads. On Docker 29's containerd image store, `docker image ls` DISK USAGE counts both the unpacked layers and the compressed blobs, which is why it shows 612 MB for this image.

The image is 7.9x smaller unpacked, 11.6x smaller to pull, and builds 5.3x faster than the original. The warm rebuild skips both the dependency install and the training run, because requirements and training code are copied before the serving code.

## Clean up
```bash
docker compose down
docker image rm lab3-api:local lab3-smoke:local
```
Optionally drop the base image too, but only if nothing else on the machine uses it; other images commonly share `python:3.12-slim`:
```bash
docker image rm python:3.12-slim
```
No cloud resources are used.

## Known limitations
- The image is 470 MB unpacked (142 MB compressed), over the 400 MB target, which was set from an estimate before measuring and was not reachable with this stack: the slim base (134 MB) plus numpy, scipy, and scikit-learn (253 MB) is already 387 MB, leaving 13 MB for FastAPI, pydantic, uvicorn, and their dependencies, which measured 83 MB.
- `docker compose up --exit-code-from smoke` hangs instead of exiting when `api` fails to start, on Compose v5.6.1: the gate holds and `smoke` never runs, but the attached `up` never returns. `docker compose up -d --wait` reports `dependency failed to start` and exits 1 in about 3 s, so that is the form used above for the failure path.
- The model is baked into the image, so retraining means a rebuild.
- Cloud Run and Kubernetes ignore `HEALTHCHECK`; they need their own `startupProbe` and `readinessProbe`.
- Training runs at build time, so the build needs the training data available and a build that cannot train cannot produce an image.
- One uvicorn worker. Lab 2's load test saturated one worker near 10 concurrent requests, so the c=5 smoke numbers above are below saturation and are a regression check, not a capacity measurement.
- The readiness 503 is still a contract that never fires: the loader raises during `lifespan`, so a bad model exits the process instead of leaving it up and not-ready. The failure path above shows exit code 3, not a 503.
- `.env` holds no secrets today. It is gitignored at the repo root, and `.dockerignore` keeps it out of the build context, so the habit holds when one is added.
