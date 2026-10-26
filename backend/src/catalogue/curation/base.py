from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from typing import Final, Protocol, Self

from pydantic import BaseModel, Field

from catalogue.domain.models import CurationProviderName, CurationStatus, NewDataset


# The SDK sends this model as the structured-output schema, docstring and descriptions included,
# so they are written for Claude. It carries no maxItems or maxLength: the SDK moves both out of
# the schema it sends, into the description text, but still enforces them on the reply, so one
# surplus tag would fail the whole curation. The descriptions state the limits and the normaliser
# enforces them.
class CurationDraft(BaseModel):
    """Catalogue curation of one dataset: tags in facet order and a one-sentence summary."""

    tags: list[str] = Field(
        description=(
            "Up to 6 tags, usually 3 to 5, ordered by facet: domain, subject, sensitivity, "
            "cadence, with at most two per facet. Leave out any facet the dataset gives no "
            "evidence for. Each tag is a single lowercase word or a short hyphenated phrase, with "
            'acronyms in upper case (PII, HR, FX). Never a generic tag such as "data".'
        )
    )
    summary: str = Field(
        description=(
            'Exactly one sentence of at most 30 words, starting with "A" or "An", saying what '
            "the dataset is and what it covers, including its cadence when known. It never names "
            "the owning team or adds facts the dataset does not support."
        )
    )


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
    a failed result, so a provider raises `CurationError` only to say which failure it was.
    """

    @property
    def name(self) -> CurationProviderName: ...

    @property
    def model(self) -> str | None:
        """The model the provider asks for, or None when it calls no model."""
        ...

    async def curate(self, new: NewDataset) -> CurationDraft: ...


@dataclass(frozen=True, slots=True)
class CurationResult:
    """The outcome `CurationService` hands to `DatasetService` to store with the record."""

    status: CurationStatus
    provider: CurationProviderName
    tags: tuple[str, ...]
    summary: str | None
    detail: str | None

    @classmethod
    def completed(cls, provider: CurationProviderName, tags: tuple[str, ...], summary: str) -> Self:
        return cls(status="completed", provider=provider, tags=tags, summary=summary, detail=None)

    @classmethod
    def failed(cls, provider: CurationProviderName, failure: CurationFailure) -> Self:
        return cls(status="failed", provider=provider, tags=(), summary=None, detail=failure.detail)
