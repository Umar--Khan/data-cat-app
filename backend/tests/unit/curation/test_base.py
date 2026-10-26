from catalogue.curation.base import CurationDraft, CurationError, CurationFailure, CurationResult


def test_each_failure_carries_the_detail_from_the_failures_table() -> None:
    assert {failure.value: failure.detail for failure in CurationFailure} == {
        "timeout": "AI curation timed out.",
        "rate_limited": "The AI service is handling too many requests.",
        "unavailable": "The AI service could not be reached.",
        "misconfigured": "AI curation is not configured correctly on the server.",
        "refused": "The AI model declined to curate this description.",
        "invalid_output": "The AI response could not be used.",
        "unexpected": "AI curation failed unexpectedly.",
    }


def test_curation_error_carries_its_failure() -> None:
    error = CurationError(CurationFailure.RATE_LIMITED)

    assert error.failure is CurationFailure.RATE_LIMITED
    assert str(error) == "rate_limited"


def test_a_failed_result_has_no_tags_or_summary_and_the_failure_detail() -> None:
    result = CurationResult.failed("anthropic", CurationFailure.TIMEOUT)

    assert result == CurationResult(
        status="failed",
        provider="anthropic",
        tags=(),
        summary=None,
        detail="AI curation timed out.",
    )


def test_a_completed_result_has_no_detail() -> None:
    result = CurationResult.completed("keyword", ("finance", "daily"), "A daily feed.")

    assert result == CurationResult(
        status="completed",
        provider="keyword",
        tags=("finance", "daily"),
        summary="A daily feed.",
        detail=None,
    )


def test_draft_schema_describes_each_field_and_sets_no_length_limits() -> None:
    schema = CurationDraft.model_json_schema()
    tags, summary = schema["properties"]["tags"], schema["properties"]["summary"]

    assert schema["required"] == ["tags", "summary"]
    assert schema["description"]
    assert tags["description"]
    assert summary["description"]
    assert tags["items"] == {"type": "string"}
    assert not {"minItems", "maxItems"} & tags.keys()
    assert not {"minLength", "maxLength"} & summary.keys()


def test_draft_accepts_output_beyond_the_limits_so_the_normaliser_can_trim_it() -> None:
    raw = {"tags": [f"tag-{number}" for number in range(9)], "summary": "A long one. " * 40}

    draft = CurationDraft.model_validate(raw)

    assert len(draft.tags) == 9
    assert draft.summary == raw["summary"]
