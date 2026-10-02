# Lab 1: GitHub Actions with gated retraining

IE7374 MLOps, Lab Assignment 1. Based on `Labs/Github_Labs/Lab2` in [raminmohammadi/MLOps](https://github.com/raminmohammadi/MLOps).

![Lab 1 workflow](https://github.com/PritKalariya/mlops-labs/actions/workflows/lab1-retrain.yml/badge.svg)

## What it does

Every push to `main` that touches this folder runs [`lab1-retrain.yml`](../.github/workflows/lab1-retrain.yml):

1. **`test`**: 6 pytest tests check the data split, the gate's logic, and that the model beats a majority-class baseline.
2. **`retrain`**, only if `test` passes: trains a random forest, scores it on a fixed held-out set, and runs a champion/challenger gate against `champion.json`.

| Gate decision | When | Result |
|---|---|---|
| promote | F1 beats the champion, or no champion exists | model uploaded as a workflow artifact; the bot commits the new `champion.json` |
| keep | F1 ties the champion | green run, nothing committed |
| block | F1 is below the champion | the run fails; the champion is unchanged |

## What I changed from the original

| Area | Original | This version | Why |
|---|---|---|---|
| Data | `make_classification` with `n_samples=random.randint(0, 2000)` | breast-cancer dataset, one fixed stratified 455/114 split in `src/dataset.py` | the size could be 0, and the evaluation data overlapped the training data |
| Evaluation | F1 logged on the training rows | F1 on the 114 held-out rows only | training-set F1 is near 1.0 by construction |
| Tests | none | 6 tests; `retrain` runs only after `test` passes (`needs: test`) | broken code never reaches training |
| Versioning | every run committed its model binary to git | models stored as workflow artifacts; only `champion.json` is committed | binaries in git stay in history forever |
| Promotion | none | champion/challenger gate in `src/gate.py` | a worse model can't replace a better one |
| MLflow | file store (`./mlruns`) | `sqlite:///mlflow.db` | MLflow 3 raises an error on the file store |
| Workflow | `@v4` actions, Python 3.9, `ubuntu-latest`, commits as the instructor, default token | `@v7` actions, Python 3.14, `ubuntu-24.04`, bot identity, `contents: write` on `retrain` only | Node 20 removal, a pinned runner, least privilege |
| Dependencies | unpinned | pinned to the versions tested locally | an unpinned MLflow broke the unmodified lab |

## The gate in action

| Push | Change to `PARAMS` | F1 | Decision | Run |
|---|---|---|---|---|
| First gated run | defaults | 0.9655 | promote (no champion yet) | [36962324197](https://github.com/PritKalariya/mlops-labs/actions/runs/36962324197) |
| Demo 1 | `max_depth=1` | 0.9452 | block | [BLOCK_RUN_ID](https://github.com/PritKalariya/mlops-labs/actions/runs/BLOCK_RUN_ID) |
| Demo 2 | back to defaults | 0.9655 | keep | [36963094376](https://github.com/PritKalariya/mlops-labs/actions/runs/36963094376) |
| Demo 3 | `max_features=1` | 0.9660 | promote | [36963399460](https://github.com/PritKalariya/mlops-labs/actions/runs/36963399460) |

## Known limitations

- **The gate trusts one metric.** It compares F1 on scikit-learn's positive class, which in this dataset is *benign*. Demo 3's model makes the same 5 errors as the old champion but misses one more cancer (malignant recall drops from 92.9% to 90.5%), and the gate promoted it. A production gate would add a guardrail: malignant recall must not drop.
- **Artifacts expire.** Public repos keep artifacts for at most 90 days, after which `champion.json` points at a deleted model. A real setup needs a model registry.
- **CI commits to `main`.** Every promotion adds a bot commit, so you have to pull before pushing, and two overlapping runs can race their pushes.

## Run it locally

```bash
python3 -m venv .venv && source .venv/bin/activate
python -m pip install -r requirements.txt
python -m pytest -v
ts=$(date '+%Y%m%d%H%M%S')
python src/train_model.py --timestamp "$ts"
python src/evaluate_model.py --timestamp "$ts"
```
