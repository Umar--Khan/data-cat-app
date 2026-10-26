import asyncio
import logging
from dataclasses import dataclass, field
from typing import cast

import pytest

from catalogue.curation.base import CurationDraft, CurationError, CurationFailure
from catalogue.curation.service import CurationService
from catalogue.domain.models import Curation, CurationProviderName, NewDataset

NEW = NewDataset(
    name="Trade Confirmations",
    owner="Middle Office",
    description=(
        "Daily export of confirmed trades including instrument type, counterparty, notional "
        "value, and settlement date."
    ),
)
SDK_MESSAGE = "Error code: 529 - overloaded_error, request_id req_011CTest"


@dataclass(frozen=True, slots=True)
class ScriptedProvider:
    """Returns its draft, or raises its exception, as a real provider would."""

    outcome: CurationDraft | Exception
    name: CurationProviderName = "anthropic"
    model: str | None = "claude-test"
    received: list[NewDataset] = field(default_factory=list)

    async def curate(self, new: NewDataset) -> CurationDraft:
        self.received.append(new)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome


def failing_with(failure: CurationFailure) -> ScriptedProvider:
    """A provider raising `failure` the way providers must: chained to the SDK's error."""
    error = CurationError(failure)
    error.__cause__ = RuntimeError(SDK_MESSAGE)
    return ScriptedProvider(error)


@pytest.mark.anyio
async def test_a_usable_draft_completes_with_normalised_tags_and_summary() -> None:
    draft = CurationDraft(
        tags=("#Trading", "trading", "Real Time", "data", "pii"),
        summary='  "a daily export of confirmed trades.  Updated nightly."',
    )
    provider = ScriptedProvider(draft)

    result = await CurationService(provider).curate(NEW)

    assert provider.received == [NEW]
    assert result == Curation(
        status="completed",
        provider="anthropic",
        tags=("trading", "real-time", "PII"),
        summary="A daily export of confirmed trades.",
        detail=None,
    )


@pytest.mark.anyio
async def test_the_result_names_the_provider_that_ran() -> None:
    provider = ScriptedProvider(CurationDraft(tags=("finance",), summary="A feed."), name="keyword")

    result = await CurationService(provider).curate(NEW)

    assert result.provider == "keyword"


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("failure", "detail"),
    [
        (CurationFailure.TIMEOUT, "AI curation timed out."),
        (CurationFailure.RATE_LIMITED, "The AI service is handling too many requests."),
        (CurationFailure.UNAVAILABLE, "The AI service could not be reached."),
        (CurationFailure.MISCONFIGURED, "AI curation is not configured correctly on the server."),
        (CurationFailure.REFUSED, "The AI model declined to curate this description."),
        (CurationFailure.INVALID_OUTPUT, "The AI response could not be used."),
        (CurationFailure.UNEXPECTED, "AI curation failed unexpectedly."),
    ],
)
async def test_each_failure_row_saves_no_curation_and_only_the_user_safe_detail(
    failure: CurationFailure, detail: str
) -> None:
    result = await CurationService(failing_with(failure)).curate(NEW)

    assert result == Curation(
        status="failed", provider="anthropic", tags=(), summary=None, detail=detail
    )


@pytest.mark.anyio
async def test_a_typed_failure_logs_its_cause_without_a_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    with caplog.at_level(logging.WARNING, logger="catalogue"):
        await CurationService(failing_with(CurationFailure.UNAVAILABLE)).curate(NEW)

    [record] = caplog.records
    assert record.name == "catalogue.curation.service"
    assert record.levelno == logging.WARNING
    assert record.getMessage() == (
        f"Curation by anthropic failed as unavailable: RuntimeError('{SDK_MESSAGE}')"
    )
    assert record.exc_info is None


@pytest.mark.anyio
async def test_a_typed_failure_without_a_cause_logs_only_the_failure(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = ScriptedProvider(CurationError(CurationFailure.REFUSED))

    with caplog.at_level(logging.WARNING, logger="catalogue"):
        await CurationService(provider).curate(NEW)

    assert [record.getMessage() for record in caplog.records] == [
        "Curation by anthropic failed as refused"
    ]


@pytest.mark.anyio
@pytest.mark.parametrize(
    "draft",
    [
        pytest.param(CurationDraft(tags=("data", "#", "misc"), summary="A feed."), id="no-tag"),
        pytest.param(CurationDraft(tags=(), summary="A feed."), id="empty-tags"),
        pytest.param(CurationDraft(tags=("finance",), summary="  "), id="blank-summary"),
        pytest.param(CurationDraft(tags=("finance",), summary='"..."'), id="punctuation-summary"),
        pytest.param(
            CurationDraft(tags=("finance",), summary="\u200b\u202e\x07"), id="invisible-summary"
        ),
    ],
)
async def test_nothing_usable_after_normalising_is_invalid_output(
    draft: CurationDraft, caplog: pytest.LogCaptureFixture
) -> None:
    with caplog.at_level(logging.WARNING, logger="catalogue"):
        result = await CurationService(ScriptedProvider(draft)).curate(NEW)

    assert result == Curation.failed("anthropic", CurationFailure.INVALID_OUTPUT.detail)
    [record] = caplog.records
    assert record.getMessage() == (
        "Curation by anthropic failed as invalid_output: nothing usable left after "
        f"normalising {draft!r}"
    )


@pytest.mark.anyio
async def test_an_unexpected_provider_error_fails_safely_and_logs_a_traceback(
    caplog: pytest.LogCaptureFixture,
) -> None:
    provider = ScriptedProvider(RuntimeError(SDK_MESSAGE))

    with caplog.at_level(logging.WARNING, logger="catalogue"):
        result = await CurationService(provider).curate(NEW)

    assert result == Curation.failed("anthropic", CurationFailure.UNEXPECTED.detail)
    [record] = caplog.records
    assert record.levelno == logging.ERROR
    assert record.getMessage() == "Curation by anthropic failed unexpectedly"
    assert record.exc_info is not None
    assert record.exc_info[1] is provider.outcome
    assert SDK_MESSAGE in caplog.text


@pytest.mark.anyio
async def test_an_error_inside_the_normaliser_is_unexpected() -> None:
    # Telling the type checker otherwise is the only way to hand the normaliser a value it cannot
    # handle.
    draft = CurationDraft(tags=cast("tuple[str, ...]", (42,)), summary="A feed.")

    result = await CurationService(ScriptedProvider(draft)).curate(NEW)

    assert result == Curation.failed("anthropic", CurationFailure.UNEXPECTED.detail)


@dataclass(frozen=True, slots=True)
class StalledProvider:
    """Never finishes, like a provider waiting on a slow API."""

    received: asyncio.Queue[NewDataset]
    name: CurationProviderName = "anthropic"
    model: str | None = "claude-test"

    async def curate(self, new: NewDataset) -> CurationDraft:
        self.received.put_nowait(new)
        never: asyncio.Future[CurationDraft] = asyncio.get_running_loop().create_future()
        return await never


@pytest.mark.anyio
async def test_cancellation_propagates_instead_of_becoming_a_failed_result(
    caplog: pytest.LogCaptureFixture,
) -> None:
    received: asyncio.Queue[NewDataset] = asyncio.Queue()
    task = asyncio.create_task(CurationService(StalledProvider(received)).curate(NEW))
    assert await received.get() == NEW

    with caplog.at_level(logging.WARNING, logger="catalogue"):
        task.cancel()
        with pytest.raises(asyncio.CancelledError):
            await task

    assert task.cancelled()
    assert caplog.records == []
