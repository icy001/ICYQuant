from services.position import (
    create_position_updated,
)


def test_position_event():
    event = create_position_updated(
        account_id="ACC",
        symbol="AAPL",
        quantity="100",
        version=2,
    )

    assert event.version == 2
    assert event.event_id