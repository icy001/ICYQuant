from services.risk import (
    Scenario,
    ScenarioRepository,
    ScenarioCalculator,
)


def test_scenario():
    repository = ScenarioRepository()

    repository.save(
        Scenario(
            "S001",
            "RATE_UP",
            {
                "AAPL": -0.05
            },
        )
    )

    scenario = repository.load(
        "S001"
    )

    result = ScenarioCalculator().calculate(
        {
            "AAPL": 100000
        },
        scenario,
    )

    assert result["AAPL"] == 95000