"""verify_api.py's result handling, run against the app in process instead of a fresh server.

CI and the verify-api skill read only the exit code, so every failed check has to reach it.
"""

import signal
from collections.abc import Iterator, Mapping
from contextlib import contextmanager

import httpx2
import pytest
from fastapi.testclient import TestClient

from catalogue.app import create_app
from catalogue.core.config import Settings
from catalogue.curation.base import CurationDraft, CurationError, CurationFailure
from scripts import verify_api
from tests.fakes import FakeCurationProvider


@pytest.fixture
def curation_script(
    monkeypatch: pytest.MonkeyPatch, settings: Settings
) -> list[CurationDraft | Exception]:
    """Serve verify_api's checks from the app in process, curating by the returned script."""
    script: list[CurationDraft | Exception] = []

    @contextmanager
    def in_process_server(_environment: Mapping[str, str]) -> Iterator[tuple[httpx2.Client, str]]:
        app = create_app(settings, curation_provider=FakeCurationProvider(script=script))
        with TestClient(app) as client:
            yield client, "keyword"

    monkeypatch.setattr(verify_api, "fresh_server", in_process_server)
    # main() turns SIGTERM into KeyboardInterrupt to stop the server it starts; pytest's own
    # handler has to stay in place.
    monkeypatch.setattr(signal, "signal", lambda *_args: None)
    return script


@pytest.mark.parametrize(
    ("outcomes", "code", "summary"),
    [
        pytest.param([], 0, "6 of 6 checks passed.", id="all-pass"),
        pytest.param(
            [CurationError(CurationFailure.UNAVAILABLE)],
            1,
            "5 of 6 checks passed.",
            id="failed-curation",
        ),
    ],
)
def test_exits_non_zero_when_a_check_fails(
    curation_script: list[CurationDraft | Exception],
    capsys: pytest.CaptureFixture[str],
    outcomes: list[CurationDraft | Exception],
    code: int,
    summary: str,
) -> None:
    curation_script.extend(outcomes)

    assert verify_api.main([]) == code
    assert capsys.readouterr().out.splitlines()[-1] == summary
