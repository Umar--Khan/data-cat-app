from collections.abc import Sequence
from typing import Protocol

from catalogue.domain.models import CuratedDataset, Dataset


class DatasetRepository(Protocol):
    """Storage for catalogue entries.

    Methods are async so a store that does I/O can implement the protocol. Each operation is one
    call that must be atomic: `add` both assigns the id and stores the record, so there is no
    read-then-write step for callers to lock. The in-memory store gets that atomicity by never
    awaiting inside a method, so each call runs to completion on the one event loop.
    """

    async def list(self) -> Sequence[Dataset]:
        """Every dataset, oldest first, as a snapshot that later writes do not change."""
        ...

    async def add(self, dataset: CuratedDataset) -> Dataset:
        """Store a dataset under a fresh id and return it as stored, like INSERT … RETURNING."""
        ...

    async def delete(self, dataset_id: str) -> Dataset:
        """Remove a dataset and return it, or raise `DatasetNotFoundError`."""
        ...
