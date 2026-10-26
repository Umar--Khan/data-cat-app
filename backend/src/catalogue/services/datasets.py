from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from catalogue.curation.service import CurationService
from catalogue.domain.models import CuratedDataset, Dataset, NewDataset
from catalogue.repositories.base import DatasetRepository

type Clock = Callable[[], datetime]


def utc_now() -> datetime:
    """The production clock. Aware UTC, so `createdAt` reaches the wire with a `Z` suffix."""
    return datetime.now(UTC)


class DatasetService:
    """The catalogue's use cases: list, create (curate, then store) and delete."""

    def __init__(
        self, repository: DatasetRepository, curation: CurationService, clock: Clock
    ) -> None:
        self._repository = repository
        self._curation = curation
        self._clock = clock

    async def list(self) -> Sequence[Dataset]:
        return await self._repository.list()

    async def create(self, new: NewDataset) -> Dataset:
        """Curate a new dataset and store it, whatever the curation outcome.

        The timestamp is read after curation, as `add()` is called. A store that never awaits
        inside `add()` stores the record before any other request runs, so two overlapping
        creates are stored in the order of their timestamps and list order agrees with
        `createdAt`.
        """
        curation = await self._curation.curate(new)
        return await self._repository.add(CuratedDataset(new, curation, self._clock()))

    async def delete(self, dataset_id: str) -> Dataset:
        """Remove a dataset and return it, or raise `DatasetNotFoundError`."""
        return await self._repository.delete(dataset_id)
