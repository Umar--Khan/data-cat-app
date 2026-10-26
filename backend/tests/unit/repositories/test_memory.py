from datetime import UTC, datetime

import pytest
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from catalogue.domain.errors import DatasetNotFoundError
from catalogue.domain.models import Curation, Dataset, NewDataset
from catalogue.repositories.base import DatasetRepository
from catalogue.repositories.memory import InMemoryDatasetRepository
from catalogue.repositories.seeds import seed_datasets

STARTED_AT = datetime(2026, 10, 25, 9, 0, tzinfo=UTC)
CREATED_AT = datetime(2026, 10, 25, 9, 30, tzinfo=UTC)
TRADE_CONFIRMATIONS = NewDataset(
    name="Trade Confirmations",
    owner="Middle Office",
    description=(
        "Daily export of confirmed trades including instrument type, counterparty, notional "
        "value, and settlement date."
    ),
)
KEYWORD_CURATION = Curation(status="completed", provider="keyword", detail=None)


@pytest.fixture
def repository() -> DatasetRepository:
    return InMemoryDatasetRepository(seed_datasets(STARTED_AT))


def add_dataset(repository: DatasetRepository) -> Dataset:
    return repository.add(
        TRADE_CONFIRMATIONS,
        tags=("trading", "finance"),
        summary="A daily export of confirmed trades.",
        curation=KEYWORD_CURATION,
        created_at=CREATED_AT,
    )


def ids(repository: DatasetRepository) -> list[str]:
    return [dataset.id for dataset in repository.list()]


def test_lists_the_initial_records_in_their_order(repository: DatasetRepository) -> None:
    assert repository.list() == seed_datasets(STARTED_AT)


def test_add_stores_the_record_under_the_id_after_the_seeds_and_returns_it(
    repository: DatasetRepository,
) -> None:
    dataset = add_dataset(repository)

    assert dataset == Dataset(
        id="4",
        name="Trade Confirmations",
        owner="Middle Office",
        description=TRADE_CONFIRMATIONS.description,
        tags=("trading", "finance"),
        summary="A daily export of confirmed trades.",
        curation=KEYWORD_CURATION,
        created_at=CREATED_AT,
    )
    assert repository.list()[-1] == dataset


def test_lists_in_insertion_order(repository: DatasetRepository) -> None:
    add_dataset(repository)
    add_dataset(repository)

    assert ids(repository) == ["1", "2", "3", "4", "5"]


def test_delete_returns_the_removed_record_and_drops_it_from_the_list(
    repository: DatasetRepository,
) -> None:
    first_seed = repository.list()[0]

    assert repository.delete("1") == first_seed
    assert ids(repository) == ["2", "3"]


def test_an_id_is_never_reused_after_its_record_is_deleted(repository: DatasetRepository) -> None:
    assert add_dataset(repository).id == "4"
    repository.delete("4")

    assert add_dataset(repository).id == "5"


def test_deleting_an_unknown_id_raises_with_that_id_and_changes_nothing(
    repository: DatasetRepository,
) -> None:
    with pytest.raises(DatasetNotFoundError) as excinfo:
        repository.delete("99")

    assert excinfo.value.dataset_id == "99"
    assert ids(repository) == ["1", "2", "3"]


def test_deleting_the_same_id_twice_raises(repository: DatasetRepository) -> None:
    repository.delete("2")

    with pytest.raises(DatasetNotFoundError):
        repository.delete("2")


def test_list_is_a_snapshot_that_later_writes_do_not_change(
    repository: DatasetRepository,
) -> None:
    snapshot = repository.list()

    add_dataset(repository)
    repository.delete("1")

    assert [dataset.id for dataset in snapshot] == ["1", "2", "3"]


def test_an_empty_repository_starts_at_id_1() -> None:
    repository = InMemoryDatasetRepository()

    assert repository.list() == ()
    assert add_dataset(repository).id == "1"


def test_ids_continue_after_the_highest_initial_id() -> None:
    seeds = seed_datasets(STARTED_AT)
    repository = InMemoryDatasetRepository([seeds[2], seeds[0]])

    assert add_dataset(repository).id == "4"


class RepositoryStateMachine(RuleBasedStateMachine):
    """Any interleaving of adds and deletes keeps ids unique and the list in insertion order.

    Deleting the newest record and then adding is the case a counter derived from the current
    records would get wrong.
    """

    def __init__(self) -> None:
        super().__init__()
        self.repository = InMemoryDatasetRepository(seed_datasets(STARTED_AT))
        self.live = ["1", "2", "3"]
        self.deleted: list[str] = []

    @rule()
    def add(self) -> None:
        dataset_id = add_dataset(self.repository).id

        assert dataset_id not in self.live
        assert dataset_id not in self.deleted
        self.live.append(dataset_id)

    @precondition(lambda machine: bool(machine.live))
    @rule(data=st.data())
    def delete(self, data: st.DataObject) -> None:
        dataset_id = data.draw(st.sampled_from(self.live))

        assert self.repository.delete(dataset_id).id == dataset_id
        self.live.remove(dataset_id)
        self.deleted.append(dataset_id)

    @precondition(lambda machine: bool(machine.deleted))
    @rule(data=st.data())
    def delete_again(self, data: st.DataObject) -> None:
        dataset_id = data.draw(st.sampled_from(self.deleted))

        with pytest.raises(DatasetNotFoundError):
            self.repository.delete(dataset_id)

    @invariant()
    def lists_live_records_in_insertion_order(self) -> None:
        assert ids(self.repository) == self.live


TestRepositoryStateMachine = RepositoryStateMachine.TestCase
