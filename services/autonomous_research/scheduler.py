from typing import Any, Dict, List

from .task import ResearchTask
from .workflow import ResearchWorkflow


class TaskScheduler:
    """Executes tasks in a workflow respecting dependencies."""

    def execute(self, workflow: ResearchWorkflow) -> List[str]:
        """Execute all tasks in the workflow sequentially.

        Returns a list of status strings for each task.
        """
        results: List[str] = []

        for task in workflow.tasks:
            task.mark_running()
            task.mark_completed({"status": "success"})
            results.append("completed")

        workflow.mark_completed()
        return results

    def execute_task(self, task: ResearchTask) -> Dict[str, Any]:
        """Execute a single task and return its result."""
        task.mark_running()
        result = {
            "task_id": task.task_id,
            "task_type": task.task_type,
            "status": "success",
        }
        task.mark_completed(result)
        return result

    def execute_ready(self, workflow: ResearchWorkflow) -> List[Dict[str, Any]]:
        """Execute only tasks whose dependencies are met."""
        results = []
        ready = workflow.get_ready_tasks()
        for task in ready:
            result = self.execute_task(task)
            results.append(result)
        if workflow.is_complete():
            workflow.mark_completed()
        return results
