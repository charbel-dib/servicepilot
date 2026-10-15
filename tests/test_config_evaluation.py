import json

import pytest
from fastapi.testclient import TestClient
from pydantic import ValidationError

from servicepilot.api import create_app
from servicepilot.config import Settings
from servicepilot.evaluation import run_evaluation
from servicepilot.status_api import app as status_app


@pytest.mark.parametrize(
    "kwargs",
    [
        {"environment": "unknown"},
        {"provider": "unknown"},
        {"embedding_backend": "unknown"},
        {"provider": "openai"},
        {"environment": "production"},
        {
            "environment": "production",
            "identities_json": '{"demo-token":{"user_id":"x","services":[]}}',
        },
        {"identities_json": "{}"},
        {"identities_json": '{"token":{"user_id":"x","services":"atlas"}}'},
    ],
)
def test_invalid_configuration_is_rejected(kwargs):
    with pytest.raises((ValidationError, ValueError)):
        Settings(_env_file=None, **kwargs)


def test_production_metadata_has_no_credentials(tmp_path):
    settings = Settings(
        environment="production",
        data_dir=tmp_path,
        _env_file=None,
        identities_json=json.dumps({"a" * 40: {"user_id": "prod", "services": ["atlas"]}}),
    )
    with TestClient(create_app(settings)) as client:
        assert client.get("/api/config").json()["demo_identities"] == []
        assert "a" * 40 not in client.get("/api/config").text


def test_status_fixture_contract():
    with TestClient(status_app) as client:
        assert client.get("/health").status_code == 200
        assert client.get("/services/atlas").json()["status"] == "degraded"
        assert client.get("/services/unknown").status_code == 404


def test_offline_evaluation_produces_inspectable_reports(tmp_path, monkeypatch):
    monkeypatch.setenv("SERVICEPILOT_PROVIDER", "offline")
    path = tmp_path / "evaluation.json"
    assert run_evaluation(str(path)) == 0
    report = json.loads(path.read_text())
    assert report["passed"] == report["total"] == 14
    assert path.with_suffix(".html").exists()
