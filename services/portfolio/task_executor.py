"""
Task executor.
"""

from .execution_result import ExecutionResult


class TaskExecutor:

    def execute(
        self,
        task,
    ):

        return ExecutionResult(
            task_id=task.task_id,
            success=True,
            result=task.payload,
        )