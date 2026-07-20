from services.research import (
    ArtifactRegistry,
    ResearchArtifact,
    ArtifactMetadata,
    ArtifactStorage,
    ArtifactService,
    ArtifactLifecycle,
)


def test_register_artifact():
    registry = ArtifactRegistry()

    artifact = ResearchArtifact(
        artifact_id="artifact-001",
        experiment_id="exp-001",
        artifact_type="REPORT",
        location="/reports/report.pdf",
    )

    registry.register(artifact)

    assert registry.get("artifact-001") == artifact


def test_research_artifact():
    artifact = ResearchArtifact(
        artifact_id="artifact-002",
        experiment_id="exp-002",
        artifact_type="MODEL",
        location="/models/model.pkl",
    )

    assert artifact.artifact_id == "artifact-002"
    assert artifact.artifact_type == "MODEL"


def test_artifact_metadata():
    metadata = ArtifactMetadata(
        version="v1",
        created_by="researcher",
        tags=["model", "ml", "alpha"],
    )

    assert metadata.version == "v1"
    assert "model" in metadata.tags


def test_artifact_storage():
    storage = ArtifactStorage()

    artifact = ResearchArtifact(
        artifact_id="artifact-003",
        experiment_id="exp-003",
        artifact_type="CHART",
        location="/charts/chart.png",
    )

    location = storage.save(artifact)

    assert location == "/charts/chart.png"


def test_artifact_service():
    registry = ArtifactRegistry()
    service = ArtifactService(registry)

    artifact = ResearchArtifact(
        artifact_id="artifact-004",
        experiment_id="exp-004",
        artifact_type="LOG",
        location="/logs/experiment.log",
    )

    result = service.register(artifact)

    assert result == artifact
    assert registry.get("artifact-004") == artifact


def test_artifact_lifecycle():
    lifecycle = ArtifactLifecycle()

    artifact = ResearchArtifact(
        artifact_id="artifact-005",
        experiment_id="exp-005",
        artifact_type="CONFIG",
        location="/config/config.yaml",
    )

    archived = lifecycle.archive(artifact)

    assert archived == artifact