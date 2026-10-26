import json
import logging
from collections.abc import Sequence
from typing import Any

import pytest
from fastapi.exceptions import RequestValidationError
from fastapi.testclient import TestClient
from starlette.exceptions import HTTPException
from starlette.requests import Request
from starlette.types import Message, Receive, Scope, Send

from catalogue.api.problems import UnhandledErrorMiddleware, exception_handlers
from catalogue.app import create_app
from catalogue.core.config import Settings
from catalogue.domain.models import Dataset
from catalogue.repositories.memory import InMemoryDatasetRepository
from tests.fakes import FakeCurationProvider

ORIGIN = "http://localhost:5173"
VALID = {"name": "Trade Confirmations", "owner": "Middle Office", "description": "Daily trades."}
MALFORMED = {
    "type": "/problems/malformed-body",
    "title": "Malformed request body",
    "status": 400,
    "detail": "The request body must be a JSON object sent as application/json.",
    "instance": "/datasets",
    "errors": [],
}


class BrokenRepository(InMemoryDatasetRepository):
    """Stands in for a bug below the API that no handler foresees."""

    async def list(self) -> Sequence[Dataset]:
        raise RuntimeError("the store's secret internals")


def test_invalid_fields_are_a_validation_problem_with_one_error_per_field(
    client: TestClient,
) -> None:
    response = client.post("/datasets", json={"owner": "Finance Team"})

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "/problems/validation-error",
        "title": "Invalid request body",
        "status": 400,
        "detail": "The request body has invalid fields: name, description.",
        "instance": "/datasets",
        "errors": [
            {"field": "name", "message": "This field is required."},
            {"field": "description", "message": "This field is required."},
        ],
    }


@pytest.mark.parametrize(
    ("change", "field", "message"),
    [
        pytest.param({"name": None}, "name", "This field is required.", id="missing"),
        pytest.param({"owner": ""}, "owner", "This field must not be blank.", id="empty"),
        pytest.param(
            {"owner": " \t\n "}, "owner", "This field must not be blank.", id="blank-after-trim"
        ),
        pytest.param(
            {"name": "x" * 121}, "name", "This field must be at most 120 characters.", id="too-long"
        ),
        pytest.param(
            {"description": "x" * 2001},
            "description",
            "This field must be at most 2000 characters.",
            id="description-too-long",
        ),
        pytest.param({"name": 42}, "name", "This field must be a string.", id="number"),
        pytest.param({"owner": ["Finance"]}, "owner", "This field must be a string.", id="array"),
        pytest.param({"tags": ["finance"]}, "tags", "This field is not allowed.", id="extra"),
        pytest.param({"id": "9"}, "id", "This field is not allowed.", id="client-id"),
    ],
)
def test_each_field_error_has_its_own_message(
    client: TestClient, change: dict[str, Any], field: str, message: str
) -> None:
    body = {key: value for key, value in {**VALID, **change}.items() if value is not None}

    response = client.post("/datasets", json=body)

    assert response.status_code == 400
    assert response.json()["type"] == "/problems/validation-error"
    assert response.json()["errors"] == [{"field": field, "message": message}]


def test_invisible_and_control_characters_are_field_errors(
    client: TestClient, curation_provider: FakeCurationProvider
) -> None:
    body = {"name": "\u200b\u200b", "owner": "\x00\x07", "description": "\u202eevil\x1b[31m"}

    response = client.post("/datasets", json=body)

    assert response.status_code == 400
    assert response.json()["errors"] == [
        {"field": "name", "message": "This field must not be blank."},
        {"field": "owner", "message": "This field must not be blank."},
        {
            "field": "description",
            "message": "This field must not contain control or invisible characters.",
        },
    ]
    assert curation_provider.received == []


@pytest.mark.parametrize(
    ("change", "field"),
    [
        pytest.param({"name": "\u200b"}, "name", id="zero-width-space"),
        pytest.param({"owner": "\ufeff"}, "owner", id="byte-order-mark"),
        pytest.param({"name": "\u0301\u0301"}, "name", id="combining-marks-alone"),
        pytest.param({"description": "\u2066\u2069"}, "description", id="bidi-isolates"),
        pytest.param({"description": "\u00a0\u200b\u3000"}, "description", id="spaces-and-format"),
    ],
)
def test_a_value_with_no_visible_character_is_blank(
    client: TestClient, change: dict[str, str], field: str
) -> None:
    response = client.post("/datasets", json={**VALID, **change})

    assert response.json()["errors"] == [
        {"field": field, "message": "This field must not be blank."}
    ]


@pytest.mark.parametrize(
    ("change", "field"),
    [
        pytest.param({"name": "Trade\u200bConfirmations"}, "name", id="zero-width-space"),
        pytest.param({"name": "Trade\u202eConfirmations"}, "name", id="bidi-override"),
        pytest.param({"owner": "\ufeffMiddle Office"}, "owner", id="byte-order-mark"),
        pytest.param({"owner": "Middle\x07Office"}, "owner", id="bell"),
        pytest.param({"name": "Trade\tConfirmations"}, "name", id="tab-in-name"),
        pytest.param({"owner": "Middle\nOffice"}, "owner", id="newline-in-owner"),
        pytest.param({"description": "Daily\rtrades."}, "description", id="carriage-return"),
        pytest.param({"description": "Daily\x1b[31m trades."}, "description", id="escape"),
        pytest.param({"description": "Daily\x85trades."}, "description", id="next-line"),
    ],
)
def test_a_control_or_format_character_is_rejected(
    client: TestClient, change: dict[str, str], field: str
) -> None:
    response = client.post("/datasets", json={**VALID, **change})

    assert response.json()["errors"] == [
        {"field": field, "message": "This field must not contain control or invisible characters."}
    ]


def test_the_description_keeps_its_tabs_and_line_breaks(client: TestClient) -> None:
    description = "Daily trades.\n\n\tUpdated nightly."

    response = client.post("/datasets", json={**VALID, "description": description})

    assert response.status_code == 201
    assert response.json()["description"] == description


def test_other_field_errors_keep_pydantics_message(client: TestClient) -> None:
    body = b'{"name": "\\ud800", "owner": "Middle Office", "description": "Daily trades."}'

    response = client.post("/datasets", content=body, headers={"Content-Type": "application/json"})

    [error] = response.json()["errors"]
    assert error == {
        "field": "name",
        "message": ("Input should be a valid string, unable to parse raw data as a unicode string"),
    }


def test_declared_fields_come_first_then_unknown_fields_as_sent(client: TestClient) -> None:
    response = client.post("/datasets", json={"tags": [], **VALID, "id": "9", "name": 1})

    assert response.json()["detail"] == "The request body has invalid fields: name, tags, id."
    assert [error["field"] for error in response.json()["errors"]] == ["name", "tags", "id"]


@pytest.mark.parametrize(
    ("content", "content_type"),
    [
        pytest.param(b'{"name": "Trade', "application/json", id="invalid-json"),
        pytest.param(b'["Trade Confirmations"]', "application/json", id="array"),
        pytest.param(b'"Trade Confirmations"', "application/json", id="string"),
        pytest.param(b"null", "application/json", id="null"),
        pytest.param(b"", "application/json", id="empty"),
        pytest.param(b'{"name": "Trade"}', "text/plain", id="non-json-content-type"),
        pytest.param(b'{"name": "Trade"}', None, id="no-content-type"),
        pytest.param(b'{"name": "Tr\xffde"}', "application/json", id="undecodable"),
    ],
)
def test_a_body_that_is_not_a_json_object_is_a_malformed_body_problem(
    client: TestClient, content: bytes, content_type: str | None
) -> None:
    headers = {} if content_type is None else {"Content-Type": content_type}

    response = client.post("/datasets", content=content, headers=headers)

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == MALFORMED


def test_an_unknown_dataset_id_is_a_dataset_not_found_problem(client: TestClient) -> None:
    response = client.delete("/datasets/99")

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "/problems/dataset-not-found",
        "title": "Dataset not found",
        "status": 404,
        "detail": 'No dataset has id "99". It may have been deleted already.',
        "instance": "/datasets/99",
        "errors": [],
    }


def test_deleting_twice_is_a_dataset_not_found_problem(client: TestClient) -> None:
    client.delete("/datasets/2")

    response = client.delete("/datasets/2")

    assert response.status_code == 404
    assert response.json()["type"] == "/problems/dataset-not-found"


@pytest.mark.parametrize(
    ("method", "path"),
    [
        pytest.param("GET", "/datasets/1/tags", id="deeper-path"),
        pytest.param("GET", "/datasets/", id="list-with-trailing-slash"),
        pytest.param("POST", "/datasets/", id="create-with-trailing-slash"),
        pytest.param("DELETE", "/datasets/1/", id="delete-with-trailing-slash"),
        pytest.param("GET", "/health/", id="health-with-trailing-slash"),
    ],
)
def test_an_unknown_route_is_a_not_found_problem(
    client: TestClient, method: str, path: str
) -> None:
    response = client.request(method, path, follow_redirects=False)

    assert response.status_code == 404
    assert response.headers["content-type"] == "application/problem+json"
    assert "location" not in response.headers
    assert response.json() == {
        "type": "about:blank",
        "title": "Not Found",
        "status": 404,
        "detail": f"No resource exists at {path}.",
        "instance": path,
        "errors": [],
    }


@pytest.mark.parametrize(
    ("method", "path", "instance", "detail"),
    [
        pytest.param(
            "DELETE",
            "/datasets/abc%20def",
            "/datasets/abc%20def",
            'No dataset has id "abc def". It may have been deleted already.',
            id="dataset-not-found",
        ),
        pytest.param(
            "GET",
            "/no%20such/caf%C3%A9",
            "/no%20such/caf%C3%A9",
            "No resource exists at /no such/café.",
            id="about-blank",
        ),
    ],
)
def test_instance_is_a_uri_reference_while_detail_reads_decoded(
    client: TestClient, method: str, path: str, instance: str, detail: str
) -> None:
    response = client.request(method, path)

    assert response.json()["instance"] == instance
    assert response.json()["detail"] == detail


@pytest.mark.parametrize(
    ("method", "path", "allow"),
    [
        ("GET", "/datasets/4", "DELETE"),
        ("PUT", "/datasets", "GET, POST"),
        ("DELETE", "/datasets", "GET, POST"),
        ("PATCH", "/datasets/1", "DELETE"),
        ("POST", "/health", "GET"),
    ],
)
def test_an_unsupported_method_is_a_405_problem_with_a_complete_allow_header(
    client: TestClient, method: str, path: str, allow: str
) -> None:
    response = client.request(method, path)

    assert response.status_code == 405
    assert response.headers["allow"] == allow
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "about:blank",
        "title": "Method Not Allowed",
        "status": 405,
        "detail": f"{path} does not support {method}. It supports {allow}.",
        "instance": path,
        "errors": [],
    }


def test_head_is_a_405_on_routes_that_answer_get(client: TestClient) -> None:
    # A known limitation, recorded in specs/api-contract.md: FastAPI does not add HEAD to GET
    # routes the way Starlette's own Route does.
    response = client.head("/datasets")

    assert response.status_code == 405
    assert response.headers["allow"] == "GET, POST"


def test_an_unhandled_exception_is_a_500_problem_with_cors_headers(
    settings: Settings, caplog: pytest.LogCaptureFixture
) -> None:
    app = create_app(
        settings, repository=BrokenRepository(), curation_provider=FakeCurationProvider()
    )

    with TestClient(app) as client:
        response = client.get("/datasets", headers={"Origin": ORIGIN})

    assert response.status_code == 500
    assert response.headers["content-type"] == "application/problem+json"
    assert response.headers["access-control-allow-origin"] == ORIGIN
    assert response.json() == {
        "type": "about:blank",
        "title": "Internal Server Error",
        "status": 500,
        "detail": "The server hit an unexpected error.",
        "instance": "/datasets",
        "errors": [],
    }
    [record] = [record for record in caplog.records if record.name == "catalogue.api.problems"]
    assert record.levelno == logging.ERROR
    assert record.getMessage() == "Unhandled error in GET /datasets"
    assert record.exc_info is not None
    assert "secret internals" not in response.text


@pytest.mark.parametrize(
    ("method", "path", "body"),
    [
        ("POST", "/datasets", {}),
        ("DELETE", "/datasets/99", None),
        ("GET", "/missing", None),
        ("PUT", "/datasets", None),
    ],
)
def test_problems_carry_cors_headers_for_a_configured_origin(
    client: TestClient, method: str, path: str, body: dict[str, str] | None
) -> None:
    response = client.request(method, path, json=body, headers={"Origin": ORIGIN})

    assert response.status_code >= 400
    assert response.headers["access-control-allow-origin"] == ORIGIN


@pytest.mark.anyio
async def test_an_http_error_without_a_dedicated_problem_keeps_its_status_and_detail() -> None:
    request = Request({"type": "http", "method": "GET", "path": "/datasets", "headers": []})
    handler = exception_handlers()[HTTPException]

    response = await handler(request, HTTPException(409, "Already exists", {"Retry-After": "1"}))

    assert response.status_code == 409
    assert response.headers["retry-after"] == "1"
    assert response.headers["content-type"] == "application/problem+json"
    assert response.body == (
        b'{"type":"about:blank","title":"Conflict","status":409,"detail":"Already exists",'
        b'"instance":"/datasets","errors":[]}'
    )


def plain_request() -> Request:
    return Request({"type": "http", "method": "POST", "path": "/datasets", "headers": []})


@pytest.mark.anyio
async def test_a_400_other_than_a_body_parse_failure_keeps_its_own_detail() -> None:
    handler = exception_handlers()[HTTPException]

    response = await handler(plain_request(), HTTPException(400, "The page token has expired."))

    assert json.loads(bytes(response.body)) == {
        "type": "about:blank",
        "title": "Bad Request",
        "status": 400,
        "detail": "The page token has expired.",
        "instance": "/datasets",
        "errors": [],
    }


@pytest.mark.anyio
async def test_a_nested_body_property_is_named_by_its_path() -> None:
    handler = exception_handlers()[RequestValidationError]
    error = RequestValidationError(
        [{"type": "string_type", "loc": ("body", "tags", 0), "msg": "Not a string", "input": 1}]
    )

    response = await handler(plain_request(), error)

    assert json.loads(bytes(response.body))["errors"] == [
        {"field": "tags.0", "message": "This field must be a string."}
    ]


@pytest.mark.anyio
async def test_an_invalid_parameter_outside_the_body_is_a_bad_request_without_field_errors() -> (
    None
):
    handler = exception_handlers()[RequestValidationError]
    error = RequestValidationError(
        [
            {"type": "int_parsing", "loc": ("query", "limit"), "msg": "Not a number", "input": "x"},
            {"type": "missing", "loc": ("body", "name"), "msg": "Field required", "input": {}},
        ]
    )

    response = await handler(plain_request(), error)

    assert response.status_code == 400
    assert json.loads(bytes(response.body)) == {
        "type": "about:blank",
        "title": "Bad Request",
        "status": 400,
        "detail": "The request has invalid parameters: query.limit, body.name.",
        "instance": "/datasets",
        "errors": [],
    }


@pytest.mark.anyio
async def test_an_error_after_the_response_started_is_left_to_the_server() -> None:
    sent: list[Message] = []

    async def streams_then_fails(_scope: Scope, _receive: Receive, send: Send) -> None:
        await send({"type": "http.response.start", "status": 200, "headers": []})
        raise RuntimeError("failed mid-stream")

    async def receive() -> Message:
        return {"type": "http.request", "body": b""}

    async def send(message: Message) -> None:
        sent.append(message)

    middleware = UnhandledErrorMiddleware(streams_then_fails)
    scope: Scope = {"type": "http", "method": "GET", "path": "/datasets", "headers": []}

    with pytest.raises(RuntimeError, match="failed mid-stream"):
        await middleware(scope, receive, send)
    assert sent == [{"type": "http.response.start", "status": 200, "headers": []}]
