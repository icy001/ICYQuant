from services.platform.workflow import (
    WorkflowDefinition,
    WorkflowEngine,
    StepExecutor,
)


def test_workflow():

    wf = WorkflowDefinition(
        "wf",
        "Research",
        ["research"],
    )

    engine = WorkflowEngine(
        StepExecutor()
    )

    result = engine.run(
        wf,
        {},
    )

    assert len(result) == 1