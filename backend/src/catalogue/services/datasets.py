from collections.abc import Callable, Sequence
from datetime import UTC, datetime

from catalogue.curation.service import CurationService
from catalogue.domain.models import Curation, Dataset, NewDataset
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
        return self._repository.list()

    async def create(self, new: NewDataset) -> Dataset:
        """Curate a new dataset and store it, whatever the curation outcome.

        The timestamp is read after curation, immediately before `add()`, with no await between
        them. Two overlapping creates are therefore stored in the order of their timestamps, so
        list order and `createdAt` always agree.
        """
        result = await self._curation.curate(new)
        return self._repository.add(
            new,
            tags=result.tags,
            summary=result.summary,
            curation=Curation(status=result.status, provider=result.provider, detail=result.detail),
            created_at=self._clock(),
        )

    async def delete(self, dataset_id: str) -> Dataset:
        """Remove a dataset and return it, or raise `DatasetNotFoundError`."""
        return self._repository.delete(dataset_id)
