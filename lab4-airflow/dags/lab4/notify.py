"""Failure and success notifications.

Every notification does two things, in this order:

1. always writes one `lab4-alert` line to the log (task log for task callbacks, dag processor log
   for DAG callbacks);
2. sends an email through the SMTP provider's hook on the `smtp_gmail` Connection, only when both
   that Connection and ALERT_TO are set. The password stays inside the Connection, so Airflow's
   secrets masker covers it. Nothing here builds smtplib from raw env values.

Nothing in this module raises: a broken alert must never hide the task's own error.
"""
from __future__ import annotations

import html
import json
import logging
import os
import re
import socket
from pathlib import Path
from typing import Any

from airflow.providers.smtp.hooks.smtp import SmtpHook
from airflow.sdk import BaseHook

from lab4 import config

log = logging.getLogger(__name__)

_MAX_MSG = 300


def _one_line(value: Any) -> str:
    text = re.sub(r"\s+", " ", str(value)).strip()
    return text if len(text) <= _MAX_MSG else text[: _MAX_MSG - 3] + "..."


def _who() -> str:
    """Which process is logging: compose service name, container host, pid."""
    service = os.environ.get(config.SERVICE_ENV, "unknown")
    return f"via={service} host={socket.gethostname()} pid={os.getpid()}"


def _recipients() -> list[str]:
    """ALERT_TO may hold one address or several separated by commas or semicolons."""
    return [a.strip() for a in re.split(r"[,;]", os.environ.get(config.ALERT_TO_ENV, "")) if a.strip()]


def _missing_config() -> list[str]:
    """Names of what is missing for email to work. Empty means email is enabled."""
    missing = []
    if not _recipients():
        missing.append(config.ALERT_TO_ENV)
    try:
        conn = BaseHook.get_connection(config.SMTP_CONN_ID)
        if not conn.host:
            missing.append(f"connection {config.SMTP_CONN_ID} (no host)")
    except Exception:  # noqa: BLE001 - any lookup error means "not usable"
        missing.append(f"connection {config.SMTP_CONN_ID}")
    return missing


def _send_email(subject: str, body: str) -> None:
    missing = _missing_config()
    if missing:
        log.info("lab4-notify email disabled: missing %s", ", ".join(missing))
        return
    try:
        with SmtpHook(smtp_conn_id=config.SMTP_CONN_ID) as hook:
            hook.send_email_smtp(
                to=_recipients(),
                subject=subject,
                html_content=f"<pre>{html.escape(body)}</pre>",
            )
        log.info("lab4-notify email sent: to=%s %s", ", ".join(_recipients()), _who())
    except Exception as exc:  # noqa: BLE001 - a failed send is logged, never raised
        log.warning("lab4-notify email send failed: %s: %s", type(exc).__name__, _one_line(exc))


def _ti_of(context: dict[str, Any]) -> Any:
    return context.get("ti") or context.get("task_instance")


def notify_failure(context: dict[str, Any]) -> None:
    """Task on_failure_callback. Fires once, after the final retry."""
    try:
        ti = _ti_of(context)
        dag_id = getattr(ti, "dag_id", None) or getattr(context.get("dag"), "dag_id", "?")
        task_id = getattr(ti, "task_id", "?")
        run_id = getattr(ti, "run_id", None) or context.get("run_id", "?")
        try_number = getattr(ti, "try_number", "?")
        error = context.get("exception") or context.get("reason") or "unknown"
        error_class = type(error).__name__ if isinstance(error, BaseException) else "Error"

        line = (
            f"dag={dag_id} task={task_id} run_id={run_id} try={try_number} "
            f"error={error_class}: {_one_line(error)}"
        )
        log.error("lab4-alert failure %s", line)
        _send_email(f"[lab4] FAILED {dag_id}.{task_id} (try {try_number})", line)
    except Exception:  # noqa: BLE001
        log.exception("lab4-notify failure callback itself failed")


def _read_metrics(run_id: str) -> dict[str, Any] | None:
    try:
        metrics = json.loads((Path(config.MODEL_DIR) / config.METRICS_FILENAME).read_text())
    except Exception:  # noqa: BLE001
        return None
    return metrics if metrics.get("run_id") == run_id else None


def notify_success(context: dict[str, Any]) -> None:
    """DAG on_success_callback. Runs in the dag processor and reports the accuracy."""
    try:
        dag_id = getattr(context.get("dag"), "dag_id", "?")
        run_id = context.get("run_id", "?")
        metrics = _read_metrics(run_id)
        accuracy = f"{metrics['accuracy']:.4f}" if metrics else "unavailable"

        line = f"dag={dag_id} run_id={run_id} accuracy={accuracy}"
        log.info("lab4-alert success %s %s", line, _who())
        _send_email(f"[lab4] SUCCESS {dag_id} accuracy={accuracy}", line)
    except Exception:  # noqa: BLE001
        log.exception("lab4-notify success callback itself failed")
