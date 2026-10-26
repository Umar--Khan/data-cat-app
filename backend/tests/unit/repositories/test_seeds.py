import json
from datetime import UTC, datetime

from catalogue.domain.models import Curation
from catalogue.repositories.seeds import seed_datasets

STARTED_AT = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)

# The brief's "Sample Data" block, verbatim.
BRIEF_SAMPLE_DATA = """
[
  {
    "id": "1",
    "name": "Customer Transactions",
    "owner": "Finance Team",
    "description": "Contains daily transaction records including transaction ID, customer ID, amount, currency, and timestamp.",
    "tags": ["finance", "transactions", "PII", "daily"],
    "summary": "A daily feed of customer transaction records covering amounts, currencies, and timestamps."
  },
  {
    "id": "2",
    "name": "Product Inventory",
    "owner": "Operations Team",
    "description": "Snapshot of warehouse stock levels by SKU, including product name, quantity on hand, and reorder threshold.",
    "tags": ["inventory", "operations", "warehouse"],
    "summary": "A warehouse snapshot tracking stock levels and reorder thresholds per product SKU."
  },
  {
    "id": "3",
    "name": "Employee Directory",
    "owner": "HR Team",
    "description": "List of current employees with name, department, role, and office location. Updated weekly.",
    "tags": ["HR", "PII", "employees", "weekly"],
    "summary": "A weekly-refreshed directory of employees including role, department, and location."
  }
]
"""  # noqa: E501


def test_seeds_are_the_brief_sample_data_with_its_own_tag_order() -> None:
    seeds = [
        {
            "id": seed.id,
            "name": seed.name,
            "owner": seed.owner,
            "description": seed.description,
            "tags": list(seed.tags),
            "summary": seed.summary,
        }
        for seed in seed_datasets(STARTED_AT)
    ]

    assert seeds == json.loads(BRIEF_SAMPLE_DATA)


def test_seeds_are_credited_to_hand_curation_and_created_at_the_given_time() -> None:
    for seed in seed_datasets(STARTED_AT):
        assert seed.curation == Curation(status="completed", provider="seed", detail=None)
        assert seed.created_at == STARTED_AT
