"""Pre-promotion checks against one URL: readiness, golden predictions, model
version, then a short load run for non-2xx responses and p95 latency.

python -m deploy.gate --url URL --expect-version V [--skip-load] [--token-from-gcloud]
python -m deploy.gate --url URL --record-golden        (writes deploy/golden.json)
"""
import argparse
import asyncio
import json
import math
import statistics
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import httpx

from . import config

GOLDEN_FILE = Path(__file__).with_name("golden.json")
FLOAT_TOL = 1e-6

# Chosen so that swapping petal_length and petal_width changes the predicted class
# of every input (checked against the v1 model: 0->1, 1->2, 1->2, 0->2, 2->1).
GOLDEN_INPUTS = [
    {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2},
    {"sepal_length": 6.0, "sepal_width": 2.9, "petal_length": 4.5, "petal_width": 1.5},
    {"sepal_length": 6.0, "sepal_width": 3.0, "petal_length": 4.0, "petal_width": 1.4},
    {"sepal_length": 5.0, "sepal_width": 3.4, "petal_length": 4.8, "petal_width": 0.3},
    {"sepal_length": 4.9, "sepal_width": 3.1, "petal_length": 1.5, "petal_width": 2.0},
]


@dataclass
class GateResult:
    ok: bool
    failures: list = field(default_factory=list)
    p95_ms: float | None = None

    def report(self):
        p95 = "n/a" if self.p95_ms is None else f"{self.p95_ms:.1f} ms"
        return f"gate {'PASS' if self.ok else 'FAIL'} p95={p95}" + "".join(f"\n  - {f}" for f in self.failures)


def headers_for(token):
    return {"Authorization": f"Bearer {token}"} if token else {}


def values_match(got, want):
    """Labels and ints exactly, floats within FLOAT_TOL, containers recursively."""
    if isinstance(want, dict):
        return isinstance(got, dict) and set(want) <= set(got) and all(values_match(got[k], v) for k, v in want.items())
    if isinstance(want, list):
        return isinstance(got, list) and len(got) == len(want) and all(values_match(g, w) for g, w in zip(got, want))
    if isinstance(want, bool) or isinstance(want, int) or isinstance(want, str) or want is None:
        return got == want and type(got) is type(want)
    if isinstance(want, float):
        return isinstance(got, (int, float)) and math.isclose(got, want, rel_tol=0, abs_tol=FLOAT_TOL)
    return got == want


def load_golden(path=GOLDEN_FILE):
    return json.loads(Path(path).read_text())["cases"]


def p95(values):
    return statistics.quantiles(values, n=100)[94]


async def check_readiness(client, base):
    try:
        r = await client.get(base + config.READY_PATH)
    except httpx.HTTPError as exc:
        return [f"readiness request failed: {exc!r}"]
    return [] if r.status_code == 200 else [f"readiness returned HTTP {r.status_code}, want 200"]


async def check_golden(client, base, cases, expect_version):
    failures = []
    for i, case in enumerate(cases):
        try:
            r = await client.post(base + config.PREDICT_PATH, json=case["input"])
        except httpx.HTTPError as exc:
            failures.append(f"golden[{i}] request failed: {exc!r}")
            continue
        if r.status_code != 200:
            failures.append(f"golden[{i}] HTTP {r.status_code}")
            continue
        body = r.json()
        if not values_match(body, case["output"]):
            failures.append(f"golden[{i}] mismatch: got "
                            f"{ {k: body.get(k) for k in case['output']} } want {case['output']}")
        if expect_version is not None and body.get("model_version") != expect_version:
            failures.append(f"golden[{i}] model_version {body.get('model_version')!r}, want {expect_version!r}")
    return failures


async def check_load(client, base, n, concurrency, p95_limit_ms, warmup=20):
    payload = GOLDEN_INPUTS[0]
    sem = asyncio.Semaphore(concurrency)
    times, bad = [], []

    async def one(record):
        async with sem:
            start = time.perf_counter()
            try:
                r = await client.post(base + config.PREDICT_PATH, json=payload)
            except httpx.HTTPError as exc:
                if record:
                    bad.append(repr(exc))
                return
            ms = (time.perf_counter() - start) * 1000
        if not 200 <= r.status_code < 300:
            if record:
                bad.append(f"HTTP {r.status_code}")
        elif record:
            times.append(ms)

    for _ in range(warmup):
        await one(False)
    await asyncio.gather(*(one(True) for _ in range(n)))

    failures = []
    if bad:
        failures.append(f"{len(bad)} of {n} load requests were not 2xx (first: {bad[0]})")
    measured = p95(times) if len(times) >= 2 else None
    if measured is None:
        failures.append("no successful load requests to measure p95")
    elif measured > p95_limit_ms:
        failures.append(f"p95 {measured:.1f} ms over limit {p95_limit_ms:.1f} ms")
    return failures, measured


async def run_gate_async(base, token, cases, expect_version, p95_limit_ms, *, n=200, concurrency=5,
                         skip_load=False, transport=None):
    base = base.rstrip("/")
    limits = httpx.Limits(max_connections=max(concurrency, 5))
    async with httpx.AsyncClient(headers=headers_for(token), timeout=30, limits=limits, transport=transport) as client:
        failures = await check_readiness(client, base)
        if failures:
            return GateResult(False, failures)
        failures = await check_golden(client, base, cases, expect_version)
        if failures:
            return GateResult(False, failures)
        if skip_load:
            return GateResult(True)
        load_failures, measured = await check_load(client, base, n, concurrency, p95_limit_ms)
        return GateResult(not load_failures, load_failures, measured)


def run_gate(base, token, cases, expect_version, p95_limit_ms, **kwargs):
    return asyncio.run(run_gate_async(base, token, cases, expect_version, p95_limit_ms, **kwargs))


async def run_requests(base, token, n, *, path=config.PREDICT_PATH, concurrency=5, transport=None):
    """Plain request burst used by the canary: returns the list of non-2xx or error descriptions."""
    base = base.rstrip("/")
    sem = asyncio.Semaphore(concurrency)
    bad = []
    async with httpx.AsyncClient(headers=headers_for(token), timeout=30, transport=transport) as client:
        async def one():
            async with sem:
                try:
                    r = await client.post(base + path, json=GOLDEN_INPUTS[0])
                except httpx.HTTPError as exc:
                    bad.append(repr(exc))
                    return
            if not 200 <= r.status_code < 300:
                bad.append(f"HTTP {r.status_code}")
        await asyncio.gather(*(one() for _ in range(n)))
    return bad


def record_golden(base, token, out=GOLDEN_FILE):
    cases = []
    with httpx.Client(headers=headers_for(token), timeout=30) as client:
        for payload in GOLDEN_INPUTS:
            r = client.post(base.rstrip("/") + config.PREDICT_PATH, json=payload)
            r.raise_for_status()
            body = r.json()
            cases.append({"input": payload, "output": {"species_id": body["species_id"], "species": body["species"]}})
    Path(out).write_text(json.dumps({"cases": cases}, indent=2) + "\n")
    return cases


def main(argv=None):
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--url", required=True)
    ap.add_argument("--expect-version")
    ap.add_argument("--skip-load", action="store_true")
    ap.add_argument("--record-golden", action="store_true")
    ap.add_argument("--token-from-gcloud", action="store_true", help="fetch an identity token for a private service")
    args = ap.parse_args(argv)

    token = None
    if args.token_from_gcloud:
        from .gcloud import Gcloud
        token = Gcloud().identity_token()
    if args.record_golden:
        cases = record_golden(args.url, token)
        print(f"wrote {len(cases)} golden cases to {GOLDEN_FILE}")
        return 0
    settings = config.load()
    result = run_gate(args.url, token, load_golden(), args.expect_version, config.gate_p95_ms(settings),
                      n=int(settings["GATE_REQUESTS"]), concurrency=int(settings["GATE_CONCURRENCY"]),
                      skip_load=args.skip_load)
    print(result.report())
    return 0 if result.ok else 3


if __name__ == "__main__":
    sys.exit(main())
