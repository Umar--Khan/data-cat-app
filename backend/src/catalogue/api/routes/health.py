from fastapi import APIRouter

from catalogue.api.deps import CurationProviderNameDep
from catalogue.api.schemas import Health

router = APIRouter()


@router.get("/health", summary="Report that the API is up and which curation provider is active")
async def get_health(curation_provider: CurationProviderNameDep) -> Health:
    return Health(status="ok", curation_provider=curation_provider)
