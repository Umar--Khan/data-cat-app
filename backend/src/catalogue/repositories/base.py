from collections.abc import Sequence
from datetime import datetime
from typing import Protocol

from catalogue.domain.models import Curation, Dataset, NewDataset


class DatasetRepository(Protocol):
    """Storage for catalogue entries.

    Methods are synchronous on purpose. With one event loop that makes every call atomic without
    a lock, and it is why `add` both assigns the id and stores the record: an implementation that
    awaited between the two would need a lock this protocol cannot express.
    """

    def list(self) -> Sequence[Dataset]:
        """Every dataset, oldest first, as a snapshot that later writes do not change."""
        ...

    def add(
        self,
        new: NewDataset,
        *,
        tags: tuple[str, ...],
        summary: str | None,
        curation: Curation,
        created_at: datetime,
    ) -> Dataset:
        """Store a dataset under a fresh id and return it as stored, like INSERT … RETURNING."""
        ...

    def delete(self, dataset_id: str) -> Dataset:
        """Remove a dataset and return it, or raise `DatasetNotFoundError`."""
        ...
