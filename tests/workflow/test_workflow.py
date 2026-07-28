from services.workflow import *


def test_workflow_engine():

    workflow = WorkflowDefinition(
        "WF001",
        "ORDER_FLOW",
        [
            WorkflowTask(
                "T001",
                "RISK_CHECK",
                "risk",
                "CREATED"
            )
        ]
    )

    service = WorkflowService(
        WorkflowEngine(
            TaskExecutor()
        ),
        WorkflowRepository()
    )

    result = service.start(
        workflow
    )

    assert result == WorkflowState.COMPLETED
