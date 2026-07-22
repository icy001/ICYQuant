from datetime import datetime

from services.research import (
    ResearchArtifact,
    ArtifactRepository,
    ArtifactStorage,
    ArtifactVersionManager,
    ArtifactLifecycle,
)


def test_publish_artifact():

    artifact = ResearchArtifact(
        "ART001",
        "P001",
        "NOTEBOOK",
        "Momentum Notebook",
        "v1",
        datetime.utcnow(),
        "/artifacts/ART001",
    )

    lifecycle = ArtifactLifecycle(
        ArtifactRepository(),
        ArtifactStorage(),
        ArtifactVersionManager(),
    )

    result = lifecycle.publish(
        artifact,
        "# notebook",
    )

    assert result.artifact_id == "ART001"