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
    DefaultAsyncHttpxClient,
    Timeout,
    omit,
)
from anthropic.types.beta import BetaTextBlockParam
from anthropic.types.beta.parsed_beta_message import ParsedBetaMessage
from pydantic import ValidationError

from catalogue.core.config import Settings
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
_CONNECT_TIMEOUT_SECONDS: Final = 5
_FALLBACK_BETA: Final = "server-side-fallback-2026-07-01"
_SYSTEM: Final[tuple[BetaTextBlockParam, ...]] = (
    {"type": "text", "text": SYSTEM_PROMPT, "cache_control": {"type": "ephemeral"}},
)


def build_client(
    settings: Settings, *, http_client: DefaultAsyncHttpxClient | None = None
) -> AsyncAnthropic:
    """The SDK client, configured the same way in production and in tests.

    The key, host and workspace always come from Settings. Passing them explicitly stops the SDK's
    own discovery (`ANTHROPIC_AUTH_TOKEN`, `ant auth login` profiles) from choosing any of them.
    The client timeout and single retry only bound each attempt; the provider's `asyncio.timeout`
    is the real deadline, because the SDK waits out any `retry-after` the API sends, however long.
    """
    if settings.anthropic_api_key is None:
        raise ValueError("The Anthropic client needs ANTHROPIC_API_KEY")
    workspace = settings.anthropic_workspace_id
    return AsyncAnthropic(
        api_key=settings.anthropic_api_key.get_secret_value(),
        base_url=settings.anthropic_base_url,
        timeout=Timeout(settings.anthropic_timeout_seconds, connect=_CONNECT_TIMEOUT_SECONDS),
        max_retries=1,
        default_headers=None if workspace is None else {"anthropic-workspace-id": workspace},
        http_client=http_client,
    )


class AnthropicCurationProvider:
    """Curates with Claude through structured outputs.

    The caller owns the client and closes it. Each failure the Failures table in specs/curation.md
    names is raised as a `CurationError` from the SDK's exception, so the log keeps the SDK's
    details while users see only the failure's sentence.
    """

    name: Final[CurationProviderName] = "anthropic"

    def __init__(self, client: AsyncAnthropic, settings: Settings) -> None:
        self.model: Final = settings.anthropic_model
        self._client = client
        self._budget = settings.anthropic_timeout_seconds
        self._fallback = settings.anthropic_model in FALLBACK_MODELS

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
                    output_format=CurationDraft,
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

        draft = message.parsed_output
        if message.stop_reason == "refusal":
            _log_rejected(message)
            raise CurationError(CurationFailure.REFUSED)
        if message.stop_reason == "max_tokens" or draft is None:
            _log_rejected(message)
            raise CurationError(CurationFailure.INVALID_OUTPUT)
        _log_served(message)
        return draft


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


def _fallback_ran(message: ParsedBetaMessage[CurationDraft]) -> bool:
    return any(entry.type == "fallback_message" for entry in message.usage.iterations or ())


def _log_served(message: ParsedBetaMessage[CurationDraft]) -> None:
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


def _log_unparseable(response: AsyncAPIResponse[ParsedBetaMessage[CurationDraft]]) -> None:
    """Record what the `ValidationError` cannot carry: the stop reason and the request id.

    A reply cut off at max_tokens and a refusal partway through fail to parse alike, and only the
    raw stop reason tells them apart.
    """
    logger.warning(
        "Claude curation response unparseable: stop_reason=%s request_id=%s",
        response.http_response.json().get("stop_reason"),
        response.request_id,
    )


def _log_rejected(message: ParsedBetaMessage[CurationDraft]) -> None:
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
