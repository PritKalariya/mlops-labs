import argparse
import hashlib
import json
from datetime import datetime, timezone
from pathlib import Path

import joblib
import sklearn
from sklearn.metrics import accuracy_score
from sklearn.tree import DecisionTreeClassifier

from data import load_data, split_data

MODEL_ROOT = Path(__file__).resolve().parent.parent / "model"
FEATURES = ["sepal_length", "sepal_width", "petal_length", "petal_width"]


def fit_model(X_train, y_train):
    model = DecisionTreeClassifier(max_depth=3, random_state=12)
    model.fit(X_train, y_train)
    return model


def save(model, version, test_accuracy):
    out_dir = MODEL_ROOT / version
    out_dir.mkdir(parents=True, exist_ok=True)
    model_path = out_dir / "model.pkl"
    joblib.dump(model, model_path)

    with open(model_path, "rb") as f:
        sha256 = hashlib.file_digest(f, "sha256").hexdigest()

    metadata = {
        "version": version,
        "sklearn_version": sklearn.__version__,
        "sha256": sha256,
        "test_accuracy": round(test_accuracy, 4),
        "features": FEATURES,
        "trained_at": datetime.now(timezone.utc).isoformat(),
    }
    (out_dir / "metadata.json").write_text(json.dumps(metadata, indent=2))
    return model_path


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--version", default="1.0.0")
    args = parser.parse_args()

    X, y = load_data()
    X_train, X_test, y_train, y_test = split_data(X, y)
    model = fit_model(X_train, y_train)
    acc = accuracy_score(y_test, model.predict(X_test))
    path = save(model, args.version, acc)
    print(f"saved {path}  test_accuracy={acc:.4f}")
