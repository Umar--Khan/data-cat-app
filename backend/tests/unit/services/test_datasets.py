from datetime import UTC, datetime, timedelta

import anyio
import anyio.to_thread
import pytest

from catalogue.curation.base import CurationError, CurationFailure
from catalogue.curation.service import CurationService
from catalogue.domain.errors import DatasetNotFoundError
from catalogue.domain.models import Curation, Dataset, NewDataset
from catalogue.repositories.memory import InMemoryDatasetRepository
from catalogue.services.datasets import DatasetService, utc_now
from tests.fakes import DRAFT, FakeCurationProvider, Gate, TickingClock

NEW = NewDataset(
    name="Trade Confirmations",
    owner="Middle Office",
    description="Daily export of confirmed trades including instrument type and counterparty.",
)


def service_with(
    provider: FakeCurationProvider, clock: TickingClock, repository: InMemoryDatasetRepository
) -> DatasetService:
    return DatasetService(repository, CurationService(provider), clock)


@pytest.mark.anyio
async def test_create_stores_the_curation_result_under_a_new_id() -> None:
    clock = TickingClock()
    repository = InMemoryDatasetRepository()
    service = service_with(FakeCurationProvider(), clock, repository)

    dataset = await service.create(NEW)

    assert dataset == Dataset(
        id="1",
        name=NEW.name,
        owner=NEW.owner,
        description=NEW.description,
        curation=Curation.completed("keyword", DRAFT.tags, DRAFT.summary),
        created_at=TickingClock.START,
    )
    assert await repository.list() == (dataset,)


@pytest.mark.anyio
async def test_create_stores_a_failed_curation_with_no_tags_or_summary() -> None:
    provider = FakeCurationProvider(script=[CurationError(CurationFailure.TIMEOUT)])
    service = service_with(provider, TickingClock(), InMemoryDatasetRepository())

    dataset = await service.create(NEW)

    assert dataset.curation == Curation.failed("keyword", "AI curation timed out.")


@pytest.mark.anyio
async def test_create_reads_the_clock_only_after_curation() -> None:
    gate = Gate()
    clock = TickingClock()
    service = service_with(
        FakeCurationProvider(gates={NEW.name: gate}), clock, InMemoryDatasetRepository()
    )

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(service.create, NEW)
        await anyio.to_thread.run_sync(gate.reached.wait, Gate.TIMEOUT_SECONDS)
        assert clock.readings == []
        gate.open()

    assert clock.readings == [TickingClock.START]


@pytest.mark.anyio
async def test_overlapping_creates_are_stored_in_the_order_of_their_timestamps() -> None:
    gate = Gate()
    repository = InMemoryDatasetRepository()
    service = service_with(FakeCurationProvider(gates={"First": gate}), TickingClock(), repository)
    first = NewDataset(name="First", owner=NEW.owner, description=NEW.description)
    second = NewDataset(name="Second", owner=NEW.owner, description=NEW.description)

    async with anyio.create_task_group() as tasks:
        tasks.start_soon(service.create, first)
        await anyio.to_thread.run_sync(gate.reached.wait, Gate.TIMEOUT_SECONDS)
        await service.create(second)
        gate.open()

    stored = [(dataset.id, dataset.name, dataset.created_at) for dataset in await repository.list()]
    assert stored == [
        ("1", "Second", TickingClock.START),
        ("2", "First", TickingClock.START + timedelta(seconds=1)),
    ]


@pytest.mark.anyio
async def test_list_returns_every_dataset_oldest_first() -> None:
    service = service_with(FakeCurationProvider(), TickingClock(), InMemoryDatasetRepository())
    created = [
        await service.create(NewDataset(name=name, owner=NEW.owner, description=NEW.description))
        for name in ("First", "Second")
    ]

    assert list(await service.list()) == created


@pytest.mark.anyio
async def test_delete_removes_the_dataset_and_returns_it() -> None:
    repository = InMemoryDatasetRepository()
    service = service_with(FakeCurationProvider(), TickingClock(), repository)
    dataset = await service.create(NEW)

    assert await service.delete(dataset.id) == dataset
    assert await repository.list() == ()


@pytest.mark.anyio
async def test_delete_of_an_unknown_id_raises_dataset_not_found() -> None:
    service = service_with(FakeCurationProvider(), TickingClock(), InMemoryDatasetRepository())

    with pytest.raises(DatasetNotFoundError) as excinfo:
        await service.delete("42")

    assert excinfo.value.dataset_id == "42"


def test_utc_now_is_timezone_aware_utc() -> None:
    before = datetime.now(UTC)

    now = utc_now()

    assert now.tzinfo is UTC
    assert before <= now <= datetime.now(UTC)
