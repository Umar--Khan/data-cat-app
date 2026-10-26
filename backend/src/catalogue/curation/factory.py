from collections.abc import AsyncIterator
from contextlib import asynccontextmanager
from typing import Final

from anthropic import AsyncAnthropic, DefaultAsyncHttpxClient, Timeout

from catalogue.core.config import Settings
from catalogue.curation.anthropic_provider import AnthropicCurationProvider
from catalogue.curation.base import CurationProvider
from catalogue.curation.keyword_provider import KeywordCurationProvider
from catalogue.domain.models import CurationProviderName

_CONNECT_TIMEOUT_SECONDS: Final = 5


def select_provider_name(settings: Settings) -> CurationProviderName:
    """Apply the provider selection rules in specs/curation.md.

    An explicit `anthropic` without a key never gets here: Settings validation rejects it.
    """
    if settings.curation_provider == "auto":
        return "keyword" if settings.anthropic_api_key is None else "anthropic"
    return settings.curation_provider


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


@asynccontextmanager
async def open_curation_provider(settings: Settings) -> AsyncIterator[CurationProvider]:
    """The selected provider, kept open for as long as the app runs.

    The SDK client holds a connection pool, so it is closed when the context exits rather than
    left for the garbage collector.
    """
    if select_provider_name(settings) == "anthropic":
        async with build_client(settings) as client:
            yield AnthropicCurationProvider(
                client,
                model=settings.anthropic_model,
                timeout_seconds=settings.anthropic_timeout_seconds,
            )
    else:
        yield KeywordCurationProvider(delay_ms=settings.keyword_delay_ms)
