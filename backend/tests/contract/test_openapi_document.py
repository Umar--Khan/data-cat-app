from typing import Any

import pytest
from fastapi.testclient import TestClient

from catalogue.app import create_app
from catalogue.core.config import Settings

PROBLEM = {"application/problem+json": {"schema": {"$ref": "#/components/schemas/ProblemDetails"}}}


@pytest.fixture
def document(settings: Settings) -> dict[str, Any]:
    return create_app(settings).openapi()


def operations(document: dict[str, Any]) -> list[tuple[str, str, dict[str, Any]]]:
    return [
        (method.upper(), path, operation)
        for path, path_item in document["paths"].items()
        for method, operation in path_item.items()
    ]


def test_operation_ids_are_the_contract(document: dict[str, Any]) -> None:
    assert {
        (method, path): operation["operationId"] for method, path, operation in operations(document)
    } == {
        ("GET", "/datasets"): "listDatasets",
        ("POST", "/datasets"): "createDataset",
        ("DELETE", "/datasets/{id}"): "deleteDataset",
        ("GET", "/health"): "getHealth",
    }


def test_schema_names_are_the_contract(document: dict[str, Any]) -> None:
    assert sorted(document["components"]["schemas"]) == [
        "Curation",
        "CurationProviderName",
        "CurationSource",
        "CurationStatus",
        "Dataset",
        "DatasetCreate",
        "FieldError",
        "Health",
        "ProblemDetails",
    ]


@pytest.mark.parametrize(
    ("name", "values"),
    [
        ("CurationStatus", ["completed", "failed"]),
        ("CurationProviderName", ["anthropic", "keyword"]),
        ("CurationSource", ["anthropic", "keyword", "seed"]),
    ],
)
def test_enums_are_named_components(document: dict[str, Any], name: str, values: list[str]) -> None:
    assert document["components"]["schemas"][name] == {"enum": values, "type": "string"}


def test_the_path_parameter_is_id(document: dict[str, Any]) -> None:
    [parameter] = document["paths"]["/datasets/{id}"]["delete"]["parameters"]

    assert (parameter["name"], parameter["in"], parameter["required"]) == ("id", "path", True)


def test_create_takes_a_closed_object_with_trimmed_length_limits(document: dict[str, Any]) -> None:
    schema = document["components"]["schemas"]["DatasetCreate"]

    assert schema["additionalProperties"] is False
    assert schema["required"] == ["name", "owner", "description"]
    limits = {
        field: (rule["minLength"], rule["maxLength"])
        for field, rule in schema["properties"].items()
    }
    assert limits == {"name": (1, 120), "owner": (1, 120), "description": (1, 2000)}


def test_every_response_field_is_required(document: dict[str, Any]) -> None:
    for name in ("Dataset", "Curation", "Health", "ProblemDetails", "FieldError"):
        schema = document["components"]["schemas"][name]
        assert schema["required"] == list(schema["properties"]), name


@pytest.mark.parametrize(
    ("method", "path", "statuses"),
    [
        ("GET", "/datasets", ["200"]),
        ("POST", "/datasets", ["201", "400", "413", "429", "4XX"]),
        ("DELETE", "/datasets/{id}", ["200", "404", "4XX"]),
        ("GET", "/health", ["200"]),
    ],
)
def test_documented_statuses_have_no_422_and_no_default(
    document: dict[str, Any], method: str, path: str, statuses: list[str]
) -> None:
    assert list(document["paths"][path][method.lower()]["responses"]) == statuses


def test_error_bodies_are_documented_as_problem_json(document: dict[str, Any]) -> None:
    errors = [
        response["content"]
        for _, _, operation in operations(document)
        for status, response in operation["responses"].items()
        if not status.startswith("2")
    ]

    assert errors == [PROBLEM] * 6


def test_create_documents_the_location_header(document: dict[str, Any]) -> None:
    created = document["paths"]["/datasets"]["post"]["responses"]["201"]

    assert created["headers"]["Location"]["required"] is True


def test_create_documents_retry_after_on_a_429(document: dict[str, Any]) -> None:
    throttled = document["paths"]["/datasets"]["post"]["responses"]["429"]

    assert throttled["headers"]["Retry-After"]["required"] is True
    assert throttled["headers"]["Retry-After"]["schema"] == {"type": "integer"}


def test_the_served_document_stays_the_same_across_requests(settings: Settings) -> None:
    with TestClient(create_app(settings)) as client:
        first, second = (client.get("/openapi.json").json() for _ in range(2))

    assert first == second
    assert first["paths"]["/datasets"]["post"]["responses"]["400"]["content"] == PROBLEM
