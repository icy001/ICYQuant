from services.research import (
    ObjectiveFunction,
    SearchSpace,
    OptimizationTrial,
    OptimizationResult,
    Optimizer,
    OptimizationService,
)


def test_objective():
    objective = ObjectiveFunction()

    score = objective.evaluate({"sharpe": 1.8})

    assert score == 1.8


def test_search_space():
    space = SearchSpace(
        parameters={
            "window": [10, 20, 30],
            "threshold": [0.3, 0.5, 0.7],
        }
    )

    assert "window" in space.parameters
    assert len(space.parameters["window"]) == 3


def test_optimization_trial():
    trial = OptimizationTrial(
        trial_id="trial-001",
        parameters={"window": 20, "threshold": 0.5},
    )

    assert trial.trial_id == "trial-001"
    assert trial.parameters["window"] == 20


def test_optimizer():
    optimizer = Optimizer()
    objective = ObjectiveFunction()

    trials = [
        {"sharpe": 1.2},
        {"sharpe": 1.8},
        {"sharpe": 1.5},
    ]

    result = optimizer.optimize(trials, objective)

    assert result.best_parameters["sharpe"] == 1.8


def test_optimization_service():
    optimizer = Optimizer()
    service = OptimizationService(optimizer)
    objective = ObjectiveFunction()

    trials = [
        {"sharpe": 1.0},
        {"sharpe": 2.0},
    ]

    result = service.run(trials, objective)

    assert result.best_parameters["sharpe"] == 2.0