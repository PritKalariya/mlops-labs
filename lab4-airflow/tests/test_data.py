"""fetch classification: transient errors propagate (Airflow retries), permanent ones fail at once."""
from __future__ import annotations

import hashlib
import os
import socket
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer

import pytest
import requests
from airflow.sdk.exceptions import AirflowFailException

from lab4 import data

BODY = b"col_a,col_b\n1,2\n3,4\n"
SHA = hashlib.sha256(BODY).hexdigest()


class _Handler(BaseHTTPRequestHandler):
    def do_GET(self):  # noqa: N802 - http.server API
        status, body = {
            "/ok": (200, BODY),
            "/missing": (404, b"not found"),
            "/forbidden": (403, b"forbidden"),
            "/boom": (503, b"unavailable"),
        }.get(self.path, (200, BODY))
        if self.path == "/slow":
            time.sleep(1.5)
        self.send_response(status)
        self.send_header("Content-Length", str(len(body)))
        self.end_headers()
        self.wfile.write(body)

    def log_message(self, *args):  # keep pytest output quiet
        pass


@pytest.fixture(scope="module")
def base_url():
    server = ThreadingHTTPServer(("127.0.0.1", 0), _Handler)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    yield f"http://127.0.0.1:{server.server_address[1]}"
    server.shutdown()


def test_success_writes_verified_file(base_url, tmp_path):
    path = data.download_csv(f"{base_url}/ok", SHA, str(tmp_path), timeout=5)
    assert open(path, "rb").read() == BODY
    assert path.startswith(str(tmp_path))
    assert os.stat(path).st_mode & 0o777 == 0o644


def test_uppercase_expected_hash_is_accepted(base_url, tmp_path):
    data.download_csv(f"{base_url}/ok", SHA.upper(), str(tmp_path), timeout=5)


@pytest.mark.parametrize("path", ["/missing", "/forbidden"])
def test_http_4xx_is_permanent(base_url, tmp_path, path):
    with pytest.raises(AirflowFailException):
        data.download_csv(f"{base_url}{path}", SHA, str(tmp_path), timeout=5)


def test_hash_mismatch_is_permanent_and_writes_nothing(base_url, tmp_path):
    with pytest.raises(AirflowFailException, match="sha256 mismatch"):
        data.download_csv(f"{base_url}/ok", "0" * 64, str(tmp_path), timeout=5)
    assert list(tmp_path.iterdir()) == []


def test_http_5xx_is_transient(base_url, tmp_path):
    with pytest.raises(requests.exceptions.HTTPError) as err:
        data.download_csv(f"{base_url}/boom", SHA, str(tmp_path), timeout=5)
    assert not isinstance(err.value, AirflowFailException)


def test_timeout_is_transient(base_url, tmp_path):
    with pytest.raises(requests.exceptions.Timeout):
        data.download_csv(f"{base_url}/slow", SHA, str(tmp_path), timeout=0.3)


def test_connection_error_is_transient(tmp_path):
    with socket.socket() as sock:  # grab a free port, then close it so nothing listens
        sock.bind(("127.0.0.1", 0))
        port = sock.getsockname()[1]
    with pytest.raises(requests.exceptions.ConnectionError):
        data.download_csv(f"http://127.0.0.1:{port}/x.csv", SHA, str(tmp_path), timeout=2)
