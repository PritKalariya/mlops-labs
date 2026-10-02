import argparse
import json

import joblib
from sklearn.metrics import f1_score

from dataset import load_split

if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--timestamp", type=str, required=True)
    timestamp = parser.parse_args().timestamp

    model = joblib.load(f"model_{timestamp}_dt_model.joblib")
    _, X_test, _, y_test = load_split()

    metrics = {"F1_Score": f1_score(y_test, model.predict(X_test))}
    with open(f"{timestamp}_metrics.json", "w") as f:
        json.dump(metrics, f, indent=4)

    print(f"F1 on {len(y_test)} held-out rows: {metrics['F1_Score']:.4f}")
