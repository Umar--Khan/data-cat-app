from typing import Annotated

from fastapi import APIRouter, Path, Response, status

from catalogue.api.deps import DatasetServiceDep
from catalogue.api.openapi import problem
from catalogue.api.schemas import Dataset, DatasetCreate
from catalogue.domain.models import NewDataset

router = APIRouter(prefix="/datasets")


@router.get("", summary="List every dataset, oldest first")
async def list_datasets(datasets: DatasetServiceDep) -> list[Dataset]:
    return [Dataset.model_validate(dataset) for dataset in await datasets.list()]


@router.post(
    "",
    status_code=status.HTTP_201_CREATED,
    summary="Register a dataset, curate it and store it",
    responses={
        status.HTTP_201_CREATED: {
            "description": "Stored, whether or not curation succeeded. `curation` says which.",
            "headers": {
                "Location": {
                    "description": "The new dataset's path, as a relative reference",
                    "required": True,
                    "schema": {"type": "string"},
                }
            },
        },
        status.HTTP_400_BAD_REQUEST: problem("The body is malformed or has invalid fields"),
        "4XX": problem("Client error"),
    },
)
async def create_dataset(
    body: DatasetCreate, datasets: DatasetServiceDep, response: Response
) -> Dataset:
    dataset = await datasets.create(
        NewDataset(name=body.name, owner=body.owner, description=body.description)
    )
    response.headers["Location"] = f"/datasets/{dataset.id}"
    return Dataset.model_validate(dataset)


@router.delete(
    "/{id}",
    summary="Delete a dataset and return it",
    responses={
        status.HTTP_404_NOT_FOUND: problem("No dataset has this id"),
        "4XX": problem("Client error"),
    },
)
async def delete_dataset(
    dataset_id: Annotated[str, Path(alias="id")], datasets: DatasetServiceDep
) -> Dataset:
    return Dataset.model_validate(await datasets.delete(dataset_id))
