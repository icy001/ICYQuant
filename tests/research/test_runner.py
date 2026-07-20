import pytest

from services.research import (
    Experiment,
    ExperimentContext,
    ExperimentRunner,
    ExperimentController,
    RunnerService,
)


@pytest.mark.asyncio
async def test_runner():
    runner = ExperimentRunner()

    experiment = Experiment(
        experiment_id="exp-001",
        name="Momentum",
        owner="research",
        status="CREATED",
    )

    context = ExperimentContext(
        dataset="NASDAQ",
        parameter_version="v1",
        strategy_id="momentum",
    )

    result = await runner.run(experiment, context)

    assert result.status == "COMPLETED"


@pytest.mark.asyncio
async def test_controller():
    controller = ExperimentController()
    runner = ExperimentRunner()

    experiment = Experiment(
        experiment_id="exp-002",
        name="Value",
        owner="quant",
        status="CREATED",
    )

    context = ExperimentContext(
        dataset="NYSE",
        parameter_version="v2",
        strategy_id="value",
    )

    result = await controller.execute(runner, experiment, context)

    assert result.experiment_id == "exp-002"
    assert result.status == "COMPLETED"


@pytest.mark.asyncio
async def test_runner_service():
    controller = ExperimentController()
    service = RunnerService(controller)
    runner = ExperimentRunner()

    experiment = Experiment(
        experiment_id="exp-003",
        name="Quality",
        owner="research",
        status="CREATED",
    )

    context = ExperimentContext(
        dataset="SP500",
        parameter_version="v3",
        strategy_id="quality",
    )

    result = await service.start(runner, experiment, context)

    assert result.experiment_id == "exp-003"
    assert result.status == "COMPLETED"