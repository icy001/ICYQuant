from services.position import *


def test_position_service():

    repository = PositionRepository()

    manager = PositionManager(
        repository
    )

    service = PositionService(
        manager
    )

    position = Position(
        "POS001",
        "ACC001",
        "PF001",
        "NVDA",
        100,
        150,
        PositionSide.LONG
    )

    service.create_position(
        position
    )

    result = service.query_position(
        "POS001"
    )

    assert result.symbol == "NVDA"