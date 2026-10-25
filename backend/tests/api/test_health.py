import logging

import pytest
from fastapi.testclient import TestClient
from pydantic import SecretStr

from catalogue.app import create_app
from catalogue.core.config import Settings


def test_health_reports_the_keyword_provider(client: TestClient) -> None:
    response = client.get("/health")

    assert response.status_code == 200
    assert response.json() == {"status": "ok", "curationProvider": "keyword"}


def test_health_reports_anthropic_under_auto_when_a_key_is_set() -> None:
    settings = Settings(_env_file=None, ANTHROPIC_API_KEY=SecretStr("sk-ant-test"))

    with TestClient(create_app(settings)) as client:
        response = client.get("/health")

    assert response.json() == {"status": "ok", "curationProvider": "anthropic"}


def test_create_app_without_settings_reads_the_environment(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-ant-from-shell")

    with TestClient(create_app()) as client:
        response = client.get("/health")

    assert response.json()["curationProvider"] == "anthropic"


def test_create_app_reports_invalid_configuration_without_a_traceback(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("CATALOGUE_CURATION_PROVIDER", "anthropic")

    with pytest.raises(SystemExit) as excinfo:
        create_app()

    message = str(excinfo.value.code)
    assert message.startswith("Invalid configuration in the environment or backend/.env\n")
    assert "CATALOGUE_CURATION_PROVIDER=anthropic requires ANTHROPIC_API_KEY" in message
    assert excinfo.value.__suppress_context__


def test_startup_logs_the_provider_model_and_host_but_never_the_key(
    caplog: pytest.LogCaptureFixture,
) -> None:
    settings = Settings(
        _env_file=None,
        ANTHROPIC_API_KEY=SecretStr("sk-ant-secret"),
        ANTHROPIC_BASE_URL="http://127.0.0.1:9",
        anthropic_model="claude-test-model",
    )

    with caplog.at_level(logging.INFO, logger="catalogue"), TestClient(create_app(settings)):
        pass

    assert startup_messages(caplog) == [
        "Curation provider: anthropic, model claude-test-model, host http://127.0.0.1:9"
    ]
    assert "sk-ant-secret" not in caplog.text


def test_startup_logs_the_keyword_provider(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.INFO, logger="catalogue"), TestClient(create_app(settings)):
        pass

    assert startup_messages(caplog) == ["Curation provider: keyword"]


def startup_messages(caplog: pytest.LogCaptureFixture) -> list[str]:
    return [record.getMessage() for record in caplog.records if record.name == "catalogue.app"]


def test_cors_preflight_allows_a_configured_origin(client: TestClient) -> None:
    response = client.options(
        "/health",
        headers={
            "Origin": "http://localhost:5173",
            "Access-Control-Request-Method": "DELETE",
            "Access-Control-Request-Headers": "Content-Type",
        },
    )

    assert response.status_code == 200
    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert set(response.headers["access-control-allow-methods"].split(", ")) == {
        "GET",
        "POST",
        "DELETE",
    }


def test_cors_exposes_location_to_a_configured_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:5173"})

    assert response.headers["access-control-allow-origin"] == "http://localhost:5173"
    assert response.headers["access-control-expose-headers"] == "Location"


def test_cors_ignores_an_unlisted_origin(client: TestClient) -> None:
    response = client.get("/health", headers={"Origin": "http://localhost:4173"})

    assert response.status_code == 200
    assert "access-control-allow-origin" not in response.headers
