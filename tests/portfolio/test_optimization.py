from services.portfolio import (
    PortfolioOptimizer,
    OptimizationValidator,
    PortfolioOptimizationEngine,
    OptimizationService,
    OptimizationObjective,
    AllocationConstraint,
    OptimizationResult,
)


def test_optimizer():
    optimizer = PortfolioOptimizer()

    result = optimizer.optimize(
        [
            "AAPL",
            "MSFT",
        ],
        "MAX_SHARPE",
    )

    assert len(result) == 2


def test_optimizer_three_assets():
    optimizer = PortfolioOptimizer()

    result = optimizer.optimize(
        [
            "AAPL",
            "MSFT",
            "GOOG",
        ],
        "MAX_SHARPE",
    )

    assert len(result) == 3
    assert all(abs(v - 1/3) < 0.0001 for v in result.values())


def test_optimization_validator():
    validator = OptimizationValidator()

    weights = {"AAPL": 0.5, "MSFT": 0.5}

    assert validator.validate(weights)


def test_optimization_validator_invalid():
    validator = OptimizationValidator()

    weights = {"AAPL": 0.6, "MSFT": 0.5}

    assert not validator.validate(weights)


def test_optimization_engine():
    optimizer = PortfolioOptimizer()
    validator = OptimizationValidator()
    engine = PortfolioOptimizationEngine(optimizer, validator)

    result = engine.run(["AAPL", "MSFT"], OptimizationObjective.MAX_SHARPE)

    assert isinstance(result, OptimizationResult)
    assert len(result.weights) == 2


def test_optimization_service():
    optimizer = PortfolioOptimizer()
    validator = OptimizationValidator()
    engine = PortfolioOptimizationEngine(optimizer, validator)
    service = OptimizationService(engine)

    result = service.optimize(["AAPL", "MSFT"], OptimizationObjective.MAX_SHARPE)

    assert isinstance(result, OptimizationResult)


def test_optimization_objective():
    assert OptimizationObjective.MAX_RETURN.value == "MAX_RETURN"
    assert OptimizationObjective.MIN_RISK.value == "MIN_RISK"
    assert OptimizationObjective.MAX_SHARPE.value == "MAX_SHARPE"


def test_allocation_constraint():
    constraint = AllocationConstraint(
        asset_class="EQUITY",
        min_weight=0.1,
        max_weight=0.8,
    )

    assert constraint.asset_class == "EQUITY"
    assert constraint.min_weight == 0.1
    assert constraint.max_weight == 0.8