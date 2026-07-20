from services.backtest import (
    RollingWindowSplitter,
    StrategyTrainer,
    StrategyValidator,
    WalkForwardEngine,
    WalkForwardService,
    AnalysisWindow,
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
    splitter = RollingWindowSplitter()
    trainer = StrategyTrainer()
    validator = StrategyValidator()

    engine = WalkForwardEngine(splitter, trainer, validator)
    service = WalkForwardService(engine)

    strategy = {"name": "test_strategy"}
    dataset = [1, 2, 3, 4]

    result = service.analyze(strategy, dataset)

    assert result is True


def test_analysis_window():
    window = AnalysisWindow(
        training_start="2024-01-01",
        training_end="2024-06-30",
        validation_start="2024-07-01",
        validation_end="2024-12-31",
    )

    assert window.training_start == "2024-01-01"
    assert window.validation_end == "2024-12-31"