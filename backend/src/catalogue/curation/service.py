import logging

from catalogue.curation.base import CurationError, CurationFailure, CurationProvider
from catalogue.curation.normalise import normalise_summary, normalise_tags
from catalogue.domain.models import Curation, NewDataset

logger = logging.getLogger(__name__)


class CurationService:
    """The failure boundary between a curation provider and the record being saved.

    A curation can fail in more ways than any provider lists, and none of them may stop the
    record being stored, so `curate` returns a failed curation instead of raising.
    """

    def __init__(self, provider: CurationProvider) -> None:
        self._provider = provider

    async def curate(self, new: NewDataset) -> Curation:
        provider = self._provider.name
        try:
            draft = await self._provider.curate(new)
            tags = normalise_tags(draft.tags)
            summary = normalise_summary(draft.summary)
        except CurationError as error:
            # The cause holds the SDK's message, status code and request id: worth logging, and
            # never shown to users.
            cause = "" if error.__cause__ is None else f": {error.__cause__!r}"
            logger.warning("Curation by %s failed as %s%s", provider, error.failure, cause)
            return Curation.failed(provider, error.failure.detail)
        # The one broad except that lets a request carry on; the API's unhandled-error middleware
        # catches everything too, but only to render the 500. SDK exception lists are not
        # exhaustive and a provider or the normaliser can have bugs, but neither may lose the
        # record. CancelledError is not an Exception, so a cancelled request still unwinds.
        except Exception:
            logger.exception("Curation by %s failed unexpectedly", provider)
            return Curation.failed(provider, CurationFailure.UNEXPECTED.detail)
        if not tags or not summary:
            logger.warning(
                "Curation by %s failed as %s: nothing usable left after normalising %r",
                provider,
                CurationFailure.INVALID_OUTPUT,
                draft,
            )
            return Curation.failed(provider, CurationFailure.INVALID_OUTPUT.detail)
        return Curation.completed(provider, tags, summary)
