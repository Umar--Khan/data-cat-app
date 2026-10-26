import math
import time
from collections.abc import Callable
from dataclasses import dataclass
from http import HTTPStatus
from typing import Final

from starlette.datastructures import Headers
from starlette.exceptions import HTTPException
from starlette.types import ASGIApp, Message, Receive, Scope, Send

# The largest valid body holds 2,240 code points of field values. JSON can escape each astral code
# point as a 12-byte surrogate pair, so even that body stays under 27 KB, and 32 KiB leaves room
# for the keys and for whitespace the API trims.
MAX_BODY_BYTES: Final = 32 * 1024
# Bounds the rate limiter's memory however many addresses arrive.
MAX_TRACKED_CLIENTS: Final = 10_000
# A bucket's burst equals its per-minute rate, so an empty bucket is full again after one window.
_WINDOW_SECONDS: Final = 60.0

type MonotonicClock = Callable[[], float]


class BodySizeLimitMiddleware:
    """Rejects a request body over `max_bytes` with a 413 problem, before it is buffered.

    The check sits in `receive`, which the route calls to read the body, so the 413 is raised
    inside the app and rendered by the problem handlers with CORS headers. Starlette's own
    RequestBodyLimitMiddleware answers in text/plain instead. It must be installed inside
    CORSMiddleware.
    """

    def __init__(self, app: ASGIApp, max_bytes: int = MAX_BODY_BYTES) -> None:
        self.app = app
        self.max_bytes = max_bytes

    async def __call__(self, scope: Scope, receive: Receive, send: Send) -> None:
        if scope["type"] != "http":
            await self.app(scope, receive, send)
            return

        declared = Headers(scope=scope).get("content-length", "")
        received = 0

        async def limited_receive() -> Message:
            nonlocal received
            # A declared length is checked before any of the body is read. Uvicorn rejects a
            # malformed one itself, and a chunked body declares none, so the count below is what
            # stops those.
            if declared.isdecimal() and int(declared) > self.max_bytes:
                raise self._too_large()
            message = await receive()
            received += len(message.get("body", b""))
            if received > self.max_bytes:
                raise self._too_large()
            return message

        await self.app(scope, limited_receive, send)

    def _too_large(self) -> HTTPException:
        return HTTPException(
            HTTPStatus.CONTENT_TOO_LARGE,
            f"The request body must be at most {self.max_bytes} bytes.",
        )


@dataclass(slots=True)
class _Bucket:
    tokens: float
    updated: float


class RateLimiter:
    """A token bucket per client, holding `per_minute` tokens and refilled continuously.

    Each `take` spends one token. The burst equals the per-minute rate, so a client can act that
    many times at once and then once every 60 / `per_minute` seconds.
    """

    def __init__(
        self,
        per_minute: int,
        *,
        clock: MonotonicClock = time.monotonic,
        max_clients: int = MAX_TRACKED_CLIENTS,
    ) -> None:
        self._capacity = float(per_minute)
        self._refill_per_second = per_minute / _WINDOW_SECONDS
        self._clock = clock
        self._max_clients = max_clients
        # Least recently seen first: `take` moves a client to the end, so idle ones collect at the
        # front, where forgetting them costs nothing per bucket kept.
        self._buckets: dict[str, _Bucket] = {}

    def take(self, client: str) -> int:
        """Spend one of `client`'s tokens and return 0, or return whole seconds until it has one."""
        now = self._clock()
        self._forget_idle(now)
        bucket = self._buckets.pop(client, None)
        if bucket is None:
            if len(self._buckets) >= self._max_clients:
                # Every tracked client was seen within the window. Forgetting the one seen
                # longest ago lets it burst again, which is cheaper than refusing new clients.
                del self._buckets[next(iter(self._buckets))]
            bucket = _Bucket(tokens=self._capacity, updated=now)
        else:
            refilled = bucket.tokens + (now - bucket.updated) * self._refill_per_second
            bucket.tokens = min(self._capacity, refilled)
            bucket.updated = now
        self._buckets[client] = bucket
        if bucket.tokens >= 1:
            bucket.tokens -= 1
            return 0
        return math.ceil((1 - bucket.tokens) / self._refill_per_second)

    def _forget_idle(self, now: float) -> None:
        # A bucket left alone for a whole window is full again, and a full bucket behaves exactly
        # like no bucket, so dropping it forgets nothing.
        while self._buckets:
            oldest = next(iter(self._buckets))
            if now - self._buckets[oldest].updated < _WINDOW_SECONDS:
                return
            del self._buckets[oldest]
