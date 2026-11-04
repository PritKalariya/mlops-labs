# Baseline: the original lab, unmodified

The original Lab_3 was run once without code changes so that the "Original" column of the README is measured, not described.

## Source

| Item | Value |
|---|---|
| Repo | https://github.com/raminmohammadi/MLOps/tree/main/Labs/Airflow_Labs/Lab_3 |

## Environment

| Item | Value |
|---|---|
| Image | `apache/airflow:2.11.2-python3.12` (Python 3.12) |
| Run | `airflow db migrate`, then `airflow dags test Airflow_Lab3_new2`, in one container with a throwaway SQLite database |
| Requirements | Lab_3 `requirements.txt` via `_PIP_ADDITIONAL_REQUIREMENTS`; resolved to scikit-learn 1.8.0, pandas 2.1.4, numpy 1.26.4, scipy 1.17.1 |

## Result

| Task | State |
|---|---|
| `load_data_task` | success |
| `data_preprocessing_task` | success |
| `separate_data_outputs_task` | success |
| `build_save_model_task` | success |
| `task_send_email` | failed |

- Accuracy: 0.97 (300 held-out rows, 30% split, `random_state=42`).
- The email task failed because the connection `email_smtp` does not exist (`AirflowNotFoundException`). It is the only reason the DAG run ends `failed`.

## Needed to run it

- The data file is bind-mounted at `/home/mlops_fall_2024/advertising.csv`, the hard-coded path, instead of editing code.
- `dags test` takes a logical date in the future: with the default date, `start_date=datetime.now()` is later than the run, every task is skipped and the run reports success.
- Accuracy comes from calling the lab's `load_model` directly on the saved `model.sav`, because the DAG never reports it.

## Defects in the original

- `dags/src/model_development.py:18`: the data path is hard-coded to `/home/mlops_fall_2024/advertising.csv`.
- `readme.md`: it triggers `sample_dag`, but the DAG id is `Airflow_Lab3_new2`.
- `dags/src/success_email.py`: a string recipient is joined character by character, and the recipient is the placeholder `'your_email'`.
- `dags/src/success_email.py`: `server.quit()` runs in `finally` even when the connect failed.
- `dags/my_dag.py`: `start_date=datetime.now()` changes on every parse, no schedule is set, and `retries` is 0.
- `dags/my_dag.py`: numpy tuples travel through pickled XCom (`enable_xcom_pickling` is switched on in the DAG file).
- `dags/my_dag.py` and `dags/src/success_email.py`: Airflow 2 only APIs (`provide_context`, `airflow.operators.*`, `airflow.hooks.base`).
