"""Single source of truth for the data split.

train_model.py and evaluate_model.py both call load_split(), so the
model is always scored on the same held-out rows it never trained on.
"""
from sklearn.datasets import load_breast_cancer
from sklearn.model_selection import train_test_split

SEED = 42
TEST_SIZE = 0.2


def load_split():
    X, y = load_breast_cancer(return_X_y=True)
    return train_test_split(
        X, y, test_size=TEST_SIZE, random_state=SEED, stratify=y
    )
