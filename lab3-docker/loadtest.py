import argparse
import asyncio
import os
import statistics
import sys
import time

import httpx

URL = os.environ.get("LOADTEST_URL", "http://127.0.0.1:8000/v1/predict")
PAYLOAD = {"sepal_length": 5.1, "sepal_width": 3.5, "petal_length": 1.4, "petal_width": 0.2}
WARMUP = 20


async def one_request(client, url, sem, client_ms, handler_ms, failures):
    async with sem:
        start = time.perf_counter()
        try:
            r = await client.post(url, json=PAYLOAD)
        except httpx.HTTPError as exc:
            failures.append(repr(exc))
            return
        elapsed = (time.perf_counter() - start) * 1000
    if r.status_code != 200:
        failures.append(f"HTTP {r.status_code}")
        return
    client_ms.append(elapsed)
    handler_ms.append(float(r.headers["x-process-time"]))


def p50_p95(xs):
    q = statistics.quantiles(xs, n=100)
    return q[49], q[94]


async def run(url, n, concurrency, failures):
    client_ms, handler_ms = [], []
    sem = asyncio.Semaphore(concurrency)
    limits = httpx.Limits(max_connections=concurrency)
    async with httpx.AsyncClient(limits=limits, timeout=30) as client:
        for _ in range(WARMUP):
            await one_request(client, url, asyncio.Semaphore(1), [], [], failures)
        await asyncio.gather(*(one_request(client, url, sem, client_ms, handler_ms, failures)
                               for _ in range(n)))
    if not client_ms:
        print(f"| {concurrency:>3} |       - |       - |       - |       - |       - |")
        return
    c50, c95 = p50_p95(client_ms)
    h50, h95 = p50_p95(handler_ms)
    print(f"| {concurrency:>3} | {c50:7.2f} | {c95:7.2f} | {h50:7.2f} | {h95:7.2f} | {c95 - h95:7.2f} |")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--url", default=URL, help="predict endpoint; env LOADTEST_URL also works")
    parser.add_argument("-n", type=int, default=200)
    parser.add_argument("-c", type=int, nargs="+", default=[5])
    args = parser.parse_args()

    failures = []
    print(f"target {args.url}")
    print("|   c | client p50 | client p95 | handler p50 | handler p95 | p95 gap |")
    print("|---|---|---|---|---|---|")
    for c in args.c:
        asyncio.run(run(args.url, args.n, c, failures))

    total = (args.n + WARMUP) * len(args.c)
    print(f"requests={total} failures={len(failures)}")
    if failures:
        for f in failures[:5]:
            print(f"  failure: {f}")
        sys.exit(1)


if __name__ == "__main__":
    main()
