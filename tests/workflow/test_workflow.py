from services.workflow import *


def test_workflow():
    repo = WorkflowRepository()
    service = WorkflowService(repo)

    workflow = WorkflowInstance(
        "WF001",
        "Settlement",
        WorkflowState.CREATED
    )

    result = service.start(workflow)

    assert result.state == WorkflowState.RUNNING
