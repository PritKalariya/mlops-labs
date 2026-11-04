"""Lab 4: ad-click classifier pipeline on Airflow 3.

fetch_data -> preprocess -> train -> evaluate

Only fetch_data retries, and only on transient errors (network, timeout, HTTP 5xx). A 4xx response
or a sha256 mismatch fails at once. Failures and success are reported through lab4.notify.
"""
from __future__ import annotations

from datetime import timedelta

import pendulum
from airflow.sdk import Param, dag, get_current_context, task

from lab4 import config, data, model
from lab4.notify import notify_failure, notify_success

DOC = __doc__


@dag(
    dag_id="lab4_ad_click",
    start_date=pendulum.datetime(2025, 1, 1, tz="America/New_York"),
    schedule="@daily",
    catchup=False,
    max_active_runs=1,
    params={
        "data_url": Param(config.DATA_URL, type="string", description="CSV to download"),
        "expected_sha256": Param(config.DATA_SHA256, type="string", description="sha256 of the CSV"),
        "request_timeout": Param(
            config.REQUEST_TIMEOUT_S, type="integer", minimum=1, description="HTTP timeout, seconds"
        ),
    },
    default_args={"owner": "lab4", "retries": 0, "on_failure_callback": notify_failure},
    on_success_callback=notify_success,
    tags=["lab4"],
    doc_md=DOC,
)
def lab4_ad_click():
    @task(
        retries=2,
        retry_delay=timedelta(seconds=30),
        # In Airflow 3.3 this is a multiplier, not a flag: True means 1.0, which is no backoff.
        retry_exponential_backoff=2.0,
        max_retry_delay=timedelta(minutes=5),
    )
    def fetch_data() -> str:
        params = get_current_context()["params"]
        return data.download_csv(
            url=params["data_url"],
            expected_sha256=params["expected_sha256"],
            dest_dir=config.DATA_DIR,
            timeout=params["request_timeout"],
        )

    @task(multiple_outputs=False)
    def preprocess(csv_path: str) -> str:
        return model.preprocess(csv_path, config.DATA_DIR)

    @task(multiple_outputs=False)
    def train(splits_path: str) -> str:
        return model.train(splits_path, config.MODEL_DIR)

    @task(multiple_outputs=False)
    def evaluate(splits_path: str, model_path: str) -> float:
        run_id = get_current_context()["run_id"]
        return model.evaluate(splits_path, model_path, config.MODEL_DIR, run_id)

    csv_path = fetch_data()
    splits_path = preprocess(csv_path)
    model_path = train(splits_path)
    evaluate(splits_path, model_path)


lab4_ad_click()
