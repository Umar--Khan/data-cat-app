import re
from collections.abc import Iterable, Mapping
from typing import Final

MAX_TAGS: Final = 6
MAX_TAG_LENGTH: Final = 32
MAX_SUMMARY_LENGTH: Final = 240

CANONICAL_ACRONYMS: Final[Mapping[str, str]] = {
    acronym.casefold(): acronym
    for acronym in ("PII", "HR", "FX", "SKU", "KYC", "AML", "CRM", "ESG", "P&L")
}
GENERIC_TAGS: Final = frozenset({"data", "dataset", "datasets", "table", "misc"})
TAG_PATTERN: Final = re.compile(r"[A-Za-z0-9]+(?:-[A-Za-z0-9]+)*")

_CANONICAL = frozenset(CANONICAL_ACRONYMS.values())
_KEPT_CAPS_LENGTHS = range(2, 6)
_TAG_WRAPPING = re.compile(r"^[\s#\"']+|[\s#\"']+$")
_WHITESPACE = re.compile(r"\s+")
# Straight quotes, then curly double and single quotes.
_QUOTE_PAIRS: Final[Mapping[str, str]] = {
    '"': '"',
    "'": "'",
    "\u201c": "\u201d",
    "\u2018": "\u2019",
}
_OPENERS = r"[(\[\"'\u201c\u2018]*"
_CLOSERS = r"[\"'\u201d\u2019)\]]*"
_SENTENCE_END = re.compile(rf"[.!?]+{_CLOSERS}(?=\s)")
# A full stop after one of these rarely ends a sentence, so "e.g. trades" or "approx. 40
# currencies" stays in one piece. "etc." is left out because it usually closes a list that ends
# the sentence.
_ABBREVIATION = re.compile(
    rf"{_OPENERS}(?:(?:[a-z]\.){{2,}}|(?:approx|incl|excl|vs|cf|nos?|mrs?|ms|dr|st)\.){_CLOSERS}",
    re.IGNORECASE,
)
_TERMINAL_PUNCTUATION = re.compile(rf"[.!?…]{_CLOSERS}$")
# Stripped before the closing full stop or ellipsis, so a sentence never ends in ",." or ":…".
# The last two are an en dash and an em dash.
_DANGLING_PUNCTUATION = " ,;:-\u2013\u2014"


def canonical_case(token: str) -> str:
    """Case one word as a tag would have it.

    The keyword provider cases dataset names with it too, so an acronym reads the same in a
    summary as in the tags beside it.
    """
    if (acronym := CANONICAL_ACRONYMS.get(token.casefold())) is not None:
        return acronym
    if token.isupper() and len(token) in _KEPT_CAPS_LENGTHS:
        return token
    return token.lower()


def normalise_tags(raw: Iterable[str]) -> tuple[str, ...]:
    """Apply the tag rules in specs/curation.md, in their numbered order.

    Case is decided per hyphen-separated token, so "Customer-PII" keeps its acronym as
    "customer-PII" instead of losing it to "customer-pii".
    """
    tags: list[str] = []
    seen: set[str] = set()
    for value in raw:
        stripped = _WHITESPACE.sub("-", _TAG_WRAPPING.sub("", value))
        tag = "-".join(canonical_case(token) for token in stripped.split("-"))
        key = tag.casefold()
        usable = (
            0 < len(tag) <= MAX_TAG_LENGTH
            and key not in GENERIC_TAGS
            and (tag in _CANONICAL or TAG_PATTERN.fullmatch(tag) is not None)
        )
        if usable and key not in seen:
            seen.add(key)
            tags.append(tag)
    return tuple(tags[:MAX_TAGS])


def first_sentence(text: str) -> str:
    """Cut `text` after its first sentence.

    A terminator counts only when whitespace follows it, so decimals, versions and domain names
    never end a sentence.
    """
    for end in _SENTENCE_END.finditer(text):
        word = text[: end.end()].rsplit(maxsplit=1)[-1]
        if _ABBREVIATION.fullmatch(word) is None:
            return text[: end.end()]
    return text


def normalise_summary(raw: str) -> str:
    """Apply the summary rules in specs/curation.md, in their numbered order.

    Returns an empty string when no letter or digit is left, so punctuation alone never passes
    for a summary.
    """
    summary = " ".join(raw.split())
    while summary and _QUOTE_PAIRS.get(summary[0]) == summary[-1]:
        summary = summary[1:-1].strip()
    summary = first_sentence(summary)
    if len(summary) > MAX_SUMMARY_LENGTH:
        # One character is kept back for the ellipsis, so no summary exceeds the limit.
        cut = summary[: MAX_SUMMARY_LENGTH - 1]
        if not summary[MAX_SUMMARY_LENGTH - 1].isspace():
            cut = cut.rpartition(" ")[0] or cut
        summary = cut.rstrip(_DANGLING_PUNCTUATION) + "…"
    elif summary and _TERMINAL_PUNCTUATION.search(summary) is None:
        summary = summary.rstrip(_DANGLING_PUNCTUATION) + "."
    summary = summary[:1].upper() + summary[1:]
    return summary if any(character.isalnum() for character in summary) else ""
