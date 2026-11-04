"""The lab's own logic (preprocess, train, evaluate) with fixed seeds.

Every function takes and returns file paths or JSON-safe values, never arrays, so XCom stays small
and needs no pickling.
"""
from __future__ import annotations

import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.compose import make_column_transformer
from sklearn.linear_model import LogisticRegression
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import MinMaxScaler, StandardScaler

from lab4 import config

DROP_COLUMNS = ["Timestamp", "Clicked on Ad", "Ad Topic Line", "Country", "City"]
NUM_COLUMNS = ["Daily Time Spent on Site", "Age", "Area Income", "Daily Internet Usage", "Male"]


def preprocess(csv_path: str, out_dir: str) -> str:
    """Split and scale the data, save the arrays to out_dir, return the .npz path."""
    df = pd.read_csv(csv_path)
    X = df.drop(DROP_COLUMNS, axis=1)
    y = df["Clicked on Ad"]
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=config.TEST_SIZE, random_state=config.SEED
    )
    ct = make_column_transformer(
        (MinMaxScaler(), NUM_COLUMNS),
        (StandardScaler(), NUM_COLUMNS),
        remainder="passthrough",
    )
    X_train = ct.fit_transform(X_train)
    X_test = ct.transform(X_test)

    out = Path(out_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / config.SPLITS_FILENAME
    np.savez_compressed(
        path, X_train=X_train, X_test=X_test, y_train=y_train.to_numpy(), y_test=y_test.to_numpy()
    )
    return str(path)


def train(splits_path: str, model_dir: str) -> str:
    """Fit a LogisticRegression on the training split, save it, return the model path."""
    with np.load(splits_path) as splits:
        X_train, y_train = splits["X_train"], splits["y_train"]
    clf = LogisticRegression(random_state=config.SEED)
    clf.fit(X_train, y_train)

    out = Path(model_dir)
    out.mkdir(parents=True, exist_ok=True)
    path = out / config.MODEL_FILENAME
    joblib.dump(clf, path)
    return str(path)


def evaluate(splits_path: str, model_path: str, model_dir: str, run_id: str) -> float:
    """Score the model on the test split, write metrics.json, return the accuracy."""
    with np.load(splits_path) as splits:
        X_test, y_test = splits["X_test"], splits["y_test"]
    clf = joblib.load(model_path)
    accuracy = float(clf.score(X_test, y_test))

    # The DAG-level success callback runs in the dag processor, outside any task. It reads the
    # result from this file (the model dir is mounted in every service) rather than from XCom.
    # run_id guards against reporting a stale file.
    metrics = {"run_id": run_id, "accuracy": accuracy, "n_test": int(len(y_test))}
    (Path(model_dir) / config.METRICS_FILENAME).write_text(json.dumps(metrics))
    return accuracy
