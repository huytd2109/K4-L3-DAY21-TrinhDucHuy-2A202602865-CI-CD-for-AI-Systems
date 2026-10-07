import json
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
import pytest
from sklearn.ensemble import GradientBoostingClassifier
from sklearn.metrics import accuracy_score, f1_score

from src.train import train


FEATURE_NAMES = [
    "age", "workclass", "education_num", "marital_status", "occupation",
    "relationship", "sex", "capital_gain", "capital_loss", "hours_per_week",
]
PARAMS = {"n_estimators": 10, "learning_rate": 0.1, "max_depth": 2}


@pytest.fixture(autouse=True)
def isolated_training(tmp_path, monkeypatch):
    """Keep test models, reports and MLflow runs separate from real experiments."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("MLFLOW_TRACKING_URI", f"sqlite:///{tmp_path.as_posix()}/mlflow.db")
    monkeypatch.setenv("MLFLOW_ARTIFACT_ROOT", "./mlartifacts")


def _make_temp_data(tmp_path):
    rng = np.random.default_rng(0)
    n = 200
    X = rng.random((n, len(FEATURE_NAMES)))
    y = rng.integers(0, 2, size=n)
    df = pd.DataFrame(X, columns=FEATURE_NAMES)
    df["target"] = y
    train_path = str(tmp_path / "train.csv")
    eval_path = str(tmp_path / "holdout.csv")
    df.iloc[:160].to_csv(train_path, index=False)
    df.iloc[160:].to_csv(eval_path, index=False)
    return train_path, eval_path


def test_train_returns_float(tmp_path):
    train_path, eval_path = _make_temp_data(tmp_path)
    f1 = train(PARAMS, data_path=train_path, eval_path=eval_path)
    assert isinstance(f1, float)
    assert 0.0 <= f1 <= 1.0
    model = joblib.load("models/model.joblib")
    holdout = pd.read_csv(eval_path)
    preds = model.predict(holdout.drop(columns=["target"]))
    assert f1 == pytest.approx(f1_score(holdout["target"], preds))


def test_report_file_created(tmp_path):
    train_path, eval_path = _make_temp_data(tmp_path)
    f1 = train(PARAMS, data_path=train_path, eval_path=eval_path)
    assert Path("outputs/report.json").is_file()
    with open("outputs/report.json", encoding="utf-8") as f:
        report = json.load(f)
    assert set(report) == {"f1_score", "accuracy"}
    assert report["f1_score"] == pytest.approx(f1)
    model = joblib.load("models/model.joblib")
    holdout = pd.read_csv(eval_path)
    preds = model.predict(holdout.drop(columns=["target"]))
    assert report["accuracy"] == pytest.approx(accuracy_score(holdout["target"], preds))


def test_model_file_created(tmp_path):
    train_path, eval_path = _make_temp_data(tmp_path)
    train(PARAMS, data_path=train_path, eval_path=eval_path)
    assert Path("models/model.joblib").is_file()
    model = joblib.load("models/model.joblib")
    assert isinstance(model, GradientBoostingClassifier)
    assert list(model.feature_names_in_) == FEATURE_NAMES
    assert model.random_state == 42
    assert all(model.get_params()[name] == value for name, value in PARAMS.items())
    holdout = pd.read_csv(eval_path)
    assert set(model.predict(holdout.drop(columns=["target"]))) <= {0, 1}
