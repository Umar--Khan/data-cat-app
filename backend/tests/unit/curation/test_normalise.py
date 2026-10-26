import pytest

from catalogue.curation.normalise import normalise_summary, normalise_tags

LONG_WORDS = " ".join(["abcdefghi"] * 30)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("  finance\t", "finance", id="surrounding-whitespace"),
        pytest.param("#finance", "finance", id="hash"),
        pytest.param('"finance"', "finance", id="double-quotes"),
        pytest.param("'finance'", "finance", id="single-quotes"),
        pytest.param(' # "finance" ', "finance", id="mixed-wrapping"),
        pytest.param("real time", "real-time", id="space-to-hyphen"),
        pytest.param("supply \t\n chain", "supply-chain", id="whitespace-run-to-one-hyphen"),
    ],
)
def test_rule_1_strips_wrapping_and_hyphenates_internal_whitespace(raw: str, expected: str) -> None:
    assert normalise_tags([raw]) == (expected,)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        *(
            pytest.param(raw, canonical, id=f"acronym-{canonical}")
            for raw, canonical in [
                ("pii", "PII"),
                ("Hr", "HR"),
                ("fx", "FX"),
                ("Sku", "SKU"),
                ("kyc", "KYC"),
                ("aml", "AML"),
                ("crm", "CRM"),
                ("Esg", "ESG"),
                ("p&l", "P&L"),
            ]
        ),
        pytest.param("GDPR", "GDPR", id="other-caps-of-four-kept"),
        pytest.param("SWIFT", "SWIFT", id="other-caps-of-five-kept"),
        pytest.param("IT", "IT", id="other-caps-of-two-kept"),
        pytest.param("B2B", "B2B", id="caps-with-digit-kept"),
        pytest.param("TRADES", "trades", id="caps-of-six-lowered"),
        pytest.param("A", "a", id="single-capital-lowered"),
        pytest.param("Finance", "finance", id="title-case-lowered"),
        pytest.param("Customer-PII", "customer-PII", id="decided-per-hyphenated-token"),
        pytest.param("FX Rates", "FX-rates", id="after-hyphenation"),
    ],
)
def test_rule_2_cases_acronyms_and_lowercases_the_rest(raw: str, expected: str) -> None:
    assert normalise_tags([raw]) == (expected,)


@pytest.mark.parametrize(
    "raw",
    [
        pytest.param("", id="empty"),
        pytest.param("  #' ", id="empty-after-stripping"),
        pytest.param("a" * 33, id="longer-than-32"),
        pytest.param("data", id="generic-data"),
        pytest.param("Dataset", id="generic-dataset"),
        pytest.param("DATA", id="generic-in-capitals"),
        pytest.param("datasets", id="generic-datasets"),
        pytest.param("table", id="generic-table"),
        pytest.param("misc", id="generic-misc"),
        pytest.param("order_book", id="underscore"),
        pytest.param("café", id="non-ascii"),
        pytest.param("trading!", id="punctuation"),
        pytest.param("-finance", id="leading-hyphen"),
        pytest.param("p&l-statements", id="ampersand-outside-the-acronym"),
    ],
)
def test_rule_3_drops_unusable_tags(raw: str) -> None:
    assert normalise_tags([raw, "finance"]) == ("finance",)


def test_rule_3_keeps_a_tag_of_exactly_32_characters() -> None:
    assert normalise_tags(["a" * 32]) == ("a" * 32,)


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(["finance", "Finance", "FINANCE"], ("finance",), id="case-insensitive"),
        pytest.param(["PII", "pii"], ("PII",), id="acronym-twice"),
        pytest.param(["real time", "Real-Time"], ("real-time",), id="equal-after-rules-1-and-2"),
        pytest.param(["b", "a", "B"], ("b", "a"), id="first-occurrence-keeps-its-place"),
    ],
)
def test_rule_4_deduplicates_keeping_the_first(raw: list[str], expected: tuple[str, ...]) -> None:
    assert normalise_tags(raw) == expected


def test_rule_4_caps_at_six_after_dropping() -> None:
    raw = ["data", "one", "two", "one", "three", "four", "five", "six", "seven"]

    assert normalise_tags(raw) == ("one", "two", "three", "four", "five", "six")


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("  A   daily\n feed. ", "A daily feed.", id="whitespace"),
        pytest.param('"A daily feed."', "A daily feed.", id="double-quotes"),
        pytest.param("'A daily feed.'", "A daily feed.", id="single-quotes"),
        pytest.param("\u201cA daily feed.\u201d", "A daily feed.", id="curly-double-quotes"),
        pytest.param("\u2018A daily feed.\u2019", "A daily feed.", id="curly-single-quotes"),
        pytest.param("\"' A daily feed. '\"", "A daily feed.", id="nested-quotes"),
        pytest.param('"A daily" feed.', '"A daily" feed.', id="quotes-that-do-not-wrap"),
        pytest.param("A dai\u200bly fe\u00aded.", "A daily feed.", id="format-characters"),
        pytest.param("\u202eA daily feed.\u202c", "A daily feed.", id="bidi-controls"),
        pytest.param("A \x1b[31mdaily\x07 feed.", "A [31mdaily feed.", id="control-characters"),
        pytest.param("A daily\x85feed.\x1f", "A daily feed.", id="whitespace-controls"),
        pytest.param('\ufeff"A daily feed."', "A daily feed.", id="before-wrapping-quotes"),
    ],
)
def test_summary_rule_1_drops_hidden_characters_collapses_whitespace_and_strips_quotes(
    raw: str, expected: str
) -> None:
    assert normalise_summary(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("A daily feed. Updated weekly.", "A daily feed.", id="full-stop"),
        pytest.param("A daily feed! Updated weekly.", "A daily feed!", id="exclamation-mark"),
        pytest.param("A daily feed? Updated weekly.", "A daily feed?", id="question-mark"),
        pytest.param('A "daily feed." Updated weekly.', 'A "daily feed."', id="closing-quote"),
        pytest.param(
            "A feed of e.g. trades and positions. More.",
            "A feed of e.g. trades and positions.",
            id="e.g.",
        ),
        pytest.param(
            "Rates for approx. 40 currencies. More.",
            "Rates for approx. 40 currencies.",
            id="approx",
        ),
        pytest.param("U.S. Treasury yields. More.", "U.S. Treasury yields.", id="initialism"),
        pytest.param(
            "A feed of 3.5 million rows. More.", "A feed of 3.5 million rows.", id="decimal"
        ),
        pytest.param(
            "Rows from example.com daily. More.", "Rows from example.com daily.", id="domain"
        ),
        pytest.param(
            "Covers trades, positions, etc. Updated daily.",
            "Covers trades, positions, etc.",
            id="etc-ends-the-sentence",
        ),
    ],
)
def test_summary_rule_2_keeps_the_first_sentence(raw: str, expected: str) -> None:
    assert normalise_summary(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param(
            f"A {LONG_WORDS}", "A " + " ".join(["abcdefghi"] * 23) + "…", id="cut-inside-a-word"
        ),
        pytest.param(f"A {'x' * 237} tail words", f"A {'x' * 237}…", id="cut-where-a-word-ends"),
        pytest.param(f"A{'x' * 300}", f"A{'x' * 238}…", id="no-word-boundary"),
        pytest.param(
            "A " + ", ".join(["abcdefghi"] * 30),
            "A " + ", ".join(["abcdefghi"] * 21) + "…",
            id="no-comma-before-the-ellipsis",
        ),
        pytest.param(f"A {'x' * 237}.", f"A {'x' * 237}.", id="exactly-240-kept"),
    ],
)
def test_summary_rule_3_cuts_a_long_sentence_at_a_word_boundary(raw: str, expected: str) -> None:
    summary = normalise_summary(raw)

    assert summary == expected
    assert len(summary) <= 240


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("A daily feed", "A daily feed.", id="adds-a-full-stop"),
        pytest.param("A daily feed,", "A daily feed.", id="replaces-a-comma"),
        pytest.param("A daily feed:", "A daily feed.", id="replaces-a-colon"),
        pytest.param("A daily feed \u2014", "A daily feed.", id="replaces-a-dash"),
        pytest.param("A daily feed!", "A daily feed!", id="keeps-an-exclamation-mark"),
        pytest.param("A daily feed…", "A daily feed…", id="keeps-an-ellipsis"),
        pytest.param('A "daily feed."', 'A "daily feed."', id="keeps-a-stop-inside-quotes"),
    ],
)
def test_summary_rule_3_ends_a_short_sentence_with_punctuation(raw: str, expected: str) -> None:
    assert normalise_summary(raw) == expected


@pytest.mark.parametrize(
    ("raw", "expected"),
    [
        pytest.param("a daily feed.", "A daily feed.", id="article"),
        pytest.param('"an export of trades"', "An export of trades.", id="after-the-other-rules"),
    ],
)
def test_summary_rule_4_capitalises_the_first_character(raw: str, expected: str) -> None:
    assert normalise_summary(raw) == expected


@pytest.mark.parametrize("raw", ["", "   ", '""', "...", "\u2014", "''."])
def test_summary_without_a_letter_or_digit_is_empty(raw: str) -> None:
    assert normalise_summary(raw) == ""
