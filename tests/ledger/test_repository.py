from services.ledger import (
    JournalModel,
    JournalRepository,
)


def test_repository_model():
    repository = JournalRepository(
        session=None,
    )

    assert repository.model is JournalModel