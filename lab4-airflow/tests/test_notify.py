"""notify never raises, and says why when email is off."""
from __future__ import annotations

import json
import logging
from types import SimpleNamespace

import pytest

from lab4 import config, notify


@pytest.fixture(autouse=True)
def email_unconfigured(monkeypatch):
    """Start every test with email off, even when the container has it configured."""
    monkeypatch.delenv(config.ALERT_TO_ENV, raising=False)
    monkeypatch.delenv("AIRFLOW_CONN_SMTP_GMAIL", raising=False)


def _failure_context(exc: Exception | None = None):
    ti = SimpleNamespace(dag_id="lab4_ad_click", task_id="fetch_data", run_id="manual__x", try_number=3)
    return {"ti": ti, "exception": exc or ValueError("boom\nsecond line")}


def test_failure_with_missing_config_logs_and_does_not_raise(caplog):
    with caplog.at_level(logging.INFO, logger="lab4.notify"):
        notify.notify_failure(_failure_context())
    text = caplog.text
    assert "lab4-alert failure dag=lab4_ad_click task=fetch_data run_id=manual__x try=3" in text
    assert "error=ValueError: boom second line" in text
    assert "email disabled: missing ALERT_TO, connection smtp_gmail" in text


def test_alert_to_alone_is_not_enough(monkeypatch, caplog):
    monkeypatch.setenv(config.ALERT_TO_ENV, "someone@example.com")
    with caplog.at_level(logging.INFO, logger="lab4.notify"):
        notify.notify_failure(_failure_context())
    assert "email disabled: missing connection smtp_gmail" in caplog.text
    assert "ALERT_TO" not in caplog.text.split("email disabled:")[1]


def test_success_with_missing_config_logs_and_does_not_raise(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(config, "MODEL_DIR", str(tmp_path))
    with caplog.at_level(logging.INFO, logger="lab4.notify"):
        notify.notify_success({"dag": SimpleNamespace(dag_id="lab4_ad_click"), "run_id": "r1"})
    assert "lab4-alert success dag=lab4_ad_click run_id=r1 accuracy=unavailable" in caplog.text
    assert "email disabled" in caplog.text


def test_success_reports_accuracy_only_for_the_same_run(monkeypatch, tmp_path, caplog):
    monkeypatch.setattr(config, "MODEL_DIR", str(tmp_path))
    (tmp_path / config.METRICS_FILENAME).write_text(
        json.dumps({"run_id": "r1", "accuracy": 0.97, "n_test": 300})
    )
    ctx = {"dag": SimpleNamespace(dag_id="lab4_ad_click"), "run_id": "r1"}
    with caplog.at_level(logging.INFO, logger="lab4.notify"):
        notify.notify_success(ctx)
        notify.notify_success({**ctx, "run_id": "other-run"})
    assert "run_id=r1 accuracy=0.9700" in caplog.text
    assert "run_id=other-run accuracy=unavailable" in caplog.text


def test_garbage_context_does_not_raise(caplog):
    with caplog.at_level(logging.INFO, logger="lab4.notify"):
        notify.notify_failure({})
        notify.notify_success({})


def test_recipient_string_is_split_on_addresses_not_characters(monkeypatch):
    monkeypatch.setenv(config.ALERT_TO_ENV, "a@example.com, b@example.com;c@example.com")
    assert notify._recipients() == ["a@example.com", "b@example.com", "c@example.com"]


def test_failed_send_is_logged_and_never_raised(monkeypatch, caplog):
    class BrokenHook:
        def __init__(self, **_):
            pass

        def __enter__(self):
            raise ConnectionRefusedError("smtp is down")

        def __exit__(self, *exc):
            return False

    monkeypatch.setattr(notify, "_missing_config", lambda: [])
    monkeypatch.setenv(config.ALERT_TO_ENV, "a@example.com")
    monkeypatch.setattr(notify, "SmtpHook", BrokenHook)
    with caplog.at_level(logging.INFO, logger="lab4.notify"):
        notify.notify_failure(_failure_context())
    assert "lab4-alert failure" in caplog.text
    assert "email send failed: ConnectionRefusedError: smtp is down" in caplog.text


def test_send_goes_through_the_smtp_hook_on_the_named_connection(monkeypatch, caplog):
    sent = {}

    class FakeHook:
        def __init__(self, smtp_conn_id):
            sent["conn_id"] = smtp_conn_id

        def __enter__(self):
            return self

        def __exit__(self, *exc):
            return False

        def send_email_smtp(self, **kwargs):
            sent.update(kwargs)

    monkeypatch.setattr(notify, "_missing_config", lambda: [])
    monkeypatch.setenv(config.ALERT_TO_ENV, "a@example.com,b@example.com")
    monkeypatch.setattr(notify, "SmtpHook", FakeHook)
    with caplog.at_level(logging.INFO, logger="lab4.notify"):
        notify.notify_failure(_failure_context())
    assert sent["conn_id"] == "smtp_gmail"
    assert sent["to"] == ["a@example.com", "b@example.com"]
    assert "[lab4] FAILED lab4_ad_click.fetch_data (try 3)" in sent["subject"]
    assert "email sent: to=a@example.com, b@example.com" in caplog.text
