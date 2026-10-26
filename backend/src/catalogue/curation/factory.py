from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from catalogue.core.config import Settings
from catalogue.curation.anthropic_provider import AnthropicCurationProvider, build_client
from catalogue.curation.base import CurationProvider
from catalogue.curation.keyword_provider import KeywordCurationProvider
from catalogue.domain.models import CurationProviderName


def select_provider_name(settings: Settings) -> CurationProviderName:
    """Apply the provider selection rules in specs/curation.md.

    An explicit `anthropic` without a key never gets here: Settings validation rejects it.
    """
    if settings.curation_provider == "auto":
        return "keyword" if settings.anthropic_api_key is None else "anthropic"
    return settings.curation_provider


@asynccontextmanager
async def open_curation_provider(settings: Settings) -> AsyncIterator[CurationProvider]:
    """The selected provider, kept open for as long as the app runs.

    The SDK client holds a connection pool, so it is closed when the context exits rather than
    left for the garbage collector.
    """
    if select_provider_name(settings) == "anthropic":
        async with build_client(settings) as client:
            yield AnthropicCurationProvider(client, settings)
    else:
        yield KeywordCurationProvider(delay_ms=settings.keyword_delay_ms)
