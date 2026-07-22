from datetime import datetime

from services.research import (
    NotebookRuntime,
    NotebookExecutor,
    WorkflowScheduler,
    ResearchPipeline,
    ResearchNotebook,
    ResearchWorkflow,
)


def test_pipeline():

    notebook = ResearchNotebook(
        "NB001",
        "Factor Notebook",
        "P001",
        datetime.utcnow(),
        "# notebook",
    )

    workflow = ResearchWorkflow(
        "WF001",
        "P001",
        "NB001",
        "CREATED",
    )

    pipeline = ResearchPipeline(
        WorkflowScheduler(),
        NotebookExecutor(
            NotebookRuntime(),
        ),
    )

    result = pipeline.execute(
        workflow,
        notebook,
    )

    assert result["workflow"].state == "COMPLETED"