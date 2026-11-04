"""Static settings for the lab4_ad_click DAG."""
from __future__ import annotations

import os

# HEAD of raminmohammadi/MLOps when this lab was rebuilt. The raw URL is pinned to it,
# so the data cannot change under the DAG.
SOURCE_SHA = "034eb50747db15a5c4c08fe61876f8300d7fd649"
DATA_URL = (
    "https://raw.githubusercontent.com/raminmohammadi/MLOps/"
    f"{SOURCE_SHA}/Labs/Airflow_Labs/Lab_3/dags/data/advertising.csv"
)
DATA_SHA256 = "00f638aa4103ebf52935d3a62a60328100cc02a8111ca2b4769b4b3596f498f9"
DATA_FILENAME = "advertising.csv"

# Seconds. Overridable per run through the request_timeout param.
REQUEST_TIMEOUT_S = 30

# Working directories, bind-mounted read-write by docker-compose.yaml.
DATA_DIR = os.environ.get("LAB4_DATA_DIR", "/opt/airflow/data")
MODEL_DIR = os.environ.get("LAB4_MODEL_DIR", "/opt/airflow/model")

SPLITS_FILENAME = "splits.npz"
MODEL_FILENAME = "model.joblib"
METRICS_FILENAME = "metrics.json"

SEED = 42
TEST_SIZE = 0.3

# Notifications.
SMTP_CONN_ID = "smtp_gmail"
ALERT_TO_ENV = "ALERT_TO"
SERVICE_ENV = "LAB4_SERVICE"
