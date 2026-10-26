from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol

from catalogue.domain.models import CurationProviderName, NewDataset


@dataclass(frozen=True, slots=True)
class CurationDraft:
    """A provider's raw tags and summary, which `CurationService` normalises before storing.

    Raw means unchecked: a provider may return more tags than are kept, or a summary that is too
    long or empty, and the normaliser decides what survives.
    """

    tags: tuple[str, ...]
    summary: str


class CurationFailure(StrEnum):
    """Why a curation failed: one member per row of the Failures table in specs/curation.md."""

    TIMEOUT = "timeout"
    RATE_LIMITED = "rate_limited"
    UNAVAILABLE = "unavailable"
    MISCONFIGURED = "misconfigured"
    REFUSED = "refused"
    INVALID_OUTPUT = "invalid_output"
    UNEXPECTED = "unexpected"

    @property
    def detail(self) -> str:
        """The sentence stored as `curation.detail`.

        Users read it, so it never names an SDK error, a status code or a request id; those go
        to the log.
        """
        return _DETAILS[self]


_DETAILS: Final[Mapping[CurationFailure, str]] = {
    CurationFailure.TIMEOUT: "AI curation timed out.",
    CurationFailure.RATE_LIMITED: "The AI service is handling too many requests.",
    CurationFailure.UNAVAILABLE: "The AI service could not be reached.",
    CurationFailure.MISCONFIGURED: "AI curation is not configured correctly on the server.",
    CurationFailure.REFUSED: "The AI model declined to curate this description.",
    CurationFailure.INVALID_OUTPUT: "The AI response could not be used.",
    CurationFailure.UNEXPECTED: "AI curation failed unexpectedly.",
}


class CurationError(Exception):
    """Raised by a provider for a failure it recognises.

    Raise it `from` the original exception, so the log keeps the SDK's details while users see
    only the failure's `detail`.
    """

    def __init__(self, failure: CurationFailure) -> None:
        super().__init__(failure)
        self.failure = failure


class CurationProvider(Protocol):
    """Turns a new dataset into a raw draft.

    `CurationService` normalises the draft and turns any exception, `CurationError` or not, into
    a failed curation, so a provider raises `CurationError` only to say which failure it was.
    """

    @property
    def name(self) -> CurationProviderName: ...

    @property
    def model(self) -> str | None:
        """The model the provider asks for, or None when it calls no model."""
        ...

    async def curate(self, new: NewDataset) -> CurationDraft: ...
