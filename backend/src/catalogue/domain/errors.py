class DatasetNotFoundError(LookupError):
    """No dataset has this id, either because it never existed or because it was deleted.

    Ids are never reused, so a deleted id stays unknown for the life of the process.
    """

    def __init__(self, dataset_id: str) -> None:
        super().__init__(f"No dataset has id {dataset_id!r}")
        self.dataset_id = dataset_id
