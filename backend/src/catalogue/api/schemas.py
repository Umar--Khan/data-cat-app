from typing import Literal

from pydantic import BaseModel, ConfigDict
from pydantic.alias_generators import to_camel

from catalogue.domain.models import CurationProviderName


class CamelModel(BaseModel):
    """Base for every wire model: snake_case in Python, camelCase in JSON and OpenAPI."""

    model_config = ConfigDict(
        alias_generator=to_camel,
        validate_by_name=True,
        validate_by_alias=True,
        serialize_by_alias=True,
        from_attributes=True,
    )


class Health(CamelModel):
    status: Literal["ok"]
    curation_provider: CurationProviderName
