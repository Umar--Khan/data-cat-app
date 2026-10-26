import asyncio

import pytest
from hypothesis import given
from hypothesis import strategies as st

from catalogue.curation.base import CurationDraft
from catalogue.curation.keyword_provider import TAXONOMY, KeywordCurationProvider
from catalogue.curation.normalise import (
    CANONICAL_ACRONYMS,
    MAX_TAG_LENGTH,
    TAG_PATTERN,
    first_sentence,
    normalise_summary,
    normalise_tags,
)
from catalogue.curation.service import CurationService
from catalogue.domain.models import NewDataset

CADENCE_TAGS = {rule.tag for rule in TAXONOMY if rule.facet == "cadence"}


async def curate(name: str, owner: str, description: str) -> CurationDraft:
    return await KeywordCurationProvider().curate(NewDataset(name, owner, description))


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "owner", "description", "tags", "summary"),
    [
        pytest.param(
            "Trade Confirmations",
            "Middle Office",
            "Daily export of confirmed trades including instrument type, counterparty, notional "
            "value, and settlement date.",
            ["trading", "finance", "settlements", "daily"],
            "A daily export of confirmed trades covering instrument type, counterparty, and "
            "notional value.",
            id="brief-test-payload",
        ),
        pytest.param(
            "Customer Transactions",
            "Finance Team",
            "Contains daily transaction records including transaction ID, customer ID, amount, "
            "currency, and timestamp.",
            ["finance", "transactions", "PII", "daily"],
            "A daily dataset of customer transactions covering amount, currency, and timestamp.",
            id="seed-1",
        ),
        pytest.param(
            "Product Inventory",
            "Operations Team",
            "Snapshot of warehouse stock levels by SKU, including product name, quantity on hand, "
            "and reorder threshold.",
            ["operations", "inventory", "warehouse"],
            "A snapshot of warehouse stock levels by SKU covering product name, quantity on hand, "
            "and reorder threshold.",
            id="seed-2",
        ),
        pytest.param(
            "Employee Directory",
            "HR Team",
            "List of current employees with name, department, role, and office location. Updated "
            "weekly.",
            ["HR", "employees", "PII", "weekly"],
            "A weekly list of current employees covering name, department, and role.",
            id="seed-3",
        ),
    ],
)
async def test_golden_cases(
    name: str, owner: str, description: str, tags: list[str], summary: str
) -> None:
    assert await curate(name, owner, description) == CurationDraft(
        tags=tuple(tags), summary=summary
    )


# Realistic datasets beyond the brief, kept so a taxonomy change shows its effect on each.
@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "owner", "description", "tags", "summary"),
    [
        pytest.param(
            "Web Analytics Events",
            "Growth Team",
            "Clickstream events from the website and mobile app, including page URL, session ID, "
            "user ID, and referrer. Streamed in real time.",
            ["digital", "events", "PII", "real-time"],
            "A real-time dataset of web analytics events covering page URL and referrer.",
            id="web-analytics-events",
        ),
        pytest.param(
            "FX Rates",
            "Treasury",
            "Daily snapshot of end-of-day FX rates for 40 currency pairs from Reuters.",
            ["finance", "FX", "daily"],
            "A snapshot of end-of-day FX rates for 40 currency pairs from Reuters.",
            id="fx-rates",
        ),
        pytest.param(
            "Exchange Rates",
            "Treasury",
            "Hourly feed of spot exchange rates for major currency pairs.",
            ["finance", "FX", "hourly"],
            "An hourly feed of spot exchange rates for major currency pairs.",
            id="exchange-rates",
        ),
        pytest.param(
            "Patient Admissions",
            "Clinical Operations",
            "Hospital admissions and discharges including patient ID, ward, admission date, "
            "diagnosis code, and length of stay. Refreshed nightly.",
            ["healthcare", "operations", "admissions", "patients", "PII", "daily"],
            "A daily dataset of patient admissions covering ward, admission date, and diagnosis "
            "code.",
            id="patient-admissions",
        ),
        pytest.param(
            "Supplier Invoices",
            "Accounts Payable",
            "Invoices received from suppliers with invoice number, supplier name, amount, GST, "
            "due date, and payment status.",
            ["finance", "procurement", "invoices", "suppliers"],
            "A dataset of supplier invoices covering invoice number, supplier name, and amount.",
            id="supplier-invoices",
        ),
        pytest.param(
            "IoT Telemetry",
            "Platform Engineering",
            "Sensor readings from factory-floor devices every 5 seconds, including device ID, "
            "temperature, vibration, and status.",
            ["engineering", "manufacturing", "telemetry", "devices", "real-time"],
            "A real-time dataset of IoT telemetry covering temperature, vibration, and status.",
            id="iot-telemetry",
        ),
        pytest.param(
            "Marketing Campaigns",
            "Growth Marketing",
            "Weekly report of paid social and search campaigns with spend, impressions, clicks, "
            "and conversions.",
            ["marketing", "campaigns", "weekly"],
            "A weekly report of paid social and search campaigns covering spend, impressions, and "
            "clicks.",
            id="marketing-campaigns",
        ),
        pytest.param(
            "Newsletter Subscribers",
            "Marketing",
            "Subscribers to the monthly newsletter with first name, email, and signup date.",
            ["marketing", "customers", "PII", "monthly"],
            "A monthly dataset of newsletter subscribers covering first name, email, and signup "
            "date.",
            id="newsletter-subscribers",
        ),
        pytest.param(
            "Payroll",
            "People Operations",
            "Fortnightly payroll run for all employees with employee number, gross pay, tax "
            "withheld, and superannuation.",
            ["HR", "finance", "payroll", "employees", "PII", "fortnightly"],
            "A fortnightly dataset of payroll covering employee number, gross pay, and tax "
            "withheld.",
            id="payroll",
        ),
        pytest.param(
            "Leave Balances",
            "HR Team",
            "Annual leave and sick leave balances for every employee, refreshed every Monday.",
            ["HR", "leave", "employees", "weekly"],
            "A weekly dataset of leave balances.",
            id="leave-balances",
        ),
        pytest.param(
            "Contractor Timesheets",
            "Workforce Planning",
            "Bi-weekly timesheets submitted by contractors, with contractor name, hours, and rate.",
            ["HR", "employees", "PII", "fortnightly"],
            "A fortnightly dataset of contractor timesheets covering contractor name, hours, and "
            "rate.",
            id="contractor-timesheets",
        ),
        pytest.param(
            "Employee Expense Claims",
            "Finance Operations",
            "Expense claims submitted by staff, with employee ID, merchant, amount, category, and "
            "approval status. Updated daily.",
            ["finance", "HR", "expenses", "claims", "PII", "daily"],
            "A daily dataset of employee expense claims covering merchant, amount, and category.",
            id="employee-expense-claims",
        ),
        pytest.param(
            "Support Tickets",
            "Customer Service",
            "All customer support tickets with ticket ID, customer email, category, priority, and "
            "resolution time.",
            ["customer-service", "tickets", "PII"],
            "A dataset of support tickets covering customer email, category, and priority.",
            id="support-tickets",
        ),
        pytest.param(
            "Customer Feedback",
            "CX Team",
            "NPS survey responses with customer name, score, and free-text comments, collected "
            "monthly.",
            ["customer-service", "surveys", "PII", "monthly"],
            "A monthly dataset of customer feedback covering customer name, score, and free-text "
            "comments.",
            id="customer-feedback",
        ),
        pytest.param(
            "General Ledger",
            "Group Finance",
            "Monthly general ledger extract with account code, cost centre, debit, credit, and "
            "posting date.",
            ["finance", "ledger", "monthly"],
            "A monthly dataset of general ledger covering account code, cost centre, and debit.",
            id="general-ledger",
        ),
        pytest.param(
            "Credit Risk Exposures",
            "Risk Management",
            "Daily counterparty credit exposures by legal entity, including exposure amount, "
            "limit, and rating.",
            ["risk", "finance", "exposures", "daily"],
            "A daily dataset of credit risk exposures covering exposure amount, limit, and rating.",
            id="credit-risk-exposures",
        ),
        pytest.param(
            "KYC Checks",
            "Financial Crime",
            "Customer due diligence results for new clients, including client ID, date of birth, "
            "passport number, and risk rating.",
            ["compliance", "risk", "KYC", "customers", "PII"],
            "A dataset of KYC checks covering date of birth, passport number, and risk rating.",
            id="kyc-checks",
        ),
        pytest.param(
            "Sanctions Screening Hits",
            "Compliance",
            "Real-time feed of sanctions screening alerts with matched entity name, list source, "
            "and match score.",
            ["compliance", "sanctions", "real-time"],
            "A real-time feed of sanctions screening alerts covering matched entity name, list "
            "source, and match score.",
            id="sanctions-screening-hits",
        ),
        pytest.param(
            "Loan Book",
            "Retail Lending",
            "Month-end snapshot of all active home loans, including loan ID, borrower name, "
            "balance, interest rate, and arrears status.",
            ["lending", "finance", "loans", "rates", "PII", "monthly"],
            "A monthly snapshot of all active home loans covering borrower name, balance, and "
            "interest rate.",
            id="loan-book",
        ),
        pytest.param(
            "Interest Rate Curves",
            "Markets Treasury",
            "End-of-day yield curves for AUD, USD, and EUR, including tenor, rate, and curve name.",
            ["finance", "trading", "rates", "daily"],
            "A daily dataset of interest rate curves covering tenor, rate, and curve name.",
            id="interest-rate-curves",
        ),
        pytest.param(
            "Bond Prices",
            "Fixed Income",
            "End-of-day closing prices for government and corporate bonds, including ISIN, "
            "coupon, and yield.",
            ["trading", "prices", "daily"],
            "A daily dataset of bond prices covering ISIN, coupon, and yield.",
            id="bond-prices",
        ),
        pytest.param(
            "Insurance Claims",
            "Claims Operations",
            "Motor insurance claims lodged by policyholders, including claim number, policy "
            "number, incident date, and claim amount. Updated daily.",
            ["insurance", "operations", "claims", "daily"],
            "A daily dataset of insurance claims covering claim number, policy number, and "
            "incident date.",
            id="insurance-claims",
        ),
        pytest.param(
            "Store Sales",
            "Retail Analytics",
            "Hourly point-of-sale transactions by store and SKU, including quantity, unit price, "
            "discount, and basket ID.",
            ["sales", "transactions", "hourly"],
            "An hourly dataset of store sales covering quantity, unit price, and discount.",
            id="store-sales",
        ),
        pytest.param(
            "Purchase Orders",
            "Procurement",
            "Purchase orders raised against approved vendors, with PO number, vendor, line items, "
            "and total value. Updated hourly.",
            ["procurement", "orders", "suppliers", "hourly"],
            "An hourly dataset of purchase orders covering PO number, vendor, and line items.",
            id="purchase-orders",
        ),
        pytest.param(
            "Fleet Vehicle Telematics",
            "Logistics",
            "GPS positions and fuel usage for delivery vans, streamed every 30 seconds, including "
            "vehicle ID, driver ID, speed, and location.",
            ["operations", "vehicles", "telemetry", "PII", "real-time"],
            "A real-time dataset of fleet vehicle telematics covering speed and location.",
            id="fleet-vehicle-telematics",
        ),
        pytest.param(
            "Server Access Logs",
            "Platform Security",
            "Authentication events from all production servers with username, source IP address, "
            "timestamp, and outcome.",
            ["security", "engineering", "logs", "events", "PII"],
            "A dataset of server access logs covering username, source IP address, and timestamp.",
            id="server-access-logs",
        ),
        pytest.param(
            "Safety Incidents",
            "Workplace Health and Safety",
            "Workplace safety incidents with location, severity, and corrective action.",
            ["safety", "incidents"],
            "A dataset of safety incidents covering location, severity, and corrective action.",
            id="safety-incidents",
        ),
        pytest.param(
            "Emissions Inventory",
            "Sustainability",
            "Annual scope 1, 2 and 3 greenhouse gas emissions by site, with CO2e tonnes and data "
            "source.",
            ["ESG", "emissions", "annual"],
            "An annual dataset of emissions inventory covering CO2e tonnes and data source.",
            id="emissions-inventory",
        ),
    ],
)
async def test_regression_cases(
    name: str, owner: str, description: str, tags: list[str], summary: str
) -> None:
    assert await curate(name, owner, description) == CurationDraft(
        tags=tuple(tags), summary=summary
    )


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "owner", "description", "tags"),
    [
        pytest.param(
            "Payroll",
            "Treasury",
            "Campaign spend.",
            ["HR", "finance", "payroll", "campaigns"],
            id="name-3-beats-owner-2-beats-description-1",
        ),
        pytest.param(
            "Sample",
            "Finance",
            "Marketing, marketing, and more marketing.",
            ["finance", "marketing"],
            id="presence-not-frequency",
        ),
        pytest.param(
            "Sample",
            "Team",
            "Trades and loans.",
            ["trading", "lending", "loans"],
            id="ties-in-taxonomy-order",
        ),
        pytest.param(
            "Sample",
            "Team",
            "Updated daily. Customer ID. Invoices. Finance.",
            ["finance", "invoices", "PII", "daily"],
            id="facet-order-not-text-order",
        ),
        pytest.param(
            "Sample",
            "Team",
            "Daily and weekly trades, loans, insurance premiums, invoices, payments, and "
            "settlements, with customer ID and employees with name.",
            ["trading", "lending", "payments", "settlements", "PII", "daily"],
            id="facet-caps-2-2-1-1",
        ),
    ],
)
async def test_selection(name: str, owner: str, description: str, tags: list[str]) -> None:
    assert (await curate(name, owner, description)).tags == tuple(tags)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "description",
    [
        pytest.param("Accounts with email, tier, and region.", id="listed-email"),
        pytest.param("Orders with customer email, total, and status.", id="customer-email"),
        pytest.param("Leads with email address and source.", id="email-address"),
        pytest.param("Plans with phone number and tier.", id="phone-number"),
        pytest.param("Shipments with delivery address and weight.", id="delivery-address"),
        pytest.param("Accounts with name, address, and tier.", id="listed-address"),
        pytest.param("Memberships with date of birth and tier.", id="date-of-birth"),
        pytest.param("Visas with tax file number and status.", id="tax-file-number"),
        pytest.param("Bookings with passport number and nationality.", id="passport"),
        pytest.param("Hires with driver's licence and vehicle.", id="driver-licence"),
        pytest.param("Claims with client number and amount.", id="client-number"),
        pytest.param("Shifts with employee ID and hours.", id="employee-id"),
        pytest.param("Visits with patient ID and ward.", id="patient-id"),
        pytest.param("Logins with user ID and timestamp.", id="user-id"),
        pytest.param("Sessions with source IP address and browser.", id="ip-address"),
        pytest.param("Records flagged as containing PII.", id="stated-outright"),
    ],
)
async def test_pii_rule_a_a_direct_identifier_is_enough(description: str) -> None:
    assert "PII" in (await curate("Sample", "Team", description)).tags


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "description"),
    [
        pytest.param("Sample", "Employees with name and role.", id="employees-with-name"),
        pytest.param("Sample", "Customers including name, segment, and region.", id="listed"),
        pytest.param("Sample", "Contractors with full name and day rate.", id="full-name"),
        pytest.param("Sample", "Ward list with patient names and beds.", id="person-qualified"),
        pytest.param("Staff List", "Rows with name and team.", id="person-noun-in-the-name"),
    ],
)
async def test_pii_rule_b_a_person_noun_with_an_unqualified_name(
    name: str, description: str
) -> None:
    assert "PII" in (await curate(name, "Team", description)).tags


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("owner", "description"),
    [
        pytest.param("Team", "Products with product name, price, and category.", id="product"),
        pytest.param(
            "Team", "Trades with counterparty, notional, and currency.", id="counterparty"
        ),
        pytest.param("Team", "Counterparties with counterparty name and LEI.", id="cpty-name"),
        pytest.param("Team", "Suppliers with name and ABN.", id="name-without-a-person-noun"),
        pytest.param("Team", "Invoices with supplier name and amount.", id="supplier-name"),
        pytest.param(
            "Team",
            "Performance of email and social campaigns with sends and opens.",
            id="email-campaigns",
        ),
        pytest.param("Team", "Warehouses with warehouse address and capacity.", id="site-address"),
        pytest.param(
            "Customer Success", "Products with name and price.", id="person-only-in-owner"
        ),
        pytest.param(
            "Team",
            "Customers with product name and price.",
            id="qualified-name-beside-a-person-noun",
        ),
    ],
)
async def test_pii_negatives(owner: str, description: str) -> None:
    assert "PII" not in (await curate("Sample", owner, description)).tags


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("description", "cadence"),
    [
        pytest.param("Prices by desk. Refreshed hourly.", "hourly", id="second-sentence"),
        pytest.param("Prices streamed in real time.", "real-time", id="real-time"),
        pytest.param("Prices captured every 5 seconds.", "real-time", id="every-few-seconds"),
        pytest.param("Nightly prices.", "daily", id="nightly"),
        pytest.param("End-of-day prices.", "daily", id="end-of-day"),
        pytest.param("Prices refreshed every Monday.", "weekly", id="every-monday"),
        pytest.param("Bi-weekly prices.", "fortnightly", id="bi-weekly"),
        pytest.param("Month-end prices.", "monthly", id="month-end"),
        pytest.param("Quarterly prices.", "quarterly", id="quarterly"),
        pytest.param("Prices published annually.", "annual", id="annually"),
    ],
)
async def test_cadence_is_read_from_the_whole_description(description: str, cadence: str) -> None:
    assert (await curate("Prices", "Team", description)).tags == ("prices", cadence)


@pytest.mark.anyio
@pytest.mark.parametrize(
    "description",
    [
        pytest.param("Daily active users by country.", id="daily-active-users"),
        pytest.param("Average daily balance per account.", id="average-daily"),
        pytest.param("Annual leave balances.", id="annual-leave"),
        pytest.param("Annual salary bands.", id="annual-salary"),
        pytest.param("Half-hourly meter readings.", id="half-hourly"),
    ],
)
async def test_a_measure_named_after_a_period_is_not_a_cadence(description: str) -> None:
    assert not CADENCE_TAGS & set((await curate("Sample", "Team", description)).tags)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("description", "present", "absent"),
    [
        pytest.param(
            "Warehouse stock levels by site.", {"inventory", "warehouse"}, set(), id="stock-levels"
        ),
        pytest.param(
            "Stock prices by exchange.", {"trading", "prices"}, {"inventory"}, id="stock-prices"
        ),
        pytest.param(
            "Tables in the data warehouse.", {"engineering"}, {"warehouse"}, id="data-warehouse"
        ),
        pytest.param(
            "An inventory of tables and owners.",
            set(),
            {"inventory", "operations"},
            id="inventory-of-tables",
        ),
        pytest.param(
            "Emissions inventory by site.",
            {"ESG", "emissions"},
            {"inventory"},
            id="emissions-inventory",
        ),
        pytest.param(
            "Prices checked in order to reconcile.", {"prices"}, {"orders"}, id="in-order-to"
        ),
        pytest.param("Prices with a 24 hr turnaround.", {"prices"}, {"HR"}, id="hr-for-hours"),
        pytest.param("Prices as it stands.", {"prices"}, {"IT"}, id="it-the-pronoun"),
        pytest.param(
            "Customers with social security number.",
            {"customers", "PII"},
            {"security"},
            id="social-security",
        ),
        pytest.param(
            "Transaction monitoring alerts.",
            {"compliance", "AML"},
            {"engineering"},
            id="transaction-monitoring",
        ),
        pytest.param(
            "Help desk tickets by priority.",
            {"customer-service", "tickets"},
            {"trading"},
            id="help-desk",
        ),
        pytest.param("Promotions granted to staff.", {"HR"}, {"marketing"}, id="staff-promotions"),
        pytest.param(
            "Bank accounts at retail branches.", {"finance"}, {"sales"}, id="retail-banking"
        ),
        pytest.param(
            "Claims with incident date and amount.", {"claims"}, {"incidents"}, id="incident-date"
        ),
    ],
)
async def test_ambiguous_words_count_only_in_a_qualifying_phrase(
    description: str, present: set[str], absent: set[str]
) -> None:
    tags = set((await curate("Sample", "Team", description)).tags)

    assert present <= tags
    assert not absent & tags


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "description", "tags"),
    [
        pytest.param(
            "Board Pack Q3",
            "Quarterly board papers and minutes.",
            ["board", "pack", "Q3", "quarterly"],
            id="acronym-kept-cadence-appended",
        ),
        pytest.param(
            "Alpha Beta Gamma Delta", "Stuff.", ["alpha", "beta", "gamma"], id="at-most-three-words"
        ),
        pytest.param("The Master List of Things", "Stuff.", ["things"], id="stopwords-dropped"),
        pytest.param(
            "ABC Monthly Pack", "Stuff.", ["ABC", "pack", "monthly"], id="cadence-word-not-repeated"
        ),
        pytest.param(
            "Zeta Register", "Rows with email address.", ["zeta", "PII"], id="sensitivity-appended"
        ),
        pytest.param("Alpha alpha ALPHA Beta", "Stuff.", ["alpha", "beta"], id="distinct-words"),
        pytest.param("Misc Data", "Stuff.", ["uncategorised"], id="generic-words-dropped"),
        pytest.param("Q Ab Xy", "Stuff.", ["uncategorised"], id="short-words-dropped"),
        pytest.param("Café Données", "Stuff.", ["uncategorised"], id="non-ascii-words-dropped"),
        pytest.param(
            "Zeta Feed",
            "Transactions by merchant.",
            ["transactions"],
            id="a-subject-alone-skips-the-fallback",
        ),
    ],
)
async def test_fallback_takes_name_words_when_no_domain_or_subject_matches(
    name: str, description: str, tags: list[str]
) -> None:
    assert (await curate(name, "Team", description)).tags == tuple(tags)


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "description", "summary"),
    [
        pytest.param(
            "Prices", "Hourly feed of prices.", "An hourly feed of prices.", id="an-hourly"
        ),
        pytest.param(
            "Revenue", "Annual report of revenue.", "An annual report of revenue.", id="an-annual"
        ),
        pytest.param("Trades", "Export of trades.", "An export of trades.", id="an-export"),
        pytest.param(
            "Balances", "Extract of balances.", "An extract of balances.", id="an-extract"
        ),
        pytest.param("Prices", "Feed of prices.", "A feed of prices.", id="a-feed"),
        pytest.param("Staff", "Weekly list of staff.", "A weekly list of staff.", id="a-weekly"),
        pytest.param(
            "Store Sales",
            "Till transactions, refreshed hourly.",
            "An hourly dataset of store sales.",
            id="an-hourly-dataset",
        ),
        pytest.param(
            "Group Revenue",
            "Revenue by segment, published annually.",
            "An annual dataset of group revenue.",
            id="an-annual-dataset",
        ),
        pytest.param(
            "Store Sales",
            "Till transactions, refreshed daily.",
            "A daily dataset of store sales.",
            id="a-daily-dataset",
        ),
    ],
)
async def test_summary_article(name: str, description: str, summary: str) -> None:
    assert (await curate(name, "Team", description)).summary == summary


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("name", "description", "summary"),
    [
        pytest.param(
            "Ledger",
            "A daily export of general ledger balances, with account and amount.",
            "A daily export of general ledger balances covering account and amount.",
            id="leading-article",
        ),
        pytest.param(
            "Stock",
            "The weekly snapshot of stock levels.",
            "A weekly snapshot of stock levels.",
            id="leading-the",
        ),
        pytest.param(
            "Stock",
            "Snapshot of stock levels, with SKU.",
            "A snapshot of stock levels covering SKU.",
            id="object-punctuation-removed",
        ),
        pytest.param(
            "Balances",
            "Export of daily balances.",
            "An export of daily balances.",
            id="cadence-already-in-the-object",
        ),
        pytest.param(
            "Daily Trades",
            "Trades by desk.",
            "A dataset of daily trades.",
            id="cadence-already-in-the-name",
        ),
        pytest.param(
            "Trades",
            "Daily exports of trades.",
            "A daily dataset of trades.",
            id="plural-artifact-not-matched",
        ),
        pytest.param(
            "Products",
            "Master list of products.",
            "A dataset of products.",
            id="adjective-before-artifact-not-matched",
        ),
        pytest.param(
            "Trades",
            "Export of, with amount.",
            "A dataset of trades covering amount.",
            id="empty-object",
        ),
        pytest.param(
            "IoT Device Fleet",
            "Sensors.",
            "A dataset of IoT device fleet.",
            id="mixed-case-acronym-kept",
        ),
        pytest.param(
            "HR Headcount", "Staff.", "A dataset of HR headcount.", id="canonical-acronym-kept"
        ),
        pytest.param(
            "CUSTOMER TRANSACTIONS",
            "Rows.",
            "A dataset of customer transactions.",
            id="capitals-lowered",
        ),
        pytest.param("P&L by Desk", "Rows.", "A dataset of P&L by desk.", id="ampersand-acronym"),
        pytest.param(
            "Customer Orders!",
            "Rows.",
            "A dataset of customer orders.",
            id="name-punctuation-removed",
        ),
    ],
)
async def test_summary_template(name: str, description: str, summary: str) -> None:
    assert (await curate(name, "Team", description)).summary == summary


@pytest.mark.anyio
@pytest.mark.parametrize(
    ("description", "summary"),
    [
        pytest.param("Accounts by branch.", "A dataset of accounts.", id="no-marker"),
        pytest.param("Accounts with balance.", "A dataset of accounts covering balance.", id="one"),
        pytest.param(
            "Accounts with balance and currency.",
            "A dataset of accounts covering balance and currency.",
            id="two",
        ),
        pytest.param(
            "Accounts with balance, currency, and branch.",
            "A dataset of accounts covering balance, currency, and branch.",
            id="three",
        ),
        pytest.param(
            "Accounts with balance, currency, branch, and status.",
            "A dataset of accounts covering balance, currency, and branch.",
            id="first-three-of-four",
        ),
        pytest.param(
            "Accounts with debit or credit amount.",
            "A dataset of accounts covering debit and credit amount.",
            id="or",
        ),
        pytest.param(
            "Accounts containing balance.",
            "A dataset of accounts covering balance.",
            id="containing",
        ),
        pytest.param(
            "Accounts covering balance.", "A dataset of accounts covering balance.", id="covering"
        ),
        pytest.param(
            "Accounts including account key, customer UUID, record identifier, row ID, and "
            "balance.",
            "A dataset of accounts covering balance.",
            id="identifier-fields-dropped",
        ),
        pytest.param(
            "Accounts with account ID and row key.", "A dataset of accounts.", id="only-identifiers"
        ),
        pytest.param(
            "Accounts with balance. With currency.",
            "A dataset of accounts covering balance.",
            id="first-sentence-only",
        ),
    ],
)
async def test_summary_fields(description: str, summary: str) -> None:
    assert (await curate("Accounts", "Team", description)).summary == summary


def test_every_taxonomy_tag_is_already_normalised() -> None:
    for rule in TAXONOMY:
        assert normalise_tags([rule.tag]) == (rule.tag,), rule.tag


def test_a_tag_belongs_to_one_facet() -> None:
    facets: dict[str, set[str]] = {}
    for rule in TAXONOMY:
        facets.setdefault(rule.tag, set()).add(rule.facet)

    assert {tag: found for tag, found in facets.items() if len(found) > 1} == {}


def test_identifies_itself_as_the_keyword_provider_with_no_model() -> None:
    provider = KeywordCurationProvider()

    assert provider.name == "keyword"
    assert provider.model is None


@pytest.mark.anyio
async def test_awaits_the_configured_delay_through_the_injected_sleep_before_curating() -> None:
    delays: list[float] = []
    gate = asyncio.Event()

    async def sleep(seconds: float) -> None:
        delays.append(seconds)
        await gate.wait()

    provider = KeywordCurationProvider(delay_ms=1200, sleep=sleep)
    task = asyncio.create_task(provider.curate(NewDataset("Prices", "Team", "Nightly prices.")))
    await asyncio.sleep(0)

    assert delays == [1.2]
    assert not task.done()

    gate.set()

    assert (await task).tags == ("prices", "daily")


# Words the taxonomy, template and fallback react to, so generated text exercises their rules
# far more often than random characters would.
VOCABULARY = [
    *("Daily", "weekly", "every", "Monday", "real-time", "annual", "leave"),
    *("export", "extract", "snapshot", "list", "of", "A", "An", "The"),
    *("with", "including", "covering", "and", "or", ",", ".", "!", "?", "e.g.", "U.S.", "…"),
    *("name", "email", "address", "customer", "employees", "ID", "key", "UUID"),
    *("PII", "HR", "IT", "FX", "P&L", "SKU", "Q3", "Café", "x" * 40, '"', "'", "#"),
    *("trades", "inventory", "stock", "levels", "warehouse", "data", "misc", "table"),
]


def bounded_text(max_size: int) -> st.SearchStrategy[str]:
    """Text the API would accept for a field: trimmed, non-blank, at most `max_size` long."""
    vocabulary = st.lists(st.sampled_from(VOCABULARY), min_size=1, max_size=60).map(" ".join)
    return (
        st.one_of(st.text(min_size=1, max_size=max_size), vocabulary)
        .map(lambda text: text[:max_size].strip())
        .filter(bool)
    )


@pytest.mark.anyio
@given(name=bounded_text(120), owner=bounded_text(120), description=bounded_text(2000))
async def test_keyword_curation_always_completes(name: str, owner: str, description: str) -> None:
    result = await CurationService(KeywordCurationProvider()).curate(
        NewDataset(name, owner, description)
    )

    assert result.status == "completed"
    assert 1 <= len(result.tags) <= 6
    for tag in result.tags:
        assert tag in CANONICAL_ACRONYMS.values() or TAG_PATTERN.fullmatch(tag), tag
        assert len(tag) <= MAX_TAG_LENGTH
    assert len({tag.casefold() for tag in result.tags}) == len(result.tags)
    assert result.summary
    assert first_sentence(result.summary) == result.summary
    assert normalise_summary(result.summary) == result.summary
