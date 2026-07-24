from services.platform.risk import (
    DrawdownController,
)


def test_drawdown():

    controller = DrawdownController()

    result = controller.check(
        80,
        100,
    )

    assert result["drawdown"] == 0.2