from services.platform.finance import (
    FinancialWorldModel,
)


def test_world_model():

    model = FinancialWorldModel()

    model.update(
        "FED_RATE",
        5.25,
    )

    assert model.snapshot()["FED_RATE"] == 5.25