import itertools
from collections.abc import Iterable, Sequence
from datetime import datetime

from catalogue.domain.errors import DatasetNotFoundError
from catalogue.domain.models import Curation, Dataset, NewDataset


class InMemoryDatasetRepository:
    """Holds the catalogue in process memory, so a restart brings back only the initial records.

    New ids count up from the highest initial id and are never reissued, so a client holding the
    id of a deleted record can never delete a newer one by mistake.
    """

    def __init__(self, initial: Iterable[Dataset] = ()) -> None:
        self._datasets = {dataset.id: dataset for dataset in initial}
        self._ids = itertools.count(max(map(int, self._datasets), default=0) + 1)

    def list(self) -> Sequence[Dataset]:
        return tuple(self._datasets.values())

    def add(
        self,
        new: NewDataset,
        *,
        tags: tuple[str, ...],
        summary: str | None,
        curation: Curation,
        created_at: datetime,
    ) -> Dataset:
        dataset = Dataset(
            id=str(next(self._ids)),
            name=new.name,
            owner=new.owner,
            description=new.description,
            tags=tags,
            summary=summary,
            curation=curation,
            created_at=created_at,
        )
        self._datasets[dataset.id] = dataset
        return dataset

    def delete(self, dataset_id: str) -> Dataset:
        dataset = self._datasets.pop(dataset_id, None)
        if dataset is None:
            raise DatasetNotFoundError(dataset_id)
        return dataset
