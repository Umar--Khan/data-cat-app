from collections import deque

import pytest
from starlette.exceptions import HTTPException
from starlette.types import Message, Receive, Scope, Send

from catalogue.api.limits import MAX_BODY_BYTES, BodySizeLimitMiddleware, RateLimiter
from tests.fakes import ManualClock


def test_a_client_may_burst_its_per_minute_rate_and_then_waits_for_the_next_token() -> None:
    limiter = RateLimiter(10, clock=ManualClock())

    assert [limiter.take("192.0.2.1") for _ in range(10)] == [0] * 10
    assert limiter.take("192.0.2.1") == 6


def test_tokens_refill_continuously_and_a_refused_request_spends_none() -> None:
    clock = ManualClock()
    limiter = RateLimiter(10, clock=clock)
    for _ in range(10):
        limiter.take("192.0.2.1")

    clock.advance(5.9)
    assert limiter.take("192.0.2.1") == 1
    clock.advance(0.2)
    assert limiter.take("192.0.2.1") == 0


def test_the_wait_is_rounded_up_to_whole_seconds() -> None:
    limiter = RateLimiter(7, clock=ManualClock())
    for _ in range(7):
        limiter.take("192.0.2.1")

    # One token every 60 / 7 = 8.57 seconds.
    assert limiter.take("192.0.2.1") == 9


def test_each_client_has_its_own_bucket() -> None:
    limiter = RateLimiter(1, clock=ManualClock())

    assert limiter.take("192.0.2.1") == 0
    assert limiter.take("192.0.2.2") == 0
    assert limiter.take("192.0.2.1") == 60


def test_a_client_idle_for_a_minute_is_forgotten() -> None:
    clock = ManualClock()
    limiter = RateLimiter(10, clock=clock)
    limiter.take("192.0.2.1")
    limiter.take("192.0.2.2")
    clock.advance(30)
    limiter.take("192.0.2.2")
    clock.advance(30)

    limiter.take("192.0.2.3")

    assert list(limiter._buckets) == ["192.0.2.2", "192.0.2.3"]


def test_at_capacity_the_client_seen_longest_ago_is_forgotten_and_may_burst_again() -> None:
    clock = ManualClock()
    limiter = RateLimiter(1, clock=clock, max_clients=2)
    for client in ("192.0.2.1", "192.0.2.2", "192.0.2.3"):
        assert limiter.take(client) == 0
        clock.advance(1)

    assert list(limiter._buckets) == ["192.0.2.2", "192.0.2.3"]
    assert limiter.take("192.0.2.1") == 0
    assert list(limiter._buckets) == ["192.0.2.3", "192.0.2.1"]


async def read_whole_body(_scope: Scope, receive: Receive, _send: Send) -> None:
    more_body = True
    while more_body:
        message = await receive()
        more_body = message.get("more_body", False)


async def no_send(message: Message) -> None:
    raise AssertionError(f"Nothing should be sent, got {message}")


def http_scope(*headers: tuple[bytes, bytes]) -> Scope:
    return {"type": "http", "method": "POST", "path": "/datasets", "headers": list(headers)}


class Body:
    """Hands the body over in chunks, as a server streams it, and counts how many it gave."""

    def __init__(self, *chunks: bytes) -> None:
        self._chunks = deque(chunks)
        self.delivered = 0

    async def __call__(self) -> Message:
        self.delivered += 1
        chunk = self._chunks.popleft()
        return {"type": "http.request", "body": chunk, "more_body": bool(self._chunks)}


def test_the_default_limit_is_32_kib() -> None:
    assert MAX_BODY_BYTES == 32 * 1024


@pytest.mark.anyio
async def test_a_declared_length_over_the_limit_fails_before_any_of_the_body_is_read() -> None:
    body = Body(b"x" * 11)
    middleware = BodySizeLimitMiddleware(read_whole_body, max_bytes=10)

    with pytest.raises(HTTPException) as excinfo:
        await middleware(http_scope((b"content-length", b"11")), body, no_send)

    assert excinfo.value.status_code == 413
    assert excinfo.value.detail == "The request body must be at most 10 bytes."
    assert body.delivered == 0


@pytest.mark.anyio
async def test_a_streamed_body_fails_at_the_chunk_that_crosses_the_limit() -> None:
    body = Body(b"x" * 6, b"x" * 6, b"x" * 6)
    middleware = BodySizeLimitMiddleware(read_whole_body, max_bytes=10)

    with pytest.raises(HTTPException) as excinfo:
        await middleware(http_scope(), body, no_send)

    assert excinfo.value.status_code == 413
    assert body.delivered == 2


@pytest.mark.anyio
async def test_a_body_of_exactly_the_limit_is_read_in_full() -> None:
    body = Body(b"x" * 4, b"x" * 6)
    middleware = BodySizeLimitMiddleware(read_whole_body, max_bytes=10)

    await middleware(http_scope((b"content-length", b"10")), body, no_send)

    assert body.delivered == 2
