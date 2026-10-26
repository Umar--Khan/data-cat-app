from datetime import UTC, datetime

import pytest

from catalogue.domain.models import (
    MAX_DESCRIPTION_LENGTH,
    MAX_NAME_LENGTH,
    MAX_OWNER_LENGTH,
    Curation,
    Dataset,
    NewDataset,
)

VALID = {"name": "Trade Confirmations", "owner": "Middle Office", "description": "Daily trades."}
LIMITS = {
    "name": MAX_NAME_LENGTH,
    "owner": MAX_OWNER_LENGTH,
    "description": MAX_DESCRIPTION_LENGTH,
}


def test_the_field_limits_are_the_api_contracts() -> None:
    assert LIMITS == {"name": 120, "owner": 120, "description": 2000}


@pytest.mark.parametrize("field", LIMITS)
def test_a_new_dataset_accepts_each_field_at_its_limit_in_code_points(field: str) -> None:
    value = "\N{MATHEMATICAL DOUBLE-STRUCK CAPITAL A}" * LIMITS[field]

    assert getattr(NewDataset(**{**VALID, field: value}), field) == value


@pytest.mark.parametrize("field", LIMITS)
def test_a_new_dataset_rejects_a_field_over_its_limit(field: str) -> None:
    limit = LIMITS[field]

    with pytest.raises(ValueError, match=f"^{field} must be 1 to {limit} characters, not "):
        NewDataset(**{**VALID, field: "x" * (limit + 1)})


@pytest.mark.parametrize("field", LIMITS)
def test_a_new_dataset_rejects_an_empty_field(field: str) -> None:
    with pytest.raises(ValueError, match=f"^{field} must be 1 to "):
        NewDataset(**{**VALID, field: ""})


def test_a_completed_curation_has_tags_a_summary_and_no_detail() -> None:
    assert Curation.completed("keyword", ("finance", "daily"), "A daily feed.") == Curation(
        status="completed",
        provider="keyword",
        tags=("finance", "daily"),
        summary="A daily feed.",
        detail=None,
    )


def test_a_failed_curation_has_no_tags_or_summary_only_the_detail() -> None:
    assert Curation.failed("anthropic", "AI curation timed out.") == Curation(
        status="failed",
        provider="anthropic",
        tags=(),
        summary=None,
        detail="AI curation timed out.",
    )


def test_a_datasets_tags_and_summary_are_its_curations() -> None:
    curation = Curation.completed("seed", ("finance",), "A daily feed.")
    dataset = Dataset(
        id="1",
        created_at=datetime(2026, 10, 25, tzinfo=UTC),
        curation=curation,
        **VALID,
    )

    assert (dataset.tags, dataset.summary) == (("finance",), "A daily feed.")
