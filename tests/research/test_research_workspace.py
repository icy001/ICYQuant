from datetime import datetime

from services.research import (
    ResearchProject,
    ResearchRepository,
)


def test_create_project():

    project = ResearchProject(
        "P001",
        "Alpha Research",
        "Factor research",
        datetime.utcnow(),
        "ACTIVE",
    )

    repository = ResearchRepository()

    repository.save(
        project
    )

    result = repository.get(
        "P001"
    )

    assert result.name == "Alpha Research"