"""Download and verify the dataset.

Failure classification is the point of this module:

* transient (network error, timeout, HTTP 5xx): let the exception propagate, Airflow retries;
* permanent (HTTP 4xx, hash mismatch): raise AirflowFailException, Airflow does not retry.
"""
from __future__ import annotations

import hashlib
import os
import tempfile
from pathlib import Path

import requests
from airflow.sdk.exceptions import AirflowFailException

from lab4 import config


def download_csv(url: str, expected_sha256: str, dest_dir: str, timeout: float) -> str:
    """Fetch url, verify its sha256, write it atomically into dest_dir, return the file path."""
    # requests.ConnectionError and requests.Timeout propagate on purpose: they are retried.
    resp = requests.get(url, timeout=timeout)

    status = resp.status_code
    if status >= 500:
        resp.raise_for_status()  # requests.HTTPError, transient, retried
    if status != 200:
        # 4xx, and anything else that is not a plain 200, will not get better by retrying.
        raise AirflowFailException(f"permanent failure: HTTP {status} from {url}")

    actual = hashlib.sha256(resp.content).hexdigest()
    if actual != expected_sha256.strip().lower():
        raise AirflowFailException(
            f"sha256 mismatch for {url}: expected {expected_sha256}, got {actual}"
        )

    out_dir = Path(dest_dir)
    out_dir.mkdir(parents=True, exist_ok=True)
    final = out_dir / config.DATA_FILENAME
    fd, tmp_name = tempfile.mkstemp(dir=out_dir, prefix=".download-")
    try:
        with os.fdopen(fd, "wb") as fh:
            fh.write(resp.content)
        os.chmod(tmp_name, 0o644)  # mkstemp creates 0600
        os.replace(tmp_name, final)
    except BaseException:
        Path(tmp_name).unlink(missing_ok=True)
        raise
    return str(final)
