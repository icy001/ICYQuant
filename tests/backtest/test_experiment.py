from services.backtest import (
    BacktestExperiment,
    ExperimentRepository,
    ExperimentConfig,
    ExperimentResult,
    ExperimentService,
    ExperimentComparator,
)


def test_experiment_repository():
    repository = ExperimentRepository()

    experiment = BacktestExperiment(
        experiment_id="exp-001",
        strategy_id="momentum",
        version="v1",
    )

    repository.save(experiment)

    assert repository.get("exp-001") == experiment


def test_experiment_not_found():
    repository = ExperimentRepository()

    assert repository.get("exp-999") is None


def test_backtest_experiment():
    experiment = BacktestExperiment(
        experiment_id="exp-002",
        strategy_id="mean_reversion",
        version="v2",
    )

    assert experiment.experiment_id == "exp-002"
    assert experiment.strategy_id == "mean_reversion"
    assert experiment.version == "v2"


def test_experiment_config():
    config = ExperimentConfig(
        parameters={"window_size": 100},
        dataset="SPX_1min",
        initial_cash=1000000,
    )

    assert config.parameters == {"window_size": 100}
    assert config.dataset == "SPX_1min"
    assert config.initial_cash == 1000000


def test_experiment_result():
    result = ExperimentResult(
        experiment_id="exp-003",
        return_rate=0.25,
        sharpe_ratio=1.8,
    )

    assert result.experiment_id == "exp-003"
    assert result.return_rate == 0.25
    assert result.sharpe_ratio == 1.8


def test_experiment_service():
    repository = ExperimentRepository()
    service = ExperimentService(repository)

    experiment = BacktestExperiment(
        experiment_id="exp-004",
        strategy_id="factor",
        version="v1",
    )

    result = service.create(experiment)

    assert result == experiment
    assert repository.get("exp-004") == experiment


def test_experiment_comparator():
    comparator = ExperimentComparator()

    results = [
        ExperimentResult(experiment_id="exp-001", return_rate=0.15, sharpe_ratio=1.2),
        ExperimentResult(experiment_id="exp-002", return_rate=0.25, sharpe_ratio=1.8),
        ExperimentResult(experiment_id="exp-003", return_rate=0.20, sharpe_ratio=1.5),
    ]

    best = comparator.compare(results)

    assert best.experiment_id == "exp-002"
    assert best.return_rate == 0.25