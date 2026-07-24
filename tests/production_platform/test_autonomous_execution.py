from services.platform.execution import (
    ExecutionTask,
    GoalExecutionManager,
)


def test_execution_task():

    manager = GoalExecutionManager()

    manager.submit(
        ExecutionTask(
            "task-1",
            "BUY",
            "NVDA",
            {},
        )
    )

    assert len(
        manager.pending()
    ) == 1