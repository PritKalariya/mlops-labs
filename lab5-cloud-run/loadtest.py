import argparse
import asyncio
import os
import statistics
import time

import httpx

URL = os.environ.get("LOADTEST_URL", "http://127.0.0.1:8000/v1/predict")
# Optional bearer token for a private Cloud Run service, e.g.
#   LOADTEST_TOKEN=$(gcloud auth print-identity-token) python loadtest.py --url https://.../v1/predict
TOKEN = os.environ.get("LOADTEST_TOKEN")
PAYLOAD = {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}
WARMUP = 20


async def one_request(client, url, sem, client_ms, handler_ms):
    async with sem:
        start = time.perf_counter()
        r = await client.post(url, json=PAYLOAD)
        elapsed = (time.perf_counter() - start) * 1000
    r.raise_for_status()
    client_ms.append(elapsed)
    handler_ms.append(float(r.headers["x-process-time"]))


def p50_p95(xs):
    q = statistics.quantiles(xs, n=100)
    return q[49], q[94]


async def run(n, concurrency, url=URL):
    client_ms, handler_ms = [], []
    sem = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency)
    headers = {"Authorization": f"Bearer {TOKEN}"} if TOKEN else {}
    async with httpx.AsyncClient(limits=limits, timeout=30, headers=headers) as client:
        for _ in range(WARMUP):
            await one_request(client, url, asyncio.Semaphore(1), [], [])
        await asyncio.gather(*(one_request(client, url, sem, client_ms, handler_ms) for _ in range(n)))
    c50, c95 = p50_p95(client_ms)
    h50, h95 = p50_p95(handler_ms)
    print(f"| {concurrency:>3} | {c50:7.2f} | {c95:7.2f} | {h50:7.2f} | {h95:7.2f} | {c95 - h95:7.2f} |")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=URL, help="predict endpoint; env LOADTEST_URL also works")
    parser.add_argument("-n", type=int, default=1000)
    parser.add_argument("-c", type=int, nargs="+", default=[1, 10, 50])
    args = parser.parse_args()
    print("|   c | client p50 | client p95 | handler p50 | handler p95 | p95 gap |")
    print("|---|---|---|---|---|---|")
    for c in args.c:
        asyncio.run(run(args.n, c, args.url))


if __name__ == "__main__":
    main()
