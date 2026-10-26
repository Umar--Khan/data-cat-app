from concurrent.futures import ThreadPoolExecutor
from typing import Any

import pytest
from fastapi.testclient import TestClient

from catalogue.app import create_app
from catalogue.core.config import Settings
from catalogue.curation.base import CurationError, CurationFailure
from catalogue.domain.models import NewDataset
from tests.fakes import DRAFT, FakeCurationProvider, Gate, TickingClock

TEST_PAYLOAD = {
    "name": "Trade Confirmations",
    "owner": "Middle Office",
    "description": (
        "Daily export of confirmed trades including instrument type, counterparty, notional "
        "value, and settlement date."
    ),
}
STARTED_AT = "2026-10-25T09:30:00Z"


def payload(name: str) -> dict[str, str]:
    return {**TEST_PAYLOAD, "name": name}


def ids(client: TestClient) -> list[str]:
    return [dataset["id"] for dataset in client.get("/datasets").json()]


# The brief's API checklist, one test per item.


def test_get_datasets_returns_all_three_preloaded_entries_on_startup(client: TestClient) -> None:
    response = client.get("/datasets")

    assert response.status_code == 200
    datasets = response.json()
    assert [(dataset["id"], dataset["name"]) for dataset in datasets] == [
        ("1", "Customer Transactions"),
        ("2", "Product Inventory"),
        ("3", "Employee Directory"),
    ]
    assert all(
        dataset["curation"] == {"status": "completed", "provider": "seed", "detail": None}
        for dataset in datasets
    )
    assert {dataset["createdAt"] for dataset in datasets} == {STARTED_AT}


def test_post_datasets_with_the_test_payload_returns_201_with_tags_and_summary_populated(
    client: TestClient,
) -> None:
    response = client.post("/datasets", json=TEST_PAYLOAD)

    assert response.status_code == 201
    assert response.json() == {
        "id": "4",
        **TEST_PAYLOAD,
        "tags": list(DRAFT.tags),
        "summary": DRAFT.summary,
        "curation": {"status": "completed", "provider": "keyword", "detail": None},
        "createdAt": "2026-10-25T09:30:01Z",
    }
    assert client.get("/datasets").json()[-1] == response.json()


def test_delete_datasets_1_returns_200_and_the_entry_no_longer_appears_in_a_subsequent_get(
    client: TestClient,
) -> None:
    response = client.delete("/datasets/1")

    assert response.status_code == 200
    assert response.json()["id"] == "1"
    assert response.json()["name"] == "Customer Transactions"
    assert ids(client) == ["2", "3"]


@pytest.mark.parametrize("missing", ["name", "description"])
def test_post_datasets_with_a_missing_name_or_description_returns_400_with_an_error_message(
    client: TestClient, missing: str
) -> None:
    body = {field: value for field, value in TEST_PAYLOAD.items() if field != missing}

    response = client.post("/datasets", json=body)

    assert response.status_code == 400
    assert response.headers["content-type"] == "application/problem+json"
    assert response.json() == {
        "type": "/problems/validation-error",
        "title": "Invalid request body",
        "status": 400,
        "detail": f"The request body has an invalid field: {missing}.",
        "instance": "/datasets",
        "errors": [{"field": missing, "message": "This field is required."}],
    }
    assert ids(client) == ["1", "2", "3"]


# The rest of the behaviour contract in specs/api-contract.md.


def test_the_wire_shape_is_camel_case_with_every_field_present(client: TestClient) -> None:
    assert client.get("/datasets").json()[0] == {
        "id": "1",
        "name": "Customer Transactions",
        "owner": "Finance Team",
        "description": (
            "Contains daily transaction records including transaction ID, customer ID, amount, "
            "currency, and timestamp."
        ),
        "tags": ["finance", "transactions", "PII", "daily"],
        "summary": (
            "A daily feed of customer transaction records covering amounts, currencies, and "
            "timestamps."
        ),
        "curation": {"status": "completed", "provider": "seed", "detail": None},
        "createdAt": STARTED_AT,
    }


def test_location_is_a_relative_reference_that_only_delete_accepts(client: TestClient) -> None:
    created = client.post("/datasets", json=TEST_PAYLOAD)

    location = created.headers["location"]
    assert location == "/datasets/4"
    followed = client.get(location)
    assert followed.status_code == 405
    assert followed.headers["allow"] == "DELETE"
    assert client.delete(location).json() == created.json()


def test_ids_continue_after_the_seeds_and_are_never_reused(client: TestClient) -> None:
    assert client.post("/datasets", json=payload("First")).json()["id"] == "4"
    assert client.delete("/datasets/4").status_code == 200
    assert client.delete("/datasets/3").status_code == 200

    assert client.post("/datasets", json=payload("Second")).json()["id"] == "5"
    assert ids(client) == ["1", "2", "5"]


def test_created_at_follows_list_order_when_two_posts_overlap(
    client: TestClient, curation_provider: FakeCurationProvider
) -> None:
    gate = Gate()
    curation_provider.gates["First"] = gate

    with ThreadPoolExecutor(max_workers=1) as pool:
        first = pool.submit(client.post, "/datasets", json=payload("First"))
        assert gate.reached.wait(Gate.TIMEOUT_SECONDS)
        second = client.post("/datasets", json=payload("Second"))
        gate.open()
        first_response = first.result(timeout=Gate.TIMEOUT_SECONDS)

    assert (second.json()["id"], first_response.json()["id"]) == ("4", "5")
    listed = client.get("/datasets").json()
    assert [(dataset["name"], dataset["createdAt"]) for dataset in listed[3:]] == [
        ("Second", "2026-10-25T09:30:01Z"),
        ("First", "2026-10-25T09:30:02Z"),
    ]


@pytest.mark.parametrize(
    ("raised", "detail"),
    [
        (CurationError(CurationFailure.UNAVAILABLE), "The AI service could not be reached."),
        (RuntimeError("provider bug"), "AI curation failed unexpectedly."),
    ],
)
def test_a_failed_curation_still_saves_the_dataset_and_returns_201(
    client: TestClient, curation_provider: FakeCurationProvider, raised: Exception, detail: str
) -> None:
    curation_provider.script.append(raised)

    response = client.post("/datasets", json=TEST_PAYLOAD)

    assert response.status_code == 201
    assert response.headers["location"] == "/datasets/4"
    dataset = response.json()
    assert (dataset["tags"], dataset["summary"]) == ([], None)
    assert dataset["curation"] == {"status": "failed", "provider": "keyword", "detail": detail}
    assert client.get("/datasets").json()[-1] == dataset


def test_surrounding_whitespace_is_trimmed_before_curating_and_storing(
    client: TestClient, curation_provider: FakeCurationProvider
) -> None:
    padded = {field: f" \t{value}\n " for field, value in TEST_PAYLOAD.items()}

    response = client.post("/datasets", json=padded)

    assert response.status_code == 201
    assert {field: response.json()[field] for field in TEST_PAYLOAD} == TEST_PAYLOAD
    assert curation_provider.received == [NewDataset(**TEST_PAYLOAD)]


@pytest.mark.parametrize(("field", "limit"), [("name", 120), ("owner", 120), ("description", 2000)])
@pytest.mark.parametrize("character", ["a", "\N{MATHEMATICAL DOUBLE-STRUCK CAPITAL A}"])
def test_lengths_are_counted_in_code_points_after_trimming(
    client: TestClient, field: str, limit: int, character: str
) -> None:
    at_limit = client.post("/datasets", json={**TEST_PAYLOAD, field: f"  {character * limit}  "})
    over_limit = client.post("/datasets", json={**TEST_PAYLOAD, field: character * (limit + 1)})

    assert at_limit.status_code == 201
    assert at_limit.json()[field] == character * limit
    assert over_limit.status_code == 400
    assert over_limit.json()["errors"] == [
        {"field": field, "message": f"This field must be at most {limit} characters."}
    ]


def test_restarting_restores_the_startup_state(settings: Settings) -> None:
    app = create_app(settings, curation_provider=FakeCurationProvider(), clock=TickingClock())

    with TestClient(app) as client:
        client.delete("/datasets/1")
        client.post("/datasets", json=TEST_PAYLOAD)
    with TestClient(app) as client:
        restarted: list[dict[str, Any]] = client.get("/datasets").json()
        recreated = client.post("/datasets", json=TEST_PAYLOAD).json()

    assert [dataset["id"] for dataset in restarted] == ["1", "2", "3"]
    assert {dataset["createdAt"] for dataset in restarted} == {"2026-10-25T09:30:02Z"}
    assert recreated["id"] == "4"
