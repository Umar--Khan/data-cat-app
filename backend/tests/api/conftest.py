from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from catalogue.app import create_app
from catalogue.core.config import Settings
from tests.fakes import FakeCurationProvider, TickingClock


@pytest.fixture
def curation_provider() -> FakeCurationProvider:
    return FakeCurationProvider()


@pytest.fixture
def clock() -> TickingClock:
    return TickingClock()


@pytest.fixture
def client(
    settings: Settings, curation_provider: FakeCurationProvider, clock: TickingClock
) -> Iterator[TestClient]:
    """The app with a scripted provider and a ticking clock, through its real lifespan."""
    app = create_app(settings, curation_provider=curation_provider, clock=clock)
    with TestClient(app) as client:
        yield client
