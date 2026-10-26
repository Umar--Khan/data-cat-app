from datetime import datetime

from catalogue.domain.models import Curation, Dataset


def _hand_curated(tags: tuple[str, ...], summary: str) -> Curation:
    # The brief curated these by hand, so crediting either provider would misreport where they
    # came from.
    return Curation.completed("seed", tags, summary)


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
            curation=_hand_curated(
                ("finance", "transactions", "PII", "daily"),
                "A daily feed of customer transaction records covering amounts, currencies, "
                "and timestamps.",
            ),
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
            curation=_hand_curated(
                ("inventory", "operations", "warehouse"),
                "A warehouse snapshot tracking stock levels and reorder thresholds per product "
                "SKU.",
            ),
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
            curation=_hand_curated(
                ("HR", "PII", "employees", "weekly"),
                "A weekly-refreshed directory of employees including role, department, and "
                "location.",
            ),
            created_at=created_at,
        ),
    )
