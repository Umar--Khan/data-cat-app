from catalogue.core.config import Settings
from catalogue.domain.models import CurationProviderName


def select_provider_name(settings: Settings) -> CurationProviderName:
    """Apply the provider selection rules in specs/curation.md.

    An explicit `anthropic` without a key never gets here: Settings validation rejects it.
    """
    if settings.curation_provider == "auto":
        return "keyword" if settings.anthropic_api_key is None else "anthropic"
    return settings.curation_provider
