"""The request limits in specs/api-contract.md: the body size limit and the create rate limit."""

import json
from collections.abc import Iterator

import pytest
from fastapi import HTTPException, Request
from fastapi.testclient import TestClient

from catalogue.api.deps import limit_create_rate
from catalogue.api.limits import MAX_BODY_BYTES, RateLimiter
from catalogue.app import create_app
from catalogue.core.config import Settings
from tests.fakes import FakeCurationProvider, ManualClock

ORIGIN = "http://localhost:5173"
VALID = {"name": "Trade Confirmations", "owner": "Middle Office", "description": "Daily trades."}
JSON = {"Content-Type": "application/json"}
TOO_LARGE = {
    "type": "about:blank",
    "title": "Content Too Large",
    "status": 413,
    "detail": f"The request body must be at most {MAX_BODY_BYTES} bytes.",
    "instance": "/datasets",
    "errors": [],
}


def test_a_body_declared_over_the_limit_is_a_413_problem_with_cors_headers(
    client: TestClient, curation_provider: FakeCurationProvider
) -> None:
    body = json.dumps({**VALID, "description": "x" * MAX_BODY_BYTES}).encode()

    response = client.post("/datasets", content=body, headers={**JSON, "Origin": ORIGIN})

    assert response.status_code == 413
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.json() == TOO_LARGE
    assert curation_provider.received == []


def test_a_chunked_body_over_the_limit_is_a_413_problem(client: TestClient) -> None:
    def chunks() -> Iterator[bytes]:
        yield b'{"name": "'
        for _ in range(MAX_BODY_BYTES // 1024 + 1):
            yield b"x" * 1024
        yield b'"}'

    response = client.post("/datasets", content=chunks(), headers=JSON)

    assert "content-length" not in response.request.headers
    assert response.status_code == 413
    assert response.json() == TOO_LARGE


def test_the_largest_valid_body_fits_even_with_every_character_escaped(client: TestClient) -> None:
    astral = "\N{MATHEMATICAL DOUBLE-STRUCK CAPITAL A}"
    largest = {"name": astral * 120, "owner": astral * 120, "description": astral * 2000}
    body = json.dumps(largest, ensure_ascii=True).encode()

    response = client.post("/datasets", content=body, headers=JSON)

    assert len(body) > 26_000
    assert response.status_code == 201


@pytest.fixture
def monotonic() -> ManualClock:
    return ManualClock()


@pytest.fixture
def limited(settings: Settings, monotonic: ManualClock) -> Iterator[TestClient]:
    """The app allowing two creates a minute, on a clock the test moves."""
    app = create_app(
        settings,
        curation_provider=FakeCurationProvider(),
        rate_limiter=RateLimiter(2, clock=monotonic),
    )
    with TestClient(app) as client:
        yield client


def test_a_create_over_the_rate_limit_is_a_429_problem_with_retry_after(
    limited: TestClient,
) -> None:
    assert [limited.post("/datasets", json=VALID).status_code for _ in range(2)] == [201, 201]

    response = limited.post("/datasets", json=VALID, headers={"Origin": ORIGIN})

    assert response.status_code == 429
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["retry-after"] == "30"
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert "Retry-After" in response.headers["access-control-expose-headers"]
    assert response.json() == {
        "type": "about:blank",
        "title": "Too Many Requests",
        "status": 429,
        "detail": "Too many datasets were added from this address. Try again in 30 seconds.",
        "instance": "/datasets",
        "errors": [],
    }
    assert len(limited.get("/datasets").json()) == 5


def test_a_refused_create_may_be_retried_after_the_wait(
    limited: TestClient, monotonic: ManualClock
) -> None:
    for _ in range(2):
        limited.post("/datasets", json=VALID)

    monotonic.advance(29.5)
    almost = limited.post("/datasets", json=VALID)
    monotonic.advance(0.5)
    retried = limited.post("/datasets", json=VALID)

    assert almost.headers["retry-after"] == "1"
    assert almost.json()["detail"].endswith("Try again in 1 second.")
    assert retried.status_code == 201


def test_only_creates_are_rate_limited(limited: TestClient) -> None:
    for _ in range(2):
        limited.post("/datasets", json=VALID)

    assert [limited.get("/datasets").status_code for _ in range(5)] == [200] * 5
    assert limited.get("/health").status_code == 200
    assert limited.delete("/datasets/4").status_code == 200
    assert limited.post("/datasets", json=VALID).status_code == 429


def test_a_create_with_invalid_fields_spends_a_token_but_an_unreadable_body_does_not(
    limited: TestClient,
) -> None:
    # The limit is checked once the body has been read as JSON, before its fields are validated.
    malformed = limited.post("/datasets", content=b"{", headers=JSON)
    too_large = limited.post("/datasets", content=b"x" * (MAX_BODY_BYTES + 1), headers=JSON)
    invalid = limited.post("/datasets", json={"owner": "Middle Office"})

    assert [malformed.status_code, too_large.status_code, invalid.status_code] == [400, 413, 400]
    assert limited.post("/datasets", json=VALID).status_code == 201
    assert limited.post("/datasets", json=VALID).status_code == 429


def create_request(client: tuple[str, int] | None, limiter: RateLimiter) -> Request:
    return Request(
        {
            "type": "http",
            "method": "POST",
            "path": "/datasets",
            "headers": [],
            "client": client,
            "state": {"create_rate_limiter": limiter},
        }
    )


def test_the_limit_is_kept_per_client_address_whatever_the_port() -> None:
    limiter = RateLimiter(1, clock=ManualClock())

    limit_create_rate(create_request(("192.0.2.1", 50000), limiter))
    limit_create_rate(create_request(("192.0.2.2", 50000), limiter))
    with pytest.raises(HTTPException) as excinfo:
        limit_create_rate(create_request(("192.0.2.1", 50001), limiter))

    assert excinfo.value.status_code == 429


def test_requests_without_a_client_address_share_one_bucket() -> None:
    limiter = RateLimiter(1, clock=ManualClock())

    limit_create_rate(create_request(None, limiter))
    with pytest.raises(HTTPException) as excinfo:
        limit_create_rate(create_request(None, limiter))

    assert excinfo.value.status_code == 429
