from services.backtest import (
    ParameterOptimizer,
    StrategyEvaluator,
    ParameterRange,
    SearchSpace,
    OptimizationResult,
    OptimizationService,
    ParameterSpace,
    GridSearchOptimizer,
)


def test_optimizer():
    optimizer = ParameterOptimizer(StrategyEvaluator())

    result = optimizer.optimize(
        [
            {"score": 0.5},
            {"score": 0.8},
        ]
    )

    assert result.score == 0.8


def test_strategy_evaluator():
    evaluator = StrategyEvaluator()

    result = evaluator.evaluate({"score": 0.75})

    assert result == 0.75


def test_strategy_evaluator_default():
    evaluator = StrategyEvaluator()

    result = evaluator.evaluate({})

    assert result == 0


def test_parameter_range():
    param = ParameterRange(name="window_size", values=[50, 100, 200])

    assert param.name == "window_size"
    assert param.values == [50, 100, 200]


def test_search_space():
    params = [
        ParameterRange(name="param1", values=[1, 2]),
        ParameterRange(name="param2", values=[3, 4]),
    ]

    space = SearchSpace(params)

    combinations = space.combinations()

    assert len(combinations) == 4


def test_optimization_result():
    result = OptimizationResult(parameters={"alpha": 0.1}, score=0.85)

    assert result.parameters == {"alpha": 0.1}
    assert result.score == 0.85


def test_optimization_service():
    from services.backtest.optimization_repository import OptimizationRepository
    from services.backtest.optimization_runner import OptimizationRunner
    
    runner = OptimizationRunner(OptimizationRepository())
    service = OptimizationService(runner)

    result = service.evaluate({"alpha": 0.1}, 0.9)

    assert result.score == 0.9
    assert result.parameters == {"alpha": 0.1}


def test_optimizer_empty():
    optimizer = ParameterOptimizer(StrategyEvaluator())

    result = optimizer.optimize([])

    assert result is None


def test_grid_search():

    space = ParameterSpace(
        {
            "ma": [
                5,
                10,
            ],
            "stop": [
                1,
                2,
            ],
        }
    )


    result = list(
        GridSearchOptimizer().generate(
            space
        )
    )


    assert len(
        result
    ) == 4