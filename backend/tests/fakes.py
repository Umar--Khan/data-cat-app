import threading
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta

import anyio.to_thread

from catalogue.curation.base import CurationDraft
from catalogue.domain.models import CurationProviderName, NewDataset

DRAFT = CurationDraft(
    tags=["trading", "finance", "settlements", "daily"],
    summary=(
        "A daily export of confirmed trades covering instrument type, counterparty, and notional "
        "value."
    ),
)


class Gate:
    """Holds a curation until the test opens it, so requests can overlap deterministically.

    Under TestClient the app's event loop runs in another thread, so the gate uses thread-safe
    events and waits for them off the loop. The wait is bounded so a broken test fails instead of
    hanging.
    """

    TIMEOUT_SECONDS = 5

    def __init__(self) -> None:
        self.reached = threading.Event()
        self._opened = threading.Event()

    def open(self) -> None:
        self._opened.set()

    async def pass_through(self) -> None:
        self.reached.set()
        opened = await anyio.to_thread.run_sync(self._opened.wait, self.TIMEOUT_SECONDS)
        if not opened:
            raise TimeoutError("The test never opened the gate")


@dataclass
class FakeCurationProvider:
    """A curation provider that follows a script.

    Each call removes the next outcome from `script`, returning a draft or raising an exception,
    and returns `DRAFT` once the script is empty. A call for a dataset named in `gates` waits at
    that gate first.
    """

    script: list[CurationDraft | Exception] = field(default_factory=list)
    gates: dict[str, Gate] = field(default_factory=dict)
    name: CurationProviderName = "keyword"
    model: str | None = None
    received: list[NewDataset] = field(default_factory=list)

    async def curate(self, new: NewDataset) -> CurationDraft:
        self.received.append(new)
        gate = self.gates.get(new.name)
        if gate is not None:
            await gate.pass_through()
        outcome = self.script.pop(0) if self.script else DRAFT
        if isinstance(outcome, Exception):
            raise outcome
        return outcome


class TickingClock:
    """A clock whose every reading is one second after the last, so readings show their order."""

    START = datetime(2026, 10, 25, 9, 30, tzinfo=UTC)

    def __init__(self) -> None:
        self.readings: list[datetime] = []

    def __call__(self) -> datetime:
        reading = self.START + timedelta(seconds=len(self.readings))
        self.readings.append(reading)
        return reading
