import os
from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from catalogue.app import create_app
from catalogue.core.config import Settings


@pytest.fixture(autouse=True)
def isolated_environment(monkeypatch: pytest.MonkeyPatch) -> None:
    """Keep the developer's shell and `backend/.env` out of every test.

    pydantic-settings matches variable names case-insensitively, hence `upper()`. The dead
    base URL means a stray real client fails fast instead of reaching Anthropic, and clearing
    `env_file` means a `Settings()` built without `_env_file=None` never reads `backend/.env`.
    """
    for name in list(os.environ):
        if name.upper().startswith(("ANTHROPIC_", "CATALOGUE_")):
            monkeypatch.delenv(name)
    monkeypatch.setenv("ANTHROPIC_BASE_URL", "http://127.0.0.1:9")
    monkeypatch.setitem(Settings.model_config, "env_file", None)


@pytest.fixture
def settings() -> Settings:
    return Settings(_env_file=None, curation_provider="keyword")


@pytest.fixture
def client(settings: Settings) -> Iterator[TestClient]:
    with TestClient(create_app(settings)) as client:
        yield client
