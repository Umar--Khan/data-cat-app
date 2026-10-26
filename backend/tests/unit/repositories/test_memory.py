from collections.abc import Coroutine
from datetime import UTC, datetime
from typing import Any

import pytest
from hypothesis import strategies as st
from hypothesis.stateful import RuleBasedStateMachine, invariant, precondition, rule

from catalogue.domain.errors import DatasetNotFoundError
from catalogue.domain.models import CuratedDataset, Curation, Dataset, NewDataset
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
KEYWORD_CURATION = Curation.completed(
    "keyword", ("trading", "finance"), "A daily export of confirmed trades."
)


def run[T](call: Coroutine[Any, Any, T]) -> T:
    """Finish a store call in one step, failing if it ever suspends.

    That the in-memory store never awaits inside a method is what makes each call atomic on the
    event loop (docs/architecture.md, State and concurrency), so every test here checks it.
    """
    try:
        call.send(None)
    except StopIteration as finished:
        result: T = finished.value
        return result
    call.close()
    raise AssertionError("The in-memory store awaited inside a method")


@pytest.fixture
def repository() -> InMemoryDatasetRepository:
    return InMemoryDatasetRepository(seed_datasets(STARTED_AT))


def add_dataset(repository: InMemoryDatasetRepository) -> Dataset:
    return run(repository.add(CuratedDataset(TRADE_CONFIRMATIONS, KEYWORD_CURATION, CREATED_AT)))


def ids(repository: InMemoryDatasetRepository) -> list[str]:
    return [dataset.id for dataset in run(repository.list())]


def test_lists_the_initial_records_in_their_order(repository: InMemoryDatasetRepository) -> None:
    assert run(repository.list()) == seed_datasets(STARTED_AT)


def test_add_stores_the_record_under_the_id_after_the_seeds_and_returns_it(
    repository: InMemoryDatasetRepository,
) -> None:
    dataset = add_dataset(repository)

    assert dataset == Dataset(
        id="4",
        name="Trade Confirmations",
        owner="Middle Office",
        description=TRADE_CONFIRMATIONS.description,
        curation=KEYWORD_CURATION,
        created_at=CREATED_AT,
    )
    assert run(repository.list())[-1] == dataset


def test_lists_in_insertion_order(repository: InMemoryDatasetRepository) -> None:
    add_dataset(repository)
    add_dataset(repository)

    assert ids(repository) == ["1", "2", "3", "4", "5"]


def test_delete_returns_the_removed_record_and_drops_it_from_the_list(
    repository: InMemoryDatasetRepository,
) -> None:
    first_seed = run(repository.list())[0]

    assert run(repository.delete("1")) == first_seed
    assert ids(repository) == ["2", "3"]


def test_an_id_is_never_reused_after_its_record_is_deleted(
    repository: InMemoryDatasetRepository,
) -> None:
    assert add_dataset(repository).id == "4"
    run(repository.delete("4"))

    assert add_dataset(repository).id == "5"


def test_deleting_an_unknown_id_raises_with_that_id_and_changes_nothing(
    repository: InMemoryDatasetRepository,
) -> None:
    with pytest.raises(DatasetNotFoundError) as excinfo:
        run(repository.delete("99"))

    assert excinfo.value.dataset_id == "99"
    assert ids(repository) == ["1", "2", "3"]


def test_deleting_the_same_id_twice_raises(repository: InMemoryDatasetRepository) -> None:
    run(repository.delete("2"))

    with pytest.raises(DatasetNotFoundError):
        run(repository.delete("2"))


def test_list_is_a_snapshot_that_later_writes_do_not_change(
    repository: InMemoryDatasetRepository,
) -> None:
    snapshot = run(repository.list())

    add_dataset(repository)
    run(repository.delete("1"))

    assert [dataset.id for dataset in snapshot] == ["1", "2", "3"]


def test_an_empty_repository_starts_at_id_1() -> None:
    repository = InMemoryDatasetRepository()

    assert run(repository.list()) == ()
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

        assert run(self.repository.delete(dataset_id)).id == dataset_id
        self.live.remove(dataset_id)
        self.deleted.append(dataset_id)

    @precondition(lambda machine: bool(machine.deleted))
    @rule(data=st.data())
    def delete_again(self, data: st.DataObject) -> None:
        dataset_id = data.draw(st.sampled_from(self.deleted))

        with pytest.raises(DatasetNotFoundError):
            run(self.repository.delete(dataset_id))

    @invariant()
    def lists_live_records_in_insertion_order(self) -> None:
        assert ids(self.repository) == self.live


TestRepositoryStateMachine = RepositoryStateMachine.TestCase
