from services.position import (
    PositionModel,
    PositionRepository,
)


def test_repository_model():
    repository = PositionRepository(
        session=None,
    )

    assert repository.model is PositionModel