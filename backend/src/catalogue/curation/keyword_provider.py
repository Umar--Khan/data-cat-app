import asyncio
import re
from collections.abc import Awaitable, Callable, Iterable, Mapping
from dataclasses import dataclass, field
from typing import Final, Literal

from catalogue.curation.base import CurationDraft
from catalogue.curation.normalise import canonical_case, first_sentence, normalise_tags
from catalogue.domain.models import CurationProviderName, NewDataset

type Facet = Literal["domain", "subject", "sensitivity", "cadence"]
type Sleep = Callable[[float], Awaitable[object]]


def _bounded(patterns: Iterable[str]) -> re.Pattern[str]:
    return re.compile(rf"\b(?:{'|'.join(patterns)})\b", re.IGNORECASE)


@dataclass(frozen=True, slots=True)
class TagRule:
    """One tag and the phrases that are evidence for it.

    Patterns are regular-expression fragments, matched case-insensitively on word boundaries. A
    short or ambiguous word appears only inside a phrase that pins its meaning, so "stock
    levels" counts for inventory and "stock prices" does not. A rule with `context` counts only
    when one of those phrases also appears in the dataset's name or description.
    """

    tag: str
    facet: Facet
    patterns: tuple[str, ...]
    context: tuple[str, ...] = ()
    regex: re.Pattern[str] = field(init=False, repr=False, compare=False)
    context_regex: re.Pattern[str] | None = field(init=False, repr=False, compare=False)

    def __post_init__(self) -> None:
        # Frozen, so the compiled patterns are set the way dataclasses set fields themselves.
        object.__setattr__(self, "regex", _bounded(self.patterns))
        object.__setattr__(self, "context_regex", _bounded(self.context) if self.context else None)


# Facet order, with each facet's cap.
FACET_CAPS: Final[Mapping[Facet, int]] = {"domain": 2, "subject": 2, "sensitivity": 1, "cadence": 1}

# People whose records identify them. Companies and counterparties are deliberately absent.
_PERSON = (
    r"(?:customers?|clients?|employees?|staff|patients?|users?|members?|students?|applicants?"
    r"|candidates?|contacts?|subscribers?|people|persons?|individuals?|residents?|passengers?"
    r"|guests?|donors?|borrowers?|policyholders?|drivers?|workers?|contractors?)"
)
_ID_HOLDER = r"(?:customer|client|employee|staff|patient|user|member|student|driver)"
# A word standing alone in a field list, as in "with name, email, and role".
_LISTED = (
    r"(?:(?<=, )|(?<=\bwith )|(?<=\band )|(?<=\bor )|(?<=\bincluding )|(?<=\bcontaining )"
    r"|(?<=\bcovering )|(?<=\())"
)
_LISTED_END = r"(?=\s*(?:[,;.)]|and\b|or\b|$))"
# Stock held for sale or use. An emissions inventory or an inventory of tables is not that.
_GOODS_INVENTORY = (
    r"(?<!emissions )(?<!carbon )inventor(?:y|ies)"
    r"(?! of (?:tables|datasets|data|systems|applications|models|reports))"
)


def _cadence_word(word: str) -> str:
    # "Daily active users" and "average daily volume" are measures, not how often data arrives,
    # and "bi-weekly" or "half-hourly" is a different cadence from the word it ends with.
    return (
        rf"(?<!average )(?<!-){word}(?!\s(?:active|average|volumes?|limits?|rates?|leave"
        r"|salar(?:y|ies)|income|revenue|turnover|spend|caps?|allowances?)\b)"
    )


# The taxonomy and the stopwords are tables, packed onto as few lines as fit. The formatter
# would put every pattern and word on a line of its own and triple their length.
# fmt: off
TAXONOMY: Final[tuple[TagRule, ...]] = (
    # Domain: the business area. Specific areas come first so they win ties with broad ones.
    TagRule("trading", "domain", (
        r"trades", r"trading", r"traders?", r"front office", r"order books?", r"executions?",
        r"trade (?:confirmations?|bookings?|captures?|blotters?|lifecycle|reporting)",
        r"equit(?:y|ies)", r"bonds", r"derivatives?", r"swaps", r"futures", r"securities",
        r"portfolios?", r"market data", r"tick data", r"blotters?", r"brokers?", r"markets",
        r"(?:stock|share|bond|equity) (?:prices?|quotes?)", r"stock (?:exchanges?|markets?)",
        r"(?:trading|open|portfolio|net|long|short) positions?",
    )),
    TagRule("risk", "domain", (
        r"risk", r"(?-i:VaR)", r"value at risk", r"exposures?", r"credit (?:limits?|ratings?)",
        r"stress tests?", r"collateral", r"margin calls?", r"probability of default",
    )),
    TagRule("compliance", "domain", (
        r"compliance", r"regulatory", r"regulators?", r"KYC", r"know your customer", r"AML",
        r"(?:anti-)?money laundering", r"sanctions", r"watchlists?", r"surveillance", r"GDPR",
        r"due diligence", r"financial crime", r"suspicious (?:activity|transactions?)",
        r"transaction monitoring",
    )),
    TagRule("lending", "domain", (
        r"lending", r"loans?", r"mortgages?", r"borrowers?", r"arrears", r"repayments?",
        r"credit (?:applications?|facilities|cards?)",
    )),
    TagRule("insurance", "domain", (
        r"insurance", r"insurers?", r"underwriting", r"actuarial", r"premiums",
        r"policyholders?", r"insurance claims?",
    )),
    TagRule("finance", "domain", (
        r"finance", r"financial (?:statements?|reporting|results|planning|controls?)",
        r"accounting", r"accountants?", r"ledgers?", r"journal entries", r"P&L",
        r"profit (?:and|&) loss", r"balance sheets?", r"revenue", r"budget(?:s|ing)?",
        r"(?:financial|revenue|cash|budget|cost) forecasts?", r"invoic(?:e|es|ing)", r"billing",
        r"treasury", r"tax(?:es|ation)?", r"expenses?", r"cost cent(?:re|er)s?", r"amounts?",
        r"currenc(?:y|ies)", r"middle office", r"back office", r"settlements?",
        r"accounts (?:payable|receivable)", r"payments?", r"cash ?flows?", r"interest rates?",
        r"banking", r"bank (?:accounts?|branches|statements?|transfers?)",
    )),
    TagRule("sales", "domain", (
        r"sales", r"selling", r"CRM", r"sales pipeline", r"opportunit(?:y|ies)", r"deals",
        r"(?:sales )?quotations?", r"sales leads?", r"account executives?", r"quotas?",
        r"resellers?", r"point[- ]of[- ]sale", r"retail (?:sales|stores?|analytics)",
        r"merchandising",
    )),
    TagRule("marketing", "domain", (
        r"marketing", r"campaigns?", r"advertising", r"ads", r"impressions", r"click-?through",
        r"CTR", r"newsletters?", r"SEO", r"SEM", r"social media", r"attribution",
        r"(?:sales|marketing|price|retail) promotions?", r"promotional",
        r"UTM", r"open rates?", r"leads", r"lead (?:generation|scor(?:e|es|ing))",
        r"(?:ad|campaign|funnel) conversions?",
    )),
    TagRule("customer-service", "domain", (
        r"customer (?:service|support|care|experience|success)", r"CX",
        r"support (?:tickets?|cases?|requests?|calls?|agents?)", r"help ?desk",
        r"(?:call|contact) cent(?:re|er)s?", r"complaints?", r"CSAT", r"NPS",
    )),
    TagRule("digital", "domain", (
        r"digital", r"web analytics", r"websites?", r"web ?site", r"mobile apps?", r"apps",
        r"clickstream", r"page ?views", r"e-?commerce", r"online (?:orders?|sales|store|banking)",
        r"product analytics",
    )),
    TagRule("HR", "domain", (
        r"(?-i:HR)", r"hr (?:team|department|dept|ops|operations)", r"human resources",
        r"people (?:team|operations|ops|analytics)", r"employees?", r"staff", r"workforce",
        r"headcount", r"payroll", r"recruit(?:ing|ment|ers?)", r"hiring", r"attrition",
        r"talent", r"(?:annual|sick|parental|personal) leave", r"leave (?:requests?|balances?)",
        r"absences?", r"absenteeism", r"employee (?:benefits|onboarding)", r"compensation",
        r"salar(?:y|ies)", r"performance reviews?", r"job (?:titles?|grades?|postings?)",
    )),
    TagRule("procurement", "domain", (
        r"procurement", r"purchasing", r"purchase orders?", r"suppliers?", r"vendors?",
        r"sourcing", r"(?:supplier|vendor|procurement) spend",
    )),
    TagRule("operations", "domain", (
        r"(?<!people )operations", r"ops", r"logistics", r"supply chain",
        r"(?<!data )warehous(?:e|es|ing)", _GOODS_INVENTORY,
        r"stock (?:levels?|on hand|counts?|movements?)", r"fulfil?ment", r"shipments?",
        r"deliver(?:y|ies)", r"freight", r"fleet", r"maintenance",
    )),
    TagRule("manufacturing", "domain", (
        r"manufacturing", r"factor(?:y|ies)", r"factory[- ]floor", r"shop[- ]floor",
        r"production (?:lines?|runs?|plants?)", r"assembly lines?", r"OEE",
    )),
    TagRule("healthcare", "domain", (
        r"health ?care", r"clinical", r"patients?", r"hospitals?", r"medical", r"wards?",
        r"diagnos(?:is|es|tic)", r"prescriptions?", r"medications?", r"clinics?",
    )),
    TagRule("ESG", "domain", (
        r"ESG", r"sustainability", r"emissions?", r"carbon", r"climate", r"greenhouse gas(?:es)?",
        r"GHG", r"energy (?:use|usage|consumption)", r"renewables?",
    )),
    TagRule("legal", "domain", (
        r"legal (?:matters?|team|holds?)", r"litigation", r"lawsuits?", r"counsel", r"NDAs?",
    )),
    TagRule("facilities", "domain", (
        r"facilities", r"real estate", r"office space", r"floor ?plans?", r"desk bookings?",
        r"occupancy", r"(?:property|office) leases?",
    )),
    TagRule("safety", "domain", (
        r"(?:workplace|occupational|work|health and) safety", r"WHS", r"OHS", r"hazards?",
        r"injur(?:y|ies)", r"safety incidents?",
    )),
    TagRule("security", "domain", (
        r"(?<!social )security", r"cyber ?security", r"authentication", r"logins?",
        r"vulnerabilit(?:y|ies)", r"threats?", r"firewalls?", r"phishing", r"SIEM",
        r"access logs?",
    )),
    TagRule("engineering", "domain", (
        r"engineering", r"infrastructure", r"servers?", r"deployments?", r"outages?", r"uptime",
        r"latency", r"APIs?", r"microservices?", r"cloud", r"kubernetes", r"observability",
        r"(?<!transaction )monitoring", r"SRE", r"devops",
        r"(?:IT|security|production|service|major) incidents?",
        r"data (?:platforms?|pipelines?|lakes?|warehouses?)", r"metadata", r"schemas?",
    )),
    TagRule("IT", "domain", (
        r"(?-i:IT)", r"information technology", r"service desk", r"laptops?",
        r"software licen[cs]es?", r"active directory", r"access requests?",
    )),

    # Subject: what each record describes.
    TagRule("transactions", "subject", (r"transactions?",)),
    TagRule("payments", "subject", (
        r"payments?", r"remittances?", r"direct debits?", r"wire transfers?",
    )),
    TagRule("settlements", "subject", (r"settlements?", r"settled trades?")),
    TagRule("positions", "subject", (r"(?:trading|open|portfolio|net|long|short) positions?",)),
    TagRule("prices", "subject", (
        r"prices", r"pricing", r"price (?:history|feeds?|points?|changes?)",
        r"(?:market|price|stock) quotes", r"(?:bid|ask|mid|closing|opening|spot|market) prices?",
    )),
    TagRule("FX", "subject", (r"FX", r"foreign exchange", r"currency pairs?", r"exchange rates?")),
    TagRule("rates", "subject", (
        r"interest rates?", r"yield curves?", r"(?:swap|benchmark|reference|base|cash) rates?",
    )),
    TagRule("exposures", "subject", (r"exposures?",)),
    TagRule("balances", "subject", (
        r"(?:account|cash|bank|deposit|loan|average daily) balances?",
    )),
    TagRule("P&L", "subject", (r"P&L", r"profit (?:and|&) loss", r"income statements?")),
    TagRule("ledger", "subject", (
        r"(?:general )?ledgers?", r"journal entries", r"journals", r"trial balances?",
    )),
    TagRule("invoices", "subject", (r"invoices?", r"invoicing", r"credit notes?")),
    TagRule("expenses", "subject", (r"expenses?", r"reimbursements?")),
    TagRule("claims", "subject", (r"claims",)),
    TagRule("budgets", "subject", (r"budgets?", r"budgeting")),
    TagRule("payroll", "subject", (
        r"payroll", r"pay ?runs?", r"payslips?", r"wages?", r"gross pay", r"net pay",
        r"superannuation", r"pension contributions?",
    )),
    TagRule("loans", "subject", (r"loans?", r"mortgages?")),
    TagRule("KYC", "subject", (
        r"KYC", r"know your customer", r"customer due diligence", r"identity verification",
    )),
    TagRule("AML", "subject", (
        r"AML", r"(?:anti-)?money laundering", r"suspicious (?:activity|transactions?)",
        r"transaction monitoring",
    )),
    TagRule("sanctions", "subject", (r"sanctions", r"watchlists?")),
    TagRule("customers", "subject", (
        r"customers", r"clients", r"subscribers",
        r"(?:customer|client) (?:master|profiles?|accounts?|base|segments?|segmentation"
        r"|demographics|details|records|lists?|churn|lifetime value)",
    )),
    TagRule("counterparties", "subject", (r"counterparties",)),
    TagRule("users", "subject", (r"users", r"user (?:accounts?|profiles?|base)")),
    TagRule("leads", "subject", (r"leads", r"sales leads?", r"lead (?:scores?|sources?)")),
    TagRule("campaigns", "subject", (r"campaigns?",)),
    TagRule("orders", "subject", (
        r"orders", r"(?:sales|purchase|customer|online|web) orders?",
        r"order (?:lines?|items?|history|status)",
    )),
    TagRule("products", "subject", (
        r"products",
        r"product (?:catalog(?:ue)?s?|master|hierarchy|range|listings?|details|attributes)",
    )),
    TagRule("inventory", "subject", (
        _GOODS_INVENTORY, r"stock-?outs?",
        r"stock (?:levels?|on hand|counts?|movements?|takes?)", r"(?:quantity|units) on hand",
        r"reorder (?:points?|levels?|thresholds?|quantit(?:y|ies))",
    )),
    TagRule("warehouse", "subject", (
        r"(?<!data )warehouses?", r"warehousing", r"distribution cent(?:re|er)s?",
        r"fulfil?ment cent(?:re|er)s?",
    )),
    TagRule("shipments", "subject", (
        r"shipments?", r"deliveries", r"consignments?", r"parcels?", r"freight",
    )),
    TagRule("vehicles", "subject", (r"vehicles?", r"vans", r"trucks")),
    TagRule("suppliers", "subject", (r"suppliers?", r"vendors?")),
    TagRule("contracts", "subject", (r"contracts?", r"agreements")),
    TagRule("employees", "subject", (
        r"employees?", r"staff", r"workforce", r"headcount", r"personnel",
    )),
    TagRule("candidates", "subject", (
        r"candidates?", r"applicants?", r"job applications?", r"requisitions?",
        r"vacanc(?:y|ies)",
    )),
    TagRule("leave", "subject", (
        r"(?:annual|sick|parental|personal) leave", r"leave (?:requests?|balances?|records?)",
        r"absences?",
    )),
    TagRule("tickets", "subject", (
        r"(?:support|service|help ?desk|IT|customer|incident) tickets?", r"tickets",
        r"support cases",
    )),
    TagRule("calls", "subject", (r"calls", r"call (?:volumes?|records?|recordings?)")),
    TagRule("complaints", "subject", (r"complaints?",)),
    TagRule("surveys", "subject", (r"surveys?", r"survey responses", r"NPS", r"CSAT")),
    TagRule("events", "subject", (
        r"(?:web|app|user|analytics|tracking|product|authentication|login|security) events",
        r"clickstream", r"page ?views", r"click events",
    )),
    TagRule("admissions", "subject", (
        r"admissions?", r"discharges?", r"inpatient stays?", r"length of stay",
    )),
    TagRule("patients", "subject", (r"patients?",)),
    TagRule("telemetry", "subject", (
        r"telemetry", r"telematics", r"sensor (?:readings?|data)", r"device readings?",
        r"meter readings?",
    )),
    TagRule("devices", "subject", (r"devices?", r"sensors?")),
    TagRule("incidents", "subject", (
        r"incidents", r"(?:IT|security|production|service|major|safety) incidents?", r"outages?",
    )),
    TagRule("logs", "subject", (
        r"(?:access|audit|application|server|system|event|web|error|call) logs?",
    )),
    TagRule("assets", "subject", (r"(?:IT|fixed|hardware) assets?", r"asset registers?")),
    TagRule("emissions", "subject", (
        r"emissions?", r"carbon footprint", r"CO2e?", r"greenhouse gas(?:es)?", r"GHG",
    )),
    TagRule("energy", "subject", (
        r"energy (?:use|usage|consumption)", r"electricity", r"kWh", r"gas usage",
    )),

    # Sensitivity, rule (a): a direct identifier is enough on its own.
    TagRule("PII", "sensitivity", (
        r"e-?mail address(?:es)?", rf"{_PERSON} e-?mails?", rf"{_LISTED}e-?mail{_LISTED_END}",
        r"(?:tele)?phone (?:numbers?|nos?)", r"mobile (?:numbers?|nos?)",
        r"contact (?:numbers?|details)", rf"{_PERSON} (?:tele)?phones?",
        rf"{_LISTED}(?:tele)?phone{_LISTED_END}",
        r"(?:home|postal|street|mailing|residential|billing|delivery|shipping|e-?mail|IP)"
        r" address(?:es)?",
        rf"{_PERSON} address(?:es)?", rf"{_LISTED}address(?:es)?{_LISTED_END}",
        r"dates? of birth", r"DOB", r"birth ?dates?",
        r"(?:government|national|tax|social security|national insurance|medicare)"
        r" (?:ids?|identifiers?|numbers?|nos?)",
        r"SSNs?", r"TFNs?", r"tax file numbers?", r"passports?",
        r"(?:driver'?s?|driving) licen[cs]es?", r"licen[cs]e numbers?",
        rf"{_ID_HOLDER} (?:ids?|identifiers?|numbers?|nos?)",
        r"PII", r"personally identifiable", r"personal (?:data|information|details)",
    )),
    # Rule (b): a name field identifies someone only when the records are about people, so
    # "product name" and "counterparty name" never count.
    TagRule("PII", "sensitivity", (
        rf"{_LISTED}names?{_LISTED_END}", rf"{_PERSON} names?", r"surnames?",
        r"(?:first|last|full|given|family|middle|maiden) names?",
    ), context=(_PERSON,)),

    # Cadence: how often the data arrives, only when the dataset says so. Ties go to the more
    # frequent cadence.
    TagRule("real-time", "cadence", (
        r"real[- ]time", r"streaming", r"streamed", r"live (?:feeds?|streams?|data)",
        r"every (?:\d+ )?seconds?",
    )),
    TagRule("hourly", "cadence", (
        _cadence_word("hourly"), r"every hour", r"each hour", r"once an hour",
    )),
    TagRule("daily", "cadence", (
        _cadence_word("daily"), r"nightly", r"end[- ]of[- ]day", r"EOD", r"once a day",
        r"(?:every|each) (?:day|night|morning|evening|business day|weekday)",
    )),
    TagRule("weekly", "cadence", (
        _cadence_word("weekly"), r"(?:every|each|once a) week",
        r"every (?:mon|tues|wednes|thurs|fri|satur|sun)day",
    )),
    TagRule("fortnightly", "cadence", (
        r"fortnightly", r"bi-?weekly", r"every (?:two|2) weeks", r"every other week",
    )),
    TagRule("monthly", "cadence", (
        _cadence_word("monthly"), r"(?:every|each|once a) month", r"month[- ]end",
        r"end of (?:the|each|every) month",
    )),
    TagRule("quarterly", "cadence", (
        r"quarterly", r"(?:every|each|once a) quarter", r"quarter[- ]end",
        r"end of (?:the|each|every) quarter",
    )),
    TagRule("annual", "cadence", (
        _cadence_word("annual(?:ly)?"), _cadence_word("yearly"),
        r"(?:every|each|once a) year", r"year[- ]end", r"end of (?:the|each|every) year",
    )),
)

# Words that say nothing about what a dataset covers. Words under three letters are dropped
# anyway; the short ones here are for names typed in capitals, where "OF" would pass as an acronym.
_NAME_STOPWORDS: Final = frozenset({
    "an", "as", "at", "by", "in", "is", "of", "on", "or", "to", "the", "and", "for", "from",
    "with", "without", "into", "per", "via", "all", "any", "each", "every", "our", "new", "old",
    "current", "latest", "master", "main", "raw", "full", "final", "info", "information",
    "details", "record", "records", "file", "files", "list", "lists", "log", "logs", "report",
    "reports", "export", "exports", "extract", "extracts", "feed", "feeds", "snapshot",
    "snapshots", "stream", "streams", "register", "directory", "tables", "view", "views",
    "summary", "overview", "team", "real-time", "hourly", "daily", "nightly", "weekly",
    "fortnightly", "monthly", "quarterly", "annual", "yearly",
})
# fmt: on

_NAME_WEIGHT: Final = 3
_OWNER_WEIGHT: Final = 2
_DESCRIPTION_WEIGHT: Final = 1

_FALLBACK_WORDS: Final = 3
_FALLBACK_MIN_LETTERS: Final = 3
_UNCATEGORISED: Final = "uncategorised"
_NAME_WORD = re.compile(r"[^\W_]+(?:[-&][^\W_]+)*")
_ARTIFACTS = r"export|extract|feed|snapshot|list|log|report|stream|register|directory"
_CADENCE_WORDS = (
    r"real[- ]time|hourly|daily|nightly|weekly|fortnightly|monthly|quarterly|annual|yearly"
    r"|end[- ]of[- ]day|EOD|month[- ]end|quarter[- ]end|year[- ]end"
)
_TEMPLATE = re.compile(
    rf"(?:(?:an?|the) )?(?:(?:{_CADENCE_WORDS}) )?(?P<artifact>{_ARTIFACTS}) of"
    r" (?P<object>.+)",
    re.IGNORECASE,
)
_MARKER = re.compile(r"\b(?:including|with|covering|containing)\b", re.IGNORECASE)
_FIELD_SEPARATOR = re.compile(r",|\b(?:and|or)\b", re.IGNORECASE)
_IDENTIFIER_FIELD = re.compile(r"\b(?:ids?|identifiers?|keys?|uuids?|guids?)$", re.IGNORECASE)
_FIELDS_KEPT: Final = 3
_DISPLAY_WORD = re.compile(r"[^\W_]+(?:&[^\W_]+)*")
_TRAILING = " .,;:!?…"
_AN_WORDS: Final = frozenset({"export", "extract", "annual", "hourly"})


class KeywordCurationProvider:
    """Curates from a weighted facet taxonomy and a summary template, without a model.

    It models the same facets, tag style and summary shape as the Claude prompt, so both
    providers' output reads alike, and it is deterministic, so tests pin its output exactly.
    """

    name: Final[CurationProviderName] = "keyword"
    model: Final = None

    def __init__(self, *, delay_ms: int = 0, sleep: Sleep = asyncio.sleep) -> None:
        self._delay_seconds = delay_ms / 1000
        self._sleep = sleep

    async def curate(self, new: NewDataset) -> CurationDraft:
        await self._sleep(self._delay_seconds)
        name, owner, description = (
            " ".join(text.split()) for text in (new.name, new.owner, new.description)
        )
        selected = _select(name, owner, description)
        cadence = next((rule for rule in selected if rule.facet == "cadence"), None)
        return CurationDraft(
            tags=_tags(selected, name), summary=_summary(name, description, cadence)
        )


def _select(name: str, owner: str, description: str) -> list[TagRule]:
    fields = ((name, _NAME_WEIGHT), (owner, _OWNER_WEIGHT), (description, _DESCRIPTION_WEIGHT))
    about = f"{name}\n{description}"
    scores = {rule: _score(rule, fields, about) for rule in TAXONOMY}
    selected: list[TagRule] = []
    for facet, cap in FACET_CAPS.items():
        # sorted() is stable, so equal scores stay in taxonomy order.
        ranked = sorted(
            (rule for rule in TAXONOMY if rule.facet == facet and scores[rule]),
            key=lambda rule: -scores[rule],
        )
        tags: list[str] = []
        for rule in ranked:
            if rule.tag not in tags and len(tags) < cap:
                tags.append(rule.tag)
                selected.append(rule)
    return selected


def _score(rule: TagRule, fields: Iterable[tuple[str, int]], about: str) -> int:
    # The owner says who maintains the data, not whom it describes, so context ignores it.
    if rule.context_regex is not None and rule.context_regex.search(about) is None:
        return 0
    return sum(weight for text, weight in fields if rule.regex.search(text))


def _tags(selected: list[TagRule], name: str) -> tuple[str, ...]:
    tags = tuple(rule.tag for rule in selected)
    if any(rule.facet in {"domain", "subject"} for rule in selected):
        return tags
    # Normalising here, not only in CurationService, is what guarantees a usable tag survives.
    words = normalise_tags(word for word in _NAME_WORD.findall(name) if _distinctive(word))
    return normalise_tags((*words[:_FALLBACK_WORDS], *tags)) or (_UNCATEGORISED,)


def _distinctive(word: str) -> bool:
    if word.casefold() in _NAME_STOPWORDS:
        return False
    is_acronym = canonical_case(word).isupper()
    return is_acronym or sum(char.isalpha() for char in word) >= _FALLBACK_MIN_LETTERS


def _summary(name: str, description: str, cadence: TagRule | None) -> str:
    sentence = first_sentence(description).rstrip(_TRAILING)
    noun, described = _artifact_of(sentence) or ("dataset", _display_name(name))
    # "A daily dataset of daily trades" would say it twice.
    if cadence is not None and cadence.regex.search(described) is None:
        noun = f"{cadence.tag} {noun}"
    article = "An" if noun.split(" ", 1)[0] in _AN_WORDS else "A"
    fields = _fields(sentence)
    covering = f" covering {fields}" if fields else ""
    return f"{article} {noun} of {described}{covering}."


def _artifact_of(sentence: str) -> tuple[str, str] | None:
    template = _TEMPLATE.fullmatch(sentence)
    if template is None:
        return None
    described = _MARKER.split(template["object"], maxsplit=1)[0].rstrip(_TRAILING)
    return (template["artifact"].lower(), described) if _has_word(described) else None


def _display_name(name: str) -> str:
    def case(word: re.Match[str]) -> str:
        text = word[0]
        # Mixed case such as "IoT" or "SKUs" is an acronym or a brand, kept as the owner wrote it.
        if text[1:] != text[1:].lower() and not text.isupper():
            return text
        return canonical_case(text)

    return _DISPLAY_WORD.sub(case, name).rstrip(_TRAILING)


def _fields(sentence: str) -> str:
    marker = _MARKER.search(sentence)
    if marker is None:
        return ""
    pieces = (piece.strip(_TRAILING) for piece in _FIELD_SEPARATOR.split(sentence[marker.end() :]))
    kept = [piece for piece in pieces if _has_word(piece) and not _IDENTIFIER_FIELD.search(piece)]
    if not kept:
        return ""
    *leading, last = kept[:_FIELDS_KEPT]
    if not leading:
        return last
    serial_comma = "," if len(leading) > 1 else ""
    return f"{', '.join(leading)}{serial_comma} and {last}"


def _has_word(text: str) -> bool:
    return any(char.isalnum() for char in text)
