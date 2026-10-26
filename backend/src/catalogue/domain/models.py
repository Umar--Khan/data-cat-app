from dataclasses import dataclass
from datetime import datetime
from typing import Literal

type CurationStatus = Literal["completed", "failed"]
type CurationProviderName = Literal["anthropic", "keyword"]
# Spelled out rather than built from CurationProviderName: a union of the two would reach OpenAPI
# as an anyOf of a reference and a constant instead of one named enum.
type CurationSource = Literal["anthropic", "keyword", "seed"]


@dataclass(frozen=True, slots=True)
class NewDataset:
    """A dataset as a user registers it, before curation.

    The API has already trimmed the values and checked their lengths, so nothing below it
    validates them again.
    """

    name: str
    owner: str
    description: str


@dataclass(frozen=True, slots=True)
class Curation:
    """Where a dataset's tags and summary came from and whether curation worked.

    `detail` is shown to users, so it is a plain sentence and never an SDK message.
    """

    status: CurationStatus
    provider: CurationSource
    detail: str | None


@dataclass(frozen=True, slots=True)
class Dataset:
    """A catalogue entry as stored.

    The in-memory store hands out the objects it holds, so immutability, down to `tags` being a
    tuple, is what stops a caller changing the catalogue. `created_at` is timezone-aware UTC so it
    serialises with a `Z` suffix.
    """

    id: str
    name: str
    owner: str
    description: str
    tags: tuple[str, ...]
    summary: str | None
    curation: Curation
    created_at: datetime
