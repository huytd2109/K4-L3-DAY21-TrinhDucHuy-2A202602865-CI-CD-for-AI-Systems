import importlib.util
from pathlib import Path
from unittest.mock import Mock

import joblib
import numpy as np
import pandas as pd
import pytest
from fastapi.testclient import TestClient
from sklearn.ensemble import GradientBoostingClassifier

from tests.test_train import FEATURE_NAMES


@pytest.fixture
def api(tmp_path, monkeypatch):
    """Exercise real inference; mock only the S3 transfer to keep tests offline."""
    values = np.zeros((40, 10))
    labels = np.array([0] * 20 + [1] * 20)
    values[:, 2] = np.where(labels == 1, 14, 5)
    model = GradientBoostingClassifier(n_estimators=10, random_state=42)
    model.fit(pd.DataFrame(values, columns=FEATURE_NAMES), labels)
    client = Mock()
    client.download_file.side_effect = lambda bucket, key, path: joblib.dump(model, path)
    monkeypatch.setattr("boto3.client", lambda service: client)
    monkeypatch.setenv("ARTIFACT_BUCKET", "test-income-bucket")
    monkeypatch.setenv("MODEL_PATH", str(tmp_path / "models/model.joblib"))
    source = Path(__file__).resolve().parents[1] / "src/serve.py"
    spec = importlib.util.spec_from_file_location("income_test_serve", source)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    client.download_file.assert_called_once_with(
        "test-income-bucket", "artifacts/current/model.joblib",
        str(tmp_path / "models/model.download"),
    )
    assert (tmp_path / "models/model.joblib").is_file()
    with TestClient(module.app) as test_client:
        yield test_client


def test_healthz(api):
    response = api.get("/healthz")
    assert response.status_code == 200
    assert response.json() == {"status": "ok"}


@pytest.mark.parametrize("education,prediction,label", [
    (5, 0, "thu_nhap_thap"), (14, 1, "thu_nhap_cao"),
])
def test_score_labels(api, education, prediction, label):
    response = api.post("/score", json={"features": [28, 2, education, 2, 11, 0, 1, 0, 0, 45]})
    assert response.status_code == 200
    assert response.json() == {"prediction": prediction, "label": label}


def test_score_rejects_wrong_feature_count(api):
    assert api.post("/score", json={"features": [1, 2]}).status_code == 400


def test_score_rejects_non_numeric_input(api):
    assert api.post("/score", json={"features": ["invalid"] * 10}).status_code == 422


def test_score_rejects_non_finite_input(api):
    assert api.post("/score", json={"features": ["NaN"] * 10}).status_code == 400
