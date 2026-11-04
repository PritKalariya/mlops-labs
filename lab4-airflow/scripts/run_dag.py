#!/usr/bin/env python3
"""Trigger lab4_ad_click through the Airflow REST API with a JWT, wait for it, print the result.

usage: scripts/run_dag.py [CONF_JSON] [--timeout SECONDS] [--port PORT]

CONF_JSON overrides the DAG params, e.g. '{"data_url": "http://10.255.255.1/x.csv", "request_timeout": 5}'.
Reads the admin credentials and AIRFLOW_PORT from ./.env without printing them. Standard library only.
"""
from __future__ import annotations

import argparse
import json
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

DAG_ID = "lab4_ad_click"
DONE = {"success", "failed"}


def read_env(path: Path) -> dict[str, str]:
    env = {}
    for line in path.read_text().splitlines():
        if line and not line.startswith("#") and "=" in line:
            key, _, value = line.partition("=")
            env[key.strip()] = value.strip().strip("'\"")
    return env


class Api:
    def __init__(self, base: str, username: str, password: str):
        self.base = base
        self.token = self._call("POST", "/auth/token", {"username": username, "password": password})[
            "access_token"
        ]

    def _call(self, method: str, path: str, body: dict | None = None):
        data = json.dumps(body).encode() if body is not None else None
        req = urllib.request.Request(self.base + path, data=data, method=method)
        req.add_header("Content-Type", "application/json")
        if getattr(self, "token", None):
            req.add_header("Authorization", f"Bearer {self.token}")
        try:
            with urllib.request.urlopen(req, timeout=30) as resp:
                return json.loads(resp.read() or b"{}")
        except urllib.error.HTTPError as err:
            sys.exit(f"{method} {path} -> HTTP {err.code}: {err.read().decode()[:300]}")

    def call(self, method: str, path: str, body: dict | None = None):
        return self._call(method, path, body)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawTextHelpFormatter)
    parser.add_argument("conf", nargs="?", default="{}", help="JSON object of param overrides")
    parser.add_argument("--timeout", type=int, default=300, help="seconds to wait for the run")
    parser.add_argument("--port", help="API port on 127.0.0.1 (default: AIRFLOW_PORT from .env), e.g. an SSH tunnel's")
    args = parser.parse_args()

    env = read_env(Path(__file__).resolve().parent.parent / ".env")
    base = f"http://127.0.0.1:{args.port or env.get('AIRFLOW_PORT', '8080')}"
    api = Api(base, env["_AIRFLOW_WWW_USER_USERNAME"], env["_AIRFLOW_WWW_USER_PASSWORD"])

    api.call("PATCH", f"/api/v2/dags/{DAG_ID}", {"is_paused": False})
    run = api.call("POST", f"/api/v2/dags/{DAG_ID}/dagRuns", {"logical_date": None, "conf": json.loads(args.conf)})
    run_id = run["dag_run_id"]
    print(f"run_id: {run_id}")

    # The one bounded wait: poll the run state until it finishes or the timeout passes.
    deadline = time.monotonic() + args.timeout
    state = run["state"]
    while state not in DONE and time.monotonic() < deadline:
        time.sleep(5)
        state = api.call("GET", f"/api/v2/dags/{DAG_ID}/dagRuns/{run_id}")["state"]
    print(f"state: {state}" + ("" if state in DONE else f" (still not finished after {args.timeout}s)"))

    tis = api.call("GET", f"/api/v2/dags/{DAG_ID}/dagRuns/{run_id}/taskInstances")["task_instances"]
    print("tasks:")
    for ti in sorted(tis, key=lambda t: t["start_date"] or ""):
        print(f"  {ti['task_id']:<12} {ti['state']!s:<16} try_number={ti['try_number']}")

    for ti in tis:
        tries = api.call(
            "GET", f"/api/v2/dags/{DAG_ID}/dagRuns/{run_id}/taskInstances/{ti['task_id']}/tries"
        ).get("task_instances", [])
        if len(tries) > 1:
            print(f"tries of {ti['task_id']}:")
            for t in tries:
                print(f"  try {t['try_number']}: start={t['start_date']} end={t['end_date']} state={t['state']}")

    if state == "success":
        xcom = api.call(
            "GET", f"/api/v2/dags/{DAG_ID}/dagRuns/{run_id}/taskInstances/evaluate/xcomEntries/return_value"
        )
        print(f"accuracy: {xcom['value']}")
    sys.exit(0 if state == "success" else 1)


if __name__ == "__main__":
    main()
