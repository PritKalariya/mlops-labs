"""The DAG parses cleanly and has the intended shape."""
from __future__ import annotations

from datetime import timedelta

import pytest
from airflow.dag_processing.dagbag import DagBag

from lab4.notify import notify_failure, notify_success

DAG_ID = "lab4_ad_click"
TASKS = {"fetch_data", "preprocess", "train", "evaluate"}


@pytest.fixture(scope="module")
def dagbag():
    # No include_examples argument in Airflow 3: AIRFLOW__CORE__LOAD_EXAMPLES=false covers it.
    return DagBag(dag_folder="/opt/airflow/dags")


@pytest.fixture(scope="module")
def dag(dagbag):
    return dagbag.dags[DAG_ID]


def test_dag_imports_with_no_errors(dagbag):
    assert dagbag.import_errors == {}
    assert DAG_ID in dagbag.dags


def test_tasks_and_order(dag):
    assert {t.task_id for t in dag.tasks} == TASKS
    assert dag.get_task("fetch_data").downstream_task_ids == {"preprocess"}
    assert dag.get_task("preprocess").downstream_task_ids == {"train", "evaluate"}
    assert dag.get_task("train").downstream_task_ids == {"evaluate"}
    assert dag.get_task("evaluate").downstream_task_ids == set()


def test_only_fetch_data_has_retries(dag):
    retries = {t.task_id: t.retries for t in dag.tasks}
    assert retries["fetch_data"] == 2
    assert {k: v for k, v in retries.items() if k != "fetch_data"} == {
        "preprocess": 0,
        "train": 0,
        "evaluate": 0,
    }


def test_fetch_data_backoff_is_real_exponential_backoff(dag):
    task = dag.get_task("fetch_data")
    assert task.retry_delay == timedelta(seconds=30)
    assert task.max_retry_delay == timedelta(minutes=5)
    # In Airflow 3.3 this is a multiplier. True would mean 1.0, which is no backoff at all.
    assert task.retry_exponential_backoff == 2.0


def test_schedule_and_run_settings(dag):
    assert dag.catchup is False
    assert dag.max_active_runs == 1
    assert dag.start_date.year == 2025  # fixed, not datetime.now()
    assert dag.timezone.name == "America/New_York"


def test_params_are_overridable(dag):
    assert {"data_url", "expected_sha256", "request_timeout"} <= set(dag.params)


def test_callbacks_are_wired(dag):
    assert dag.on_success_callback is notify_success
    for task in dag.tasks:
        callbacks = task.on_failure_callback
        callbacks = callbacks if isinstance(callbacks, list) else [callbacks]
        assert notify_failure in callbacks, task.task_id
