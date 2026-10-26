from catalogue.curation.base import CurationError, CurationFailure


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
