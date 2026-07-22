from services.backtest import (
    DependencyValidator,
    ModuleHealthChecker,
)


def test_platform_bootstrap():

    validator = DependencyValidator()

    checker = ModuleHealthChecker()

    assert validator.validate(
        [1, 2, 3]
    )

    result = checker.check(
        [
            "Replay",
            "Execution",
        ]
    )

    assert result["Replay"] == "HEALTHY"