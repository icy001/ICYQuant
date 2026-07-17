from services.research import (
    Experiment,
    ExperimentRegistry,
    ExperimentService,
    ExperimentStatus,
)


def test_register_experiment():
    registry = ExperimentRegistry()

    experiment = Experiment(
        experiment_id="exp-001",
        name="Momentum Alpha",
        owner="research",
        status="CREATED",
    )

    registry.register(experiment)

    assert registry.get("exp-001") == experiment


def test_experiment_status_enum():
    assert ExperimentStatus.CREATED.value == "CREATED"
    assert ExperimentStatus.RUNNING.value == "RUNNING"
    assert ExperimentStatus.COMPLETED.value == "COMPLETED"
    assert ExperimentStatus.FAILED.value == "FAILED"


def test_experiment_service_create():
    registry = ExperimentRegistry()
    service = ExperimentService(registry)

    experiment = Experiment(
        experiment_id="exp-002",
        name="Value Strategy",
        owner="quant",
        status="CREATED",
    )

    result = service.create(experiment)

    assert result == experiment
    assert registry.get("exp-002") == experiment