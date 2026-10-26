from http import HTTPStatus
from typing import Annotated, TypedDict, cast

from fastapi import Depends, HTTPException, Request

from catalogue.api.limits import RateLimiter
from catalogue.domain.models import CurationProviderName
from catalogue.services.datasets import DatasetService


class LifespanState(TypedDict):
    datasets: DatasetService
    curation_provider_name: CurationProviderName
    create_rate_limiter: RateLimiter


def _lifespan_state(request: Request) -> LifespanState:
    # Starlette's Request[LifespanState] would type this without a cast, but FastAPI 0.162 does
    # not inject a parameterised Request. The runtime State object supports the same item access.
    return cast("LifespanState", request.state)


def get_datasets(request: Request) -> DatasetService:
    return _lifespan_state(request)["datasets"]


def get_curation_provider_name(request: Request) -> CurationProviderName:
    return _lifespan_state(request)["curation_provider_name"]


def limit_create_rate(request: Request) -> None:
    """Spend one of the client's create tokens, or refuse the request with a 429 problem.

    The client is the peer address uvicorn reports. Behind a proxy that is the proxy, unless
    uvicorn is told to trust its forwarding headers (specs/api-contract.md). A server on a Unix
    socket has no peer address, so all its clients share one bucket.
    """
    client = "" if request.client is None else request.client.host
    wait = _lifespan_state(request)["create_rate_limiter"].take(client)
    if wait:
        seconds = "1 second" if wait == 1 else f"{wait} seconds"
        raise HTTPException(
            HTTPStatus.TOO_MANY_REQUESTS,
            f"Too many datasets were added from this address. Try again in {seconds}.",
            headers={"Retry-After": str(wait)},
        )


DatasetServiceDep = Annotated[DatasetService, Depends(get_datasets)]
CurationProviderNameDep = Annotated[CurationProviderName, Depends(get_curation_provider_name)]
