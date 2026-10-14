# Lab 2: FastAPI model serving

## Overview
Serves a scikit-learn Iris classifier over HTTP with FastAPI. Based on the course lab `Labs/API_Labs/FastAPI_Labs`. The concept is the service contract around a model: typed and validated requests, explicit errors, health checks a platform can probe, safe model loading, and measured latency.

## Prerequisites
- Ubuntu 26.04 LTS
- Python 3.14.4 with `venv`
- `git`, `curl`
- Package versions are pinned in `requirements.txt` (FastAPI 0.143.0, uvicorn 0.54.0, scikit-learn 1.9.1, pydantic 2.14.1, pydantic-settings 2.15.0)
- No accounts or credentials needed

## Setup
```bash
git clone https://github.com/PritKalariya/mlops-labs.git
cd mlops-labs/lab2-fastapi
python3 -m venv .venv && source .venv/bin/activate
pip install -r requirements.txt
```

Configuration is optional; the defaults load model `1.0.0`. To override, set the variables listed in `.env.example` in your shell before starting the server.

## Run
Train the model (writes `model/1.0.0/model.pkl` and `metadata.json`; the `model/` folder is not committed):
```bash
cd src
python train.py
```

Start the server on http://127.0.0.1:8000 (interactive docs at `/docs`):
```bash
uvicorn main:app
```

In a second terminal (with the venv active), from `lab2-fastapi/`:
```bash
curl -s http://127.0.0.1:8000/health/live; echo
curl -s http://127.0.0.1:8000/health/ready; echo
curl -s -X POST http://127.0.0.1:8000/v1/predict -H 'Content-Type: application/json' \
  -d '{"sepal_length":5.1,"sepal_width":3.5,"petal_length":1.4,"petal_width":0.2}'; echo
```

Load test (restart the server with `uvicorn main:app --no-access-log` first, so per-request logging doesn't inflate the numbers):
```bash
python loadtest.py
```

## Expected result
```
{"status":"alive"}
{"status":"ready","model_version":"1.0.0"}
{"species_id":0,"species":"setosa","model_version":"1.0.0"}
```
Every response carries an `x-process-time` header (handler latency in ms). `train.py` prints the test accuracy (0.9556 on the 45-row test split).

Load test on a ROG Zephyrus G14 (client and server on the same machine), 1,000 requests per row, latencies in ms:

| c | client p50 | client p95 | handler p50 | handler p95 | p95 gap |
|---|---|---|---|---|---|
| 1 | 1.82 | 2.43 | 0.72 | 1.04 | 1.39 |
| 10 | 13.35 | 33.71 | 1.22 | 2.33 | 31.38 |
| 50 | 108.14 | 465.36 | 4.36 | 10.97 | 454.39 |

The handler stays cheap while client latency grows about 190x from c=1 to c=50: the gap is queueing. One uvicorn worker with CPU-bound predictions saturates at roughly 500 to 750 requests/s, so beyond about c=10, extra concurrency only adds waiting.

## Clean up
`Ctrl+C` in the server terminal, then `deactivate`. No cloud resources are used.

## What I changed
| Area | Original | Mine | Why |
|---|---|---|---|
| Request schema | Four bare floats | `Field(gt=0, le=30)` on each, unknown fields rejected | A negative petal length got a confident prediction; now it's a 422. Bounds reject the impossible, not the unusual (that's drift detection's job) |
| Response schema | `{"response": int}` | `species_id`, `species` (enum), `model_version` | Callers get a label and know which model answered |
| Route | `POST /predict`, errors as 500 with the raw exception text | `POST /v1/predict`, 503 declared in the OpenAPI spec | The version prefix allows a breaking v2 without breaking v1 callers; the old 500 leaked internals and wasn't in the spec |
| Health | `GET /` always returns `healthy` | `/health/live` (process up) and `/health/ready` (model loaded, else 503) | A check that can't say no makes rollback-on-health-check useless |
| Model loading | `joblib.load` on every request, from a path relative to the working directory | Loaded once at startup via `lifespan` | No disk read per request; works from any directory |
| Configuration | Hard-coded path | `IRIS_ARTIFACT_URI` and `IRIS_ARTIFACT_VERSION`, with a loader that dispatches on URI scheme (`file://` implemented, `gs://` stubbed) | Changing models is a config change; adding a storage backend is one function |
| Artifact verification | None | `train.py` writes `metadata.json` (version, sklearn version, sha256, test accuracy); the loader refuses to start on any mismatch, before unpickling | A stale or tampered pickle fails loudly instead of serving wrong answers. Unpickling runs code, so checks come first |
| Training | Test split created and never used | Test accuracy computed and recorded; one folder per model version | The stock code gave no evidence the model worked |
| Latency | None | Middleware sets `x-process-time` (handler latency only) | Server-side timing per request |
| Load test | None | `loadtest.py`: client vs handler p50/p95 at c=1, 10, 50 | The gap between the two is queueing, which handler timing alone can't show |

## Known limitations
- The server refuses to start on a bad model, so the readiness 503 is a documented contract that never fires in this design. Loading in the background would make it reachable, at the cost of a server that runs without serving.
- `gs://` is a stub. A real backend needs credentials and a download step.
- The sha256 proves the file matches its metadata, not who wrote either. Signing or a model registry would cover authenticity.
- `x-process-time` excludes network, HTTP parsing, and time queued before the app.
- Load test client and server share one CPU, so client numbers at c=50 include the client's own overhead. Single uvicorn worker.
- `/v1` has no `/v2` yet.
- Accuracy is measured on 45 test rows.
