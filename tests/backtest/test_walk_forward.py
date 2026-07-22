from services.backtest import (
    RollingWindowSplitter,
    StrategyTrainer,
    StrategyValidator,
    WalkForwardEngine,
    WalkForwardService,
    AnalysisWindow,
    DatasetSplitter,
)


def test_split_window():
    splitter = RollingWindowSplitter()

    result = splitter.split([1, 2, 3, 4], 2)

    assert result[0] == [1, 2]
    assert result[1] == [3, 4]


def test_strategy_trainer():
    trainer = StrategyTrainer()

    strategy = {"name": "test_strategy"}
    dataset = [1, 2, 3]

    result = trainer.train(strategy, dataset)

    assert result == strategy


def test_strategy_validator():
    validator = StrategyValidator()

    strategy = {"name": "test_strategy"}
    dataset = [1, 2, 3]

    result = validator.validate(strategy, dataset)

    assert result is True


def test_walk_forward_engine():
    splitter = RollingWindowSplitter()
    trainer = StrategyTrainer()
    validator = StrategyValidator()

    engine = WalkForwardEngine(splitter, trainer, validator)

    strategy = {"name": "test_strategy"}
    dataset = [1, 2, 3, 4]

    result = engine.run(strategy, dataset)

    assert result is True


def test_walk_forward_service():
    from services.backtest.rolling_optimizer import RollingOptimizer
    from services.backtest.out_of_sample_analyzer import OutOfSampleAnalyzer
    from services.backtest.walk_forward_runner import WalkForwardRunner
    from services.backtest.grid_search_optimizer import GridSearchOptimizer
    from services.backtest.parameter_space import ParameterSpace
    
    splitter = DatasetSplitter()
    optimizer = RollingOptimizer()
    analyzer = OutOfSampleAnalyzer()
    
    runner = WalkForwardRunner(splitter, optimizer, analyzer)
    service = WalkForwardService(runner)
    
    grid_search = GridSearchOptimizer()
    parameter_space = ParameterSpace({"ma": [5, 10]})
    
    result = service.execute(
        list(range(10)),
        0.7,
        grid_search,
        parameter_space,
        {"sharpe": 1.5},
    )
    
    assert result.parameters is not None
    assert result.performance["train_size"] == 7


def test_analysis_window():
    window = AnalysisWindow(
        training_start="2024-01-01",
        training_end="2024-06-30",
        validation_start="2024-07-01",
        validation_end="2024-12-31",
    )

    assert window.training_start == "2024-01-01"
    assert window.validation_end == "2024-12-31"


def test_dataset_splitter():

    train, test = DatasetSplitter().split(
        list(range(10)),
        0.7,
    )

    assert len(train) == 7

    assert len(test) == 3