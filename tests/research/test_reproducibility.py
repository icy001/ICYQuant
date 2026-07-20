from services.research import (
    EnvironmentSnapshot,
    ExperimentConfiguration,
    ExperimentManifest,
    SnapshotManager,
    ReproducibilityValidator,
    ReproducibilityService,
)


def test_snapshot_creation():
    manager = SnapshotManager()

    manifest = ExperimentManifest(
        experiment_id="exp-001",
        dataset_version="v1",
        strategy_version="v2",
        environment=EnvironmentSnapshot(
            python_version="3.12",
            platform="linux",
            timezone="UTC",
        ),
        configuration=ExperimentConfiguration(
            config_version="v1",
            values={},
        ),
    )

    snapshot = manager.create(manifest)

    assert snapshot.experiment_id == "exp-001"


def test_environment_snapshot():
    env = EnvironmentSnapshot(
        python_version="3.11",
        platform="windows",
        timezone="Asia/Shanghai",
    )

    assert env.python_version == "3.11"
    assert env.platform == "windows"


def test_experiment_configuration():
    config = ExperimentConfiguration(
        config_version="v2",
        values={"window": 20, "threshold": 0.5},
    )

    assert config.config_version == "v2"
    assert "window" in config.values


def test_reproducibility_validator():
    validator = ReproducibilityValidator()

    manifest = ExperimentManifest(
        experiment_id="exp-002",
        dataset_version="v1",
        strategy_version="v1",
        environment=EnvironmentSnapshot("3.12", "linux", "UTC"),
        configuration=ExperimentConfiguration("v1", {}),
    )

    result = validator.validate(manifest)

    assert result is True


def test_reproducibility_service():
    manager = SnapshotManager()
    validator = ReproducibilityValidator()
    service = ReproducibilityService(manager, validator)

    manifest = ExperimentManifest(
        experiment_id="exp-003",
        dataset_version="v1",
        strategy_version="v1",
        environment=EnvironmentSnapshot("3.12", "linux", "UTC"),
        configuration=ExperimentConfiguration("v1", {}),
    )

    snapshot = service.register(manifest)

    assert snapshot.experiment_id == "exp-003"