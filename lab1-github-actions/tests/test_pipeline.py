"""Tests that gate training in CI. They check that the code still works;
the champion gate (slice 3) checks whether the model got better."""
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import f1_score

from dataset import load_split
from train_model import PARAMS


def test_split_is_deterministic():
    first, second = load_split(), load_split()
    for a, b in zip(first, second):
        assert (a == b).all()


def test_no_test_row_leaks_into_training():
    X_train, X_test, _, _ = load_split()
    train_rows = {row.tobytes() for row in X_train}
    assert not any(row.tobytes() in train_rows for row in X_test)


def test_split_sizes_and_class_balance():
    X_train, X_test, y_train, y_test = load_split()
    assert (len(X_train), len(X_test)) == (455, 114)
    assert abs(y_train.mean() - y_test.mean()) < 0.01


def test_model_beats_majority_baseline():
    X_train, X_test, y_train, y_test = load_split()
    model = RandomForestClassifier(**PARAMS).fit(X_train, y_train)
    # Always predicting "benign" scores an F1 of about 0.77 on this split.
    assert f1_score(y_test, model.predict(X_test)) > 0.9
