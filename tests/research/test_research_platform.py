from services.research import (
    ResearchDependencyValidator,
    ResearchModuleHealthChecker,
)


def test_platform_bootstrap():

    validator = ResearchDependencyValidator()

    checker = ResearchModuleHealthChecker()

    assert validator.validate(
        [1, 2, 3]
    )

    result = checker.check(
        [
            "FeatureStore",
            "FactorEngine",
            "Notebook",
        ]
    )

    assert result["FeatureStore"] == "HEALTHY"