from datetime import datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field
from pydantic.alias_generators import to_camel

from catalogue.domain.models import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_OWNER_LENGTH,
    CurationProviderName,
    CurationSource,
    CurationStatus,
)


class CamelModel(BaseModel):
    """Base for every wire model: snake_case in Python, camelCase in JSON and OpenAPI."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        from_attributes=True,
    )


class DatasetCreate(CamelModel):
    """A dataset to register. Each field is trimmed before its length is checked."""

    # Forbidding extra fields tells a client that sends `tags` or `id` that the server sets them,
    # instead of silently dropping what it sent.
    model_config = ConfigDict(
        extra="forbid",
        str_strip_whitespace=True,
        json_schema_extra={
            "examples": [
                {
                    "name": "Trade Confirmations",
                    "owner": "Middle Office",
                    "description": (
                        "Daily export of confirmed trades including instrument type, "
                        "counterparty, notional value, and settlement date."
                    ),
                }
            ]
        },
    )

    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH)
    owner: str = Field(min_length=1, max_length=MAX_OWNER_LENGTH)
    description: str = Field(min_length=1, max_length=MAX_DESCRIPTION_LENGTH)


class Curation(CamelModel):
    status: CurationStatus
    provider: CurationSource = Field(
        description="Who produced the tags and summary. `seed` marks the hand-curated sample data."
    )
    detail: str | None = Field(
        description="Why curation failed, as a sentence safe to show users. Null unless failed."
    )


class Dataset(CamelModel):
    """A catalogue entry as stored."""

    id: str
    name: str
    owner: str
    description: str
    tags: list[str] = Field(
        max_length=6,
        description=(
            "Providers are asked for facet order: domain, subject, sensitivity, cadence. "
            "The seed records keep the brief's own order. Empty only when curation failed."
        ),
    )
    summary: str | None = Field(description="One sentence. Null only when curation failed.")
    curation: Curation
    created_at: datetime = Field(description="When the entry was stored, in UTC.")


class Health(CamelModel):
    status: Literal["ok"]
    curation_provider: CurationProviderName


class FieldError(CamelModel):
    field: str = Field(description="The request body property, as sent.")
    message: str


class ProblemDetails(CamelModel):
    """An RFC 9457 problem: the body of every error response."""

    type: str
    title: str
    status: int
    detail: str
    instance: str
    errors: list[FieldError] = Field(
        description="One entry per invalid field. Empty unless the request body failed validation."
    )
