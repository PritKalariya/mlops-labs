import argparse

import mlflow
from joblib import dump
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import accuracy_score, f1_score

from dataset import SEED, TEST_SIZE, load_split

# Hyperparameters live in one place, so a change is a one-line diff.
PARAMS = {"n_estimators": 100, "max_depth": None, "max_features": 1, "random_state": SEED}

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", type=str, required=True)
    timestamp = parser.parse_args().timestamp

    X_train, X_test, y_train, y_test = load_split()

    mlflow.set_tracking_uri("sqlite:///mlflow.db")
    mlflow.set_experiment("lab1-breast-cancer")

    with mlflow.start_run(run_name=timestamp):
        mlflow.log_params({**PARAMS, "test_size": TEST_SIZE, "n_train": len(X_train)})

        model = RandomForestClassifier(**PARAMS)
        model.fit(X_train, y_train)

        y_pred = model.predict(X_test)
        mlflow.log_metrics({
            "test_accuracy": accuracy_score(y_test, y_pred),
            "test_f1": f1_score(y_test, y_pred),
        })

    dump(model, f"model_{timestamp}_dt_model.joblib")
    print(f"Trained model_{timestamp} on {len(X_train)} rows")
