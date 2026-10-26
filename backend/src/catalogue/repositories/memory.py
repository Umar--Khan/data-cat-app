import itertools
from collections.abc import Iterable, Sequence

from catalogue.domain.errors import DatasetNotFoundError
from catalogue.domain.models import CuratedDataset, Dataset


class InMemoryDatasetRepository:
    """Holds the catalogue in process memory, so a restart brings back only the initial records.

    New ids count up from the highest initial id and are never reissued, so a client holding the
    id of a deleted record can never delete a newer one by mistake. No method awaits, which is
    what makes each one atomic on the event loop without a lock.
    """

    def __init__(self, initial: Iterable[Dataset] = ()) -> None:
        self._datasets = {dataset.id: dataset for dataset in initial}
        self._ids = itertools.count(max(map(int, self._datasets), default=0) + 1)

    async def list(self) -> Sequence[Dataset]:
        return tuple(self._datasets.values())

    async def add(self, dataset: CuratedDataset) -> Dataset:
        stored = Dataset(
            id=str(next(self._ids)),
            name=dataset.new.name,
            owner=dataset.new.owner,
            description=dataset.new.description,
            curation=dataset.curation,
            created_at=dataset.created_at,
        )
        self._datasets[stored.id] = stored
        return stored

    async def delete(self, dataset_id: str) -> Dataset:
        dataset = self._datasets.pop(dataset_id, None)
        if dataset is None:
            raise DatasetNotFoundError(dataset_id)
        return dataset
