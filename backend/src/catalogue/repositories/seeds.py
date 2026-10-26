from datetime import datetime

from catalogue.domain.models import Curation, Dataset

# The brief curated these by hand, so crediting either provider would misreport where they came
# from.
_HAND_CURATED = Curation(status="completed", provider="seed", detail=None)


def seed_datasets(created_at: datetime) -> tuple[Dataset, ...]:
    """The brief's three sample entries, which keep the catalogue from starting empty.

    Tags, their order and the summaries are the brief's own. The keyword provider's golden cases
    curate the same inputs differently, and that is intended.
    """
    return (
        Dataset(
            id="1",
            name="Customer Transactions",
            owner="Finance Team",
            description=(
                "Contains daily transaction records including transaction ID, customer ID, "
                "amount, currency, and timestamp."
            ),
            tags=("finance", "transactions", "PII", "daily"),
            summary=(
                "A daily feed of customer transaction records covering amounts, currencies, "
                "and timestamps."
            ),
            curation=_HAND_CURATED,
            created_at=created_at,
        ),
        Dataset(
            id="2",
            name="Product Inventory",
            owner="Operations Team",
            description=(
                "Snapshot of warehouse stock levels by SKU, including product name, quantity on "
                "hand, and reorder threshold."
            ),
            tags=("inventory", "operations", "warehouse"),
            summary=(
                "A warehouse snapshot tracking stock levels and reorder thresholds per product SKU."
            ),
            curation=_HAND_CURATED,
            created_at=created_at,
        ),
        Dataset(
            id="3",
            name="Employee Directory",
            owner="HR Team",
            description=(
                "List of current employees with name, department, role, and office location. "
                "Updated weekly."
            ),
            tags=("HR", "PII", "employees", "weekly"),
            summary=(
                "A weekly-refreshed directory of employees including role, department, and "
                "location."
            ),
            curation=_HAND_CURATED,
            created_at=created_at,
        ),
    )
