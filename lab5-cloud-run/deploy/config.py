"""Fixed lab values plus the non-secret tunables read from .env.

Environment variables win over .env, and .env wins over the defaults below.
Nothing here is a secret: identity tokens are fetched at call time and never stored.
"""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

PROJECT = "boston-resilience-twin"
REGION = "us-east1"
REGISTRY_HOST = "us-east1-docker.pkg.dev"
REPO = "lab5"
SERVICE = "lab5-forecast"
SERVICE_ACCOUNT = f"lab5-run@{PROJECT}.iam.gserviceaccount.com"
LABEL = "purpose=lab5"
IMAGE_NAME = f"{REGISTRY_HOST}/{PROJECT}/{REPO}/forecast"

CAND_TAG = "cand"
LIVE_PATH = "/health/live"
READY_PATH = "/health/ready"
PREDICT_PATH = "/v1/predict"

DEFAULTS = {
    "GATE_P95_MS": "500",
    "GATE_REQUESTS": "200",
    "GATE_CONCURRENCY": "5",
    "CANARY_REQUESTS": "100",
}


def _read_dotenv(path: Path) -> dict[str, str]:
    values: dict[str, str] = {}
    if not path.is_file():
        return values
    for raw in path.read_text().splitlines():
        line = raw.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, value = line.partition("=")
        values[key.strip()] = value.strip().strip('"').strip("'")
    return values


def load(env_file: Path | None = None) -> dict[str, str]:
    merged = dict(DEFAULTS)
    merged.update(_read_dotenv(env_file or ROOT / ".env"))
    for key in DEFAULTS:
        if key in os.environ:
            merged[key] = os.environ[key]
    return merged


def gate_p95_ms(settings: dict[str, str] | None = None) -> float:
    return float((settings or load())["GATE_P95_MS"])
