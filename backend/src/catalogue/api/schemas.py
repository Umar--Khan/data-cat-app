import unicodedata
from datetime import datetime
from typing import Final, Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator
from pydantic.alias_generators import to_camel
from pydantic_core import PydanticCustomError

from catalogue.domain.models import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_OWNER_LENGTH,
    CurationProviderName,
    CurationSource,
    CurationStatus,
)

# Controls (Cc) can drive a terminal or break a line the reader never sees, and format characters
# (Cf) are invisible or reorder the text around them, so two names can look the same while
# differing, or read differently from how they are stored.
_HIDDEN_CATEGORIES: Final = frozenset({"Cc", "Cf"})
# A description is free text from a textarea, so it may keep its tabs and line breaks.
_DESCRIPTION_CONTROLS: Final = frozenset("\t\n")
# Letters, numbers, punctuation and symbols. Whitespace, combining marks on their own and the C
# categories show nothing, so a value made only of them is blank.
_VISIBLE_GROUPS: Final = frozenset("LNPS")
_VISIBLE_TEXT: Final = (
    "At least one letter, digit, punctuation mark or symbol, and no control or invisible "
    "format characters."
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

    name: str = Field(min_length=1, max_length=MAX_NAME_LENGTH, description=_VISIBLE_TEXT)
    owner: str = Field(min_length=1, max_length=MAX_OWNER_LENGTH, description=_VISIBLE_TEXT)
    description: str = Field(
        min_length=1,
        max_length=MAX_DESCRIPTION_LENGTH,
        description=f"{_VISIBLE_TEXT} Tabs and line breaks are allowed.",
    )

    @field_validator("name", "owner")
    @classmethod
    def _single_line(cls, value: str) -> str:
        return _require_visible_text(value, allowed=frozenset())

    @field_validator("description")
    @classmethod
    def _free_text(cls, value: str) -> str:
        return _require_visible_text(value, allowed=_DESCRIPTION_CONTROLS)


def _require_visible_text(value: str, *, allowed: frozenset[str]) -> str:
    categories = [unicodedata.category(character) for character in value]
    if not any(category[0] in _VISIBLE_GROUPS for category in categories):
        raise PydanticCustomError("blank", "Value has no visible character")
    if any(
        category in _HIDDEN_CATEGORIES and character not in allowed
        for character, category in zip(value, categories, strict=True)
    ):
        raise PydanticCustomError("control_character", "Value has a control or format character")
    return value


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
