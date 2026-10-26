from typing import Any

import pytest
import schemathesis
from schemathesis import Case
from schemathesis.checks import not_a_server_error
from schemathesis.specs.openapi.checks import (
    content_type_conformance,
    response_headers_conformance,
    response_schema_conformance,
    status_code_conformance,
)
from schemathesis.specs.openapi.schemas import OpenApiSchema

from catalogue.app import create_app
from catalogue.core.config import Settings


@pytest.fixture
def api_schema(settings: Settings) -> OpenApiSchema:
    """The real app with the keyword provider, built after the environment is isolated.

    Loading the schema in a fixture rather than at import time is what lets the autouse
    `isolated_environment` fixture run first.
    """
    return schemathesis.openapi.from_asgi("/openapi.json", create_app(settings))


schema = schemathesis.pytest.from_fixture("api_schema")


@schema.parametrize()
def test_every_operation_keeps_its_documented_contract(case: Case[Any]) -> None:
    case.call_and_validate(
        checks=[
            not_a_server_error,
            status_code_conformance,
            response_schema_conformance,
            content_type_conformance,
            response_headers_conformance,
        ]
    )
