from services.risk import (
    StressScenario,
    StressScenarioRepository,
    StressCalculator,
    StressEngine,
)


def test_stress():
    repository = StressScenarioRepository()

    repository.save(
        StressScenario(
            "SCENARIO-001",
            "Market Crash",
            -0.1,
        )
    )

    engine = StressEngine(
        repository,
        StressCalculator(),
    )

    result = engine.run(
        "SCENARIO-001",
        {
            "AAPL": 100000
        },
    )

    assert result.after_value == 90000