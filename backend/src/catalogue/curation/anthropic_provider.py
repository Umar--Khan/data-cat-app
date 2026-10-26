import asyncio
import logging
from http import HTTPStatus
from typing import Final

from anthropic import (
    APIConnectionError,
    APIStatusError,
    APITimeoutError,
    AsyncAnthropic,
    AsyncAPIResponse,
    omit,
)
from anthropic.types.beta import BetaTextBlockParam
from anthropic.types.beta.parsed_beta_message import ParsedBetaMessage
from pydantic import BaseModel, ConfigDict, Field, ValidationError

from catalogue.curation.base import CurationDraft, CurationError, CurationFailure
from catalogue.curation.prompt import SYSTEM_PROMPT, render_dataset
from catalogue.domain.models import CurationProviderName, NewDataset

logger = logging.getLogger(__name__)

# The models that accept the server-side refusal fallback. Any other model answers its beta
# parameters with a 400, so sending them unconditionally would let a model change fail every call.
FALLBACK_MODELS: Final = frozenset(
    {"claude-opus-5-5", "claude-opus-5", "claude-fable-5-1", "claude-sonnet-5-5"}
)

# Opus 5.5 always thinks, and its thinking counts toward this limit as well as the short reply.
_MAX_TOKENS: Final = 4096
_FALLBACK_BETA: Final = "server-side-fallback-2026-07-01"
_SYSTEM: Final[tuple[BetaTextBlockParam, ...]] = (
    {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
)


# The SDK sends this model as the structured-output schema, docstring and descriptions included,
# so they are written for Claude. It carries no maxItems or maxLength: the SDK moves both out of
# the schema it sends, into the description text, but still enforces them on the reply, so one
# surplus tag would fail the whole curation. The descriptions state the limits and the normaliser
# enforces them. Claude also sees the title, which names the draft rather than this class.
class _ClaudeCuration(BaseModel):
    """Catalogue curation of one dataset: tags in facet order and a one-sentence summary."""

    model_config = ConfigDict(title="CurationDraft")

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


class AnthropicCurationProvider:
    """Curates with Claude through structured outputs.

    The caller owns the client and closes it. Each failure the Failures table in specs/curation.md
    names is raised as a `CurationError` from the SDK's exception, so the log keeps the SDK's
    details while users see only the failure's sentence.
    """

    name: Final[CurationProviderName] = "anthropic"

    def __init__(
        self,
        client: AsyncAnthropic,
        *,
        model: str,
        timeout_seconds: float,
    ) -> None:
        self.model: Final = model
        self._client = client
        self._budget = timeout_seconds
        self._fallback = model in FALLBACK_MODELS

    async def curate(self, new: NewDataset) -> CurationDraft:
        try:
            async with asyncio.timeout(self._budget):
                # The raw response outlives a ValidationError from parsing, so the log can still
                # say what Claude stopped on and which request it was.
                response = await self._client.beta.messages.with_raw_response.parse(
                    model=self.model,
                    max_tokens=_MAX_TOKENS,
                    system=_SYSTEM,
                    messages=[{"role": "user", "content": render_dataset(new)}],
                    output_config={"effort": "low"},
                    output_format=_ClaudeCuration,
                    betas=[_FALLBACK_BETA] if self._fallback else omit,
                    fallbacks="default" if self._fallback else omit,
                )
                try:
                    message = await response.parse()
                except ValidationError:
                    _log_unparseable(response)
                    raise
        except (TimeoutError, APITimeoutError) as error:
            raise CurationError(CurationFailure.TIMEOUT) from error
        except APIConnectionError as error:
            raise CurationError(CurationFailure.UNAVAILABLE) from error
        except APIStatusError as error:
            raise CurationError(_failure_for_status(error.status_code)) from error
        except ValidationError as error:
            raise CurationError(CurationFailure.INVALID_OUTPUT) from error

        parsed = message.parsed_output
        if message.stop_reason == "refusal":
            _log_rejected(message)
            raise CurationError(CurationFailure.REFUSED)
        if message.stop_reason == "max_tokens" or parsed is None:
            _log_rejected(message)
            raise CurationError(CurationFailure.INVALID_OUTPUT)
        _log_served(message)
        return CurationDraft(tags=tuple(parsed.tags), summary=parsed.summary)


def _failure_for_status(status_code: int) -> CurationFailure:
    """Classify by status code: 529 `OverloadedError` does not subclass `InternalServerError`.

    A 408 has no SDK class of its own either. The SDK retries it as a request timeout, so it is a
    timeout here too, not a request the server rejects outright.
    """
    if status_code == HTTPStatus.REQUEST_TIMEOUT:
        return CurationFailure.TIMEOUT
    if status_code == HTTPStatus.TOO_MANY_REQUESTS:
        return CurationFailure.RATE_LIMITED
    if status_code >= HTTPStatus.INTERNAL_SERVER_ERROR:
        return CurationFailure.UNAVAILABLE
    return CurationFailure.MISCONFIGURED


def _fallback_ran(message: ParsedBetaMessage[_ClaudeCuration]) -> bool:
    return any(entry.type == "fallback_message" for entry in message.usage.iterations or ())


def _log_served(message: ParsedBetaMessage[_ClaudeCuration]) -> None:
    usage = message.usage
    logger.info(
        "Claude curation served by %s: fallback=%s input_tokens=%d cache_read_input_tokens=%d "
        "cache_creation_input_tokens=%d output_tokens=%d request_id=%s",
        message.model,
        _fallback_ran(message),
        usage.input_tokens,
        usage.cache_read_input_tokens or 0,
        usage.cache_creation_input_tokens or 0,
        usage.output_tokens,
        message._request_id,
    )


def _log_unparseable(response: AsyncAPIResponse[ParsedBetaMessage[_ClaudeCuration]]) -> None:
    """Record what the `ValidationError` cannot carry: the stop reason and the request id.

    A reply cut off at max_tokens and a refusal partway through fail to parse alike, and only the
    raw stop reason tells them apart.
    """
    logger.warning(
        "Claude curation response unparseable: stop_reason=%s request_id=%s",
        response.http_response.json().get("stop_reason"),
        response.request_id,
    )


def _log_rejected(message: ParsedBetaMessage[_ClaudeCuration]) -> None:
    """Record what the raised `CurationError` cannot carry: no SDK exception lies behind it."""
    logger.warning(
        "Claude curation response unusable: stop_reason=%s refusal_category=%s model=%s "
        "fallback=%s request_id=%s",
        message.stop_reason,
        message.stop_details.category if message.stop_details else None,
        message.model,
        _fallback_ran(message),
        message._request_id,
    )
