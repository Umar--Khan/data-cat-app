from dataclasses import dataclass
from datetime import datetime
from typing import Final, Literal, Self

type CurationStatus = Literal["completed", "failed"]
type CurationProviderName = Literal["anthropic", "keyword"]
# Spelled out rather than built from CurationProviderName: a union of the two would reach OpenAPI
# as an anyOf of a reference and a constant instead of one named enum.
type CurationSource = Literal["anthropic", "keyword", "seed"]

# In code points, after trimming. The API's wire schema checks the same limits first, so a client
# hears about one as a field error; these hold for every other caller.
MAX_NAME_LENGTH: Final = 120
MAX_OWNER_LENGTH: Final = 120
MAX_DESCRIPTION_LENGTH: Final = 2000


@dataclass(frozen=True, slots=True)
class NewDataset:
    """A dataset as a user registers it, before curation.

    The length limits are checked here because they bound what a curation costs, whoever builds
    the dataset. Trimming and the character rules are the API's: they decide what a client may
    send, not what a curation may cost.
    """

    name: str
    owner: str
    description: str

    def __post_init__(self) -> None:
        for field, value, limit in (
            ("name", self.name, MAX_NAME_LENGTH),
            ("owner", self.owner, MAX_OWNER_LENGTH),
            ("description", self.description, MAX_DESCRIPTION_LENGTH),
        ):
            if not 1 <= len(value) <= limit:
                raise ValueError(f"{field} must be 1 to {limit} characters, not {len(value)}")


@dataclass(frozen=True, slots=True)
class Curation:
    """A dataset's tags and summary, who produced them, and whether curation worked.

    A failed curation has no tags and no summary, only a `detail`. Users read it, so it is a plain
    sentence and never an SDK message.
    """

    status: CurationStatus
    provider: CurationSource
    tags: tuple[str, ...]
    summary: str | None
    detail: str | None

    @classmethod
    def completed(cls, provider: CurationSource, tags: tuple[str, ...], summary: str) -> Self:
        return cls(status="completed", provider=provider, tags=tags, summary=summary, detail=None)

    @classmethod
    def failed(cls, provider: CurationSource, detail: str) -> Self:
        return cls(status="failed", provider=provider, tags=(), summary=None, detail=detail)


@dataclass(frozen=True, slots=True)
class CuratedDataset:
    """A new dataset with its curation and timestamp: a `Dataset` before storage assigns its id."""

    new: NewDataset
    curation: Curation
    created_at: datetime


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
    curation: Curation
    created_at: datetime

    @property
    def tags(self) -> tuple[str, ...]:
        return self.curation.tags

    @property
    def summary(self) -> str | None:
        return self.curation.summary
