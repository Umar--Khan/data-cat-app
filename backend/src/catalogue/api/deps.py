from typing import Annotated, TypedDict, cast

from fastapi import Depends, Request

from catalogue.domain.models import CurationProviderName


class LifespanState(TypedDict):
    curation_provider_name: CurationProviderName


def _lifespan_state(request: Request) -> LifespanState:
    # Starlette's Request[LifespanState] would type this without a cast, but FastAPI 0.162 does
    # not inject a parameterised Request. The runtime State object supports the same item access.
    return cast("LifespanState", request.state)


def get_curation_provider_name(request: Request) -> CurationProviderName:
    return _lifespan_state(request)["curation_provider_name"]


CurationProviderNameDep = Annotated[CurationProviderName, Depends(get_curation_provider_name)]
